"""Strict v2 intent spec: the user's ask as measurable checks, data only.

The intent spec fixes what "the part the user asked for" means before any
geometry exists. Each feature is either measurable on the native solid
(envelope, hole, planar_face, volume) or a note that a person must review.
Anything the ask did not state belongs in `unknowns`, never in an invented
value. A plan is judged against this file, not against itself.
"""
import math
import re
from .common import ForgeError, canonical_hash

SCHEMA = "intent.v1"
AXES = ("x", "y", "z")
NORMALS = ("+x", "-x", "+y", "-y", "+z", "-z")
ID = re.compile(r"^[a-z][a-z0-9-]{0,47}$")
MAX_FEATURES = 64
# What a hole end opens into. "void" is empty space inside the part, such as a
# bore or cavity. "shoulder" is a filled step around a narrower coaxial hole.
HOLE_ENDS = ("outside", "floor", "void", "shoulder")
MAX_TEXT = 4000
FIELDS = {"schema_version", "ask", "units", "envelope", "solid_count", "features",
          "unknowns", "confirmation"}
OPTIONAL = {"volume_mm3"}
FEATURE_FIELDS = {
    "hole": ({"id", "kind", "axis", "diameter_mm", "position_mm", "depth", "tolerance_mm"}, {"source"}),
    "planar_face": ({"id", "kind", "normal", "offset", "min_area_mm2", "tolerance_mm"}, {"source", "max_area_mm2"}),
    "note": ({"id", "kind", "text"}, {"source"}),
}


def number(value, name, low, high, *, low_open=False):
    if (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
            or value > high or value < low or (low_open and value == low)):
        bound = f"({low}, {high}]" if low_open else f"[{low}, {high}]"
        raise ForgeError(f"{name} must be a finite number in {bound}")
    return value


def text(value, name, limit=MAX_TEXT):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ForgeError(f"{name} must be nonempty text of at most {limit} characters")
    return value


def exact_fields(value, required, optional, name):
    if not isinstance(value, dict):
        raise ForgeError(f"{name} must be an object")
    keys = set(value)
    if not required <= keys or keys - required - optional:
        raise ForgeError(f"{name} fields must match schema; missing={sorted(required - keys)}, "
                         f"unknown={sorted(keys - required - optional)}")


def plane_axes(axis):
    """Coordinates of a hole position: the two axes perpendicular to the hole axis."""
    return [a for a in AXES if a != axis]


def check_feature(feature, envelope, index):
    name = f"features[{index}]"
    if not isinstance(feature, dict) or feature.get("kind") not in FEATURE_FIELDS:
        raise ForgeError(f"{name}.kind must be one of {sorted(FEATURE_FIELDS)}")
    required, optional = FEATURE_FIELDS[feature["kind"]]
    exact_fields(feature, required, optional, name)
    if not isinstance(feature["id"], str) or not ID.match(feature["id"]):
        raise ForgeError(f"{name}.id must match {ID.pattern}")
    if "source" in feature:
        text(feature["source"], f"{name}.source", 500)
    size = dict(zip(AXES, envelope["size_mm"]))
    if feature["kind"] == "note":
        text(feature["text"], f"{name}.text", 500)
        return
    number(feature["tolerance_mm"], f"{name}.tolerance_mm", 0.001, 5)
    if feature["kind"] == "hole":
        if feature["axis"] not in AXES:
            raise ForgeError(f"{name}.axis must be one of {AXES}")
        number(feature["diameter_mm"], f"{name}.diameter_mm", 0, 500, low_open=True)
        position = feature["position_mm"]
        if not isinstance(position, list) or len(position) != 2:
            raise ForgeError(f"{name}.position_mm must hold two values: {'/'.join(plane_axes(feature['axis']))} "
                             "from the envelope minimum corner")
        for value, axis in zip(position, plane_axes(feature["axis"])):
            number(value, f"{name}.position_mm.{axis}", 0, size[axis])
        depth = feature["depth"]
        if isinstance(depth, dict) and "ends" in depth:
            exact_fields(depth, {"ends"}, {"depth_mm"}, f"{name}.depth")
            exact_fields(depth["ends"], {"min", "max"}, set(), f"{name}.depth.ends")
            if any(end not in HOLE_ENDS for end in depth["ends"].values()):
                raise ForgeError(f"{name}.depth.ends values must be one of {HOLE_ENDS}")
            if "outside" not in depth["ends"].values():
                raise ForgeError(f"{name}.depth.ends must open to the outside at one end or more")
            if "depth_mm" in depth:
                number(depth["depth_mm"], f"{name}.depth.depth_mm", 0, size[feature["axis"]], low_open=True)
        elif depth != "through":
            exact_fields(depth, {"depth_mm", "open_end"}, set(), f"{name}.depth")
            number(depth["depth_mm"], f"{name}.depth.depth_mm", 0, size[feature["axis"]], low_open=True)
            if depth["open_end"] not in ("min", "max"):
                raise ForgeError(f"{name}.depth.open_end must be min or max")
    else:
        if feature["normal"] not in NORMALS:
            raise ForgeError(f"{name}.normal must be one of {NORMALS}")
        offset, axis = feature["offset"], feature["normal"][1]
        if offset not in ("min", "max"):
            number(offset, f"{name}.offset", 0, size[axis])
        number(feature["min_area_mm2"], f"{name}.min_area_mm2", 0, 250000, low_open=True)
        if "max_area_mm2" in feature:
            # An upper bound catches a face that is too big, such as an overlong slot wall.
            number(feature["max_area_mm2"], f"{name}.max_area_mm2", feature["min_area_mm2"], 250000)


def check_intent(intent, *, require_confirmed=False):
    exact_fields(intent, FIELDS, OPTIONAL, "intent")
    if intent["schema_version"] != SCHEMA:
        raise ForgeError(f"Unsupported intent schema_version; expected {SCHEMA!r}")
    if intent["units"] != "mm":
        raise ForgeError("Intent units must be mm")
    text(intent["ask"], "ask")
    envelope = intent["envelope"]
    exact_fields(envelope, {"size_mm", "tolerance_mm"}, set(), "envelope")
    if not isinstance(envelope["size_mm"], list) or len(envelope["size_mm"]) != 3:
        raise ForgeError("envelope.size_mm must hold x, y and z sizes")
    for value, axis in zip(envelope["size_mm"], AXES):
        number(value, f"envelope.size_mm.{axis}", 1, 500)
    number(envelope["tolerance_mm"], "envelope.tolerance_mm", 0.001, 5)
    if intent["solid_count"] != 1 or type(intent["solid_count"]) is not int:
        raise ForgeError("The v2 preview profile supports exactly one solid")
    if "volume_mm3" in intent:
        volume = intent["volume_mm3"]
        exact_fields(volume, {"min", "max"}, set(), "volume_mm3")
        number(volume["min"], "volume_mm3.min", 0, 125000000)
        number(volume["max"], "volume_mm3.max", volume["min"], 125000000)
    features = intent["features"]
    if not isinstance(features, list) or len(features) > MAX_FEATURES:
        raise ForgeError(f"features must be a list of at most {MAX_FEATURES}")
    for index, feature in enumerate(features):
        check_feature(feature, envelope, index)
    ids = [f["id"] for f in features]
    if len(ids) != len(set(ids)):
        raise ForgeError("Feature ids must be unique")
    unknowns = intent["unknowns"]
    if not isinstance(unknowns, list) or len(unknowns) > 32:
        raise ForgeError("unknowns must be a list of at most 32 items")
    for index, item in enumerate(unknowns):
        text(item, f"unknowns[{index}]", 200)
    confirmation = intent["confirmation"]
    exact_fields(confirmation, {"status"}, {"by", "note"}, "confirmation")
    if confirmation["status"] not in ("draft", "confirmed"):
        raise ForgeError("confirmation.status must be draft or confirmed")
    if confirmation["status"] == "confirmed" and confirmation.get("by") != "user":
        raise ForgeError("A confirmed intent must record confirmation.by = user")
    for key in ("by", "note"):
        if key in confirmation:
            text(confirmation[key], f"confirmation.{key}", 500)
    if require_confirmed and confirmation["status"] != "confirmed":
        raise ForgeError("Intent is a draft; show it to the user and record their confirmation before building",
                         2, "intent_unconfirmed")
    return intent


def summarize(intent):
    """Stable CLI summary of what will be measured and what stays with a person."""
    measured = ["envelope", "solid_count"] + (["volume_mm3"] if "volume_mm3" in intent else [])
    measured += [f["id"] for f in intent["features"] if f["kind"] != "note"]
    return {"schema_version": SCHEMA, "status": "pass", "intent_sha256": canonical_hash(intent),
            "confirmation": intent["confirmation"]["status"], "measured_checks": measured,
            "person_checks": [f["id"] for f in intent["features"] if f["kind"] == "note"],
            "unknowns": intent["unknowns"]}
