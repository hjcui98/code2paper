/** Serial Stage03 evidence runner; does not alter the runtime or select another peer. */
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const [output, mode] = process.argv.slice(2);
if (output === undefined || !['build', 'focused', 'focused-module', 'compat', 'b02', 'audit'].includes(mode)) throw new Error('usage: stage03-run.mjs OUTPUT_ROOT build|focused|focused-module|compat|b02|audit');
const candidate = '0.2.0-rc.1+loop-origin.1';
const devRoot = path.join(repo, '.dsh-dev/candidates', candidate);
const manifest = JSON.parse(readFileSync(path.join(devRoot, 'manifest.json'), 'utf8'));
const npm = path.join(path.dirname(process.execPath), '../lib/node_modules/npm/bin/npm-cli.js');
const env = { ...process.env, C2P_DSH_CANDIDATE: candidate, C2P_DSH_DEV_ROOT: devRoot, PYTHONDONTWRITEBYTECODE: '1' };
mkdirSync(output, { recursive: true });
const actions = mode === 'build'
  ? ['typecheck', 'build', 'stage'].map(action => ({ label: action, argv: [manifest.node, npm, '--prefix', 'integrations/dsh', 'run', action] }))
  : (mode === 'focused' || mode === 'focused-module')
    ? [{ label: 'wire-writer-request', argv: ['python', ...(mode === 'focused-module' ? ['-m', 'scripts.dsh_dev'] : ['scripts/dsh_dev.py']), '--candidate', candidate, 'test', '--',
      path.join(repo, 'integrations/dsh/tests/wire.test.ts'), path.join(repo, 'integrations/dsh/tests/writer-request.test.ts')] }]
    : mode === 'compat' ? [{ label: 'compat', argv: [manifest.node, npm, '--prefix', 'integrations/dsh', 'run', 'test:compat'] }]
      : mode === 'b02' ? [{ label: 'b02', argv: ['python', '-m', 'pytest', '-q', 'integrations/dsh/dev/tests'] }]
      : [{ label: 'audit', argv: ['python', 'scripts/dsh_dev.py', '--candidate', candidate, 'audit'] }];
const sanitize = value => value.replace(/([?&](?:token|key|secret|password)=)[^\s&"'<>]+/gi, '$1<redacted>')
  .replace(/(authorization["']?\s*[:=]\s*["']?)(?:Bearer\s+)?[^\s,"'}]+/gi, '$1<redacted>');
for (const action of actions) {
  const started = new Date().toISOString();
  const result = spawnSync(action.argv[0], action.argv.slice(1), { cwd: repo, env, encoding: 'utf8', timeout: 300000, maxBuffer: 20 << 20 });
  const log = sanitize(`${result.stdout ?? ''}${result.stderr ?? ''}`);
  const logPath = path.join(output, `${action.label}.log`);
  writeFileSync(logPath, log, { flag: 'wx' });
  const record = { argv: action.argv, cwd: repo, started, finished: new Date().toISOString(),
    candidate, dev_root: devRoot, node: process.execPath, status: result.status, signal: result.signal,
    error: result.error?.message, log: logPath, log_sha256: createHash('sha256').update(log).digest('hex') };
  writeFileSync(path.join(output, `${action.label}.command.json`), `${JSON.stringify(record, null, 2)}\n`, { flag: 'wx' });
  process.stdout.write(`${action.label}: exit=${String(result.status)} log=${logPath}\n`);
  if (result.error !== undefined || result.status !== 0) { process.stdout.write(log.slice(-12000)); process.exit(1); }
}
