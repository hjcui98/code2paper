/** Ordinary JSON-looking text is rejected; actual native completion still spends fees. */
process.env['C2P_STAGE04_TEST_OUTCOME']='text_stop';
await import(new URL('./host-provider.test.ts',import.meta.url).href);
