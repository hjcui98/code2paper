/** Real usage with zero billed input survives a provider error; no finish mint. */
process.env['C2P_STAGE04_TEST_NATIVE_TOOL_CHOICE']='1';
process.env['C2P_STAGE04_TEST_OUTCOME']='provider_error_cached_usage';
await import(new URL('./host-provider.test.ts',import.meta.url).href);
