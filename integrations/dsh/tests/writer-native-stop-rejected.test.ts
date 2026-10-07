/** A content refusal still settles and releases an actually completed native stop. */
process.env['C2P_STAGE04_TEST_OUTCOME']='wrong_atom_binding';
process.env['C2P_STAGE04_NATIVE_TOOL_FINISH']='stop';
await import(new URL('./host-provider.test.ts',import.meta.url).href);
