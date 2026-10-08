"""Real native FreeCAD tests are opt-in; policy/path guards need no runtime."""
import json
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from printkit.adapters import freecad
from printkit.adapters.base import AdapterError, RuntimeUnavailable
from printkit.common import ForgeError


def request(dimensions=(20, 16, 12)):
    return {'schema_version': '1', 'generator_id': 'freecad-stepped-block',
            'generator_version': '1', 'backend': 'freecad', 'units': 'mm',
            'parameters': dict(zip(('width_mm', 'depth_mm', 'height_mm'), dimensions)),
            'dimensions_mm': list(dimensions), 'tolerance_mm': .1,
            'allowed_components': 1, 'part_count': 1,
            'export_formats': ['stl', 'fcstd', 'step'], 'render_profile': 'five-view',
            'validation_profile': 'solid-single-part', 'printer_profile': None}


class FreeCADAdapterTests(unittest.TestCase):
    def test_missing_runtime_explicit(self):
        with patch.object(freecad, 'MODULE', Path('/nonexistent/FreeCAD.so')):
            result = freecad.discover()
        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(result['smoke_status'], 'not_run')

    def test_unavailable_does_not_fallback(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(freecad, 'discover', return_value={'status': 'unavailable'}):
            with self.assertRaises(RuntimeUnavailable):
                freecad.generate(request(), tmp)
            self.assertFalse((Path(tmp) / 'exports/model.stl').exists())

    def test_bounded_declarative_parameters(self):
        bad = []
        for value in (True, False, None, '20', float('nan'), float('inf'), 10**1000, 4.999, 100.001):
            r = request(); r['parameters']['width_mm'] = value; bad.append(r)
        for key, value in (('backend', 'blender'), ('generator_id', 'unknown'), ('parameters', {})):
            r = request(); r[key] = value; bad.append(r)
        r = request(); r['parameters']['code'] = 'import os'; bad.append(r)
        for r in bad:
            with self.subTest(r=r), tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(AdapterError):
                    freecad.generate(r, tmp)

    def test_stale_artifacts_and_reports_rejected(self):
        for name in ('native/model.FCStd', 'exports/model.step', 'exports/model.stl',
                     'native/generation.json', 'native/reopen.json', 'logs/freecad-generate.log'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp) / name; p.parent.mkdir(parents=True); p.write_text('stale')
                with self.assertRaises(AdapterError):
                    freecad.generate(request(), tmp)
                self.assertEqual(p.read_text(), 'stale')

    def test_symlink_output_and_log_rejected(self):
        for name in ('native', 'exports', 'logs', 'request.json', 'logs/freecad-generate.log'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); run = root / 'run'; run.mkdir()
                target = root / 'outside'; target.mkdir()
                dest = run / name; dest.parent.mkdir(parents=True, exist_ok=True); dest.symlink_to(target)
                with self.assertRaises(ForgeError):
                    freecad.generate(request(), run)

    def test_request_mismatch_rejected_without_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'request.json'; path.write_text(json.dumps(request((30, 30, 30))))
            with self.assertRaises(AdapterError):
                freecad.generate(request(), tmp)

    def test_fixed_runtime_argv(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(freecad, 'run_process', return_value={}) as run:
            freecad._run('generate', Path(tmp))
            argv = run.call_args.args[0]
            self.assertEqual(argv[:3], [Path('/usr/bin/python3'), '-I', '-B'])
            self.assertEqual(argv[3], freecad.SCRIPT)
            self.assertNotIn('env_extra', run.call_args.kwargs)


@unittest.skipUnless(os.environ.get('PRINTKIT_FREECAD_INTEGRATION') == '1', 'explicit native FreeCAD integration')
class FreeCADNativeTests(unittest.TestCase):
    def test_golden_and_extreme_parameter_roundtrips(self):
        from printkit.validation import validate_mesh
        for dims in ((20, 16, 12), (5, 5, 5), (100, 100, 100), (5, 100, 5), (100, 5, 100)):
            with self.subTest(dims=dims), tempfile.TemporaryDirectory() as tmp:
                r = request(dims)
                # JSON formatting is caller-owned and must survive generation.
                path = Path(tmp) / 'request.json'; original = json.dumps(r, separators=(',', ':')) + '\n'; path.write_text(original)
                result = freecad.generate(r, tmp)
                self.assertEqual(path.read_text(), original)
                self.assertTrue(result['native_checks']['fresh_process'])
                self.assertEqual(result['native_checks']['asset_license'], 'GPL-3.0-or-later')
                for label in ('native', 'step'):
                    check = result['native_checks'][label]
                    self.assertEqual(check['solid_count'], 1)
                    self.assertTrue(check['brep_valid'])
                    self.assertTrue(all(check['feature_checks'].values()))
                    self.assertAlmostEqual(check['volume_mm3'], check['expected_volume_mm3'], places=5)
                    hole = check['hole_geometry']
                    self.assertEqual(hole['linear_tolerance_mm'], 1e-6)
                    self.assertEqual(hole['cylindrical_face_count'], 1)
                    for actual, expected in zip(hole['center_xy_mm'], (dims[0] / 4, dims[1] / 2)):
                        self.assertAlmostEqual(actual, expected, places=6)
                    self.assertAlmostEqual(hole['radius_mm'], min(dims[0] / 8, dims[1] / 6), places=6)
                    self.assertAlmostEqual(abs(hole['axis'][2]), 1, places=9)
                    for actual, expected in zip(hole['z_extent_mm'], (0, dims[2] / 2)):
                        self.assertAlmostEqual(actual, expected, places=6)
                    for actual, expected in zip(check['dimensions_mm'], dims):
                        self.assertAlmostEqual(actual, expected, places=5)
                self.assertEqual(set(result['artifacts']), {'fcstd', 'step', 'stl'})
                for key in ('binary_sha256', 'native_module_sha256', 'script_sha256'):
                    self.assertEqual(len(result['provenance'][key]), 64)
                validated = validate_mesh(Path(tmp) / 'exports/model.stl', r)
                self.assertEqual(validated['geometry_state'], 'geometry_validated', validated)

    def test_native_and_step_corruption_fail_closed(self):
        for name in ('native/model.FCStd', 'exports/model.step'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                freecad.generate(request(), tmp)
                (Path(tmp) / name).write_bytes(b'corrupt')
                with self.assertRaises(ForgeError):
                    freecad._run('reopen', Path(tmp))

    def test_watertight_missing_hole_rejected(self):
        # Valid closed dimensions alone must not pass the native feature contract.
        for artifact in ('fcstd', 'step'):
            with self.subTest(artifact=artifact), tempfile.TemporaryDirectory() as tmp:
                freecad.generate(request(), tmp)
                script = ("import sys;sys.path.insert(0,'/usr/lib/freecad/lib');"
                          "import FreeCAD as A,Part;from pathlib import Path;"
                          "p=Path(sys.argv[1]);"
                          "s=Part.makeBox(20,16,6).fuse(Part.makeBox(10,16,6,A.Vector(10,0,6))).removeSplitter();"
                          "assert s.isValid() and s.isClosed() and len(s.Solids)==1;"
                          + ("d=A.openDocument(str(p/'native/model.FCStd'));d.Objects[0].Shape=s;"
                             "d.recompute();d.save();A.closeDocument(d.Name)"
                             if artifact == 'fcstd' else "s.exportStep(str(p/'exports/model.step'))"))
                freecad.run_process([freecad.PYTHON, '-I', '-B', '-c', script, tmp],
                                    tmp, Path(tmp) / 'logs/fixture.log', timeout=30)
                with self.assertRaises(ForgeError):
                    freecad._run('reopen', Path(tmp))

    def test_wrong_dimensions_fail_native_reopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            freecad.generate(request(), tmp)
            (Path(tmp) / 'request.json').write_text(json.dumps(request((21, 16, 12))))
            with self.assertRaises(ForgeError):
                freecad._run('reopen', Path(tmp))

    def test_analytic_hole_mutations_rejected_independently(self):
        # Replace one actual native artifact at a time; no mocking inspect_shape.
        # Shifted holes retain exact volume, valid solids and the old void probes.
        holes = {
            'shift_y_032': "hole=Part.makeCylinder(2.5,12,A.Vector(5,8.32,0))",
            'shift_y_1': "hole=Part.makeCylinder(2.5,12,A.Vector(5,9,0))",
            'shift_x_032': "hole=Part.makeCylinder(2.5,12,A.Vector(5.32,8,0))",
            'wrong_radius': "hole=Part.makeCylinder(2.6,12,A.Vector(5,8,0))",
            'blind_equal_volume': "hole=Part.makeCylinder(2.5*math.sqrt(6/5.95),5.95,A.Vector(5,8,.05))",
            'tilted_equal_volume': ("axis=A.Vector(0,.01,1);axis.normalize();"
                                    "hole=Part.makeCylinder(2.5*math.sqrt(axis.z),14,A.Vector(5,7.99,-1),axis)"),
            'elliptical_equal_volume': ("ellipse=Part.Ellipse(A.Vector(5,8,0),3.125,2).toShape();"
                                        "hole=Part.Face(Part.Wire([ellipse])).extrude(A.Vector(0,0,12))"),
        }
        for artifact in ('fcstd', 'step'):
            for name, hole in holes.items():
                with self.subTest(artifact=artifact, mutation=name), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    freecad.generate(request(), root)
                    unchanged = ['exports/model.stl', 'exports/model.step' if artifact == 'fcstd' else 'native/model.FCStd']
                    hashes = {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in unchanged}
                    script = ("import sys,math;sys.path.insert(0,'/usr/lib/freecad/lib');"
                              "import FreeCAD as A,Part;from pathlib import Path;"
                              "p=Path(sys.argv[1]);" + hole + ";"
                              "s=Part.makeBox(20,16,6).fuse(Part.makeBox(10,16,6,A.Vector(10,0,6))).cut(hole).removeSplitter();"
                              "assert s.isValid() and s.isClosed() and len(s.Solids)==1;"
                              + ("expected=2880-math.pi*2.5**2*6;"
                                 "assert abs(s.Volume-expected)<=max(1e-6,expected*1e-8);"
                                 if name != 'wrong_radius' else '')
                              + ("d=A.openDocument(str(p/'native/model.FCStd'));d.Objects[0].Shape=s;"
                                 "d.recompute();d.save();A.closeDocument(d.Name)"
                                 if artifact == 'fcstd' else "s.exportStep(str(p/'exports/model.step'))"))
                    freecad.run_process([freecad.PYTHON, '-I', '-B', '-c', script, tmp],
                                        root, root / 'logs/fixture.log', timeout=30)
                    for path, expected in hashes.items():
                        self.assertEqual(hashlib.sha256((root / path).read_bytes()).hexdigest(), expected)
                    (root / 'native/reopen.json').unlink()
                    with self.assertRaises(ForgeError):
                        freecad._run('reopen', root)
                    self.assertFalse((root / 'native/reopen.json').exists())
                    self.assertIn('Native through-hole', (root / 'logs/freecad-reopen.log').read_text())


if __name__ == '__main__':
    unittest.main()
