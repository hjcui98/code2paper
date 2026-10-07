/** Real Host/provider bytes with an atom witness outside the frozen contract. */
process.env['C2P_STAGE04_TEST_OUTCOME']='wrong_atom_binding';
await import(new URL('./host-provider.test.ts',import.meta.url).href);
export {};
