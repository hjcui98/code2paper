/** Explicit Host entry. Offline admission never substitutes for a send permit. */
import { execFile } from 'node:child_process';
import { createHash } from 'node:crypto';
import { open } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import type { Context } from '@deepseek-ai/cordis';
import { serialExecutionPolicy } from './execution-policy.js';
import { startKernelWorker, type KernelWorkerLaunch } from './kernel-client.js';
import { KernelAuthority, runSingleWriter, runMultistepWriter, type KernelAuthorityConfig, type SingleWriterRun } from './workflow-driver.js';
import { decodeWire, isObject, MAX_WIRE_BYTES, type JsonObject } from './wire.js';
import type { GatedAdapterSource } from './request-accounting.js';

export interface ExperimentalHostOptions {
  readonly experimentalDsh: boolean;
  readonly candidate: string;
  readonly offlineReceipt: string;
  readonly worker: KernelWorkerLaunch;
  readonly execution?: { readonly parallel_agents?: boolean };
  readonly launchFile?: string;
}

function checkOptions(options: ExperimentalHostOptions): void {
  if (options.experimentalDsh !== true) throw new Error('experimental_dsh_opt_in_required');
  serialExecutionPolicy(options.execution);
  if (typeof options.candidate !== 'string' || options.candidate === ''
    || path.basename(options.candidate) !== options.candidate || ['.','..'].includes(options.candidate)) {
    throw new Error('host_admission_candidate_invalid');
  }
  for (const value of [options.offlineReceipt,options.worker.pythonExecutable,options.worker.engineRoot,options.worker.bootstrapPath]) {
    if (typeof value !== 'string' || !path.isAbsolute(value)) throw new Error('host_admission_absolute_path_required');
  }
  if (options.launchFile !== undefined && !path.isAbsolute(options.launchFile)) throw new Error('host_admission_absolute_path_required');
}

/** Runs the original read-only owner before a kernel, claim, or adapter exists. */
export async function admitExperimentalHost(options: ExperimentalHostOptions): Promise<JsonObject> {
  return await admitHost(options,'final');
}

// Qualification is private to the explicit CLI command. A caller of the public
// Host API cannot replace final admission with a core suite receipt.
async function admitHost(options: ExperimentalHostOptions, mode:'final'|'qualification'): Promise<JsonObject> {
  checkOptions(options);
  const {worker}=options;
  const argv=['-m','code2paper.integrations.dsh.host_admission','--bootstrap',worker.bootstrapPath,
    '--offline-receipt',options.offlineReceipt,'--candidate',options.candidate,'--parallel-agents','false'];
  if (options.launchFile !== undefined) argv.push('--launch-file',options.launchFile);
  if (mode === 'qualification') {
    if (options.launchFile === undefined) throw new Error('host_cli_launch_file_required');
    argv.push('--qualification-core');
  }
  const environment={...process.env,PYTHONPATH:path.join(worker.engineRoot,'src'),PYTHONDONTWRITEBYTECODE:'1'};
  for (const key of ['OPENAI_API_KEY','DEEPSEEK_API_KEY','ANTHROPIC_API_KEY','GOOGLE_API_KEY',
    'GEMINI_API_KEY','AZURE_OPENAI_API_KEY']) delete (environment as NodeJS.ProcessEnv)[key];
  const result=await new Promise<JsonObject>((resolve,reject)=>{
    execFile(worker.pythonExecutable,argv,{cwd:worker.engineRoot,env:environment,timeout:30_000,
      maxBuffer:64<<10,killSignal:'SIGKILL'},(error,stdout)=>{
      let receipt:JsonObject;
      try {const parsed=decodeWire(stdout.trim());if (!isObject(parsed)) throw new Error();receipt=parsed;}
      catch {reject(new Error('host_admission_process_failed'));return;}
      if (error !== null || receipt.admitted !== true) {
        const reason=typeof receipt.reason === 'string' && /^[a-z0-9_]+$/.test(receipt.reason)
          ? receipt.reason : 'host_admission_process_failed';
        reject(new Error(reason));return;
      }
      if (receipt.schema_version !== (mode === 'qualification' ? 'DshHostAdmissionV1' : 'DshTargetAdmissionV1') || receipt.scope !== (mode === 'qualification' ? 'dsh-stage04-qualification' : 'dsh-stage04-offline')
        || receipt.candidate !== options.candidate || receipt.parallel_agents !== false
        || receipt.model_execution_authorized !== false
        || (mode === 'qualification'
          ? receipt.qualification_only !== true || receipt.normal_entry_authorized !== false
          : receipt.qualification_only !== false || receipt.normal_entry_authorized !== true)
        || ['engine_digest','validator_digest','composition_digest','effective_config_digest',
          'bootstrap_digest','receipt_digest',...(mode === 'final' ? ['coverage_receipt_digest','runtime_authority_digest',
            'domain_read_set_digest','model_config_digest','backend_binding_digest','launch_digest'] : [])].some(key=>typeof receipt[key] !== 'string'
            || !/^sha256:[0-9a-f]{64}$/.test(receipt[key] as string))) {reject(new Error('host_admission_receipt_invalid'));return;}
      const target=receipt.target_scope;const namespace=receipt.network_namespace;
      if (mode === 'final' && (receipt.coverage_receipt_digest !== receipt.receipt_digest
        || !isObject(target) || Object.keys(target).sort().join(',') !== 'execution_id,task_epoch,task_id'
        || typeof target.execution_id !== 'string' || target.execution_id === ''
        || typeof target.task_id !== 'string' || target.task_id === ''
        || !Number.isSafeInteger(target.task_epoch) || (target.task_epoch as number)<0
        || !isObject(namespace) || Object.keys(namespace).sort().join(',') !== 'device,inode'
        || ![namespace.device,namespace.inode].every(value=>typeof value === 'number' && Number.isSafeInteger(value) && value>0))) {
        reject(new Error('host_admission_receipt_invalid'));return;
      }
      resolve(receipt);
    });
  });
  return result;
}

export interface ExperimentalWriterOptions extends ExperimentalHostOptions {
  readonly authority: Omit<KernelAuthorityConfig,'contractRef'>;
  readonly initialize: JsonObject;
  readonly frozenRef: JsonObject;
  readonly projectionRef: JsonObject;
  readonly run: Omit<SingleWriterRun,'authority'|'execution'|'verifyComposition'>;
}

/** Trusted Host integration; never registered as a model-facing command/tool. */
export async function executeExperimentalWriter(ctx: Context, options: ExperimentalWriterOptions): Promise<JsonObject> {
  return await executeAdmittedWriter(ctx,options,await admitExperimentalHost(options));
}

async function executeAdmittedWriter(ctx: Context, options: ExperimentalWriterOptions, admission:JsonObject): Promise<JsonObject> {
  if (options.authority.compositionDigest !== admission.composition_digest
    || options.run.input.composition_digest !== admission.composition_digest
    || options.initialize.validator_digest !== admission.validator_digest) throw new Error('host_admission_launch_mismatch');
  if (admission.schema_version === 'DshTargetAdmissionV1') {
    const target=admission.target_scope as JsonObject;const scope=options.authority.scope;
    if (target.execution_id !== scope.execution_id || target.task_id !== scope.task_id
      || target.task_epoch !== scope.task_epoch) throw new Error('host_admission_launch_mismatch');
  }
  const kernel=startKernelWorker(ctx,options.worker);
  try {
    await kernel.call('initialize',options.initialize);
    const ref=await kernel.call('task.prepare',{...options.authority.scope,frozen_ref:options.frozenRef,
      projection_ref:options.projectionRef,cap:options.run.input.post_clamp_max_output_tokens});
    if (!isObject(ref)) throw new Error('host_prepared_contract_invalid');
    const authority=new KernelAuthority(kernel,{...options.authority,contractRef:ref});
    const run=options.authority.accountingVersion==='c2p-dsh-task-loop-v2' ? runMultistepWriter : runSingleWriter;
    return await run(ctx,{...options.run,authority,execution:options.execution,
      verifyComposition:async()=>{await kernel.call('initialize',options.initialize);}});
  } finally {await kernel.close();}
}

async function readLaunch(file: string, expectedDigest: string): Promise<JsonObject> {
  const handle=await open(file,'r');
  let bytes:Buffer;
  try {
    const buffer=Buffer.alloc(MAX_WIRE_BYTES+1);
    let length=0;
    while (length<buffer.length) {
      const result=await handle.read(buffer,length,buffer.length-length,null);
      if (result.bytesRead === 0) break;
      length+=result.bytesRead;
    }
    bytes=buffer.subarray(0,length);
  } finally {await handle.close();}
  if (`sha256:${createHash('sha256').update(bytes).digest('hex')}` !== expectedDigest) throw new Error('host_admission_launch_changed');
  const value=decodeWire(bytes);
  if (!isObject(value)) throw new Error('host_admission_launch_invalid');
  return value;
}

/** Boot after the original owner admits the selected isolated offline scope. */
async function runOperatorLaunch(options: ExperimentalHostOptions, mode:'final'|'qualification'): Promise<JsonObject> {
  if (mode === 'final' && process.env.C2P_DSH_OFFLINE_EXECUTION !== '1') throw new Error('host_cli_offline_launcher_required');
  if (options.launchFile === undefined) throw new Error('host_cli_launch_file_required');
  const admission=await admitHost(options,mode);
  const admissionCompletedMs=Date.now();
  if (typeof admission.launch_digest !== 'string' || admission.launch_digest === '') throw new Error('host_admission_launch_binding_required');
  const launch=await readLaunch(options.launchFile,admission.launch_digest);
  const string=(key:string):string=>{
    const value=launch[key];if (typeof value !== 'string' || value === '') throw new Error('host_cli_launch_invalid');return value;
  };
  const object=(key:string):JsonObject=>{
    const value=launch[key];if (!isObject(value)) throw new Error('host_cli_launch_invalid');return value;
  };
  const config=string('config_path');const cwd=string('cwd');
  const overlays=launch.overlay_paths;
  if (!path.isAbsolute(config) || !path.isAbsolute(cwd) || !Array.isArray(overlays)
    || overlays.some(value=>typeof value !== 'string' || !path.isAbsolute(value))) throw new Error('host_cli_launch_invalid');
  const devRoot=process.env.C2P_DSH_DEV_ROOT;
  if (devRoot !== path.join(options.worker.engineRoot,'.dsh-dev/candidates',options.candidate)
    || process.env.C2P_DSH_CANDIDATE !== options.candidate) throw new Error('host_cli_candidate_mismatch');
  const {boot,loadProfileDirectory,loadOverlayPatches}=await import('@deepseek-ai/dsh-app-boot');
  const {provideCmdline}=await import('@deepseek-ai/dsh-cmdline');
  const PiAi=await import('@deepseek-ai/dsh-llm-pi-ai');
  const profileDir=path.join(devRoot,'home/profiles/code2paper-dev-compat');
  const profile=loadProfileDirectory('code2paper-opt-in',profileDir,path.join(devRoot,'runtime/node_modules/@deepseek-ai/dsh/package.json'));
  const ctx=await boot('code2paper-opt-in',config,[...profile.layers.flatMap(layer=>layer.patches),...profile.patches,
    ...overlays.flatMap(file=>loadOverlayPatches('code2paper-opt-in',file as string)),
    ...loadOverlayPatches('code2paper-opt-in',path.join(options.worker.engineRoot,'integrations/dsh/dev/offline.patch.yml')),
    {id:'web-runtime',config:{printUrl:false,openBrowser:false,surfaceContext:false,trustedHosts:[]}}],host=>{
    provideCmdline(host,{args:['--host','127.0.0.1','--port','0','--no-open'],exit:()=>{}});
  });
  let registration:ReturnType<Context['llm']['registerAdapter']> | undefined;
  try {
    let adapter:GatedAdapterSource | undefined;
    const register=ctx.llm.registerAdapter.bind(ctx.llm);
    ctx.llm.registerAdapter=(providers,value)=>{adapter=value as unknown as GatedAdapterSource;
      registration=register(providers,value);return registration;};
    try {await ctx.plugin(PiAi,object('provider_config') as never);} finally {ctx.llm.registerAdapter=register;}
    if (adapter === undefined || registration === undefined) throw new Error('host_cli_adapter_unavailable');
    // The driver owns the gated registration; retain the real public adapter
    // value rather than inspecting private runtime registries.
    registration();registration=undefined;
    const scope=object('scope');
    const receipt=await executeAdmittedWriter(ctx,{...options,
      authority:{scope:scope as unknown as KernelAuthorityConfig['scope'],
        caller:{executionId:String(scope.execution_id),runId:string('run_id'),hostGeneration:ctx.code2paperBridge.hostGeneration},
        owner:string('owner'),compositionDigest:String(admission.composition_digest),budgetRef:object('budget_ref')},
      initialize:object('initialize'),frozenRef:object('frozen_ref'),projectionRef:object('projection_ref'),
      run:{input:object('input') as unknown as SingleWriterRun['input'],projection:object('projection') as unknown as SingleWriterRun['projection'],
        adapter,cwd,signal:AbortSignal.timeout(300_000)}},admission);
    return mode === 'qualification'
      ? {schema_version:'DshHostQualificationResultV1',admission_scope:'dsh-stage04-qualification',
        qualification_only:true,normal_entry_authorized:false,model_execution_authorized:false,
        admission_completed_ms:admissionCompletedMs,receipt}
      : {schema_version:'DshHostExecutionResultV1',admission,admission_completed_ms:admissionCompletedMs,receipt};
  } finally {
    try {registration?.();await ctx.sessionPersistence.flush();} finally {await ctx.fiber.dispose();}
  }
}

/** `qualify` executes only the isolated offline qualification, never normal admission. */
export async function cliMain(argv: readonly string[]): Promise<number> {
  try {
    if (!['admit','run','qualify'].includes(argv[0] ?? '')) throw new Error('host_cli_command_invalid');
    const values=new Map<string,string>();
    let optIn=false;
    for (let index=1;index<argv.length;index++) {
      const key=argv[index]!;
      if (key === '--experimental-dsh') {if (optIn) throw new Error('host_cli_duplicate_option');optIn=true;continue;}
      if (!['--candidate','--offline-receipt','--python','--engine-root','--bootstrap','--parallel-agents','--launch-file'].includes(key)
        || values.has(key) || argv[index+1] === undefined || argv[index+1]!.startsWith('--')) throw new Error('host_cli_option_invalid');
      values.set(key,argv[++index]!);
    }
    const flag=values.get('--parallel-agents') ?? 'false';
    if (!['true','false'].includes(flag)) throw new Error('execution_parallel_flag_invalid');
    const options:ExperimentalHostOptions={experimentalDsh:optIn,candidate:values.get('--candidate') ?? '',
      offlineReceipt:values.get('--offline-receipt') ?? '',execution:{parallel_agents:flag === 'true'},
      ...(values.has('--launch-file') ? {launchFile:values.get('--launch-file')!} : {}),
      worker:{pythonExecutable:values.get('--python') ?? '',engineRoot:values.get('--engine-root') ?? '',
        bootstrapPath:values.get('--bootstrap') ?? ''}};
    checkOptions(options);
    const receipt=argv[0] === 'admit' ? await admitExperimentalHost(options)
      : await runOperatorLaunch(options,argv[0] === 'qualify' ? 'qualification' : 'final');
    process.stdout.write(`${JSON.stringify(receipt)}\n`);return 0;
  } catch (error) {
    const reason=error instanceof Error && /^[a-z0-9_]+$/.test(error.message) ? error.message : 'host_cli_failed';
    process.stdout.write(`${JSON.stringify({schema_version:'DshHostAdmissionV1',admitted:false,reason})}\n`);return 2;
  }
}

if (process.argv[1] !== undefined && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exitCode=await cliMain(process.argv.slice(2));
}
