# Release acceptance map

This source release supplies **bounded native modeling instructions for a dot's Linux cloud computer**. It is not completion of the proposed architecture MVP, a cross-platform application or a runtime installer. A capability is accepted only with evidence for the exact source, runtime and request; adapter code and a checked-in lock file alone are not execution evidence.

## Existing bounded Blender preview

- Source-only Python 3.11+ CLI with no pip runtime dependencies; native applications are separate prerequisites.
- Two original bounded generators: `calibration-block` and flat extruded robot `geometric-mascot`, targeting Linux x86_64 / Blender 4.3.2.
- Strict millimeter requests for one solid part, STL and editable BLEND output, native reopen and five exported-STL views.
- Independent exported-STL topology, dimension, volume, intersection and solid-shell validation with fail-closed unknowns and work budgets.
- Distinct geometry findings and unresolved printing/manual gates; no blanket print-ready claim.
- Retained runs, stage journals, source snapshots, hash-bound manifests, portable bundles and integrity verification.
- Reviewed-code native subprocess limits, with missing sandbox controls explicitly recorded.
- Source licenses, runtime/upstream inventories and public operational documentation.

[Release verification results](release-validation.md) record the existing tested examples, clean-source reinstall, resume and retrieved-bundle regeneration. These bullets describe bounded scope; the actual reports establish individual execution results. They do not certify every parameter combination or every negative fixture proposed by the architecture. Run fresh smoke acceptance on another dot's Linux computer before relying on it.

## FreeCAD integration: bounded workflow verified

The new route targets Linux x86_64, native FreeCAD 1.0.0 / Open CASCADE 7.8.1, and Blender 4.3.2 for exported-STL views. Its sole family is `freecad-stepped-block`, with width/depth/height each 5–100 mm, a half-height base, raised half-width step and vertical through-hole. Expected deliverables are FCStd, STEP, STL and five mesh views.

Fresh FCStd BRep reopening, STEP solid round-trip checks, independent STL topology/intersections/dimensions, analytic volume, required-feature probes and measured hole cross-sections passed. Actual five-view review, interrupted-stage recovery, copied-bundle verification and regeneration from embedded source also passed. See [FreeCAD verification](freecad-verification.md) and the [workflow](freecad-workflow.md); these results cover the named Linux runtime and bounded family, not every environment or physical use.

Even a successful FreeCAD geometry run leaves printer/process/material, wall/clearance suitability, slicing, visual approval and physical-print checks separate. Native-solid validity does not certify the tessellated mesh or real-world use.

## Blocked: required architecture acceptance

- Pinned Lane A end-to-end regeneration requires Blender 4.5.12 LTS. Blender 4.3.2 is incompatible and official exact-runtime retrieval returned HTTP 403. The adapter is present; exact-runtime acceptance is not complete.
- Architecture MVP acceptance as a whole: the Lane A gate remains open. Successful original Blender or FreeCAD examples cannot substitute for it.
- Any run whose required geometry check fails, crashes, is unavailable or exhausts its budget. Such evidence is blocked, not geometry-validated.

## Deferred or not certified

- General measured wall thickness, tiny-feature and clearance assessment; full orientation/support assessment; named slicer/toolpath checks and physical-print evidence. Bounded feature probes are not substitutes for these checks.
- General modeling requests, assemblies, intentional hollow/nested-shell profiles and broader generator families.
- Experimental 3D Slicer and additional runtime/operating-system profiles. Cross-platform installers and desktop-app packaging are outside this Linux instruction set.
- Adversarial untrusted-code execution with network/filesystem isolation and aggregate process-tree resource controls.
- Exhaustive coverage of every proposed architectural fixture, signed releases and binary runtime redistribution.
- A fresh-machine test without relying on existing native installations; downloadable runtime setup and broader benchmark claims.

## Before expanding this map

Retain a fresh source checkout, exact native-runtime identity, original request, raw test results, actual exported mesh, native/STEP evidence where applicable, validation report, all views, manifest and verified retrieved bundle. Exercise failure cases as well as valid cases. Document remaining uncertainty and environment prerequisites. Never promote a skipped check, missing metric, executable discovery or attractive image into acceptance evidence.
