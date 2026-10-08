"""Independent, bounded solid-profile validation of the exact printing STL.

Geometry validated means these declared geometry gates passed. It is never a
print-suitability claim. Unsupported feature and physical gates stay unknown.
"""
import hashlib
import math
from pathlib import Path
import time
from .export_checks import MeshError, parse_stl, MAX_BYTES
from .topology import inspect_topology
from .intersections import rational, improper_intersection, point_inside

MAX_PAIR_TESTS = 200000
MAX_VALIDATION_SECONDS = 30.0
class ValidationTimeout(Exception):
    pass


GEOMETRY_CODES = ('export_parse', 'finite_coordinates', 'nonempty_mesh',
    'dimensions', 'boundary_edges', 'nonmanifold_edges', 'nonmanifold_vertices',
    'degenerate_faces', 'duplicate_faces', 'consistent_orientation',
    'components', 'positive_shell_volumes', 'self_intersections', 'shell_nesting')


def validate_mesh(path, request):
    """Return a JSON-compatible v1 report; required errors/unknowns fail closed.

    STL has no units: coordinates are interpreted as mm by this explicit request
    contract. Identity is exact (no tolerance welding). Dimension tolerance is
    used only for dimension comparison, never to hide geometric defects.
    """
    checks, metrics = [], {}
    started = time.monotonic()

    def ensure_budget():
        if time.monotonic() - started > MAX_VALIDATION_SECONDS:
            raise ValidationTimeout('Cooperative validation deadline exceeded')

    def check(code, status, actual=None, expected=None, method='independent STL inspection', evidence=None, next_action=None, required=True):
        checks.append(dict(code=code, status=status, actual=actual, expected=expected,
            method=method, evidence=evidence or [], next_action=next_action or
            ('none' if status == 'pass' else 'Revise the source and export a new attempt; retain this evidence.'),
            required=required))

    def finish():
        present = {c['code'] for c in checks}
        required_codes = GEOMETRY_CODES + (('generator_contract', 'generator_features', 'generator_volume', 'generator_cross_sections') if request.get('generator_id') == 'freecad-stepped-block' else ())
        for code in required_codes:
            if code not in present:
                check(code, 'unknown', method='not evaluated because a prerequisite failed')
        for code in ('wall_thickness', 'small_features', 'clearances', 'build_envelope',
                     'orientation_supports', 'visual_completeness', 'slicer', 'physical_print'):
            check(code, 'unknown', method='not implemented or requires process/human evidence',
                  next_action='Review with the intended printer/material and inspect the model; slice and test print as appropriate.', required=False)
        metrics['validation_seconds'] = time.monotonic() - started
        if metrics['validation_seconds'] > MAX_VALIDATION_SECONDS and not any(c['code'] == 'validation_deadline' for c in checks):
            check('validation_deadline', 'unknown', metrics['validation_seconds'], MAX_VALIDATION_SECONDS,
                  method='cooperative whole-validation deadline; hard process deadline belongs to caller')
        blocked = any(c['required'] and c['status'] != 'pass' for c in checks)
        return dict(schema_version='1', profile='solid-single-part',
                    geometry_state='blocked' if blocked else 'geometry_validated',
                    print_state='needs_review', checks=checks, metrics=metrics,
                    validator='printkit-exact-stl-v1')

    try:
        dims = request.get('dimensions_mm')
        tol = request.get('tolerance_mm')
        allowed = request.get('allowed_components')
        valid_number = lambda v: type(v) in (int, float) and math.isfinite(v)
        valid = (isinstance(dims, (list, tuple)) and len(dims) == 3 and
                 all(valid_number(v) and v > 0 for v in dims) and
                 valid_number(tol) and tol >= 0 and type(allowed) is int and allowed >= 1 and
                 request.get('units', 'mm') == 'mm')
        check('request_contract', 'pass' if valid else 'fail',
              expected='positive finite dimensions_mm[3], finite nonnegative tolerance_mm, positive integer allowed_components, mm units')
        if not valid: return finish()
        # Explicitly restricted initial profile, rather than silently accepting assemblies.
        check('solid_profile', 'pass' if allowed == 1 else 'fail', allowed, 1,
              method='initial single-solid profile; assemblies/cavities not supported')
        ensure_budget()
        with Path(path).open('rb') as handle:
            data = handle.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES: raise MeshError('export_budget', 'STL exceeds byte budget')
        metrics.update(sha256=hashlib.sha256(data).hexdigest(), byte_size=len(data))
        ensure_budget()
        triangles, encoding = parse_stl(data, ensure_budget)
        metrics.update(triangle_count=len(triangles), encoding=encoding)
        check('export_parse', 'pass', encoding, 'complete, strictly parsed STL', evidence=[{'sha256': metrics['sha256'], 'byte_size': len(data)}])
        check('finite_coordinates', 'pass', True, True)
        check('nonempty_mesh', 'pass', len(triangles), '>0 triangles')
        vertices = [v for t in triangles for v in t]
        minimum = [min(v[k] for v in vertices) for k in range(3)]
        maximum = [max(v[k] for v in vertices) for k in range(3)]
        actual_dims = [b-a for a, b in zip(minimum, maximum)]
        metrics.update(dimensions_mm=actual_dims, bounds_mm=[minimum, maximum])
        check('dimensions', 'pass' if all(abs(a-b) <= tol for a, b in zip(actual_dims, dims)) else 'fail', actual_dims,
              {'dimensions_mm': dims, 'tolerance_mm': tol}, method='axis-aligned bounds of exact exported vertices')
        ensure_budget()
        top = inspect_topology(triangles, ensure_budget)
        ensure_budget()
        metrics.update(component_count=len(top['components']), signed_volumes_mm3=top['signed_volumes_mm3'],
                       signed_volume_signs=top['signed_volume_signs'], volume_underflow_exact_mm3=top['volume_underflow_exact_mm3'])
        for code, key in (('boundary_edges', 'boundary_edges'), ('nonmanifold_edges', 'nonmanifold_edges'),
                          ('nonmanifold_vertices', 'nonmanifold_vertices'), ('degenerate_faces', 'degenerate_faces'),
                          ('duplicate_faces', 'duplicate_faces'), ('consistent_orientation', 'inconsistent_edges')):
            bad = top[key]
            check(code, 'fail' if bad else 'pass', len(bad), 0,
                  method='exact vertex identity; edge incidence and connected cyclic vertex links', evidence=bad[:20])
        check('components', 'pass' if len(top['components']) == allowed else 'fail', len(top['components']), allowed,
              method='face adjacency through shared exact edges')
        check('positive_shell_volumes', 'pass' if all(v > 0 for v in top['signed_volume_signs']) else 'fail',
              {'volumes_mm3': top['signed_volumes_mm3'], 'exact_signs': top['signed_volume_signs']}, 'each shell strictly positive', method='exact rational oriented tetrahedron sum per component')
        if top['degenerate_faces'] or top['duplicate_faces']:
            check('self_intersections', 'unknown', method='degenerate or duplicate triangles prevent independent intersection assessment')
            return finish()
        exact = []
        for t in triangles:
            ensure_budget()
            exact.append(rational(t))
        boxes = [(tuple(min(p[k] for p in t) for k in range(3)), tuple(max(p[k] for p in t) for k in range(3))) for t in triangles]
        order = sorted(range(len(triangles)), key=lambda i: boxes[i][0][0])
        hits, tests, candidates, exhausted = [], 0, 0, False
        # Sweep broad phase includes touching boxes; all touching pairs receive exact predicates.
        for pos, i in enumerate(order):
            for j in order[pos+1:]:
                if boxes[j][0][0] > boxes[i][1][0]: break
                candidates += 1
                if candidates > MAX_PAIR_TESTS * 20 or time.monotonic()-started > MAX_VALIDATION_SECONDS:
                    exhausted = True; break
                if any(boxes[i][1][k] < boxes[j][0][k] or boxes[j][1][k] < boxes[i][0][k] for k in (1, 2)): continue
                tests += 1
                if tests > MAX_PAIR_TESTS:
                    exhausted = True; break
                intersects = improper_intersection(exact[i], exact[j])
                ensure_budget()
                if intersects:
                    if len(hits) < 100: hits.append([i, j])
            if exhausted: break
        ensure_budget()
        metrics.update(intersection_pair_tests=tests, intersection_candidates=candidates)
        check('self_intersections', 'fail' if hits else ('unknown' if exhausted else 'pass'),
              {'pairs': hits, 'budget_exhausted': exhausted}, 'no intersections beyond a shared topological vertex/edge',
              method='conservative AABB sweep + exact rational 3D/coplanar intersection predicates', evidence=hits)
        # A contact at a shared topological point is independently rejected by vertex-link checks.
        if hits or exhausted or any(top[k] for k in ('boundary_edges', 'nonmanifold_edges', 'nonmanifold_vertices')):
            check('shell_nesting', 'unknown', method='requires closed nonintersecting manifold shells')
        else:
            nesting, unresolved = [], False
            for i, shell in enumerate(top['components']):
                for j, other in enumerate(top['components']):
                    if i == j: continue
                    if time.monotonic()-started > MAX_VALIDATION_SECONDS:
                        unresolved = True; break
                    result = point_inside(exact[shell[0]][0], [exact[k] for k in other], ensure_budget)
                    ensure_budget()
                    if result is None: unresolved = True
                    elif result: nesting.append([i, j])
            check('shell_nesting', 'fail' if nesting else ('unknown' if unresolved else 'pass'), nesting, [],
                  method='exact rational ray parity; deterministic edge-degeneracy retries', evidence=nesting)
        if request.get('generator_id') == 'freecad-stepped-block' and all(c['status'] == 'pass' for c in checks if c['required']):
            from .generator_checks import check_generator
            checks.extend(check_generator(triangles, request, ensure_budget))
            ensure_budget()
        return finish()
    except ValidationTimeout as exc:
        check('validation_deadline', 'unknown', str(exc), MAX_VALIDATION_SECONDS,
              method='cooperative deadline includes parsing, topology and geometry')
        return finish()
    except MeshError as exc:
        check(exc.code, 'fail', str(exc), 'valid STL within supported budgets')
        return finish()
    except Exception as exc:  # Required gate failures must never turn into passes.
        check('validator_error', 'unknown', type(exc).__name__, 'successful independent validation',
              method='caught failure; no validation claim', next_action='Inspect the retained export and validator diagnostic, then rerun.')
        return finish()
