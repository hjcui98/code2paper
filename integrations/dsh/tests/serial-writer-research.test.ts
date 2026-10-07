/** Typed gap follows the same actual single-Writer chain without auto-retry. */
process.env['C2P_STAGE04_TEST_OUTCOME']='research_required';
await import(new URL('./host-provider.test.ts',import.meta.url).href);
export {};
