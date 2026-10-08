# Runtime setup

## Native preview profile

The bounded original `calibration-block` and `geometric-mascot` generators target Blender **4.3.2**, Linux x86_64, with Workbench previews. Python **3.11 or newer** runs the orchestration CLI. Blender's own Python runtime is separate.

Use the already installed, reviewed runtime when available. Select a Blender executable with `PRINTKIT_BLENDER` if it is not on PATH. Read `runtime-lock.json` for version and provenance. An observed executable hash identifies the tested file; it is not a vendor archive verification or a claim that another installation is equivalent.

Run the doctor and a fresh bundled example on every new environment. Discovery without a real generation/export/reopen/render test remains unverified. No runtime is downloaded as a side effect of a model command. Obtain missing software only through an approved official distribution route, respecting platform permissions.

The implementation uses Unix process groups and resource limits. Other operating systems and architectures are untested; this source-only release is not a portable runtime installer.

## Pinned upstream Lane A

`upstream.lock.json` pins the builder repository to commit `f31eef7f87ec8573a106c2f6dbd6f76a49da94ae` and selected source hashes. The adapter invokes its CLI. It does not silently replace the builder implementation or patch its runtime guard.

Lane A requires **Blender 4.5.12 LTS**. Installed Blender 4.3.2 does not satisfy this requirement. Official runtime retrieval returned **HTTP 403** in the release environment. The migration is therefore blocked. Do not bypass access restrictions, substitute Boolean solvers, remove version checks or cite successful original native examples as Lane A acceptance.

On an environment where the exact official runtime can legitimately be obtained, verify the archive checksum from the reviewed runtime lock and import the separately reviewed upstream source with `python scripts/fetch-upstream.py --source /path/to/reviewed-checkout`, or explicitly fetch the pin with `python scripts/fetch-upstream.py --git`. The default selected source lives under ignored `vendor/upstream`; point `PRINTKIT_UPSTREAM` only at an equivalent verified selected tree, not a full checkout. Then run fresh runtime and adapter acceptance tests. The source pin is necessary but is not itself runtime acceptance.

## Deferred options

A Docker route exists in the upstream project, but this starter has not accepted it as a fallback runtime. Do not assume Docker or nested containers are available. FreeCAD, 3D Slicer and additional platform profiles remain deferred integrations. No applications or container images are redistributed here.
