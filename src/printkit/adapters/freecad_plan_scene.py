"""Fixed FreeCAD plan interpreter and B-rep measurer; run in isolated system Python.

The plan is data. Each op name maps to one function in OPS below; no plan
value is evaluated, imported or used as an attribute name. The outer process
validates the plan strictly before this helper runs; this helper still
rejects unknown ops and fields. All coordinates are mm.
"""
import json
import math
from pathlib import Path
import sys
import time

# Reviewed distro location, not a plan-supplied module search path.
sys.path.insert(0, '/usr/lib/freecad/lib')
import FreeCAD as App
import Part
import MeshPart

LINEAR_DEFLECTION = 0.05
ANGULAR_DEFLECTION = 0.25
MAX_TRIANGLES = 10000  # Same budget as independent STL validation.
PROBE_MM = 0.01
LINEAR_TOL = 1e-6
AXES = {'x': App.Vector(1, 0, 0), 'y': App.Vector(0, 1, 0), 'z': App.Vector(0, 0, 1)}
PLANE_NORMAL = {'xy': 'z', 'xz': 'y', 'yz': 'x'}


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def runtime():
    return {'version': '.'.join(App.Version()[:3]), 'occ_version': Part.OCC_VERSION,
            'python_version': sys.version.split()[0], 'native_module': Path(App.__file__).name}


def vec(values):
    return App.Vector(*[float(v) for v in values])


def on_plane(plane, a, b, offset):
    return {'xy': (a, b, offset), 'xz': (a, offset, b), 'yz': (offset, a, b)}[plane]


def face_from(points3):
    wire = Part.makePolygon([vec(p) for p in points3] + [vec(points3[0])])
    return Part.Face(wire)


def moved(shape, by):
    copy = shape.copy()
    copy.translate(by)
    return copy


def turned(shape, about, axis, degrees):
    copy = shape.copy()
    copy.rotate(about, AXES[axis], degrees)
    return copy


def fuse_all(shapes):
    result = shapes[0]
    for shape in shapes[1:]:
        result = result.fuse(shape)
    return result.removeSplitter()


def edges(shape, selector):
    if selector == 'all':
        return shape.Edges
    axis = AXES[selector[-1]]
    picked = []
    for edge in shape.Edges:
        if isinstance(edge.Curve, Part.Line):
            direction = edge.Curve.Direction
            if abs(abs(direction.dot(axis)) - 1) <= 1e-9:
                picked.append(edge)
    if not picked:
        raise ValueError(f'No edges match selector {selector}')
    return picked


def op_box(s, get):
    return Part.makeBox(*[float(v) for v in s['size_mm']], vec(s.get('at_mm', [0, 0, 0])))


def op_cylinder(s, get):
    return Part.makeCylinder(float(s['radius_mm']), float(s['height_mm']), vec(s.get('at_mm', [0, 0, 0])),
                             AXES[s.get('axis', 'z')])


def op_cone(s, get):
    return Part.makeCone(float(s['radius1_mm']), float(s['radius2_mm']), float(s['height_mm']),
                         vec(s.get('at_mm', [0, 0, 0])), AXES[s.get('axis', 'z')])


def op_sphere(s, get):
    return Part.makeSphere(float(s['radius_mm']), vec(s.get('at_mm', [0, 0, 0])))


def op_extrude(s, get):
    offset = s.get('offset_mm', 0)
    face = face_from([on_plane(s['plane'], a, b, offset) for a, b in s['points']])
    return face.extrude(AXES[PLANE_NORMAL[s['plane']]] * float(s['height_mm']))


def op_revolve(s, get):
    at = s.get('at_mm', [0, 0, 0])
    face = face_from([(at[0] + r, at[1], at[2] + z) for r, z in s['points']])
    return face.revolve(vec(at), AXES['z'], float(s.get('angle_deg', 360)))


def op_union(s, get):
    return fuse_all([get(i) for i in s['of']])


def op_intersect(s, get):
    result = get(s['of'][0])
    for other in s['of'][1:]:
        result = result.common(get(other))
    return result.removeSplitter()


def op_cut(s, get):
    tools = [get(i) for i in s['tools']]
    return get(s['from']).cut(tools[0] if len(tools) == 1 else fuse_all(tools)).removeSplitter()


def op_translate(s, get):
    return moved(get(s['target']), vec(s['by_mm']))


def op_rotate(s, get):
    return turned(get(s['target']), vec(s.get('about_mm', [0, 0, 0])), s['axis'], float(s['angle_deg']))


def op_mirror(s, get):
    axis = PLANE_NORMAL[s['plane']]
    base = App.Vector(0, 0, 0)
    setattr(base, axis, float(s.get('through_mm', 0)))
    return get(s['target']).mirror(base, AXES[axis])


def op_linear_pattern(s, get):
    shape, step = get(s['target']), vec(s['step_mm'])
    return fuse_all([moved(shape, step * k) for k in range(s['count'])])


def op_polar_pattern(s, get):
    shape, count, angle = get(s['target']), s['count'], float(s.get('angle_deg', 360))
    pitch = angle / count if abs(abs(angle) - 360) < 1e-9 else angle / (count - 1)
    about = vec(s.get('about_mm', [0, 0, 0]))
    return fuse_all([turned(shape, about, s['axis'], pitch * k) for k in range(count)])


def op_fillet(s, get):
    shape = get(s['target'])
    return shape.makeFillet(float(s['radius_mm']), edges(shape, s['edges']))


def op_chamfer(s, get):
    shape = get(s['target'])
    return shape.makeChamfer(float(s['size_mm']), edges(shape, s['edges']))


OPS = {'box': op_box, 'cylinder': op_cylinder, 'cone': op_cone, 'sphere': op_sphere,
       'extrude': op_extrude, 'revolve': op_revolve, 'union': op_union, 'intersect': op_intersect,
       'cut': op_cut, 'translate': op_translate, 'rotate': op_rotate, 'mirror': op_mirror,
       'linear_pattern': op_linear_pattern, 'polar_pattern': op_polar_pattern,
       'fillet': op_fillet, 'chamfer': op_chamfer}


class StepFailed(Exception):
    def __init__(self, step, op, cause):
        super().__init__(f'{op} step {step!r} failed: {type(cause).__name__}: {cause}')
        self.step, self.op, self.cause = step, op, cause


def build(plan):
    if plan.get('schema_version') != 'plan.v1' or plan.get('units') != 'mm':
        raise ValueError('Unsupported plan')
    shapes = {}
    for step in plan['steps']:
        function = OPS.get(step.get('op'))
        if function is None or step['id'] in shapes:
            raise ValueError('Unknown op or duplicate step id')
        try:
            shapes[step['id']] = function(step, lambda name: shapes[name])
        except Exception as exc:
            raise StepFailed(step['id'], step['op'], exc) from exc
    shape = shapes[plan['result']]
    if shape.isNull() or not shape.Solids:
        raise ValueError('Plan result has no solid')
    return shape.Solids[0] if len(shape.Solids) == 1 else shape


def named_axis(direction):
    for name, axis in AXES.items():
        if abs(abs(direction.dot(axis)) - 1) <= 1e-9:
            return name
    return None


def cylinders(shape, low):
    """Group analytic cylinder faces into whole cylinders and probe each one."""
    pieces = []
    for face in shape.Faces:
        surface = face.Surface
        if not isinstance(surface, Part.Cylinder):
            continue
        axis = named_axis(surface.Axis)
        direction = AXES[axis] if axis else App.Vector(surface.Axis).normalize()
        sign = 1 if surface.Axis.dot(direction) > 0 else -1
        u0, u1, v0, v1 = face.ParameterRange
        along = surface.Center.dot(direction)
        foot = surface.Center - direction * along
        pieces.append({'axis': axis, 'direction': direction, 'foot': foot, 'radius': surface.Radius,
                       'span': sorted([along + sign * v0, along + sign * v1]), 'angle': u1 - u0})
    groups = []
    for piece in sorted(pieces, key=lambda p: p['span'][0]):
        for group in groups:
            if (abs(abs(group['direction'].dot(piece['direction'])) - 1) <= 1e-9
                    and abs(group['radius'] - piece['radius']) <= LINEAR_TOL
                    and (group['foot'] - piece['foot']).Length <= LINEAR_TOL
                    and piece['span'][0] <= group['span'][1] + LINEAR_TOL):
                same = abs(piece['span'][0] - group['span'][0]) <= LINEAR_TOL and abs(piece['span'][1] - group['span'][1]) <= LINEAR_TOL
                group['span'][1] = max(group['span'][1], piece['span'][1])
                # Split faces of one cylinder share a span and add up their angles.
                group['angle'] = group['angle'] + piece['angle'] if same else max(group['angle'], piece['angle'])
                break
        else:
            groups.append(dict(piece, span=list(piece['span'])))
    inside = lambda point: shape.isInside(point, 1e-7, False)
    result = []
    for g in groups:
        d, foot, (s0, s1) = g['direction'], g['foot'], g['span']
        void = not inside(foot + d * ((s0 + s1) / 2))
        entry = {'axis': g['axis'], 'radius_mm': g['radius'], 'angle_rad': g['angle'],
                 'kind': 'void' if void else 'boss', 'position_mm': None, 'span_mm': None, 'ends_open': None}
        if g['axis']:
            index = 'xyz'.index(g['axis'])
            plane = [i for i in range(3) if i != index]
            point = [foot.x, foot.y, foot.z]
            entry['position_mm'] = [point[i] - low[i] for i in plane]
            entry['span_mm'] = [s0 - low[index], s1 - low[index]]
            entry['ends_open'] = [not inside(foot + d * (s0 - PROBE_MM)), not inside(foot + d * (s1 + PROBE_MM))]
        result.append(entry)
    return result


def planes(shape, low):
    result = []
    for face in shape.Faces:
        if not isinstance(face.Surface, Part.Plane):
            continue
        u0, u1, v0, v1 = face.ParameterRange
        normal = face.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
        axis = named_axis(normal)
        entry = {'normal': None, 'offset_mm': None, 'area_mm2': face.Area}
        if axis:
            index = 'xyz'.index(axis)
            entry['normal'] = ('+' if [normal.x, normal.y, normal.z][index] > 0 else '-') + axis
            point = face.Vertexes[0].Point
            entry['offset_mm'] = [point.x, point.y, point.z][index] - low[index]
        result.append(entry)
    return result


def measure(shape):
    box = shape.BoundBox
    low = [box.XMin, box.YMin, box.ZMin]
    return {'valid': shape.isValid(), 'closed': shape.isClosed(), 'solid_count': len(shape.Solids),
            'size_mm': [box.XLength, box.YLength, box.ZLength], 'origin_mm': low,
            'volume_mm3': shape.Volume, 'area_mm2': shape.Area, 'face_count': len(shape.Faces),
            'cylinders': cylinders(shape, low), 'planes': planes(shape, low),
            'linear_tolerance_mm': LINEAR_TOL, 'probe_offset_mm': PROBE_MM}


def generate(run):
    plan = json.loads((run / 'plan.json').read_text())
    start = time.perf_counter()
    shape = build(plan)
    construction_seconds = time.perf_counter() - start
    native = measure(shape)
    document = App.newDocument('DotForgePlan')
    obj = document.addObject('Part::Feature', 'Model')
    obj.Shape = shape
    obj.addProperty('App::PropertyString', 'PlanSchema', 'Provenance')
    obj.PlanSchema = plan['schema_version']
    document.recompute()
    start = time.perf_counter()
    document.saveAs(str(run / 'native/model.FCStd'))
    shape.exportStep(str(run / 'exports/model.step'))
    mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=LINEAR_DEFLECTION,
                                  AngularDeflection=ANGULAR_DEFLECTION, Relative=False)
    if mesh.CountFacets > MAX_TRIANGLES:
        raise ValueError('Tessellation triangle budget exceeded')
    mesh.write(str(run / 'exports/model.stl'))
    App.closeDocument(document.Name)
    dump(run / 'native/generation.json', {'status': 'pass', 'runtime': runtime(), 'measure': native,
         'triangles': mesh.CountFacets, 'model_construction_seconds': construction_seconds,
         'native_save_and_export_seconds': time.perf_counter() - start,
         'tessellation': {'linear_deflection_mm': LINEAR_DEFLECTION,
                          'angular_deflection_radians': ANGULAR_DEFLECTION, 'relative': False}})


def reopen(run):
    # Only our newly emitted data-only Part::Feature document is accepted.
    document = App.openDocument(str(run / 'native/model.FCStd'))
    try:
        if len(document.Objects) != 1 or document.Objects[0].TypeId != 'Part::Feature':
            raise ValueError('Native document object inventory differs')
        native = measure(document.Objects[0].Shape)
    finally:
        App.closeDocument(document.Name)
    exported = Part.Shape()
    exported.read(str(run / 'exports/model.step'))
    step = measure(exported)
    same = (abs(native['volume_mm3'] - step['volume_mm3']) <= max(1e-6, abs(native['volume_mm3']) * 1e-8)
            and all(abs(a - b) <= LINEAR_TOL for a, b in zip(native['size_mm'], step['size_mm']))
            and len(native['cylinders']) == len(step['cylinders']) and native['solid_count'] == step['solid_count'])
    if not same:
        raise ValueError('STEP round trip differs from the native solid')
    # The STEP reimport is the measured deliverable.
    dump(run / 'native/measure.json', step)
    dump(run / 'native/reopen.json', {'status': 'pass', 'fresh_process': True,
         'method': 'fresh native FCStd reopen and separate STEP BREP import, both measured',
         'native': native, 'step': step, 'runtime': runtime()})


def main():
    mode, target = sys.argv[1:]
    run = Path(target)
    if mode == 'generate':
        try:
            generate(run)
        except StepFailed as exc:
            # A plan FreeCAD cannot build is a plan finding, not a runtime fault.
            dump(run / 'native/plan-failure.json', {'status': 'fail', 'step': exc.step, 'op': exc.op,
                 'error': f'{type(exc.cause).__name__}: {exc.cause}'[:2000], 'runtime': runtime()})
            raise
    elif mode == 'reopen':
        reopen(run)
    else:
        raise ValueError('Unknown helper mode')


if __name__ == '__main__':
    main()
