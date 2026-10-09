"""Printability facts for any STL: a character, a figure or a downloaded model.

This answers "will it print and survive?", never "does it look right?". Likeness
and style are always a person check. Each check reports what it measured and
how; a sampled search that finds nothing says `no_findings`, not `pass`.

Assumptions are explicit in the report: +z is up, the lowest point sits on the
bed, and units are mm. Pure Python, no third-party packages.
"""
import hashlib
import math
from pathlib import Path
from .common import ForgeError
from .validation.export_checks import MeshError, parse_stl

SCHEMA = "printability.v1"
MAX_BYTES = 64 * 1024 * 1024
MAX_TRIANGLES = 300000
BED_TOL_MM = 0.05  # A vertex this close to the lowest z touches the bed.
MIN_BASE_MM2 = 10.0  # Less than this on the bed is a pinpoint contact, not a base.
DEFAULT_MIN_WALL_MM = 0.8  # Two lines of a 0.4 mm FDM nozzle; set it for the real printer.
DEFAULT_OVERHANG_DEG = 45.0
DEFAULT_SAMPLES = 600
PERSON_CHECKS = [
    "Likeness and look: compare the views with what you asked for",
    "Print settings: material, layer height, supports and orientation in the slicer",
    "A test print",
]


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def unit_normal(t):
    n = cross(sub(t[1], t[0]), sub(t[2], t[0]))
    length = math.sqrt(dot(n, n))
    return (n[0] / length, n[1] / length, n[2] / length) if length > 0 else None, length / 2


def topology(triangles):
    """Closed, consistently oriented shells from exact vertex identity."""
    directed, undirected = {}, {}
    parent = list(range(len(triangles)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    first_face = {}
    for index, t in enumerate(triangles):
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            directed[(a, b)] = directed.get((a, b), 0) + 1
            key = (a, b) if a < b else (b, a)
            undirected[key] = undirected.get(key, 0) + 1
            if key in first_face:
                parent[find(index)] = find(first_face[key])
            else:
                first_face[key] = index
    boundary = sum(1 for n in undirected.values() if n == 1)
    nonmanifold = sum(1 for n in undirected.values() if n > 2)
    flipped = sum(1 for (a, b), n in directed.items() if n > 1 or (b, a) not in directed)
    shells = {}
    for index, t in enumerate(triangles):
        root = find(index)
        # Signed volume of the tetrahedron to the origin; positive for an outward-facing shell.
        shells[root] = shells.get(root, 0.0) + dot(t[0], cross(t[1], t[2])) / 6
    return {"boundary_edges": boundary, "nonmanifold_edges": nonmanifold, "inconsistent_edges": flipped,
            "shell_volumes_mm3": sorted(shells.values(), reverse=True)}


def mass_centre(triangles):
    volume, centre = 0.0, [0.0, 0.0, 0.0]
    for a, b, c in triangles:
        v = dot(a, cross(b, c)) / 6
        volume += v
        for k in range(3):
            centre[k] += v * (a[k] + b[k] + c[k]) / 4
    return volume, [x / volume for x in centre] if volume else None


def hull(points):
    """Convex hull in xy, counter-clockwise (monotone chain)."""
    points = sorted(set(points))
    if len(points) < 3:
        return points
    turn = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in points:
        while len(lower) >= 2 and turn(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(points):
        while len(upper) >= 2 and turn(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def inside_margin(polygon, point):
    """Signed distance from point to the nearest edge of a CCW convex polygon; negative is outside."""
    if len(polygon) < 3:
        return None
    margin = math.inf
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        edge = (b[0] - a[0], b[1] - a[1])
        length = math.hypot(*edge)
        margin = min(margin, (edge[0] * (point[1] - a[1]) - edge[1] * (point[0] - a[0])) / length)
    return margin


class Grid:
    """Uniform grid of triangle indices for ray casting."""

    def __init__(self, triangles, low, high):
        self.triangles, self.low = triangles, low
        span = max(high[k] - low[k] for k in range(3)) or 1.0
        self.cell = max(span / max(8, round(len(triangles) ** (1 / 3) * 2)), 1e-3)
        self.size = [max(1, math.ceil((high[k] - low[k]) / self.cell) + 1) for k in range(3)]
        self.cells = {}
        for index, t in enumerate(triangles):
            lo = [self.index(min(p[k] for p in t), k) for k in range(3)]
            hi = [self.index(max(p[k] for p in t), k) for k in range(3)]
            for i in range(lo[0], hi[0] + 1):
                for j in range(lo[1], hi[1] + 1):
                    for m in range(lo[2], hi[2] + 1):
                        self.cells.setdefault((i, j, m), []).append(index)

    def index(self, value, k):
        return min(self.size[k] - 1, max(0, int((value - self.low[k]) / self.cell)))

    def first_hit(self, origin, direction, skip):
        """Distance to the nearest triangle along the ray (Amanatides-Woo walk), or None."""
        cell = [self.index(origin[k], k) for k in range(3)]
        step, t_max, t_delta = [0, 0, 0], [math.inf] * 3, [math.inf] * 3
        for k in range(3):
            if direction[k] > 0:
                step[k] = 1
                t_max[k] = (self.low[k] + (cell[k] + 1) * self.cell - origin[k]) / direction[k]
                t_delta[k] = self.cell / direction[k]
            elif direction[k] < 0:
                step[k] = -1
                t_max[k] = (self.low[k] + cell[k] * self.cell - origin[k]) / direction[k]
                t_delta[k] = -self.cell / direction[k]
        best, seen = None, {skip}
        while all(0 <= cell[k] < self.size[k] for k in range(3)):
            for index in self.cells.get(tuple(cell), ()):
                if index in seen:
                    continue
                seen.add(index)
                hit = ray_triangle(origin, direction, self.triangles[index])
                if hit is not None and (best is None or hit < best):
                    best = hit
            k = min(range(3), key=lambda axis: t_max[axis])
            if best is not None and best <= t_max[k]:
                return best
            cell[k] += step[k]
            t_max[k] += t_delta[k]
        return best


def ray_triangle(origin, direction, t):
    """Moller-Trumbore; distance along a unit direction, or None."""
    e1, e2 = sub(t[1], t[0]), sub(t[2], t[0])
    p = cross(direction, e2)
    det = dot(e1, p)
    if abs(det) < 1e-12:
        return None
    s = sub(origin, t[0])
    u = dot(s, p) / det
    if u < 0 or u > 1:
        return None
    q = cross(s, e1)
    v = dot(direction, q) / det
    if v < 0 or u + v > 1:
        return None
    distance = dot(e2, q) / det
    return distance if distance > 1e-6 else None


def thickness_samples(triangles, normals, areas, low, high, count):
    """Local thickness at area-stratified surface points: distance inward to the opposite surface."""
    grid = Grid(triangles, low, high)
    total = sum(areas)
    order, results, running, k = [], [], 0.0, 0
    count = min(count, len(triangles))
    for index, area in enumerate(areas):
        running += area
        while k < count and (k + 0.5) / count * total <= running:
            order.append(index)
            k += 1
    for index in order:
        n = normals[index]
        if n is None:
            continue
        t = triangles[index]
        centre = tuple(sum(p[j] for p in t) / 3 for j in range(3))
        inward = (-n[0], -n[1], -n[2])
        start = (centre[0] + inward[0] * 1e-5, centre[1] + inward[1] * 1e-5, centre[2] + inward[2] * 1e-5)
        results.append((grid.first_hit(start, inward, index), centre))
    return results


def check(code, status, actual=None, expected=None, method=""):
    return {"code": code, "status": status, "actual": actual, "expected": expected, "method": method}


def assess(path, *, bed_mm=None, min_wall_mm=DEFAULT_MIN_WALL_MM, overhang_deg=DEFAULT_OVERHANG_DEG,
           samples=DEFAULT_SAMPLES):
    path = Path(path)
    with path.open("rb") as handle:
        data = handle.read(MAX_BYTES + 1)
    try:
        triangles, encoding = parse_stl(data, max_bytes=MAX_BYTES, max_triangles=MAX_TRIANGLES)
    except MeshError as exc:
        raise ForgeError(f"STL could not be read: {exc}. Decimate meshes above {MAX_TRIANGLES} triangles.",
                         2, exc.code) from exc
    checks, findings = [], []
    vertices = [p for t in triangles for p in t]
    low = [min(p[k] for p in vertices) for k in range(3)]
    high = [max(p[k] for p in vertices) for k in range(3)]
    size = [high[k] - low[k] for k in range(3)]
    facets = [unit_normal(t) for t in triangles]
    normals, areas = [f[0] for f in facets], [f[1] for f in facets]

    top = topology(triangles)
    closed = top["boundary_edges"] == 0 and top["nonmanifold_edges"] == 0
    checks.append(check("closed_mesh", "pass" if closed else "fail",
                        {k: top[k] for k in ("boundary_edges", "nonmanifold_edges")}, 0,
                        "edge incidence by exact vertex identity"))
    oriented = closed and top["inconsistent_edges"] == 0
    checks.append(check("orientation", "pass" if oriented else ("fail" if closed else "unknown"),
                        top["inconsistent_edges"], 0, "each edge used once in each direction"))
    shells = top["shell_volumes_mm3"]
    sound = oriented and all(v > 0 for v in shells)
    checks.append(check("shells", "pass" if sound and len(shells) == 1 else
                        ("needs_review" if sound else ("fail" if oriented else "unknown")),
                        {"count": len(shells), "volumes_mm3": shells[:10]}, "one shell with positive volume",
                        "connected faces; signed volume per shell"))
    if sound and len(shells) > 1:
        findings.append(f"{len(shells)} separate shells: loose parts print separately or fall over")
    checks.append(check("self_intersections", "unknown", None, None,
                        "not checked here; the slicer shows overlapping or inverted regions"))

    if bed_mm:
        fits = all(a <= b for a, b in zip(size, bed_mm)) or all(a <= b for a, b in zip((size[1], size[0], size[2]), bed_mm))
        checks.append(check("fits_bed", "pass" if fits else "fail", size, bed_mm, "bounding box, upright, may turn 90 degrees"))
        if not fits:
            findings.append("too big for the bed in this orientation")
    else:
        checks.append(check("fits_bed", "unknown", size, None, "no bed size given"))

    on_bed = [i for i, t in enumerate(triangles)
              if all(p[2] <= low[2] + BED_TOL_MM for p in t) and normals[i] and normals[i][2] < -0.999]
    base_area = sum(areas[i] for i in on_bed)
    contact = hull([(p[0], p[1]) for p in vertices if p[2] <= low[2] + BED_TOL_MM])
    base = "fail" if base_area == 0 else ("pass" if base_area >= MIN_BASE_MM2 else "needs_review")
    checks.append(check("flat_base", base, {"area_mm2": round(base_area, 3)}, f">= {MIN_BASE_MM2:g} mm2",
                        "downward faces within 0.05 mm of the lowest point"))
    if base == "fail":
        findings.append("no flat face on the bed: it balances on a point or edge")
    elif base == "needs_review":
        findings.append(f"only {base_area:.1f} mm2 touches the bed: it may not stick or stand")

    volume, centre = mass_centre(triangles) if sound else (None, None)
    if centre is None:
        checks.append(check("stands_up", "unknown", None, None, "needs a closed, oriented mesh"))
    else:
        margin = inside_margin(contact, (centre[0], centre[1]))
        height = centre[2] - low[2]
        tilt = math.degrees(math.atan2(margin, height)) if margin is not None and margin > 0 and height > 0 else 0.0
        status = "unknown" if margin is None else ("fail" if margin <= 0 else ("needs_review" if tilt < 5 else "pass"))
        checks.append(check("stands_up", status,
                            {"centre_of_mass_mm": [round(c - l, 3) for c, l in zip(centre, low)],
                             "margin_mm": None if margin is None else round(margin, 3), "tip_angle_deg": round(tilt, 2)},
                            "centre of mass over the base, at least 5 degrees from tipping",
                            "uniform density; convex footprint of the points on the bed"))
        if status == "fail":
            findings.append("the centre of mass is outside the base: it falls over without a stand")
        elif status == "needs_review":
            findings.append(f"it tips over if tilted about {tilt:.1f} degrees")

    limit = -math.cos(math.radians(overhang_deg))
    hanging = [i for i, n in enumerate(normals) if n and n[2] < limit
               and max(p[2] for p in triangles[i]) > low[2] + BED_TOL_MM]  # Only faces lying on the bed are supported.
    hang_area = sum(areas[i] for i in hanging)
    surface = sum(areas)
    checks.append(check("overhangs", "needs_review" if hang_area > 0 else "pass",
                        {"area_mm2": round(hang_area, 2), "share_of_surface": round(hang_area / surface, 4) if surface else None,
                         "z_range_mm": [round(min(min(p[2] for p in triangles[i]) for i in hanging) - low[2], 2),
                                        round(max(max(p[2] for p in triangles[i]) for i in hanging) - low[2], 2)] if hanging else None},
                        f"faces more than {overhang_deg:g} degrees past vertical, off the bed",
                        "face normals; supports or a different orientation may be needed"))
    if hang_area > 0:
        findings.append(f"{hang_area:.0f} mm2 of overhang needs supports or a different orientation")

    if not sound:
        checks.append(check("thin_features", "unknown", None, None, "needs a closed, oriented mesh"))
    else:
        found = thickness_samples(triangles, normals, areas, low, high, samples)
        thin = sorted(((d, c) for d, c in found if d is not None and d < min_wall_mm), key=lambda x: x[0])
        misses = sum(1 for d, _ in found if d is None)
        measured = [d for d, _ in found if d is not None]
        actual = {"samples": len(found), "unresolved": misses, "min_mm": round(min(measured), 3) if measured else None,
                  "thin_samples": len(thin),
                  "thinnest_at_mm": [[round(v - l, 2) for v, l in zip(c, low)] for _, c in thin[:5]]}
        status = "needs_review" if thin else ("unknown" if misses > len(found) // 10 else "no_findings")
        checks.append(check("thin_features", status, actual, f">= {min_wall_mm} mm",
                            "inward ray from area-stratified surface samples; a sampled search can miss small spots"))
        if thin:
            findings.append(f"{len(thin)} of {len(found)} samples are thinner than {min_wall_mm} mm "
                            f"(thinnest {thin[0][0]:.2f} mm): these parts may break or not print")

    checks.append(check("hollow_and_drain", "unknown", None, None,
                        "for resin prints: hollowing and drain holes are not checked"))
    blocked = any(c["status"] == "fail" for c in checks)
    return {"schema_version": SCHEMA,
            "file": {"name": path.name, "sha256": hashlib.sha256(data).hexdigest(), "triangles": len(triangles),
                     "encoding": encoding},
            "assumptions": {"units": "mm", "up": "+z", "on_bed": "lowest point", "min_base_mm2": MIN_BASE_MM2,
                            "min_wall_mm": min_wall_mm,
                            "overhang_deg": overhang_deg, "bed_mm": bed_mm},
            "size_mm": [round(s, 3) for s in size], "volume_mm3": round(volume, 3) if volume else None,
            "state": "blocked" if blocked else "needs_review", "findings": findings,
            "checks": checks, "person_checks": PERSON_CHECKS, "print_state": "needs_review"}
