#!/usr/bin/env python3
"""build_floor_plan.py - Deterministic floor plan SVG generator and model validator.

Generates polished architectural 1600x1200 SVG and manages inline block in index.html.
Driven entirely by assets/brand/floor-plan-model.json with Python stdlib (no external dependencies).

Validation scope and exact limits:
- Centerline ray-segment intersection, 2D bounding boxes, and door sweep quarter clearances are verified.
- Full CAD 3D volumetric clearance, sweep tolerance, and turning physics are not performed.
"""

import argparse
import hashlib
import json
import math
import os
import random
import re
import sys
from collections import defaultdict
from typing import Any, Dict, List, Set, Tuple

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "assets", "brand", "floor-plan-model.json")
SVG_PATH = os.path.join(BASE_DIR, "assets", "brand", "entry-floor-plan.svg")
INDEX_PATH = os.path.join(BASE_DIR, "index.html")
MANIFEST_PATH = os.path.join(BASE_DIR, "assets", "brand", "manifest.json")
START_MARKER = "<!-- FLOOR_PLAN_START -->"
END_MARKER = "<!-- FLOOR_PLAN_END -->"


# ==============================================================================
# Model Geometry Helpers
# ==============================================================================

def compute_door_geometry(op: Dict[str, Any], wall: Dict[str, Any]) -> Dict[str, Any]:
    """Compute generic vector geometry for hinged/glass doors from explicit model properties."""
    w1, w2 = wall["start"], wall["end"]
    thick = float(wall["thickness"])
    w_len = math.hypot(w2[0] - w1[0], w2[1] - w1[1])
    ux, uy = (w2[0] - w1[0]) / w_len, (w2[1] - w1[1]) / w_len
    swing_side = op.get("swing_side", "left")
    n_face = (uy, -ux) if swing_side == "left" else (-uy, ux)
    offset, w_ft = float(op["offset_ft"]), float(op["width_ft"])
    hinge_end = op.get("hinge_end", "start")
    s_h = offset + w_ft if hinge_end == "end" else offset
    s_c = offset if hinge_end == "end" else offset + w_ft
    hx_ft, hy_ft = w1[0] + s_h * ux + (thick / 2.0) * n_face[0], w1[1] + s_h * uy + (thick / 2.0) * n_face[1]
    cx_ft, cy_ft = w1[0] + s_c * ux + (thick / 2.0) * n_face[0], w1[1] + s_c * uy + (thick / 2.0) * n_face[1]
    ox_ft, oy_ft = hx_ft + w_ft * n_face[0], hy_ft + w_ft * n_face[1]
    cross_z = (cx_ft - hx_ft) * (oy_ft - hy_ft) - (cy_ft - hy_ft) * (ox_ft - hx_ft)
    return {
        "hinge": (hx_ft, hy_ft), "closed": (cx_ft, cy_ft), "open": (ox_ft, oy_ft),
        "radius": w_ft, "sweep_flag": 1 if cross_z > 0 else 0, "normal": n_face,
        "ux": ux, "uy": uy, "offset": offset, "w_ft": w_ft, "thick": thick, "w1": w1
    }


# ==============================================================================
# Model Validation
# ==============================================================================

def validate_model(m: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Execute bounded meaningful validation on the architectural data model."""
    errors = []

    # 1. Unique IDs
    seen_ids: Set[str] = set()
    for cat in ["spaces", "walls", "openings", "fixtures", "furniture", "trees", "circulation", "annotations"]:
        for item in m.get(cat, []):
            iid = item.get("id")
            if iid:
                if iid in seen_ids: errors.append(f"Duplicate ID '{iid}' in '{cat}'")
                seen_ids.add(iid)

    # 2. Positive dimensions & Area arithmetic
    for s in m.get("spaces", []):
        b = s.get("bounds", {})
        if b.get("width", 0) <= 0 or b.get("height", 0) <= 0 or s.get("area_sqft", 0) <= 0:
            errors.append(f"Space '{s.get('id')}' has non-positive bounds or area")
        if abs(b.get("width", 0) * b.get("height", 0) - s.get("area_sqft", 0)) > 0.05:
            errors.append(f"Area mismatch in '{s['id']}': bounds product != area_sqft")

    for w in m.get("walls", []):
        wlen = math.hypot(w["end"][0] - w["start"][0], w["end"][1] - w["start"][1])
        if w.get("thickness", 0) <= 0 or wlen <= 0:
            errors.append(f"Wall '{w.get('id')}' has non-positive thickness or zero length")

    for op in m.get("openings", []):
        if op.get("width_ft", 0) <= 0 or op.get("height_ft", 0) <= 0:
            errors.append(f"Opening '{op.get('id')}' has non-positive dimensions")

    for t in m.get("trees", []):
        if t.get("canopy_radius_ft", 0) <= 0 or t.get("trunk_radius_ft", 0) <= 0:
            errors.append(f"Tree '{t.get('id')}' has non-positive radius")

    # 3. Required rooms
    required = {"courtyard", "kitchen", "dining_room", "living_room", "primary_bedroom", "guest_bedroom"}
    missing = required - {s["id"] for s in m.get("spaces", [])}
    if missing: errors.append(f"Missing required rooms: {missing}")

    # 4. Pairwise room non-overlap
    spaces = m.get("spaces", [])
    for i in range(len(spaces)):
        for j in range(i + 1, len(spaces)):
            a, b = spaces[i]["bounds"], spaces[j]["bounds"]
            if (max(a["x"], b["x"]) < min(a["x"] + a["width"], b["x"] + b["width"]) - 1e-4 and
                    max(a["y"], b["y"]) < min(a["y"] + a["height"], b["y"] + b["height"]) - 1e-4):
                errors.append(f"Spaces overlap: '{spaces[i]['id']}' and '{spaces[j]['id']}'")

    # 5. Wall & opening bounds and non-overlap
    wall_map = {w["id"]: w for w in m.get("walls", [])}
    wall_ops = defaultdict(list)
    for op in m.get("openings", []):
        wid = op.get("wall_id")
        if wid not in wall_map:
            errors.append(f"Opening '{op.get('id')}' references missing wall '{wid}'")
            continue
        w = wall_map[wid]
        wlen = math.hypot(w["end"][0] - w["start"][0], w["end"][1] - w["start"][1])
        if op.get("offset_ft", 0) < -1e-4 or op["offset_ft"] + op["width_ft"] > wlen + 1e-4:
            errors.append(f"Opening '{op['id']}' exceeds wall '{wid}' length ({wlen:.2f})")
        wall_ops[wid].append(op)

    for wid, ops in wall_ops.items():
        ops_sorted = sorted(ops, key=lambda o: o["offset_ft"])
        for k in range(len(ops_sorted) - 1):
            if ops_sorted[k]["offset_ft"] + ops_sorted[k]["width_ft"] > ops_sorted[k + 1]["offset_ft"] + 1e-4:
                errors.append(f"Openings overlap on '{wid}': '{ops_sorted[k]['id']}' & '{ops_sorted[k+1]['id']}'")

    # 6. Room containment for furniture & fixtures
    space_map = {s["id"]: s for s in spaces}
    for cat in ["fixtures", "furniture"]:
        for item in m.get(cat, []):
            rid = item.get("room_id")
            if rid not in space_map:
                errors.append(f"Item '{item.get('id')}' references unknown room '{rid}'")
                continue
            rb, ib = space_map[rid]["bounds"], item["bounds"]
            if (ib["x"] < rb["x"] - 1e-4 or ib["y"] < rb["y"] - 1e-4 or
                    ib["x"] + ib["width"] > rb["x"] + rb["width"] + 1e-4 or
                    ib["y"] + ib["height"] > rb["y"] + rb["height"] + 1e-4):
                errors.append(f"Item '{item['id']}' exceeds room '{rid}' bounds")

    # 7. Bedroom shared hallway door endpoints and escape windows
    for b_id, b_name in [("primary_bedroom", "Primary"), ("guest_bedroom", "Guest 1"), ("second_guest_bedroom", "Guest 2")]:
        has_door = any(o.get("type") in ("hinged_door", "pocket_door") and "shared_hallway" in o.get("connected_space_ids", []) and b_id in o.get("connected_space_ids", []) for o in m.get("openings", []))
        if not has_door: errors.append(f"{b_name} bed '{b_id}' missing direct door to shared_hallway")
        has_egress = any(o.get("type") == "egress_window" and b_id in o.get("connected_space_ids", []) and any("exterior" in sp for sp in o.get("connected_space_ids", [])) for o in m.get("openings", []))
        if not has_egress: errors.append(f"{b_name} bed '{b_id}' missing emergency egress window")

    # 8. Corridor vs narrow doorway width & circulation routes
    if space_map.get("shared_hallway") and min(space_map["shared_hallway"]["bounds"]["width"], space_map["shared_hallway"]["bounds"]["height"]) < 3.0:
        errors.append("Shared hallway corridor width < 3.0 ft code minimum")

    def line_intersect(p1, p2, p3, p4):
        x1, y1 = p1; x2, y2 = p2; x3, y3 = p3; x4, y4 = p4
        denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(denom) < 1e-9: return None
        t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
        u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denom
        return u if (0.0 <= t <= 1.0 and 0.0 <= u <= 1.0) else None

    def line_rect_hit(p1, p2, rect):
        rx, ry, rw, rh = rect["x"], rect["y"], rect["width"], rect["height"]
        if (rx < p1[0] < rx + rw and ry < p1[1] < ry + rh) or (rx < p2[0] < rx + rw and ry < p2[1] < ry + rh): return True
        edges = [((rx, ry), (rx + rw, ry)), ((rx + rw, ry), (rx + rw, ry + rh)), ((rx + rw, ry + rh), (rx, ry + rh)), ((rx, ry + rh), (rx, ry))]
        return any(line_intersect(p1, p2, e1, e2) is not None for e1, e2 in edges)

    openings_map = {o["id"]: o for o in m.get("openings", [])}
    solid_furn = [f for f in m.get("furniture", []) if f.get("type") not in ("area_rug", "sectional_sofa")]

    for route in m.get("circulation", []):
        pts = route.get("points", [])
        traversed = set(route.get("doorways_traversed", []))
        for idx in range(len(pts) - 1):
            seg1, seg2 = pts[idx], pts[idx + 1]
            for wid, w in wall_map.items():
                u = line_intersect(seg1, seg2, w["start"], w["end"])
                if u is not None:
                    dist = u * math.hypot(w["end"][0] - w["start"][0], w["end"][1] - w["start"][1])
                    hit_op = any(op["offset_ft"] - 0.2 <= dist <= op["offset_ft"] + op["width_ft"] + 0.2
                                 for op_id in traversed if (op := openings_map.get(op_id)) and op.get("wall_id") == wid)
                    if not hit_op: errors.append(f"Route '{route['id']}' illegal wall intersection with '{wid}'")
            for fu in solid_furn:
                if line_rect_hit(seg1, seg2, fu["bounds"]):
                    errors.append(f"Route '{route['id']}' collides with furniture '{fu['id']}'")

    # 9. Door leaf & swept quadrant clearance validation
    for op in m.get("openings", []):
        if op.get("type") not in ("hinged_door", "glass_door"): continue
        wid = op.get("wall_id")
        if wid not in wall_map: continue
        geom = compute_door_geometry(op, wall_map[wid])
        hx, hy, r = geom["hinge"][0], geom["hinge"][1], geom["radius"]
        target_rooms = [rid for rid in op.get("connected_space_ids", []) if rid != "exterior"]
        for item in m.get("furniture", []) + m.get("fixtures", []):
            if item.get("type") in ("area_rug", "shelving", "closet_rod") or item.get("room_id") not in target_rooms: continue
            ib = item["bounds"]
            corners = [(ib["x"], ib["y"]), (ib["x"] + ib["width"], ib["y"]),
                       (ib["x"] + ib["width"], ib["y"] + ib["height"]), (ib["x"], ib["y"] + ib["height"])]
            collided = False
            for px, py in corners:
                if math.hypot(px - hx, py - hy) < r - 1e-4:
                    dx, dy = px - hx, py - hy
                    v_c, v_o = (geom["closed"][0] - hx, geom["closed"][1] - hy), (geom["open"][0] - hx, geom["open"][1] - hy)
                    if dx * v_c[0] + dy * v_c[1] >= -1e-4 and dx * v_o[0] + dy * v_o[1] >= -1e-4:
                        collided = True; break
            if not collided and (line_rect_hit(geom["hinge"], geom["open"], ib) or line_rect_hit(geom["hinge"], geom["closed"], ib)):
                collided = True
            if collided:
                errors.append(f"Door '{op['id']}' sweep collides with '{item['id']}' in room '{item.get('room_id')}'")

    # 10. Trees fit within canvas viewBox
    scale, ox, oy = m["drawing"]["scale_pixels_per_foot"], m["drawing"]["offset_pixels"]["x"], m["drawing"]["offset_pixels"]["y"]
    for t in m.get("trees", []):
        px, py = t["position"]["x"] * scale + ox, t["position"]["y"] * scale + oy
        pr = t["canopy_radius_ft"] * scale
        if px - pr < -1e-4 or px + pr > 1600 + 1e-4 or py - pr < -1e-4 or py + pr > 1200 + 1e-4:
            errors.append(f"Tree '{t['id']}' canopy extends beyond canvas viewBox")

    # 11. Prohibited affirmative compliance claims
    raw_json = json.dumps(m).lower()
    for phrase in ["certified compliant", "permit ready", "code compliant approval"]:
        if phrase in raw_json: errors.append(f"Model contains prohibited compliance claim: '{phrase}'")

    # 12. Design comfort targets (kitchen work aisles & stool frontage, primary tub-to-vanity clearance)
    items_map = {x["id"]: x for x in m.get("fixtures", []) + m.get("furniture", [])}
    if "FIX_KITCHEN_ISLAND" in items_map and "FIX_KITCHEN_COUNTER_W" in items_map:
        isl_b, west_b = items_map["FIX_KITCHEN_ISLAND"]["bounds"], items_map["FIX_KITCHEN_COUNTER_W"]["bounds"]
        w_aisle = isl_b["x"] - (west_b["x"] + west_b["width"])
        if w_aisle < 3.5 - 1e-4:
            errors.append(f"Kitchen west work aisle < 42 inches (actual: {w_aisle * 12:.1f} in)")
    if "FIX_KITCHEN_ISLAND" in items_map and "FIX_KITCHEN_COUNTER_N" in items_map:
        isl_b, n_b = items_map["FIX_KITCHEN_ISLAND"]["bounds"], items_map["FIX_KITCHEN_COUNTER_N"]["bounds"]
        n_aisle = isl_b["y"] - (n_b["y"] + n_b["height"])
        if n_aisle < 3.5 - 1e-4:
            errors.append(f"Kitchen north work aisle < 42 inches (actual: {n_aisle * 12:.1f} in)")
    k_stools = [x for x in m.get("furniture", []) if x.get("room_id") == "kitchen" and x.get("type") == "stool"]
    if "FIX_KITCHEN_ISLAND" in items_map and k_stools:
        frontage_in = (items_map["FIX_KITCHEN_ISLAND"]["bounds"]["width"] / len(k_stools)) * 12
        if frontage_in < 24.0 - 1e-4:
            errors.append(f"Island stool frontage < 24 nominal inches (actual: {frontage_in:.1f} in)")
    if "FIX_PRI_TUB" in items_map and "FIX_PRI_VANITY" in items_map:
        tub_b, van_b = items_map["FIX_PRI_TUB"]["bounds"], items_map["FIX_PRI_VANITY"]["bounds"]
        tv_clear = van_b["y"] - (tub_b["y"] + tub_b["height"])
        if tv_clear < 3.0 - 1e-4:
            errors.append(f"Primary tub to facing vanity clearance < 36 inches (actual: {tv_clear * 12:.1f} in)")
    # Pantry pocket door span must not sit behind the west prep counter (door is on the vertical pantry wall)
    pantry_op = openings_map.get("OP_PANTRY_DOOR")
    if pantry_op and pantry_op.get("wall_id") in wall_map and "FIX_KITCHEN_COUNTER_W" in items_map:
        pw = wall_map[pantry_op["wall_id"]]
        if abs(pw["start"][0] - pw["end"][0]) < 1e-4:
            d0 = min(pw["start"][1], pw["end"][1]) + pantry_op["offset_ft"]
            d1 = d0 + pantry_op["width_ft"]
            wb = items_map["FIX_KITCHEN_COUNTER_W"]["bounds"]
            if max(d0, wb["y"]) < min(d1, wb["y"] + wb["height"]) - 1e-4:
                errors.append(f"Pantry door span (y {d0:.2f}-{d1:.2f}) is blocked by west work counter (y {wb['y']:.2f}-{wb['y'] + wb['height']:.2f})")

    sofa = items_map["FURN_LIVING_SECTIONAL"]["bounds"]
    coffee = items_map["FURN_LIVING_COFFEE_TABLE"]["bounds"]
    for gap in (coffee["x"]-sofa["x"]-2.8, coffee["y"]-sofa["y"]-2.8):
        if gap < 1.5-1e-4: errors.append("Coffee table requires at least 18 inches from both sectional seating runs")
    for op in m["openings"]:
        if op["type"] == "pocket_door":
            wall=wall_map[op["wall_id"]]
            length=math.dist(wall["start"],wall["end"])
            if op["offset_ft"]+2*op["width_ft"] > length+1e-4:
                errors.append(f"Pocket leaf cannot retract completely within {op['wall_id']}")

    return len(errors) == 0, errors


# ==============================================================================
# SVG Generation
# ==============================================================================

def r_tag(x: float, y: float, w: float, h: float, fill="none", stroke="none", sw=0.0, rx=0.0, da="") -> str:
    r_s = f' rx="{rx}"' if rx else ""; sw_s = f' stroke-width="{sw}"' if sw else ""; da_s = f' stroke-dasharray="{da}"' if da else ""
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{fill}" stroke="{stroke}"{sw_s}{r_s}{da_s}/>'


def l_tag(x1: float, y1: float, x2: float, y2: float, stroke="#5f8156", sw=1.2, da="") -> str:
    da_s = f' stroke-dasharray="{da}"' if da else ""
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" stroke-width="{sw}"{da_s}/>'


def c_tag(cx: float, cy: float, r: float, fill="none", stroke="none", sw=0.0, da="") -> str:
    da_s = f' stroke-dasharray="{da}"' if da else ""; sw_s = f' stroke-width="{sw}"' if sw else ""
    return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}" stroke="{stroke}"{sw_s}{da_s}/>'


def render_realistic_tree(tree: Dict[str, Any], scale: float, ox: float, oy: float) -> List[str]:
    """Generate top-down architectural tree with natural clustered outline, branch structure, and leaf accents."""
    seed = int(hashlib.md5(tree["id"].encode("utf-8")).hexdigest()[:8], 16)
    rng = random.Random(seed)

    tcx = tree["position"]["x"] * scale + ox
    tcy = tree["position"]["y"] * scale + oy
    tr_px = tree["canopy_radius_ft"] * scale
    trunk_r = max(4.0, tree["trunk_radius_ft"] * scale)
    base_lobes = tree.get("lobe_count", 9)

    lines = [f'    <g id="{tree["id"]}">' ]

    # 1. Outer organic clustered canopy outline
    num_pts = base_lobes * 4
    cluster_pts = []
    for i in range(num_pts):
        ang = 2.0 * math.pi * i / num_pts
        harmonic = 0.08 * math.cos(base_lobes * ang) + 0.04 * math.sin(2 * base_lobes * ang)
        jitter = rng.uniform(-0.03, 0.03)
        cr = tr_px * (0.92 + harmonic + jitter)
        cluster_pts.append((tcx + cr * math.cos(ang), tcy + cr * math.sin(ang)))

    d_outer = [f"M {cluster_pts[0][0]:.1f} {cluster_pts[0][1]:.1f}"]
    n = len(cluster_pts)
    for i in range(n):
        p0, p1, p2, p3 = cluster_pts[i - 1], cluster_pts[i], cluster_pts[(i + 1) % n], cluster_pts[(i + 2) % n]
        c1x, c1y = p1[0] + (p2[0] - p0[0]) / 6.0, p1[1] + (p2[1] - p0[1]) / 6.0
        c2x, c2y = p2[0] - (p3[0] - p1[0]) / 6.0, p2[1] - (p3[1] - p1[1]) / 6.0
        d_outer.append(f"C {c1x:.1f} {c1y:.1f}, {c2x:.1f} {c2y:.1f}, {p2[0]:.1f} {p2[1]:.1f}")
    lines.append(f'      <path d="{" ".join(d_outer)} Z" fill="#e2e8ce" fill-opacity="0.55" stroke="#4d734c" stroke-width="1.4"/>')

    # 2. Secondary inner layered foliage wash with subtle green transparency
    num_inner_pts = base_lobes * 3
    inner_pts = []
    phase_shift = rng.uniform(0.1, 0.4)
    for i in range(num_inner_pts):
        ang = 2.0 * math.pi * i / num_inner_pts + phase_shift
        harmonic = 0.07 * math.cos(base_lobes * ang)
        jitter = rng.uniform(-0.03, 0.03)
        cr = tr_px * (0.76 + harmonic + jitter)
        inner_pts.append((tcx + cr * math.cos(ang), tcy + cr * math.sin(ang)))

    d_inner = [f"M {inner_pts[0][0]:.1f} {inner_pts[0][1]:.1f}"]
    ni = len(inner_pts)
    for i in range(ni):
        p0, p1, p2, p3 = inner_pts[i - 1], inner_pts[i], inner_pts[(i + 1) % ni], inner_pts[(i + 2) % ni]
        c1x, c1y = p1[0] + (p2[0] - p0[0]) / 6.0, p1[1] + (p2[1] - p0[1]) / 6.0
        c2x, c2y = p2[0] - (p3[0] - p1[0]) / 6.0, p2[1] - (p3[1] - p1[1]) / 6.0
        d_inner.append(f"C {c1x:.1f} {c1y:.1f}, {c2x:.1f} {c2y:.1f}, {p2[0]:.1f} {p2[1]:.1f}")
    lines.append(f'      <path d="{" ".join(d_inner)} Z" fill="#d5e0be" fill-opacity="0.40" stroke="#729669" stroke-width="0.9" stroke-dasharray="4 3"/>')

    # 3. Soft internal foliage cluster discs
    lines.append('      <g fill="#cddab2" fill-opacity="0.30" stroke="none">')
    for k in range(base_lobes):
        c_ang = 2.0 * math.pi * k / base_lobes + rng.uniform(-0.15, 0.15)
        c_dist = tr_px * rng.uniform(0.40, 0.65)
        cl_r = tr_px * rng.uniform(0.20, 0.32)
        lines.append(f'        <circle cx="{tcx + c_dist * math.cos(c_ang):.1f}" cy="{tcy + c_dist * math.sin(c_ang):.1f}" r="{cl_r:.1f}"/>')
    lines.append('      </g>')

    # 4. Varied architectural branch structure (main radiating limbs + secondary forking twigs)
    lines.append('      <g fill="none" stroke="#4d734c" stroke-width="1.6" stroke-linecap="round">')
    twig_lines = []
    leaf_accents = []

    for k in range(base_lobes):
        ang = 2.0 * math.pi * k / base_lobes + rng.uniform(-0.10, 0.10)
        bx1 = tcx + trunk_r * math.cos(ang)
        by1 = tcy + trunk_r * math.sin(ang)

        fork_r = tr_px * rng.uniform(0.48, 0.60)
        bend_ang = ang + rng.uniform(-0.08, 0.08)
        bx2 = tcx + fork_r * math.cos(bend_ang)
        by2 = tcy + fork_r * math.sin(bend_ang)
        lines.append(f'        <line x1="{bx1:.1f}" y1="{by1:.1f}" x2="{bx2:.1f}" y2="{by2:.1f}"/>')

        twig_spread = rng.uniform(0.18, 0.26)
        t1_ang = bend_ang - twig_spread
        t1_r = tr_px * rng.uniform(0.80, 0.88)
        tx1, ty1 = tcx + t1_r * math.cos(t1_ang), tcy + t1_r * math.sin(t1_ang)
        twig_lines.append(f'        <line x1="{bx2:.1f}" y1="{by2:.1f}" x2="{tx1:.1f}" y2="{ty1:.1f}"/>')

        t2_ang = bend_ang + twig_spread
        t2_r = tr_px * rng.uniform(0.80, 0.88)
        tx2, ty2 = tcx + t2_r * math.cos(t2_ang), tcy + t2_r * math.sin(t2_ang)
        twig_lines.append(f'        <line x1="{bx2:.1f}" y1="{by2:.1f}" x2="{tx2:.1f}" y2="{ty2:.1f}"/>')

        for lx, ly, l_ang in [(tx1, ty1, t1_ang), (tx2, ty2, t2_ang)]:
            cos_a, sin_a = math.cos(l_ang), math.sin(l_ang)
            leaf_accents.append(f'        <ellipse cx="{lx + 3.0*cos_a:.1f}" cy="{ly + 3.0*sin_a:.1f}" rx="3.5" ry="1.8" transform="rotate({math.degrees(l_ang):.1f} {lx + 3.0*cos_a:.1f} {ly + 3.0*sin_a:.1f})" fill="#4d734c" fill-opacity="0.75" stroke="#3b5e3a" stroke-width="0.5"/>')
            leaf_accents.append(f'        <ellipse cx="{lx + 5.0*cos_a + 2.0*sin_a:.1f}" cy="{ly + 5.0*sin_a - 2.0*cos_a:.1f}" rx="2.8" ry="1.4" transform="rotate({math.degrees(l_ang - 0.4):.1f} {lx + 5.0*cos_a + 2.0*sin_a:.1f} {ly + 5.0*sin_a - 2.0*cos_a:.1f})" fill="#5f8156" fill-opacity="0.7" stroke="#3b5e3a" stroke-width="0.4"/>')

    lines.append('      </g>')
    lines.append('      <g fill="none" stroke="#5f8156" stroke-width="1.1" stroke-linecap="round">')
    lines.extend(twig_lines)
    lines.append('      </g>')
    lines.append('      <g>')
    lines.extend(leaf_accents)
    lines.append('      </g>')

    # 5. Trunk and center core
    lines.append(f'      <circle cx="{tcx:.1f}" cy="{tcy:.1f}" r="{trunk_r:.1f}" fill="#3b5e3a"/>')
    lines.append(f'      <circle cx="{tcx:.1f}" cy="{tcy:.1f}" r="{trunk_r * 1.6:.1f}" fill="none" stroke="#3b5e3a" stroke-width="1.0" stroke-dasharray="2 2"/>')
    lines.append('    </g>')
    return lines


def generate_svg(m: Dict[str, Any]) -> str:
    """Generate deterministic, responsive, polished architectural SVG floor plan."""
    scale = float(m["drawing"]["scale_pixels_per_foot"])
    ox, oy = float(m["drawing"]["offset_pixels"]["x"]), float(m["drawing"]["offset_pixels"]["y"])

    def to_px(x_ft: float, y_ft: float) -> Tuple[float, float]:
        return (x_ft * scale + ox, y_ft * scale + oy)

    lines: List[str] = [
        '<svg class="floor-plan" aria-hidden="true" focusable="false" viewBox="0 0 1600 1200" xmlns="http://www.w3.org/2000/svg">',
        '  <defs>',
        '    <pattern id="fp-pave" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M 40 0 H 0 V 40" fill="none" stroke="#b9c9a8" stroke-width="0.9"/></pattern>',
        '    <pattern id="fp-bath-tile" width="16" height="16" patternUnits="userSpaceOnUse"><path d="M 16 0 H 0 V 16" fill="none" stroke="#b9c9a8" stroke-width="0.75"/></pattern>',
        '    <pattern id="fp-wood" width="48" height="12" patternUnits="userSpaceOnUse"><line x1="0" y1="12" x2="48" y2="12" stroke="#d5deca" stroke-width="0.7"/><line x1="24" y1="0" x2="24" y2="12" stroke="#d5deca" stroke-width="0.7"/></pattern>',
        '  </defs>',
        '  <rect width="1600" height="1200" fill="#f3efe0"/>',
        '  <g class="plan-shell">',
        '    <rect x="40" y="40" width="1520" height="1120" fill="none" stroke="#8eaa80" stroke-width="1.1" stroke-dasharray="6 6"/>',
        '    <path d="M 40 1050 H 1560 M 40 1146 H 1560" fill="none" stroke="#8eaa80" stroke-width="1.1"/>',
        '    <path d="M 1344 380 H 1370 V 1050 H 1330" fill="none" stroke="#8eaa80" stroke-width="1.2" stroke-dasharray="4 4"/>',
        '    <g fill="none" stroke="#5f8156" stroke-width="1.4"><rect x="476" y="1042" width="40" height="15" rx="3"/><rect x="476" y="1066" width="40" height="15" rx="3"/><rect x="476" y="1090" width="40" height="15" rx="3"/><rect x="476" y="1114" width="40" height="15" rx="3"/></g>'
    ]

    # Real wall segments cut at openings
    wall_ops = defaultdict(list)
    for op in m["openings"]: wall_ops[op["wall_id"]].append(op)
    wall_colors = {"exterior": "#3b5e3a", "interior_bearing": "#3b5e3a", "plumbing": "#4d734c", "partition": "#4d734c"}

    for w in m["walls"]:
        wid, w1, w2, thick = w["id"], w["start"], w["end"], float(w["thickness"])
        color = wall_colors.get(w.get("type"), "#3b5e3a")
        is_horiz = abs(w1[1] - w2[1]) < 1e-4
        wlen = abs(w2[0] - w1[0]) if is_horiz else abs(w2[1] - w1[1])
        ops = sorted(wall_ops[wid], key=lambda o: o["offset_ft"])
        intervals, curr = [], 0.0
        for op in ops:
            if op["offset_ft"] > curr: intervals.append((curr, op["offset_ft"]))
            curr = max(curr, op["offset_ft"] + op["width_ft"])
        if curr < wlen: intervals.append((curr, wlen))

        for ta, tb in intervals:
            if tb - ta < 0.01: continue
            if is_horiz:
                xa = 0.0 if ta == 0 and wid in ["W_EXT_N", "W_EXT_S"] else w1[0] + ta
                xb = 64.0 if tb == wlen and wid in ["W_EXT_N", "W_EXT_S"] else w1[0] + tb
                lines.append(f'    {r_tag(xa*scale + ox, (w1[1] - thick/2.0)*scale + oy, (xb - xa)*scale, thick*scale, color, color, 0.5)}')
            else:
                ya = 0.75 if ta == 0 and wid in ["W_EXT_W", "W_EXT_E"] else w1[1] + ta
                yb = 53.25 if tb == wlen and wid in ["W_EXT_W", "W_EXT_E"] else w1[1] + tb
                lines.append(f'    {r_tag((w1[0] - thick/2.0)*scale + ox, ya*scale + oy, thick*scale, (yb - ya)*scale, color, color, 0.5)}')

    # Openings: Doors, Sliders, Pocket Doors, Windows
    for op in m["openings"]:
        wid, op_type = op["wall_id"], op["type"]
        w = next(item for item in m["walls"] if item["id"] == wid)
        thick, is_horiz, op_w_px = float(w["thickness"]), abs(w["start"][1] - w["end"][1]) < 1e-4, op["width_ft"] * scale
        ox_ft = w["start"][0] + (op["offset_ft"] if is_horiz else 0)
        oy_ft = w["start"][1] + (0 if is_horiz else op["offset_ft"])
        op_px, op_py = to_px(ox_ft, oy_ft)

        if op_type in ("hinged_door", "glass_door"):
            geom = compute_door_geometry(op, w)
            hx, hy = to_px(*geom["hinge"]); cx_px, cy_px = to_px(*geom["closed"]); ox_px, oy_px = to_px(*geom["open"])
            dc = "#3b5e3a" if w.get("type") == "exterior" else "#4d734c"
            lines.append(f'      {l_tag(hx, hy, ox_px, oy_px, stroke=dc, sw=2.2)}')
            lines.append(f'      <path d="M {cx_px:.1f} {cy_px:.1f} A {geom["radius"]*scale:.1f} {geom["radius"]*scale:.1f} 0 0 {geom["sweep_flag"]} {ox_px:.1f} {oy_px:.1f}" fill="none" stroke="#5f8156" stroke-width="1.2" stroke-dasharray="3 3"/>')
            if w.get("type") == "exterior":
                n_out = (-geom["normal"][0], -geom["normal"][1])
                s1 = to_px(geom["w1"][0] + geom["offset"] * geom["ux"] + (geom["thick"] / 2.0) * n_out[0], geom["w1"][1] + geom["offset"] * geom["uy"] + (geom["thick"] / 2.0) * n_out[1])
                s2 = to_px(geom["w1"][0] + (geom["offset"] + geom["w_ft"]) * geom["ux"] + (geom["thick"] / 2.0) * n_out[0], geom["w1"][1] + (geom["offset"] + geom["w_ft"]) * geom["uy"] + (geom["thick"] / 2.0) * n_out[1])
                lines.append(f'      {l_tag(s1[0], s1[1], s2[0], s2[1], stroke="#729669", sw=1.0)}')

        elif op_type == "sliding_glass_door":
            if is_horiz:
                y1, y2, p_len = op_py - 3, op_py + 3, op_w_px / 3.0 + 8
                lines += [l_tag(op_px, y1, op_px + op_w_px, y1, sw=1.2), l_tag(op_px, y2, op_px + op_w_px, y2, sw=1.2),
                          r_tag(op_px, y1 - 2, p_len, 4, "#f3efe0", "#5f8156", 1.4),
                          r_tag(op_px + op_w_px / 3.0 - 4, y2 - 2, p_len, 4, "#f3efe0", "#5f8156", 1.4),
                          r_tag(op_px + 2 * op_w_px / 3.0 - 8, y1 - 2, p_len, 4, "#f3efe0", "#5f8156", 1.4)]
            else:
                x1, x2, p_len = op_px - 3, op_px + 3, op_w_px / 2.0 + 6
                lines += [l_tag(x1, op_py, x1, op_py + op_w_px, sw=1.2), l_tag(x2, op_py, x2, op_py + op_w_px, sw=1.2),
                          r_tag(x1 - 2, op_py, 4, p_len, "#f3efe0", "#5f8156", 1.4), r_tag(x2 - 2, op_py + op_w_px / 2.0 - 4, 4, p_len, "#f3efe0", "#5f8156", 1.4)]

        elif op_type == "pocket_door":
            # Draw the leaf retracted inside the wall, leaving the doorway visibly open.
            if is_horiz:
                lines += [l_tag(op_px, op_py, op_px + op_w_px, op_py, stroke="#729669", sw=.8, da="2 4"), r_tag(op_px + op_w_px + 1, op_py - 2, op_w_px - 2, 4, "#f3efe0", "#4d734c", 1.2)]
            else:
                lines += [l_tag(op_px, op_py, op_px, op_py + op_w_px, stroke="#729669", sw=.8, da="2 4"), r_tag(op_px - 2, op_py + op_w_px + 1, 4, op_w_px - 2, "#f3efe0", "#4d734c", 1.2)]

        elif op_type == "cased_opening":
            if is_horiz:
                lines += [l_tag(op_px, op_py - thick*scale/2, op_px, op_py + thick*scale/2, "#4d734c", 1.5), l_tag(op_px + op_w_px, op_py - thick*scale/2, op_px + op_w_px, op_py + thick*scale/2, "#4d734c", 1.5)]
            else:
                lines += [l_tag(op_px - thick*scale/2, op_py, op_px + thick*scale/2, op_py, "#4d734c", 1.5), l_tag(op_px - thick*scale/2, op_py + op_w_px, op_px + thick*scale/2, op_py + op_w_px, "#4d734c", 1.5)]

        elif op_type in ("window", "egress_window"):
            if is_horiz:
                lines += [l_tag(op_px, op_py - 2.5, op_px + op_w_px, op_py - 2.5, sw=1.4), l_tag(op_px, op_py + 2.5, op_px + op_w_px, op_py + 2.5, sw=1.4),
                          l_tag(op_px, op_py - thick*scale/2, op_px, op_py + thick*scale/2, "#3b5e3a", 1.2), l_tag(op_px + op_w_px, op_py - thick*scale/2, op_px + op_w_px, op_py + thick*scale/2, "#3b5e3a", 1.2)]
            else:
                lines += [l_tag(op_px - 2.5, op_py, op_px - 2.5, op_py + op_w_px, sw=1.4), l_tag(op_px + 2.5, op_py, op_px + 2.5, op_py + op_w_px, sw=1.4),
                          l_tag(op_px - thick*scale/2, op_py, op_px + thick*scale/2, op_py, "#3b5e3a", 1.2), l_tag(op_px - thick*scale/2, op_py + op_w_px, op_px + thick*scale/2, op_py + op_w_px, "#3b5e3a", 1.2)]
                if op_type == "egress_window":
                    outer_x, sash_len = op_px + thick * scale / 2, op_w_px * 0.8
                    lines += [l_tag(outer_x, op_py, outer_x + sash_len, op_py - 10, "#3b5e3a", 1.6),
                              f'      <path d="M {outer_x:.1f} {op_py + op_w_px:.1f} A {sash_len:.1f} {sash_len:.1f} 0 0 1 {outer_x + sash_len:.1f} {op_py - 10:.1f}" fill="none" stroke="#5f8156" stroke-width="1.1" stroke-dasharray="3 3"/>']

    # Architectural Realistic Trees (Visible at initial stage in .plan-shell)
    for tree in m["trees"]:
        lines.extend(render_realistic_tree(tree, scale, ox, oy))

    lines.append('  </g>')  # End .plan-shell

    # --------------------------------------------------------------------------
    # GROUP 2: .plan-fixtures (Flooring Insets & Architectural Fixtures)
    # --------------------------------------------------------------------------
    lines.append('  <g class="plan-fixtures">')
    for sp_id in ["living_room", "dining_room", "kitchen", "primary_bedroom", "guest_bedroom", "second_guest_bedroom", "hallway_sitting", "primary_dressing"]:
        sb = next((s for s in m["spaces"] if s["id"] == sp_id), None)
        if sb:
            spx, spy = to_px(sb["bounds"]["x"], sb["bounds"]["y"])
            lines.append(f'    {r_tag(spx + 4, spy + 4, sb["bounds"]["width"] * scale - 8, sb["bounds"]["height"] * scale - 8, fill="url(#fp-wood)")}')

    for sp_id, pat, pad in [("courtyard", "fp-pave", 6), ("primary_bathroom", "fp-bath-tile", 4), ("guest_bathroom", "fp-bath-tile", 4)]:
        sb = next((s for s in m["spaces"] if s["id"] == sp_id), None)
        if sb:
            spx, spy = to_px(sb["bounds"]["x"], sb["bounds"]["y"])
            lines.append(f'    {r_tag(spx + pad, spy + pad, sb["bounds"]["width"] * scale - pad * 2, sb["bounds"]["height"] * scale - pad * 2, fill=f"url(#{pat})")}')

    for fx in m["fixtures"]:
        b, ftype = fx["bounds"], fx["type"]
        fx_px, fx_py = to_px(b["x"], b["y"]); fw_px, fh_px = b["width"] * scale, b["height"] * scale
        if ftype in ("countertop", "range"):
            lines.append(f'    {r_tag(fx_px, fx_py, fw_px, fh_px, "#ece9dc", "#5f8156", 1.4)}')
            if ftype == "range":
                for cx_o in [fw_px * 0.28, fw_px * 0.72]:
                    for cy_o in [fh_px * 0.32, fh_px * 0.68]: lines.append(f'    {c_tag(fx_px + cx_o, fx_py + cy_o, 6.5, stroke="#5f8156", sw=1.1)}')
        elif ftype == "island":
            lines.append(f'    {r_tag(fx_px, fx_py, fw_px, fh_px, "#ece9dc", "#5f8156", 1.6, rx=4)}')
        elif ftype == "sink":
            lines += [r_tag(fx_px, fx_py, fw_px, fh_px, "#f3efe0", "#5f8156", 1.3, rx=3), l_tag(fx_px + fw_px/2, fx_py, fx_px + fw_px/2, fx_py + fh_px, "#5f8156", 1), c_tag(fx_px + fw_px/2, fx_py + fh_px/2, 2, fill="#5f8156")]
        elif ftype == "refrigerator":
            lines += [r_tag(fx_px, fx_py, fw_px, fh_px, "#ece9dc", "#5f8156", 1.4), l_tag(fx_px, fx_py + fh_px - 6, fx_px + fw_px, fx_py + fh_px - 6, sw=1.1)]
        elif ftype in ("double_vanity", "vanity"):
            lines.append(f'    {r_tag(fx_px, fx_py, fw_px, fh_px, "#ece9dc", "#5f8156", 1.4)}')
            cxs = [fw_px * 0.28, fw_px * 0.72] if ftype == "double_vanity" else [fw_px * 0.5]
            for cx_o in cxs: lines.append(f'    <ellipse cx="{fx_px + cx_o:.1f}" cy="{fx_py + fh_px * 0.5:.1f}" rx="12" ry="8" fill="#f3efe0" stroke="#5f8156" stroke-width="1.2"/>')
        elif ftype == "freestanding_tub":
            lines += [r_tag(fx_px, fx_py, fw_px, fh_px, "#f3efe0", "#5f8156", 1.6, rx=20), r_tag(fx_px + 5, fx_py + 5, fw_px - 10, fh_px - 10, rx=15, stroke="#5f8156", sw=1.0), c_tag(fx_px + 16, fx_py + fh_px / 2, 2, fill="#5f8156")]
        elif ftype == "full_depth_tub":
            lines += [r_tag(fx_px, fx_py, fw_px, fh_px, "#ece9dc", "#5f8156", 1.4),
                      l_tag(fx_px, fx_py + 16, fx_px + fw_px, fx_py + 16, "#8eaa80", 0.9, da="3 3"),
                      l_tag(fx_px, fx_py + fh_px - 16, fx_px + fw_px, fx_py + fh_px - 16, "#8eaa80", 0.9, da="3 3"),
                      r_tag(fx_px + 4, fx_py + 18, fw_px - 8, fh_px - 36, "#f3efe0", "#5f8156", 1.2, rx=14),
                      c_tag(fx_px + fw_px / 2, fx_py + 26, 3, fill="#5f8156")]
        elif ftype == "walk_in_shower":
            lines += [r_tag(fx_px, fx_py, fw_px, fh_px, stroke="#5f8156", sw=1.5), l_tag(fx_px, fx_py, fx_px + fw_px, fx_py + fh_px, "#b9c9a8", 0.9), l_tag(fx_px + fw_px, fx_py, fx_px, fx_py + fh_px, "#b9c9a8", 0.9), c_tag(fx_px + fw_px / 2, fx_py + fh_px / 2, 4, "#f3efe0", "#5f8156", 1.2)]
        elif ftype == "water_closet":
            lines += [r_tag(fx_px, fx_py, fw_px, 10, "#ece9dc", "#5f8156", 1.3, rx=2), f'    <ellipse cx="{fx_px + fw_px / 2:.1f}" cy="{fx_py + 10 + (fh_px - 10) / 2:.1f}" rx="{fw_px / 2 - 2:.1f}" ry="{(fh_px - 10) / 2:.1f}" fill="#f3efe0" stroke="#5f8156" stroke-width="1.3"/>']
        elif ftype == "tub_shower_combo":
            lines += [r_tag(fx_px, fx_py, fw_px, fh_px, "#ece9dc", "#5f8156", 1.4, rx=4), r_tag(fx_px + 4, fx_py + 4, fw_px - 8, fh_px - 8, "#f3efe0", "#5f8156", 1.1, rx=14), c_tag(fx_px + 14, fx_py + fh_px / 2, 3, fill="#5f8156")]
        elif ftype == "washer_dryer":
            lines += [r_tag(fx_px, fx_py, fw_px, fh_px, "#ece9dc", "#5f8156", 1.4), c_tag(fx_px + fw_px * 0.26, fx_py + fh_px * 0.5, 12, stroke="#5f8156", sw=1.2), c_tag(fx_px + fw_px * 0.74, fx_py + fh_px * 0.5, 12, stroke="#5f8156", sw=1.2)]
        elif ftype == "counter_sink":
            lines += [r_tag(fx_px, fx_py, fw_px, fh_px, "#ece9dc", "#5f8156", 1.4), r_tag(fx_px + 8, fx_py + 6, fw_px - 16, fh_px - 12, "#f3efe0", "#5f8156", 1.2, rx=3)]
        elif ftype == "fountain":
            fcx, fcy = fx_px + fw_px / 2, fx_py + fh_px / 2
            lines += [c_tag(fcx, fcy, fw_px / 2, "#f3efe0", "#5f8156", 1.5), c_tag(fcx, fcy, fw_px * 0.35, stroke="#8eaa80", sw=1.0, da="3 3"), c_tag(fcx, fcy, 3, fill="#3b5e3a")]
        elif ftype in ("shelving", "closet_rod"):
            lines.append(f'    {r_tag(fx_px, fx_py, fw_px, fh_px, stroke="#729669", sw=1.0, da="3 3")}')
        elif ftype == "built_in_closet":
            lines += [r_tag(fx_px, fx_py, fw_px, fh_px, stroke="#729669", sw=1.2, da="4 3"),
                      l_tag(fx_px + 4, fx_py + fh_px / 2, fx_px + fw_px - 4, fx_py + fh_px / 2, "#5f8156", 1.4),
                      l_tag(fx_px + 4, fx_py + 4, fx_px + fw_px - 4, fx_py + 4, "#8eaa80", 0.9)]
    lines.append('  </g>')  # End .plan-fixtures

    # --------------------------------------------------------------------------
    # GROUP 3: .plan-furniture (Rugs, Movable Furniture & Annotations)
    # --------------------------------------------------------------------------
    lines.append('  <g class="plan-furniture">')
    rug = next((fu for fu in m["furniture"] if fu["type"] == "area_rug"), None)
    if rug:
        rb = rug["bounds"]; r_px, r_py = to_px(rb["x"], rb["y"])
        lines.append(f'    <rect x="{r_px:.1f}" y="{r_py:.1f}" width="{rb["width"] * scale:.1f}" height="{rb["height"] * scale:.1f}" rx="6" fill="#ece9dc" fill-opacity="0.45" stroke="#b9c9a8" stroke-width="1.2" stroke-dasharray="6 4"/>')

    for fu in m["furniture"]:
        ftype, b = fu["type"], fu["bounds"]
        if ftype == "area_rug": continue
        fu_px, fu_py = to_px(b["x"], b["y"]); fw_px, fh_px = b["width"] * scale, b["height"] * scale

        rotation = fu.get("rotation_deg", 0)
        lines.append(f'    <g data-furniture="{fu["id"]}" transform="rotate({rotation} {fu_px + fw_px/2:.1f} {fu_py + fh_px/2:.1f})">')
        if ftype == "sectional_sofa":
            d_px = 2.8 * scale
            path_d = f"M {fu_px} {fu_py} H {fu_px + fw_px} V {fu_py + d_px} H {fu_px + d_px} V {fu_py + fh_px} H {fu_px} Z"
            lines += [f'    <path d="{path_d}" fill="#ece9dc" stroke="#5f8156" stroke-width="1.6" stroke-linejoin="round"/>',
                      f'    {l_tag(fu_px + d_px, fu_py, fu_px + d_px, fu_py + d_px, sw=1.0)}',
                      f'    {l_tag(fu_px + fw_px * 0.6, fu_py, fu_px + fw_px * 0.6, fu_py + d_px, sw=1.0)}',
                      f'    {l_tag(fu_px, fu_py + fh_px * 0.58, fu_px + d_px, fu_py + fh_px * 0.58, sw=1.0)}']
        elif ftype == "coffee_table":
            lines += [r_tag(fu_px, fu_py, fw_px, fh_px, "#f5f2e9", "#5f8156", 1.4, rx=3), r_tag(fu_px + 3, fu_py + 3, fw_px - 6, fh_px - 6, stroke="#8eaa80", sw=0.8)]
        elif ftype in ("armchair", "lounge_chair"):
            lines += [r_tag(fu_px, fu_py, fw_px, fh_px, "#ece9dc", "#5f8156", 1.4, rx=6), r_tag(fu_px + 5, fu_py + 5, fw_px - 10, fh_px - 10, stroke="#8eaa80", sw=0.9, rx=4)]
        elif ftype == "dining_table":
            lines += [r_tag(fu_px, fu_py, fw_px, fh_px, "#ece9dc", "#5f8156", 1.5, rx=4), r_tag(fu_px + 4, fu_py + 4, fw_px - 8, fh_px - 8, stroke="#8eaa80", sw=0.8, rx=2)]
        elif ftype == "dining_chair":
            lines.append(f'    {r_tag(fu_px, fu_py, fw_px, fh_px, "#ece9dc", "#5f8156", 1.2, rx=3)}')
        elif ftype == "stool":
            lines += [c_tag(fu_px + fw_px / 2, fu_py + fh_px / 2, fw_px / 2, fill="#ece9dc", stroke="#5f8156", sw=1.3),
                      c_tag(fu_px + fw_px / 2, fu_py + fh_px / 2, fw_px * 0.3, fill="none", stroke="#8eaa80", sw=0.8)]
        elif ftype in ("king_bed", "queen_bed"):
            pw = (fw_px - 16) / 2.0
            lines += [r_tag(fu_px, fu_py, fw_px, 6, "#3b5e3a", "#3b5e3a", 1.0), r_tag(fu_px, fu_py + 6, fw_px, fh_px - 6, "#ece9dc", "#5f8156", 1.5, rx=4),
                      l_tag(fu_px, fu_py + fh_px * 0.55, fu_px + fw_px, fu_py + fh_px * 0.55, sw=1.1),
                      r_tag(fu_px + 5, fu_py + 10, pw, 18, "#f5f2e9", "#5f8156", 1.1, rx=3), r_tag(fu_px + 11 + pw, fu_py + 10, pw, 18, "#f5f2e9", "#5f8156", 1.1, rx=3)]
        elif ftype == "nightstand":
            lines += [r_tag(fu_px, fu_py, fw_px, fh_px, "#ece9dc", "#5f8156", 1.2, rx=2), c_tag(fu_px + fw_px / 2, fu_py + fh_px / 2, 4, "#f5f2e9", "#5f8156", 0.9)]
        elif ftype in ("dresser", "credenza_bookcase", "wardrobe_closet", "console_table", "writing_desk", "side_table"):
            lines += [r_tag(fu_px, fu_py, fw_px, fh_px, "#ece9dc", "#5f8156", 1.3, rx=2), l_tag(fu_px, fu_py + 4, fu_px + fw_px, fu_py + 4, "#8eaa80", 0.8)]

        lines.append('    </g>')

    # Final stage annotations: North arrow, Scale bar, Footprint dimensions & Room labels
    fp_w, fp_d = float(m["building"]["footprint"]["width_ft"]), float(m["building"]["footprint"]["depth_ft"])
    w_label = f'{int(fp_w)}\'-{int(round((fp_w % 1) * 12))}" OVERALL WIDTH' if fp_w % 1 else f'{int(fp_w)}\'-0" OVERALL WIDTH'
    d_label = f'{int(fp_d)}\'-{int(round((fp_d % 1) * 12))}" DEPTH' if fp_d % 1 else f'{int(fp_d)}\'-0" DEPTH'

    # North arrow in upper right margin
    lines.append('    <g transform="translate(1480, 84)"><circle r="24" fill="none" stroke="#5f8156" stroke-width="1.4"/><path d="M 0 -18 L 7 10 L 0 4 L -7 10 Z" fill="#3b5e3a"/><text y="-28" text-anchor="middle" font-family="Instrument, Arial, sans-serif" font-size="12" font-weight="700" fill="#3b5e3a">N</text></g>')

    # Scale bar in blank north margin centered above overall width dimension
    cx_bar = ox + (fp_w * scale) / 2.0
    bar_x0 = cx_bar - 15.0 * scale
    lines += [
        f'    <g transform="translate({bar_x0:.1f}, 52)">',
        f'      <rect x="0" y="0" width="{10.0*scale:.1f}" height="6" fill="#3b5e3a"/>',
        f'      <rect x="{10.0*scale:.1f}" y="0" width="{10.0*scale:.1f}" height="6" fill="#8eaa80"/>',
        f'      <rect x="{20.0*scale:.1f}" y="0" width="{10.0*scale:.1f}" height="6" fill="#3b5e3a"/>',
        f'      <path d="M 0 0 V 10 M {10.0*scale:.1f} 0 V 10 M {20.0*scale:.1f} 0 V 10 M {30.0*scale:.1f} 0 V 10" stroke="#3b5e3a" stroke-width="1.2"/>',
        f'      <text x="0" y="22" font-family="Instrument, Arial, sans-serif" font-size="10" fill="#4d734c" text-anchor="middle">0\'</text>',
        f'      <text x="{10.0*scale:.1f}" y="22" font-family="Instrument, Arial, sans-serif" font-size="10" fill="#4d734c" text-anchor="middle">10\'</text>',
        f'      <text x="{20.0*scale:.1f}" y="22" font-family="Instrument, Arial, sans-serif" font-size="10" fill="#4d734c" text-anchor="middle">20\'</text>',
        f'      <text x="{30.0*scale:.1f}" y="22" font-family="Instrument, Arial, sans-serif" font-size="10" fill="#4d734c" text-anchor="middle">30\'</text>',
        f'      <text x="{15.0*scale:.1f}" y="36" font-family="Instrument, Arial, sans-serif" font-size="10" letter-spacing="1.5px" fill="#729669" text-anchor="middle">FEET</text>',
        '    </g>'
    ]

    # Footprint dimension lines
    w_px, d_px = fp_w * scale, fp_d * scale
    lines += [
        '    <g font-family="Instrument, Arial, sans-serif" font-size="12" fill="#4d734c" letter-spacing="1px">',
        f'      <path d="M {ox:.1f} 124 H {ox + w_px:.1f} M {ox:.1f} 116 V 168 M {ox + w_px:.1f} 116 V 168" stroke="#729669" stroke-width="1.1" fill="none"/>',
        f'      <path d="M {ox - 6:.1f} 130 L {ox + 6:.1f} 118 M {ox + w_px - 6:.1f} 130 L {ox + w_px + 6:.1f} 118" stroke="#3b5e3a" stroke-width="1.6"/>',
        f'      <text x="{ox + w_px / 2.0:.1f}" y="116" text-anchor="middle" font-weight="600">{w_label}</text>',
        f'      <path d="M 236 {oy:.1f} V {oy + d_px:.1f} M 228 {oy:.1f} H {ox:.1f} M 228 {oy + d_px:.1f} H {ox:.1f}" stroke="#729669" stroke-width="1.1" fill="none"/>',
        f'      <path d="M 230 {oy + 6:.1f} L 242 {oy - 6:.1f} M 230 {oy + d_px + 6:.1f} L 242 {oy + d_px - 6:.1f}" stroke="#3b5e3a" stroke-width="1.6"/>',
        f'      <text x="226" y="{oy + d_px / 2.0:.1f}" text-anchor="end" font-weight="600">{d_label}</text>',
        '    </g>'
    ]

    # Room Annotations & Dimension Labels
    lines.append('    <g font-family="Instrument, Arial, sans-serif" text-anchor="middle">')
    for ann in m["annotations"]:
        ax_px, ay_px = to_px(ann["position"]["x"], ann["position"]["y"])
        # Optional per-annotation font overrides (defaults preserve prior output exactly).
        p_fs = ann.get("primary_font_size", 12)
        p_ls = ann.get("primary_letter_spacing", 2)
        d_fs = ann.get("dimension_font_size", 10)
        d_ls = ann.get("dimension_letter_spacing", 1)
        lines += [f'      <text x="{ax_px:.1f}" y="{ay_px:.1f}" font-size="{p_fs}" font-weight="600" letter-spacing="{p_ls}px" fill="#4d734c">{ann["primary_text"]}</text>',
                  f'      <text x="{ax_px:.1f}" y="{ay_px + 14:.1f}" font-size="{d_fs}" letter-spacing="{d_ls}px" fill="#729669">{ann["dimension_text"]}</text>']
    lines += ['    </g>', '  </g>', '</svg>']

    return "\n".join(lines) + "\n"


# ==============================================================================
# CLI Actions
# ==============================================================================

def execute_write() -> int:
    """Generate SVG, update managed block in index.html and record hash in manifest."""
    with open(MODEL_PATH, "r", encoding="utf-8") as f: model = json.load(f)

    is_valid, errors = validate_model(model)
    if not is_valid:
        print("ERROR: Model validation failed before write:")
        for err in errors: print(f"  - {err}")
        return 1

    svg_content = generate_svg(model)
    with open(SVG_PATH, "w", encoding="utf-8") as f: f.write(svg_content)
    print(f"Successfully wrote standalone SVG: {SVG_PATH}")

    if os.path.exists(INDEX_PATH):
        with open(INDEX_PATH, "r", encoding="utf-8") as f: index_text = f.read()
        pattern = re.compile(re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER), re.DOTALL)
        if not pattern.search(index_text):
            print("ERROR: Could not locate FLOOR_PLAN markers in index.html")
            return 1
        replacement = f"{START_MARKER}\n{svg_content.strip()}\n    {END_MARKER}"
        with open(INDEX_PATH, "w", encoding="utf-8") as f: f.write(pattern.sub(replacement, index_text, count=1))
        print("Successfully updated inline SVG managed block in index.html")

    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f: manifest = json.load(f)
        svg_sha256 = hashlib.sha256(svg_content.encode("utf-8")).hexdigest()
        num_spaces = len(model.get("spaces", []))
        fp_w = int(model.get("building", {}).get("footprint", {}).get("width_ft", 64))
        fp_d = int(model.get("building", {}).get("footprint", {}).get("depth_ft", 54))
        scale_val = int(model.get("drawing", {}).get("scale_pixels_per_foot", 16))
        manifest["entry-floor-plan.svg"] = {
            "source": "Generated by scripts/build_floor_plan.py from assets/brand/floor-plan-model.json",
            "type": "generated conceptual floor-plan diagram (vector)",
            "date": "2026-10-03",
            "inspiration": f"Feedback 1 & 3 PDF (Dallas, TX single-storey courtyard residence concept with {num_spaces} spaces: primary bedroom suite with linked dressing room and ensuite bath, guest bedrooms 1 & 2, central courtyard, kitchen with pantry and island seating, dining for 8, living, and sitting lounge; architectural lobed trees after page 2 reference).",
            "revision": f"Feedback 1 & 3 (2026-10-03): single-storey courtyard residence schematic model with {num_spaces} spaces, 3 bedrooms, Feedback 3 linked bathroom/dressing suite, full-depth tub, enlarged kitchen/island, 8-seat dining, and external escape windows.",
            "scale": f"Dimensioned architectural concept at {scale_val} px/ft scale ({fp_w}ft x {fp_d}ft footprint); planning assumptions only, not surveyed or permit-ready",
            "sha256": svg_sha256
        }
        with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
            f.write("\n")
        print(f"Successfully updated manifest record with SHA256: {svg_sha256}")

    print("All --write targets updated deterministically.")
    return 0


def execute_check() -> int:
    """Validate model, regenerated SVG, managed block and manifest hash exactly."""
    with open(MODEL_PATH, "r", encoding="utf-8") as f: model = json.load(f)

    is_valid, errors = validate_model(model)
    if not is_valid:
        print("FAIL: Model validation failed:")
        for err in errors: print(f"  - {err}")
        return 1

    expected_svg = generate_svg(model)
    if not os.path.exists(SVG_PATH):
        print(f"FAIL: SVG file does not exist: {SVG_PATH}")
        return 1
    with open(SVG_PATH, "r", encoding="utf-8") as f: actual_svg = f.read()

    if actual_svg != expected_svg:
        print("FAIL: Standalone SVG in assets/brand/entry-floor-plan.svg differs from model")
        return 1

    if not os.path.exists(INDEX_PATH):
        print(f"FAIL: index.html does not exist: {INDEX_PATH}")
        return 1
    with open(INDEX_PATH, "r", encoding="utf-8") as f: index_text = f.read()

    match = re.search(re.escape(START_MARKER) + r"(.*?)" + re.escape(END_MARKER), index_text, re.DOTALL)
    if not match:
        print("FAIL: Managed block markers not found in index.html")
        return 1

    if match.group(1).strip() != expected_svg.strip():
        print("FAIL: Inline SVG managed block in index.html differs from model output")
        return 1

    if not os.path.exists(MANIFEST_PATH):
        print(f"FAIL: manifest.json does not exist: {MANIFEST_PATH}")
        return 1
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f: manifest = json.load(f)

    recorded_hash = manifest.get("entry-floor-plan.svg", {}).get("sha256")
    actual_hash = hashlib.sha256(expected_svg.encode("utf-8")).hexdigest()
    if recorded_hash != actual_hash:
        print(f"FAIL: Manifest hash mismatch: recorded {recorded_hash} != computed {actual_hash}")
        return 1

    print("PASS: Model validation passed. Standalone SVG, inline managed block, and manifest hash match exactly.")
    return 0


def execute_validate_only() -> int:
    """Validate model geometry only without checking generated artifacts."""
    with open(MODEL_PATH, "r", encoding="utf-8") as f: model = json.load(f)
    is_valid, errors = validate_model(model)
    if not is_valid:
        print("FAIL: Model validation failed:")
        for err in errors: print(f"  - {err}")
        return 1
    print("PASS: Model geometry validation passed with 0 errors.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Deterministic Floor Plan Generator & Validator")
    parser.add_argument("--write", action="store_true", help="Generate SVG, update index.html managed block and manifest")
    parser.add_argument("--check", action="store_true", help="Validate model, check SVG and managed block for staleness")
    parser.add_argument("--validate-only", action="store_true", help="Validate model geometry without requiring synced outputs")
    args = parser.parse_args()

    if args.write: sys.exit(execute_write())
    elif args.check: sys.exit(execute_check())
    elif args.validate_only: sys.exit(execute_validate_only())
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
