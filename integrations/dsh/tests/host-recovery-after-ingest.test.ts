/** Actual worker process cut; shared real provider/Session harness. */
process.env['C2P_STAGE04_TEST_RECOVERY_CUT']='after-ingest';
await import(new URL('./host-provider.test.ts',import.meta.url).href);
export {};
