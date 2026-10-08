"""Hash-verified portable run bundles; never extracts untrusted archives."""
from pathlib import Path, PurePosixPath
import hashlib
import json
import os
import tempfile
import zipfile
from .common import ForgeError, load_json, safe_file, sha256, write_json

MANIFEST = "manifest.json"
MAX_BUNDLE = 536870912

def artifact_records(run):
    run = Path(run)
    records = []
    for path in sorted(run.rglob("*")):
        if path.is_symlink():
            raise ForgeError("Run contains a symlink", 4, "unsafe_artifact_path")
        if path.is_file() and path.name not in {MANIFEST, "COMPLETE"} and not path.name.startswith(".partial-"):
            relative = path.relative_to(run).as_posix()
            records.append({"path": relative, "bytes": path.stat().st_size, "sha256": sha256(path)})
    if sum(x["bytes"] for x in records) > MAX_BUNDLE:
        raise ForgeError("Bundle byte budget exceeded", 4, "output_budget")
    return records

def finalize(run, provenance, stages):
    run = Path(run)
    manifest = {"schema_version": "1", "state": "complete", "provenance": provenance,
                "stages": stages, "artifacts": artifact_records(run),
                "trust": "Hashes detect corruption; this manifest is unsigned and is not proof against intentional forgery."}
    write_json(run / MANIFEST, manifest)
    write_json(run / "COMPLETE", {"manifest_sha256": sha256(run / MANIFEST)})
    return manifest

def verify_run(run, require_complete=True):
    run = Path(run)
    if run.is_symlink() or any(p.is_symlink() for p in run.rglob("*")):
        raise ForgeError("Run contains symlink artifacts", 4, "unsafe_artifact_path")
    files = [p for p in run.rglob("*") if p.is_file()]
    if len(files) > 10000 or sum(p.stat().st_size for p in files) > MAX_BUNDLE:
        raise ForgeError("Run inventory exceeds verification budget", 4, "output_budget")
    manifest = load_json(run / MANIFEST)
    if manifest.get("schema_version") != "1" or manifest.get("state") != "complete":
        raise ForgeError("Unsupported or incomplete manifest", 4, "invalid_manifest")
    if require_complete:
        complete = load_json(run / "COMPLETE")
        if complete.get("manifest_sha256") != sha256(run / MANIFEST):
            raise ForgeError("Completion marker disagrees with manifest", 4, "manifest_hash_mismatch")
    records = manifest.get("artifacts")
    if not isinstance(records, list) or not records:
        raise ForgeError("Manifest has no artifacts", 4, "invalid_manifest")
    seen = set()
    for item in records:
        if not isinstance(item, dict) or set(item) != {"path", "bytes", "sha256"} or item["path"] in seen:
            raise ForgeError("Invalid or duplicate manifest record", 4, "invalid_manifest")
        seen.add(item["path"])
        path = safe_file(run, item["path"])
        if not path.is_file() or path.stat().st_size != item["bytes"] or sha256(path) != item["sha256"]:
            raise ForgeError(f"Artifact hash/size mismatch: {item['path']}", 4, "artifact_hash_mismatch")
    actual = {p.relative_to(run).as_posix() for p in run.rglob("*") if p.is_file() and p.name not in {MANIFEST, "COMPLETE"}}
    if actual != seen:
        raise ForgeError("Manifest does not cover exact run contents", 4, "manifest_inventory_mismatch")
    for required in ("request.json", "validation.json", "exports/model.stl", "native/model.blend", "metrics.json"):
        if required not in seen:
            raise ForgeError(f"Missing required artifact: {required}", 4, "invalid_manifest")
    validation = load_json(run / "validation.json")
    expected = next(x["sha256"] for x in records if x["path"] == "exports/model.stl")
    if validation.get("artifact_sha256") != expected:
        raise ForgeError("Validation does not bind the exported mesh", 4, "validation_hash_mismatch")
    # A consistent unsigned manifest is not proof of validation: independently
    # recompute required geometry gates before reporting integrity success.
    from .contracts import check_request
    from .isolated_validation import validate_bounded
    request = check_request(load_json(run / "request.json"))
    fresh = validate_bounded(run / "exports/model.stl", request)
    if fresh.get("geometry_state") != validation.get("geometry_state"):
        raise ForgeError("Recorded geometry verdict is not reproducible", 4, "forged_validation")
    if fresh.get("metrics", {}).get("sha256") != expected:
        raise ForgeError("Mesh changed during integrity validation", 4, "validation_hash_mismatch")
    recorded_gates = {c.get("code"): c.get("status") for c in validation.get("checks", []) if c.get("required")}
    actual_gates = {c.get("code"): c.get("status") for c in fresh.get("checks", []) if c.get("required")}
    if recorded_gates != actual_gates:
        raise ForgeError("Recorded geometry gates differ from fresh validation", 4, "forged_validation")
    if manifest.get("provenance", {}).get("geometry_state") != validation.get("geometry_state"):
        raise ForgeError("Manifest and validation disagree", 4, "forged_validation")
    return manifest

def create_bundle(run, output=None):
    run = Path(run).resolve()
    manifest = verify_run(run)
    output = Path(output).resolve() if output else run.with_name(run.name + ".zip")
    if output.is_relative_to(run):
        raise ForgeError("Bundle destination must be outside its run")
    if output.exists():
        raise ForgeError("Bundle destination already exists; choose a new path")
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=output.parent, prefix=".partial-")
    os.close(fd)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name in sorted([x["path"] for x in manifest["artifacts"]] + [MANIFEST, "COMPLETE"]):
                archive.write(safe_file(run, name), name)
        verify_bundle(temporary)
        os.replace(temporary, output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {"schema_version": "1", "bundle": output.name, "sha256": sha256(output), "bytes": output.stat().st_size}

def verify_bundle(path):
    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            names = [x.filename for x in entries]
            if len(names) != len(set(names)) or len(names) > 10000:
                raise ForgeError("Duplicate/excessive bundle members", 4, "unsafe_bundle")
            if sum(x.file_size for x in entries) > MAX_BUNDLE:
                raise ForgeError("Uncompressed bundle exceeds budget", 4, "unsafe_bundle")
            for item in entries:
                p = PurePosixPath(item.filename)
                if p.is_absolute() or ".." in p.parts or "\\" in item.filename or item.is_dir() or ((item.external_attr >> 16) & 0o170000) == 0o120000:
                    raise ForgeError("Unsafe bundle member", 4, "unsafe_bundle")
            # Temporary materialization is bounded and path-checked before writing.
            with tempfile.TemporaryDirectory(prefix="printkit-verify-") as directory:
                for item in entries:
                    dest = safe_file(directory, item.filename)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(item) as source, dest.open("wb") as target:
                        while block := source.read(1024*1024):
                            target.write(block)
                manifest = verify_run(directory)
            return {"schema_version": "1", "status": "pass", "artifact_count": len(manifest["artifacts"]),
                    "sha256": sha256(path), "authenticity": "unsigned; only internal integrity verified"}
    except (OSError, zipfile.BadZipFile, KeyError, ValueError) as exc:
        raise ForgeError(f"Invalid bundle: {exc}", 4, "invalid_bundle") from exc
