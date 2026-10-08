"""Bounded feature evidence from exported triangles, independent of CAD reports.

Sampling verifies named points, not every surface or print suitability. These
checks supplement (and require) the topology/intersection gates in the caller.
"""
import math
from collections import defaultdict
from fractions import Fraction
from .intersections import rational, point_inside, normal, dot, sub, cross, inside

GENERATOR_CODES = ('generator_contract', 'generator_features', 'generator_volume',
                   'generator_cross_sections')
VOLUME_RELATIVE_TOLERANCE = 0.002


def _finding(code, status, actual=None, expected=None, method='', evidence=None):
    return dict(code=code, status=status, actual=actual, expected=expected,
                method=method, evidence=evidence or [], required=True,
                next_action='none' if status == 'pass' else
                'Revise the generator or exported mesh and rerun; retain this evidence.')


def _section_loops(exact, z, budget_check):
    """Intersect triangles with a plane without welding or geometry libraries.

    Coplanar facets and non-simple section graphs are unresolved, never repaired.
    """
    graph, segments = defaultdict(set), set()
    for triangle in exact:
        budget_check()
        offsets = [p[2] - z for p in triangle]
        if all(v == 0 for v in offsets):
            return None, 'coplanar triangle at section plane'
        points = {p[:2] for p, dz in zip(triangle, offsets) if dz == 0}
        for i in range(3):
            a, b = triangle[i], triangle[(i+1) % 3]
            da, db = offsets[i], offsets[(i+1) % 3]
            if da * db < 0:
                points.add(tuple(a[k] + (b[k]-a[k]) * da / (da-db) for k in (0,1)))
        if len(points) < 2:
            continue
        if len(points) != 2:
            return None, 'non-segment triangle intersection'
        segment = frozenset(points)
        if segment in segments:
            return None, 'duplicate section segment'
        segments.add(segment)
        a,b = tuple(points)
        graph[a].add(b); graph[b].add(a)
    if any(len(neighbors) != 2 for neighbors in graph.values()):
        return None, 'section graph is not a union of closed degree-two loops'
    unseen, loops = set(graph), []
    while unseen:
        budget_check()
        start = min(unseen)
        previous, current, loop = None, start, []
        while True:
            budget_check()
            loop.append(current); unseen.remove(current)
            candidates = graph[current] - ({previous} if previous is not None else set())
            following = min(candidates)
            if following == start:
                break
            if following not in unseen:
                return None, 'section traversal revisited a vertex'
            previous, current = current, following
        loops.append(loop)
    return loops, None


def _cross_sections(exact, w, d, h, r, budget_check):
    # Float32 STL rounding is <8e-6 mm within the 100 mm parameter range.
    # Use a conservative dimension-scaled allowance, separate from mesh sag.
    float_margin = max(w,d,h) * 2e-7
    center_tol, diameter_tol = .05 + float_margin, .1 + 2 * float_margin
    evidence = []
    for z in (Fraction(h) / 4, Fraction(h) * 3 / 8):
        loops, error = _section_loops(exact, z, budget_check)
        item = {'z_mm':float(z), 'status':'unknown' if error else 'pass'}
        if error:
            item['reason'] = error
            evidence.append(item)
            continue
        item['loop_count'] = len(loops)
        if len(loops) != 2:
            item.update(status='fail', reason='expected one outer loop and one hole loop')
            evidence.append(item)
            continue
        def area(loop):
            return abs(sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(loop,loop[1:]+loop[:1])))
        outer, hole = sorted(loops, key=area, reverse=True)
        lo = [float(min(p[k] for p in outer)) for k in (0,1)]
        hi = [float(max(p[k] for p in outer)) for k in (0,1)]
        outer_ok = all(abs(a-b) <= float_margin for a,b in zip(lo+hi,[0,0,w,d]))
        # Bounds alone cannot establish the rectangular outer contour.
        for a,b in zip(outer,outer[1:]+outer[:1]):
            budget_check()
            if not any(abs(float(a[k])-bound) <= float_margin and
                       abs(float(b[k])-bound) <= float_margin
                       for k,bound in ((0,0),(0,w),(1,0),(1,d))):
                outer_ok = False
        hole_lo = [float(min(p[k] for p in hole)) for k in (0,1)]
        hole_hi = [float(max(p[k] for p in hole)) for k in (0,1)]
        center = [(a+b)/2 for a,b in zip(hole_lo,hole_hi)]
        diameters = [b-a for a,b in zip(hole_lo,hole_hi)]
        radial_errors = []
        # Test segment interiors too: every chord's nearest point to the
        # measured center and endpoints must lie in the allowed circular band.
        for a,b in zip(hole,hole[1:]+hole[:1]):
            budget_check()
            a,b = tuple(map(float,a)),tuple(map(float,b))
            delta = [b[k]-a[k] for k in (0,1)]
            length2 = sum(v*v for v in delta)
            t = max(0,min(1,sum((center[k]-a[k])*delta[k] for k in (0,1))/length2))
            nearest = [a[k]+t*delta[k] for k in (0,1)]
            radial_errors.extend(abs(math.hypot(p[0]-center[0],p[1]-center[1])-r)
                                 for p in (a,b,nearest))
        circle_error = max(radial_errors)
        center_ok = all(abs(a-b) <= center_tol for a,b in zip(center,[w/4,d/2]))
        diameter_ok = all(abs(v-2*r) <= diameter_tol for v in diameters)
        circle_ok = circle_error <= .05 + float_margin
        item.update(status='pass' if outer_ok and center_ok and diameter_ok and circle_ok else 'fail',
                    outer_bounds_mm=[lo,hi], outer_rectangle=outer_ok,
                    hole_center_mm=center, hole_diameters_mm=diameters,
                    max_radial_error_mm=circle_error,
                    center_matches=center_ok, diameters_match=diameter_ok,
                    circular_band_matches=circle_ok)
        evidence.append(item)
    status = ('fail' if any(e['status']=='fail' for e in evidence) else
              'unknown' if any(e['status']=='unknown' for e in evidence) else 'pass')
    return _finding('generator_cross_sections',status,evidence,
        {'section_z_mm':[h/4,3*h/8], 'loops_per_section':2,
         'hole_center_mm':[w/4,d/2], 'hole_diameter_mm':2*r,
         'center_tolerance_mm':center_tol, 'diameter_tolerance_mm':diameter_tol,
         'radial_tolerance_mm':.05+float_margin},
        'exact rational triangle-plane segments and degree-two closed loops; '
        'rectangular outer boundary and one circular-band inner boundary; '
        'center from inner-loop bounding-box midpoint; 0.05 mm linear '
        'tessellation allowance plus bounded float32 roundoff; checks only '
        'two declared sections, not arbitrary features or all surfaces',evidence)


def check_generator(triangles, request, budget_check=lambda: None):
    """Check the named generator contract; unresolved predicates fail closed.

    The caller must enforce its whole-validation deadline through budget_check.
    No generator identifier means the generic, non-parametric mesh profile.
    """
    generator = request.get('generator_id')
    if generator is None:
        return []
    if generator != 'freecad-stepped-block':
        return [_finding(code, 'unknown', generator,
                         'freecad-stepped-block', 'unsupported generator contract')
                for code in GENERATOR_CODES]
    params = request.get('parameters')
    keys = ('width_mm', 'depth_mm', 'height_mm')
    valid = (isinstance(params, dict) and set(params) == set(keys) and
             all(type(params[k]) in (int, float) and 5 <= params[k] <= 100
                 and math.isfinite(params[k]) for k in keys))
    checks = [_finding('generator_contract', 'pass' if valid else 'fail', params,
                       'exact width_mm/depth_mm/height_mm keys, finite numbers in [5,100]',
                       'independent bounded parameter contract')]
    if not valid:
        return checks + [_finding(code, 'unknown', method='invalid generator parameters')
                         for code in GENERATOR_CODES[1:]]
    w, d, h = (params[k] for k in keys)
    r = min(w / 8, d / 6)
    expected = .75 * w * d * h - math.pi * r * r * h / 2
    exact = []
    for triangle in triangles:
        budget_check()
        exact.append(rational(triangle))
    checks.append(_cross_sections(exact, w, d, h, r, budget_check))
    volume_six = Fraction(0)
    for t in exact:
        budget_check()
        volume_six += dot(t[0], cross(t[1], t[2]))
    actual = float(volume_six / 6)
    checks.append(_finding('generator_volume',
        'pass' if abs(actual - expected) <= expected * VOLUME_RELATIVE_TOLERANCE else 'fail',
        actual, {'volume_mm3': expected, 'relative_tolerance': VOLUME_RELATIVE_TOLERANCE},
        'exact rational signed tetrahedron sum of exported triangles versus '
        '0.75*w*d*h - pi*min(w/8,d/6)^2*h/2; fixed 0.2% tolerance covers '
        'the bounded generator tessellation (0.05 mm linear, 0.25 rad angular); '
        'not a generic geometric error guarantee'))
    cx, cy = w / 4, d / 2
    probes = []
    for zlabel, z in (('lower', h / 8), ('upper', 3 * h / 8)):
        probes.append(('hole_center_' + zlabel, (cx, cy, z), False))
        for axis, dx, dy in (('east', 1, 0), ('west', -1, 0),
                             ('north', 0, 1), ('south', 0, -1)):
            probes.append(('hole_void_' + axis + '_' + zlabel,
                           (cx + dx * .6 * r, cy + dy * .6 * r, z), False))
            probes.append(('hole_wall_' + axis + '_' + zlabel,
                           (cx + dx * 1.3 * r, cy + dy * 1.3 * r, z), True))
    probes.extend([
        ('raised_right', (.75 * w, .5 * d, .75 * h), True),
        ('lower_left_open', (.25 * w, .2 * d, .75 * h), False),
    ])
    for x in (.05 * w, .95 * w):
        for y in (.05 * d, .95 * d):
            probes.append(('base_corner', (x, y, .25 * h), True))
    evidence = []
    for label, point, wanted in probes:
        budget_check()
        p = tuple(Fraction(v) for v in point)
        boundary = False
        for triangle in exact:
            budget_check()
            n = normal(triangle)
            if n == (0, 0, 0) or (dot(n, sub(p, triangle[0])) == 0 and inside(p, triangle, n)):
                boundary = True
                break
        value = None if boundary else point_inside(p, exact, budget_check)
        evidence.append(dict(probe=label, point_mm=list(point), expected_solid=wanted,
                             actual_solid=value, on_surface_or_degenerate=boundary))
    failed = any(e['actual_solid'] is not None and e['actual_solid'] != e['expected_solid'] for e in evidence)
    unknown = any(e['actual_solid'] is None for e in evidence)
    checks.append(_finding('generator_features', 'fail' if failed else 'unknown' if unknown else 'pass',
        {'failed_probes': sum(e['actual_solid'] is not None and e['actual_solid'] != e['expected_solid'] for e in evidence),
         'unresolved_probes': sum(e['actual_solid'] is None for e in evidence)},
        'all declared hole, step and base sample points match',
        'independent exact rational ray parity with edge-degeneracy retries and '
        'explicit surface-point rejection; finite samples cannot certify all surfaces '
        'or visual completeness; topology and intersection gates must also pass', evidence))
    return checks
