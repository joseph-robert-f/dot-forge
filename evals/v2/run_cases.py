"""Build every field-test case, attempt and mutant, and print one line for each.

Run from the repository root on a computer with the FreeCAD runtime:
    PYTHONPATH=src python3 evals/v2/run_cases.py build/field-test [--cold-measure]
The output directory must not exist. Each build gets its own run directory.
With --cold-measure, each built STEP is also measured by `printkit measure`
against the same intent, and the row says whether every check agrees.
"""
import json
import sys
from pathlib import Path
from printkit.common import ForgeError, load_json
from printkit.forge import build
from printkit.measure import measure_part

CASES = Path(__file__).resolve().parent / "cases"


def runs():
    for folder in sorted(p for p in CASES.iterdir() if p.is_dir()):
        for plan in sorted(folder.glob("plan-*.json")):
            attempt = plan.stem.split("-")[1]
            intent = folder / ("intent.json" if attempt == "001" else f"intent-{attempt}.json")
            yield f"{folder.name}-{attempt}", intent, plan
        latest = sorted(folder.glob("intent*.json"), key=lambda p: (p.name != "intent.json", p.name))[-1]
        for plan in sorted(folder.glob("mutants/*.json")):
            yield f"{folder.name}--{plan.stem}", latest, plan


def main(output, cold=False):
    output = Path(output)
    if output.exists():
        sys.exit(f"{output} exists; use a new directory")
    output.mkdir(parents=True)
    rows = []
    for name, intent, plan in runs():
        try:
            report = build(load_json(intent), load_json(plan), output / name)
            failed = [c["code"] for c in report["conformance"]["checks"] if c["required"] and c["status"] != "pass"]
            row = {"run": name, "intent_state": report["intent_state"], "geometry_state": report["geometry_state"],
                   "failed": failed}
            if cold:
                again = measure_part(output / name / "exports/model.step", output / f"{name}.measure", intent=load_json(intent))
                same = lambda r: {c["code"]: c["status"] for c in r["conformance"]["checks"]}
                row["cold_measure_matches"] = same(again) == same(report) and again["intent_state"] == report["intent_state"]
        except ForgeError as exc:
            row = {"run": name, "error": exc.code, "message": str(exc)[:200]}
        rows.append(row)
        print(json.dumps(row))
    (output / "summary.json").write_text(json.dumps(rows, indent=2) + "\n")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--cold-measure"]
    main(args[0] if args else "build/field-test", cold="--cold-measure" in sys.argv[1:])
