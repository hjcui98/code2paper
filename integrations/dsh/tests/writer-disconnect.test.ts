/** Actual native transport lifecycle; no production provider calls. */
process.env['C2P_STAGE04_TEST_NATIVE_TOOL_CHOICE']='1';
process.env['C2P_STAGE04_TEST_OUTCOME']='disconnect';
await import(new URL('./host-provider.test.ts',import.meta.url).href);
