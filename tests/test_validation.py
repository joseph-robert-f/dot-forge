"""Adversarial fixtures with explicit intended gates, no external engine needed."""
import math
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
from printkit.validation import validate_mesh
from printkit.validation.intersections import rational, improper_intersection, point_inside


def cube(lo=(0, 0, 0), hi=(1, 1, 1)):
    vertices = [(lo[0],lo[1],lo[2]), (hi[0],lo[1],lo[2]), (hi[0],hi[1],lo[2]), (lo[0],hi[1],lo[2]),
                (lo[0],lo[1],hi[2]), (hi[0],lo[1],hi[2]), (hi[0],hi[1],hi[2]), (lo[0],hi[1],hi[2])]
    faces = [(0,2,1),(0,3,2),(4,5,6),(4,6,7),(0,1,5),(0,5,4),(1,2,6),(1,6,5),(2,3,7),(2,7,6),(3,0,4),(3,4,7)]
    return [tuple(vertices[i] for i in face) for face in faces]


def stl(triangles, binary=True):
    if binary:
        return b'Independent fixture'.ljust(80,b'\0') + struct.pack('<I',len(triangles)) + b''.join(
            struct.pack('<12fH',0,0,0,*(v for p in t for v in p),0) for t in triangles)
    body = ['solid fixture']
    for t in triangles:
        body += ['facet normal 0 0 0','outer loop']
        body += ['vertex '+' '.join(str(v) for v in p) for p in t]
        body += ['endloop','endfacet']
    return ('\n'.join(body+['endsolid fixture'])+'\n').encode()


class ValidationTests(unittest.TestCase):
    def report(self, triangles=None, data=None, **request):
        config = dict(dimensions_mm=[1,1,1], tolerance_mm=0.00001, allowed_components=1)
        config.update(request)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'mesh.stl'
            path.write_bytes(data if data is not None else stl(triangles))
            return validate_mesh(path, config)

    def gate(self, report, code, status='fail'):
        finding = next(c for c in report['checks'] if c['code'] == code)
        self.assertEqual(finding['status'],status,(code, finding, report['geometry_state']))
        if status != 'pass': self.assertEqual(report['geometry_state'],'blocked')

    def test_valid_binary_and_ascii(self):
        for binary in (True, False):
            r = self.report(data=stl(cube(),binary))
            self.assertEqual(r['geometry_state'],'geometry_validated',r['checks'])
            self.assertEqual(r['metrics']['signed_volumes_mm3'],[1.0])
            self.assertTrue(all(c['status']=='unknown' for c in r['checks'] if not c['required']))

    def test_translated_large_solid(self):
        r=self.report(cube((10000,10000,10000),(10001,10001,10001)))
        self.assertEqual(r['geometry_state'],'geometry_validated')

    def test_valid_rotated_solid(self):
        # Binary-friendly rigid rotation around z; many non-axis-aligned predicates.
        t=[tuple((.6*p[0]-.8*p[1], .8*p[0]+.6*p[1], p[2]) for p in face) for face in cube()]
        self.assertEqual(self.report(t,dimensions_mm=[1.4,1.4,1])['geometry_state'],'geometry_validated')

    def test_valid_tetrahedron(self):
        v=[(0,0,0),(1,0,0),(0,1,0),(0,0,1)]
        t=[tuple(v[i] for i in f) for f in [(0,2,1),(0,1,3),(0,3,2),(1,2,3)]]
        self.assertEqual(self.report(t)['geometry_state'],'geometry_validated')

    def test_thin_shape_not_certified_for_printing(self):
        r=self.report(cube((0,0,0),(1,1,.0001)),dimensions_mm=[1,1,.0001])
        self.assertEqual(r['geometry_state'],'geometry_validated')
        self.assertEqual(r['print_state'],'needs_review')
        for code in ('wall_thickness','small_features','clearances','build_envelope','visual_completeness'):
            check=next(c for c in r['checks'] if c['code']==code)
            self.assertEqual(check['status'],'unknown')
            self.assertFalse(check['required'])

    def test_binary_solid_header_is_not_ascii(self):
        data = stl(cube()); data = b'solid binary'+data[12:]
        self.assertEqual(self.report(data=data)['geometry_state'],'geometry_validated')

    def test_missing_face(self): self.gate(self.report(cube()[:-1]),'boundary_edges')
    def test_duplicate_face(self): self.gate(self.report(cube()+[cube()[0]]),'duplicate_faces')
    def test_pathological_duplicate_faces_is_bounded(self):
        r=self.report([cube()[0]]*10000)
        self.gate(r,'duplicate_faces')
        self.gate(r,'nonmanifold_edges')
        self.assertEqual(r['metrics']['triangle_count'],10000)

    def test_nonmanifold_edge(self): self.gate(self.report(cube()+[cube()[0]]),'nonmanifold_edges')
    def test_duplicate_reverse(self): self.gate(self.report(cube()+[tuple(reversed(cube()[0]))]),'duplicate_faces')
    def test_inconsistent_orientation(self):
        t=cube(); t[0]=tuple(reversed(t[0]))
        self.gate(self.report(t),'consistent_orientation')
    def test_reversed_shell(self): self.gate(self.report([tuple(reversed(t)) for t in cube()]),'positive_shell_volumes')
    def test_per_shell_volume_not_aggregate(self):
        t=cube()+[tuple(reversed(t)) for t in cube((2,2,2),(2.5,2.5,2.5))]
        self.gate(self.report(t),'positive_shell_volumes')
    def test_zero_area(self): self.gate(self.report(cube()+[((0,0,0),(1,1,1),(2,2,2))]),'degenerate_faces')
    def test_bowtie_vertex(self): self.gate(self.report(cube()+cube((1,1,1),(2,2,2))),'nonmanifold_vertices')
    def test_face_contact(self): self.gate(self.report(cube()+cube((1,0,0),(2,1,1))),'nonmanifold_edges')
    def test_edge_contact(self): self.gate(self.report(cube()+cube((1,1,0),(2,2,1))),'nonmanifold_edges')
    def test_contact_without_shared_vertices(self):
        self.gate(self.report(cube()+cube((1,.2,.2),(2,.8,.8))),'self_intersections')
    def test_overlapping_closed_solids(self): self.gate(self.report(cube()+cube((.5,.25,.25),(1.5,.75,.75))),'self_intersections')
    def test_coplanar_overlap(self): self.gate(self.report(cube()+cube((.5,0,0),(1.5,1,1))),'self_intersections')
    def test_self_intersecting_closed_mesh(self):
        t=[tuple((.25,.25,-.5) if p==(1,1,1) else p for p in face) for face in cube()]
        r=self.report(t)
        self.gate(r,'boundary_edges','pass'); self.gate(r,'nonmanifold_edges','pass')
        self.gate(r,'self_intersections')
    def test_nested_shells(self): self.gate(self.report(cube()+cube((.2,.2,.2),(.8,.8,.8))),'shell_nesting')
    def test_floating_component(self): self.gate(self.report(cube()+cube((2,2,2),(3,3,3))),'components')
    def test_multiple_components_profile_not_silently_supported(self): self.gate(self.report(cube()+cube((2,2,2),(3,3,3)),allowed_components=2),'solid_profile')
    def test_wrong_units(self): self.gate(self.report(cube((0,0,0),(1000,1000,1000))),'dimensions')
    def test_dimension_tolerance(self): self.assertEqual(self.report(cube(),dimensions_mm=[1.001,1,1],tolerance_mm=.002)['geometry_state'],'geometry_validated')
    def test_empty(self): self.gate(self.report(data=stl([])),'nonempty_mesh')
    def test_truncated_binary(self): self.gate(self.report(data=stl(cube())[:-1]),'export_parse')
    def test_binary_trailing_bytes(self): self.gate(self.report(data=stl(cube())+b'garbage'),'export_parse')
    def test_ascii_trailing_bytes(self): self.gate(self.report(data=stl(cube(),False)+b'garbage'),'export_parse')
    def test_ascii_nan(self): self.gate(self.report(data=stl(cube(),False).replace(b'vertex 0 0 0',b'vertex nan 0 0',1)),'finite_coordinates')
    def test_binary_nan(self):
        data=bytearray(stl(cube()));struct.pack_into('<f',data,96,float('nan'))
        self.gate(self.report(data=data),'finite_coordinates')
    def test_nonfinite_normal(self):
        data=bytearray(stl(cube()));struct.pack_into('<f',data,84,float('inf'))
        self.gate(self.report(data=data),'finite_coordinates')
    def test_coordinate_budget(self): self.gate(self.report(cube((0,0,0),(1e12,1,1))),'coordinate_budget')
    def test_triangle_budget(self):
        with patch('printkit.validation.export_checks.MAX_TRIANGLES',5): self.gate(self.report(cube()),'triangle_budget')
    def test_byte_budget(self):
        with patch('printkit.validation.MAX_BYTES',100): self.gate(self.report(cube()),'export_budget')
    def test_intersection_budget(self):
        with patch('printkit.validation.MAX_PAIR_TESTS',0): self.gate(self.report(cube()),'self_intersections','unknown')
    def test_timeout(self):
        with patch('printkit.validation.MAX_VALIDATION_SECONDS',-1): self.gate(self.report(cube()),'self_intersections','unknown')
    def test_deadline_includes_parsing_and_topology(self):
        import printkit.validation as validator
        for stage in ('parse_stl','inspect_topology'):
            clock=[0.0]
            original=getattr(validator,stage)
            def slow_stage(*args,**kwargs):
                result=original(*args,**kwargs)
                clock[0]=31.0
                return result
            with patch('printkit.validation.time.monotonic',side_effect=lambda:clock[0]), patch('printkit.validation.'+stage,side_effect=slow_stage):
                self.gate(self.report(cube()),'validation_deadline','unknown')

    def test_validator_crash(self):
        with patch('printkit.validation.inspect_topology',side_effect=RuntimeError('fixture failure')):
            self.gate(self.report(cube()),'validator_error','unknown')
    def test_invalid_request(self):
        for params in ({'dimensions_mm':[float('nan'),1,1]}, {'tolerance_mm':-1},{'allowed_components':True},{'units':'in'}):
            self.gate(self.report(cube(),**params),'request_contract')
    def test_missing_export(self): self.gate(validate_mesh('/definitely/missing.stl',dict(dimensions_mm=[1,1,1],tolerance_mm=0,allowed_components=1)),'validator_error','unknown')
    def test_coplanar_adjacent_triangles_pass(self):
        a=rational(((0,0,0),(1,0,0),(1,1,0)));b=rational(((0,0,0),(1,1,0),(0,1,0)))
        self.assertFalse(improper_intersection(a,b))
    def test_adjacent_folded_overlap_fails(self):
        a=rational(((0,0,0),(1,0,0),(1,1,0)));b=rational(((0,0,0),(1,0,0),(.5,.25,0)))
        self.assertTrue(improper_intersection(a,b))
    def test_exact_ray_parity(self):
        shell=[rational(t) for t in cube()]
        self.assertTrue(point_inside(rational([(.5,.5,.5)])[0],shell))
        self.assertFalse(point_inside(rational([(2,2,2)])[0],shell))


if __name__=='__main__': unittest.main()
