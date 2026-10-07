/** Actual assessor rejection remains primary when backend cleanup also fails. */
process.env['C2P_STAGE04_TEST_OUTCOME']='invalid_content';
process.env['C2P_STAGE04_RELEASE_FAULT']='1';
await import(new URL('./host-provider.test.ts',import.meta.url).href);
export {};
