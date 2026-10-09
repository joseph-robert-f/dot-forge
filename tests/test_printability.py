"""Printability facts on small meshes built here, so no model files are needed."""
import io
import json
import math
from contextlib import redirect_stdout
from pathlib import Path
import struct
import tempfile
import unittest
from printkit import cli
from printkit.common import ForgeError
from printkit.printability import assess


def ears(polygon):
    """Triangulate a simple counter-clockwise polygon by ear clipping."""
    cross = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    inside = lambda p, a, b, c: cross(a, b, p) >= 0 and cross(b, c, p) >= 0 and cross(c, a, p) >= 0
    index, out = list(range(len(polygon))), []
    while len(index) > 3:
        for k in range(len(index)):
            i, j, m = index[k - 1], index[k], index[(k + 1) % len(index)]
            a, b, c = polygon[i], polygon[j], polygon[m]
            if cross(a, b, c) > 0 and not any(inside(polygon[n], a, b, c) for n in index if n not in (i, j, m)):
                out.append((i, j, m))
                index.pop(k)
                break
    out.append(tuple(index))
    return out


def prism(polygon, depth, offset=(0, 0, 0)):
    """A closed prism: polygon in xz (counter-clockwise seen from -y), extruded along +y."""
    ox, oy, oz = offset
    near = [(x + ox, oy, z + oz) for x, z in polygon]
    far = [(x + ox, oy + depth, z + oz) for x, z in polygon]
    tris = [(near[i], near[j], near[k]) for i, j, k in ears(polygon)]
    tris += [(far[i], far[k], far[j]) for i, j, k in ears(polygon)]
    for i in range(len(polygon)):
        j = (i + 1) % len(polygon)
        tris += [(near[i], far[i], far[j]), (near[i], far[j], near[j])]
    return tris


def box(x, y, z, offset=(0, 0, 0)):
    return prism([(0, 0), (x, 0), (x, z), (0, z)], y, offset)


def sphere(r, n=24):
    # Rounded so the poles and the seam share exact vertices.
    points = lambda i, j: tuple(round(v, 9) + 0.0 for v in (r * math.sin(math.pi * i / n) * math.cos(2 * math.pi * j / n),
                                                          r * math.sin(math.pi * i / n) * math.sin(2 * math.pi * j / n),
                                                          r * math.cos(math.pi * i / n)))
    tris = []
    for i in range(n):
        for j in range(n):
            a, b, c, d = points(i, j), points(i + 1, j), points(i + 1, j + 1), points(i, j + 1)
            if i > 0:
                tris.append((a, b, d))
            if i < n - 1:
                tris.append((b, c, d))
    return tris


def write(tris, folder, name="m.stl"):
    path = Path(folder) / name
    data = bytearray(80) + struct.pack("<I", len(tris))
    for t in tris:
        data += struct.pack("<12fH", 0, 0, 0, *[v for p in t for v in p], 0)
    path.write_bytes(bytes(data))
    return path


def statuses(report):
    return {c["code"]: c["status"] for c in report["checks"]}


class PrintabilityTests(unittest.TestCase):
    def assess(self, tris, **kwargs):
        with tempfile.TemporaryDirectory() as tmp:
            return assess(write(tris, tmp), **kwargs)

    def test_cube_is_sound_and_stands(self):
        report = self.assess(box(20, 20, 20))
        s = statuses(report)
        for code in ("closed_mesh", "orientation", "shells", "flat_base", "stands_up", "overhangs"):
            self.assertEqual(s[code], "pass", code)
        self.assertEqual(s["thin_features"], "no_findings")  # A sampled search never claims a pass.
        self.assertEqual(s["self_intersections"], "unknown")
        self.assertAlmostEqual(report["volume_mm3"], 8000, places=1)
        self.assertEqual(report["print_state"], "needs_review")
        self.assertEqual(report["state"], "needs_review")

    def test_leaning_figure_falls_over(self):
        lean = prism([(0, 0), (6, 0), (46, 25), (40, 25)], 10)
        report = self.assess(lean)
        self.assertEqual(statuses(report)["stands_up"], "fail")
        self.assertEqual(report["state"], "blocked")
        self.assertEqual(statuses(report)["overhangs"], "needs_review")

    def test_wide_top_on_a_post_needs_supports(self):
        tee = prism([(8, 0), (12, 0), (12, 20), (20, 20), (20, 24), (0, 24), (0, 20), (8, 20)], 10)
        check = next(c for c in self.assess(tee)["checks"] if c["code"] == "overhangs")
        self.assertEqual(check["status"], "needs_review")
        self.assertAlmostEqual(check["actual"]["area_mm2"], 160, places=3)

    def test_thin_fin_is_found(self):
        fin = prism([(0, 0), (20, 0), (20, 4), (10.5, 4), (10.5, 30), (10, 30), (10, 4), (0, 4)], 20)
        report = self.assess(fin, min_wall_mm=0.8)
        check = next(c for c in report["checks"] if c["code"] == "thin_features")
        self.assertEqual(check["status"], "needs_review")
        self.assertAlmostEqual(check["actual"]["min_mm"], 0.5, places=3)

    def test_open_mesh_leaves_dependent_checks_unknown(self):
        report = self.assess(box(10, 10, 10)[:-1])
        s = statuses(report)
        self.assertEqual(s["closed_mesh"], "fail")
        self.assertEqual(s["stands_up"], "unknown")
        self.assertEqual(s["thin_features"], "unknown")
        self.assertEqual(report["state"], "blocked")

    def test_loose_parts_and_bed_size(self):
        report = self.assess(box(10, 10, 10) + box(10, 10, 10, (20, 0, 0)), bed_mm=[25, 40, 40])
        s = statuses(report)
        self.assertEqual(s["shells"], "needs_review")
        self.assertEqual(s["fits_bed"], "pass")  # 30 x 10 fits when turned 90 degrees.
        self.assertEqual(statuses(self.assess(box(10, 10, 10), bed_mm=[5, 50, 50]))["fits_bed"], "fail")
        self.assertEqual(statuses(self.assess(box(10, 10, 10)))["fits_bed"], "unknown")

    def test_pinpoint_base_needs_review(self):
        wedge = prism([(9, 0), (11, 0), (20, 10), (0, 10)], 2)  # Touches the bed with 4 mm2.
        report = self.assess(wedge)
        self.assertEqual(statuses(report)["flat_base"], "needs_review")

    def test_ball_has_no_flat_base(self):
        report = self.assess(sphere(10))
        self.assertEqual(statuses(report)["flat_base"], "fail")
        self.assertEqual(statuses(report)["closed_mesh"], "pass")

    def test_cli_exit_codes_and_bad_options(self):
        with tempfile.TemporaryDirectory() as tmp:
            good, bad = write(box(10, 10, 10), tmp, "a.stl"), write(box(10, 10, 10)[:-1], tmp, "b.stl")
            for path, code in ((good, 5), (bad, 4)):
                out = io.StringIO()
                with redirect_stdout(out):
                    self.assertEqual(cli.main(["printability", str(path)]), code)
                self.assertEqual(json.loads(out.getvalue())["schema_version"], "printability.v1")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(["printability", str(good), "--min-wall", "0"]), 2)
            (Path(tmp) / "c.stl").write_bytes(b"not an stl")
            with self.assertRaises(ForgeError):
                assess(Path(tmp) / "c.stl")


if __name__ == "__main__":
    unittest.main()
