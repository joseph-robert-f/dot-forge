"""Write the v2 field-test cases: one intent and first plan per request.

Run from the repository root: PYTHONPATH=src python3 evals/v2/make_cases.py
Each case is what a Dot would draft for the ask, written before any build.
Confirmation is simulated for the evaluation; see evals/v2/README.md.
"""
import json
import math
from pathlib import Path
from printkit.common import canonical_hash
from printkit.intent import check_intent, summarize
from printkit.plan import check_plan

ROOT = Path(__file__).resolve().parent / "cases"
SIMULATED = {"status": "confirmed", "by": "user",
             "note": "Evaluation fixture. The evaluator simulated this confirmation and the answers to the open questions."}
T = 0.05


def hole(id, axis, d, pos, depth="through", source=""):
    return {"id": id, "kind": "hole", "axis": axis, "diameter_mm": d, "position_mm": pos,
            "depth": depth, "tolerance_mm": T, "source": source}


def partial(id, axis, d, pos, arc, length=None, source=""):
    """A partial cylindrical void: arc is (min, max) in degrees at mid-length."""
    out = {"id": id, "kind": "partial_hole", "axis": axis, "diameter_mm": d, "position_mm": pos,
           "min_arc_deg": arc[0], "max_arc_deg": arc[1], "tolerance_mm": T, "source": source}
    if length:
        out["length_mm"] = length
    return out


def face(id, normal, offset, area, source=""):
    return {"id": id, "kind": "planar_face", "normal": normal, "offset": offset,
            "min_area_mm2": area, "tolerance_mm": T, "source": source}


def note(id, text, source=""):
    return {"id": id, "kind": "note", "text": text, "source": source}


def intent(ask, size, features, unknowns, volume=None, questions=(), status=SIMULATED):
    out = {"schema_version": "intent.v1", "units": "mm", "ask": ask, "confirmation": status,
           "envelope": {"size_mm": size, "tolerance_mm": T}, "solid_count": 1,
           "features": features, "unknowns": list(unknowns)}
    if volume:
        out["volume_mm3"] = {"min": volume[0], "max": volume[1]}
    return out, list(questions)


def plan(steps, result, notes=None):
    out = {"schema_version": "plan.v1", "units": "mm", "steps": steps, "result": result}
    if notes:
        out["notes"] = notes
    return out


def gear_points(teeth=20, module=1.0, pressure_deg=20.0):
    """Involute spur gear outline, 5 points per flank, centred on the origin."""
    rp, ra, rf = teeth * module / 2, teeth * module / 2 + module, teeth * module / 2 - 1.25 * module
    rb = rp * math.cos(math.radians(pressure_deg))
    inv = lambda a: math.tan(a) - a
    half = math.pi * module / 2 / 2 / rp + inv(math.radians(pressure_deg))
    theta = lambda r: half - inv(math.acos(min(1.0, rb / r)))
    radii = [rb, (rb + rp) / 2, rp, (rp + ra) / 2, ra]
    flank = [(rf, theta(rb))] + [(r, theta(r)) for r in radii]
    points = []
    for k in range(teeth):
        c = 2 * math.pi * k / teeth
        side = [(r, c - t) for r, t in flank] + [(r, c + t) for r, t in reversed(flank)]
        points += [[round(r * math.cos(a), 4), round(r * math.sin(a), 4)] for r, a in side]
    return points


CASES = {}

# 1. Two-axis holes on an L bracket.
CASES["l-bracket"] = (
    intent("I need an L bracket to screw a shelf support into a corner. Both legs 30 mm long, 20 mm wide, "
           "3 mm thick. One 4.5 mm screw hole in the middle of each leg.",
           [30, 20, 30],
           [hole("base-hole", "z", 4.5, [16.5, 10], source="one 4.5 mm screw hole in the middle of each leg"),
            hole("wall-hole", "x", 4.5, [10, 16.5], source="one 4.5 mm screw hole in the middle of each leg"),
            face("base-bottom", "-z", "min", 550, "legs 30 mm long, 20 mm wide"),
            face("wall-back", "-x", "min", 550, "legs 30 mm long, 20 mm wide")],
           ["screw head type", "load on the bracket", "inside corner fillet", "printer and material"],
           questions=["Middle of the whole leg (15 mm) or middle of the flat part past the other leg (16.5 mm)? "
                      "Simulated answer: the flat part."]),
    plan([{"id": "base", "op": "box", "size_mm": [30, 20, 3]},
          {"id": "wall", "op": "box", "size_mm": [3, 20, 30]},
          {"id": "body", "op": "union", "of": ["base", "wall"]},
          {"id": "drill-base", "op": "cylinder", "radius_mm": 2.25, "height_mm": 5, "at_mm": [16.5, 10, -1]},
          {"id": "drill-wall", "op": "cylinder", "radius_mm": 2.25, "height_mm": 5, "at_mm": [-1, 10, 16.5], "axis": "x"},
          {"id": "bracket", "op": "cut", "from": "body", "tools": ["drill-base", "drill-wall"]}], "bracket"))

# 2. Coaxial counterbore over a clearance hole.
CASES["counterbored-spacer"] = (
    intent("Spacer for an M5 bolt: 16 mm round, 12 mm tall, with a 5.5 mm clearance hole. Counterbore it from "
           "the top, 9 mm wide and 5 mm deep, so the bolt head sits below the surface.",
           [16, 16, 12],
           [hole("clearance", "z", 5.5, [8, 8], source="5.5 mm clearance hole"),
            hole("counterbore", "z", 9, [8, 8], {"depth_mm": 5, "open_end": "max"},
                 "counterbore it from the top, 9 mm wide and 5 mm deep"),
            face("bottom", "-z", "min", 170, "16 mm round"),
            face("top", "+z", "max", 130, "16 mm round")],
           ["bolt head height", "printer and material"]),
    plan([{"id": "round", "op": "cylinder", "radius_mm": 8, "height_mm": 12, "at_mm": [8, 8, 0]},
          {"id": "bore", "op": "cylinder", "radius_mm": 2.75, "height_mm": 14, "at_mm": [8, 8, -1]},
          {"id": "cbore", "op": "cylinder", "radius_mm": 4.5, "height_mm": 6, "at_mm": [8, 8, 7]},
          {"id": "spacer", "op": "cut", "from": "round", "tools": ["bore", "cbore"]}], "spacer"))

# 3. Snap-in cable channel: an open, partial bore.
CASES["cable-clip"] = (
    intent("A clip that screws to the underside of my desk and holds one 6 mm cable. I'll use a 3.5 mm wood screw.",
           [24, 12, 10],
           [hole("screw", "z", 4, [6, 6], source="3.5 mm wood screw"),
            face("desk-face", "+z", "max", 260, "screws to the underside of my desk"),
            note("cable-channel", "A 6.5 mm channel along y holds the 6 mm cable. A 5 mm opening at the bottom "
                 "lets the cable snap in.", "holds one 6 mm cable")],
           ["countersink for the screw head", "how tight the cable should be held", "printer and material"],
           questions=["Clip size is not stated. Proposed 24 x 12 x 10 mm. Simulated answer: yes.",
                      "Clearance or pilot hole for the 3.5 mm screw? Simulated answer: 4 mm clearance."]),
    plan([{"id": "block", "op": "box", "size_mm": [24, 12, 10]},
          {"id": "channel", "op": "cylinder", "radius_mm": 3.25, "height_mm": 14, "at_mm": [16, -1, 5], "axis": "y"},
          {"id": "mouth", "op": "box", "size_mm": [5, 14, 6], "at_mm": [13.5, -1, -1]},
          {"id": "screw", "op": "cylinder", "radius_mm": 2, "height_mm": 12, "at_mm": [6, 6, -1]},
          {"id": "clip", "op": "cut", "from": "block", "tools": ["channel", "mouth", "screw"]}], "clip"))

# 4. A lid whose lip size is only measurable as face offsets.
CASES["box-lid"] = (
    intent("Lid for a project box. The opening is 80 x 50 mm inside and the walls are 2 mm thick. Make the lid "
           "2 mm thick with a lip that drops 4 mm into the opening so it press-fits.",
           [84, 54, 6],
           [face("top", "+z", "max", 4500, "lid 2 mm thick over an 80 x 50 opening with 2 mm walls"),
            face("lip-bottom", "-z", "min", 390, "a lip that drops 4 mm"),
            face("lip-x-high", "+x", 81.85, 190, "lip fits inside the 80 mm opening"),
            face("lip-x-low", "-x", 2.15, 190, "lip fits inside the 80 mm opening"),
            face("lip-y-high", "+y", 51.85, 300, "lip fits inside the 50 mm opening"),
            face("lip-y-low", "-y", 2.15, 300, "lip fits inside the 50 mm opening"),
            note("press-fit", "The lip must press-fit. Only trying it on the real box shows this.", "so it press-fits")],
           ["actual box tolerance", "printer and material"],
           questions=["Clearance per side for the press fit? Simulated answer: 0.15 mm.",
                      "Lip wall thickness? Simulated answer: 1.6 mm."]),
    plan([{"id": "plate", "op": "box", "size_mm": [84, 54, 2], "at_mm": [0, 0, 4]},
          {"id": "lip-outer", "op": "box", "size_mm": [79.7, 49.7, 4], "at_mm": [2.15, 2.15, 0]},
          {"id": "lip-inner", "op": "box", "size_mm": [76.5, 46.5, 5], "at_mm": [3.75, 3.75, -1]},
          {"id": "lip", "op": "cut", "from": "lip-outer", "tools": ["lip-inner"]},
          {"id": "lid", "op": "union", "of": ["plate", "lip"]}], "lid"))

# 5. The key requirement is an angle.
CASES["phone-stand"] = (
    intent("A simple phone stand. The phone leans back at about 60 degrees, there's a lip at the front so it "
           "doesn't slide off, and it needs to fit a phone in a case, so around 80 mm wide.",
           [75, 80, 74.28],
           [face("bottom", "-z", "min", 5900, "simple phone stand"),
            face("seat", "+z", 5, 900, "fit a phone in a case"),
            face("lip-face", "+x", 4, 700, "a lip at the front so it doesn't slide off"),
            note("lean-angle", "The support face leans back 60 degrees from horizontal.", "leans back at about 60 degrees"),
            note("phone-fit", "A phone in its case fits in the 12 mm seat.", "fit a phone in a case")],
           ["phone thickness in its case", "phone height", "charging cable access", "printer and material"],
           questions=["Depth and height are not stated. Proposed 75 mm deep with an 80 mm support face. "
                      "Simulated answer: yes."]),
    plan([{"id": "stand", "op": "extrude", "plane": "xz", "height_mm": 80,
           "points": [[0, 0], [75, 0], [61.2, 71.28], [56, 74.28], [16, 5], [4, 5], [4, 14], [0, 14]]}], "stand",
         "Support face runs from (16, 5) at 60 degrees: 80 mm long, so the top is at x 56, z 74.28."))

# 6. Plain tube with a volume derived only from stated numbers.
CASES["tube"] = (
    intent("A 50 mm long tube, 25 mm outside diameter, 21 mm inside.",
           [25, 25, 50],
           [hole("bore", "z", 21, [12.5, 12.5], source="21 mm inside"),
            face("end-low", "-z", "min", 140, "50 mm long tube"),
            face("end-high", "+z", "max", 140, "50 mm long tube")],
           ["printer and material"], volume=(7200, 7250)),
    plan([{"id": "outside", "op": "cylinder", "radius_mm": 12.5, "height_mm": 50, "at_mm": [12.5, 12.5, 0]},
          {"id": "inside", "op": "cylinder", "radius_mm": 10.5, "height_mm": 52, "at_mm": [12.5, 12.5, -1]},
          {"id": "tube", "op": "cut", "from": "outside", "tools": ["inside"]}], "tube"))

# 7. Radial set-screw hole into a bore.
CASES["shaft-collar"] = (
    intent("Shaft collar for an 8 mm rod: 20 mm outside, 10 mm tall, with a hole in the side for an M3 set "
           "screw going into the bore.",
           [20, 20, 10],
           [hole("bore", "z", 8.2, [10, 10], source="shaft collar for an 8 mm rod"),
            hole("set-screw", "x", 2.5, [10, 5], source="a hole in the side for an M3 set screw going into the bore"),
            face("bottom", "-z", "min", 250, "20 mm outside, 10 mm tall")],
           ["fit on the rod", "printer and material"],
           questions=["Bore clearance? Simulated answer: 8.2 mm.",
                      "Tap the plastic, or use a heat-set insert? Simulated answer: tap a 2.5 mm hole."]),
    plan([{"id": "ring", "op": "cylinder", "radius_mm": 10, "height_mm": 10, "at_mm": [10, 10, 0]},
          {"id": "bore", "op": "cylinder", "radius_mm": 4.1, "height_mm": 12, "at_mm": [10, 10, -1]},
          {"id": "tap", "op": "cylinder", "radius_mm": 1.25, "height_mm": 8, "at_mm": [-1, 10, 5], "axis": "x"},
          {"id": "collar", "op": "cut", "from": "ring", "tools": ["bore", "tap"]}], "collar"))

# 8. A slot is two half cylinders and two flat walls.
CASES["slotted-plate"] = (
    intent("Mounting plate 50 x 20 x 3 with an adjustment slot in the middle, 5 mm wide and 20 mm long, and a "
           "4 mm hole 6 mm in from each end.",
           [50, 20, 3],
           [hole("hole-left", "z", 4, [6, 10], source="a 4 mm hole 6 mm in from each end"),
            hole("hole-right", "z", 4, [44, 10], source="a 4 mm hole 6 mm in from each end"),
            face("slot-wall-low", "+y", 7.5, 44, "slot 5 mm wide"),
            face("slot-wall-high", "-y", 12.5, 44, "slot 5 mm wide"),
            note("slot-ends", "The slot ends are round. The slot is 20 mm long overall.", "20 mm long")],
           ["screw size for the slot", "printer and material"]),
    plan([{"id": "plate", "op": "box", "size_mm": [50, 20, 3]},
          {"id": "slot-mid", "op": "box", "size_mm": [15, 5, 5], "at_mm": [17.5, 7.5, -1]},
          {"id": "slot-end-a", "op": "cylinder", "radius_mm": 2.5, "height_mm": 5, "at_mm": [17.5, 10, -1]},
          {"id": "slot-end-b", "op": "cylinder", "radius_mm": 2.5, "height_mm": 5, "at_mm": [32.5, 10, -1]},
          {"id": "drill", "op": "cylinder", "radius_mm": 2, "height_mm": 5, "at_mm": [6, 10, -1]},
          {"id": "drills", "op": "linear_pattern", "target": "drill", "step_mm": [38, 0, 0], "count": 2},
          {"id": "part", "op": "cut", "from": "plate", "tools": ["slot-mid", "slot-end-a", "slot-end-b", "drills"]}],
         "part"))

# 9. Bracket with a brace, holes on two axes.
CASES["shelf-bracket"] = (
    intent("Shelf bracket: 60 mm down the wall, 60 mm under the shelf, 25 mm wide, 4 mm thick, with a triangle "
           "brace between the legs. Two 4 mm screw holes in each leg.",
           [60, 25, 60],
           [hole("wall-1", "x", 4, [6.5, 10], source="two 4 mm screw holes in each leg"),
            hole("wall-2", "x", 4, [18.5, 10], source="two 4 mm screw holes in each leg"),
            hole("shelf-1", "z", 4, [50, 6.5], source="two 4 mm screw holes in each leg"),
            hole("shelf-2", "z", 4, [50, 18.5], source="two 4 mm screw holes in each leg"),
            face("wall-face", "-x", "min", 1400, "60 mm down the wall"),
            face("shelf-face", "+z", "max", 1400, "60 mm under the shelf"),
            note("brace", "A triangle brace joins the two legs.", "a triangle brace between the legs")],
           ["shelf load", "screw type", "printer and material"],
           questions=["The brace fills the middle of both legs. Put the holes below and beyond it? "
                      "Simulated answer: yes."]),
    plan([{"id": "profile", "op": "extrude", "plane": "xz", "height_mm": 25,
           "points": [[0, 0], [4, 0], [4, 20], [40, 56], [60, 56], [60, 60], [0, 60]]},
          {"id": "wall-drill", "op": "cylinder", "radius_mm": 2, "height_mm": 6, "at_mm": [-1, 6.5, 10], "axis": "x"},
          {"id": "wall-drills", "op": "linear_pattern", "target": "wall-drill", "step_mm": [0, 12, 0], "count": 2},
          {"id": "shelf-drill", "op": "cylinder", "radius_mm": 2, "height_mm": 6, "at_mm": [50, 6.5, 55]},
          {"id": "shelf-drills", "op": "linear_pattern", "target": "shelf-drill", "step_mm": [0, 12, 0], "count": 2},
          {"id": "bracket", "op": "cut", "from": "profile", "tools": ["wall-drills", "shelf-drills"]}], "bracket"))

# 10. Vague ask: the right result is questions, not a part.
CASES["sd-card-box"] = (
    intent("make me a little box for my SD cards",
           [1, 1, 1],
           [note("holds-cards", "Holds SD cards.", "a little box for my SD cards")],
           ["number of cards", "full-size or microSD", "lid or open tray", "outside size", "printer and material"],
           questions=["How many cards?", "Full-size SD, microSD, or both?", "Lid, hinge, or open tray?",
                      "Any size limit, for example a drawer?"],
           status={"status": "draft"}),
    None)

# 11. Gear with a D-shaft bore.
GEAR_TIP = 10.9945
CASES["spur-gear"] = (
    intent("A 20 tooth spur gear, module 1, 6 mm thick, with a 5 mm D-shaft bore.",
           [2 * GEAR_TIP, 2 * GEAR_TIP, 6],
           [hole("bore", "z", 5, [GEAR_TIP, GEAR_TIP], source="5 mm D-shaft bore"),
            face("face-low", "-z", "min", 250, "6 mm thick"),
            note("teeth", "20 involute teeth, module 1, 20 degree pressure angle.", "20 tooth spur gear, module 1"),
            note("d-flat", "The bore has a flat 4.5 mm across for the D-shaft.", "D-shaft bore")],
           ["mating gear", "backlash", "printer and material"],
           questions=["Pressure angle? Simulated answer: 20 degrees.",
                      "Width across the flat? Simulated answer: 4.5 mm."]),
    plan([{"id": "blank", "op": "extrude", "plane": "xy", "height_mm": 6, "points": gear_points()},
          {"id": "shaft", "op": "cylinder", "radius_mm": 2.5, "height_mm": 8, "at_mm": [0, 0, -1]},
          {"id": "keep", "op": "box", "size_mm": [6, 5, 8], "at_mm": [-3, -3, -1]},
          {"id": "d-shaft", "op": "intersect", "of": ["shaft", "keep"]},
          {"id": "gear", "op": "cut", "from": "blank", "tools": ["d-shaft"]}], "gear",
         "The keep box ends at y 2, so the flat is 4.5 mm from the far side of the 5 mm bore."))

# 12. Hollow inside: a nested shell that the docs say is unsupported.
CASES["hollow-ball"] = (
    intent("A hollow ball, 40 mm across, with 2 mm walls.",
           [40, 40, 40],
           [note("hollow", "Hollow inside, with a 2 mm wall.", "hollow ... with 2 mm walls")],
           ["printer and material", "drain hole for resin or powder"], volume=(9050, 9110)),
    plan([{"id": "outside", "op": "sphere", "radius_mm": 20, "at_mm": [20, 20, 20]},
          {"id": "inside", "op": "sphere", "radius_mm": 18, "at_mm": [20, 20, 20]},
          {"id": "ball", "op": "cut", "from": "outside", "tools": ["inside"]}], "ball"))

# 13. Threads: no op can make them.
CASES["bottle-cap"] = (
    intent("A cap that screws onto a standard 28 mm soda bottle.",
           [1, 1, 1],
           [note("thread", "Internal thread that fits a 28 mm PCO 1881 bottle neck.", "screws onto a 28 mm soda bottle")],
           ["thread profile", "seal", "printer and material"],
           questions=["Dot Forge has no thread or helix operation, and cannot measure a thread. "
                      "Make a plain press-on cap instead, or stop?"],
           status={"status": "draft"}),
    None)


def revise(spec, change, features=None, unknowns=None):
    """A later attempt that needs a changed intent, so the user must confirm again."""
    spec = json.loads(json.dumps(spec))
    if features:
        spec["features"] = features(spec["features"])
    if unknowns is not None:
        spec["unknowns"] = unknowns
    note_text = spec["confirmation"].get("note", SIMULATED["note"])
    note_text = note_text if "Revision:" in note_text else note_text + " Revision:"
    spec["confirmation"] = dict(SIMULATED, note=f"{note_text} {change}")
    return spec


def set_depth(feature_id, depth):
    """Replace one hole's depth with a new form."""
    return lambda fs: [dict(f, depth=depth) if f["id"] == feature_id else f for f in fs]


def drain_height(spec):
    """Attempt 2 kept 40 mm tall; the drain hole trims the bottom pole to 39.94 mm."""
    spec = revise(spec, "Attempt 3: the drain trims the bottom, so the height is 39.94 mm.")
    spec["envelope"]["size_mm"][2] = round(20 + math.sqrt(20 ** 2 - 1.5 ** 2), 2)
    return spec


DRAIN_PLAN = {"steps": CASES["hollow-ball"][1]["steps"][:-1] + [
    {"id": "drain", "op": "cylinder", "radius_mm": 1.5, "height_mm": 4, "at_mm": [20, 20, -1]},
    {"id": "ball", "op": "cut", "from": "outside", "tools": ["inside", "drain"]}]}

# Later attempts for blocked cases, in order. Each step takes the previous intent
# and returns the new intent and any plan changes (None keeps the plan).
ATTEMPTS = {
    "spur-gear": [lambda spec: (
        revise(spec, "a D-bore is not a full cylinder, so it cannot be a measured hole. Moved to a note.",
               lambda fs: [f for f in fs if f["id"] != "bore"] + [
                   note("bore", "5 mm bore for the D-shaft, centred on the gear.", "5 mm D-shaft bore")]),
        None),
        lambda spec: (
            revise(spec, "Attempt 3: the D-bore is measured as a partial hole (286 degrees of a 5 mm circle) "
                         "and the flat as a face 4.5 mm across from the far wall.",
                   lambda fs: [f for f in fs if f["id"] not in ("bore", "d-flat")] + [
                       partial("bore", "z", 5, [GEAR_TIP, GEAR_TIP], (280, 292), 6, "5 mm D-shaft bore"),
                       dict(face("d-flat", "-y", round(GEAR_TIP + 2, 4), 17, "5 mm D-shaft bore"),
                            max_area_mm2=19)]),
            None)],
    "hollow-ball": [
        lambda spec: (
            revise(spec, "a sealed cavity is not supported. User accepted a 3 mm drain hole at the bottom.",
                   lambda fs: fs + [hole("drain", "z", 3, [20, 20],
                                         source="user answer: add a 3 mm drain hole at the bottom")],
                   ["printer and material"]),
            DRAIN_PLAN),
        lambda spec: (drain_height(spec), None),
        lambda spec: (revise(spec, "Attempt 4: the drain opens into the cavity, not to the outside at both ends.",
                             set_depth("drain", {"ends": {"min": "outside", "max": "void"}})), None)],
    "counterbored-spacer": [lambda spec: (
        revise(spec, "the counterbore floor is a shoulder around the clearance hole, not a solid floor.",
               set_depth("counterbore", {"ends": {"min": "shoulder", "max": "outside"}, "depth_mm": 5})), None)],
    "slotted-plate": [
        lambda spec: (
            revise(spec, "the slot walls are 15 mm of flat between the round ends (45 mm2 each), so they get a "
                         "maximum area too. A longer slot now fails.",
                   lambda fs: [dict(f, max_area_mm2=46) if f["id"].startswith("slot-wall") else f for f in fs]),
            None),
        lambda spec: (
            revise(spec, "Attempt 3: the round slot ends are measured as two half holes.",
                   lambda fs: [f for f in fs if f["id"] != "slot-ends"] + [
                       partial(f"slot-end-{i}", "z", 5, [x, 10], (175, 185), 3, "slot 5 mm wide and 20 mm long")
                       for i, x in ((1, 17.5), (2, 32.5))]),
            None)],
    "cable-clip": [lambda spec: (
        revise(spec, "the cable channel is measured as a partial hole: 6.5 mm across, open at the bottom "
                     "through a 5 mm mouth, so about 259 degrees.",
               lambda fs: [f for f in fs if f["id"] != "cable-channel"] + [
                   partial("cable-channel", "y", 6.5, [16, 5], (250, 270), 12, "holds one 6 mm cable"),
                   note("cable-fit", "The 6 mm cable snaps in through the 5 mm mouth and stays put.",
                        "holds one 6 mm cable")]),
        None)],
    "shaft-collar": [lambda spec: (
        revise(spec, "the set-screw hole opens into the bore, not to the outside at both ends.",
               set_depth("set-screw", {"ends": {"min": "outside", "max": "void"}})), None)],
}


def edit(case, **changes):
    """Copy of a case's first plan with some steps changed: one realistic plan mistake."""
    copy = json.loads(json.dumps(CASES[case][1]))
    for step in copy["steps"]:
        step.update(changes.get(step["id"].replace("-", "_"), {}))
    return copy


def drop(case, cut_id, *tools):
    """Copy of a case's first plan with cutting tools left out."""
    copy = json.loads(json.dumps(CASES[case][1]))
    copy["steps"] = [s for s in copy["steps"] if s["id"] not in tools]
    cut = next(s for s in copy["steps"] if s["id"] == cut_id)
    cut["tools"] = [t for t in cut["tools"] if t not in tools]
    return copy


# Each mutant is one plausible mistake. "expect" is what a careful reviewer wants: caught or not.
MUTANTS = {
    "l-bracket": [("hole-mid-whole-leg", "Wall hole at the middle of the whole leg (15 mm), not the flat part.",
                   lambda: edit("l-bracket", drill_wall={"at_mm": [-1, 10, 15]}))],
    "counterbored-spacer": [
        ("counterbore-4-deep", "Counterbore 4 mm deep, not 5.",
         lambda: edit("counterbored-spacer", cbore={"at_mm": [8, 8, 8]})),
        ("counterbore-from-bottom", "Counterbore cut from the bottom.",
         lambda: edit("counterbored-spacer", cbore={"at_mm": [8, 8, -1]}))],
    "cable-clip": [("no-channel", "Cable channel and its opening left out.",
                    lambda: drop("cable-clip", "clip", "channel", "mouth")),
                   ("no-mouth", "Channel cut without the opening, so the cable cannot snap in.",
                    lambda: drop("cable-clip", "clip", "mouth"))],
    "spur-gear": [("round-bore", "Plain round bore, no flat for the D-shaft.",
                   lambda: (lambda p: dict(p, steps=[s for s in p["steps"] if s["id"] not in ("keep", "d-shaft")]))(
                       edit("spur-gear", gear={"tools": ["shaft"]})))],
    "box-lid": [("lip-no-clearance", "Lip sized to the opening, 80 x 50, with no clearance.",
                 lambda: edit("box-lid", lip_outer={"size_mm": [80, 50, 4], "at_mm": [2, 2, 0]}))],
    "phone-stand": [("lean-70", "Support face at 70 degrees, not 60.",
                     lambda: edit("phone-stand", stand={"points": [[0, 0], [75, 0], [48.4, 79.17], [43.36, 80.17],
                                                                   [16, 5], [4, 5], [4, 14], [0, 14]]}))],
    "tube": [("thin-wall", "Inside diameter 22, not 21.", lambda: edit("tube", inside={"radius_mm": 11}))],
    "shaft-collar": [("short-tap", "Set-screw hole stops short of the bore.",
                      lambda: edit("shaft-collar", tap={"height_mm": 5}))],
    "slotted-plate": [("long-slot", "Slot 25 mm long, not 20.",
                       lambda: edit("slotted-plate", slot_mid={"size_mm": [20, 5, 5]},
                                    slot_end_b={"at_mm": [37.5, 10, -1]}))],
    "shelf-bracket": [
        ("no-brace", "Brace left out of the profile.",
         lambda: edit("shelf-bracket", profile={"points": [[0, 0], [4, 0], [4, 56], [60, 56], [60, 60], [0, 60]]})),
        ("shelf-holes-centred", "Shelf holes moved to the centre line.",
         lambda: edit("shelf-bracket", shelf_drill={"at_mm": [50, 12.5, 55]}))],
}

def main():
    index = []
    for name, ((spec, questions), first_plan) in CASES.items():
        folder = ROOT / name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "intent.json").write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n")
        check_intent(spec)
        summary = summarize(spec)
        entry = {"case": name, "ask": spec["ask"], "questions": questions,
                 "measured_checks": len(summary["measured_checks"]), "person_checks": len(summary["person_checks"]),
                 "unknowns": len(spec["unknowns"]), "status": spec["confirmation"]["status"]}
        if first_plan is not None:
            first_plan["intent_sha256"] = canonical_hash(spec)
            check_plan(first_plan, spec)
            (folder / "plan-001.json").write_text(json.dumps(first_plan, indent=2, sort_keys=True) + "\n")
        spec_n, plan_n = spec, first_plan
        for number, step in enumerate(ATTEMPTS.get(name, []), start=2):
            spec_n, changes = step(spec_n)
            check_intent(spec_n, require_confirmed=True)
            plan_n = dict(json.loads(json.dumps(plan_n)), **(changes or {}))
            plan_n["intent_sha256"] = canonical_hash(spec_n)
            check_plan(plan_n, spec_n)
            (folder / f"intent-{number:03}.json").write_text(json.dumps(spec_n, indent=2, sort_keys=True) + "\n")
            (folder / f"plan-{number:03}.json").write_text(json.dumps(plan_n, indent=2, sort_keys=True) + "\n")
            entry["revision"] = spec_n["confirmation"]["note"]
        # Mutants are judged against the last intent, the one the correct plan is built for.
        for mutant, description, make in MUTANTS.get(name, []):
            mutated = make()
            mutated["intent_sha256"] = canonical_hash(spec_n)
            check_plan(mutated, spec_n)
            (folder / "mutants").mkdir(exist_ok=True)
            (folder / "mutants" / f"{mutant}.json").write_text(json.dumps(mutated, indent=2, sort_keys=True) + "\n")
            entry.setdefault("mutants", {})[mutant] = description
        index.append(entry)
    (ROOT / "index.json").write_text(json.dumps(index, indent=2) + "\n")
    for e in index:
        print(f"{e['case']:20} {e['status']:9} measured={e['measured_checks']} person={e['person_checks']} unknowns={e['unknowns']}")


if __name__ == "__main__":
    main()
