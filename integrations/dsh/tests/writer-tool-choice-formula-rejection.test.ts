/** Forced native selection cannot authorize a foreign formula package. */
process.env['C2P_STAGE04_TEST_NATIVE_TOOL_CHOICE']='1';
process.env['C2P_STAGE04_TEST_OUTCOME']='wrong_formula_binding';
await import(new URL('./host-provider.test.ts',import.meta.url).href);
