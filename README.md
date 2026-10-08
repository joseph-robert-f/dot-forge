# Dot Forge

A source-only starter for producing **bounded, original 3D model candidates with inspectable evidence**. Python 3.11+ orchestrates reviewed Blender generators; exported geometry is checked separately from generation.

**Release scope: native preview, not architecture MVP completion.** The original `calibration-block` and flat, extruded robot `geometric-mascot` examples target the documented Blender 4.3.2 preview profile. The pinned upstream Lane A adapter requires Blender 4.5.12 LTS and remains blocked in the release test environment. The exact-runtime download returned HTTP 403; no alternate solver or bypass is substituted. See [acceptance status](docs/acceptance.md).

A successful preview or a closed mesh does not establish print suitability. Required geometry checks can remain unknown. Wall thickness, clearances, slicing, visual approval and real-print testing are separate gates; this release does not issue a universal “print-ready” certification.

## Start here

- [Quickstart](docs/quickstart.md): run the doctor and an original example
- [Runtime setup](docs/runtime-setup.md): exact profiles and the blocked Lane A route
- [Validation explained](docs/validation-explained.md): what the evidence means
- [Assistant workflow](docs/assistant-workflow.md): use this repository with an assistant
- [Recovery and bundles](docs/recovery.md): retain, verify and continue work
- [Compatibility](docs/compatibility.md) and [acceptance map](docs/acceptance.md)
- [Benchmark methodology](benchmarks/methodology.md) and [verified preview results](docs/release-validation.md)

The CLI provides `doctor`, `check-request`, `run`, `generate`, `validate`, `render`, `inspect`, `benchmark`, `bundle`, `resume` and `verify-bundle`. Run `python -m printkit --help` with `PYTHONPATH=src`, or use the installed `printkit` entry point. Individual commands have `--help`.

There are no Python runtime package dependencies. Blender is a separate application, not a bundled dependency. The project neither downloads applications during generation nor sends models to printers. Native subprocess limits are **not a security sandbox**. Execute only reviewed code. See [security](SECURITY.md).

## License and distribution

Starter source is GPL-3.0-or-later; see [LICENSE](LICENSE). The independent original example assets have the policy in [ASSET_LICENSE.md](ASSET_LICENSE.md). [Third-party notices](THIRD_PARTY_NOTICES.md) identify the pinned external builder and runtime boundaries. No application binaries are distributed. A model's geometry, input rights and intended use need their own review.

Keep generated models, renders, private requests and benchmark runs outside Git. Publishing or uploading designs is a separate, explicit decision. See [publishing](docs/publishing.md) and [contributing](CONTRIBUTING.md).
