# FreeCAD workflow verification: 2026-10-08

This extends the Linux dot-computer starter with one reviewed dimensioned-solid family. It does not establish arbitrary text-to-CAD capability, resolve Lane A, or certify printing.

## Tested shape and native tools

- `freecad-stepped-block`: 30 × 24 × 18 mm example, half-height base, right-half raised step and a through-hole in the lower left ledge.
- Native FreeCAD 1.0.0 / Open CASCADE 7.8.1 through system Python 3.13.5; Blender 4.3.2 Workbench for exact-STL previews.
- FCStd and STEP each reopened as one valid closed BRep solid, with volume **9322.39218 mm³** and matching bounds/features.
- Printing STL: **228 triangles**, one connected closed manifold shell; dimensions, orientation, intersection, analytic-volume, feature-probe and cross-section gates passed.
- STL SHA-256: `817ea3118caf36cb5551a50356cba014b62d204eaae5e56968063ea3c678637a`.

`runtime-lock.json` records observed native identities and their limited hash scope. Native applications were preinstalled; no clean runtime download/install or transitive binary redistribution was tested.

## Independent workflow evidence

A fresh source-only copy with no existing models passed request checking, FreeCAD doctor smoke, generation, pause/resume, inspection, bundle creation and copied-ZIP verification. All five rendered images were inspected; the oblique camera exposes both the step and hole.

Source extracted from that verified ZIP regenerated a byte-identical STL and identical preview pixels. Native BRep data also matched; FCStd timestamps/UUID/object identity, STEP timestamps and PNG metadata can differ. Byte-identical native containers are not required for geometric reproducibility.

The final native document also records the original example's GPL-3.0-or-later license, instead of FreeCAD's default “All rights reserved” metadata. Fresh reopening verifies this metadata. Its dimension properties describe generator inputs; they are not a live feature-history tree.

## Adversarial and regression checks

The full source suite with both native integrations enabled passed **138 tests with no skips** on the final implementation. It covers five FreeCAD golden/extreme shapes, corrupt FCStd/STEP, missing holes despite watertight same-bounds solids, incorrect backend/export contracts, runtime drift, incomplete native artifacts and blocked diagnostic persistence, alongside the existing Blender/mesh/bundle cases.

Independent review found and fixed missing preview-runtime binding. A 0.32 mm displaced-hole counterfeit initially passed sparse occupancy probes; two required rational cross-section checks now reject it. Tests cover a 0.049/0.051 mm center-tolerance boundary, wrong radius, extra holes and unresolved/open sections. Tolerances reflect this generator's tessellation: they do not certify arbitrary geometry, minimum walls or physical fit.

## Source identity and timing

- Geometry and fresh-source journey implementation hash: `d0a15b7e464bb73be12768560bca1cc98d291e13401ebee460efc891bd6cbd9a`.
- Final implementation, additionally aligning native license metadata: `5cf8433c286beccca5d92773e586fa4ac1595074a1bd31469425869c405017cb`.

[Raw three-repetition benchmark](../benchmarks/results/freecad-stepped-2026-10-08.json): all three geometry runs passed; full-pipeline median **19.85 s**, range **17.94–22.62 s**. This includes native-process startup, export, independent validation and five-view rendering. It used the geometry/journey implementation above; the later metadata-only license change is not included in that timing sample.

Shared-hardware contention and OS caches were uncontrolled. Setup/download, development and human-review time, provider usage and per-run peak RSS remain unavailable, not zero. These are not cross-backend speed/cost comparisons: the Blender examples have different geometry and work.

## Remaining gates

FreeCAD success does not resolve Blender 4.5.12 Lane A acceptance, the exact detailed-cat model, general wall/clearance assessment, slicing/toolpaths or physical-print success. Each successful example still exits with manual review required. Source CI is separate from native runtime evidence; check the actual workflow status for the exact commit used.
