/** Actual-byte measurements for I01; Python owns the canonical composition digest. */
import { createHash } from 'node:crypto';
import { lstat, readFile, readdir, readlink, realpath, stat, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const packageRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const repoRoot = path.resolve(packageRoot, '../..');

export async function measureFile(location) {
  const resolved = await realpath(location);
  const bytes = await readFile(resolved);
  return { location, resolved, size: bytes.length, sha256: createHash('sha256').update(bytes).digest('hex') };
}

/** Match the existing development inventory: relative links, no external targets. */
export async function measureTree(location) {
  const root = await realpath(location);
  const entries = {};
  async function walk(directory) {
    for (const name of (await readdir(directory)).sort()) {
      const full = path.join(directory, name);
      const relative = path.relative(root, full).split(path.sep).join('/');
      const info = await lstat(full);
      if (info.isSymbolicLink()) {
        const target = await realpath(full);
        const link = await readlink(full);
        if (path.isAbsolute(link) || (target !== root && !target.startsWith(`${root}${path.sep}`))) {
          throw new Error(`external tree symlink: ${full}`);
        }
        entries[relative] = { link };
      } else if (info.isDirectory()) await walk(full);
      else if (info.isFile()) {
        const measured = await measureFile(full);
        entries[relative] = { sha256: measured.sha256, size: measured.size };
      } else throw new Error(`unsupported filesystem entry: ${full}`);
    }
  }
  await walk(root);
  return { location, resolved: root, entries };
}

/** Resolve at the staged Loader entry and at the TS development consumer separately. */
export async function measureEnvironment(devRoot) {
  const staged = path.join(devRoot, 'home/profiles/node_modules/@code2paper/dsh-bundle');
  const stagedEntry = path.join(staged, 'lib/index.js');
  const peerLink = path.join(packageRoot, 'node_modules/@deepseek-ai');
  const resolveAt = (anchor) => createRequire(anchor);
  const names = [
    '@deepseek-ai/cordis', '@deepseek-ai/cordis-plugin-loader', '@deepseek-ai/dsh-app-boot',
    '@deepseek-ai/dsh-agent', '@deepseek-ai/dsh-agent-loop', '@deepseek-ai/dsh-agent-preset-registry',
    '@deepseek-ai/dsh-system-prompt', '@deepseek-ai/dsh-llm', '@deepseek-ai/dsh-llm-pi-ai',
    '@deepseek-ai/dsh-session', '@deepseek-ai/dsh-subagent', '@deepseek-ai/dsh-tools',
  ];
  const consumers = {};
  for (const [name, anchor] of [['staged', stagedEntry], ['development', path.join(packageRoot, 'src/index.ts')]]) {
    const resolver = resolveAt(anchor);
    const modules = {};
    for (const specifier of names) modules[specifier] = await measureFile(resolver.resolve(specifier));
    consumers[name] = { anchor: await measureFile(anchor), modules };
  }
  const files = {};
  for (const location of [
    path.join(packageRoot, 'package.json'), path.join(packageRoot, 'package-lock.json'),
    path.join(packageRoot, 'tsconfig.json'), path.join(packageRoot, 'lib/build-receipt.json'),
    path.join(packageRoot, 'presets/code2paper.patch.yml'), path.join(packageRoot, 'cordis.patch.yml'),
    path.join(devRoot, 'manifest.json'), path.join(devRoot, 'toolchain.json'),
    path.join(devRoot, 'runtime/package-lock.json'),
  ]) files[path.relative(repoRoot, location)] = await measureFile(location);
  if (!(await stat(process.execPath)).isFile()) throw new Error('Node executable is not a file');
  return {
    measurement_version: 'c2p-stage03-actual-bytes/1',
    digest_authority: 'python',
    node: { ...await measureFile(process.execPath), version: process.version },
    peer_link: { location: peerLink, link: await readlink(peerLink), resolved: await realpath(peerLink) },
    consumers, files,
    runtime: await measureTree(path.join(devRoot, 'runtime')),
    build: await measureTree(path.join(packageRoot, 'lib')),
    staging: await measureTree(staged),
  };
}

if (process.argv[1] !== undefined && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const [devRoot, output] = process.argv.slice(2);
  if (devRoot === undefined || output === undefined) throw new Error('usage: stage03-measure.mjs DEV_ROOT OUTPUT_JSON');
  const measured = await measureEnvironment(path.resolve(devRoot));
  await writeFile(output, `${JSON.stringify(measured, null, 2)}\n`, { flag: 'wx' });
  process.stdout.write(`measured ${Object.keys(measured.runtime.entries).length} runtime entries; output=${output}\n`);
}
