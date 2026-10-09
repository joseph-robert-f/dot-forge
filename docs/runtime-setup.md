# Runtime setup

## Default dot-native profile

The default `dot-native` profile targets the applications already installed on the dot's Linux x86_64 cloud computer. It includes all three bounded generators: `calibration-block` and `geometric-mascot` use Blender **4.3.2** with Workbench previews; `freecad-stepped-block` uses FreeCAD **1.0.0** / Open CASCADE **7.8.1**, with the same Blender for STL views. Python **3.11 or newer** runs the orchestration CLI; the observed CLI interpreter is **3.12.14**, and FreeCAD uses system Python **3.13.5**. The native Blender and FreeCAD profiles both require their observed Python **3.13.5**; the orchestration interpreter is separate. Native Python drift fails closed until a new profile is reviewed.

Use the already installed, reviewed runtime when available. Select a Blender executable with `PRINTKIT_BLENDER` if it is not on PATH. Read `runtime-lock.json` for version and provenance. An observed executable hash identifies the tested file; it is not a vendor archive verification or a claim that another installation is equivalent.

Run `python -m printkit doctor --json --all-smoke NEW_DIRECTORY` on every new environment to test all three default families. For selected-family work, run the selected backend's fresh smoke as well as capability discovery. Discovery without a real generation/export/reopen/validation/render test remains unverified. No runtime is downloaded as a side effect of a model command. Obtain missing software only through an approved official distribution route, respecting platform permissions.

The implementation uses Unix process groups and resource limits. Other operating systems and architectures are untested; this source-only release is not a portable runtime installer.

## Optional pinned upstream Lane A

`upstream.lock.json` pins the builder repository to commit `f31eef7f87ec8573a106c2f6dbd6f76a49da94ae` and selected source hashes. The adapter invokes its CLI. It does not silently replace the builder implementation or patch its runtime guard.

Lane A requires **Blender 4.5.12 LTS**. Installed Blender 4.3.2 does not satisfy this requirement. Official runtime retrieval returned **HTTP 403** in the release environment. The optional migration is therefore blocked; it is not a prerequisite for the default `dot-native` profile. The original architecture contract remains incomplete and unchanged. Do not bypass access restrictions, substitute Boolean solvers, remove version checks or cite successful original native examples as Lane A acceptance.

On an environment where the exact official runtime can legitimately be obtained, verify the archive checksum from the reviewed runtime lock and import the separately reviewed upstream source with `python scripts/fetch-upstream.py --source /path/to/reviewed-checkout`, or explicitly fetch the pin with `python scripts/fetch-upstream.py --git`. The default selected source lives under ignored `vendor/upstream`; point `PRINTKIT_UPSTREAM` only at an equivalent verified selected tree, not a full checkout. Then run fresh runtime and adapter acceptance tests. The source pin is necessary but is not itself runtime acceptance.

## Deferred options

A Docker route exists in the upstream project, but this starter has not accepted it as a fallback runtime. Do not assume Docker or nested containers are available. A Slicer installation under `/opt/slicer/5.10.0` may appear in observational inventory; this scan could not start it normally or with `QT_QPA_PLATFORM=offscreen` because the required Qt display/plugin was unavailable, but its integration is experimental/deferred: it is neither a required default runtime nor an accepted generator or toolpath check. Optional tool discovery does not execute a model workflow or imply acceptance. Additional operating-system profiles are outside the current Linux-focused scope. No applications or container images are redistributed here.

## FreeCAD native profile

The curated stepped-part workflow uses installed FreeCAD 1.0.0 / Open CASCADE 7.8.1 modules through Linux system Python, not a GUI session. The tested distro paths are `/usr/bin/python3` and `/usr/lib/freecad/lib`; doctor runs native probes, checks the required versions and capabilities, and records observed executable and library hashes. It does not authenticate installed binaries against the hashes in `runtime-lock.json` before execution. This is a specific Linux profile, not a generic runtime installer. The installed `freecadcmd` launcher was unreliable in the test environment; it is neither invoked nor represented as the tested execution path.

Generation, fresh FCStd reopening and STEP reimport use isolated Python invocation with a sanitized environment and existing execution budgets. Actual printing STL is independently validated, and Blender 4.3.2 supplies the same five views. Source distribution contains no FreeCAD binaries. On another dot’s computer, unavailable or incompatible tools remain blocked until supported setup is authorized.
