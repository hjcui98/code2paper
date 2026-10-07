/** Actual Host rechecks frozen config bytes before creating a task claim. */
process.env['C2P_STAGE04_TEST_OUTCOME']='composition_drift';
await import(new URL('./host-provider.test.ts',import.meta.url).href);
export {};
