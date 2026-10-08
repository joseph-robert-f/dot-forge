# Dot Forge

Premade instructions and reviewed model generators for making **bounded, original 3D-printing candidates on a dot's Linux cloud computer**. Give your dot this repository and the prompt below; you do not need to operate a modeling app yourself.

This is a source-only starter, not an application installer or a general text-to-anything modeler. Python 3.11+ coordinates separately installed native applications. Your dot must check its own computer: another dot may not have the same applications or capabilities.

## Copy this to your dot

> Use Dot Forge on your Linux cloud computer. Read its README and AGENTS.md, inspect your installed applications, and run the capability doctor plus the bundled smoke example for the model family we choose. Do not silently download or install anything. Ask only for missing dimensions and intended-use details that affect the model. Use a reviewed, supported generator; explain if my request is outside its scope. Generate a fresh candidate, review front, side, back, top and oblique views of the actual exported STL, and show me the findings and remaining checks. Give me the editable native model, printing candidate, previews and evidence in a verified, durable bundle. Follow your normal permission rules for setup, sharing and printer access. Do not call it print-ready without evidence.

For a specific starting point, add one of these:

- “Help me make the flat robot mascot. Ask for any missing dimensions.”
- “Help me make the dimensioned stepped part with a through-hole. Ask for any missing dimensions and what I want to use it for.”

## What it can make

- **Blender mesh examples:** the `calibration-block` and flat, extruded robot `geometric-mascot`, using Blender 4.3.2. These are bounded generators with supported parameters, not arbitrary sculpting.
- **FreeCAD dimensioned solid:** `freecad-stepped-block`, using FreeCAD 1.0.0 / Open CASCADE 7.8.1. It makes one stepped block with an integral lower base, raised half-width step and a vertical through-hole. Each overall dimension is 5–100 mm. Outputs are FCStd, STEP and STL; Blender 4.3.2 renders the exported STL. See the [FreeCAD workflow](docs/freecad-workflow.md). Native round trips, independent STL checks, five views and fresh-bundle regeneration are verified for the documented profile; see [FreeCAD verification](docs/freecad-verification.md). Every other computer still needs its own smoke acceptance.

Choose FreeCAD for this supported dimensioned-solid family and Blender for the supported flat mascot or calibration mesh. A different part, assembly or organic character needs a separately reviewed generator; a prompt cannot expand these families automatically.

**Release scope remains a bounded native preview.** The pinned upstream Lane A adapter requires Blender 4.5.12 LTS and is still blocked: official exact-runtime retrieval returned HTTP 403. No alternate solver or bypass is substituted. The working Blender examples and the new FreeCAD route do not complete that gate. See [acceptance status](docs/acceptance.md).

A closed solid, successful render or geometry pass does not establish print suitability. Printer/material settings, thickness and clearance assessment, orientation/supports, slicing, visual approval and a physical test remain separate checks.

## Instructions and evidence

- [Assistant workflow](docs/assistant-workflow.md): the full handoff and copy-paste prompts
- [FreeCAD workflow](docs/freecad-workflow.md): dimensions, outputs and solid/mesh checks
- [Quickstart](docs/quickstart.md) and [runtime setup](docs/runtime-setup.md): Linux commands and prerequisites
- [Validation explained](docs/validation-explained.md): what passed, failed or remains unknown
- [Recovery and bundles](docs/recovery.md): preserve, verify and continue a run
- [Compatibility](docs/compatibility.md) and [acceptance map](docs/acceptance.md)
- [Benchmark methodology](benchmarks/methodology.md) and [release verification results](docs/release-validation.md)

The CLI provides `doctor`, `check-request`, `run`, `generate`, `validate`, `render`, `inspect`, `benchmark`, `bundle`, `resume` and `verify-bundle`. From a source checkout, use `PYTHONPATH=src python -m printkit --help`; each command also has `--help`. There are no pip runtime dependencies for the orchestrator. Native Blender and FreeCAD installations are separate prerequisites, not bundled Python dependencies.

No model command downloads applications or sends a model to a printer. Native subprocess limits are **not a security sandbox**; execute only reviewed code. See [security](SECURITY.md).

## License and distribution

Starter source is GPL-3.0-or-later; see [LICENSE](LICENSE). Original example assets follow [ASSET_LICENSE.md](ASSET_LICENSE.md). [Third-party notices](THIRD_PARTY_NOTICES.md) identify external source and runtime boundaries. No application binaries are distributed. Input rights, model geometry and intended use need their own review.

Keep generated models, renders, private requests and benchmark runs outside Git. Publishing or uploading designs is a separate, explicit decision. See [publishing](docs/publishing.md) and [contributing](CONTRIBUTING.md).
