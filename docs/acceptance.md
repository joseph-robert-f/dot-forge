# Release acceptance map

This source release is a **bounded native preview**. It is not completion of the proposed architecture MVP. A capability is accepted only with evidence for the exact source, runtime and request; a feature's implementation or a checked-in lock file alone is not execution evidence.

## Done: implemented preview scope

- Source-only Python 3.11+ CLI with no pip runtime dependencies and separate Blender runtime discovery.
- Two original bounded native generators: `calibration-block` and `geometric-mascot`, targeting Blender 4.3.2.
- Strict millimeter request contracts for one solid part, STL and editable BLEND output, native reopen and five exported-STL views.
- Independent exported-STL topology, dimension, volume, intersection and solid-shell validation with fail-closed unknowns and work budgets.
- Distinct geometry findings and unresolved printing/manual gates; no blanket print-ready claim.
- Retained runs, stage journals, source snapshots, hash-bound manifests, portable bundles and integrity verification.
- Reviewed-code native subprocess limits, with missing sandbox controls explicitly recorded.
- Source licenses, runtime/upstream inventories and public operational documentation.

[Release verification results](release-validation.md) record the tested examples, clean-source reinstall, resume and retrieved-bundle regeneration. These bullets describe implementation scope. Consult the actual test output and generated run reports for execution results on your environment. They do not certify every parameter combination or every negative fixture proposed by the architecture.

## Blocked: required architecture acceptance

- Pinned Lane A end-to-end regeneration: requires Blender 4.5.12 LTS. The available 4.3.2 runtime is incompatible and official exact-runtime retrieval returned HTTP 403. The adapter is present; exact-runtime acceptance is not complete.
- Architecture MVP acceptance as a whole: the Lane A gate above is still open. Successful native original examples cannot substitute for it.
- Any individual run whose required geometry check fails, crashes, is unavailable or exhausts its budget. Such evidence remains blocked, not geometry-validated.

## Deferred or not certified

- Measured wall thickness, tiny features and clearances; full orientation/support assessment; named slicer/toolpath checks and physical-print evidence.
- General modeling requests, assemblies, intentional hollow/nested-shell profiles and broader generator families.
- FreeCAD, experimental 3D Slicer and additional operating-system/runtime profiles.
- Adversarial untrusted-code execution with network/filesystem isolation and aggregate process-tree resource controls.
- Exhaustive coverage of every proposed architectural acceptance fixture, cross-platform reproducibility, signed releases and binary runtime redistribution.
- A fresh-machine test without relying on an existing installed runtime; downloadable runtime setup and broader benchmark claims.

## Before expanding this map

Retain a fresh source checkout, exact runtime identity, original request, raw test results, actual exported mesh, validation report, all views, manifest and verified bundle. Exercise failure cases as well as valid cases. Document residual uncertainty and any environment prerequisite. Never promote a skipped check, a missing metric or a pretty image into acceptance evidence.
