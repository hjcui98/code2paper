/** Actual SDK forced compaction child + two Writer steps, original ledger/recovery. */
process.env['C2P_STAGE04_MULTISTEP']='1';
process.env['C2P_STAGE04_COMPACTION']='1';
process.env['C2P_STAGE04_TEST_OUTCOME']='draft';
await import(new URL('./host-provider.test.ts',import.meta.url).href);
export {};
