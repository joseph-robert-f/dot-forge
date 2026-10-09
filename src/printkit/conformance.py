"""Judge native-solid measurements against a confirmed intent spec.

Pure Python, so it is testable without FreeCAD. The measurement comes from the
FreeCAD helper (`native/measure.json`). Positions are measured from the minimum
corner of the solid's bounding box, the same frame the intent spec uses.

A check passes only when the measured value meets the intent within its
tolerance. A missing or unreadable measurement is `unknown`, never a pass.
Notes and unrequested holes go to a person as `needs_review`.
"""
import math
from .common import ForgeError
from .intent import AXES, plane_axes

FULL_TURN = 2 * math.pi - 1e-6
SCHEMA = "conformance.v1"


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def check_measurement(m):
    """Reject malformed measurements instead of letting them pass by omission."""
    try:
        ok = (isinstance(m, dict) and type(m["valid"]) is bool and type(m["closed"]) is bool
              and type(m["solid_count"]) is int and type(m["shell_count"]) is int
              and len(m["size_mm"]) == 3 and all(map(finite, m["size_mm"]))
              and finite(m["volume_mm3"]) and isinstance(m["cylinders"], list) and isinstance(m["planes"], list))
        for c in m["cylinders"]:
            ok = ok and c["axis"] in (*AXES, None) and finite(c["radius_mm"]) and finite(c["angle_rad"]) \
                and c["kind"] in ("void", "boss")
        for p in m["planes"]:
            ok = ok and finite(p["area_mm2"])
    except (KeyError, TypeError):
        ok = False
    if not ok:
        raise ForgeError("Measurement is malformed; rerun the FreeCAD measurement stage", 4, "measurement_invalid")
    return m


def record(code, status, actual=None, expected=None, method="native B-rep measurement", required=True):
    return {"code": code, "status": status, "actual": actual, "expected": expected,
            "method": method, "required": required}


def holes(m):
    return [c for c in m["cylinders"] if c["kind"] == "void" and c["angle_rad"] >= FULL_TURN
            and c["axis"] is not None and c.get("position_mm") is not None]


def check_hole(feature, measured, claimed):
    axis, tol = feature["axis"], feature["tolerance_mm"]
    want_r = feature["diameter_mm"] / 2
    code = f"feature:{feature['id']}"
    expected = {k: feature[k] for k in ("axis", "diameter_mm", "position_mm", "depth", "tolerance_mm")}
    same_axis = [(i, c) for i, c in enumerate(measured) if c["axis"] == axis and i not in claimed]
    distance = lambda c: math.dist(c["position_mm"], feature["position_mm"])
    matches = [(i, c) for i, c in same_axis if abs(c["radius_mm"] - want_r) <= tol
               and all(abs(a - b) <= tol for a, b in zip(c["position_mm"], feature["position_mm"]))]
    if not matches:
        nearest = min(same_axis, key=lambda ic: distance(ic[1]), default=(None, None))[1]
        found = None if nearest is None else {"diameter_mm": 2 * nearest["radius_mm"],
                                              "position_mm": nearest["position_mm"]}
        return record(code, "fail", {"nearest_hole": found}, expected,
                      f"no full cylindrical void on axis {axis} at this diameter and position")
    index, hole = min(matches, key=lambda ic: distance(ic[1]))
    claimed.add(index)
    ends, span = hole.get("ends_open"), hole.get("span_mm")
    actual = {"diameter_mm": 2 * hole["radius_mm"], "position_mm": hole["position_mm"],
              "span_mm": span, "ends_open": ends}
    if not isinstance(ends, list) or len(ends) != 2 or not all(type(e) is bool for e in ends) \
            or not isinstance(span, list) or len(span) != 2 or not all(map(finite, span)):
        return record(code, "unknown", actual, expected, "hole ends could not be probed")
    if feature["depth"] == "through":
        ok = ends == [True, True]
    else:
        open_index = 1 if feature["depth"]["open_end"] == "max" else 0
        ok = ends[open_index] and not ends[1 - open_index] \
            and abs((span[1] - span[0]) - feature["depth"]["depth_mm"]) <= tol
    return record(code, "pass" if ok else "fail", actual, expected,
                  "analytic cylinder radius/axis/position; probes beyond each end decide through or blind")


def check_planar(feature, m):
    axis = feature["normal"][1]
    size = dict(zip(AXES, m["size_mm"]))[axis]
    want = {"min": 0, "max": size}.get(feature["offset"], feature["offset"])
    tol = feature["tolerance_mm"]
    area = sum(p["area_mm2"] for p in m["planes"] if p.get("normal") == feature["normal"]
               and finite(p.get("offset_mm")) and abs(p["offset_mm"] - want) <= tol)
    return record(f"feature:{feature['id']}", "pass" if area >= feature["min_area_mm2"] else "fail",
                  {"area_mm2": area}, {k: feature[k] for k in ("normal", "offset", "min_area_mm2", "tolerance_mm")},
                  "sum of planar face areas with this outward normal at this offset")


def conform(intent, measurement):
    m = check_measurement(measurement)
    # One shell per solid: an inner shell is a sealed cavity, which v2 does not support.
    whole = m["valid"] and m["closed"] and m["solid_count"] == intent["solid_count"] == m["shell_count"]
    checks = [record("native_solid", "pass" if whole else "fail",
                     {"valid": m["valid"], "closed": m["closed"], "solid_count": m["solid_count"],
                      "shell_count": m["shell_count"]},
                     {"valid": True, "closed": True, "solid_count": intent["solid_count"],
                      "shell_count": intent["solid_count"]})]
    envelope = intent["envelope"]
    checks.append(record("envelope", "pass" if all(abs(a - b) <= envelope["tolerance_mm"]
                                                   for a, b in zip(m["size_mm"], envelope["size_mm"])) else "fail",
                         m["size_mm"], envelope, "bounding box of the native solid"))
    if "volume_mm3" in intent:
        v = intent["volume_mm3"]
        checks.append(record("volume", "pass" if v["min"] <= m["volume_mm3"] <= v["max"] else "fail",
                             m["volume_mm3"], v))
    measured, claimed = holes(m), set()
    # Exact intent features claim holes first; each measured hole satisfies at most one feature.
    for feature in intent["features"]:
        if feature["kind"] == "hole":
            checks.append(check_hole(feature, measured, claimed))
        elif feature["kind"] == "planar_face":
            checks.append(check_planar(feature, m))
        else:
            checks.append(record(f"feature:{feature['id']}", "needs_review", None, feature["text"],
                                 "a person compares the five views with this note", required=False))
    extra = [{"axis": c["axis"], "diameter_mm": 2 * c["radius_mm"], "position_mm": c["position_mm"]}
             for i, c in enumerate(measured) if i not in claimed]
    checks.append(record("unrequested_holes", "needs_review" if extra else "pass", extra, [],
                         "full cylindrical voids that no intent feature asked for", required=False))
    for unknown in intent["unknowns"]:
        checks.append(record("unknown", "unknown", None, unknown, "not stated in the ask; not assumed", required=False))
    blocked = any(c["required"] and c["status"] != "pass" for c in checks)
    return {"schema_version": SCHEMA, "intent_state": "blocked" if blocked else "conforms",
            "person_checks": [c["code"] for c in checks if c["status"] == "needs_review"],
            "checks": checks}
