# Benchmark methodology

Correctness comes before speed. A fast failure stays a failure, and unavailable required geometry checks stay unknown. The CLI smoke suite exercises the bounded original calibration and mascot examples; it is not a performance comparison with FreeCAD, Slicer, the upstream cat or general generative modeling.

Retain each request, runtime/source identity, outcome, raw metrics and evidence bundle. Record failures and time-limited attempts rather than dropping them from summaries. Do not compare runs with different geometry, quality settings, validation policy or hardware as if only speed changed.

## Measurement boundaries

- Keep application acquisition/setup, engine startup, generation/export, native reopen, independent validation and rendering distinguishable. If stages are combined by the adapter, label the combined scope instead of inventing separate values.
- Generation is deterministic reviewed code; assistant development, human iteration and optional model-provider usage are different costs.
- Wall time is measured for subprocess stages. CPU accounting covers waited-for child processes and depends on the operating system's descendant accounting.
- Per-run peak RSS is unavailable in the current wrapper; it is deliberately null because a cumulative child high-water mark cannot isolate one run. Do not report it as zero.
- Record actual enforced controls. Thread environment settings are not a hard CPU allocation, and native execution is not a sandbox.
- Preserve mesh sizes, triangle counts and validator work/time metrics where available. No metric should be inferred from file existence.

A smoke suite establishes a narrow functional result. To make a performance claim, run several independent repetitions under identical settings, retain raw samples, disclose cache state and shared-machine contention, and report median and range. Distinguish cold setup, cold process startup and warm caches explicitly. A single sample cannot support a speed or cost ranking.

The blocked Lane A runtime is a censored/unavailable route, not an unfavorable timing result. Native 4.3.2 examples do not measure equivalent behavior of the pinned 4.5.12 upstream implementation.

Review public benchmark reports for private paths and machine identifiers. Publish only intentionally selected coarse hardware summaries and authorized artifacts. No automatic upload is part of benchmarking.

## Run the suite

```sh
PYTHONPATH=src python -m printkit benchmark --suite smoke --output build/benchmark-001 --repetitions 3
```

The supported repetition range is 1–10, default 3. The output directory must be new. The suite writes incremental `raw.json` and a final `benchmark.json` with per-case median/range and pass counts. Summaries include censored/failing observations and are only comparable when all geometry checks pass. Each run retains its finalized evidence directory; ZIP creation is separate.
