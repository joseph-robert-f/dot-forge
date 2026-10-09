"""Build two small figures in FreeCAD and export fine STL meshes for the printability check.

Run with FreeCAD's Python: python3 evals/printability/make_figures.py OUTPUT_DIR
The figures are made here, so no third-party character model is downloaded or shared.
- figure.stl: a figure on a round base, holding a thin sword out to one side.
- figure-no-base.stl: the same figure without its base, leaning forward.
"""
import sys
from pathlib import Path
sys.path.insert(0, '/usr/lib/freecad/lib')
import FreeCAD as App  # noqa: E402
import MeshPart  # noqa: E402
import Part  # noqa: E402

V = App.Vector


def figure(base=True, lean=0.0):
    body = Part.makeCone(9, 6, 26, V(0, 0, 4))
    head = Part.makeSphere(7, V(0, 0, 36))
    ears = [Part.makeCone(2.5, 0.2, 6, V(x, 0, 41), V(0, 0, 1)) for x in (-4, 4)]
    arm = Part.makeCylinder(1.8, 14, V(5, 0, 22), V(1, 0, -0.4))
    sword = Part.makeCylinder(0.3, 22, V(17, 0, 17), V(0.2, 0, 1))
    hilt = Part.makeBox(1.2, 4, 1.2, V(16.8, -2, 16.4))
    parts = [body, head, arm, sword, hilt] + ears
    if base:
        parts.append(Part.makeCylinder(14, 4))
    else:
        parts.append(Part.makeCylinder(6, 4))
    shape = parts[0].fuse(parts[1:]).removeSplitter()
    if lean:
        shape.rotate(V(0, 0, 0), V(0, 1, 0), lean)
    return shape


def export(shape, path):
    mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.02, AngularDeflection=0.1, Relative=False)
    mesh.write(str(path))
    return mesh.CountFacets


out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
print('figure.stl', export(figure(), out / 'figure.stl'))
print('figure-no-base.stl', export(figure(base=False, lean=18), out / 'figure-no-base.stl'))
