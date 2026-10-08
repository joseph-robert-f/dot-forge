# CLI reference

Run from a reviewed checkout with `PYTHONPATH=src python -m printkit`, or use an installed `printkit` entry point. Commands return JSON on stdout and diagnostic text on stderr. JSON reports use `schema_version: "1"`; help is human-readable argparse output.

```text
printkit doctor [--json] [--backend blender|freecad] [--smoke NEW_RUN]
printkit check-request REQUEST_JSON
printkit run --request REQUEST_JSON --output NEW_RUN
printkit generate --request REQUEST_JSON --output NEW_RUN
printkit validate --run RUN [--profile solid-single-part]
printkit render --run RUN
printkit inspect --run RUN
printkit benchmark [--suite smoke|freecad-smoke] --output NEW_DIRECTORY [--repetitions 3]
printkit bundle --run RUN [--output NEW_ZIP]
printkit resume --run RUN
printkit verify-bundle BUNDLE_ZIP
```

- `doctor` discovers Python, platform, scratch, Blender and FreeCAD capabilities. `--json` is accepted for clarity; output is JSON either way. `--smoke` performs a real selected-backend generation/export/reopen/validation/render into a new run.
- `check-request` checks the strict supported request contract without generating geometry.
- `generate` creates the source snapshot and native/export artifacts. It does not establish independent geometry validity.
- `run` generates, validates, renders and finalizes the evidence directory. ZIP bundling is separate.
- `validate` independently checks the exact printing STL. Only the initial `solid-single-part` profile is supported.
- `render` produces the five exported-STL preview views. Human visual completeness remains unknown.
- `inspect` verifies a finalized run's integrity and returns its manifest and validation evidence. It is not a live viewer or an incomplete-run inspector.
- `benchmark --suite smoke` runs the two Blender examples; `--suite freecad-smoke` runs the stepped FreeCAD part, with 1–10 repetitions each, retaining failed observations.
- `bundle` verifies a finalized run and creates a ZIP outside it. The default is a sibling named after the run with `.zip` appended. Existing destinations are rejected.
- `resume` verifies a completed run or safely continues an incomplete one. Changed request/source identities or completed artifact hashes block reuse. Incomplete generation creates a new sibling attempt.
- `verify-bundle` checks bounded ZIP contents and internal integrity without executing embedded source.

Completed attempts are immutable: standalone `validate` and `render` reject a completed run. Use a fresh attempt for changed work. After standalone stages, `resume` can revalidate and finalize the incomplete attempt.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Command succeeded within its own scope; does not imply print approval |
| 2 | Invalid request or unsupported command arguments |
| 3 | Runtime unavailable, incompatible or failed |
| 4 | Blocked validation, integrity problem or another blocked required gate |
| 5 | Candidate needs manual/printing review |
| 6 | Execution timeout |
| 7 | Internal failure |

A geometry-valid `run`, `validate` or `inspect` normally exits 5 because printing/manual checks remain unresolved. Do not use `command && next-command` if you intend to continue after this expected review state without examining it. A successful doctor smoke or benchmark may exit 0 for its narrower geometry-test scope while printing remains unverified. Read the structured report, not just the exit code.

`doctor --backend blender|freecad` chooses the smoke workflow and command exit status (default: blender). Both native capabilities are reported. `--smoke NEW_RUN` performs the selected complete workflow, including actual STL validation and Blender previews.
