"""Immutable attempts with hash-bound stages and conservative recovery."""
from pathlib import Path
import platform
import shutil
import subprocess
import time
from . import __version__
from .common import ForgeError, canonical_hash, load_json, sha256, write_json
from .contracts import check_request
from .bundle import finalize, verify_run


def repository_root():
    return Path(__file__).resolve().parents[2]

def implementation_identity():
    root = Path(__file__).parent
    files = {p.relative_to(root).as_posix(): sha256(p) for p in sorted(root.rglob("*.py"))}
    return {"version": __version__, "python_source_sha256": canonical_hash(files), "files": files}

def source_commit():
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repository_root(), capture_output=True, text=True, timeout=5)
        return result.stdout.strip() if result.returncode == 0 else "uncommitted"
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable"

def _journal(run):
    return load_json(Path(run) / "journal.json")

def verify_identity(run):
    run = Path(run)
    journal = _journal(run)
    if sha256(run/"request.json") != journal.get("request_sha256"):
        raise ForgeError("Request changed; start a fresh attempt", 4, "request_changed")
    if journal.get("implementation") != implementation_identity():
        raise ForgeError("Implementation changed; start a fresh attempt", 4, "implementation_changed")
    generation = run/"generation.json"
    if generation.is_file():
        provenance = load_json(generation).get("provenance", {})
        if provenance.get("binary_sha256"):
            from .adapters.blender import discover
            current = discover()
            if current.get("binary_sha256") != provenance["binary_sha256"] or current.get("version") != provenance.get("blender_version"):
                raise ForgeError("Runtime identity changed; regenerate in a fresh attempt", 4, "runtime_changed")
    return journal

def stage_record(run, stage, paths, details=None):
    run = Path(run)
    journal = _journal(run)
    journal["stages"][stage] = {"status": "complete", "artifacts": {str(p): sha256(run/p) for p in paths}, "details": details or {}}
    write_json(run / "journal.json", journal)

def verify_stage(run, stage):
    run = Path(run)
    journal = verify_identity(run)
    record = journal.get("stages", {}).get(stage)
    if not record or record.get("status") != "complete":
        return False
    from .common import safe_file
    required = {"generation": {"native/model.blend", "exports/model.stl", "generation.json"},
                "validation": {"validation.json", "exports/model.stl"},
                "render": {"render.json", *[f"previews/{view}.png" for view in ("front", "side", "back", "top", "oblique")]}}
    artifacts = record.get("artifacts", {})
    if not isinstance(artifacts, dict) or not required[stage].issubset(artifacts):
        raise ForgeError("Stage lacks required evidence", 4, "invalid_stage")
    if stage == "generation" and record.get("details", {}).get("request_sha256") != journal["request_sha256"]:
        raise ForgeError("Generation request identity mismatch", 4, "request_changed")
    for name, digest in artifacts.items():
        path = safe_file(run, name)
        if not path.is_file() or sha256(path) != digest:
            raise ForgeError(f"Stage artifact changed: {name}; start a new attempt", 4, "stale_stage")
    return True

def _snapshot_source(run):
    root = repository_root()
    target = Path(run) / "source"
    target.mkdir()
    # Source-only reproducibility copy, never arbitrary cwd files or VCS credentials.
    for folder in ("src", "schemas", "examples", "profiles", "scripts", "docs", "tests", "benchmarks"):
        source = root / folder
        if source.exists():
            shutil.copytree(source, target/folder, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.egg-info", "*.dist-info"))
    for name in ("pyproject.toml", "README.md", "AGENTS.md", "SECURITY.md", "CONTRIBUTING.md", "LICENSE", "ASSET_LICENSE.md", "THIRD_PARTY_NOTICES.md", "dependency-lock.json", "runtime-lock.json", "upstream.lock.json"):
        if (root/name).is_file():
            shutil.copyfile(root/name, target/name)

def begin(request, run):
    check_request(request)
    run = Path(run)
    if run.exists():
        raise ForgeError("Output already exists; use resume or choose a fresh attempt")
    run.mkdir(parents=True)
    for folder in ("native", "exports", "previews", "logs"):
        (run/folder).mkdir()
    write_json(run/"request.json", request)
    write_json(run/"resolved-profile.json", {"schema_version": "1", "validation_profile": request["validation_profile"],
               "units": "mm", "printer_profile": request["printer_profile"], "print_readiness": "unverified"})
    write_json(run/"journal.json", {"schema_version": "1", "request_sha256": sha256(run/"request.json"),
               "implementation": implementation_identity(), "stages": {}})
    _snapshot_source(run)
    return run

def sanitize_logs(run):
    run = Path(run).resolve()
    from .common import safe_file
    safe_file(run, "logs")
    for path in (run/"logs").rglob("*"):
        safe_file(run, path.relative_to(run))
        if path.is_file():
            text = path.read_text(errors="replace")
            for private in sorted({str(run), str(repository_root()), str(Path.home())}, key=len, reverse=True):
                if len(private) > 1:
                    text = text.replace(private, "<workspace>")
            path.write_text(text)

def generate(request, run):
    from .adapters import blender
    run = begin(request, run)
    started = time.monotonic()
    try:
        result = blender.generate(request, run)
        write_json(run/"generation.json", result)
        write_json(run/"metrics.json", {"schema_version": "1", "generation_wall_seconds": time.monotonic()-started,
                   "setup_download_seconds": None, "assistant_development_seconds": None, "human_iteration_seconds": None,
                   "model_provider_usage": None, "hardware": {"architecture": platform.machine(), "system": platform.system()},
                   "runtime_metrics": result.get("metrics", {}), "native_stage_metrics": result.get("native_generation", {}), "cache": "native engine launched fresh; OS caches uncontrolled"})
        stage_record(run, "generation", ["native/model.blend", "exports/model.stl", "generation.json"], {"request_sha256": sha256(run/"request.json")})
    except Exception as exc:
        write_json(run/"failure.json", {"schema_version": "1", "stage": "generation", "code": getattr(exc, "finding", "internal_failure"),
                   "message": str(exc), "next_action": "Inspect retained logs; correct runtime then resume into a new attempt."})
        raise
    finally:
        sanitize_logs(run)
    return result

def validate(run):
    from .isolated_validation import validate_bounded
    run = Path(run)
    request = check_request(load_json(run/"request.json"))
    if not verify_stage(run, "generation"):
        raise ForgeError("Generation did not complete", 4, "incomplete_generation")
    before_hash = sha256(run/"exports/model.stl")
    started = time.monotonic()
    try:
        report = validate_bounded(run/"exports/model.stl", request)
    except Exception as exc:
        report = {"schema_version": "1", "geometry_state": "blocked", "checks": [{"code": getattr(exc, "finding", "validator_crash"), "status": "unknown",
                  "actual": type(exc).__name__, "expected": "successful validation", "method": "independent validator", "evidence": None, "next_action": "Inspect validator failure; never accept this artifact."}]}
    after_hash = sha256(run/"exports/model.stl")
    validated_hash = report.get("metrics", {}).get("sha256")
    if before_hash != after_hash or (validated_hash is not None and validated_hash != after_hash):
        raise ForgeError("Export changed during validation; retain output and regenerate", 4, "validation_race")
    if report.get("geometry_state") == "geometry_validated" and validated_hash != after_hash:
        raise ForgeError("Validator did not bind parsed bytes", 4, "validation_hash_missing")
    report["artifact_sha256"] = after_hash
    report["print_assessment"] = print_assessment(request, report.get("metrics", {}).get("dimensions_mm"))
    report["overall_state"] = "blocked" if report.get("geometry_state") != "geometry_validated" or report["print_assessment"]["state"] == "blocked" else "needs_review"
    report["release_status"] = "candidate_only"
    write_json(run/"validation.json", report)
    metrics = load_json(run/"metrics.json")
    metrics["validation_wall_seconds"] = time.monotonic()-started
    write_json(run/"metrics.json", metrics)
    stage_record(run, "validation", ["validation.json", "exports/model.stl"])
    return report

def print_assessment(request, actual_dimensions=None):
    checks = [{"code": code, "status": "unknown", "severity": "manual", "next_action": action} for code, action in [
        ("visual_completeness", "Compare all five previews with requested features; no automatic design-match certification."),
        ("wall_thickness", "Measure minimum walls/features against the actual process profile."),
        ("clearance", "Measure intended gaps and fit against the actual mating part."),
        ("supports_and_orientation", "Review bed contact, overhangs and bridges in your slicer."),
        ("slicer_gate", "Slice the exact hashed STL with a named printer/material profile; inspect layers and repair notices."),
        ("physical_gate", "Print and inspect a test part; measure fit where applicable.")]]
    printer = request["printer_profile"]
    if printer is None:
        checks.append({"code": "build_envelope", "status": "unknown", "severity": "manual", "next_action": "Select a printer profile."})
    elif actual_dimensions is None:
        checks.append({"code": "build_envelope", "status": "unknown", "severity": "manual", "next_action": "Obtain verified exported dimensions."})
    else:
        fits = all(a <= b for a,b in zip(actual_dimensions, printer["build_envelope_mm"]))
        checks.append({"code": "build_envelope", "status": "pass" if fits else "fail", "severity": "block",
                       "method": "actual exported axis-aligned bounds in proposed orientation", "actual": actual_dimensions,
                       "expected": printer["build_envelope_mm"], "units": "mm", "next_action": "Confirm printer margin and orientation."})
    return {"state": "blocked" if any(x["status"] == "fail" for x in checks) else "needs_review", "checks": checks,
            "physical_success": "unverified"}

def render(run):
    from .adapters import blender
    run = Path(run)
    if not verify_stage(run, "generation"):
        raise ForgeError("Generation did not complete", 4, "incomplete_generation")
    request = check_request(load_json(run/"request.json"))
    started = time.monotonic()
    try:
        result = blender.render(request, run)
    finally:
        sanitize_logs(run)
    write_json(run/"render.json", result)
    previews = sorted(p.relative_to(run).as_posix() for p in (run/"previews").glob("*.png"))
    if len(previews) < 5:
        raise ForgeError("Five preview views were not produced", 4, "preview_incomplete")
    contact = '<!doctype html><html lang="en"><meta charset="utf-8"><title>Five-view model review</title><style>body{font-family:system-ui;background:#eef4f4;color:#17333b;margin:2rem}main{display:flex;flex-wrap:wrap}figure{margin:1rem}img{max-width:30rem;width:100%}</style><h1>Five-view model review</h1><p>Rendered from the exact printing STL. Visual completeness and print suitability require review.</p><main>'
    for view in ("front", "side", "back", "top", "oblique"):
        contact += f'<figure><img src="{view}.png" alt="{view} view of exported mesh"><figcaption>{view.title()}</figcaption></figure>'
    contact += "</main></html>"
    (run/"previews/contact-sheet.html").write_text(contact)
    stage_record(run, "render", previews + ["render.json", "previews/contact-sheet.html"])
    metrics = load_json(run/"metrics.json")
    metrics["render_wall_seconds"] = time.monotonic()-started
    write_json(run/"metrics.json", metrics)
    return result

def finish(run):
    run = Path(run)
    for stage in ("generation", "validation", "render"):
        if not verify_stage(run, stage):
            raise ForgeError(f"Stage incomplete: {stage}", 4, "incomplete_stage")
    report = load_json(run/"validation.json")
    journal = _journal(run)
    provenance = {"source_commit": source_commit(), "implementation": implementation_identity(), "units": "mm",
                  "request_sha256": sha256(run/"request.json"), "geometry_state": report["geometry_state"],
                  "print_readiness": "unverified", "environment_class": "native-reviewed-code-not-sandboxed"}
    finalize(run, provenance, journal["stages"])
    return report

def run_all(request, run):
    generate(request, run)
    validate(run)
    render(run)
    return finish(run)

def resume(run):
    run = Path(run)
    request = check_request(load_json(run/"request.json"))
    journal = _journal(run)
    if sha256(run/"request.json") != journal.get("request_sha256"):
        raise ForgeError("Request changed; use a new attempt", 4, "request_changed")
    if journal.get("implementation") != implementation_identity():
        raise ForgeError("Implementation changed; regenerate in a fresh attempt", 4, "implementation_changed")
    if (run/"COMPLETE").exists():
        verify_run(run)
        return load_json(run/"validation.json")
    if not verify_stage(run, "generation"):
        index = 1
        while run.with_name(f"{run.name}-retry-{index}").exists():
            index += 1
        retry = run.with_name(f"{run.name}-retry-{index}")
        report = run_all(request, retry)
        return {"schema_version": "1", "new_attempt": retry.name, "validation": report}
    # Revalidate even if earlier validation completed. Never infer success from presence.
    validate(run)
    if not verify_stage(run, "render"):
        render(run)
    return finish(run)
