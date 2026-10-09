# Printability field check

Two figures test the printability check on character-like meshes. `make_figures.py` builds them in FreeCAD from simple shapes, so no third-party character model is downloaded or shared. Generated STL files stay out of Git.

```sh
python3 evals/printability/make_figures.py build/figures        # FreeCAD's Python
PYTHONPATH=src python3 -m printkit printability build/figures/figure.stl --bed 220 220 250
PYTHONPATH=src python3 -m printkit printability build/figures/figure-no-base.stl --bed 220 220 250
```

Run on 2026-10-09 with FreeCAD 1.0.0 in a Debian 13 container. Each mesh has 13,196 triangles.

| Check | figure.stl (on a round base, thin sword) | figure-no-base.stl (no base, leans 18°) |
| --- | --- | --- |
| closed_mesh, orientation, shells | pass, one shell | pass, one shell |
| flat_base | pass, 615 mm² | **fail**, 0 mm² |
| stands_up | pass, tips at 42° | **fail**, centre of mass 0.4 mm outside the footprint |
| overhangs | needs_review, 94 mm² (arm and head) | needs_review, 332 mm² |
| thin_features | needs_review, sword 0.60 mm | needs_review, 0.56 mm |
| Exit code | 5 | 4 |
| Time | 0.3 s | 0.4 s |

The thinnest points in `figure.stl` are on the 0.6 mm sword, as built. A synthetic sphere of 295,680 triangles took 42 seconds and 411 MB.
