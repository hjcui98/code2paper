/** Explicit provider selection still goes through the original Writer gates. */
process.env['C2P_STAGE04_TEST_NATIVE_TOOL_CHOICE']='1';
process.env['C2P_STAGE04_TEST_OUTCOME']='draft';
await import(new URL('./host-provider.test.ts',import.meta.url).href);
