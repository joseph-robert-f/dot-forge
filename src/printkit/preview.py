"""v2 preview: a draft build the person can look at before they confirm the intent.

The preview builds the plan from a draft intent, draws five exact views of the
solid with their measured sizes, and lists in plain words what will be checked,
what a person decides, and what was not stated. It is never a deliverable.
After approval, `build --approved-preview` records which views the person saw
and confirms that the final solid matches them.
"""
import html
import math
from pathlib import Path
from .common import ForgeError, canonical_hash, load_json, sha256, write_json
from .conformance import conform
from .forge import fresh_run
from .intent import check_intent, plane_axes
from .plan import check_plan
from .adapters import freecad_plan

SCHEMA = "preview.v1"
ORTHO = ("front", "right", "back", "top")
LAYOUT = (("front", 0, 0), ("right", 1, 0), ("back", 2, 0), ("top", 0, 1), ("iso", 1, 1))
CELL_W, CELL_H, MARGIN = 440, 380, 24
INK, HIDDEN, DIM, PASS, FAIL, REVIEW = "#1d1c1a", "#a7a297", "#6b675f", "#3f6f5a", "#c4562f", "#a9802f"
SIZE_MATCH_MM, VOLUME_MATCH_REL = 1e-6, 1e-9


def intent_key(intent):
    """The intent without its confirmation: the same request before and after approval."""
    return canonical_hash({k: v for k, v in intent.items() if k != "confirmation"})


def plan_key(plan):
    """The plan without its intent binding, which changes when the intent is confirmed."""
    return canonical_hash({k: v for k, v in plan.items() if k != "intent_sha256"})


def mm(value):
    return f"{value:.2f}".rstrip("0").rstrip(".")


def describe(feature):
    """One plain sentence per intent feature."""
    if feature["kind"] in ("hole", "partial_hole"):
        where = ", ".join(f"{a} {mm(v)}" for a, v in zip(plane_axes(feature["axis"]), feature["position_mm"]))
        if feature["kind"] == "partial_hole":
            arc = f"{mm(feature['min_arc_deg'])} to {mm(feature['max_arc_deg'])}" if "max_arc_deg" in feature \
                else f"at least {mm(feature['min_arc_deg'])}"
            length = f", {mm(feature['length_mm'])} mm long" if "length_mm" in feature else ""
            return f"Partial hole {feature['id']}: {mm(feature['diameter_mm'])} mm across, along {feature['axis']} at {where}, wall {arc} degrees{length}"
        depth = feature["depth"]
        if depth == "through":
            how = "through"
        elif "ends" in depth:
            how = f"ends {depth['ends']['min']} and {depth['ends']['max']}"
            how += f", {mm(depth['depth_mm'])} mm long" if "depth_mm" in depth else ""
        else:
            how = f"blind, {mm(depth['depth_mm'])} mm deep, open at the {'high' if depth['open_end'] == 'max' else 'low'} side"
        return f"Hole {feature['id']}: {mm(feature['diameter_mm'])} mm, along {feature['axis']} at {where}, {how}"
    if feature["kind"] == "planar_face":
        offset = feature["offset"]
        at = {"min": "the low side", "max": "the high side"}[offset] if offset in ("min", "max") else f"{mm(offset)} mm"
        area = f"at least {mm(feature['min_area_mm2'])} mm2"
        area += f" and at most {mm(feature['max_area_mm2'])} mm2" if "max_area_mm2" in feature else ""
        return f"Flat face {feature['id']}: facing {feature['normal']} at {at}, {area}"
    return f"For you to judge: {feature['text']}"


def summary_lines(intent, conformance):
    status = {c["code"]: c["status"] for c in conformance["checks"]}
    size = intent["envelope"]["size_mm"]
    checked = [(f"Overall size {mm(size[0])} x {mm(size[1])} x {mm(size[2])} mm "
                f"(within {mm(intent['envelope']['tolerance_mm'])} mm)", status.get("envelope"))]
    if "volume_mm3" in intent:
        v = intent["volume_mm3"]
        checked.append((f"Volume {mm(v['min'])} to {mm(v['max'])} mm3", status.get("volume")))
    checked += [(describe(f), status.get(f"feature:{f['id']}")) for f in intent["features"] if f["kind"] != "note"]
    judged = [f["text"] for f in intent["features"] if f["kind"] == "note"]
    return checked, judged, list(intent["unknowns"])


def wrap(text, width):
    lines, line = [], ""
    for word in text.split():
        if line and len(line) + 1 + len(word) > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    return lines + ([line] if line else [])


def project(axes, point):
    return (sum(a * b for a, b in zip(axes[0], point)), sum(a * b for a, b in zip(axes[1], point)))


def bounds(view):
    points = [p for line in view["visible"] + view["hidden"] for p in line]
    if not points:
        raise ForgeError("A preview view has no lines; the solid could not be projected", 4, "preview_failed")
    return (min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points))


def sheet(lines, intent, measure, conformance):
    """Five views on one SVG sheet, with overall sizes and hole labels, plus the plain summary."""
    size, low = measure["size_mm"], measure["origin_mm"]
    box = {name: bounds(lines[name]) for name in lines}
    ortho_scale = min(min((CELL_W - 110) / max(box[n][2] - box[n][0], 1e-6),
                          (CELL_H - 120) / max(box[n][3] - box[n][1], 1e-6)) for n in ORTHO)
    iso_scale = min((CELL_W - 60) / max(box["iso"][2] - box["iso"][0], 1e-6),
                    (CELL_H - 80) / max(box["iso"][3] - box["iso"][1], 1e-6))
    width, height = 3 * CELL_W + 2 * MARGIN, 2 * CELL_H + 2 * MARGIN
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
           f'font-family="Helvetica, Arial, sans-serif">', f'<rect width="{width}" height="{height}" fill="#ffffff"/>']
    status = {c["code"]: c["status"] for c in conformance["checks"]}
    for name, col, row in LAYOUT:
        view, (x0, y0, x1, y1) = lines[name], box[name]
        scale = iso_scale if name == "iso" else ortho_scale
        cx, cy = MARGIN + col * CELL_W + CELL_W / 2 - (20 if name != "iso" else 0), MARGIN + row * CELL_H + CELL_H / 2 - 6
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        to = lambda p: (cx + (p[0] - mx) * scale, cy - (p[1] - my) * scale)
        path = lambda polylines: "".join("M" + " L".join(f"{x:.2f} {y:.2f}" for x, y in map(to, line)) for line in polylines)
        out.append(f'<text x="{MARGIN + col * CELL_W + 8}" y="{MARGIN + row * CELL_H + 22}" font-size="14" fill="{DIM}">{name}</text>')
        if view["hidden"]:
            out.append(f'<path d="{path(view["hidden"])}" fill="none" stroke="{HIDDEN}" stroke-width="1" stroke-dasharray="4 3"/>')
        out.append(f'<path d="{path(view["visible"])}" fill="none" stroke="{INK}" stroke-width="1.6" stroke-linejoin="round"/>')
        if name == "iso":
            continue
        # Overall sizes come from the measurement, not from the drawing.
        across = sum(abs(a) * s for a, s in zip(view["axes"][0], size))
        tall = sum(abs(a) * s for a, s in zip(view["axes"][1], size))
        (left, bottom), (right, top) = to((x0, y0)), to((x1, y1))
        y_dim, x_dim = bottom + 22, right + 22
        out.append(f'<path d="M{left:.1f} {y_dim:.1f} H{right:.1f} M{left:.1f} {y_dim - 5:.1f} V{y_dim + 5:.1f} '
                   f'M{right:.1f} {y_dim - 5:.1f} V{y_dim + 5:.1f} M{x_dim:.1f} {top:.1f} V{bottom:.1f} '
                   f'M{x_dim - 5:.1f} {top:.1f} H{x_dim + 5:.1f} M{x_dim - 5:.1f} {bottom:.1f} H{x_dim + 5:.1f}" '
                   f'stroke="{DIM}" stroke-width="1" fill="none"/>')
        out.append(f'<text x="{(left + right) / 2:.1f}" y="{y_dim + 18:.1f}" font-size="13" fill="{DIM}" text-anchor="middle">{mm(across)}</text>')
        out.append(f'<text x="{x_dim + 8:.1f}" y="{(top + bottom) / 2 + 4:.1f}" font-size="13" fill="{DIM}">{mm(tall)}</text>')
        toward = view["axes"][2]
        for feature in intent["features"]:
            if feature["kind"] not in ("hole", "partial_hole"):
                continue
            k = "xyz".index(feature["axis"])
            if abs(toward[k]) < 0.99:
                continue
            point = [low[i] + size[i] / 2 for i in range(3)]
            for axis, value in zip(plane_axes(feature["axis"]), feature["position_mm"]):
                point["xyz".index(axis)] = low["xyz".index(axis)] + value
            hx, hy = to(project(view["axes"], point))
            colour = {"pass": PASS, "fail": FAIL}.get(status.get(f"feature:{feature['id']}"), REVIEW)
            out.append(f'<path d="M{hx:.1f} {hy:.1f} L{hx + 14:.1f} {hy - 14:.1f} H{hx + 22:.1f}" stroke="{colour}" fill="none"/>')
            out.append(f'<text x="{hx + 25:.1f}" y="{hy - 10:.1f}" font-size="12" fill="{colour}">'
                       f'{html.escape(feature["id"])} \u00d8{mm(feature["diameter_mm"])}</text>')
    checked, judged, unknown = summary_lines(intent, conformance)
    x, y = MARGIN + 2 * CELL_W + 8, MARGIN + CELL_H + 22
    text = []
    text.append((f"Preview, not for delivery", 14, INK))
    text.append(("Will be measured", 12, DIM))
    for line, state in checked:
        colour = {"pass": PASS, "fail": FAIL}.get(state, REVIEW)
        for i, part in enumerate(wrap(f"{state or 'unknown'}: {line}", 64)):
            text.append(((part if i == 0 else "   " + part), 11, colour))
    if judged:
        text.append(("For you to judge", 12, DIM))
        text += [(("- " if i == 0 else "  ") + part, 11, INK) for item in judged for i, part in enumerate(wrap(item, 62))]
    if unknown:
        text.append(("Not stated, not assumed", 12, DIM))
        text += [(("- " if i == 0 else "  ") + part, 11, INK) for item in unknown for i, part in enumerate(wrap(item, 62))]
    room = int((CELL_H - 30) / 15)
    if len(text) > room:
        text = text[:room - 1] + [(f"... {len(text) - room + 1} more lines in preview.md", 11, DIM)]
    for line, size_px, colour in text:
        out.append(f'<text x="{x}" y="{y}" font-size="{size_px}" fill="{colour}">{html.escape(line)}</text>')
        y += 15 if size_px < 12 else 18
    out.append("</svg>")
    return "\n".join(out) + "\n"


def markdown(intent, conformance, picture):
    checked, judged, unknown = summary_lines(intent, conformance)
    failed = [line for line, state in checked if state != "pass"]
    parts = [f"# Preview: not for delivery\n\nAsk: {intent['ask']}\n", f"Views: `{picture}`\n",
             "## I will measure\n", *[f"- {line}" for line, _ in checked]]
    if judged:
        parts += ["\n## For you to judge in the views\n", *[f"- {item}" for item in judged]]
    if unknown:
        parts += ["\n## Not stated, so not assumed\n", *[f"- {item}" for item in unknown]]
    parts.append("\n## Draft result\n")
    parts.append(f"{len(checked) - len(failed)} of {len(checked)} measured checks pass on this draft."
                 + ("" if not failed else " Not passing yet:\n\n" + "\n".join(f"- {line}" for line in failed)))
    parts.append("\nReply with changes, or approve the views and the checks. Nothing is final until you approve.\n")
    return "\n".join(parts)


def preview(intent, plan, output, *, discover=None):
    check_intent(intent)
    plan_summary = check_plan(plan, intent)
    run = fresh_run(output)
    write_json(run / "intent.json", intent)
    write_json(run / "plan.json", plan)
    record = {"schema_version": SCHEMA, "delivery": "not_for_delivery", "intent_key": intent_key(intent),
              "plan_key": plan_key(plan), "plan_warnings": plan_summary["warnings"]}
    try:
        freecad_plan.generate(run, discover)
    except ForgeError as exc:
        record.update(state="blocked", failure={"code": exc.finding, "message": str(exc)})
        write_json(run / "preview.json", record)
        raise
    measure = load_json(run / "native/measure.json")
    conformance = conform(intent, measure)
    lines = freecad_plan.views(run)
    (run / "views/sheet.svg").write_text(sheet(lines, intent, measure, conformance))
    picture = "views/sheet.png" if freecad_plan.raster(run) else "views/sheet.svg"
    (run / "preview.md").write_text(markdown(intent, conformance, picture))
    files = ["views/lines.json", "views/sheet.svg", "native/measure.json", "preview.md"]
    files += ["views/sheet.png"] if picture.endswith(".png") else []
    record.update(state=conformance["intent_state"], picture=picture, conformance=conformance,
                  solid={k: measure[k] for k in ("size_mm", "volume_mm3", "face_count", "edge_count")},
                  files={name: sha256(run / name) for name in files})
    write_json(run / "preview.json", record)
    return record


def approval(preview_dir, intent, plan):
    """Check that a preview shows this intent and plan, and that its files are unchanged."""
    folder = Path(preview_dir)
    record = load_json(folder / "preview.json")
    if record.get("schema_version") != SCHEMA or record.get("delivery") != "not_for_delivery" or "files" not in record:
        raise ForgeError("The approved preview is incomplete; make a new preview", 2, "preview_invalid")
    if record["intent_key"] != intent_key(intent) or record["plan_key"] != plan_key(plan):
        raise ForgeError("The approved preview shows a different intent or plan; show a new preview", 2, "preview_mismatch")
    for name, digest in record["files"].items():
        if sha256(folder / name) != digest:
            raise ForgeError(f"Preview file {name} changed after it was made", 2, "preview_changed")
    return record


def same_solid(preview_solid, measure):
    return (preview_solid["face_count"] == measure["face_count"] and preview_solid["edge_count"] == measure["edge_count"]
            and all(abs(a - b) <= SIZE_MATCH_MM for a, b in zip(preview_solid["size_mm"], measure["size_mm"]))
            and math.isclose(preview_solid["volume_mm3"], measure["volume_mm3"], rel_tol=VOLUME_MATCH_REL))
