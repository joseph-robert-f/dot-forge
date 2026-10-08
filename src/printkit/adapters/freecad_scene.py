"""Original, fixed FreeCAD helper; run in isolated system Python, never request code.

The one supported model is a full-width half-height base, a half-width upper
step, and a vertical through-hole in the lower ledge. All coordinates are mm.
"""
import json
import math
from pathlib import Path
import sys
import time

# Reviewed distro location, not a request-supplied module search path.
sys.path.insert(0, '/usr/lib/freecad/lib')
import FreeCAD as App
import Part
import MeshPart

GENERATOR = 'freecad-stepped-block'
LINEAR_DEFLECTION = 0.05
ANGULAR_DEFLECTION = 0.25


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def runtime():
    return {'version': '.'.join(App.Version()[:3]), 'occ_version': Part.OCC_VERSION,
            'python_version': sys.version.split()[0], 'native_module': Path(App.__file__).name}


def dimensions(request):
    if request.get('generator_id') != GENERATOR or request.get('backend') != 'freecad':
        raise ValueError('Unsupported reviewed FreeCAD generator/backend')
    params = request.get('parameters')
    keys = ('width_mm', 'depth_mm', 'height_mm')
    if not isinstance(params, dict) or set(params) != set(keys):
        raise ValueError('Only width_mm/depth_mm/height_mm are supported')
    dims = [params[k] for k in keys]
    if any(type(d) not in (int, float) or not 5 <= d <= 100 or not math.isfinite(d) for d in dims):
        raise ValueError('FreeCAD dimensions must be finite numbers within 5–100 mm')
    return dims


def inspect_shape(shape, dims):
    w, d, h = dims
    radius = min(w / 8, d / 6)
    expected_volume = .75 * w * d * h - math.pi * radius ** 2 * h / 2
    box = shape.BoundBox
    actual_dims = [box.XLength, box.YLength, box.ZLength]
    origin = [box.XMin, box.YMin, box.ZMin]
    curves = sum(isinstance(edge.Curve, Part.Circle) for edge in shape.Edges)
    inside = lambda x, y, z: shape.isInside(App.Vector(x, y, z), 1e-7, False)
    features = {'base_present': inside(w / 8, d / 8, h / 4),
                'raised_step_present': inside(3 * w / 4, d / 2, 3 * h / 4),
                'lower_ledge_clear': not inside(w / 4, d / 8, 3 * h / 4),
                'through_hole_clear': all(not inside(w / 4, d / 2, h * f) for f in (.01, .25, .49)),
                'circular_edges_present': curves >= 2}
    valid = not shape.isNull() and shape.isValid() and len(shape.Solids) == 1 and shape.isClosed()
    passed = (valid and all(abs(a - b) <= 1e-6 for a, b in zip(actual_dims, dims))
              and all(abs(x) <= 1e-6 for x in origin)
              and abs(shape.Volume - expected_volume) <= max(1e-6, expected_volume * 1e-8)
              and all(features.values()))
    if not passed:
        raise ValueError('Native solid failed validity, dimension, volume, or required-feature checks')
    return {'status': 'pass', 'brep_valid': True, 'closed': True, 'solid_count': 1,
            'dimensions_mm': actual_dims, 'origin_mm': origin, 'volume_mm3': shape.Volume,
            'expected_volume_mm3': expected_volume, 'circular_edge_count': curves,
            'hole_radius_mm': radius, 'feature_checks': features}


def generate(run, request):
    dims = dimensions(request)
    w, d, h = dims
    start = time.perf_counter()
    base = Part.makeBox(w, d, h / 2)
    raised = Part.makeBox(w / 2, d, h / 2, App.Vector(w / 2, 0, h / 2))
    hole = Part.makeCylinder(min(w / 8, d / 6), h, App.Vector(w / 4, d / 2, 0))
    solid = base.fuse(raised).cut(hole).removeSplitter()
    checks = inspect_shape(solid, dims)
    construction_seconds = time.perf_counter() - start
    document = App.newDocument('CalibrationSolid')
    document.License = 'GPL-3.0-or-later'
    document.LicenseURL = 'https://www.gnu.org/licenses/gpl-3.0.html'
    obj = document.addObject('Part::Feature', 'SteppedBlock')
    obj.Shape = solid
    for name, value in zip(('Width', 'Depth', 'Height'), dims):
        obj.addProperty('App::PropertyLength', name, 'Dimensions')
        setattr(obj, name, value)
    obj.addProperty('App::PropertyString', 'Generator', 'Provenance')
    obj.Generator = GENERATOR + '@1'
    document.recompute()
    start = time.perf_counter()
    document.saveAs(str(run / 'native/model.FCStd'))
    solid.exportStep(str(run / 'exports/model.step'))
    mesh = MeshPart.meshFromShape(Shape=solid, LinearDeflection=LINEAR_DEFLECTION,
                                  AngularDeflection=ANGULAR_DEFLECTION, Relative=False)
    if mesh.CountFacets > 10000:
        raise ValueError('Tessellation triangle budget exceeded')
    mesh.write(str(run / 'exports/model.stl'))
    App.closeDocument(document.Name)
    dump(run / 'native/generation.json', {'status': 'pass', 'runtime': runtime(),
         'shape': checks, 'triangles': mesh.CountFacets, 'model_construction_seconds': construction_seconds,
         'native_save_and_export_seconds': time.perf_counter() - start,
         'tessellation': {'linear_deflection_mm': LINEAR_DEFLECTION,
                          'angular_deflection_radians': ANGULAR_DEFLECTION, 'relative': False}})


def reopen(run, request):
    dims = dimensions(request)
    # Only our newly emitted data-only Part::Feature document is accepted.
    document = App.openDocument(str(run / 'native/model.FCStd'))
    try:
        if len(document.Objects) != 1 or document.Objects[0].TypeId != 'Part::Feature':
            raise ValueError('Native document object inventory differs')
        if document.License != 'GPL-3.0-or-later' or document.LicenseURL != 'https://www.gnu.org/licenses/gpl-3.0.html':
            raise ValueError('Native example asset license metadata differs')
        obj = document.Objects[0]
        if obj.Generator != GENERATOR + '@1':
            raise ValueError('Native generator identity differs')
        if any(abs(getattr(obj, name).Value - value) > 1e-6
               for name, value in zip(('Width', 'Depth', 'Height'), dims)):
            raise ValueError('Native parameter metadata differs')
        native = inspect_shape(obj.Shape, dims)
    finally:
        App.closeDocument(document.Name)
    exported = Part.Shape()
    exported.read(str(run / 'exports/model.step'))
    step = inspect_shape(exported, dims)
    if abs(native['volume_mm3'] - step['volume_mm3']) > max(1e-6, native['volume_mm3'] * 1e-8):
        raise ValueError('STEP round-trip volume differs')
    dump(run / 'native/reopen.json', {'status': 'pass', 'fresh_process': True,
         'method': 'fresh native FreeCAD FCStd reopen and separate STEP BREP import',
         'native': native, 'step': step, 'asset_license': 'GPL-3.0-or-later', 'native_dimensions_mm': native['dimensions_mm'],
         'step_dimensions_mm': step['dimensions_mm'], 'runtime': runtime()})


def main():
    mode, target = sys.argv[1:]
    run = Path(target)
    if mode == 'discover':
        dump(run / 'runtime.json', runtime())
        return
    request = json.loads((run / 'request.json').read_text())
    if mode == 'generate':
        generate(run, request)
    elif mode == 'reopen':
        reopen(run, request)
    else:
        raise ValueError('Unknown helper mode')


if __name__ == '__main__':
    main()
