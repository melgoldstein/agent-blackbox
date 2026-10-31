# Contributing

Start with a reproducible failure, expected behavior, and a minimal trace without secrets. Changes to replay semantics need tests for both accepted and rejected executions. Keep persistence and workflow behavior independent from the UI.

Run the development commands in the README before opening a pull request. Benchmark changes to the recording path with the same workload and disclose the environment. Do not check in real credentials, private traces, or fabricated measurements.

Useful next contributions: branch alignment between unrelated traces, async storage that preserves explicit durability boundaries, and application integrations with narrowly defined replay contracts.
