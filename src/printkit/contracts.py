"""Strict declarative request contract; no executable inputs or loose fields."""
import math
from .common import ForgeError

REQUIRED = {"schema_version", "generator_id", "generator_version", "backend", "units", "parameters",
            "dimensions_mm", "tolerance_mm", "allowed_components", "part_count", "export_formats",
            "render_profile", "validation_profile", "printer_profile"}
GENERATORS = {"calibration-block", "geometric-mascot", "lane-a-character"}

def number(value, name, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high or not math.isfinite(value):
        raise ForgeError(f"{name} must be finite and between {low} and {high}")
    return value

def check_request(request):
    if not isinstance(request, dict) or set(request) != REQUIRED:
        missing = sorted(REQUIRED - set(request)) if isinstance(request, dict) else sorted(REQUIRED)
        extra = sorted(set(request) - REQUIRED) if isinstance(request, dict) else []
        raise ForgeError(f"Request fields must match schema; missing={missing}, unknown={extra}")
    for key, expected in {"schema_version": "1", "generator_version": "1", "backend": "blender", "units": "mm",
                          "render_profile": "five-view", "validation_profile": "solid-single-part"}.items():
        if request[key] != expected:
            raise ForgeError(f"Unsupported {key}; expected {expected!r}")
    if request["generator_id"] not in GENERATORS:
        raise ForgeError("Generator is not in reviewed allowlist")
    if request["part_count"] != 1 or type(request["part_count"]) is not int or request["allowed_components"] != 1 or type(request["allowed_components"]) is not int:
        raise ForgeError("Preview supports exactly one solid part/component")
    if request["export_formats"] != ["stl", "blend"]:
        raise ForgeError("Preview export_formats must be ['stl', 'blend']")
    dims = request["dimensions_mm"]
    if not isinstance(dims, list) or len(dims) != 3:
        raise ForgeError("dimensions_mm must have three values")
    for value in dims:
        number(value, "dimension", 1, 200)
    number(request["tolerance_mm"], "tolerance_mm", 0.001, 1)
    params = request["parameters"]
    if not isinstance(params, dict):
        raise ForgeError("parameters must be an object")
    if request["generator_id"] == "calibration-block":
        if set(params) != {"width_mm", "depth_mm", "height_mm"}:
            raise ForgeError("calibration-block requires width_mm/depth_mm/height_mm only")
        for key in params:
            number(params[key], key, 5, 100)
        expected = [params["width_mm"], params["depth_mm"], params["height_mm"]]
        if any(abs(a-b) > request["tolerance_mm"] for a,b in zip(dims, expected)):
            raise ForgeError("Dimensions conflict with calibration-block parameters")
    elif request["generator_id"] == "geometric-mascot":
        if set(params) != {"width_mm", "depth_mm", "height_mm"}:
            raise ForgeError("geometric-mascot requires width_mm/depth_mm/height_mm only")
        for key in params:
            number(params[key], key, 5, 100)
        expected = [params["width_mm"], params["depth_mm"], params["height_mm"]]
        if any(abs(a-b) > request["tolerance_mm"] for a,b in zip(dims, expected)):
            raise ForgeError("Dimensions conflict with geometric-mascot parameters")
    else:
        if params:
            raise ForgeError("Lane A preview uses one fixed reviewed fixture; parameters must be empty")
    printer = request["printer_profile"]
    if printer is not None:
        if not isinstance(printer, dict) or set(printer) != {"process", "build_envelope_mm", "minimum_wall_mm", "minimum_clearance_mm"}:
            raise ForgeError("printer_profile fields: process/build_envelope_mm/minimum_wall_mm/minimum_clearance_mm")
        if printer["process"] != "fdm":
            raise ForgeError("Only explicitly selected FDM assessment is supported")
        envelope = printer["build_envelope_mm"]
        if not isinstance(envelope, list) or len(envelope) != 3:
            raise ForgeError("build_envelope_mm must contain three values")
        for value in envelope:
            number(value, "build_envelope_mm", 1, 2000)
        for key in ("minimum_wall_mm", "minimum_clearance_mm"):
            number(printer[key], key, 0.01, 20)
    return request
