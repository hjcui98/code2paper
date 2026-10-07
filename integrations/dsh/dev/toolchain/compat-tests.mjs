import { readdir } from 'node:fs/promises';
import path from 'node:path';

/** Discover source tests without relying on shell glob expansion. */
export async function discoverCompatTests(packageDir) {
  const tests = [];
  async function visit(directory) {
    let entries;
    try {
      entries = await readdir(directory, { withFileTypes: true });
    } catch (error) {
      if (error.code === 'ENOENT') return;
      throw error;
    }
    for (const entry of entries) {
      if (['node_modules', 'build', 'lib'].includes(entry.name)) continue;
      const fullPath = path.join(directory, entry.name);
      if (entry.isDirectory()) await visit(fullPath);
      else if (entry.isFile() && entry.name.endsWith('.test.ts')) tests.push(fullPath);
    }
  }
  await visit(path.join(packageDir, 'dev', 'toolchain'));
  await visit(path.join(packageDir, 'tests'));
  return tests.sort();
}
