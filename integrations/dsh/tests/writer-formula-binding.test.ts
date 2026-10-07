/** Real Host/provider bytes with a formula reference outside the frozen contract. */
process.env['C2P_STAGE04_TEST_OUTCOME']='wrong_formula_binding';
await import(new URL('./host-provider.test.ts',import.meta.url).href);
export {};
