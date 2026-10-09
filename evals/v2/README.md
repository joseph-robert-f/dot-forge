# v2 field test

This test gives Dot Forge v2 thirteen requests that it has not seen before. It records how far each request goes through intent, plan and proof, and where the checker is wrong or blind.

Run on 2026-10-09 in a Debian 13 container with conda-forge FreeCAD 1.0.0 and Open CASCADE 7.8.1. The runtime gate was not changed. The results are not yet confirmed on a Dot.

The results below use the checker after the field-test fixes and after commit `450095d` (full-aperture hole ends). That commit decides that a hole which opens into another void, not to the outside, is neither through nor blind. Such a hole is `unknown`, and it blocks.

## How the test was made

- The evaluator acted as the Dot. For each request, the evaluator wrote a draft intent, the questions a Dot must ask, and a first plan. All of this was done before any build.
- The evaluator also simulated the user's answers and the confirmation. Each intent says this in `confirmation.note`. No person confirmed these intents.
- The evaluator knew how the checker works. This can make the intents fit the checker better than a real Dot's would.
- Each case also has realistic wrong plans in `mutants/`. A mutant tests whether the checker catches a plan mistake.

## Files

| Path | Contents |
| --- | --- |
| `make_cases.py` | Writes every intent, plan and mutant. Edit this file, not the JSON. |
| `run_cases.py` | Builds every attempt and mutant into a new directory and prints one line for each. |
| `cases/<case>/intent.json`, `plan-001.json` | The first attempt |
| `cases/<case>/intent-00N.json`, `plan-00N.json` | Later attempts, after a changed intent |
| `cases/<case>/mutants/*.json` | Wrong plans for the first intent |
| `cases/index.json` | The ask, the questions, and the check counts for each case |

To run the test on your Dot:

```sh
PYTHONPATH=src python3 evals/v2/make_cases.py
PYTHONPATH=src python3 evals/v2/run_cases.py build/field-test
```

## Results

### First attempts

| Case | What it tests | Before the fixes | Now |
| --- | --- | --- | --- |
| l-bracket | Holes on two axes | conforms | conforms |
| counterbored-spacer | Blind counterbore over a clearance hole | blocked, and **a false hole for a person** | blocked: `counterbore` is unknown (opens into the clearance hole) |
| cable-clip | Open cable channel | conforms | conforms |
| box-lid | Lip size as face offsets | conforms | conforms |
| phone-stand | Main requirement is an angle | conforms | conforms |
| tube | Bore through a round part | conforms, **with a false hole for a person** | conforms |
| shaft-collar | Side hole into a bore | **exit 3, checker bug** | blocked: `set-screw` is unknown (opens into the bore) |
| slotted-plate | Slot with round ends | conforms | conforms |
| shelf-bracket | Brace and holes on two axes | conforms | conforms |
| spur-gear | Involute teeth and a D-shaft bore | blocked | blocked (correct: the intent was wrong) |
| hollow-ball | Sealed cavity | **intent said conforms**; the STL check blocked it | blocked by `native_solid` (correct) |
| sd-card-box | Vague ask | stops at questions | stops at questions |
| bottle-cap | Threads | stops: no operation can make a thread | same |

Three correct parts block today: the spacer, the collar and the drained ball. In each, a hole opens into another void. The checker is not wrong about what it measured. The intent has no way to ask for such a hole.

### Repairs

| Case | Attempt | Change | Result |
| --- | --- | --- | --- |
| spur-gear | 002 | A D-bore is not a full cylinder, so it moved from a measured hole to a person check | conforms |
| hollow-ball | 002 | The user accepted a 3 mm drain hole, so the part has one shell | blocked: the drain trims the bottom, and the intent still said 40 mm tall |
| hollow-ball | 003 | The intent height is 39.94 mm | blocked: `drain` is unknown (opens into the cavity) |

Attempt 002 of the hollow ball was the evaluator's own mistake. The checker caught it.

### Wrong plans

A wrong plan is caught only if the correct plan passes. Five of the eleven wrong plans meet that test.

| Mutant | Result |
| --- | --- |
| l-bracket: wall hole at 15 mm, not 16.5 mm | caught by `wall-hole` |
| box-lid: lip with no clearance | caught by all four lip faces |
| phone-stand: 70 degrees, not 60 | caught by `envelope` only |
| tube: inside diameter 22 mm | caught by `bore`, `volume` and both ends |
| shelf-bracket: shelf holes on the centre line | caught by `shelf-1` and `shelf-2` |
| counterbored-spacer: counterbore 4 mm deep | blocked, but the correct spacer also blocks |
| counterbored-spacer: counterbore from the bottom | blocked, but the correct spacer also blocks |
| shaft-collar: set-screw hole stops short of the bore | blocked, but the correct collar also blocks |
| cable-clip: no cable channel | **not caught** |
| shelf-bracket: no brace | **not caught** |
| slotted-plate: slot 25 mm long, not 20 mm | **not caught** |

Each miss is a requirement that only a person check covers, or that a minimum face area cannot limit. The report still sends the note to a person, so a careful person can find the mistake in the views. The phone-stand angle was caught only because the Dot's proposed envelope came from the 60 degree shape.

## Checker bugs found and fixed

1. **Loose bounding box.** FreeCAD's plain `BoundBox` includes trim-curve tolerance. On the shaft collar it was 1.3 µm outside the surface, so the STEP copy measured differently and the build stopped with exit 3. All envelopes and positions used this frame. The measurer now uses the exact optimal bounding box.
2. **Loose hole span.** A hole span came from the face parameter range, which follows the approximated trim curve. On the collar's side hole it was 1 µm loose. For an axis-aligned hole, the span now comes from the exact face extent.
3. **Outer wall read as a hole.** A cylinder was called a void when a point on its axis was outside the solid. Around a bore, that point is in the bore, so the outer wall of a tube, spacer or collar was reported as an unrequested hole. A cylinder is now a void when its outward face normal points toward its axis.
4. **Counterbore read as through.** The end probe was on the axis. Below a counterbore, it fell into the clearance hole, so the blind counterbore read as open at both ends. Commit `450095d` replaced the probe with full-aperture checks. The counterbore end is now unknown, not open. The field test's own fix for this was dropped in the merge.
5. **Sealed cavity passed the intent check.** `native_solid` counted solids but not shells. A hollow ball is one solid with two shells. The measurer now reports `shell_count`, and `native_solid` requires one shell for each solid. The STEP round trip also compares shell counts.

The native tests now include the tube, the collar and the hollow ball.

## Gaps found, not fixed

These change the intent contract, so they need a decision first.

| Gap | Seen in | Possible change |
| --- | --- | --- |
| A hole that opens into another void is neither through nor blind | counterbore, set-screw hole, drain hole | An end kind for "opens into a void", or counterbore and cross-hole features |
| A partial cylinder cannot be a measured feature | cable channel, slot ends, D-bore | A feature for a partial cylindrical void: axis, diameter, position and minimum arc |
| A face check has a minimum area but no maximum | slot length | Optional `max_area_mm2` on `planar_face` |
| No angled faces | phone-stand angle | A `planar_face` with a normal vector |
| A draft intent must have an envelope, so the Dot uses a placeholder such as `[1, 1, 1]` | sd-card-box, bottle-cap | Allow a draft without an envelope |
| Every feature needs a `source` from the ask | cable-clip size, lid clearance, collar fit | Record the user's answers in the intent, and let a feature cite an answer |
| `confirmation.by` must be `user` | all cases | A test fixture cannot say that its confirmation is simulated, except in a note |

## What did not need a change

- Questions came before geometry in every case with an unknown that changes the part.
- The build refused the two draft intents with exit 2 (`intent_unconfirmed`).
- No case needed a new plan operation. The 16 operations built all eleven parts.
- Builds took 1 to 6 seconds, and the hollow ball took about 19 seconds.
