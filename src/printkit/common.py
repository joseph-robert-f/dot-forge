"""Small strict I/O primitives shared by the CLI."""
import hashlib
import json
import os
from pathlib import Path
import tempfile

SCHEMA = "1"
class ForgeError(Exception):
    def __init__(self, message, code=2, finding="invalid_request"):
        super().__init__(message)
        self.code, self.finding = code, finding

def load_json(path):
    def reject_constant(value):
        raise ValueError(f"Nonfinite JSON number: {value}")
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    try:
        if Path(path).stat().st_size > 8 * 1024 * 1024:
            raise ForgeError("JSON input exceeds 8 MiB budget")
        return json.loads(Path(path).read_text(), parse_constant=reject_constant, object_pairs_hook=unique_pairs)
    except (OSError, ValueError) as exc:
        raise ForgeError(f"Cannot read valid JSON: {Path(path).name}: {exc}") from exc

def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    fd, temporary = tempfile.mkstemp(prefix=".partial-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            digest.update(block)
    return digest.hexdigest()

def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()

def safe_file(root, relative):
    root = Path(root).resolve()
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:
        raise ForgeError("Unsafe artifact path", 4, "unsafe_artifact_path")
    path = root / rel
    if any(p.is_symlink() for p in [path, *path.parents] if p != root.parent):
        raise ForgeError("Symlink artifacts are not supported", 4, "unsafe_artifact_path")
    if not path.resolve().is_relative_to(root):
        raise ForgeError("Artifact escapes run directory", 4, "unsafe_artifact_path")
    return path
