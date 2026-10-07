/** Actual native rejection, original fees and exact-owner release; isolated provider only. */
process.env['C2P_STAGE04_TEST_OUTCOME']='packet10_original';
await import(new URL('./host-provider.test.ts',import.meta.url).href);
