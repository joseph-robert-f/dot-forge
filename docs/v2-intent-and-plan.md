# Dot Forge v2: intent, plan, proof (preview)

v2 lets you make an open-ended part in FreeCAD. It does not limit you to the three reviewed generators. Instead, it controls how a part is described and how the result is checked.

> **Status: preview.** The intent and plan contracts, the conformance checks and the CLI are tested without FreeCAD. The FreeCAD interpreter and measurer (`src/printkit/adapters/freecad_plan_scene.py`) pass the native tests (`tests/test_v2_freecad_native.py`) with conda-forge FreeCAD 1.0.0 and OCC 7.8.1 in a Debian 13 container. They passed on a Dot's exact runtime profile at commit `09128ea`. The measurer changed after that (see the [field test](../evals/v2/README.md)), so run the native tests again on your Dot. After a change to the helper, run `PRINTKIT_FREECAD_INTEGRATION=1 PYTHONPATH=src python3 -m unittest tests.test_v2_freecad_native -v` on your Dot before you trust a v2 result. Five-view previews and evidence bundles are not connected to v2 yet.

## The three files

| File | Who writes it | What it holds |
| --- | --- | --- |
| `intent.json` | The assistant, then the user confirms it | The ask as checks you can measure. Unstated values go in `unknowns`. |
| `plan.json` | The assistant | A FreeCAD feature tree. It is data, not code. It is bound to one intent by hash. |
| `report.json` | Dot Forge | Each intent check with its measured result. The independent STL checks. The open items. |

The plan is judged against the intent, not against itself. A plan can build exactly what it says and still fail, because the intent asked for something else.

## Procedure

1. Write the user's ask into `intent.json`. Use `"confirmation": {"status": "draft"}`.
   - Put each dimension and feature that the ask states as a measurable feature.
   - Put each requirement that you cannot measure as a `note`. A person checks notes.
   - Put each value that the ask does not state in `unknowns`. Do not invent a value.
2. Check the intent:
   ```sh
   python -m printkit check-intent intent.json
   ```
   The result lists the measured checks, the person checks and the unknowns.
3. Show the intent to the user. Ask about each unknown that changes the part.
4. When the user agrees, set `"confirmation": {"status": "confirmed", "by": "user"}`. Do not confirm for the user.
5. Write `plan.json`. Set `intent_sha256` to the `intent_sha256` value from step 2. Run `check-intent` again after any change to the intent, because the hash changes.
6. Check the plan:
   ```sh
   python -m printkit check-plan plan.json --intent intent.json
   ```
   A warning means that a step does not contribute to the result.
7. Build into a new run directory:
   ```sh
   python -m printkit build --intent intent.json --plan plan.json --output build/plate-001
   ```
8. Read `build/plate-001/report.json`:
   - `intent_state`: `conforms` or `blocked`. This answers "is it the part the user asked for?"
   - `geometry_state`: the independent STL checks. This answers "is the exported mesh sound?"
   - `print_state`: always `needs_review`. Dot Forge does not decide print readiness.
   - `person_checks`: the items that a person must do.
   - If FreeCAD cannot build a step (for example, a fillet that is too large), `build` exits 4 with `plan_step_failed`. The message and `native/plan-failure.json` name the step and the FreeCAD error.
9. If a check fails, do not edit the run. Change the plan (or, with the user, the intent) and build into a new run directory. Keep the failed run.

Exit codes: `0` pass, `2` invalid input, `3` FreeCAD unavailable, `4` blocked, `5` built and conforming, but person and print review is still open.

## Intent features

All positions are in mm from the **minimum corner of the part's bounding box**. The plan can put the part anywhere. The checks measure relative to the part.

| Kind | Measured how | Fields |
| --- | --- | --- |
| `envelope` (top level) | Bounding box of the solid | `size_mm` [x, y, z], `tolerance_mm` |
| `volume_mm3` (top level, optional) | Solid volume | `min`, `max` |
| `hole` | A full cylindrical void on an axis. Full-aperture B-rep checks decide what each end opens into. | `axis`, `diameter_mm`, `position_mm`, `depth`, `tolerance_mm` |
| `partial_hole` | A cylindrical void that does not go all the way around, on an axis. An exact section at the middle of its length gives the arc. | `axis`, `diameter_mm`, `position_mm`, `min_arc_deg`, optional `max_arc_deg` and `length_mm`, `tolerance_mm` |
| `planar_face` | Sum of flat face areas with this outward normal at this offset | `normal`, `offset` (`min`, `max` or mm), `min_area_mm2`, optional `max_area_mm2`, `tolerance_mm` |
| `note` | Not measured. A person compares the views with the text. | `text` |

Hole position: for axis `z`, use `[x, y]`. For axis `y`, use `[x, z]`. For axis `x`, use `[y, z]`.
Partial hole: use it for a channel, a round slot end or a D-bore. Position and diameter work as for a hole. The arc is the part of the circle that is wall, in degrees, measured at the middle of the length: a half-round slot end is 180, and a 5 mm D-bore with a flat 4.5 mm from the far side is 286. Set `min_arc_deg` and `max_arc_deg` around the arc you expect. A full circle is never a partial hole, so a channel cut without its opening fails, and the full hole goes to `unrequested_holes`. A cross hole at the middle of the length reduces the measured arc.

Face area: the check adds up every flat face with the same outward normal at the same offset. `min_area_mm2` catches a face that is missing or too small. `max_area_mm2` catches a face that is too big, for example the wall of a slot that is too long. Set the maximum from all the faces at that offset, not from one face.

Hole depth has three forms:

- `"through"`: both ends open to the outside of the part.
- `{"depth_mm": 8, "open_end": "max"}`: a blind hole that opens on the high side of the axis and has a filled floor.
- `{"ends": {"min": "outside", "max": "void"}}`: name what each end opens into. Use this form for a counterbore, a set-screw hole into a bore, or a drain hole into a cavity. Add `"depth_mm"` to check the hole length.

| End | Meaning | Proof |
| --- | --- | --- |
| `outside` | Clear to the outside of the part | The full aperture is clear from the end to beyond the part |
| `floor` | A filled end | A thin cap of the full aperture past the end is all material |
| `void` | Empty space inside the part, such as a bore or a cavity | The full aperture is clear for 0.5 mm past the end, but not to the outside |
| `shoulder` | A filled step around a narrower coaxial hole, such as a counterbore floor | The ring between the narrower hole and the wall is all material, and the narrower opening is clear |

One end must be `outside`. Each end must match exactly. An end that has no proof is `unknown` and blocks. A counterbore is two features: the narrow hole (`"through"`) and the wide hole (`{"ends": {"min": "shoulder", "max": "outside"}, "depth_mm": 5}`). Where a hole meets a curved face, its length is measured to the farthest point of the edge, so leave out `depth_mm` for a `void` end.

Hole tolerance applies to the **diameter**, each position coordinate, and blind depth in mm. A through hole requires the whole measured cylindrical aperture to be clear, including its continuation to the outside of the part on both ends. A blind end requires a completely filled end cap. Partial obstruction (such as a wide counterbore above a narrower through-hole), interrupted apertures, or unsuccessful B-rep checks remain `unknown` and block conformance; they do not count as a blind floor. This applies to `"through"` and blind depths. Use the `ends` form to ask for a counterbore or a hole into a void. Countersinks (conical) are not measured.

Each measured hole can satisfy only one feature. A full hole that no feature asked for goes to `person_checks` as `unrequested_holes`. A partial cylinder (for example, a fillet) is never counted as a hole.

## Plan operations

Each step has an `id` and an `op`. A step can refer only to earlier steps.

| Op | Makes |
| --- | --- |
| `box`, `cylinder`, `cone`, `sphere` | Primitives. `at_mm` is the box minimum corner, or the base center, or the sphere center. |
| `extrude` | A simple polygon in `xy`, `xz` or `yz`, extruded along +z, +y or +x |
| `revolve` | A `[radius, z]` profile revolved about a vertical axis |
| `union`, `intersect`, `cut` | Booleans |
| `translate`, `rotate`, `mirror` | Moved copies |
| `linear_pattern`, `polar_pattern` | Unions of 2–64 copies (256 copies in total per plan) |
| `fillet`, `chamfer` | Round or bevel `all` edges, or straight edges `parallel_x`, `parallel_y` or `parallel_z` |

Tips:
- Make cutting tools longer than the body by about 1 mm on each side. A coplanar cut can leave a thin skin.
- Round or bevel a blank before you cut holes into it. Then the edge selector only finds the edges you mean.

See `schemas/intent.v1.json`, `schemas/plan.v1.json` and the two examples:
- `examples/v2/stepped-block`: the v1 FreeCAD generator, written as a plan.
- `examples/v2/mounting-plate`: an open-ended ask that v1 could not express. It has four screw holes, a flat bottom and rounded corners.
- `examples/v2/knob`: a revolved knob with a blind shaft hole from below and twelve grip notches.

## Limits

- One solid only. Assemblies and sealed cavities are not supported. `native_solid` requires one shell for each solid.
- Features measured today: envelope, volume, axis-aligned cylindrical holes, axis-aligned partial holes and axis-aligned flat faces. Other requirements (fillet radius, wall thickness, text, threads, angled holes and faces) are notes for a person. They are never a pass. A partial cylinder is never a full hole.
- A confirmed intent is a process record, not a signature. The tool cannot prove that the user saw it.
- The STL check allows the envelope tolerance plus 0.05 mm, because mesh vertices on curved faces can sit inside the true surface.
- The plan is interpreted by fixed code, but FreeCAD still runs without network or filesystem isolation. See [SECURITY.md](../SECURITY.md).
