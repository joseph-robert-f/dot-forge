# Changelog

## Unreleased: v2 preview

- Add the v2 intent spec (`schemas/intent.v1.json`). It records the user's ask as measurable checks, notes for a person, and unknowns. A build needs a confirmed intent.
- Add the v2 build plan (`schemas/plan.v1.json`). It is a declarative FreeCAD feature tree with 16 operations, bound to one intent by hash.
- Add `printkit check-intent`, `check-plan`, `build` and `conform`.
- Add a fixed FreeCAD plan interpreter and B-rep measurer. Its native tests pass on a Dot's exact FreeCAD 1.0.0 / OCC 7.8.1 profile (last run at commit `09128ea`, including the knob example).
- The STEP round trip compares counts, sizes and every cylinder, and allows 1e-4 relative error on integrated volume and area. The 1e-8 limit from v1 rejected a correct revolved part. OCC integration error on B-spline-trimmed faces is about 1e-5.
- Add a third example: a knob with a blind shaft hole and grip notches.
- A plan step that FreeCAD cannot build exits 4 with `plan_step_failed`. The report names the step and the FreeCAD error.
- Add conformance checks for envelope, volume, axis-aligned holes (through or blind) and flat faces. Unrequested holes go to a person.
- Add two examples: the stepped block written as a plan, and an open-ended mounting plate.
- Add a field test (`evals/v2`) with thirteen new requests and eleven wrong plans. It found five measurer faults:
  - Envelopes and positions use the exact bounding box. The plain box included trim tolerance and failed the STEP round trip of a side hole.
  - Hole spans use the exact face extent, not the trim-curve parameter range.
  - A cylinder is a void when its face normal points toward its axis. Before, the outer wall of a tube was reported as a hole.
  - A blind counterbore over a clearance hole read as through. The full-aperture end checks now make that end unknown.
  - `native_solid` requires one shell for each solid, so a sealed cavity blocks. The STEP round trip compares shell counts.
- A hole can name what each end opens into: `{"ends": {"min": ..., "max": ...}}` with `outside`, `floor`, `void` or `shoulder`. This expresses counterbores, set-screw holes into a bore and drain holes into a cavity. Each end must be proven over the full aperture, or it is unknown. `"through"` and blind depths do not change. The field test's spacer, collar and drained ball now conform, and their wrong plans are caught.
- `planar_face` takes an optional `max_area_mm2`. It must not be less than `min_area_mm2`. The field test's overlong slot is now caught.
- Add the `partial_hole` intent feature for channels, slot ends and D-bores: axis, diameter, position, an arc range in degrees and an optional length. The measurer takes the arc from an exact section at mid-length. The field test's cable channel, slot ends and D-bore are now measured, and three more wrong plans are caught.
- Add `printkit printability` for any STL, such as a character or a figure. It reports a closed mesh, loose parts, bed size, flat base, stability, overhangs and sampled thin parts. It never judges likeness and never claims print readiness. See `docs/printability.md`.
- The README leads with functional parts. The publishing guide covers characters and designs that belong to someone else.
- Add `printkit preview`: a draft build with five exact line views (front, right, back, top, iso) from FreeCAD's hidden-line projection, measured overall sizes, labelled holes, and a plain summary of what will be measured, judged and not assumed. PNG through FreeCAD's Qt when present, SVG otherwise. Never a deliverable.
- `build --approved-preview` binds the build to the preview the user approved. It refuses a different intent or plan or changed preview files, and records whether the final solid matches the preview.
- v1 requests, generators and checks do not change. A report with `overall_state: blocked` now always exits 4.

## 1.02

Release display name: **1.02**. The package version is **1.0.2**, and the Git tag is **v1.0.2**. This is a regular release, ready for the three supported Linux workflows. The existing 1.01 pre-release remains available.

This release updates version and release-status metadata only. It does not change model generators, geometry checks, native runtime requirements, dependencies or supported parameters. Use a new attempt after a source-version change; do not reuse evidence from a different source identity.

The supported scope remains a source-only workflow for a dot's Linux x86_64 cloud computer: a Blender calibration block, a flat extruded mascot and a FreeCAD stepped solid with a through-hole. Every dot must check its installed tools and run fresh smoke acceptance. Applications are not installed or distributed.

Regular-release status does not certify a physical print. Printer/material suitability, wall thickness, clearances, orientation, supports, slicing, user design approval and physical-print testing remain separate. Optional Lane A and Slicer retain their documented limits. See [acceptance](docs/acceptance.md).

## 1.01

Release display name: **1.01**. The corresponding semantic package version is **1.0.1**, and the Git tag is **v1.0.1**. This naming choice preserves the requested release label while keeping the existing three-part package version format.

This is a source-only preview for a dot's Linux x86_64 cloud computer. It supports three bounded model families: a Blender calibration block, a flat extruded mascot, and a FreeCAD stepped block with a through-hole. It does not install or distribute native applications.

### Changes

- Align the default workflow with the observed Blender 4.3.2 / native Python 3.13.5 and FreeCAD 1.0.0 / Open CASCADE 7.8.1 / system Python 3.13.5 profiles. Orchestration uses Python 3.11 or newer and no pip runtime dependencies.
- Add actual native capability probes, all-family smoke checks, verified bundles and restored-source regeneration tests.
- Correct the source-only test count: 194 tests ran, with 187 passes and 7 intentional native-test skips. The separate installed-runtime suite ran all 194 tests without skips.
- Clarify that doctor executes native probes and records observed hashes. It does not authenticate the installed binaries against the runtime lock before executing them.

### Scope and remaining checks

Native generation, reopening, STEP round trips where applicable, exported-STL geometry checks, five-view rendering, and bundle integrity have bounded test coverage. Each computer must run its own capability and smoke checks. The observed environment is not a promise about every dot image.

Lane A remains an optional blocked integration with its original Blender 4.5.12 requirement. Slicer is optional experimental inventory. Printer/material suitability, wall and clearance assessment, supports, slicing, user design approval and physical-print testing are not certified by this release. See [acceptance](docs/acceptance.md) and [verification evidence](docs/release-validation.md).
