"""Independent polygonal fixtures, including closed same-bounds counterfeits."""
import math
import unittest
from unittest.mock import patch
from printkit.validation.generator_checks import check_generator
from printkit.validation.topology import inspect_topology


def stepped_mesh(w=20, d=16, h=12, radius_factor=1, hole_y=.5, filled=False):
    """Construct an oriented single-shell mesh without a CAD engine."""
    cx, cy, radius = w / 4, d * hole_y, min(w / 8, d / 6) * radius_factor
    corners = [(0., 0.), (w / 2, 0.), (w / 2, d), (0., d)]
    angles = sorted(set([i * 2 * math.pi / 72 for i in range(72)] +
                        [math.atan2(y-cy, x-cx) % (2*math.pi) for x, y in corners]))
    outer, inner = [], []
    for angle in angles:
        dx, dy = math.cos(angle), math.sin(angle)
        distances = []
        if dx > 1e-12: distances.append((w / 2-cx) / dx)
        if dx < -1e-12: distances.append(-cx / dx)
        if dy > 1e-12: distances.append((d-cy) / dy)
        if dy < -1e-12: distances.append(-cy / dy)
        scale = min(distances)
        x, y = cx + scale*dx, cy + scale*dy
        for target in (0., w/2):
            if abs(x-target) < 1e-9: x = target
        for target in (0., d):
            if abs(y-target) < 1e-9: y = target
        outer.append((x, y))
        inner.append((cx+radius*dx, cy+radius*dy))
    triangles = []
    def p(point, z): return (*point, z)
    def quad(a, b, c, e): triangles.extend([(a,b,c), (a,c,e)])
    def fan(points, z, positive, center):
        for i, a in enumerate(points):
            face = (p(center,z), p(a,z), p(points[(i+1)%len(points)],z))
            triangles.append(face if positive else tuple(reversed(face)))
    if filled:
        fan(outer, 0, False, (cx,cy)); fan(outer, h/2, True, (cx,cy))
    for i, a in enumerate(outer):
        j = (i+1) % len(outer); b = outer[j]
        if not filled:
            q, s = inner[i], inner[j]
            quad(p(a,h/2),p(b,h/2),p(s,h/2),p(q,h/2))
            quad(p(q,0),p(s,0),p(b,0),p(a,0))
            quad(p(q,0),p(q,h/2),p(s,h/2),p(s,0))
        if not (a[0] == b[0] == w/2):
            quad(p(a,0),p(b,0),p(b,h/2),p(a,h/2))
    interface = sorted(set(y for x,y in outer if x == w/2), reverse=True)
    right = [(w/2,0.),(w,0.),(w,d),(w/2,d)] + [(w/2,y) for y in interface if 0 < y < d]
    fan(right, 0, False, (.75*w,.5*d)); fan(right,h,True,(.75*w,.5*d))
    for i,a in enumerate(right):
        b=right[(i+1)%len(right)]
        if not (a[0] == b[0] == w/2):
            quad(p(a,0),p(b,0),p(b,h/2),p(a,h/2))
        quad(p(a,h/2),p(b,h/2),p(b,h),p(a,h))
    return triangles


class GeneratorChecksTests(unittest.TestCase):
    def request(self, w=20, d=16, h=12):
        return {'generator_id':'freecad-stepped-block', 'parameters':{
            'width_mm':w, 'depth_mm':d, 'height_mm':h}}

    def checks(self, triangles, request=None):
        return {c['code']:c for c in check_generator(triangles, request or self.request())}

    def assert_closed(self, triangles):
        top = inspect_topology(triangles)
        for key in ('boundary_edges','nonmanifold_edges','nonmanifold_vertices',
                    'degenerate_faces','duplicate_faces','inconsistent_edges'):
            self.assertFalse(top[key], (key,top[key][:3]))
        self.assertEqual(len(top['components']),1)
        self.assertGreater(top['signed_volumes_mm3'][0],0)

    def test_correct_independent_analytic_mesh(self):
        mesh=stepped_mesh(); self.assert_closed(mesh)
        checks=self.checks(mesh)
        self.assertTrue(all(c['status']=='pass' for c in checks.values()),checks)
        self.assertTrue(all(c['required'] for c in checks.values()))
        self.assertIn('cannot certify all surfaces',checks['generator_features']['method'])

    def test_missing_hole_closed_same_bounds(self):
        mesh=stepped_mesh(filled=True); self.assert_closed(mesh)
        checks=self.checks(mesh)
        self.assertEqual(checks['generator_features']['status'],'fail')
        self.assertEqual(checks['generator_volume']['status'],'fail')

    def test_wrong_hole_location_has_correct_volume(self):
        mesh=stepped_mesh(hole_y=.72); self.assert_closed(mesh)
        checks=self.checks(mesh)
        self.assertEqual(checks['generator_features']['status'],'fail')
        self.assertEqual(checks['generator_volume']['status'],'pass')

    def test_small_hole_shift_escapes_probes_but_not_sections(self):
        mesh=stepped_mesh(hole_y=.5+.32/16); self.assert_closed(mesh)
        checks=self.checks(mesh)
        self.assertEqual(checks['generator_features']['status'],'pass')
        self.assertEqual(checks['generator_volume']['status'],'pass')
        self.assertEqual(checks['generator_cross_sections']['status'],'fail')

    def test_documented_section_center_tolerance(self):
        for shift, expected in ((.049,'pass'),(.051,'fail')):
            with self.subTest(shift=shift):
                checks=self.checks(stepped_mesh(hole_y=.5+shift/16))
                self.assertEqual(checks['generator_cross_sections']['status'],expected)

    def test_wrong_radius_rejected_by_sections(self):
        checks=self.checks(stepped_mesh(radius_factor=1.025))
        self.assertEqual(checks['generator_features']['status'],'pass')
        self.assertEqual(checks['generator_cross_sections']['status'],'fail')

    def test_two_through_holes_have_three_closed_section_loops(self):
        original=stepped_mesh()
        # Keep perforated left ledge plus the exposed vertical step wall.
        left=[face for face in original if all(p[0]<=10 for p in face)]
        # Replace the solid right tower by a mirrored, taller perforated ledge.
        right=[tuple(reversed(tuple((20-x,y,2*z) for x,y,z in face)))
               for face in original if all(p[0]<=10 for p in face)
               and any(p[0]<10 for p in face)]
        # Split the two vertical interface edges at the ledge height.
        split_right=[]
        for face in right:
            for i,a in enumerate(face):
                b,c=face[(i+1)%3],face[(i+2)%3]
                if a[0]==b[0]==10 and a[1]==b[1] and abs(a[2]-b[2])==12:
                    midpoint=(10,a[1],6)
                    split_right.extend([(a,midpoint,c),(midpoint,b,c)])
                    break
            else:
                split_right.append(face)
        mesh=left+split_right
        self.assert_closed(mesh)
        check=self.checks(mesh)['generator_cross_sections']
        self.assertEqual(check['status'],'fail')
        self.assertTrue(all(section['loop_count']==3 for section in check['evidence']))

    def test_wrong_volume_can_pass_finite_feature_samples(self):
        mesh=stepped_mesh(radius_factor=1.12); self.assert_closed(mesh)
        checks=self.checks(mesh)
        self.assertEqual(checks['generator_features']['status'],'pass')
        self.assertEqual(checks['generator_volume']['status'],'fail')

    def test_missing_step_same_bounds(self):
        # Lift the low ledge to full height, preserving a proper through-hole.
        original=stepped_mesh()
        mesh=[]
        for face in original:
            mapped=tuple((x,y,12 if z==6 else z) for x,y,z in face)
            if len(set(mapped))==3: mesh.append(mapped)
        self.assert_closed(mesh)
        checks=self.checks(mesh)
        self.assertEqual(checks['generator_features']['status'],'fail')
        self.assertEqual(checks['generator_volume']['status'],'fail')

    def test_extreme_bounded_aspect_ratios(self):
        for w,d,h in ((5,5,5),(100,100,100),(5,100,5),(100,5,100)):
            with self.subTest(w=w,d=d,h=h):
                checks=self.checks(stepped_mesh(w,d,h),self.request(w,d,h))
                self.assertTrue(all(c['status']=='pass' for c in checks.values()),checks)

    def test_unresolved_parity_blocks(self):
        with patch('printkit.validation.generator_checks.point_inside',return_value=None):
            checks=self.checks(stepped_mesh())
        self.assertEqual(checks['generator_features']['status'],'unknown')

    def test_coplanar_section_is_unknown_not_repaired(self):
        mesh=stepped_mesh()+[((1,1,3),(2,1,3),(1,2,3))]
        check=self.checks(mesh)['generator_cross_sections']
        self.assertEqual(check['status'],'unknown')
        self.assertIn('coplanar',check['evidence'][0]['reason'])

    def test_open_section_is_unknown_not_welded(self):
        mesh=stepped_mesh()
        # Remove a lower exterior wall triangle that intersects both planes.
        index=next(i for i,t in enumerate(mesh)
                   if len({p[2] for p in t})>1 and all(p[0]==0 for p in t))
        del mesh[index]
        check=self.checks(mesh)['generator_cross_sections']
        self.assertEqual(check['status'],'unknown')
        self.assertIn('degree-two',check['evidence'][0]['reason'])

    def test_budget_callback_propagates(self):
        def exhausted(): raise TimeoutError('deadline')
        with self.assertRaises(TimeoutError):
            check_generator(stepped_mesh(),self.request(),exhausted)

    def test_bad_contract_and_unsupported_generator_fail_closed(self):
        for value in (True,4,101,float('nan'),float('inf'),'20'):
            checks=self.checks([],self.request(value))
            self.assertEqual(checks['generator_contract']['status'],'fail')
            self.assertEqual(checks['generator_features']['status'],'unknown')
        checks=check_generator([],{'generator_id':'unimplemented'})
        self.assertTrue(all(c['required'] and c['status']=='unknown' for c in checks))
        self.assertEqual(check_generator([],{}),[])


if __name__ == '__main__': unittest.main()
