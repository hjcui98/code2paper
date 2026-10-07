/** Native terminal with provider stop keeps the original strict completion proof. */
process.env['C2P_STAGE04_TEST_OUTCOME']='draft';
process.env['C2P_STAGE04_NATIVE_TOOL_FINISH']='stop';
await import(new URL('./host-provider.test.ts',import.meta.url).href);
