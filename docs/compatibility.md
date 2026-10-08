# Linux compatibility

Dot Forge is source and premade modeling instructions for a dot's **Linux x86_64 cloud computer**. It is not a desktop application, cross-platform installer or bundled modeling runtime. Each dot must verify its actual computer before use; applications available on one dot are not guaranteed on another.

| Route | Required native runtime | Bounded scope | Acceptance status |
| --- | --- | --- | --- |
| Original Blender examples | Blender 4.3.2 | Calibration block and flat extruded robot; STL, BLEND and five exported-STL views | Existing native preview evidence; fresh smoke required on each computer |
| FreeCAD solid | FreeCAD 1.0.0 / Open CASCADE 7.8.1; Blender 4.3.2 for STL views | One stepped block with through-hole; FCStd, STEP and STL | Verified native/STEP/STL workflow; fresh doctor smoke still required on another computer |
| Pinned upstream Lane A | Blender 4.5.12 LTS and pinned selected source | Adapter to upstream CLI | Blocked: official exact-runtime retrieval returned HTTP 403 |
| Python orchestration | Python 3.11+ | Standard-library CLI; native applications remain separate | Run source tests on the selected interpreter |
| Other runtime versions or operating systems | No accepted profile | Outside this Linux instruction set | No compatibility claim |
| 3D Slicer / slicer toolpaths | No accepted profile | Separate future work | Deferred |

The FreeCAD route uses the installed native FreeCAD Python modules through system Python. An installed graphical app or a `freecadcmd` version string alone does not prove those modules are usable. The complete preview workflow also needs the specified Blender runtime to render the exported STL. See [FreeCAD workflow](freecad-workflow.md).

Runtime discovery and a real generation/export/reopen/validation/render smoke run are different checks. Inspect the report for the exact source, request and runtime tested. Runtime hashes identify observed files; they do not establish vendor archive verification or compatibility with another installation.

No modeling command silently downloads or upgrades applications. Missing prerequisites should produce a clear blocker and an authorized setup step. Geometry validation, visual approval, named slicer evidence and physical results remain separate even when all native applications are present.

See [acceptance](acceptance.md) for evidence boundaries and [runtime setup](runtime-setup.md) for prerequisites and the unresolved Lane A gate.
