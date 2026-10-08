"""Hash-verified bundles with bounded, path-checked materialization.

Never executes embedded source.
"""
from pathlib import Path, PurePosixPath
import hashlib
import json
import os
import tempfile
import zipfile
from .common import ForgeError, load_json, safe_file, sha256, write_json

MANIFEST = "manifest.json"
MAX_BUNDLE = 536870912

# Only these deliverables belong in a portable run. The run directory may also
# serve as the native runtime's HOME; its caches/settings are never artifacts.
ARTIFACT_DIRECTORIES = ("source", "native", "exports", "previews", "logs", "qa")
ARTIFACT_ROOT_FILES = (
    "request.json", "resolved-profile.json", "journal.json", "generation.json",
    "validation.json", "render.json", "metrics.json", "failure.json",
)
MAX_MEMBERS = 10000

def artifact_path(name):
    """Whether a canonical relative name is inside the deliverable boundary."""
    if not isinstance(name, str):
        return False
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name or path.as_posix() != name:
        return False
    return name in ARTIFACT_ROOT_FILES or (len(path.parts) > 1 and path.parts[0] in ARTIFACT_DIRECTORIES)

def artifact_files(run):
    """Check all paths for symlinks, but never open excluded runtime files."""
    run = Path(run)
    if run.is_symlink():
        raise ForgeError("Run contains a symlink", 4, "unsafe_artifact_path")
    files = []
    # Bound traversal as well as delivered content. Do not follow symlinks even
    # in excluded HOME trees: they still indicate an unsafe run directory.
    for count, path in enumerate(run.rglob("*"), 1):
        if count > MAX_MEMBERS:
            raise ForgeError("Run inventory exceeds verification budget", 4, "output_budget")
        if path.is_symlink():
            raise ForgeError("Run contains a symlink", 4, "unsafe_artifact_path")
        if artifact_path(path.relative_to(run).as_posix()) and path.is_file():
            files.append(path)
    if sum(path.stat().st_size for path in files) > MAX_BUNDLE:
        raise ForgeError("Bundle byte budget exceeded", 4, "output_budget")
    return sorted(files)

def artifact_records(run):
    run = Path(run)
    return [{"path": path.relative_to(run).as_posix(), "bytes": path.stat().st_size,
             "sha256": sha256(path)} for path in artifact_files(run)]

def finalize(run, provenance, stages):
    run = Path(run)
    manifest = {"schema_version": "1", "state": "complete", "provenance": provenance,
                "stages": stages, "artifacts": artifact_records(run),
                "artifact_policy": {"name": "deliverables-only-v1",
                    "directories": list(ARTIFACT_DIRECTORIES), "root_files": list(ARTIFACT_ROOT_FILES),
                    "envelope_files": [MANIFEST, "COMPLETE"],
                    "inventory": "Exact within selected trees; runtime HOME caches/settings and unrelated root files excluded."},
                "trust": "Hashes detect corruption; this manifest is unsigned and is not proof against intentional forgery."}
    write_json(run / MANIFEST, manifest)
    write_json(run / "COMPLETE", {"manifest_sha256": sha256(run / MANIFEST)})
    return manifest

def verify_run(run, require_complete=True):
    run = Path(run)
    files = artifact_files(run)
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
        if not isinstance(item, dict) or set(item) != {"path", "bytes", "sha256"} or not artifact_path(item["path"]) or item["path"] in seen:
            raise ForgeError("Invalid or duplicate manifest record", 4, "invalid_manifest")
        seen.add(item["path"])
        path = safe_file(run, item["path"])
        if not path.is_file() or path.stat().st_size != item["bytes"] or sha256(path) != item["sha256"]:
            raise ForgeError(f"Artifact hash/size mismatch: {item['path']}", 4, "artifact_hash_mismatch")
    actual = {p.relative_to(run).as_posix() for p in files}
    if actual != seen:
        raise ForgeError("Manifest does not cover exact deliverable contents", 4, "manifest_inventory_mismatch")
    from .contracts import check_request
    from .adapters.registry import native_artifacts
    request = check_request(load_json(run / "request.json"))
    for required in ["request.json", "validation.json", "metrics.json", *native_artifacts(request)]:
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
    recorded_state = validation.get("geometry_state")
    if recorded_state not in ("blocked", "geometry_validated"):
        raise ForgeError("Unsupported recorded geometry verdict", 4, "invalid_manifest")
    if recorded_state == "geometry_validated":
        fresh = validate_bounded(run / "exports/model.stl", request)
        if fresh.get("geometry_state") != "geometry_validated":
            raise ForgeError("Recorded geometry verdict is not reproducible", 4, "forged_validation")
        if fresh.get("metrics", {}).get("sha256") != expected:
            raise ForgeError("Mesh changed during integrity validation", 4, "validation_hash_mismatch")
        recorded_gates = {c.get("code"): c.get("status") for c in validation.get("checks", []) if c.get("required")}
        actual_gates = {c.get("code"): c.get("status") for c in fresh.get("checks", []) if c.get("required")}
        if recorded_gates != actual_gates:
            raise ForgeError("Recorded geometry gates differ from fresh validation", 4, "forged_validation")
    # A blocked report is diagnostic evidence, not a geometry approval. Preserve
    # it even if the validator is unavailable or would reach a different result
    # later. Never upgrade its recorded state while checking transport integrity.
    if manifest.get("provenance", {}).get("geometry_state") != recorded_state:
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
            if len(names) != len(set(names)) or len(names) > MAX_MEMBERS:
                raise ForgeError("Duplicate/excessive bundle members", 4, "unsafe_bundle")
            if sum(x.file_size for x in entries) > MAX_BUNDLE:
                raise ForgeError("Uncompressed bundle exceeds budget", 4, "unsafe_bundle")
            for item in entries:
                if item.filename not in {MANIFEST, "COMPLETE"} and not artifact_path(item.filename):
                    raise ForgeError("Bundle member outside deliverable boundary", 4, "unsafe_bundle")
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
                    "sha256": sha256(path), "geometry_state": manifest["provenance"]["geometry_state"],
                    "geometry_revalidation": "passed" if manifest["provenance"]["geometry_state"] == "geometry_validated" else "not_requested_for_blocked_diagnostics",
                    "authenticity": "unsigned; internal integrity is not print approval"}
    except (OSError, zipfile.BadZipFile, KeyError, ValueError) as exc:
        raise ForgeError(f"Invalid bundle: {exc}", 4, "invalid_bundle") from exc
