/** Actual pi-ai/native wire; original content owner refuses, observed fees remain. */
process.env['C2P_STAGE04_TEST_OUTCOME']='invalid_content';
await import(new URL('./host-provider.test.ts',import.meta.url).href);
export {};
