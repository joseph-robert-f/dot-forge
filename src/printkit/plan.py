"""Strict v2 build plan: a declarative FreeCAD feature tree, never code.

Each step names one operation from a fixed vocabulary and refers only to
earlier steps by id. The FreeCAD helper maps each op name to one reviewed
function; no request value becomes an import, attribute name or expression.
A plan is bound to one confirmed intent by its canonical hash.
"""
import math
from .common import ForgeError, canonical_hash
from .intent import AXES, ID, exact_fields, number

SCHEMA = "plan.v1"
MAX_STEPS = 128
MAX_POINTS = 256
MAX_COPIES = 256
LENGTH = (0, 500)
COORD = (-1000, 1000)
PLANES = ("xy", "xz", "yz")
EDGES = ("all", "parallel_x", "parallel_y", "parallel_z")
# op -> (required fields, optional fields, fields that reference earlier steps)
OPS = {
    "box": ({"size_mm"}, {"at_mm"}, ()),
    "cylinder": ({"radius_mm", "height_mm"}, {"at_mm", "axis"}, ()),
    "cone": ({"radius1_mm", "radius2_mm", "height_mm"}, {"at_mm", "axis"}, ()),
    "sphere": ({"radius_mm"}, {"at_mm"}, ()),
    "extrude": ({"plane", "points", "height_mm"}, {"offset_mm"}, ()),
    "revolve": ({"points"}, {"angle_deg", "at_mm"}, ()),
    "union": ({"of"}, set(), ("of",)),
    "intersect": ({"of"}, set(), ("of",)),
    "cut": ({"from", "tools"}, set(), ("from", "tools")),
    "translate": ({"target", "by_mm"}, set(), ("target",)),
    "rotate": ({"target", "axis", "angle_deg"}, {"about_mm"}, ("target",)),
    "mirror": ({"target", "plane"}, {"through_mm"}, ("target",)),
    "linear_pattern": ({"target", "step_mm", "count"}, set(), ("target",)),
    "polar_pattern": ({"target", "axis", "count"}, {"angle_deg", "about_mm"}, ("target",)),
    "fillet": ({"target", "radius_mm", "edges"}, set(), ("target",)),
    "chamfer": ({"target", "size_mm", "edges"}, set(), ("target",)),
}


def vector(value, name, low, high, size=3):
    if not isinstance(value, list) or len(value) != size:
        raise ForgeError(f"{name} must hold {size} numbers")
    for index, item in enumerate(value):
        number(item, f"{name}[{index}]", low, high)
    return value


def length(value, name):
    return number(value, name, *LENGTH, low_open=True)


def polygon(points, name, *, radial=False):
    """Closed simple polygon; the last point joins the first."""
    if not isinstance(points, list) or not 3 <= len(points) <= MAX_POINTS:
        raise ForgeError(f"{name} must hold 3 to {MAX_POINTS} points")
    for index, point in enumerate(points):
        vector(point, f"{name}[{index}]", *COORD, size=2)
        if radial and point[0] < 0:
            raise ForgeError(f"{name}[{index}] radius must not be negative for a revolve profile")
    edges = list(zip(points, points[1:] + points[:1]))
    if any(math.dist(a, b) < 1e-6 for a, b in edges):
        raise ForgeError(f"{name} has a zero-length edge")
    area = sum(a[0] * b[1] - b[0] * a[1] for a, b in edges) / 2
    if abs(area) < 1e-6:
        raise ForgeError(f"{name} encloses no area")

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    for i, (a, b) in enumerate(edges):
        for j in range(i + 1, len(edges)):
            if j == i + 1 or (i == 0 and j == len(edges) - 1):
                continue
            c, d = edges[j]
            if (cross(a, b, c) * cross(a, b, d) < 0) and (cross(c, d, a) * cross(c, d, b) < 0):
                raise ForgeError(f"{name} edges {i} and {j} cross; the profile must be a simple polygon")
    return points


def check_step(step, index, known):
    name = f"steps[{index}]"
    if not isinstance(step, dict) or step.get("op") not in OPS:
        raise ForgeError(f"{name}.op must be one of {sorted(OPS)}")
    required, optional, refs = OPS[step["op"]]
    exact_fields(step, required | {"id", "op"}, optional, name)
    if not isinstance(step["id"], str) or not ID.match(step["id"]):
        raise ForgeError(f"{name}.id must match {ID.pattern}")
    if step["id"] in known:
        raise ForgeError(f"{name}.id {step['id']!r} is already used")
    used = []
    for field in refs:
        value = step[field]
        many = field in ("of", "tools")
        items = value if many else [value]
        if many and (not isinstance(value, list) or not value or len(value) > 64
                     or (field == "of" and len(value) < 2)):
            raise ForgeError(f"{name}.{field} must list {'2' if field == 'of' else '1'} to 64 earlier step ids")
        for item in items:
            if item not in known:
                raise ForgeError(f"{name}.{field} refers to {item!r}, which is not an earlier step")
            used.append(item)
    if len(used) != len(set(used)):
        raise ForgeError(f"{name} uses the same step more than once")
    op = step["op"]
    if "at_mm" in step:
        vector(step["at_mm"], f"{name}.at_mm", *COORD)
    if "axis" in step and step["axis"] not in AXES:
        raise ForgeError(f"{name}.axis must be one of {AXES}")
    if op == "box":
        for i, value in enumerate(vector(step["size_mm"], f"{name}.size_mm", *LENGTH)):
            length(value, f"{name}.size_mm[{i}]")
    for field in ("radius_mm", "height_mm", "radius1_mm"):
        if field in step:
            length(step[field], f"{name}.{field}")
    if op == "cone":
        number(step["radius2_mm"], f"{name}.radius2_mm", *LENGTH)
        if step["radius1_mm"] == step["radius2_mm"]:
            raise ForgeError(f"{name} has equal cone radii; use a cylinder")
    if op == "extrude":
        if step["plane"] not in PLANES:
            raise ForgeError(f"{name}.plane must be one of {PLANES}")
        polygon(step["points"], f"{name}.points")
        if "offset_mm" in step:
            number(step["offset_mm"], f"{name}.offset_mm", *COORD)
    if op == "revolve":
        polygon(step["points"], f"{name}.points", radial=True)
    if "angle_deg" in step:
        number(step["angle_deg"], f"{name}.angle_deg", -360, 360)
        if step["angle_deg"] == 0:
            raise ForgeError(f"{name}.angle_deg must not be zero")
    if op == "translate":
        vector(step["by_mm"], f"{name}.by_mm", *COORD)
    if "about_mm" in step:
        vector(step["about_mm"], f"{name}.about_mm", *COORD)
    if op == "mirror":
        if step["plane"] not in PLANES:
            raise ForgeError(f"{name}.plane must be one of {PLANES}")
        if "through_mm" in step:
            number(step["through_mm"], f"{name}.through_mm", *COORD)
    copies = 0
    if op in ("linear_pattern", "polar_pattern"):
        if type(step["count"]) is not int or not 2 <= step["count"] <= 64:
            raise ForgeError(f"{name}.count must be an integer from 2 to 64")
        copies = step["count"]
        if op == "linear_pattern":
            vector(step["step_mm"], f"{name}.step_mm", *COORD)
            if all(v == 0 for v in step["step_mm"]):
                raise ForgeError(f"{name}.step_mm must not be zero")
    if op in ("fillet", "chamfer"):
        length(step["radius_mm" if op == "fillet" else "size_mm"], f"{name}.size")
        if step["edges"] not in EDGES:
            raise ForgeError(f"{name}.edges must be one of {EDGES}")
    return used, copies


def check_plan(plan, intent=None):
    """Validate a plan; with an intent, also check that it is bound to that intent."""
    exact_fields(plan, {"schema_version", "units", "intent_sha256", "steps", "result"}, {"notes"}, "plan")
    if plan["schema_version"] != SCHEMA:
        raise ForgeError(f"Unsupported plan schema_version; expected {SCHEMA!r}")
    if plan["units"] != "mm":
        raise ForgeError("Plan units must be mm")
    if not isinstance(plan["intent_sha256"], str) or len(plan["intent_sha256"]) != 64:
        raise ForgeError("intent_sha256 must be the canonical hash of the confirmed intent")
    if intent is not None and plan["intent_sha256"] != canonical_hash(intent):
        raise ForgeError("Plan is bound to a different intent; regenerate the plan for this intent", 2, "intent_mismatch")
    if "notes" in plan and (not isinstance(plan["notes"], str) or len(plan["notes"]) > 2000):
        raise ForgeError("notes must be text of at most 2000 characters")
    steps = plan["steps"]
    if not isinstance(steps, list) or not 1 <= len(steps) <= MAX_STEPS:
        raise ForgeError(f"steps must hold 1 to {MAX_STEPS} operations")
    known, uses, copies = [], {}, 0
    for index, step in enumerate(steps):
        used, count = check_step(step, index, known)
        uses[step["id"]] = used
        copies += count
        known.append(step["id"])
    if copies > MAX_COPIES:
        raise ForgeError(f"Patterns create more than {MAX_COPIES} copies in total")
    if plan["result"] not in known:
        raise ForgeError("result must name a step")
    reachable, pending = set(), [plan["result"]]
    while pending:
        current = pending.pop()
        if current not in reachable:
            reachable.add(current)
            pending.extend(uses[current])
    unused = [s for s in known if s not in reachable]
    return {"schema_version": SCHEMA, "status": "pass", "plan_sha256": canonical_hash(plan),
            "intent_sha256": plan["intent_sha256"], "step_count": len(steps), "result": plan["result"],
            "warnings": [f"Step {s!r} does not contribute to the result" for s in unused]}
