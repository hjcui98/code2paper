/** An unregistered native function remains rejected, with exact completion accounting. */
process.env['C2P_STAGE04_TEST_OUTCOME']='unknown_tool';
await import(new URL('./host-provider.test.ts',import.meta.url).href);
