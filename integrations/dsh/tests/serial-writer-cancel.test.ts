/** Actual HTTP arrival followed by cancellation: unknown retains the original fee reservation. */
process.env['C2P_STAGE04_TEST_OUTCOME']='cancel';
await import(new URL('./host-provider.test.ts',import.meta.url).href);
export {};
