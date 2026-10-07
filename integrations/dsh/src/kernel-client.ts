/** Host-private bounded JSONL over the real DSH subprocess service. */
import path from 'node:path';
import type { Context } from '@deepseek-ai/cordis';
import type { SubprocessHandle } from '@deepseek-ai/dsh-subprocess';
import { decodeWire, isObject, type JsonObject, type JsonValue } from './wire.js';

const FRAME_LIMIT = 1 << 20;
const RPC_TIMEOUT_MS = 30_000;
const METHODS = new Set(['initialize', 'context.compaction_prompt', 'task.bind_auxiliary', 'request.measure_auxiliary', 'request.measure_step', 'request.reserve_step', 'context.materials', 'context.read_grants', 'artifact.record', 'backend.release', 'backend.observe_quiescence', 'task.prepare', 'task.claim', 'task.recover', 'task.resume',
  'task.record_tool_candidate', 'task.bind', 'task.cancel', 'task.read', 'task.read_grant', 'task.limits', 'task.capture_raw', 'task.record_output', 'task.ingest_key', 'task.ingest', 'request.reserve',
  'request.dispatch', 'request.settle', 'request.mark_unknown', 'request.status', 'worker.status', 'worker.shutdown']);

interface Pending {
  readonly resolve: (value: JsonValue) => void;
  readonly reject: (error: Error) => void;
  readonly cleanup: () => void;
}

export class KernelClient {
  private sequence = 0;
  private frame = Buffer.alloc(0);
  private readonly pending = new Map<number, Pending>();
  private readonly abandoned = new Set<number>();
  private failed: Error | undefined;
  readonly handle: SubprocessHandle;

  constructor(handle: SubprocessHandle) {
    this.handle=handle;
    if (handle.stdin === undefined || handle.stdout === undefined) throw new Error('kernel_stdio_unavailable');
    handle.stdout.on('data', (chunk: Buffer) => this.receive(chunk));
    handle.stdout.on('error', () => this.fail(new Error('kernel_stdout_failed')));
    handle.stdout.on('end', () => this.fail(new Error(this.frame.length > 0 ? 'kernel_frame_incomplete' : 'kernel_channel_closed')));
    void handle.done.catch(() => this.fail(new Error('kernel_process_failed')));
  }

  private fail(error: Error): void {
    if (this.failed !== undefined) return;
    this.failed = error;
    for (const pending of this.pending.values()) {
      pending.cleanup(); pending.reject(error);
    }
    this.pending.clear();
  }

  private receive(chunk: Buffer): void {
    if (this.failed !== undefined) return;
    let offset = 0;
    for (;;) {
      const newline = chunk.indexOf(10, offset);
      const end = newline < 0 ? chunk.length : newline;
      const segment = chunk.subarray(offset, end);
      if (this.frame.length + segment.length > FRAME_LIMIT) {
        this.fail(new Error('kernel_frame_too_large')); return;
      }
      this.frame = Buffer.concat([this.frame, segment]);
      if (newline < 0) return;
      const raw = this.frame;
      this.frame = Buffer.alloc(0);
      offset = newline + 1;
      try {
        const response = decodeWire(raw);
        if (!isObject(response) || response.jsonrpc !== '2.0' || typeof response.id !== 'number'
          || !Number.isSafeInteger(response.id) || response.id < 1
          || Object.keys(response).some((key) => !['jsonrpc', 'id', 'result', 'error'].includes(key))
          || (Object.hasOwn(response, 'result') === Object.hasOwn(response, 'error'))) {
          throw new Error('kernel_response_invalid');
        }
        const pending = this.pending.get(response.id);
        if (pending === undefined) {
          if (this.abandoned.delete(response.id)) continue;
          throw new Error('kernel_response_id_unknown');
        }
        this.pending.delete(response.id); pending.cleanup();
        if (response.error !== undefined) {
          if (!isObject(response.error) || typeof response.error.message !== 'string'
            || typeof response.error.code !== 'number'
            || Object.keys(response.error).some((key) => !['code', 'message'].includes(key))) {
            pending.reject(new Error('kernel_error_response_invalid'));
          } else pending.reject(new Error(response.error.message));
        } else pending.resolve(response.result!);
      } catch {
        this.fail(new Error('kernel_protocol_failed')); return;
      }
      if (offset === chunk.length) return;
    }
  }

  async call(method: string, params: JsonObject, signal?: AbortSignal): Promise<JsonValue> {
    if (!METHODS.has(method)) throw new Error('kernel_method_unavailable');
    if (this.failed !== undefined) throw this.failed;
    if (signal?.aborted === true) throw new Error('kernel_rpc_aborted');
    if (this.pending.size !== 0) throw new Error('kernel_rpc_inflight');
    const id = ++this.sequence;
    const raw = Buffer.from(JSON.stringify({ jsonrpc: '2.0', id, method, params }, (_key, value: unknown) => {
      if (value === undefined || typeof value === 'function' || typeof value === 'symbol' || typeof value === 'bigint'
        || (typeof value === 'number' && (!Number.isFinite(value) || (Number.isInteger(value) && !Number.isSafeInteger(value))))) {
        throw new Error('kernel_request_not_json');
      }
      return value;
    }), 'utf8');
    // The shared decoder rejects unsafe numbers, duplicate/unicode damage and
    // non-wire values before any bytes enter the worker's stdin.
    decodeWire(raw);
    if (raw.length > FRAME_LIMIT) throw new Error('kernel_frame_too_large');
    return await new Promise<JsonValue>((resolve, reject) => {
      const abandon = (code: string): void => {
        const pending = this.pending.get(id);
        if (pending === undefined) return;
        this.pending.delete(id); this.abandoned.add(id); pending.cleanup(); reject(new Error(code));
      };
      const onAbort = (): void => abandon('kernel_rpc_aborted');
      const timer = setTimeout(() => abandon('kernel_rpc_timeout'), RPC_TIMEOUT_MS);
      const cleanup = (): void => { clearTimeout(timer); signal?.removeEventListener('abort', onAbort); };
      this.pending.set(id, { resolve, reject, cleanup });
      signal?.addEventListener('abort', onAbort, { once: true });
      this.handle.stdin!.write(Buffer.concat([raw, Buffer.from('\n')]), (error) => {
        if (error !== null && error !== undefined) this.fail(new Error('kernel_stdin_failed'));
      });
    });
  }

  /** This proves only the managed worker scope, never model/provider exit. */
  async close(): Promise<void> {
    this.handle.stdin?.end();
    const cleanupSignal = AbortSignal.timeout(5_000);
    if (await this.handle.waitForExit(cleanupSignal) !== true) {
      await this.handle.terminate();
      throw new Error('kernel_worker_scope_not_quiescent');
    }
  }
}

export interface KernelWorkerLaunch {
  readonly pythonExecutable: string;
  readonly engineRoot: string;
  readonly bootstrapPath: string;
}

/** Only the operator supplies these paths; no tool/model input enters argv. */
export function startKernelWorker(ctx: Context, config: KernelWorkerLaunch): KernelClient {
  for (const key of ['pythonExecutable', 'engineRoot', 'bootstrapPath'] as const) {
    const value = config[key];
    if (typeof value !== 'string' || !path.isAbsolute(value)) {
    throw new Error('kernel_launch_absolute_path_required');
    }
  }
  if (Object.keys(config).some((key) => !['pythonExecutable', 'engineRoot', 'bootstrapPath'].includes(key))) {
    throw new Error('kernel_launch_unknown_field');
  }
  const handle = ctx.subprocess.spawn({
    argv: [config.pythonExecutable, '-m', 'code2paper.integrations.dsh.worker', '--bootstrap', config.bootstrapPath],
    cwd: config.engineRoot, graceMs: 1_000,
    env: { PYTHONPATH: path.join(config.engineRoot, 'src'), PYTHONDONTWRITEBYTECODE: '1',
      OPENAI_API_KEY: undefined, DEEPSEEK_API_KEY: undefined },
    stdio: { stdin: 'pipe', stdout: 'pipe', stderr: { maxBytes: 64 << 10 } },
  });
  return new KernelClient(handle);
}
