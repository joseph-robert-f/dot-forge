# Printability check (any STL)

Use this check for a character, a figure, a sculpt or a downloaded model. It answers one question: will this mesh print and survive? It does not answer "does it look right?". A person decides likeness and style.

The check reads one STL file. It does not need FreeCAD, Blender or a network connection. It does not change the file.

## When to use it

| The request is about | Use |
| --- | --- |
| Sizes, holes, fits, mounts, brackets, enclosures | The v2 workflow (intent, plan, proof). See [v2-intent-and-plan.md](v2-intent-and-plan.md). |
| A character, a figure, a sculpt, a decoration | This printability check, plus the person's approval of the look |
| Both: for example, a figure with a magnet pocket | v2 for the measured parts. Write the look as a note. Run the printability check on the exported STL too. |

## Run it

```sh
PYTHONPATH=src python3 -m printkit printability model.stl --bed 220 220 250
```

| Option | Default | Meaning |
| --- | --- | --- |
| `--bed X Y Z` | none | Printer build volume in mm. Without it, `fits_bed` is unknown. |
| `--min-wall` | 0.8 | Thinnest part that you accept, in mm. 0.8 mm is two lines of a 0.4 mm FDM nozzle. Use the value for your printer. |
| `--overhang-deg` | 45 | A face that leans more than this past vertical, and that is not on the bed, is an overhang. |
| `--samples` | 600 | Number of surface points for the thin-part search |

Exit codes: `5` means no check failed, and a person must still review. `4` means a check failed. `2` means the file or an option is not valid.

## What it checks

The report states its assumptions: units are mm, +z is up, and the lowest point sits on the bed. Turn the model before the check if it prints in a different orientation.

| Check | Method | Result |
| --- | --- | --- |
| `closed_mesh` | Each edge has exactly two faces | `pass` or `fail` |
| `orientation` | Each edge is used once in each direction | `pass`, `fail` or `unknown` |
| `shells` | Connected faces; signed volume of each shell | `pass` for one shell; `needs_review` for loose parts |
| `self_intersections` | Not checked | Always `unknown`. The slicer shows these. |
| `fits_bed` | Bounding box against `--bed`, upright, may turn 90° | `pass`, `fail` or `unknown` |
| `flat_base` | Area of downward faces within 0.05 mm of the lowest point | `pass` at 10 mm² or more; `needs_review` below; `fail` at 0 |
| `stands_up` | Centre of mass (uniform density) against the footprint on the bed | `fail` if outside; `needs_review` if it tips at less than 5° |
| `overhangs` | Faces that lean past `--overhang-deg`, off the bed | `needs_review` with area and height range |
| `thin_features` | An inward ray from each sample point to the opposite surface | `needs_review` with the thinnest points; `no_findings` if none found |
| `hollow_and_drain` | Not checked | Always `unknown`. Important for resin prints. |

`no_findings` is not a pass. The thin-part search uses samples, so it can miss a small thin spot. The person checks always include the look, the print settings and a test print. `print_state` is always `needs_review`.

## Limits

- Up to 300,000 triangles and 64 MB. Decimate a larger mesh first. A 100,000-triangle mesh takes about 6 seconds; 300,000 takes about 40 seconds.
- The check does not judge likeness, style, proportions or detail.
- The check does not repair a mesh. Repair it in your tools and run the check again.
- Uniform density is assumed. A hollow or infilled print can balance differently.
