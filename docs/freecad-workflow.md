# FreeCAD: a dimensioned stepped part

Use this workflow on a Dot's Linux cloud computer for the reviewed `freecad-stepped-block` family. The native profile is **FreeCAD 1.0.0 / Open CASCADE 7.8.1**, with **Blender 4.3.2** rendering the actual exported STL. Applications are separately installed prerequisites. The bounded workflow is verified on the documented profile; see [verification evidence](freecad-verification.md). Run fresh smoke acceptance on every other Dot’s computer.

## Copy this to your Dot

> Use Dot Forge's FreeCAD workflow on your Linux cloud computer to make the stepped part with its vertical through-hole. Read the repository instructions, inspect your installed applications, and run the FreeCAD doctor and a fresh smoke example. Do not silently download anything. Ask only for missing overall dimensions in millimeters and intended-use details that affect the result. Generate a fresh candidate, check the native solid and STEP round trip, independently validate the exported STL, and review front, side, back, top and oblique views. Explain all remaining printer, slicer and physical checks. Give me FCStd, STEP, STL, previews and evidence in a verified durable bundle.

## The supported shape

Width, depth and overall height are each **5–100 mm**, inclusive. The request parameters are `width_mm`, `depth_mm` and `height_mm`. Matching requested dimensions must follow the request contract.

- One integral solid with a full-width, full-depth base at half the overall height.
- A raised step on the right half of the width, reaching the overall height.
- A vertical Z-axis through-hole in the lower left ledge, centered at one quarter of the width and half the depth.
- Hole radius is the smaller of width / 8 and depth / 6; it is not an independently adjustable parameter.

The topology and proportions are fixed. This is a dimensioned CAD-solid family, not arbitrary mechanical design, general text-to-CAD or an assembly workflow. Use the Blender family for the supported flat robot mascot. A different functional part needs a separately reviewed generator and checks appropriate to its use.

## Commands for the Dot

From a reviewed repository checkout on the Linux computer:

```sh
export PYTHONPATH="$PWD/src"
python -m unittest discover -s tests -v
python -m printkit doctor --backend freecad --json
python -m printkit doctor --backend freecad --json --smoke build/freecad-smoke-001
python -m printkit check-request examples/freecad-stepped-part/request.json
python -m printkit run --request examples/freecad-stepped-part/request.json --output build/freecad-part-001
python -m printkit inspect --run build/freecad-part-001
```

Use a fresh path for each attempt. Discovery alone is unverified. Read the smoke report and inspect its actual artifacts before relying on capability. If a required runtime or check is unavailable, report the exact blocker; do not skip the check or silently replace the profile. Exit code 5 means manual/printing review remains; inspect the report rather than treating it as an internal error.

The adapter uses the installed native FreeCAD Python modules through system Python, rather than assuming a GUI or launcher proves headless capability. Blender supplies preview rendering only; the authoritative part is built by FreeCAD, and the views come from its exported printing mesh.

## What the evidence must establish

1. **Native solid:** finite requested dimensions, one closed valid BRep solid, expected dimensions and analytic volume, and the expected base, raised step and through-hole.
2. **Fresh round trip:** reopen FCStd and import STEP in a fresh process. Recheck solid validity, dimensions, volume and feature probes. Independently measure each native artifact’s analytic cylinder and its complete circular rims: hole center, radius, axis and full lower-ledge extent must match within the recorded native tolerances (1e-6 mm linear, 1e-9 radians angular). File existence is insufficient.
3. **Independent printing-mesh checks:** parse the actual exported STL separately from FreeCAD. Check finite coordinates, dimensions, topology, connected solid-shell structure, intersections, analytic-volume agreement within the defined mesh tolerance and required-feature probes.
4. **Five-view review:** inspect the actual STL from front, side, back, top and oblique viewpoints. Confirm the step and hole as well as the overall form. The user's visual approval remains separate.

A native-solid pass cannot substitute for the STL checks. Feature probes inspect selected locations; they do not prove every local wall thickness, clearance or intended-use requirement. Tessellation approximates the curved hole, so retain recorded settings and tolerances. A required check that is skipped, unavailable, crashes or exhausts its work budget remains unresolved and cannot establish geometry acceptance.

## Files to keep

- `native/model.FCStd`: editable native CAD solid with dimension metadata
- `exports/model.step`: exchange-format CAD solid
- `exports/model.stl`: printing candidate, subject to remaining print checks
- `previews/`: five exported-STL views and their contact sheet
- Request, native-check evidence, validation report, manifest and source/runtime provenance

The FCStd contains a native solid, not a full history-based parametric feature tree. Its dimension properties record the generator inputs; changing them alone does not rebuild the shape. For a supported size change, edit the request and regenerate into a new attempt.

Create and verify the portable bundle separately:

```sh
python -m printkit bundle --run build/freecad-part-001 --output build/freecad-part-001.zip
python -m printkit verify-bundle build/freecad-part-001.zip
```

Verify after transfer too. Persist through an authorized durable artifact destination and verify access before calling delivery complete. A ZIP or manifest can preserve a blocked run; packaging success does not validate its geometry.

## What remains unknown

Unless the particular run supplies separate evidence, printer/process/material suitability, build-envelope fit, wall and clearance suitability, orientation/support choices, slicer/toolpath behavior and physical-print success remain unknown. Functional fit, load capacity and safety suitability also need their own assessment. Do not describe this candidate as universally print-ready.

See [acceptance](acceptance.md), [validation explained](validation-explained.md) and [recovery](recovery.md). FreeCAD results do not resolve the separate Lane A Blender 4.5.12 gate.

The independent exported-mesh gate also measures two lower-body cross-sections. It requires closed outer/hole loops and checks hole center within 0.05 mm and diameter within 0.10 mm, plus small floating-point allowances. These are explicitly tessellation-limited checks for this generator, not a certification of every surface or printed fit.
