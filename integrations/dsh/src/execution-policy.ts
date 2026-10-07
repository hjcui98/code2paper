/** Versioned opt-in execution policy. Stage A grants one leaf/request only. */
export interface SerialExecutionPolicy {
  readonly version: 'dsh-serial-execution/1';
  readonly requestedParallel: false;
  readonly effectiveParallel: false;
  readonly maxLeafTasks: 1;
  readonly maxBackendRequests: 1;
  readonly maxRequestsPerEpoch: 1;
}

export function serialExecutionPolicy(input: unknown = {}): SerialExecutionPolicy {
  if (input === null || typeof input !== 'object' || Array.isArray(input)) {
    throw new Error('execution_policy_invalid');
  }
  const config = input as Record<string, unknown>;
  if (Object.keys(config).some((key) => key !== 'parallel_agents')) throw new Error('execution_policy_unknown_field');
  if (config.parallel_agents !== undefined && typeof config.parallel_agents !== 'boolean') {
    throw new Error('execution_parallel_flag_invalid');
  }
  if (config.parallel_agents === true) throw new Error('parallel_execution_unsupported');
  return Object.freeze({ version: 'dsh-serial-execution/1', requestedParallel: false,
    effectiveParallel: false, maxLeafTasks: 1, maxBackendRequests: 1, maxRequestsPerEpoch: 1 });
}
