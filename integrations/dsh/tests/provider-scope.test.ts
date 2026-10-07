/** R04 local owned-process observation. No model, worker, domain or fee receipt. */
import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, readFileSync, symlinkSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { after, before, test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';
import { boot, loadOverlayPatches, loadProfileDirectory } from '@deepseek-ai/dsh-app-boot';
import { provideCmdline } from '@deepseek-ai/dsh-cmdline';
import type { Context } from '@deepseek-ai/cordis';
import type { SubprocessHandle } from '@deepseek-ai/dsh-subprocess';

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const devRoot = process.env.C2P_DSH_DEV_ROOT!;
const runtime = path.join(devRoot, 'runtime');
const python = path.join(devRoot, 'pyworker/bin/python');
let ctx: Context;
let root: string;

// No setsid/detach: the survivor stays in the actual handle's managed range.
// The watchdog prevents this test fixture living indefinitely after catastrophic
// Host failure. Its expiry is never accepted as proof of requested cleanup.
const helper = String.raw`import os, signal, sys, time
from pathlib import Path
root = Path(sys.argv[1])
ready = root / 'survivor-ready.json'
heartbeat = root / 'heartbeat.txt'
pid = os.fork()
if pid:
    deadline = time.monotonic() + 10
    while not ready.exists():
        if time.monotonic() >= deadline:
            os._exit(3)
        time.sleep(0.01)
    os._exit(0)
signal.signal(signal.SIGTERM, signal.SIG_IGN)
null = os.open(os.devnull, os.O_RDWR)
for fd in (0, 1, 2):
    os.dup2(null, fd)
if null > 2:
    os.close(null)
import json
ready.write_text(json.dumps(dict(pid=os.getpid(), pgid=os.getpgrp(), parent_pid=os.getppid())))
deadline = time.monotonic() + 60
with heartbeat.open('a') as stream:
    while time.monotonic() < deadline:
        stream.write(str(time.monotonic_ns()) + '\n')
        stream.flush()
        time.sleep(0.025)
os._exit(4)
`;

before(async () => {
  assert.ok(process.env.C2P_DSH_RUN_ROOT, 'actual offline launcher output root required');
  assert.ok(process.env.C2P_DSH_DEV_ROOT, 'selected candidate required');
  root = mkdtempSync(path.join(process.env.C2P_DSH_RUN_ROOT!, 'stage04-provider-scope-'));
  mkdirSync(path.join(root, 'node_modules/@code2paper'), { recursive: true });
  symlinkSync(path.join(runtime, 'node_modules/@deepseek-ai'), path.join(root, 'node_modules/@deepseek-ai'), 'dir');
  symlinkSync(path.join(devRoot, 'home/profiles/node_modules/@code2paper/dsh-bundle'),
    path.join(root, 'node_modules/@code2paper/dsh-bundle'), 'dir');
  const profileDir = path.join(devRoot, 'home/profiles/code2paper-dev-compat');
  const profile = loadProfileDirectory('stage04-provider-scope', profileDir,
    path.join(runtime, 'node_modules/@deepseek-ai/dsh/package.json'));
  const config = path.join(root, 'cordis.yml');
  writeFileSync(config, readFileSync(path.join(profileDir, 'cordis.yml')));
  const overlay = path.join(root, 'overlay.yml');
  writeFileSync(overlay, JSON.stringify([{ id: 'web-runtime', config: {
    printUrl: false, openBrowser: false, surfaceContext: false, trustedHosts: [],
  } }]));
  ctx = await boot('stage04-provider-scope', config, [
    ...profile.layers.flatMap(layer => layer.patches), ...profile.patches,
    ...loadOverlayPatches('stage04-provider-scope', path.join(repo, 'integrations/dsh/dev/offline.patch.yml')),
    ...loadOverlayPatches('stage04-provider-scope', overlay),
  ], host => {
    provideCmdline(host, { args: ['--host', '127.0.0.1', '--port', '0', '--no-open'], exit: () => {} });
  });
});

after(async () => { await ctx?.fiber.dispose(); });

async function bounded<T>(promise: Promise<T>, milliseconds: number): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([promise, new Promise<never>((_resolve, reject) => {
      timer = setTimeout(() => reject(new Error('owned fixture direct outcome deadline')), milliseconds);
    })]);
  } finally {
    if (timer !== undefined) clearTimeout(timer);
  }
}

function heartbeat(file: string): string {
  try { return readFileSync(file, 'utf8'); } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return '';
    throw error;
  }
}

for (const stop of ['terminate', 'abort'] as const) {
  test(`actual ${stop} joins survivor after parent done and a separately bounded wait refuses quiescence`, async () => {
    const ownedRoot = path.join(root, stop);
    mkdirSync(ownedRoot);
    const helperPath = path.join(ownedRoot, 'survivor.py');
    writeFileSync(helperPath, helper);
    const cancellation = new AbortController();
    const observations: Record<string, unknown> = {
      schema_version: 'Stage04OwnedProviderScopeObservationV1', stop,
      observed_scope: 'local-owned-helper-process-range', model_execution: false,
      remote_provider_quiescence: 'not_observed',
    };
    let handle: SubprocessHandle | undefined;
    let cleanupObserved = false;
    try {
      handle = ctx.subprocess.spawn({
        argv: [python, helperPath, ownedRoot], cwd: ownedRoot, graceMs: 100,
        signal: cancellation.signal,
        stdio: { stdin: 'ignore', stdout: { maxBytes: 4096 }, stderr: { maxBytes: 4096 } },
      });
      const outcome = await bounded(handle.done, 15_000);
      observations.direct_outcome = outcome;
      assert.deepEqual(outcome, { exitCode: 0, signal: null });
      const survivor = JSON.parse(readFileSync(path.join(ownedRoot, 'survivor-ready.json'), 'utf8')) as {
        pid: number; pgid: number; parent_pid: number;
      };
      observations.survivor = survivor;
      assert.ok(Number.isSafeInteger(survivor.pid) && survivor.pid > 0);
      // PID liveness is diagnostic only; it does not release any occupancy.
      process.kill(survivor.pid, 0);
      const heartbeatPath = path.join(ownedRoot, 'heartbeat.txt');
      const beforeWait = heartbeat(heartbeatPath);
      const observationSignal = AbortSignal.timeout(300);
      const prematurelyEmpty = await handle.waitForExit(observationSignal);
      observations.pre_cleanup_wait = { empty: prematurelyEmpty, signal_aborted: observationSignal.aborted };
      assert.equal(prematurelyEmpty, false);
      assert.equal(observationSignal.aborted, true);
      const afterWait = heartbeat(heartbeatPath);
      assert.ok(afterWait.length > beforeWait.length, 'survivor must perform actual work after direct parent exit');
      observations.heartbeat_bytes_before_wait = Buffer.byteLength(beforeWait);
      observations.heartbeat_bytes_after_wait = Buffer.byteLength(afterWait);
      if (stop === 'terminate') handle.terminate();
      else cancellation.abort(new Error('owned fixture cancellation'));
      // Never reuse the aborted observation signal as the cleanup deadline.
      const cleanupSignal = AbortSignal.timeout(5_000);
      cleanupObserved = await handle.waitForExit(cleanupSignal);
      observations.cleanup_wait = { empty: cleanupObserved, signal_aborted: cleanupSignal.aborted };
      assert.equal(cleanupObserved, true, 'actual managed range must be observed empty after requested cleanup');
      assert.equal(cleanupSignal.aborted, false);
      const afterCleanup = heartbeat(heartbeatPath);
      await delay(150);
      assert.equal(heartbeat(heartbeatPath), afterCleanup, 'owned survivor must stop writing after range quiescence');
      observations.heartbeat_bytes_after_cleanup = Buffer.byteLength(afterCleanup);
      observations.heartbeat_stable_after_cleanup = true;
    } finally {
      // Failures still attempt the same owned provider cleanup; no raw PID kill,
      // worker close, fee settlement, or domain publication substitutes for it.
      try {
        if (handle && !cleanupObserved) {
          handle.terminate();
          cleanupObserved = await handle.waitForExit(AbortSignal.timeout(5_000));
          observations.failure_cleanup_empty = cleanupObserved;
        }
      } finally {
        writeFileSync(path.join(ownedRoot, 'observations.json'), JSON.stringify(observations, null, 2));
      }
      if (handle) assert.equal(cleanupObserved, true, 'owned range remained unproven after failure cleanup');
    }
  });
}
