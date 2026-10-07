/** Host-private claim/request recorder. Python remains the durable authority. */
import type { Agent } from '@deepseek-ai/dsh-agent';
import type { GenerateOptions } from '@deepseek-ai/dsh-llm';
import { createUserMessage } from '@deepseek-ai/dsh-llm';
import type { Context } from '@deepseek-ai/cordis';
import { SessionId, SessionLogOffset } from '@deepseek-ai/dsh-session';
import type {} from '@deepseek-ai/dsh-session-persistence';
import { SessionBindings, createBoundRootAgent } from './session-binding.js';
import { dispatchRole, registerCode2PaperSpawn } from './role-dispatch.js';
import { installRequestAccounting, DispatchAuthorizations, gatedAdapter, type GatedAdapterSource } from './request-accounting.js';
import { installNativeWriter, compareWriterRequest, type WriterInputRefV1, type WriterWireProjectionV1 } from './writer-request.js';
import { TerminalArgumentCapture, type CapturedRawArguments } from './terminal-result.js';
import { serialExecutionPolicy } from './execution-policy.js';
import { randomUUID } from 'node:crypto';
import type { ClaimRecorder, ClaimRequest, ClaimReceipt, GrantedTask, CallerRef } from './session-binding.js';
import type { RequestRecorder, RequestReserveRequest, ReservationReceipt, RequestDispatchRequest,
  DispatchReceipt, RequestSettleRequest, SettlementReceipt, RequestMarkUnknownRequest, UnknownReceipt } from './request-contract.js';
import { REQUEST_CONTRACT_VERSION } from './request-contract.js';
import { digestSupportedRequest, type DispatchAuthorization } from './request-accounting.js';
import { KernelClient } from './kernel-client.js';
import { MaterialRestoration, installMaterialRestoration, type MaterialScope, type RequiredMaterial } from './context-policy.js';
import { installScopedRead } from './task-tools.js';
import { observeLocalWriterWire } from './step-renderer.js';
import { EpochCompactionEngine, type CompactionInput, type SettledCompaction } from './epoch-compaction.js';
import type { BasicCompactionConfig } from '@deepseek-ai/dsh-compaction-basic';
import { decodeWire, isObject, type JsonObject, type JsonValue } from './wire.js';

export interface KernelTaskScope {
  readonly execution_id: string;
  readonly task_id: string;
  readonly task_epoch: number;
}

export interface KernelAuthorityConfig {
  readonly scope: KernelTaskScope;
  readonly caller: CallerRef;
  readonly owner: string;
  readonly compositionDigest: string;
  readonly contractRef: JsonObject;
  readonly budgetRef: JsonObject;
  readonly accountingVersion?: 'c2p-dsh-task-loop-v1' | 'c2p-dsh-task-loop-v2';
  /** Exact frozen host provider configuration; only V2 uses render-only observation. */
  readonly providerConfig?: JsonObject;
}

function object(value: JsonValue): JsonObject {
  if (!isObject(value)) throw new Error('kernel_receipt_invalid');
  return value;
}
function text(value: JsonValue | undefined): string {
  if (typeof value !== 'string' || value === '') throw new Error('kernel_receipt_invalid');
  return value;
}
function count(value: JsonValue | undefined): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0) throw new Error('kernel_receipt_invalid');
  return value;
}

function secondary(primary: unknown, stage: string, failure: unknown): void {
  if (!(primary instanceof Error)) return;
  const target=primary as Error & {cleanupFailures?: {stage: string; message: string}[]};
  target.cleanupFailures ??= [];
  target.cleanupFailures.push({stage,message:failure instanceof Error ? failure.message : String(failure)});
}

export class KernelAuthority implements ClaimRecorder, RequestRecorder {
  private claimFact: JsonObject | undefined;
  private claimReceipt: ClaimReceipt | undefined;
  private reservationFact: JsonObject | undefined;
  private assemblyDigest: string | undefined;
  private adapterFinish: string | undefined;
  private usageRecorded=false;
  private quiescenceRef: JsonObject | undefined;
  private rejectedUnknownTool=false;
  private nativeTerminalObserved=false;
  private childSessionId: string | undefined;
  private childAgent: Agent | undefined;
  private recoveryOnly=false;
  private materialPolicy: MaterialRestoration | undefined;
  private readonly epochStop=new AbortController();
  private measuredSequence=0;
  private auxiliaryBinding:JsonObject|undefined;
  private auxiliaryConfig:JsonObject|undefined;
  private observedUsage:{inputTokens:number;outputTokens:number}|undefined;
  private readonly auxiliarySessions:JsonObject[]=[];
  private readonly auxiliaryChildren=new Map<string,number>();
  private readonly localSequences=new Map<string,number>();
  private readonly completedSteps=new Set<string>();
  private currentStepProof: JsonObject | undefined;
  private readonly measuredSteps=new Map<string,{readonly ref:JsonObject;readonly sequence:number;readonly localSequence:number}>();
  private readonly requests=new Map<string,{readonly fact:JsonObject;readonly digest:string}>();
  readonly kernel: KernelClient;
  readonly config: KernelAuthorityConfig;

  constructor(kernel: KernelClient, config: KernelAuthorityConfig) {
    this.kernel=kernel; this.config=config;
  }

  private scope(): JsonObject { return { ...this.config.scope }; }

  async claim(request: ClaimRequest, options?: { readonly signal?: AbortSignal }): Promise<ClaimReceipt> {
    if (this.recoveryOnly) throw new Error('kernel_recovery_has_no_model_permission');
    if (request.task.taskId !== this.config.scope.task_id || request.task.epoch !== this.config.scope.task_epoch
      || request.caller.executionId !== this.config.caller.executionId || request.caller.runId !== this.config.caller.runId
      || request.caller.hostGeneration !== this.config.caller.hostGeneration) throw new Error('kernel_claim_scope_mismatch');
    if (request.purpose === 'child') {
      if (this.claimReceipt === undefined || request.parentClaimId !== this.claimReceipt.claimId) throw new Error('kernel_parent_claim_required');
      const state=object(await this.kernel.call('task.read',this.scope(),options?.signal));
      if (state.state !== 'claimed' || state.owner !== this.config.owner || state.claim_fence !== this.claimReceipt.fence) {
        throw new Error('kernel_claim_stale');
      }
      return this.claimReceipt;
    }
    if (this.claimReceipt !== undefined) throw new Error('kernel_root_claim_already_granted');
    const fact=object(await this.kernel.call('task.claim',{...this.scope(),owner:this.config.owner},options?.signal));
    this.claimFact=fact;
    const receipt: ClaimReceipt={claimId:`${text(fact.task_key)}:${count(fact.claim_fence)}`,
      taskId:this.config.scope.task_id,epoch:this.config.scope.task_epoch,fence:count(fact.claim_fence),
      compositionRef:this.config.compositionDigest,grantedAt:count(fact.epoch_started_ms)};
    this.claimReceipt=Object.freeze(receipt);
    return this.claimReceipt;
  }

  /** Called by the trusted spawn provider inside the unpublished child setup. */
  async persistChildBinding(child: Agent, grant: GrantedTask): Promise<void> {
    if (this.claimFact === undefined || grant.receipt !== this.claimReceipt) throw new Error('kernel_claim_required');
    await this.kernel.call('task.bind',{...this.scope(),claim:this.claimFact,
      child_id:String(child.session.id),session_id:String(child.session.id)});
    this.childSessionId=String(child.session.id);this.childAgent=child;
    if (this.config.accountingVersion === 'c2p-dsh-task-loop-v2') {
      const bundle=object(await this.kernel.call('context.materials',{...this.scope(),contract_ref:this.config.contractRef}));
      if (!isObject(bundle.scope) || !Array.isArray(bundle.required)) throw new Error('kernel_material_bundle_invalid');
      this.materialPolicy=new MaterialRestoration(bundle.scope as unknown as MaterialScope,
        bundle.required as unknown as RequiredMaterial[]);
      child.ctx.on('agent/pre-step',async (_request,next)=>{
        await this.completeCurrentStep(child.ctx,child);
        return await next();
      });
      installMaterialRestoration(child.ctx,this.materialPolicy,async()=>{
        // Reconsume the original frozen owner at every step, including after
        // compaction. A changed revision cannot reuse a cached authority bundle.
        const fresh=object(await this.kernel.call('context.materials',{...this.scope(),contract_ref:this.config.contractRef}));
        if (!isObject(fresh.scope)) throw new Error('kernel_material_bundle_invalid');
        return fresh.scope as unknown as MaterialScope;
      },true);
      const issued=object(await this.kernel.call('context.read_grants',{...this.scope(),contract_ref:this.config.contractRef}));
      if (!Array.isArray(issued.grants)) throw new Error('kernel_read_grants_invalid');
      if (issued.grants.length !== 0) {
        const navigationText=JSON.stringify({navigation_grants:issued.grants});
        child.ctx.on('agent/pre-step',async (_payload,next)=>{
          const decision=await next();if (decision.kind === 'reject') return decision;
          const present=[...child.session.deriveMessages(),...decision.messages].some(message=>message.role === 'user'
            && message.content.some(block=>block.type === 'text' && block.text === navigationText));
          return present ? decision : {...decision,messages:[...decision.messages,
            createUserMessage({source:{kind:'user'},content:[{type:'text',text:navigationText}]})]};
        });
        installScopedRead(child.ctx,{sessionId:this.childSessionId,read:async(grantId,offset,length)=>{
          const result=object(await this.kernel.call('task.read_grant',{...this.scope(),grant_id:grantId,offset,length}));
          return {model_text:text(result.model_text),delivered_bytes:count(result.delivered_bytes)};
        },stop:async error=>{this.epochStop.abort(error);}});
      }
    }
  }

  /** Record the full supported assembly; signal/session handles are not wire. */
  roleFor(child: Agent):string {return this.auxiliaryChildren.has(String(child.session.id)) ? 'compaction' : 'writer';}
  isAuxiliary(request:GenerateOptions):boolean {return this.auxiliaryChildren.has(String(request.sessionId));}
  capFor(request:GenerateOptions,writerCap:number):number {return this.auxiliaryChildren.get(String(request.sessionId)) ?? writerCap;}

  /** Run the SDK's separately bound auxiliary child; never reuse the parent stream. */
  async summarize(input:CompactionInput,parent:Agent,bindings:SessionBindings,
    options:WriterCompactionOptions,hostCtx:Context,signal?:AbortSignal):Promise<SettledCompaction> {
    if (this.config.accountingVersion!=='c2p-dsh-task-loop-v2' || this.auxiliaryBinding!==undefined
      || String(parent.session.id)!==this.childSessionId) throw new Error('kernel_compaction_parent_invalid');
    await this.completeCurrentStep(parent.ctx,parent);
    if (!await parent.ctx.sessions.flush(parent.session)) throw new Error('kernel_compaction_parent_not_durable');
    const inputRef=await this.putJson(object(decodeWire(JSON.stringify(input))));
    const parentRef=await this.putJson({schema_version:'DshSessionCaptureV1',session_id:String(parent.session.id),
      format_version:'SessionFileV4',events:decodeWire(JSON.stringify(parent.session.snapshotEvents(SessionLogOffset(0))))});
    const prompt=object(await this.kernel.call('context.compaction_prompt',{...this.scope(),contract_ref:this.config.contractRef,input_ref:inputRef},signal));
    const saved={reservation:this.reservationFact,digest:this.assemblyDigest,finish:this.adapterFinish,usage:this.usageRecorded,
      proof:this.currentStepProof,session:this.childSessionId,agent:this.childAgent,observedUsage:this.observedUsage};
    const registration=registerCode2PaperSpawn(hostCtx,{bindings,providerName:`c2p-compaction-${randomUUID()}`,
      persistChildBinding:async(child,grant)=>{
        if (grant.receipt!==this.claimReceipt) throw new Error('kernel_claim_required');
        const issued=object(await this.kernel.call('task.bind_auxiliary',{...this.scope(),contract_ref:this.config.contractRef,
          budget_ref:this.config.budgetRef,parent_session_ref:parentRef,input_ref:inputRef,
          child_id:String(child.session.id),session_id:String(child.session.id),output_tokens:options.maxTokens},signal));
        if (!isObject(issued.binding_ref) || !isObject(issued.binding) || issued.binding.prompt_text!==prompt.prompt_text) {
          throw new Error('kernel_compaction_binding_invalid');
        }
        this.auxiliaryBinding=issued.binding_ref;this.auxiliaryConfig=options.providerConfig;
        this.auxiliaryChildren.set(String(child.session.id),options.maxTokens);
        this.childSessionId=String(child.session.id);this.childAgent=child;
        this.reservationFact=undefined;this.assemblyDigest=undefined;this.adapterFinish=undefined;
        this.usageRecorded=false;this.currentStepProof=undefined;this.observedUsage=undefined;
        child.ctx.tools.restrict({allow:[]});
        child.ctx.systemPrompt.section({name:'c2p-writer-native',order:0,complete:true,interpolate:false,text:text(prompt.system_text)});
        child.ctx.systemPrompt.suppressRuntimeContext();
        if (!isObject(prompt.options)) throw new Error('kernel_compaction_options_invalid');
        const requestConfig={...prompt.options,provider:text(prompt.options.provider),model:text(prompt.options.model),maxTokens:options.maxTokens};
        child.ctx.on('agent/request',async()=>requestConfig);
        child.ctx.on('agent/pre-step',(request,next)=>request.step>1 ? Promise.resolve({kind:'reject'}) : next());
      }});
    let delegated:Awaited<ReturnType<typeof dispatchRole>>|undefined;
    try {
      delegated=await dispatchRole(hostCtx,{parent,bindings,role:'compaction',providerName:registration.providerName,
        prompt:[{type:'text',text:text(prompt.prompt_text)}],agentOptions:{...parent.options,maxTokens:options.maxTokens},
        signal:signal ?? AbortSignal.timeout(30_000)});
      const result=await delegated.run.result;const child=delegated.run.localAgent;
      if (!child || result.stopReason!=='completed') throw new Error('kernel_compaction_child_unfinished');
      await this.completeCurrentStep(child.ctx,child);
      if (this.currentStepProof===undefined || this.observedUsage===undefined || this.adapterFinish!=='stop') {
        throw new Error('kernel_compaction_settlement_missing');
      }
      const sessionRef=await this.putJson({schema_version:'DshSessionCaptureV1',session_id:String(child.session.id),
        format_version:'SessionFileV4',events:decodeWire(JSON.stringify(child.session.snapshotEvents(SessionLogOffset(0))))});
      this.auxiliarySessions.push(sessionRef);
      return {role:'compaction',parentSessionId:String(parent.session.id),childSessionId:String(child.session.id),
        requestId:this.requestId(),provider:text(parent.options.provider),model:text(parent.options.model),maxTokens:options.maxTokens,
        rawOutput:result.output,usage:this.observedUsage,naturalExhaustion:true,settlementRef:this.currentStepProof};
    } catch(error) {this.epochStop.abort(error);throw error;}
    finally {
      await delegated?.run.dispose();registration.dispose();
      this.auxiliaryBinding=undefined;this.auxiliaryConfig=undefined;
      this.reservationFact=saved.reservation;this.assemblyDigest=saved.digest;this.adapterFinish=saved.finish;
      this.usageRecorded=saved.usage;this.currentStepProof=saved.proof;this.childSessionId=saved.session;
      this.childAgent=saved.agent;this.observedUsage=saved.observedUsage;
    }
  }

  async recordActualRequest(request: GenerateOptions): Promise<JsonObject> {
    this.epochStop.signal.throwIfAborted();
    digestSupportedRequest(request);
    if (this.config.accountingVersion === 'c2p-dsh-task-loop-v2') {
      if ((this.materialPolicy === undefined && this.auxiliaryBinding===undefined) || String(request.sessionId) !== this.childSessionId) {
        throw new Error('kernel_material_policy_required');
      }
      if (this.auxiliaryBinding===undefined) this.materialPolicy!.assertRequest(request.messages,this.materialPolicy!.scope);
      if (this.childAgent === undefined || !await this.childAgent.ctx.sessions.flush(this.childAgent.session)) {
        throw new Error('kernel_material_batch_not_durable');
      }
    }
    const material: Record<string, unknown>={};
    for (const [key,value] of Object.entries(request)) if (key !== 'signal' && key !== 'sessionId' && value !== undefined) material[key]=value;
    const actualRef=await this.putJson(object(decodeWire(JSON.stringify(material))));
    if (this.config.accountingVersion === 'c2p-dsh-task-loop-v2') {
      if (this.config.providerConfig === undefined) throw new Error('kernel_step_profile_required');
      const providerRef=await this.putJson(await observeLocalWriterWire(this.auxiliaryConfig ?? this.config.providerConfig,request));
      const sequence=++this.measuredSequence;
      const measured=object(await this.kernel.call(this.auxiliaryBinding===undefined ? 'request.measure_step' : 'request.measure_auxiliary',
        {...this.scope(),contract_ref:this.config.contractRef,...(this.auxiliaryBinding===undefined ? {} : {binding_ref:this.auxiliaryBinding}),
        actual_request_ref:actualRef,provider_wire_ref:providerRef,sequence},request.signal));
      if (!isObject(measured.step_ref)) throw new Error('kernel_step_measurement_invalid');
      const sid=String(request.sessionId),localSequence=(this.localSequences.get(sid) ?? 0)+1;
      this.localSequences.set(sid,localSequence);
      this.measuredSteps.set(text(actualRef.bytes_digest),{ref:measured.step_ref,sequence,localSequence});
    }
    return actualRef;
  }

  async putJson(value: JsonObject): Promise<JsonObject> {
    return await this.putBytes(Buffer.from(JSON.stringify(value),'utf8'),'application/json');
  }

  async putBytes(raw: Uint8Array, mediaType: 'application/json' | 'application/octet-stream' | 'text/plain'): Promise<JsonObject> {
    return object(await this.kernel.call('artifact.record',{...this.scope(),raw_base64:Buffer.from(raw).toString('base64'),media_type:mediaType}));
  }

  async captureRaw(source: CapturedRawArguments): Promise<void> {
    const multistep=this.config.accountingVersion === 'c2p-dsh-task-loop-v2';
    if (!multistep && source.name !== 'c2p_terminal') return;
    if (this.childSessionId === undefined || String(source.sessionId) !== this.childSessionId) throw new Error('kernel_raw_session_mismatch');
    const rawRef=await this.putBytes(Buffer.from(source.text,'utf8'),'application/octet-stream');
    if (multistep) {
      if (source.name === undefined || source.name === '') throw new Error('kernel_raw_tool_name_missing');
      // This callback is awaited at the real block-end before the SDK forwards
      // it to schema/tool dispatch. Invalid terminal JSON still consumes its slot.
      await this.kernel.call('task.record_tool_candidate',{...this.scope(),contract_ref:this.config.contractRef,
        candidate:{schema_version:'DshToolCandidateV2',...this.scope(),child_id:this.childSessionId,
          session_id:this.childSessionId,request_id:this.requestId(),tool_call_id:source.callId,
          stream_index:source.streamIndex,name:source.name,arguments_ref:rawRef,
          source:'gated-adapter-tool-arguments-delta/2'}});
    }
    if (source.name !== 'c2p_terminal') return;
    await this.kernel.call('task.capture_raw',{...this.scope(),capture:{schema_version:'DshRawCaptureV1',...this.scope(),
      child_id:this.childSessionId,session_id:this.childSessionId,request_id:this.requestId(),tool_call_id:source.callId,
      stream_index:source.streamIndex,source:'adapter_tool_arguments_delta',arguments_completion:'block-ended',arguments_ref:rawRef}});
  }

  /** Private local recovery; never creates an Agent or invokes an adapter. */
  async recoverStoredOutput(ctx?: Context): Promise<JsonObject> {
    let failed=false; let primary: unknown;
    try { return await this.recoverOriginalStoredOutput(ctx); }
    catch (error) { failed=true; primary=error; throw error; }
    finally {
      try { await this.releaseBackend(); }
      catch (error) { if (failed) secondary(primary,'backend.release',error); else throw error; }
    }
  }

  private async recoverOriginalStoredOutput(ctx?: Context): Promise<JsonObject> {
    this.claimFact=object(await this.kernel.call('task.recover',{...this.scope(),owner:this.config.owner}));
    this.recoveryOnly=true;
    const persisted=object(await this.kernel.call('task.read',this.scope()));
    if (isObject(persisted.provider_quiescence) && isObject(persisted.provider_quiescence.quiescence_ref)) {
      this.quiescenceRef=persisted.provider_quiescence.quiescence_ref;
    }
    const status=object(await this.kernel.call('request.status',{...this.scope(),contract_ref:this.config.contractRef}));
    if (!isObject(status.reservation)) throw new Error('kernel_recorded_output_not_ready');
    this.reservationFact=status.reservation;
    if (!isObject(status.recorded_output_ref)) {
      if (ctx === undefined) throw new Error('kernel_recorded_output_not_ready');
      const view=object(await this.kernel.call('task.read',this.scope()));
      if (!isObject(view.captured_source)) throw new Error('kernel_recorded_output_not_ready');
      const source=view.captured_source;
      const readSignal=AbortSignal.timeout(5_000);
      const handle=await ctx.sessionPersistence.open(SessionId(text(source.session_id)),'read',{signal:readSignal});
      let events: JsonValue;
      try {events=decodeWire(JSON.stringify((await handle.read(0,undefined,{signal:readSignal})).events));}
      finally {await handle.close();}
      if (!Array.isArray(events)) throw new Error('kernel_recovery_session_invalid');
      const calls=events.filter(event=>isObject(event) && event.type === 'tool/call' && isObject(event.data)
        && event.data.name === 'c2p_terminal' && event.data.callId === source.tool_call_id);
      if (calls.length !== 1) throw new Error('kernel_recovery_terminal_not_ready');
      const call=object(object(calls[0]!).data!);
      const sessionRef=await this.putJson({schema_version:'DshSessionCaptureV1',session_id:source.session_id!,
        format_version:'SessionFileV4',events});
      const normalizedRef=await this.putBytes(Buffer.from(text(call.arguments),'utf8'),'application/octet-stream');
      return await this.publish({schema_version:'OutputEnvelopeV1',...this.scope(),child_id:source.child_id!,session_id:source.session_id!,
        turn_id:count(call.turn),step_id:count(call.step),tool_call_id:source.tool_call_id!,request_id:source.request_id!,
        source:'adapter_tool_arguments_delta',arguments_complete:true,provider_http:{status:'not_observed',ref:null},
        adapter_arguments:{status:'observed',ref:source.arguments_ref!},normalized_arguments:{status:'observed',ref:normalizedRef},
        stop_reason:'completed',usage:null,session_capture_ref:sessionRef});
    }
    const params={...this.scope(),contract_ref:this.config.contractRef,output_ref:status.recorded_output_ref};
    const key=object(await this.kernel.call('task.ingest_key',params));
    return object(await this.kernel.call('task.ingest',{...params,idempotency_key:text(key.idempotency_key)}));
  }

  async reserve(request: RequestReserveRequest, options?: { readonly signal?: AbortSignal }): Promise<ReservationReceipt> {
    this.epochStop.signal.throwIfAborted();
    if (this.claimReceipt === undefined || request.binding.claimId !== this.claimReceipt.claimId
      || request.binding.fence !== this.claimReceipt.fence || request.binding.compositionRef !== this.config.compositionDigest
      || request.binding.taskId !== this.config.scope.task_id || request.binding.epoch !== this.config.scope.task_epoch) {
      throw new Error('kernel_request_binding_mismatch');
    }
    const multistep=this.config.accountingVersion === 'c2p-dsh-task-loop-v2';
    if (request.identity.purpose !== (this.auxiliaryBinding===undefined ? 'writer' : 'compaction') || (!multistep && (request.identity.sequence !== 1 || this.reservationFact !== undefined))) {
      throw new Error('kernel_single_request_only');
    }
    if (request.actualRequestRef === undefined) throw new Error('kernel_actual_assembly_required');
    let fact:JsonObject;
    if (multistep) {
      const measured=this.measuredSteps.get(text(request.actualRequestRef.bytes_digest));
      if (measured === undefined || measured.localSequence !== request.identity.sequence) throw new Error('kernel_measured_step_required');
      fact=object(await this.kernel.call('request.reserve_step',{...this.scope(),contract_ref:this.config.contractRef,
        budget_ref:this.config.budgetRef,step_ref:measured.ref,event_id:`reserve:step:${request.identity.sequence}`},options?.signal));
    } else {
      fact=object(await this.kernel.call('request.reserve',{...this.scope(),contract_ref:this.config.contractRef,
        budget_ref:this.config.budgetRef,actual_request_ref:request.actualRequestRef,event_id:'reserve:primary'},options?.signal));
    }
    if (fact.request_digest !== `sha256:${request.digest.value}`) throw new Error('kernel_request_digest_mismatch');
    this.reservationFact=fact; this.assemblyDigest=request.digest.value;
    this.requests.set(text(fact.request_id),{fact,digest:request.digest.value});
    this.adapterFinish=undefined;this.usageRecorded=false;this.currentStepProof=undefined;
    return {contractVersion:REQUEST_CONTRACT_VERSION,requestId:text(fact.request_id),reservationId:text(fact.reservation_id),
      binding:request.binding,digest:request.digest,grantedAt:Date.now()};
  }

  private requireReservation(requestId: string, reservationId: string): JsonObject {
    const fact=this.requests.get(requestId)?.fact ?? this.reservationFact;
    if (fact === undefined || fact.request_id !== requestId || fact.reservation_id !== reservationId) throw new Error('kernel_reservation_unknown');
    return fact;
  }

  async dispatch(request: RequestDispatchRequest, options?: { readonly signal?: AbortSignal }): Promise<DispatchReceipt> {
    const fact=this.requireReservation(request.reservation.requestId,request.reservation.reservationId);
    if (request.digest.value !== (this.requests.get(request.reservation.requestId)?.digest ?? this.assemblyDigest)) throw new Error('kernel_request_digest_mismatch');
    await this.kernel.call('request.dispatch',{...this.scope(),contract_ref:this.config.contractRef,reservation:fact,
      event_id:'dispatch:primary',kind:'dispatch-recorded'},options?.signal);
    return {contractVersion:REQUEST_CONTRACT_VERSION,requestId:text(fact.request_id),reservationId:text(fact.reservation_id),
      digest:request.digest,stage:'dispatch-recorded',recordedAt:Date.now()};
  }

  /** The gated adapter calls this once, immediately before delegating transport. */
  async enterAdapter(request: GenerateOptions, authorization: DispatchAuthorization): Promise<void> {
    const fact=this.requireReservation(authorization.requestId,authorization.reservationId);
    if (digestSupportedRequest(request).value !== (this.requests.get(authorization.requestId)?.digest ?? this.assemblyDigest) || request.signal?.aborted === true) {
      throw new Error('kernel_adapter_assembly_changed_or_aborted');
    }
    await this.kernel.call('request.dispatch',{...this.scope(),contract_ref:this.config.contractRef,reservation:fact,
      event_id:'adapter:primary',kind:'adapter-attempt'},request.signal);
  }

  async settle(request: RequestSettleRequest): Promise<SettlementReceipt> {
    const fact=this.requireReservation(request.requestId,request.reservationId);
    if (request.finish.kind === 'unknown' || request.finish.usage === undefined
        || (request.finish.usage.inputTokens === 0 && request.finish.usage.outputTokens === 0)) {
      await this.markUnknown({requestId:request.requestId,reservationId:request.reservationId,
        lastStage:'response-observed',reason:'usage-missing'});
      throw new Error('kernel_usage_missing');
    }
    const usage=request.finish.usage;
    const evidence=await this.putJson({schema_version:'DshAdapterUsageV1',request_digest:fact.request_digest!,
      input_tokens:usage.inputTokens,output_tokens:usage.outputTokens,source:'adapter-usage'});
    const recorded=object(await this.kernel.call('request.settle',{...this.scope(),contract_ref:this.config.contractRef,reservation:fact,
      event_id:'usage:primary',kind:'usage',evidence_ref:evidence,usage_input_tokens:usage.inputTokens,usage_output_tokens:usage.outputTokens}));
    this.usageRecorded=true;this.observedUsage={inputTokens:usage.inputTokens,outputTokens:usage.outputTokens};
    // Fees remain retained until raw/Session flush and original local settlement.
    return {contractVersion:REQUEST_CONTRACT_VERSION,requestId:request.requestId,settlementId:text(recorded.event_digest),
      finish:request.finish,response:request.response,settledAt:Date.now()};
  }

  async markUnknown(request: RequestMarkUnknownRequest): Promise<UnknownReceipt> {
    const fact=this.requireReservation(request.requestId,request.reservationId);
    await this.kernel.call('request.mark_unknown',{...this.scope(),contract_ref:this.config.contractRef,reservation:fact,
      event_id:`unknown:${request.lastStage}`,kind:'send-outcome-unknown',reason:request.reason});
    return {contractVersion:REQUEST_CONTRACT_VERSION,requestId:request.requestId,lastStage:request.lastStage,
      reason:request.reason,uncertainty:'send-outcome-unknown',recordedAt:Date.now()};
  }

  observeCompletion(request: GenerateOptions, finishReason: string | undefined): void {
    if (digestSupportedRequest(request).value === this.assemblyDigest && finishReason !== undefined) this.adapterFinish=finishReason;
  }

  /** Close a navigation step only after the real SDK tool/step owner finished.
   * The terminal request remains owned by the original ingest path.
   */
  async completeCurrentStep(ctx: Context, child: Agent): Promise<void> {
    if (this.config.accountingVersion !== 'c2p-dsh-task-loop-v2' || this.reservationFact === undefined) return;
    const fact=this.reservationFact;const requestId=text(fact.request_id);
    if (this.completedSteps.has(requestId)) return;
    const view=object(await this.kernel.call('task.read',this.scope()));
    // A captured terminal may never grant an additional model step.
    if (isObject(view.captured_source)) throw new Error('kernel_terminal_candidate_already_consumed');
    const evidence=await this.captureCurrentStepProof(ctx,child);
    for (const kind of ['terminal','settlement']) await this.kernel.call('request.settle',{...this.scope(),
      contract_ref:this.config.contractRef,reservation:fact,event_id:`step-finish:${kind}`,kind,evidence_ref:evidence});
    this.completedSteps.add(requestId);
  }

  private async captureCurrentStepProof(ctx: Context, child: Agent): Promise<JsonObject> {
    if (this.reservationFact === undefined) throw new Error('kernel_reservation_required');
    const fact=this.reservationFact;const requestId=text(fact.request_id);
    if (this.childSessionId !== String(child.session.id) || !this.usageRecorded
      || (this.adapterFinish !== 'stop' && this.adapterFinish !== 'tool-calls')) throw new Error('kernel_step_not_naturally_complete');
    if (!await ctx.sessions.flush(child.session)) throw new Error('kernel_step_session_not_durable');
    const events=decodeWire(JSON.stringify(child.session.snapshotEvents(SessionLogOffset(0))));
    if (!Array.isArray(events)) throw new Error('host_session_invalid');
    const messages=events.filter(event=>isObject(event) && event.type === 'assistant/message');
    const last=messages.at(-1);
    if (!isObject(last) || !isObject(last.data)) throw new Error('kernel_step_message_missing');
    const turn=count(last.data.turn),step=count(last.data.step);
    const end=events.find(event=>isObject(event) && event.type === 'step/end' && isObject(event.data)
      && event.data.turn === turn && event.data.step === step);
    if (!isObject(end)) throw new Error('kernel_step_end_missing');
    // Persist the immutable completed prefix, not later steps or summaries.
    const prefix=events.filter(event=>isObject(event) && count(event.seq)<=count(end.seq));
    const sessionRef=await this.putJson({schema_version:'DshSessionCaptureV1',session_id:this.childSessionId,
      format_version:'SessionFileV4',events:prefix});
    const evidence=await this.putJson({schema_version:'DshStepFinishObservationV2',request_id:requestId,
      request_digest:fact.request_digest!,session_id:this.childSessionId,turn_id:turn,step_id:step,
      source:'gated-adapter-natural-exhaustion/2',finish_reason:this.adapterFinish,stream_complete:true,session_ref:sessionRef});
    this.currentStepProof=evidence;
    return evidence;
  }

  async archiveEpochQuiescence(child: Agent): Promise<void> {
    if (this.recoveryOnly) throw new Error('provider_observation_execute_claim_required');
    const final=await this.captureCurrentStepProof(child.ctx,child);
    const status=object(await this.kernel.call('request.status',{...this.scope(),contract_ref:this.config.contractRef}));
    if (!Array.isArray(status.completed_step_refs)) throw new Error('kernel_epoch_steps_missing');
    const events=decodeWire(JSON.stringify(child.session.snapshotEvents(SessionLogOffset(0))));
    if (!Array.isArray(events)) throw new Error('host_session_invalid');
    const sessionRef=await this.putJson({schema_version:'DshSessionCaptureV1',session_id:String(child.session.id),
      format_version:'SessionFileV4',events});
    const ref=await this.putJson({schema_version:'DshEpochProviderQuiescenceV2',...this.scope(),
      session_id:String(child.session.id),source:'gated-adapter-epoch-natural-exhaustion/2',
      session_ref:sessionRef,steps:[...status.completed_step_refs,final],auxiliary_sessions:[...this.auxiliarySessions]});
    await this.kernel.call('backend.observe_quiescence',{...this.scope(),quiescence_ref:ref});
    this.quiescenceRef=ref;
  }

  /** Only the gate's natural-exhaustion callback supplies adapterFinish. */
  async archiveProviderQuiescence(rawRef: JsonObject, sessionRef: JsonObject): Promise<void> {
    if (this.recoveryOnly) throw new Error('provider_observation_execute_claim_required');
    this.nativeTerminalObserved=true;
    if (this.reservationFact === undefined || !this.usageRecorded
      || (this.adapterFinish !== 'tool-calls' && this.adapterFinish !== 'stop')
      || this.childSessionId === undefined) return;
    const ref=await this.putJson({schema_version:'DshProviderQuiescenceV1',...this.scope(),
      request_id:this.reservationFact.request_id!,request_digest:this.reservationFact.request_digest!,
      session_id:this.childSessionId,source:'gated-adapter-natural-exhaustion/1',
      finish_reason:this.adapterFinish,raw_ref:rawRef,session_ref:sessionRef});
    await this.kernel.call('backend.observe_quiescence',{...this.scope(),quiescence_ref:ref});
    // An archived artifact is not a registered owner observation.
    this.quiescenceRef=ref;
  }

  /** Ordinary model text stays text; this credential grants no terminal source. */
  async archiveRejectedTextQuiescence(rawRef: JsonObject, sessionRef: JsonObject): Promise<void> {
    if (this.recoveryOnly) throw new Error('provider_observation_execute_claim_required');
    if (this.reservationFact === undefined || !this.usageRecorded || this.adapterFinish !== 'stop'
      || this.childSessionId === undefined) return;
    const ref=await this.putJson({schema_version:'DshRejectedTextProviderQuiescenceV1',...this.scope(),
      request_id:this.reservationFact.request_id!,request_digest:this.reservationFact.request_digest!,
      session_id:this.childSessionId,source:'gated-adapter-natural-text-exhaustion/1',
      finish_reason:'stop',raw_ref:rawRef,session_ref:sessionRef});
    await this.kernel.call('backend.observe_quiescence',{...this.scope(),quiescence_ref:ref});
    this.quiescenceRef=ref;
  }

  /** Exact unknown-tool rejection; no terminal name or arguments are repaired. */
  async archiveRejectedUnknownToolQuiescence(rawRef: JsonObject, sessionRef: JsonObject): Promise<void> {
    if (this.recoveryOnly) throw new Error('provider_observation_execute_claim_required');
    if (this.reservationFact === undefined || !this.usageRecorded || this.adapterFinish !== 'tool-calls'
      || this.childSessionId === undefined) return;
    const ref=await this.putJson({schema_version:'DshRejectedUnknownToolProviderQuiescenceV1',...this.scope(),
      request_id:this.reservationFact.request_id!,request_digest:this.reservationFact.request_digest!,
      session_id:this.childSessionId,source:'gated-adapter-natural-unknown-tool-exhaustion/1',
      finish_reason:'tool-calls',raw_ref:rawRef,session_ref:sessionRef});
    await this.kernel.call('backend.observe_quiescence',{...this.scope(),quiescence_ref:ref});
    this.quiescenceRef=ref; this.rejectedUnknownTool=true;
  }

  async releaseBackend(): Promise<void> {
    if (this.quiescenceRef === undefined) return;
    const status=object(await this.kernel.call('request.status',{...this.scope(),contract_ref:this.config.contractRef}));
    // Damaged/missing output, a crash or unknown send keeps the original owner.
    if (!isObject(status.recovery) || status.recovery.state !== 'validation_pending') return;
    await this.kernel.call('backend.release',{...this.scope(),quiescence_ref:this.quiescenceRef});
  }

  /** A malformed candidate still spends observed fees; it grants no domain result. */
  async settleRejectedObservation(rawRef: JsonObject, sessionRef: JsonObject): Promise<void> {
    const finish=this.adapterFinish;
    if (this.reservationFact!==undefined && this.completedSteps.has(text(this.reservationFact.request_id))) return;
    if (this.reservationFact === undefined || !this.usageRecorded
        || (finish !== 'stop' && finish !== 'tool-calls')) return;
    const status=object(await this.kernel.call('request.status',{...this.scope(),contract_ref:this.config.contractRef}));
    // Original ingest already settles either its domain receipt or rejection.
    if (isObject(status.recorded_output_ref)) return;
    const fact=this.reservationFact;
    const evidence=this.config.accountingVersion === 'c2p-dsh-task-loop-v2'
      ? this.currentStepProof : await this.putJson({schema_version:this.rejectedUnknownTool ? 'DshRejectedUnknownToolFinishObservationV1' : finish === 'stop' && !this.nativeTerminalObserved
      ? 'DshRejectedTextFinishObservationV1' : 'DshFinishObservationV1',request_digest:fact.request_digest!,
      finish_reason:finish,stream_complete:true,raw_ref:rawRef,session_ref:sessionRef});
    if (evidence === undefined) return;
    for (const kind of ['terminal','settlement']) await this.kernel.call('request.settle',{...this.scope(),
      contract_ref:this.config.contractRef,reservation:fact,event_id:`rejected-observation:${kind}`,kind,evidence_ref:evidence});
  }

  async cancel(): Promise<void> {
    if (this.claimFact !== undefined) await this.kernel.call('task.cancel',{...this.scope(),claim:this.claimFact});
  }

  async epochSignal(parent: AbortSignal): Promise<AbortSignal> {
    if (this.claimFact === undefined) throw new Error('kernel_claim_required');
    const fact=object(await this.kernel.call('task.limits',{...this.scope(),claim:this.claimFact},parent));
    const limits=object(fact.epoch_limits!);
    const remaining=count(fact.epoch_started_ms)+count(limits.max_wall_seconds)*1000-Date.now();
    if (!Number.isSafeInteger(remaining) || remaining <= 0 || remaining > 2**32-1) throw new Error('host_epoch_deadline_invalid');
    return AbortSignal.any([parent,this.epochStop.signal,AbortSignal.timeout(remaining)]);
  }

  requestId(): string {
    if (this.reservationFact === undefined) throw new Error('kernel_reservation_required');
    return text(this.reservationFact.request_id);
  }

  async publish(envelope: JsonObject): Promise<JsonObject> {
    const params={...this.scope(),contract_ref:this.config.contractRef};
    const output=object(await this.kernel.call('task.record_output',{...params,envelope}));
    const key=object(await this.kernel.call('task.ingest_key',{...params,output_ref:output}));
    return object(await this.kernel.call('task.ingest',{...params,output_ref:output,idempotency_key:text(key.idempotency_key)}));
  }
}

export interface WriterCompactionOptions {
  readonly adapter:GatedAdapterSource;
  readonly providerConfig:JsonObject;
  readonly maxTokens:number;
  readonly config?:BasicCompactionConfig;
  /** Host diagnostic trigger on the real SDK transaction, not a replacement engine. */
  readonly forceAfterStep?:number;
}

export interface SingleWriterRun {
  readonly compaction?:WriterCompactionOptions;
  readonly authority: KernelAuthority;
  readonly input: WriterInputRefV1;
  readonly projection: WriterWireProjectionV1;
  readonly adapter: GatedAdapterSource;
  readonly cwd: string;
  readonly signal: AbortSignal;
  readonly verifyComposition: () => Promise<void>;
  readonly execution?: { readonly parallel_agents?: boolean };
}

/** A root orchestrates only; exactly one bound Writer child can dispatch. */
export async function runSingleWriter(ctx: Context, options: SingleWriterRun): Promise<JsonObject> {
  if (options.authority.config.accountingVersion === 'c2p-dsh-task-loop-v2') throw new Error('host_single_writer_version_invalid');
  return await runWriter(ctx,options,false);
}

export async function runMultistepWriter(ctx: Context, options: SingleWriterRun): Promise<JsonObject> {
  if (options.authority.config.accountingVersion !== 'c2p-dsh-task-loop-v2') throw new Error('host_multistep_writer_version_invalid');
  return await runWriter(ctx,options,true);
}

async function runWriter(ctx: Context, options: SingleWriterRun, multistep: boolean): Promise<JsonObject> {
  serialExecutionPolicy(options.execution);
  const {authority,input,projection}=options;
  const cancellation=new AbortController();
  let signal=AbortSignal.any([options.signal,cancellation.signal]);
  if (input.composition_digest !== authority.config.compositionDigest
    || projection.composition_digest !== authority.config.compositionDigest) throw new Error('host_composition_mismatch');
  const route=text(input.effective_options.provider);
  const bindings=new SessionBindings({caller:authority.config.caller,recorder:authority});
  const authorizations=new DispatchAuthorizations();
  const capture=new TerminalArgumentCapture(); const disposeCapture=capture.install(ctx,source=>authority.captureRaw(source));
  let terminalCount=0;
  let requestFailure: unknown;
  let primaryFailure: unknown; let failed=false;
  let observedRaw: JsonObject | undefined;
  let observedSession: JsonObject | undefined;
  async function guardRequest<T>(effect: () => Promise<T>): Promise<T> {
    try { return await effect(); }
    catch (error) { requestFailure ??= error; throw error; }
  }
  const spawn=registerCode2PaperSpawn(ctx,{bindings,persistChildBinding:async (child,grant)=>{
    await authority.persistChildBinding(child,grant);
    installNativeWriter(child.ctx,input,()=>{terminalCount++;});
    if (options.compaction!==undefined) {
      if (!multistep) throw new Error('host_compaction_requires_v2');
      const compact=options.compaction;
      const engine=await new Promise<EpochCompactionEngine>(resolve=>{
        child.ctx.inject(['llm','tokenMeter','sessions'],injected=>{
          resolve(new EpochCompactionEngine(injected,{summarize:(summary,parent,signal)=>
            guardRequest(()=>authority.summarize(summary,parent,bindings,compact,ctx,signal))},{...compact.config,maxTokens:compact.maxTokens}));
        });
      });
      if (compact.forceAfterStep!==undefined) {
        let forced=false;
        child.ctx.on('agent/pre-step',async(request,next)=>{
          if (!forced && request.step>compact.forceAfterStep!) {
            forced=true;const nodes=child.session.surface.nodes.filter(seq=>child.session.eventAt(seq)?.type!=='system/message');
            if (nodes.length===0) throw new Error('host_compaction_surface_empty');
            await engine.compactRegion(nodes[0]!,nodes.at(-1)!,child,request.signal);
          }
          return await next();
        });
      }
    }
    if (!multistep) child.ctx.on('agent/pre-step',(request,next)=>request.step > 1 ? Promise.resolve({kind:'reject'}) : next());
  }});
  const accounting=installRequestAccounting(ctx,{bindings,recorder:{
    reserve:(request,options)=>guardRequest(()=>authority.reserve(request,options)),
    dispatch:(request,options)=>guardRequest(()=>authority.dispatch(request,options)),
    settle:authority.settle.bind(authority),markUnknown:authority.markUnknown.bind(authority),
  },route,purpose:agent=>authority.roleFor(agent),authorizations,
    recordActualRequest:request=>guardRequest(async()=>{
      if (!multistep) compareWriterRequest(projection,request);
      await options.verifyComposition();
      return await authority.recordActualRequest(request);
    }),outputCap:{version:'dsh-frozen-writer-cap/1',cap:request=>authority.capFor(request,input.post_clamp_max_output_tokens)}});
  const disposeAdapter=ctx.llm.registerAdapter([route],gatedAdapter({
    providerInfo:provider=>options.adapter.providerInfo(provider),listModels:provider=>options.adapter.listModels(provider),
    resolveModel:(provider,model,signal)=>options.adapter.resolveModel(provider,model,signal),
    providerRetryPolicy:provider=>options.adapter.providerRetryPolicy(provider),
    imageRequestPricing:(provider,model)=>options.adapter.imageRequestPricing(provider,model),
    prepareCall:async(provider,model,signal)=>{
      const prepared=await options.adapter.prepareCall(provider,model,signal);
      return {model:prepared.model,stream:async function*(request) {
        if (options.compaction!==undefined && authority.isAuxiliary(request)) {
          const auxiliary=await options.compaction.adapter.prepareCall(provider,model,request.signal);
          yield* auxiliary.stream(request);
        } else yield* prepared.stream(request);
      }};
    },stream:request=>(options.compaction!==undefined && authority.isAuxiliary(request)
      ? options.compaction.adapter : options.adapter).stream(request),
  },authorizations,undefined,
    (request,authorization)=>guardRequest(async()=>{
      if (!multistep) compareWriterRequest(projection,request);
      await options.verifyComposition();
      await authority.enterAdapter(request,authorization);
    }),(request,finish)=>authority.observeCompletion(request,finish)) as never);
  let root: Awaited<ReturnType<typeof createBoundRootAgent>> | undefined;
  let delegated: Awaited<ReturnType<typeof dispatchRole>> | undefined;
  try {
    await options.verifyComposition();
    root=await createBoundRootAgent(ctx,{bindings,sessionId:SessionId(randomUUID()),
      task:{taskId:authority.config.scope.task_id,epoch:authority.config.scope.task_epoch},cwd:options.cwd,signal});
    signal=await authority.epochSignal(signal);
    delegated=await dispatchRole(ctx,{parent:root.handle.agent,bindings,role:'writer',signal,
      ...(multistep ? {agentOptions:{provider:route,model:input.model,maxTokens:input.post_clamp_max_output_tokens}} : {}),
      prompt:[{type:'text',text:input.task_view_json}]});
    await delegated.run.result;
    // Native Agent records seam errors and can resolve its result without a
    // terminal tool. Preserve the trusted gate's first failure for the Host.
    if (requestFailure !== undefined) throw requestFailure;
    if (signal.aborted) throw new Error('host_cancelled');
    const child=delegated.run.localAgent;
    if (child === undefined) throw new Error('host_local_child_required');
    // Flush the actual persistence owner before archiving/recording output.
    await ctx.sessionPersistence.flush();
    const events=child.session.snapshotEvents(SessionLogOffset(0));
    const wireEvents=decodeWire(JSON.stringify(events));
    if (!Array.isArray(wireEvents)) throw new Error('host_session_invalid');
    const calls=wireEvents.filter(event=>isObject(event) && event.type === 'tool/call'
      && isObject(event.data) && event.data.name === 'c2p_terminal');
    const view=object(await authority.kernel.call('task.read',{...authority.config.scope}));
    const source=isObject(view.captured_source) ? view.captured_source : undefined;
    const call=calls.length === 1 ? object(object(calls[0]!).data!) : undefined;
    if (calls.length === 0 && source === undefined) {
      const sessionRef=await authority.putJson({schema_version:'DshSessionCaptureV1',session_id:String(child.session.id),
        format_version:'SessionFileV4',events:wireEvents});
      observedSession=sessionRef;
      const messages=wireEvents.filter(event=>isObject(event) && event.type === 'assistant/message');
      const message=messages.length === 1 ? object(object(messages[0]!).data!).message : undefined;
      const blocks=isObject(message) && Array.isArray(message.content) ? message.content : [];
      const plain=blocks.filter(block=>isObject(block) && block.type === 'text' && typeof block.text === 'string')
        .map(block=>(block as JsonObject).text as string).join('');
      const nativeCalls=wireEvents.filter(event=>isObject(event) && event.type === 'tool/call' && isObject(event.data))
        .map(event=>object(object(event).data!));
      const rawRef=nativeCalls.length === 0 ? await authority.putBytes(Buffer.from(plain,'utf8'),'text/plain')
        : await authority.putJson(nativeCalls.length === 1 ? {schema_version:'DshRejectedUnknownToolCaptureV1',
          tool_call_id:nativeCalls[0]!.callId ?? null,name:nativeCalls[0]!.name ?? null,
          arguments:nativeCalls[0]!.arguments ?? null} : {schema_version:'DshRejectedNativeCallsCaptureV1',calls:nativeCalls});
      observedRaw=rawRef;
      const failedTurn=wireEvents.find(event=>isObject(event) && event.type === 'turn/end'
        && isObject(event.data) && isObject(event.data.reason) && event.data.reason.kind === 'error');
      if (isObject(failedTurn) && isObject(failedTurn.data) && isObject(failedTurn.data.reason)) {
        const providerError=failedTurn.data.reason.error;
        const failure=new Error('host_provider_stream_error');
        Object.assign(failure,{providerError,terminalObservation:{request_id:authority.requestId(),
          session_id:String(child.session.id),source:'native_provider_error; no terminal',
          native_tool_calls:nativeCalls.length,raw_ref:rawRef,session_ref:sessionRef}});
        throw failure;
      }
      const failure=new Error('host_single_terminal_required');
      Object.assign(failure,{terminalObservation:{request_id:authority.requestId(),session_id:String(child.session.id),
        source:nativeCalls.length ? 'native_unknown_tool; no registered terminal' : 'ordinary_model_text; no tool arguments',
        native_tool_calls:nativeCalls.length,raw_ref:rawRef,session_ref:sessionRef}});
      try {
        if (multistep) await authority.archiveEpochQuiescence(child);
        else if (nativeCalls.length === 1) await authority.archiveRejectedUnknownToolQuiescence(rawRef,sessionRef);
        else if (nativeCalls.length === 0) await authority.archiveRejectedTextQuiescence(rawRef,sessionRef);
      }
      catch (error) { secondary(failure,'backend.observe_quiescence',error); }
      throw failure;
    }
    const callId=text(call?.callId ?? source?.tool_call_id);
    const result=wireEvents.find(event=>isObject(event) && event.type === 'tool/result' && isObject(event.data)
      && isObject(event.data.message) && event.data.message.toolCallId === callId);
    const end=wireEvents.find(event=>isObject(event) && event.type === 'turn/end');
    const raw=capture.raw(callId,{sessionId:child.session.id});
    if (raw.state !== 'captured') throw new Error('host_raw_arguments_missing');
    const sessionRef=await authority.putJson({schema_version:'DshSessionCaptureV1',session_id:String(child.session.id),
      format_version:'SessionFileV4',events:wireEvents});
    const rawRef=await authority.putBytes(Buffer.from(raw.text,'utf8'),'application/octet-stream');
    observedRaw=rawRef; observedSession=sessionRef;
    let terminalFailure: Error | undefined;
    if (calls.length !== 1 || call === undefined) terminalFailure=new Error('host_single_terminal_required');
    else if (terminalCount !== 1 || !isObject(result) || !isObject(result.data) || !isObject(result.data.message)
      || result.data.message.isError === true || !isObject(end) || !isObject(end.data)
      || !isObject(end.data.reason) || end.data.reason.kind !== 'completed') {
      const message=isObject(result) && isObject(result.data) && isObject(result.data.message) ? result.data.message : undefined;
      const blocks=Array.isArray(message?.content) ? message.content : [];
      const errorText=blocks.filter(block=>isObject(block) && block.type === 'text' && typeof block.text === 'string')
        .map(block=>(block as JsonObject).text as string).join('\n');
      terminalFailure=new Error(errorText.startsWith('Error: ') ? errorText.slice(7) : 'host_terminal_not_completed');
      Object.assign(terminalFailure,{terminalObservation:{request_id:authority.requestId(),session_id:String(child.session.id),
        tool_call_id:callId,raw_ref:rawRef,session_ref:sessionRef,turn_end:isObject(end) ? end.data : null}});
    }
    try {
      if (multistep) await authority.archiveEpochQuiescence(child);
      else await authority.archiveProviderQuiescence(rawRef,sessionRef);
    }
    catch (error) {
      if (terminalFailure === undefined) throw error;
      secondary(terminalFailure,'backend.observe_quiescence',error);
    }
    if (terminalFailure !== undefined) throw terminalFailure;
    if (call === undefined) throw new Error('host_single_terminal_required');
    const normalizedRef=await authority.putBytes(Buffer.from(text(call.arguments),'utf8'),'application/octet-stream');
    if (signal.aborted) throw new Error('host_cancelled');
    await options.verifyComposition();
    return await authority.publish({schema_version:'OutputEnvelopeV1',...authority.config.scope,
      child_id:String(child.session.id),session_id:String(child.session.id),turn_id:count(call.turn),step_id:count(call.step),
      tool_call_id:callId,request_id:authority.requestId(),source:'adapter_tool_arguments_delta',arguments_complete:true,
      provider_http:{status:'not_observed',ref:null},adapter_arguments:{status:'observed',ref:rawRef},
      normalized_arguments:{status:'observed',ref:normalizedRef},stop_reason:'completed',usage:null,session_capture_ref:sessionRef});
  } catch (error) {
    failed=true; primaryFailure=error;
    if (error instanceof Error && observedRaw !== undefined && observedSession !== undefined
      && !Object.hasOwn(error,'terminalObservation')) Object.assign(error,{terminalObservation:{
        request_id:authority.requestId(),raw_ref:observedRaw,session_ref:observedSession}});
    // Abort the actual delegated transport before cancellation or cleanup RPCs.
    // Disposing an idle Agent does not prove the provider scope has stopped.
    cancellation.abort(error);
    try { await authority.cancel(); }
    catch (cancelFailure) { secondary(error,'task.cancel',cancelFailure); }
    if (observedRaw !== undefined && observedSession !== undefined) {
      try { await authority.settleRejectedObservation(observedRaw,observedSession); }
      catch (settlementFailure) {
        secondary(error,'request.settle',settlementFailure);
      }
    }
    throw error;
  } finally {
    // Finish every owned cleanup and retain the first operation/cleanup error.
    // Neither abort nor disposal can mint a provider completion observation.
    for (const [stage,effect] of [
      ['child.dispose',()=>delegated?.run.dispose()],['root.dispose',()=>root?.dispose()],
      ['adapter.dispose',disposeAdapter],['accounting.dispose',()=>accounting.dispose()],
      ['spawn.dispose',()=>spawn.dispose()],['capture.dispose',disposeCapture],
      ['backend.release',()=>authority.releaseBackend()],
    ] as const) {
      try { await effect(); }
      catch (error) {
        if (failed) secondary(primaryFailure,stage,error);
        else { failed=true; primaryFailure=error; }
      }
    }
    if (failed) throw primaryFailure;
  }
}
