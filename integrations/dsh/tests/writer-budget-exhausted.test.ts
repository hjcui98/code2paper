/** Actual Host and private kernel refusal; provider arrivals are counted. */
process.env['C2P_STAGE04_TEST_OUTCOME']='budget_exhausted';
await import(new URL('./host-provider.test.ts',import.meta.url).href);
export {};
