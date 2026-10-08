# Native preview verification: 2026-10-08

This evidence supports sharing the **bounded native preview**. It does not complete the original architecture MVP: the pinned Lane A runtime gate remains blocked, and no physical-print claim is made.

## Evidence scope and current default

The historical results and source hashes below remain evidence for the exact implementation tested; they are not silently reassigned to later changes. The default `dot-native` profile now groups the two Blender families with the independently verified [FreeCAD stepped-part workflow](freecad-verification.md). Its observed installed stack is Blender 4.3.2, FreeCAD 1.0.0 / Open CASCADE 7.8.1, orchestration Python 3.12.14 and FreeCAD system Python 3.13.5. A Slicer 5.10.0 installation directory was found, but current startup/version probing failed without a usable Qt display/plugin; it remains optional observational inventory only.

On each dot, use `doctor --json --all-smoke NEW_DIRECTORY` for fresh execution evidence across all three default generators. Merely adding the profile or listing installed tools does not establish acceptance. Lane A remains an optional blocked integration with the exact Blender 4.5.12 LTS requirement; it does not gate default-profile acceptance, and its historical architecture obligation is still incomplete. No runtime upgrades, solver changes or new print-readiness claims follow from this alignment.

## Runtime-alignment verification: 2026-10-08

The alignment changes were tested against package Python-source identity `9c30024908697f900dd2a4ef6756029ce27f0dc380928ac8cae2187a26734a67`. No model construction, Boolean solver, validation tolerance or supported generator parameters changed.

- Source-only suite: **194 tests passed, 7 native opt-in tests skipped**.
- Actual installed-runtime suite: **194 tests passed, no skips**, in 260.9 seconds, using `PRINTKIT_INTEGRATION=1 PRINTKIT_FREECAD_INTEGRATION=1 PRINTKIT_DOT_INTEGRATION=1 python3 scripts/check-release`.
- All three default generators completed generation, native reopen, exported-STL validation, five-view rendering and hash-verified bundles. Each copied bundle was verified and extracted; each family regenerated using its embedded source with `python -S -B` and `PYTHONPATH`, without pip packages or downloaded/upgraded native applications.
- The real FreeCAD negative fixtures still reject displaced, wrong-radius, blind, tilted and elliptical holes in FCStd and STEP independently. Source-snapshot no-link and bundle-integrity regressions remain passing.
- New fail-closed tests cover wrong native versions, Python versions, platform, missing STL operators/Workbench, failed probes, partial smoke failures, and runtime changes during stage reuse.
- Fifteen actual views were inspected across the bundled block, flat mascot and stepped through-hole examples. They show the expected bounded features. This is technical visual review, not user design approval or printing acceptance.
- Current native discovery confirms Blender 4.3.2 / Python 3.13.5 / Workbench / registered STL operators; FreeCAD 1.0.0 / Open CASCADE 7.8.1 / Python 3.13.5. Blender reports FAST and EXACT Boolean solvers, with no MANIFOLD; the native examples do not use Boolean solvers.
- The full local test-log SHA-256 is `61e77f81e9e85c3cb6f7b5fc27cce27698f9813e7f37cf5feb9a85219fd8e6b6`. This records a local run; automated GitHub source CI is separate from manual native-runner acceptance.

The checks above use already installed applications on this dot’s Linux computer. They do not certify every dot image, untested parameter combinations, Lane A, slicer/toolpath suitability or physical prints. Optional Slicer remains unverified in the current runtime scan.

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

## Deliverable-only bundle hardening

A follow-up packaging change limits ZIPs to the explicit source/native/export/preview/log/QA and named-report boundary. Generated Mesa/Blender caches and unrelated process-HOME files remain in the private attempt directory and are not read into the archive. Extra non-deliverable ZIP members are rejected. Installed package bookkeeping is excluded from source snapshots.

- Updated Python implementation hash: `7ef1cc82c5e80e9a52120915eafc56b8a4a6b2dbc8cce709a72344e5b3226755`.
- Full source and actual Blender integration suite: **100 tests passed, no skips**.
- Independent bundle-scope review added four passing adversarial regressions, including a large excluded cache whose bytes must never be opened.
- A fresh mascot run, five-view render and cache-free 85-artifact ZIP passed independent re-verification; runtime cache files remained untouched outside the ZIP.
- Geometry generation is unchanged; the mascot STL retains the hash listed above.

The earlier timing sample describes the original preview implementation. No new performance or cold-install claim is inferred from this packaging fix. Older bundles listing runtime caches are rejected by the stricter reader; regenerate into a new attempt rather than rewriting successful historical evidence.
