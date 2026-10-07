/** A fake provider ignoring selection still cannot turn text into a tool. */
process.env['C2P_STAGE04_TEST_NATIVE_TOOL_CHOICE']='1';
process.env['C2P_STAGE04_TEST_OUTCOME']='text_stop';
await import(new URL('./host-provider.test.ts',import.meta.url).href);
