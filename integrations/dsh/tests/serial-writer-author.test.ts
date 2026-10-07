/** Original author page has no atom/formula obligations; technical obligations remain. */
process.env['C2P_STAGE04_TEST_OUTCOME']='draft';
process.env['C2P_STAGE04_TEST_PAGE_KIND']='author';
await import(new URL('./host-provider.test.ts',import.meta.url).href);
export {};
