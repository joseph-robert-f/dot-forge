"""v2 measure: a STEP file from any tool -> the same B-rep measurement as a build.

With a confirmed intent, the part is checked like a build: intent checks,
then an independent check of a mesh made from the STEP. The source tool,
its code and its own checks are not trusted or needed. The part is measured
as found: it is not moved or turned, so the intent's axes must be the
file's axes.
"""
from pathlib import Path
from .common import ForgeError, canonical_hash, load_json, sha256, write_json
from .conformance import conform, holes, partial_holes
from .forge import SCHEMA, fresh_run
from .intent import check_intent
from .validation import validate_mesh
from .adapters import freecad_plan

MAX_STEP_BYTES = 64 * 1024 * 1024
STEP_SUFFIXES = (".step", ".stp")
STEP_HEADER = b"ISO-10303-21;"
ARTIFACTS = ("input/part.step", "native/measure.json", "native/source.json", "exports/model.stl")
ASSUMPTIONS = {"units": "mm, as FreeCAD reads the STEP file",
               "orientation": "as in the file; the part is not moved or turned",
               "origin": "positions are from the lowest corner of the part's bounding box"}


def read_step(path):
    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise ForgeError("The STEP file does not exist or is not a regular file", 2, "step_missing")
    if source.suffix.lower() not in STEP_SUFFIXES:
        raise ForgeError("Give a STEP file (.step or .stp)", 2, "step_suffix")
    size = source.stat().st_size
    if size > MAX_STEP_BYTES:
        raise ForgeError(f"The STEP file is larger than {MAX_STEP_BYTES // (1024 * 1024)} MB", 2, "step_too_large")
    data = source.read_bytes()
    if not data.lstrip().startswith(STEP_HEADER):
        raise ForgeError("The file does not start with a STEP (ISO 10303-21) header", 2, "step_header")
    return data


def summary(m, source):
    return {"size_mm": m["size_mm"], "volume_mm3": m["volume_mm3"], "solid_count": m["solid_count"],
            "shell_count": m["shell_count"], "valid": m["valid"], "closed": m["closed"],
            "holes": len(holes(m)), "partial_holes": len(partial_holes(m)),
            "faces": dict(source["surfaces"], total=m["face_count"])}


def warnings(m, source):
    found = []
    other = source["surfaces"]["other"]
    if other:
        found.append(f"{other} of {m['face_count']} faces are not planes or cylinders. "
                     "Holes and flat faces made from them are not measured, so their checks can fail.")
    if source["mesh"]["status"] == "pass" and source["mesh"]["linear_deflection_mm"] > freecad_plan.LINEAR_DEFLECTION_MM:
        found.append(f"The check mesh uses a {source['mesh']['linear_deflection_mm']} mm deflection "
                     "to stay inside the triangle budget.")
    return found


def measure_part(step, output, *, intent=None, discover=None):
    if intent is not None:
        check_intent(intent, require_confirmed=True)
    data = read_step(step)
    run = fresh_run(output)
    (run / "input").mkdir()
    (run / "input/part.step").write_bytes(data)
    report = {"schema_version": SCHEMA, "source": {"kind": "step", "name": Path(step).name,
              "sha256": sha256(run / "input/part.step"), "bytes": len(data)},
              "assumptions": ASSUMPTIONS, "print_state": "needs_review", "previews": "not_run"}
    if intent is not None:
        write_json(run / "intent.json", intent)
        report["intent_sha256"] = canonical_hash(intent)
    try:
        result = freecad_plan.measure_step(run, discover)
    except ForgeError as exc:
        report.update(overall_state="blocked", intent_state="unknown", geometry_state="unknown",
                      failure={"code": exc.finding, "message": str(exc)})
        write_json(run / "report.json", report)
        raise
    measurement = load_json(run / "native/measure.json")
    source = result["source"]
    report.update(measurement=summary(measurement, source), warnings=warnings(measurement, source),
                  provenance=result["provenance"])
    if source["mesh"]["status"] == "pass":
        # Without an intent, the mesh must agree with the measured solid.
        size = intent["envelope"]["size_mm"] if intent else measurement["size_mm"]
        tolerance = intent["envelope"]["tolerance_mm"] if intent else 0
        mesh = validate_mesh(run / "exports/model.stl", {
            "dimensions_mm": size, "units": "mm",
            "allowed_components": intent["solid_count"] if intent else measurement["solid_count"],
            "tolerance_mm": tolerance + source["mesh"]["linear_deflection_mm"]})
        geometry = mesh["geometry_state"]
    else:
        mesh = {"status": "not_run", "reason": "The part needs more triangles than the mesh check allows "
                f"({source['mesh']['triangle_budget']}), even at {source['mesh']['tried_deflections_mm'][-1]} mm."}
        geometry = "unknown"
    report.update(geometry_state=geometry, mesh_validation=mesh)
    if intent is None:
        report.update(intent_state="not_checked",
                      overall_state="measured" if geometry == "geometry_validated" else "blocked")
    else:
        conformance = conform(intent, measurement)
        blocked = conformance["intent_state"] == "blocked" or geometry != "geometry_validated"
        report.update(intent_state=conformance["intent_state"], conformance=conformance,
                      overall_state="blocked" if blocked else "needs_review",
                      person_checks=conformance["person_checks"] + ["five_view_review", "print_settings", "physical_test"])
    report["artifacts"] = {name: sha256(run / name) for name in ARTIFACTS + (("intent.json",) if intent else ())
                           if (run / name).is_file()}
    write_json(run / "report.json", report)
    return report
