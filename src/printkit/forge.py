"""v2 build: confirmed intent + bound plan -> FreeCAD solid -> evidence.

Each build writes into a fresh run directory and keeps it, pass or fail.
A repair is a new plan in a new run directory. The report keeps three
answers apart: does the solid match the intent, is the exported mesh sound,
and is it ready to print (never decided here).
"""
from pathlib import Path
from .common import ForgeError, canonical_hash, load_json, sha256, write_json
from .conformance import conform
from .intent import check_intent
from .plan import check_plan
from .validation import validate_mesh
from .adapters import freecad_plan

SCHEMA = "report.v2"
ARTIFACTS = ("intent.json", "plan.json", "native/model.FCStd", "exports/model.step", "exports/model.stl",
             "native/generation.json", "native/reopen.json", "native/measure.json")


def fresh_run(output):
    supplied = Path(output).absolute()
    if any(path.is_symlink() for path in (supplied, *supplied.parents)):
        raise ForgeError("Symlink run directory is not supported", 4, "unsafe_artifact_path")
    if supplied.exists() and (not supplied.is_dir() or any(supplied.iterdir())):
        raise ForgeError("Run directory must be new or empty; start each attempt in a fresh directory", 4, "run_exists")
    supplied.mkdir(parents=True, exist_ok=True)
    return supplied.resolve()


def build(intent, plan, output, *, discover=None, approved_preview=None):
    check_intent(intent, require_confirmed=True)
    plan_summary = check_plan(plan, intent)
    approved = None
    if approved_preview is not None:
        from .preview import approval
        approved = approval(approved_preview, intent, plan)
    run = fresh_run(output)
    write_json(run / "intent.json", intent)
    write_json(run / "plan.json", plan)
    report = {"schema_version": SCHEMA, "intent_sha256": canonical_hash(intent),
              "plan_sha256": plan_summary["plan_sha256"], "plan_warnings": plan_summary["warnings"],
              "print_state": "needs_review", "previews": "not_run"}
    try:
        generation = freecad_plan.generate(run, discover)
    except ForgeError as exc:
        report.update(overall_state="blocked", intent_state="unknown", geometry_state="unknown",
                      failure={"code": exc.finding, "message": str(exc)})
        write_json(run / "report.json", report)
        raise
    conformance = conform(intent, load_json(run / "native/measure.json"))
    envelope = intent["envelope"]
    # STL vertices lie on curved surfaces, so the mesh box can be short by up to the chord deflection.
    mesh = validate_mesh(run / "exports/model.stl", {
        "dimensions_mm": envelope["size_mm"], "units": "mm", "allowed_components": intent["solid_count"],
        "tolerance_mm": envelope["tolerance_mm"] + freecad_plan.LINEAR_DEFLECTION_MM})
    blocked = conformance["intent_state"] == "blocked" or mesh["geometry_state"] == "blocked"
    views = ["five_view_review"]
    if approved is not None:
        from .preview import same_solid
        matches = same_solid(approved["solid"], load_json(run / "native/measure.json"))
        report["approved_preview"] = {"path": str(Path(approved_preview).resolve()), "matches": matches,
                                      "preview_sha256": sha256(Path(approved_preview) / "preview.json"),
                                      "files": approved["files"]}
        # The person approved views of this same solid; a different solid needs a new review.
        views = [] if matches else ["five_view_review"]
    report.update(intent_state=conformance["intent_state"], geometry_state=mesh["geometry_state"],
                  overall_state="blocked" if blocked else "needs_review",
                  person_checks=conformance["person_checks"] + views + ["print_settings", "physical_test"],
                  conformance=conformance, mesh_validation=mesh, generation=generation,
                  artifacts={name: sha256(run / name) for name in ARTIFACTS})
    write_json(run / "report.json", report)
    return report
