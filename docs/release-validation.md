# Native preview verification: 2026-10-08

This evidence supports sharing the **bounded native preview**. It does not complete the original architecture MVP: the pinned Lane A runtime gate remains blocked, and no physical-print claim is made.

## Tested implementation and environment

- Python implementation SHA-256: `eb3e0ec45ed01609c0026db82617da9f17c334db7119ed816c4c8b057fc89394` (the CLI's canonical hash over all package Python source files).
- Linux x86_64; Blender 4.3.2 with bundled Python 3.13.5; CLI Python 3.12.
- Exact observed executable hash and its provenance limitation are recorded in `runtime-lock.json`.
- Blender was preinstalled. A clean runtime download/install was **not** tested.

## Acceptance results

- Full source suite with actual Blender integration enabled: **87 tests passed, no skips**.
- Independent clean source copy, new virtual environment and editable reinstall: **87 tests run, one opt-in runtime test skipped**; actual native journeys were then executed separately.
- Calibration: 20 × 20 × 10 mm, one closed solid, 12 triangles.
- Original flat extruded robot mascot: 40 × 12 × 60 mm, one closed solid, 76 triangles.
- Both passed generation, fresh-process BLEND/STL reopen, independent exported-mesh validation and all five views. Ten actual rendered images were inspected for the documented basic forms; visual/design approval remains a manual gate.
- Generate-only interruption followed by resume, completed-run inspection, ZIP creation, copied-ZIP verification and source regeneration from the retrieved ZIP passed.
- The calibration STL regenerated from embedded source had the same hash: `0f96d1f7fd870a95a2a680fb417a149a7d3beb645ef4bc17092cfd80d1d104f0`.
- Mascot STL hash: `ff0269168165cd2dd0d2e27d5ade48775257cdbb55ccf888a01e55d914f1e60c`.
- Width-boundary examples at 5 and 100 mm passed for both original generators. This is representative boundary evidence, not exhaustive parameter-space certification.

Independent adversarial reviews added regressions for pathological duplicate-face memory use, deadline exhaustion, exact-volume underflow, source-shadowing, request/implementation drift, empty stage records, changed validated bytes, envelope failure, symlink handling and huge numeric inputs. Required failures and unknowns cannot become geometry passes. The validator has both cooperative algorithm budgets and a separate hard process deadline.

## Measured smoke benchmark

Three repetitions per original case, six successful geometry runs:

- Calibration full pipeline: median **17.70 s**, range **16.80–20.33 s**.
- Mascot full pipeline: median **18.51 s**, range **18.05–20.65 s**.

[Raw observations and stage metrics](../benchmarks/results/native-preview-2026-10-08.json) include failures if present; none occurred in this run. Each stage launched a fresh engine process. The benchmark began before the initial local source commit was created and finished after it; package source remained unchanged and had the implementation hash above. It is not a cold-runtime-install benchmark. OS caches and contention on shared hardware were uncontrolled. Setup/download, development and human iteration time, provider usage, and per-run peak RSS are unavailable, not zero. Do not extrapolate these numbers to another runtime or claim a total-cost advantage.

## Still blocked or unresolved

Blender 4.5.12 Lane A end-to-end acceptance, exact prior detailed-cat reproduction, full architecture MVP acceptance, measured walls/clearances, slicer/toolpath assessment and physical testing remain outstanding. See [acceptance map](acceptance.md). Source CI checks the committed Python matrix separately; inspect the actual GitHub checks for the commit you use.
