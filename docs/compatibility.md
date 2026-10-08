# Compatibility

| Route | Required runtime | Scope | Release status |
| --- | --- | --- | --- |
| Original native examples | Blender 4.3.2; Linux x86_64 | Calibration block and geometric mascot; STL, BLEND and five-view preview | Bounded preview; run local smoke acceptance |
| Pinned upstream Lane A | Blender 4.5.12 LTS; pinned selected source | Adapter to upstream CLI | Blocked: exact runtime unavailable in release environment |
| Python orchestration | Python 3.11+ | Standard-library runtime | Run source tests on the selected interpreter |
| Other Blender versions/platforms | Unspecified | No compatibility promise | Untested/incompatible with pinned profile |
| FreeCAD / 3D Slicer / slicer toolpaths | No accepted profile | Roadmap only | Deferred |

A discovered executable is not an accepted capability. Runtime locks record the tested identity and provenance limits. Geometry validation, human visual assessment, slicer evidence and physical results are separate dimensions of compatibility.

See [acceptance](acceptance.md) for release claims and [runtime setup](runtime-setup.md) for the unresolved Lane A gate.
