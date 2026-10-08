"""Exact predicates over the actual finite IEEE STL coordinates.

No epsilon welding or repair. Fractions represent parsed floats exactly. AABB
filtering is conservative and exact comparisons decide contacts/overlaps. This
bounded reference implementation favors correctness over large-mesh throughput.
"""
from fractions import Fraction


def sub(a, b): return tuple(x-y for x, y in zip(a, b))
def add(a, b): return tuple(x+y for x, y in zip(a, b))
def mul(a, k): return tuple(x*k for x in a)
def dot(a, b): return sum(x*y for x, y in zip(a, b))
def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def rational(t): return tuple(tuple(Fraction(x) for x in v) for v in t)
def normal(t): return cross(sub(t[1], t[0]), sub(t[2], t[0]))
def orient(a, b, p): return (b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])
def project(p, axis): return tuple(p[k] for k in range(3) if k != axis)


def inside(p, t, n):
    axis = max(range(3), key=lambda i: abs(n[i]))
    q = project(p, axis)
    tri = [project(v, axis) for v in t]
    signs = [orient(tri[i], tri[(i+1)%3], q) for i in range(3)]
    return all(v >= 0 for v in signs) or all(v <= 0 for v in signs)


def on_segment(p, a, b):
    return cross(sub(p, a), sub(b, a)) == (0, 0, 0) and dot(sub(p, a), sub(p, b)) <= 0


def intersection_points(a, b):
    """Vertices spanning the convex intersection of two nondegenerate triangles."""
    na, nb = normal(a), normal(b)
    distances = [dot(nb, sub(p, b[0])) for p in a]
    points = set()
    if all(d == 0 for d in distances):
        axis = max(range(3), key=lambda i: abs(nb[i]))
        for p in a:
            if inside(p, b, nb): points.add(p)
        for p in b:
            if inside(p, a, na): points.add(p)
        for i in range(3):
            p, q = a[i], a[(i+1)%3]
            pp, qq = project(p, axis), project(q, axis)
            for j in range(3):
                r, s = b[j], b[(j+1)%3]
                rr, ss = project(r, axis), project(s, axis)
                d1, d2 = orient(rr, ss, pp), orient(rr, ss, qq)
                e1, e2 = orient(pp, qq, rr), orient(pp, qq, ss)
                if d1*d2 <= 0 and e1*e2 <= 0 and d1 != d2:
                    points.add(add(p, mul(sub(q, p), d1/(d1-d2))))
        return points
    for t, other, n in ((a, b, nb), (b, a, na)):
        for i in range(3):
            p, q = t[i], t[(i+1)%3]
            dp, dq = dot(n, sub(p, other[0])), dot(n, sub(q, other[0]))
            if dp == 0 and inside(p, other, n): points.add(p)
            if dp*dq < 0:
                x = add(p, mul(sub(q, p), dp/(dp-dq)))
                if inside(x, other, n): points.add(x)
    return points


def improper_intersection(a, b):
    points = intersection_points(a, b)
    shared = set(a) & set(b)
    if len(shared) == 2:
        p, q = tuple(shared)
        return any(not on_segment(x, p, q) for x in points)
    if len(shared) == 1:
        return any(x not in shared for x in points)
    return bool(points)


def point_inside(point, shell, budget_check=lambda: None):
    """Exact parity with deterministic retries for a ray hitting an edge/vertex.

    Return None on unresolved degeneracy, never guess an interior result.
    Caller checks intersections first, so the point must not be on the shell.
    """
    for direction in ((1, 17, 113), (19, 1, 71), (37, 101, 1), (43, 59, 97)):
        count, ambiguous = 0, False
        for t in shell:
            budget_check()
            n = normal(t)
            denom = dot(n, direction)
            if denom == 0: continue
            distance = dot(n, sub(t[0], point))/denom
            if distance <= 0: continue
            p = add(point, mul(direction, distance))
            if not inside(p, t, n): continue
            if any(on_segment(p, t[i], t[(i+1)%3]) for i in range(3)):
                ambiguous = True
                break
            count += 1
        if not ambiguous: return bool(count % 2)
    return None
