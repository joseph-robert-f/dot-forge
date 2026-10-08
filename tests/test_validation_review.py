"""Independent adversarial review regressions; no external geometry dependency."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from printkit.validation import validate_mesh, improper_intersection
from printkit.validation.intersections import rational
from test_validation import cube, stl


class IndependentReviewTests(unittest.TestCase):
    def validate(self, triangles, binary=True):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'mesh.stl'
            path.write_bytes(stl(triangles, binary))
            return validate_mesh(path, dict(dimensions_mm=[1, 1, 1], tolerance_mm=.0001, allowed_components=1))

    def test_final_predicate_deadline_exhaustion_blocks(self):
        total = self.validate(cube())['metrics']['intersection_pair_tests']
        state = {'clock': 0.0, 'calls': 0}

        def predicate(a, b):
            result = improper_intersection(a, b)
            state['calls'] += 1
            if state['calls'] == total:
                state['clock'] = 31.0
            return result

        with patch('printkit.validation.time.monotonic', side_effect=lambda: state['clock']), \
             patch('printkit.validation.improper_intersection', side_effect=predicate):
            report = self.validate(cube())
        self.assertEqual(report['geometry_state'], 'blocked', report)

    def test_exact_positive_volume_underflow_not_rejected(self):
        # All AABB dimensions are 1 mm. The exact nonzero volume is < binary64 min.
        vertices = [(0, 0, 0), (1, 1, 1), (1e-200, 0, 0), (0, 1e-200, 0)]
        faces = [(0, 2, 1), (0, 1, 3), (0, 3, 2), (1, 2, 3)]
        triangles = [tuple(vertices[i] for i in face) for face in faces]
        report = self.validate(triangles, binary=False)
        self.assertEqual(report['geometry_state'], 'geometry_validated', report)
        self.assertEqual(report['print_state'], 'needs_review')

    def test_noncoplanar_plane_edge_crossing(self):
        # B has an entire edge in A's plane, with both endpoints outside A.
        a = rational(((0, 0, 0), (2, 0, 0), (0, 2, 0)))
        b = rational(((1, -1, 0), (1, 3, 0), (1, 0, 1)))
        self.assertTrue(improper_intersection(a, b))
        self.assertTrue(improper_intersection(b, a))

    def test_coplanar_crossing_without_contained_vertices(self):
        a = rational(((-2, -1, 0), (2, -1, 0), (0, 2, 0)))
        b = rational(((-2, 1, 0), (2, 1, 0), (0, -2, 0)))
        self.assertTrue(improper_intersection(a, b))
        self.assertTrue(improper_intersection(b, a))

    def test_edge_interior_contact_without_matching_vertices(self):
        a = rational(((0, 0, 0), (2, 0, 0), (0, 2, 0)))
        b = rational(((1, 0, 0), (1, -1, 1), (1, -1, -1)))
        self.assertTrue(improper_intersection(a, b))
        self.assertTrue(improper_intersection(b, a))

    def test_sub_tolerance_crack_not_welded(self):
        triangles = cube()
        first = list(triangles[0])
        first[0] = (1e-7, 0, 0)
        triangles[0] = tuple(first)
        report = self.validate(triangles)
        self.assertEqual(report['geometry_state'], 'blocked')
        boundary = next(c for c in report['checks'] if c['code'] == 'boundary_edges')
        self.assertEqual(boundary['status'], 'fail')


if __name__ == '__main__':
    unittest.main()
