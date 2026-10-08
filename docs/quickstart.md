# Quickstart

This is a Linux native preview for the two original bounded generators. It is not the blocked Lane A migration or a general text-to-3D engine. Read [runtime setup](runtime-setup.md) before installing anything.

## 1. Use a reviewed source checkout

From the repository root, use Python 3.11+ without installing pip runtime dependencies:

```sh
export PYTHONPATH="$PWD/src"
python --version
python -m printkit --help
python -m printkit doctor --help
```

The same commands are available as `printkit` when the project entry point is installed. A package installation needs build tooling; the `PYTHONPATH` route avoids a package installation for this checkout.

Use an already installed Blender 4.3.2 executable. If necessary, set `PRINTKIT_BLENDER` to its reviewed executable path. Do not download another runtime silently or change the runtime guard.

## 2. Check source and capability

```sh
python -m unittest discover -s tests -v
python -m printkit doctor --json
python -m printkit doctor --json --smoke build/doctor-smoke-001
python -m printkit check-request examples/calibration-part/request.json
```

`calibration-part` is the example directory; its generator ID is `calibration-block`. The explicit `--smoke` command generates, reopens, validates and renders a fresh calibration run. Discovery without that option remains unverified. Inspect its outputs to establish actual capability. A Lane A incompatibility message is expected on the 4.3.2 profile.

## 3. Create a fresh example attempt

```sh
python -m printkit run --request examples/calibration-part/request.json --output build/calibration-001
python -m printkit inspect --run build/calibration-001
```

Exit **5** is expected for a geometry-valid candidate that still needs manual/printing review. It is not an internal failure. Read the JSON report even if the command exits nonzero: manual-review-required and blocked states are intentionally distinct from an internal error. Do not reuse an existing output directory for a different request.

Open `previews/contact-sheet.html` for the labeled five-view review. Inspect `exports/model.stl`, `native/model.blend`, `validation.json` and the five images under `previews/`. Compare dimensions and requested features. A `geometry_validated` state still leaves printing/manual checks unresolved.

Repeat with `examples/geometric-mascot/request.json` and a new output directory. Modify only the supported finite parameters and matching requested dimensions, then run `check-request` again. The request contract allows exactly one solid part and explicitly records unknown printer information as null.

## 4. Preserve the result

`run` finalizes the evidence directory but does not automatically create a ZIP. Bundle it separately:

```sh
python -m printkit bundle --run build/calibration-001 --output build/calibration-001.zip
python -m printkit verify-bundle build/calibration-001.zip
```

Create the ZIP outside the run directory using a new filename; verify it after copying or downloading. Inspect the contents for private information before sharing them. A finalized evidence set may contain a blocked model; bundle completion is not print approval.

For individual stages and recovery:

```sh
python -m printkit generate --help
python -m printkit validate --help
python -m printkit render --help
python -m printkit bundle --help
python -m printkit verify-bundle --help
python -m printkit resume --help
python -m printkit benchmark --help
```

See [recovery](recovery.md), [validation explained](validation-explained.md) and [acceptance status](acceptance.md) before interpreting or publishing the evidence.

See [CLI reference](cli.md) for flags and exit codes.

## Dimensioned FreeCAD workflow

For the reviewed stepped block with a through-hole, use the separate [FreeCAD workflow](freecad-workflow.md). On the dot’s Linux computer, first check actual capabilities:

```sh
python -m printkit doctor --backend freecad --json
python -m printkit doctor --backend freecad --json --smoke build/freecad-smoke-001
python -m printkit check-request examples/freecad-stepped-part/request.json
python -m printkit run --request examples/freecad-stepped-part/request.json --output build/freecad-001
```

The full workflow requires the documented FreeCAD native profile and Blender preview runtime. It supplies editable FCStd, STEP exchange and STL, with native/STEP round-trip checks and independent exported-mesh feature/volume gates. Exit 5 still means manual/printing review remains. Capability on one dot’s computer does not establish availability on another; no application is downloaded during these commands.
