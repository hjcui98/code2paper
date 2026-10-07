import assert from 'node:assert/strict';
import { accessSync, constants, readFileSync, realpathSync } from 'node:fs';
import { connect, createServer } from 'node:net';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

const packageDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const devRoot = process.env.C2P_DSH_DEV_ROOT
  ? path.resolve(process.env.C2P_DSH_DEV_ROOT)
  : path.resolve(packageDir, '../../.dsh-dev');

test('compat tests have an isolated DSH home, scrubbed credentials, and readonly runtime/source', () => {
  assert.equal(process.env.DSH_HOME, path.join(devRoot, 'home'));
  const runRoot = process.env.C2P_DSH_RUN_ROOT;
  assert.ok(runRoot && path.isAbsolute(runRoot), 'launcher must supply an absolute run root');
  assert.equal(realpathSync(runRoot), runRoot, 'selected output must be canonical');
  if (runRoot !== path.join(devRoot, 'run')) {
    assert.ok(runRoot.startsWith('/tmp/') && runRoot !== '/tmp', 'explicit output stays in a fresh task directory');
  }
  for (const key of ['OPENAI_API_KEY', 'DEEPSEEK_API_KEY', 'HTTPS_PROXY', 'NODE_OPTIONS', 'NODE_PATH', 'PYTHONPATH']) {
    assert.equal(process.env[key], undefined, `${key} must not be inherited`);
  }
  assert.throws(() => accessSync(path.join(devRoot, 'runtime'), constants.W_OK));
  assert.throws(() => accessSync(packageDir, constants.W_OK));
  accessSync(runRoot, constants.W_OK);
  const interfaces = readFileSync('/proc/net/dev', 'utf8').split('\n').slice(2)
    .filter((line) => line.includes(':')).map((line) => line.split(':')[0]?.trim());
  assert.deepEqual(interfaces, ['lo'], 'offline tests must have only their own loopback interface');
});

test('offline namespace still supports a local fixture server', async () => {
  const server = createServer((socket) => socket.end('isolated-fixture'));
  await new Promise<void>((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', resolve);
  });
  try {
    const address = server.address();
    assert.ok(address && typeof address !== 'string');
    const response = await new Promise<string>((resolve, reject) => {
      const socket = connect(address.port, '127.0.0.1');
      let data = '';
      socket.setEncoding('utf8');
      socket.on('data', (chunk: string) => { data += chunk; });
      socket.once('error', reject);
      socket.once('end', () => resolve(data));
    });
    assert.equal(response, 'isolated-fixture');
  } finally {
    await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  }
});
