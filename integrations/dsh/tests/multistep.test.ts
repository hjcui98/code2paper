/** Actual two-step SDK Writer/read, original Worker fees and fresh recovery. */
process.env['C2P_STAGE04_MULTISTEP']='1';
process.env['C2P_STAGE04_TEST_OUTCOME']='draft';
await import(new URL('./host-provider.test.ts',import.meta.url).href);
export {};
