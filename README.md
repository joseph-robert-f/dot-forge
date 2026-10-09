# Dot Forge

![Dot Forge: a mounting plate built in FreeCAD, labelled with its measured size and holes, and a conforms status.](docs/media/hero.png)

**Describe a part to your Dot. Dot Forge turns the description into measurable checks, builds the part in FreeCAD, and measures the result against those checks.**

Your Dot runs the tools on its Linux cloud computer. You do not need to operate FreeCAD yourself. Each result is a **3D-printing candidate**: a model that still needs printing and physical checks. A conforming part is not approved for printing or for any use.

This repository contains source and instructions. It does not install applications.

[See it in action](#see-it-in-action) · [How it works](#how-it-works) · [Start with your Dot](#start-with-your-dot) · [Run the commands](#run-the-commands) · [Read the report](#read-the-report)

> **Status: preview.** The native tests pass on a Dot's FreeCAD 1.0.0 / Open CASCADE 7.8.1 profile (commit `09128ea`). Five-view previews and evidence bundles are not connected to this workflow yet.

## See it in action

![A recorded session: check the request and plan, build attempt 1 (blocked, two holes 2 mm off), change one number, build attempt 2 (conforms).](docs/media/demo.gif)

This is a real session, replayed. The commands, output, exit codes and times come from a recording with FreeCAD 1.0.0 ([session data](docs/media/src/session.js)). Output is trimmed with `jq`, and the replay shortens the build waits. See the [MP4 version](docs/media/demo.mp4).

![Two renders of the mounting plate. Attempt 1 has two holes at x 52 instead of x 54 and is blocked. Attempt 2 conforms.](docs/media/proof.png)

![Three parts built from open-ended requests: a mounting plate, a knob with grip notches, and a stepped block.](docs/media/gallery.png)

The model images are renders of exported STL files from real builds of the [examples](examples/v2). The hole rings, labels and counts come from each build's measurements. They are not photographs of printed parts.

## How it works

A request goes through three files. Each file has a strict schema.

| Step | File | Written by | Contents |
| --- | --- | --- | --- |
| 1. Intent | `intent.json` | Your Dot, then you confirm it | Your request as measurable checks, notes for a person, and unknowns |
| 2. Plan | `plan.json` | Your Dot | A FreeCAD feature tree, bound to the confirmed intent by hash |
| 3. Proof | `report.json` | Dot Forge | Each check with its measured result, plus the independent mesh checks |

**Intent.** Your Dot writes each stated size and feature as a check that can be measured:

- Envelope (overall size) and volume
- Holes on the x, y or z axis: diameter, position, through or blind, and depth
- Flat faces: direction, position and minimum area

A requirement that cannot be measured yet, for example "rounded corners", becomes a note for a person. A value that your request does not state goes in `unknowns`. Your Dot does not invent it. You confirm the intent before any geometry is made.

**Plan.** Your Dot writes the part as steps from a fixed set of 16 operations: box, cylinder, cone, sphere, extrude, revolve, union, intersect, cut, translate, rotate, mirror, linear and polar patterns, fillet and chamfer. The plan is data, not code. A fixed interpreter maps each operation to one FreeCAD function. If the intent changes, the old plan is refused.

**Proof.** `printkit build` runs the plan in FreeCAD and reopens the result in a fresh process. It measures the solid exactly, from its geometry, not from the mesh. Then it compares each measurement with the intent:

- A hole must have the correct axis, diameter and position. Full-aperture B-rep checks establish whether it is through or blind. Partial obstructions, including a counterbore shoulder, stay unknown.
- Each measured hole can satisfy only one check. A hole that nobody asked for goes to a person.
- A rounded corner is a partial cylinder. It is never counted as a hole.
- A missing or unreadable measurement is `unknown`, never a pass.

The build also exports STEP and STL files, checks that the STEP round trip keeps the same solid, and runs the independent STL checks.

A plan can be valid and still produce the wrong part. The [demo](#see-it-in-action) shows this: the plan placed two holes at x 52, the request said x 54, and the build was blocked.

## Start with your Dot

Give your Dot this repository URL and branch: <https://github.com/joseph-robert-f/dot-forge>, branch `dot-forge-v2`. Then copy this instruction:

> Use Dot Forge on your Linux cloud computer. Read README.md, AGENTS.md and docs/v2-intent-and-plan.md. Check that FreeCAD 1.0.0 is installed, and run the native tests. Do not download or install software without permission. Write my request as a draft intent. Put each value that I did not state in unknowns, and ask me about the unknowns that change the part. Show me the intent and wait for my confirmation. Then write a plan, build it in a new run directory, and show me the report. If a check fails, change the plan and build a new attempt. Keep the failed attempt. Show me the checks that remain for a person. Do not call the part print-ready.

Then describe your part, for example:

- "A 60 x 40 mm mounting plate, 5 mm thick, with four 4 mm screw holes 6 mm in from each corner."
- "A 30 mm round knob, 16 mm tall, with a 6 mm hole underneath for the shaft, about 8 mm deep."

Your Dot must tell you when a request needs something that Dot Forge cannot measure or build yet. See [limits](#limits).

## Prerequisites

- Linux x86_64 on the Dot cloud computer
- Python 3.11 or later for the command-line workflow
- FreeCAD 1.0.0 with Open CASCADE 7.8.1, run through its system Python 3.13.5
- A full source checkout with its schemas and examples

The Python workflow has no pip dependencies. FreeCAD is a separate installed application. If it is missing or a different version, `build` stops with exit code 3. It does not download anything. Follow [runtime setup](docs/runtime-setup.md), and do not weaken the runtime check.

## Run the commands

Run these from the repository root. Use a new output directory for each attempt.

### 1. Check the source and FreeCAD

```sh
export PYTHONPATH="$PWD/src"
python -m unittest discover -s tests
PRINTKIT_FREECAD_INTEGRATION=1 python3 -m unittest tests.test_v2_freecad_native -v
```

The first command runs the source tests. The second builds the examples and several fault cases in the installed FreeCAD. All native tests must pass. A skipped test is not a pass.

### 2. Check the intent and the plan

```sh
python -m printkit check-intent examples/v2/mounting-plate/intent.json
python -m printkit check-plan examples/v2/mounting-plate/plan.json --intent examples/v2/mounting-plate/intent.json
```

`check-intent` lists the measured checks, the checks for a person, and the unknowns. It also gives the `intent_sha256` value that the plan must carry.

### 3. Build and measure

```sh
python -m printkit build --intent examples/v2/mounting-plate/intent.json \
  --plan examples/v2/mounting-plate/plan.json --output build/plate-001
```

| Exit code | Meaning |
| --- | --- |
| 5 | The part conforms to the intent. Person and printing checks are still open. |
| 4 | Blocked: a check failed or was unknown, the mesh failed, or FreeCAD could not build a plan step |
| 3 | FreeCAD is unavailable, is a different version, or failed |
| 2 | The intent or plan is invalid, the intent is not confirmed, or the plan belongs to a different intent |

**Exit code 5 is the normal result for a good part.** Read `report.json` before you continue.

If a check fails, do not edit the run. Change the plan, or change the intent with the user, and build into a new directory. Keep the failed run.

## Read the report

Each run directory keeps its inputs, outputs and evidence:

| Output | Purpose |
| --- | --- |
| `intent.json`, `plan.json` | The confirmed intent and the plan that was built |
| `native/model.FCStd` | Editable FreeCAD model |
| `exports/model.step`, `exports/model.stl` | Solid exchange file and printing mesh |
| `native/measure.json` | Exact measurements of the exported solid |
| `native/generation.json`, `native/reopen.json` | Build record and the fresh-process round-trip check |
| `native/plan-failure.json` | Only on failure: the step and the FreeCAD error |
| `logs/` | FreeCAD output for each stage |
| `report.json` | The result |

`report.json` keeps four answers separate:

- `intent_state`: `conforms` or `blocked`. Is it the part that was asked for?
- `geometry_state`: the independent STL checks. Is the exported mesh sound?
- `print_state`: always `needs_review`. Dot Forge does not decide print readiness.
- `person_checks`: what a person must still do, for example notes from the intent, the five views, print settings and a test print.

To see each check:

```sh
jq -r '.conformance.checks[] | "\(.status)\t\(.code)"' build/plate-001/report.json
```

To check a measurement against an intent again, run `python -m printkit conform --intent intent.json --measurement build/plate-001/native/measure.json`.

## Limits

- One solid only. Assemblies and hollow or nested shells are not supported.
- Measured today: envelope, volume, holes on the x, y or z axis, and flat faces on those axes. Fillet radius, wall thickness, angled holes, threads and text are notes for a person. They are never a pass.
- A confirmed intent is a process record, not a signature. The tool cannot prove that you saw it.
- Five-view previews and evidence ZIP bundles are not connected to this workflow yet. Compare the part with your request yourself before you use it.
- Printer and material settings, clearances, orientation, supports, slicing and a physical test remain open.

## More instructions

- [Intent, plan, proof](docs/v2-intent-and-plan.md): the full procedure and every field
- [Intent schema](schemas/intent.v1.json) and [plan schema](schemas/plan.v1.json)
- [CLI reference](docs/cli.md): all commands and exit codes
- [Contributing](CONTRIBUTING.md): checks and requirements for changes
- The earlier fixed-generator workflow is still available. See the [quickstart](docs/quickstart.md).

## Security, sharing, and license

The plan is interpreted by fixed code, and plan values are never run as code. FreeCAD still runs without network or filesystem isolation. Native subprocess limits are not a security sandbox. Read [SECURITY.md](SECURITY.md) before use.

Keep generated models, private requests and run directories outside Git. Publishing or uploading a design requires a separate, explicit decision. Follow the [publishing guidance](docs/publishing.md).

The source uses GPL-3.0-or-later; see [LICENSE](LICENSE). [Third-party notices](THIRD_PARTY_NOTICES.md) identify external source and runtime boundaries. No application binaries are distributed.

The images are regenerated from real builds with `docs/media/render-models.mjs` and `docs/media/render-media.mjs`. See the comments at the top of each script.
