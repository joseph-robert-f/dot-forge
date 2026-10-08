# Quickstart

This is the default `dot-native` Linux profile for three bounded generators: Blender calibration block and flat robot mascot, plus the FreeCAD stepped block with a through-hole. It uses installed applications, without downloads or upgrades. Optional Lane A is separate and blocked; it is not required for this default workflow. Read [runtime setup](runtime-setup.md) before considering any setup change.

## 1. Use a reviewed source checkout

From the repository root, use Python 3.11+ without installing pip runtime dependencies:

```sh
export PYTHONPATH="$PWD/src"
python --version
python -m printkit --help
python -m printkit doctor --help
```

The same commands are available as `printkit` after an editable installation that retains this full reviewed source checkout. A standalone wheel is not a supported distribution: workflows need the checkout’s schemas, examples, locks and snapshot inputs. The default `PYTHONPATH` route avoids pip, build-tool installation and downloads.

Use the already installed Blender 4.3.2 and FreeCAD 1.0.0 / Open CASCADE 7.8.1 native modules. If necessary, set `PRINTKIT_BLENDER` to its reviewed executable path. FreeCAD uses system Python; see [runtime setup](runtime-setup.md). Do not download or upgrade a runtime silently or change a runtime guard.

## 2. Check source and capability

```sh
python -m unittest discover -s tests -v
python -m printkit doctor --json
python -m printkit doctor --json --all-smoke build/dot-native-smoke-001
python -m printkit check-request examples/calibration-part/request.json
```

`calibration-part` is the example directory; its generator ID is `calibration-block`. The explicit `--all-smoke` command executes all three default generators into a new parent directory, including native reopening, exported-STL validation and five-view rendering. Inspect each result; a failed required default family is not a pass. Doctor success requires all three native geometry/render workflows to pass; it leaves manual/printing checks unknown. Discovery without smoke remains unverified. Optional Lane A incompatibility and observational optional-tool inventory do not block the default profile. For a selected Blender calibration smoke only, use `doctor --json --smoke NEW_RUN`; use `doctor --backend freecad --json --smoke NEW_RUN` for the stepped part.

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
