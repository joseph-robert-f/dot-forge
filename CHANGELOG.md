# Changelog

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
