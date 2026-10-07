/** An SSE error/DONE with SDK default zero usage must retain unknown cost. */
process.env['C2P_STAGE04_TEST_NATIVE_TOOL_CHOICE']='1';
process.env['C2P_STAGE04_TEST_OUTCOME']='provider_error';
await import(new URL('./host-provider.test.ts',import.meta.url).href);
