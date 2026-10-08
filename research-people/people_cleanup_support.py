"""Blender asset generator for realistic animated people across all nine study scenes.

Produces 8 reusable pose/angle profiles covering hero walk-and-chat and interior seated/standing scenes:
  1. hero-nathan-walk-turn: Nathan, 64 frames (192x256), walk in place 32f, then turn left and chat 32f
  2. hero-carla-walk-turn: Carla, 64 frames (192x256), retargeted walk 32f, then turn right and chat 32f
  3. carla-seated-talk-right: Carla, 32 frames (256x384), seated on sofa/booth, thighs forward, knees bent, lap/chat
  4. nathan-seated-talk-left: Nathan, 32 frames (256x384), seated on lounge/chair, thighs forward, knees bent, chat
  5. nathan-standing-idle: Nathan, 32 frames (256x384), relaxed upright stance, arms at sides, natural breathing
  6. carla-standing-terrace: Carla, 32 frames (256x384), standing terrace stance looking toward horizon
  7. carla-vanity-back: Carla, 32 frames (256x384), standing back/3-quarter view fully clothed at vanity basin
  8. nathan-counter-idle: Nathan, 32 frames (256x384), standing at hospitality counter/aisle, hand near counter

Coordinator invocation from project root:
  /Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup --disable-autoexec \\
      --python research-people/build_scene_people.py -- [--preview] [--profile <name>] [--all] [--resume] [--samples 20]

Flags:
  --preview           renders preview frames (1, 32, 48, 64 for hero; 1, 16, 32 for interiors) and stops
  --profile <name>    renders a single profile by name
  --all               (default) renders all 8 profiles in sequence
  --resume            skips profiles whose output strip PNG and metadata already exist
  --samples N         Eevee samples per frame (default 20, clamp 16..32)
"""
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector, Euler, Quaternion

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

ROOT = Path(__file__).resolve().parent
SRC_N = ROOT / "source"
SRC_C = ROOT / "source-carla"
FBX_N = SRC_N / "rp_nathan_animated_003_walking.fbx"
FBX_C = SRC_C / "rp_carla_rigged_001_u3d.fbx"
RENDERED_BASE = ROOT / "rendered-scenes"
SITE_PEOPLE = ROOT.parent / "site" / "assets" / "people"
SCENES_DIR = SITE_PEOPLE / "scenes"
PROVENANCE_FILE = SCENES_DIR / "provenance.json"

# Profile definitions: lock_ortho=0.0 allows dynamic union fit with safety padding to prevent clipping
PROFILES = {
    "hero-nathan-walk-turn": {
        "person": "Nathan",
        "frame_count": 64,
        "frame_w": 192,
        "frame_h": 256,
        "elevation_deg": 30.54,
        "cam_from": Vector((6.0, -8.0, 6.8)),
        "cam_at": Vector((0.0, 0.0, 0.9)),
        "target_body_h": 224.0,
        "target_foot_row": 240.0,
        "lock_ortho": 0.0,
        "is_seated": False,
        "motion_kind": "hero_walk_turn",
        "turn_dir": 1,  # turn left (face screen-left/down toward Carla)
        "description": "Hero backyard sequence: 32 frames walking in place, then 32 frames blending to quiet stance and rotating left to face Carla in conversation."
    },
    "hero-carla-walk-turn": {
        "person": "Carla",
        "frame_count": 64,
        "frame_w": 192,
        "frame_h": 256,
        "elevation_deg": 30.54,
        "cam_from": Vector((6.0, -8.0, 6.8)),
        "cam_at": Vector((0.0, 0.0, 0.9)),
        "target_body_h": 224.0,
        "target_foot_row": 240.0,
        "lock_ortho": 0.0,
        "is_seated": False,
        "motion_kind": "hero_walk_turn",
        "turn_dir": -1,  # turn right (face screen-right/up toward Nathan)
        "description": "Hero backyard sequence: 32 frames retargeted walk in place, then 32 frames blending to quiet stance and rotating right to face Nathan in conversation."
    },
    "carla-seated-talk-right": {
        "person": "Carla",
        "frame_count": 32,
        "frame_w": 256,
        "frame_h": 384,
        "elevation_deg": 15.0,
        "cam_from": Vector((-5.5, -8.0, 3.30)),
        "cam_at": Vector((0.0, 0.0, 0.7)),
        "target_body_h": 320.0,
        "target_foot_row": 352.0,
        "lock_ortho": 0.0,
        "is_seated": True,
        "motion_kind": "seated_talk",
        "turn_dir": 1,  # face slightly right
        "description": "Interior seated profile: natural posture on sofa/booth, thighs forward, knees bent, feet on floor, lap/arm gestures turning right."
    },
    "nathan-seated-talk-left": {
        "person": "Nathan",
        "frame_count": 32,
        "frame_w": 256,
        "frame_h": 384,
        "elevation_deg": 15.0,
        "cam_from": Vector((5.5, -8.0, 3.30)),
        "cam_at": Vector((0.0, 0.0, 0.7)),
        "target_body_h": 320.0,
        "target_foot_row": 352.0,
        "lock_ortho": 0.0,
        "is_seated": True,
        "motion_kind": "seated_talk",
        "turn_dir": -1,  # face slightly left
        "description": "Interior seated profile: natural posture on lounge/window chair, thighs forward, knees bent, conversational gesturing turning left."
    },
    "nathan-standing-idle": {
        "person": "Nathan",
        "frame_count": 32,
        "frame_w": 256,
        "frame_h": 384,
        "elevation_deg": 15.0,
        "cam_from": Vector((0.0, -8.0, 2.94)),
        "cam_at": Vector((0.0, 0.0, 0.9)),
        "target_body_h": 320.0,
        "target_foot_row": 352.0,
        "lock_ortho": 0.0,
        "is_seated": False,
        "motion_kind": "standing_idle",
        "turn_dir": 0,
        "description": "Interior standing idle profile: upright relaxed stance, natural weight distribution, subtle breathing and head rotation."
    },
    "carla-standing-terrace": {
        "person": "Carla",
        "frame_count": 32,
        "frame_w": 256,
        "frame_h": 384,
        "elevation_deg": 15.0,
        "cam_from": Vector((3.5, -7.5, 2.94)),
        "cam_at": Vector((0.0, 0.0, 0.9)),
        "target_body_h": 320.0,
        "target_foot_row": 352.0,
        "lock_ortho": 0.0,
        "is_seated": False,
        "motion_kind": "standing_terrace",
        "turn_dir": 1,
        "description": "Standing terrace profile: three-quarters stance looking out toward horizon and canopy, natural relaxed arm and head motion."
    },
    "carla-vanity-back": {
        "person": "Carla",
        "frame_count": 32,
        "frame_w": 256,
        "frame_h": 384,
        "elevation_deg": 12.0,
        "cam_from": Vector((1.5, 8.0, 2.5)),
        "cam_at": Vector((0.0, 0.0, 0.85)),
        "target_body_h": 320.0,
        "target_foot_row": 352.0,
        "lock_ortho": 0.0,
        "is_seated": False,
        "motion_kind": "standing_vanity",
        "turn_dir": 0,
        "description": "Bathroom vanity profile: standing back/three-quarters view fully clothed at vanity basin looking into mirror, subtle posture and hand shifts."
    },
    "nathan-counter-idle": {
        "person": "Nathan",
        "frame_count": 32,
        "frame_w": 256,
        "frame_h": 384,
        "elevation_deg": 15.0,
        "cam_from": Vector((-1.5, -8.0, 2.94)),
        "cam_at": Vector((0.0, 0.0, 0.9)),
        "target_body_h": 320.0,
        "target_foot_row": 352.0,
        "lock_ortho": 0.0,
        "is_seated": False,
        "motion_kind": "standing_counter",
        "turn_dir": 0,
        "description": "Hospitality counter profile: natural standing posture with hand near counter height, subtle welcoming nod and conversational body shift."
    }
}


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    opt = lambda flag, default: type(default)(argv[argv.index(flag) + 1]) if flag in argv else default
    return {
        "preview": "--preview" in argv,
        "all": "--all" in argv or "--profile" not in argv,
        "profile": opt("--profile", ""),
        "resume": "--resume" in argv,
        "samples": max(16, min(32, opt("--samples", 20))),
    }


def fix_nathan_textures() -> dict:
    """Point Nathan's diffuse and normal maps to real files under source/."""
    fixed = {}
    for img in bpy.data.images:
        if not img.filepath:
            continue
        name = re.split(r"[\\/]", img.filepath)[-1]
        for cand in (SRC_N / "tex" / name, SRC_N / ("tex\\" + name), SRC_N / name):
            if cand.is_file():
                img.filepath = str(cand)
                img.reload()
                fixed[img.name] = str(cand)
                break
        else:
            for f in (SRC_N / "tex").glob("*"):
                if f.stem == Path(name).stem:
                    img.filepath = str(f)
                    img.reload()
                    fixed[img.name] = str(f)
                    break
    return fixed


def mute_nathan_materials() -> None:
    """Warm, muted clothing for Nathan: modest desaturation, matte surface."""
    for mat in bpy.data.materials:
        if not mat.use_nodes:
            continue
        tree = mat.node_tree
        bsdf = next((n for n in tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf is None:
            continue
        link = next((l for l in tree.links if l.to_socket == bsdf.inputs["Base Color"]), None)
        if link is not None:
            hsv = tree.nodes.new("ShaderNodeHueSaturation")
            hsv.inputs["Saturation"].default_value = 0.78
            hsv.inputs["Value"].default_value = 0.96
            tree.links.new(link.from_socket, hsv.inputs["Color"])
            tree.links.new(hsv.outputs["Color"], bsdf.inputs["Base Color"])
        bsdf.inputs["Roughness"].default_value = 0.8
        if "Specular IOR Level" in bsdf.inputs:
            bsdf.inputs["Specular IOR Level"].default_value = 0.2
        elif "Specular" in bsdf.inputs:
            bsdf.inputs["Specular"].default_value = 0.2


def carla_material(meshes) -> dict:
    """Carla's unmodified diffuse texture, matte surface, preserves darker skin tone naturally."""
    dif = None
    for cand in (SRC_C / "tex" / "rp_carla_rigged_001_dif.jpg",
                 SRC_C / "tex" / "rp_carla_rigged_001_dif.png",
                 SRC_C / "rp_carla_rigged_001_dif.jpg"):
        if cand.is_file():
            dif = cand
            break
    if dif is None:
        cands = list((SRC_C / "tex").glob("*dif*"))
        if cands:
            dif = cands[0]
        else:
            raise FileNotFoundError(f"Carla diffuse texture not found under {SRC_C}")

    mat = bpy.data.materials.new("carla_scan")
    mat.use_nodes = True
    tree = mat.node_tree
    bsdf = next(n for n in tree.nodes if n.type == "BSDF_PRINCIPLED")
    tex = tree.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(str(dif), check_existing=True)
    tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.8
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.2
    elif "Specular" in bsdf.inputs:
        bsdf.inputs["Specular"].default_value = 0.2
    for obj in meshes:
        obj.data.materials.clear()
        obj.data.materials.append(mat)
    return {tex.image.name: str(dif)}


def get_bone(arm, short_name: str):
    """Find a pose bone across both Nathan (prefixed) and Carla (flat) naming."""
    if arm is None or arm.pose is None:
        return None
    pb = arm.pose.bones.get(short_name)
    if pb is not None:
        return pb
    prefixed = f"rp_nathan_animated_003_walking_{short_name}"
    pb = arm.pose.bones.get(prefixed)
    if pb is not None:
        return pb
    for pb in arm.pose.bones:
        if pb.name.endswith(short_name) or pb.name.endswith(f"_{short_name}"):
            return pb
    return None


def find_hip(arm):
    named = [b for b in arm.pose.bones if re.search(r"hip|pelvis", b.name, re.I)]
    pool = named or [b for b in arm.pose.bones if b.parent is None]
    return min(pool, key=lambda b: len(b.parent_recursive))


def bake_nathan_walk(first: int, last: int) -> dict:
    """Read Nathan's evaluated bone matrices for walking frames 10..41 from donor FBX."""
    bpy.ops.import_scene.fbx(filepath=str(FBX_N), use_image_search=False, use_anim=True)
    scene = bpy.context.scene
    arm = next(o for o in scene.objects if o.type == "ARMATURE")
    if arm.animation_data is None or arm.animation_data.action is None:
        arm.animation_data_create().action = bpy.data.actions[0]
    action = arm.animation_data.action
    lo, hi = (int(v) for v in action.frame_range)
    frames = list(range(first, min(last + 1, hi) + 1))
    src = {
        "action": action.name,
        "frames": frames,
        "fps_raw": (scene.render.fps, scene.render.fps_base),
        "fps": float(scene.render.fps / scene.render.fps_base),
        "rest": {b.name: b.matrix_local.copy() for b in arm.data.bones},
        "parents": {b.name: (b.parent.name if b.parent else None) for b in arm.data.bones},
        "poses": {},
        "worlds": {},
    }
    for f in frames:
        scene.frame_set(f)
        src["worlds"][f] = arm.matrix_world.copy()
        src["poses"][f] = {pb.name: pb.matrix.copy() for pb in arm.pose.bones}
    src["world_rest"] = src["worlds"][frames[0]].copy()
    for obj in list(scene.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.actions.remove(action)
    bpy.data.orphans_purge(do_recursive=True)
    return src


_CACHED_WALK_SRC = None


def get_walk_src() -> dict:
    """Cached accessor for Nathan's evaluated donor walk matrices (frames 10..41)."""
    global _CACHED_WALK_SRC
    if _CACHED_WALK_SRC is None:
        _CACHED_WALK_SRC = bake_nathan_walk(10, 41)
    return _CACHED_WALK_SRC


def apply_walk_to_rig(src: dict, arm, target_frames: list, source_frames: list = None):
    """Apply source walk poses onto arm's bones (Carla or Nathan) using rest-aware basis math.
    Bakes verified native frames 10..41 to output frames 1..32 with all bones using quaternion modes.
    """
    names_s = set(src["rest"])
    hip_s = next((n for n in names_s if n == "hip" or n.endswith("_hip")), None)
    prefix_s = hip_s[:-len("hip")] if hip_s else ""
    
    bones = arm.data.bones
    hip_t = next((b.name for b in bones if b.name == "hip" or b.name.endswith("_hip")), None)
    prefix_t = hip_t[:-len("hip")] if hip_t else ""

    mapping = {}
    for b in bones:
        base_name = b.name[len(prefix_t):] if b.name.startswith(prefix_t) else b.name
        source_name = prefix_s + base_name
        if source_name in names_s:
            mapping[b.name] = source_name
        elif b.name in names_s:
            mapping[b.name] = b.name

    for b in bones:
        b.use_inherit_rotation, b.inherit_scale, b.use_local_location = True, "FULL", True
    order, queue = [], [b for b in bones if b.parent is None]
    while queue:
        b = queue.pop(0)
        order.append(b)
        queue.extend(b.children)

    Wt = arm.matrix_world.copy()
    Wt_inv, Rt_inv = Wt.inverted(), Wt.to_3x3().normalized().inverted()
    rest_t = {b.name: b.matrix_local.copy() for b in bones}
    rest_s, Ws0 = src["rest"], src["world_rest"]

    up_t = prefix_t + "upperleg_l" if (prefix_t + "upperleg_l") in rest_t else "upperleg_l"
    foot_t = prefix_t + "foot_l" if (prefix_t + "foot_l") in rest_t else "foot_l"
    up_s = prefix_s + "upperleg_l" if (prefix_s + "upperleg_l") in rest_s else "upperleg_l"
    foot_s = prefix_s + "foot_l" if (prefix_s + "foot_l") in rest_s else "foot_l"

    leg_len = lambda rest, W, up, foot: ((W @ rest[up].to_translation()) - (W @ rest[foot].to_translation())).length
    if up_t in rest_t and foot_t in rest_t and up_s in rest_s and foot_s in rest_s:
        k = leg_len(rest_t, Wt, up_t, foot_t) / max(1e-5, leg_len(rest_s, Ws0, up_s, foot_s))
    else:
        k = 1.0

    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
        pb.location = Vector((0.0, 0.0, 0.0))
        pb.scale = Vector((1.0, 1.0, 1.0))

    translated_names = {prefix_t + "root", prefix_t + "hip", "root", "hip"}

    for i, f in enumerate(target_frames):
        if source_frames is not None:
            src_f = source_frames[min(i, len(source_frames) - 1)]
        else:
            src_f = src["frames"][min(i, len(src["frames"]) - 1)]
        Ws = src["worlds"][src_f]
        conv = Rt_inv @ Ws.to_3x3().normalized()
        conv_inv = conv.inverted()
        pose_t = {}
        for b in order:
            n, rest_b, par = b.name, rest_t[b.name], b.parent
            inherit = (pose_t[par.name] @ rest_t[par.name].inverted() @ rest_b) if par else rest_b.copy()
            s = mapping.get(n)
            if s is None:
                m = inherit
            else:
                ps, rs = src["poses"][src_f][s], rest_s[s]
                delta = conv @ ps.to_3x3().normalized() @ rs.to_3x3().inverted() @ conv_inv
                m = (delta @ rest_b.to_3x3()).to_4x4()
                if n in translated_names:
                    d = (Ws @ ps.to_translation()) - (Ws0 @ rs.to_translation())
                    m.translation = Wt_inv @ ((Wt @ rest_b.to_translation()) + k * d)
                else:
                    m.translation = inherit.to_translation()
            pose_t[n] = m
            basis = (rest_b.inverted() @ rest_t[par.name] @ pose_t[par.name].inverted() @ m) if par else (rest_b.inverted() @ m)
            pb = arm.pose.bones[n]
            pb.rotation_quaternion = basis.to_quaternion()
            pb.keyframe_insert("rotation_quaternion", frame=f)
            if n in translated_names:
                pb.location = basis.to_translation()
                pb.keyframe_insert("location", frame=f)


def reset_rig_to_baseline(arm, baseline: dict = None):
    """Clear imported native animation for interior poses and reset all pose bones to natural baseline."""
    if arm.animation_data:
        arm.animation_data_clear()
    for b in arm.data.bones:
        b.use_inherit_rotation = True
        b.inherit_scale = "FULL"
        b.use_local_location = True
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
        if baseline and pb.name in baseline:
            pb.rotation_quaternion = baseline[pb.name].copy()
        else:
            pb.rotation_quaternion = Quaternion((1.0, 0.0, 0.0, 0.0))
        pb.rotation_euler = Euler((0.0, 0.0, 0.0))
        pb.location = Vector((0.0, 0.0, 0.0))
        pb.scale = Vector((1.0, 1.0, 1.0))
    bpy.context.view_layer.update()


def reset_rig_to_rest(arm):
    """Backward-compatible reset to rest."""
    reset_rig_to_baseline(arm, None)


ANATOMICAL_SEGMENT_CHILD = {
    "spine_01": "spine_02",
    "spine_02": "spine_03",
    "spine_03": "neck",
    "neck": "head",
    "upperleg_l": "lowerleg_l",
    "upperleg_r": "lowerleg_r",
    "lowerleg_l": "foot_l",
    "lowerleg_r": "foot_r",
    "foot_l": "ball_l",
    "foot_r": "ball_r",
    "upperarm_l": "lowerarm_l",
    "upperarm_r": "lowerarm_r",
    "lowerarm_l": "hand_l",
    "lowerarm_r": "hand_r",
    "hand_l": "middle_01_l",
    "hand_r": "middle_01_r",
}


def get_base_bone_name(name: str) -> str:
    """Normalize prefixed or flat bone name to canonical short name."""
    for short in [
        "spine_01", "spine_02", "spine_03", "neck", "head",
        "upperleg_l", "upperleg_r", "lowerleg_l", "lowerleg_r", "foot_l", "foot_r", "ball_l", "ball_r",
        "upperarm_l", "upperarm_r", "lowerarm_l", "lowerarm_r", "hand_l", "hand_r",
        "middle_01_l", "middle_01_r", "index_01_l", "index_01_r"
    ]:
        if name == short or name.endswith(f"_{short}"):
            return short
    return name


def get_anatomical_rest_vector(arm, pb) -> Vector:
    """Derive the rest anatomical segment vector in armature space (Z-up human skeleton).
    
    Uses physical joint-to-joint connections (child.head_local - bone.head_local)
    rather than artificial/synthetic bone.tail directions in FBX data.
    """
    b = arm.data.bones[pb.name]
    base = get_base_bone_name(b.name)
    
    if base == "head":
        neck_pb = get_bone(arm, "neck")
        if neck_pb:
            neck_b = arm.data.bones[neck_pb.name]
            return (b.head_local - neck_b.head_local).normalized()
        raise ValueError("Cannot derive anatomical axis for head: neck bone not found")
        
    child_base = ANATOMICAL_SEGMENT_CHILD.get(base)
    if child_base:
        child_pb = get_bone(arm, child_base)
        if child_pb:
            child_b = arm.data.bones[child_pb.name]
            vec = child_b.head_local - b.head_local
            if vec.length > 1e-5:
                return vec.normalized()
        # Fallback for hand if middle_01 is missing: index_01 or continuation of forearm vector
        if base in ("hand_l", "hand_r"):
            side = "l" if "l" in base else "r"
            idx_pb = get_bone(arm, f"index_01_{side}")
            if idx_pb:
                idx_b = arm.data.bones[idx_pb.name]
                vec = idx_b.head_local - b.head_local
                if vec.length > 1e-5:
                    return vec.normalized()
            lower_pb = get_bone(arm, f"lowerarm_{side}")
            if lower_pb:
                lower_b = arm.data.bones[lower_pb.name]
                return (b.head_local - lower_b.head_local).normalized()
                
    raise ValueError(f"No anatomical child or axis defined for bone '{pb.name}' (base '{base}')")


def set_bone_direction_world(arm, bone_name: str, target_dir_world: Vector, frame: int = None, twist_rad: float = 0.0):
    """Align an anatomical joint segment toward target_dir_world in WORLD coordinates (Z-up).
    
    Converts target_dir_world using current arm.matrix_world.to_3x3().inverted(),
    determines the rotation difference from the anatomical rest segment:
      v_rest_arm = (child.head_local - bone.head_local).normalized()
    and solves the pose matrix with correct current parent basis:
      M_target = q_rot @ b.matrix_local
      basis = rest_b^-1 @ rest_par @ pose_par^-1 @ M_target
    Updates view layer after setting each bone to ensure children read exact parent state.
    Asserts transformed anatomical rest segment dot target > 0.995 for every solved bone.
    """
    pb = get_bone(arm, bone_name)
    if pb is None:
        return
    b = arm.data.bones[pb.name]
    b.use_inherit_rotation = True
    b.inherit_scale = "FULL"
    b.use_local_location = True
    par = b.parent
    base = get_base_bone_name(b.name)
    
    # Anatomical rest segment connecting joint to child joint in armature space
    v_rest_arm = get_anatomical_rest_vector(arm, pb)

    # Foot pitch correction: preserve scanned ankle-to-ball downward slope in world coordinates
    if base in ("foot_l", "foot_r"):
        v_rest_world = arm.matrix_world.to_3x3() @ v_rest_arm
        h_rest = math.sqrt(v_rest_world.x ** 2 + v_rest_world.y ** 2)
        if h_rest > 1e-5:
            slope = v_rest_world.z / h_rest  # negative ratio z / horizontal_length
            h_target = math.sqrt(target_dir_world.x ** 2 + target_dir_world.y ** 2)
            if h_target > 1e-5:
                u_xy = Vector((target_dir_world.x / h_target, target_dir_world.y / h_target, 0.0))
                target_dir_world = Vector((u_xy.x, u_xy.y, slope)).normalized()

    v_world = target_dir_world.normalized()
    R_arm_inv = arm.matrix_world.to_3x3().inverted()
    v_arm = (R_arm_inv @ v_world).normalized()
    
    q_rot = v_rest_arm.rotation_difference(v_arm)
    if abs(twist_rad) > 1e-5:
        q_twist = Quaternion(v_arm, twist_rad)
        q_rot = q_twist @ q_rot

    M_target = q_rot.to_matrix().to_4x4() @ b.matrix_local
    
    if par:
        rest_par = par.matrix_local
        pose_par = arm.pose.bones[par.name].matrix
        basis = b.matrix_local.inverted() @ rest_par @ pose_par.inverted() @ M_target
    else:
        basis = b.matrix_local.inverted() @ M_target
        
    pb.rotation_mode = "QUATERNION"
    pb.rotation_quaternion = basis.to_quaternion()
    if frame is not None:
        pb.keyframe_insert("rotation_quaternion", frame=frame)
    bpy.context.view_layer.update()

    # Validation: measure transformed ANATOMICAL REST SEGMENT transformed to world
    seg_posed_arm = pb.matrix.to_3x3() @ b.matrix_local.to_3x3().inverted() @ v_rest_arm
    v_actual_world = (arm.matrix_world.to_3x3() @ seg_posed_arm).normalized()
    dot_val = float(v_actual_world.dot(v_world))
    if dot_val < 0.995:
        raise AssertionError(
            f"Bone '{pb.name}' anatomical alignment failed: dot={dot_val:.4f} < 0.995 "
            f"(target={list(v_world)}, actual={list(v_actual_world)})"
        )


def ground_rig_to_floor(rig, meshes, frame_count: int):
    """Offset rig.location.z so the actual evaluated lowest vertex is grounded at world Z = 0.0.
    
    Captures ALL original rig locations across frames FIRST without editing,
    computes global_min_z across all evaluated mesh vertices,
    then assigns captured location + Vector((0, 0, -global_min_z)) exactly ONCE per frame.
    Asserts resulting z-offset is constant for all frames with no incremental accumulation drift.
    """
    scene = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    
    orig_locations = {}
    min_zs = []
    
    # Pass 1: Capture all original rig locations and find global min vertex z without editing
    for f in range(1, frame_count + 1):
        scene.frame_set(f)
        bpy.context.view_layer.update()
        orig_locations[f] = rig.location.copy()
        for obj in meshes:
            ev = obj.evaluated_get(dg)
            me = ev.to_mesh()
            arr = np.empty(len(me.vertices) * 3)
            me.vertices.foreach_get("co", arr)
            mw = np.array(ev.matrix_world)
            wpts = arr.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3]
            min_zs.append(float(wpts[:, 2].min()))
            ev.to_mesh_clear()
            
    global_min_z = min(min_zs)
    z_offset = -global_min_z
    
    # Pass 2: Assign captured location + Vector(0, 0, -global_min_z) exactly ONCE per frame
    for f in range(1, frame_count + 1):
        scene.frame_set(f)
        rig.location = orig_locations[f] + Vector((0.0, 0.0, z_offset))
        rig.keyframe_insert("location", frame=f)
    bpy.context.view_layer.update()

    # Pass 3: Assert resulting z-offset is constant for all frames; figure grounded throughout, no drift
    for f in range(1, frame_count + 1):
        scene.frame_set(f)
        expected_z = orig_locations[f].z + z_offset
        actual_z = rig.location.z
        if abs(actual_z - expected_z) > 1e-4:
            raise AssertionError(
                f"Frame {f} rig z-offset drift: expected {expected_z:.6f}, got {actual_z:.6f}"
            )


def apply_seated_pose(arm, rig, meshes, person: str, frame_count: int, turn_dir: int, baseline: dict = None):
    """Set up realistic seated posture: hips at chair height, thighs horizontal, calves down, lap/chat, grounded."""
    scene = bpy.context.scene
    reset_rig_to_baseline(arm, baseline)
    hip = find_hip(arm)
    hip.location = Vector((0.0, 0.0, 0.0))

    solved_bones = {
        "spine_01", "spine_02", "spine_03", "neck", "head",
        "upperleg_l", "upperleg_r", "lowerleg_l", "lowerleg_r",
        "foot_l", "foot_r",
        "upperarm_l", "upperarm_r", "lowerarm_l", "lowerarm_r",
        "hand_l", "hand_r",
    }
    
    # In world coordinates: Z-up, facing camera along -Y
    for f in range(1, frame_count + 1):
        scene.frame_set(f)
        bpy.context.view_layer.update()
        p = (f - 1) / max(1, frame_count - 1)
        breath = math.sin(p * math.pi * 2.0) * 0.012
        chat = math.sin(p * math.pi) * 0.03
        nod = math.sin(p * math.pi * 2.0) * 0.02
        
        hip.keyframe_insert("location", frame=f)
        
        # 1. Torso gently leaning forward (world -Y) - Parent-first ordering
        set_bone_direction_world(arm, "spine_01", Vector((0.0, -0.06, 0.998 + breath)), frame=f)
        set_bone_direction_world(arm, "spine_02", Vector((0.0, -0.06, 0.998 + breath * 0.5)), frame=f)
        set_bone_direction_world(arm, "spine_03", Vector((0.0, -0.05, 0.999)), frame=f)
        set_bone_direction_world(arm, "neck", Vector((0.0, -0.04, 0.999)), frame=f)
        
        # Head upright with listening nod, turned via yaw around body up (NO sideways neck kink)
        head_yaw = turn_dir * (0.32 + chat * 0.4)
        set_bone_direction_world(arm, "head", Vector((0.0, -0.06 - nod, 0.998)), frame=f, twist_rad=head_yaw)
        
        # 2. Thighs horizontal forward (world -Y): Carla knees close, Nathan slightly wider
        if turn_dir >= 0:  # Carla (or right-facing): knees relatively close
            set_bone_direction_world(arm, "upperleg_l", Vector((0.05, -0.995, 0.04)), frame=f)
            set_bone_direction_world(arm, "upperleg_r", Vector((-0.07, -0.995, 0.04)), frame=f)
            set_bone_direction_world(arm, "lowerleg_l", Vector((0.02, -0.06, -0.998)), frame=f)
            set_bone_direction_world(arm, "lowerleg_r", Vector((-0.03, 0.02, -0.999)), frame=f)
            set_bone_direction_world(arm, "foot_l", Vector((0.02, -0.998, 0.0)), frame=f)
            set_bone_direction_world(arm, "foot_r", Vector((-0.02, -0.998, 0.0)), frame=f)
        else:              # Nathan (left-facing): slightly wider natural stance
            set_bone_direction_world(arm, "upperleg_l", Vector((0.10, -0.99, 0.05)), frame=f)
            set_bone_direction_world(arm, "upperleg_r", Vector((-0.09, -0.99, 0.04)), frame=f)
            set_bone_direction_world(arm, "lowerleg_l", Vector((0.04, 0.02, -0.999)), frame=f)
            set_bone_direction_world(arm, "lowerleg_r", Vector((-0.03, -0.06, -0.998)), frame=f)
            set_bone_direction_world(arm, "foot_l", Vector((0.03, -0.998, 0.0)), frame=f)
            set_bone_direction_world(arm, "foot_r", Vector((-0.02, -0.998, 0.0)), frame=f)
        
        # 3. Arms & Hands: upperarms close to ribs, forearms reach forward nearly horizontal on lap/thighs
        # Hands parallel to thighs with modest downward tilt, palm toward thigh, fingers keep native curl
        if turn_dir >= 0:
            # Carla: left arm resting comfortably on lap; right arm gestures quietly toward partner in middle frames
            set_bone_direction_world(arm, "upperarm_l", Vector((-0.06, -0.16, -0.985)), frame=f)
            set_bone_direction_world(arm, "lowerarm_l", Vector((-0.14, -0.985, -0.07)), frame=f)
            set_bone_direction_world(arm, "hand_l", Vector((-0.08, -0.975, -0.20)), frame=f)
            
            set_bone_direction_world(arm, "upperarm_r", Vector((0.06, -0.18, -0.98)), frame=f)
            set_bone_direction_world(arm, "lowerarm_r", Vector((0.14, -0.985, -0.07 + chat * 1.5)), frame=f)
            set_bone_direction_world(arm, "hand_r", Vector((0.08, -0.975, -0.20 + chat * 2.0)), frame=f)
        else:
            # Nathan: right arm resting comfortably on lap; left arm gestures quietly toward partner in middle frames
            set_bone_direction_world(arm, "upperarm_r", Vector((0.06, -0.16, -0.985)), frame=f)
            set_bone_direction_world(arm, "lowerarm_r", Vector((0.12, -0.965, -0.25)), frame=f)
            set_bone_direction_world(arm, "hand_r", Vector((0.08, -0.975, -0.20)), frame=f)
            
            set_bone_direction_world(arm, "upperarm_l", Vector((-0.06, -0.18, -0.98)), frame=f)
            set_bone_direction_world(arm, "lowerarm_l", Vector((-0.12, -0.965, -0.25 + chat * 1.5)), frame=f)
            set_bone_direction_world(arm, "hand_l", Vector((-0.08, -0.975, -0.20 + chat * 2.0)), frame=f)
            
        # Keyframe all untouched bones (fingers, thumbs, clavicles/shoulders) using captured native baseline
        if baseline:
            for pb in arm.pose.bones:
                base_name = get_base_bone_name(pb.name)
                if pb.name in baseline and base_name not in solved_bones:
                    pb.rotation_quaternion = baseline[pb.name]
                    pb.keyframe_insert("rotation_quaternion", frame=f)

    # Physically ground figure with actual vertex minz
    ground_rig_to_floor(rig, meshes, frame_count)


def apply_standing_pose(arm, rig, meshes, person: str, frame_count: int, stance: str, baseline: dict = None):
    """Natural upright standing pose in world coordinates with relaxed arms at sides (NO T-POSE) and grounded feet."""
    scene = bpy.context.scene
    reset_rig_to_baseline(arm, baseline)
    hip = find_hip(arm)
    hip.location = Vector((0.0, 0.0, 0.0))

    solved_bones = {
        "spine_01", "spine_02", "spine_03", "neck", "head",
        "upperleg_l", "upperleg_r", "lowerleg_l", "lowerleg_r",
        "foot_l", "foot_r",
        "upperarm_l", "upperarm_r", "lowerarm_l", "lowerarm_r"
    }
    
    for f in range(1, frame_count + 1):
        scene.frame_set(f)
        bpy.context.view_layer.update()
        p = (f - 1) / max(1, frame_count - 1)
        breath = math.sin(p * math.pi * 2.0) * 0.012
        glance = math.sin(p * math.pi) * 0.02
        nod = math.sin(p * math.pi * 2.0) * 0.015
        
        hip.keyframe_insert("location", frame=f)
        
        # Upright spine in world +Z - Parent-first ordering
        set_bone_direction_world(arm, "spine_01", Vector((0.0, -0.02, 0.999 + breath)), frame=f)
        set_bone_direction_world(arm, "spine_02", Vector((0.0, -0.01, 1.0 + breath * 0.6)), frame=f)
        set_bone_direction_world(arm, "spine_03", Vector((0.0, 0.0, 1.0)), frame=f)
        set_bone_direction_world(arm, "neck", Vector((0.0, 0.0, 1.0)), frame=f)
        
        # Asymmetric stance with one relaxed knee and arms softly bent (person-specific weight distribution)
        if stance in ("standing_idle", "standing_counter"):
            # Nathan: supporting right leg, relaxed left knee
            set_bone_direction_world(arm, "upperleg_r", Vector((-0.05, 0.01, -0.998)), frame=f)
            set_bone_direction_world(arm, "lowerleg_r", Vector((-0.02, 0.0, -0.999)), frame=f)
            set_bone_direction_world(arm, "foot_r", Vector((-0.02, -0.998, 0.0)), frame=f)
            set_bone_direction_world(arm, "upperleg_l", Vector((0.07, -0.05, -0.996)), frame=f)
            set_bone_direction_world(arm, "lowerleg_l", Vector((0.03, 0.03, -0.999)), frame=f)
            set_bone_direction_world(arm, "foot_l", Vector((0.03, -0.998, 0.0)), frame=f)
        elif stance == "standing_terrace":
            # Carla terrace: supporting left leg, relaxed right knee
            set_bone_direction_world(arm, "upperleg_l", Vector((0.05, 0.01, -0.998)), frame=f)
            set_bone_direction_world(arm, "lowerleg_l", Vector((0.02, 0.0, -0.999)), frame=f)
            set_bone_direction_world(arm, "foot_l", Vector((0.02, -0.998, 0.0)), frame=f)
            set_bone_direction_world(arm, "upperleg_r", Vector((-0.07, -0.05, -0.996)), frame=f)
            set_bone_direction_world(arm, "lowerleg_r", Vector((-0.03, 0.03, -0.999)), frame=f)
            set_bone_direction_world(arm, "foot_r", Vector((-0.03, -0.998, 0.0)), frame=f)
        else:
            # Carla vanity: symmetric balanced stance facing basin
            set_bone_direction_world(arm, "upperleg_l", Vector((0.04, 0.0, -0.999)), frame=f)
            set_bone_direction_world(arm, "upperleg_r", Vector((-0.04, 0.0, -0.999)), frame=f)
            set_bone_direction_world(arm, "lowerleg_l", Vector((0.02, 0.0, -0.999)), frame=f)
            set_bone_direction_world(arm, "lowerleg_r", Vector((-0.02, 0.0, -0.999)), frame=f)
            set_bone_direction_world(arm, "foot_l", Vector((0.0, -0.998, 0.0)), frame=f)
            set_bone_direction_world(arm, "foot_r", Vector((0.0, -0.998, 0.0)), frame=f)
        
        if stance == "standing_idle":
            # Natural arms relaxed softly down at sides, hands preserve mocap curl
            set_bone_direction_world(arm, "upperarm_l", Vector((0.11, -0.05, -0.99)), frame=f)
            set_bone_direction_world(arm, "upperarm_r", Vector((-0.11, -0.05, -0.99)), frame=f)
            set_bone_direction_world(arm, "lowerarm_l", Vector((0.06, -0.16, -0.98)), frame=f)
            set_bone_direction_world(arm, "lowerarm_r", Vector((-0.06, -0.16, -0.98)), frame=f)
            set_bone_direction_world(arm, "head", Vector((0.0, -0.04 - nod, 0.999)), frame=f, twist_rad=glance * 0.15)
            
        elif stance == "standing_terrace":
            # Looking out toward horizon and canopy, left arm relaxed, right arm softly bent near hip
            set_bone_direction_world(arm, "upperarm_l", Vector((0.11, -0.05, -0.99)), frame=f)
            set_bone_direction_world(arm, "lowerarm_l", Vector((0.06, -0.16, -0.98)), frame=f)
            set_bone_direction_world(arm, "upperarm_r", Vector((-0.15, -0.12, -0.97)), frame=f)
            set_bone_direction_world(arm, "lowerarm_r", Vector((-0.10, -0.32, -0.93)), frame=f)
            set_bone_direction_world(arm, "head", Vector((0.0, -0.04 - nod, 0.999)), frame=f, twist_rad=0.28 + glance * 0.1)
            
        elif stance == "standing_vanity":
            # Bathroom vanity: back/three-quarters view, hands near vanity basin looking into mirror
            set_bone_direction_world(arm, "upperarm_l", Vector((0.14, -0.18, -0.97)), frame=f)
            set_bone_direction_world(arm, "upperarm_r", Vector((-0.14, -0.18, -0.97)), frame=f)
            set_bone_direction_world(arm, "lowerarm_l", Vector((0.08, -0.50, -0.85 + glance * 0.1)), frame=f)
            set_bone_direction_world(arm, "lowerarm_r", Vector((-0.08, -0.50, -0.85 - glance * 0.1)), frame=f)
            set_bone_direction_world(arm, "head", Vector((0.0, -0.08 + nod, 0.995)), frame=f, twist_rad=0.0)
            
        elif stance == "standing_counter":
            # Hospitality counter: person is in aisle, hand relaxed near waist/side (NOT held aloft in midair)
            set_bone_direction_world(arm, "upperarm_l", Vector((0.11, -0.05, -0.99)), frame=f)
            set_bone_direction_world(arm, "lowerarm_l", Vector((0.06, -0.16, -0.98)), frame=f)
            set_bone_direction_world(arm, "upperarm_r", Vector((-0.13, -0.08, -0.98)), frame=f)
            set_bone_direction_world(arm, "lowerarm_r", Vector((-0.08, -0.24, -0.96)), frame=f)
            set_bone_direction_world(arm, "head", Vector((0.0, -0.04 - nod, 0.999)), frame=f, twist_rad=0.14 + glance * 0.1)

        # Keyframe all untouched bones (fingers, thumbs, wrists, shoulders) using captured native baseline
        if baseline:
            for pb in arm.pose.bones:
                base_name = get_base_bone_name(pb.name)
                if pb.name in baseline and base_name not in solved_bones:
                    pb.rotation_quaternion = baseline[pb.name]
                    pb.keyframe_insert("rotation_quaternion", frame=f)

    # Physically ground figure with actual vertex minz
    ground_rig_to_floor(rig, meshes, frame_count)


def apply_hero_motion(arm, rig, meshes, person: str, frame_count: int, turn_dir: int, baseline: dict = None):
    """64-frame Hero sequence:
    1..32: Walk in place (offsets gathered with zero translation to eliminate drift; heading matches manifest travel).
    33..42: Smoothly blend walk stride to genuinely relaxed upright standing pose (NO T-POSE arms).
    Turn toward partner (re-centering rotated hip at origin each frame to eliminate orbital drift).
    Nathan faces screen-left/down toward Carla; Carla faces screen-right/up toward Nathan.
    43..64: Conversational gestures (nodding, breathing, subtle hand gestures toward partner).
    """
    hip = find_hip(arm)
    scene = bpy.context.scene
    
    # Camera basis setup
    CAM_FROM, CAM_AT = Vector((6.0, -8.0, 6.8)), Vector((0.0, 0.0, 0.9))
    look = CAM_AT - CAM_FROM
    rot = look.to_track_quat("-Z", "Y").to_matrix()
    right, up = rot.col[0].copy(), rot.col[1].copy()
    look_dir = look.normalized()

    def screen_to_ground_dir(dx: float, dy: float) -> Vector:
        """Derive ground plane direction (Z=0) from screen displacement (dx right, dy down) via camera basis."""
        v = dx * right - dy * up
        v_ground = v - look_dir * (v.z / look_dir.z)
        return Vector((v_ground.x, v_ground.y, 0.0)).normalized()

    # 1. Travel direction matching actual manifest travel:
    # Nathan: dx = 245, dy = 65; Carla: dx = 200, dy = 55
    if person == "Nathan":
        walk_dir = screen_to_ground_dir(245.0, 65.0)
    else:
        walk_dir = screen_to_ground_dir(200.0, 55.0)

    # 2. Facing direction toward partner:
    # Pair positions: Nathan end [1280, 725], Carla end [1220, 745]
    # Nathan -> Carla: dx = 1220 - 1280 = -60 (screen-left), dy = 745 - 725 = +20 (screen-down)
    # Carla -> Nathan: dx = 1280 - 1220 = +60 (screen-right), dy = 725 - 745 = -20 (screen-up)
    if person == "Nathan":
        partner_dir = screen_to_ground_dir(-60.0, 20.0)
    else:
        partner_dir = screen_to_ground_dir(60.0, -20.0)

    # Measure natural walk travel vector of the rig
    if rig.animation_data:
        rig.animation_data_clear()
    rig.location = Vector((0.0, 0.0, 0.0))
    rig.rotation_euler = Euler((0.0, 0.0, 0.0))
    bpy.context.view_layer.update()

    def get_hip_world_xy(f: int) -> Vector:
        scene.frame_set(f)
        p = arm.matrix_world @ hip.head
        return Vector((p.x, p.y))

    move = get_hip_world_xy(32) - get_hip_world_xy(1)
    if move.length > 0.01:
        base_angle = math.atan2(move.y, move.x)
        walk_rot_z = math.atan2(walk_dir.y, walk_dir.x) - base_angle
        partner_rot_z = math.atan2(partner_dir.y, partner_dir.x) - base_angle
    else:
        walk_rot_z = 0.0
        partner_rot_z = 0.0

    # Shortest angular difference between walk heading and partner heading
    angle_diff = (partner_rot_z - walk_rot_z + math.pi) % (2.0 * math.pi) - math.pi

    # Gather walk offsets with rig translation zero BEFORE keying them (build_people.py pattern)
    rig.rotation_euler = (0.0, 0.0, walk_rot_z)
    rig.location = (0.0, 0.0, 0.0)
    bpy.context.view_layer.update()

    walk_offsets = {}
    for f in range(1, 33):
        scene.frame_set(f)
        p = arm.matrix_world @ hip.head
        walk_offsets[f] = Vector((-p.x, -p.y))

    # Keyframe walk in place frames 1..32
    for f in range(1, 33):
        scene.frame_set(f)
        o = walk_offsets[f]
        rig.location = (o.x, o.y, 0.0)
        rig.keyframe_insert("location", frame=f)
        rig.rotation_euler = (0.0, 0.0, walk_rot_z)
        rig.keyframe_insert("rotation_euler", frame=f)

    # Capture walk frame 32 poses
    scene.frame_set(32)
    bpy.context.view_layer.update()
    walk_end_rot = {pb.name: pb.rotation_quaternion.copy() for pb in arm.pose.bones if pb.rotation_mode == "QUATERNION"}

    # Solve genuinely relaxed upright standing pose in neutral character orientation (arms at sides, NOT T-pose)
    rig.location = (0.0, 0.0, 0.0)
    rig.rotation_euler = (0.0, 0.0, 0.0)
    bpy.context.view_layer.update()
    
    relaxed_pose = {}
    if baseline:
        # Pre-populate with baseline fingers/thumbs/wrists/shoulders so relaxed standing inherits mocap curl
        relaxed_pose.update(baseline)
    
    # Spine upright (parent-first)
    for sp_b, vec in [("spine_01", Vector((0.0, 0.0, 1.0))),
                      ("spine_02", Vector((0.0, 0.0, 1.0))),
                      ("spine_03", Vector((0.0, 0.0, 1.0))),
                      ("neck", Vector((0.0, 0.0, 1.0))),
                      ("head", Vector((0.0, -0.04, 0.999)))]:
        pb = get_bone(arm, sp_b)
        if pb:
            set_bone_direction_world(arm, pb.name, vec)
            relaxed_pose[pb.name] = pb.rotation_quaternion.copy()

    # Legs in relaxed asymmetric stance (parent-first)
    if person == "Nathan":
        # Supporting right leg, relaxed left knee
        leg_configs = [
            ("upperleg_r", Vector((-0.05, 0.01, -0.998))),
            ("lowerleg_r", Vector((-0.02, 0.0, -0.999))),
            ("foot_r", Vector((-0.02, -0.998, 0.0))),
            ("upperleg_l", Vector((0.07, -0.05, -0.996))),
            ("lowerleg_l", Vector((0.03, 0.03, -0.999))),
            ("foot_l", Vector((0.03, -0.998, 0.0)))
        ]
    else:
        # Carla: supporting left leg, relaxed right knee
        leg_configs = [
            ("upperleg_l", Vector((0.05, 0.01, -0.998))),
            ("lowerleg_l", Vector((0.02, 0.0, -0.999))),
            ("foot_l", Vector((0.02, -0.998, 0.0))),
            ("upperleg_r", Vector((-0.07, -0.05, -0.996))),
            ("lowerleg_r", Vector((-0.03, 0.03, -0.999))),
            ("foot_r", Vector((-0.03, -0.998, 0.0)))
        ]
    for leg_b, vec in leg_configs:
        pb = get_bone(arm, leg_b)
        if pb:
            set_bone_direction_world(arm, pb.name, vec)
            relaxed_pose[pb.name] = pb.rotation_quaternion.copy()

    # Arms relaxed naturally down at sides, softly bent (NOT T-pose or rigid straight sticks)
    for arm_b, vec in [("upperarm_l", Vector((0.11, -0.05, -0.99))),
                       ("upperarm_r", Vector((-0.11, -0.05, -0.99))),
                       ("lowerarm_l", Vector((0.06, -0.16, -0.98))),
                       ("lowerarm_r", Vector((-0.06, -0.16, -0.98)))]:
        pb = get_bone(arm, arm_b)
        if pb:
            set_bone_direction_world(arm, pb.name, vec)
            relaxed_pose[pb.name] = pb.rotation_quaternion.copy()

    # Second half: frames 33..64
    for f in range(33, frame_count + 1):
        scene.frame_set(f)
        bpy.context.view_layer.update()
        if f <= 42:
            # Smoothstep blend 32..42: transition walk stride into relaxed standing pose
            t = (f - 32) / 10.0
            s = 3.0 * t * t - 2.0 * t * t * t
            curr_rot_z = walk_rot_z + angle_diff * s
            
            for pb_name, target_q in relaxed_pose.items():
                pb = arm.pose.bones.get(pb_name)
                if pb:
                    if pb_name in walk_end_rot:
                        pb.rotation_quaternion = walk_end_rot[pb_name].slerp(target_q, s)
                    else:
                        pb.rotation_quaternion = target_q
                    pb.keyframe_insert("rotation_quaternion", frame=f)
            for pb_name, start_q in walk_end_rot.items():
                if pb_name not in relaxed_pose:
                    pb = arm.pose.bones.get(pb_name)
                    if pb:
                        pb.rotation_quaternion = start_q
                        pb.keyframe_insert("rotation_quaternion", frame=f)
        else:
            # Frames 43..64: Quiet conversation with subtle breathing, head nods, and hand gestures
            curr_rot_z = walk_rot_z + angle_diff
            p_chat = (f - 42) / 22.0
            chat_window = math.sin(p_chat * math.pi)
            breath = math.sin(p_chat * math.pi * 3.0) * 0.012
            nod = math.sin(p_chat * math.pi * 3.0) * 0.02 * chat_window

            # Keep relaxed base for all un-gesturing bones (including fingers/wrists/shoulders)
            for pb_name, target_q in relaxed_pose.items():
                pb = arm.pose.bones.get(pb_name)
                if pb:
                    pb.rotation_quaternion = target_q
                    pb.keyframe_insert("rotation_quaternion", frame=f)

            # Breathing on spine
            spine = get_bone(arm, "spine_01")
            if spine and spine.name in relaxed_pose:
                spine.rotation_quaternion = relaxed_pose[spine.name] @ Quaternion((1.0, breath * 0.5, 0.0, 0.0)).normalized()
                spine.keyframe_insert("rotation_quaternion", frame=f)

            # Head nodding (subtle listening nod - pitch only, NO ear-to-shoulder sideways roll!)
            head = get_bone(arm, "head")
            if head and head.name in relaxed_pose:
                head.rotation_quaternion = relaxed_pose[head.name] @ Quaternion((1.0, nod, 0.0, 0.0)).normalized()
                head.keyframe_insert("rotation_quaternion", frame=f)

            # Conversational gesture arm: Nathan gestures with left hand; Carla with right hand
            side = "l" if person == "Nathan" else "r"
            sign = 1.0 if side == "l" else -1.0
            arm_u = get_bone(arm, f"upperarm_{side}")
            arm_l = get_bone(arm, f"lowerarm_{side}")
            if arm_u and arm_u.name in relaxed_pose:
                arm_u.rotation_quaternion = relaxed_pose[arm_u.name] @ Quaternion((1.0, -0.08 * chat_window, sign * 0.04 * chat_window, 0.0)).normalized()
                arm_u.keyframe_insert("rotation_quaternion", frame=f)
            if arm_l and arm_l.name in relaxed_pose:
                arm_l.rotation_quaternion = relaxed_pose[arm_l.name] @ Quaternion((1.0, -0.20 * chat_window, 0.0, 0.0)).normalized()
                arm_l.keyframe_insert("rotation_quaternion", frame=f)

        # RE-CENTER actual rotated hip at origin each frame to eliminate orbital turning drift
        rig.rotation_euler = (0.0, 0.0, curr_rot_z)
        rig.location = (0.0, 0.0, 0.0)
        bpy.context.view_layer.update()
        p = arm.matrix_world @ hip.head
        rig.location = (-p.x, -p.y, 0.0)
        rig.keyframe_insert("location", frame=f)
        rig.keyframe_insert("rotation_euler", frame=f)

    # Physically ground figure with actual vertex minz across all 64 frames
    ground_rig_to_floor(rig, meshes, frame_count)


def load_rgba(path: Path) -> np.ndarray:
    img = bpy.data.images.load(str(path))
    w, h = img.size
    arr = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(arr)
    bpy.data.images.remove(img)
    return arr.reshape(h, w, 4)[::-1]


def alpha_box(frame: np.ndarray) -> dict:
    mask = frame[:, :, 3] > 0.1
    if not mask.any():
        raise SystemExit("A rendered frame is empty: check camera clipping and lighting")
    rows, cols = np.where(mask.any(axis=1))[0], np.where(mask.any(axis=0))[0]
    return {
        "top": int(rows[0]), "bottom": int(rows[-1]),
        "left": int(cols[0]), "right": int(cols[-1])
    }


def assemble_strip(rendered_dir: Path, out_png: Path, frame_count: int, fw: int, fh: int) -> list[dict]:
    """Pack frame PNGs into one horizontal RGBA strip and return measured alpha bounds."""
    strip = np.zeros((fh, fw * frame_count, 4), dtype=np.float32)
    boxes = []
    for i in range(frame_count):
        frame = load_rgba(rendered_dir / f"frame_{i:02d}.png")
        if frame.shape != (fh, fw, 4):
            raise SystemExit(f"frame_{i:02d}.png is {frame.shape[1]}x{frame.shape[0]}, expected {fw}x{fh}")
        strip[:, i * fw:(i + 1) * fw] = frame
        boxes.append(alpha_box(frame))
    
    out_png.parent.mkdir(parents=True, exist_ok=True)
    out = bpy.data.images.new(out_png.stem, fw * frame_count, fh, alpha=True)
    out.alpha_mode = "STRAIGHT"
    out.pixels.foreach_set(np.ascontiguousarray(strip[::-1]).ravel())
    out.filepath_raw, out.file_format = str(out_png), "PNG"
    out.save()
    bpy.data.images.remove(out)
    return boxes


def render_profile(profile_name: str, cfg: dict, preview: bool, samples: int, resume: bool):
    """Build, pose, fit camera, and render one profile."""
    out_png = SCENES_DIR / f"{profile_name}.png"
    out_json = SCENES_DIR / f"{profile_name}.json"
    rendered_dir = RENDERED_BASE / profile_name
    rendered_dir.mkdir(parents=True, exist_ok=True)

    if resume and out_png.is_file() and out_json.is_file() and not preview:
        print(f"RESUME: {profile_name} already rendered and valid, skipping.")
        return

    print(f"\n--- Building Profile: {profile_name} ({cfg['person']}, {cfg['frame_count']} frames, {cfg['frame_w']}x{cfg['frame_h']}) ---")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene

    person = cfg["person"]
    frame_count = cfg["frame_count"]
    fw, fh = cfg["frame_w"], cfg["frame_h"]
    motion_kind = cfg["motion_kind"]

    walk_src = get_walk_src()

    # Import target figure
    if person == "Nathan":
        bpy.ops.import_scene.fbx(filepath=str(FBX_N), use_image_search=False, use_anim=True)
        textures = fix_nathan_textures()
        mute_nathan_materials()
    else:
        bpy.ops.import_scene.fbx(filepath=str(FBX_C), use_image_search=False, use_anim=False)
        meshes = [o for o in scene.objects if o.type == "MESH"]
        textures = carla_material(meshes)

    arm = next(o for o in scene.objects if o.type == "ARMATURE")
    meshes = [o for o in scene.objects if o.type == "MESH"]

    # Capture natural authored native walk pose (frame 16) as baseline for fingers, wrists, shoulders
    if person == "Nathan":
        scene.frame_set(16)
        bpy.context.view_layer.update()
        baseline = {
            pb.name: pb.rotation_quaternion.copy()
            if pb.rotation_mode == "QUATERNION"
            else pb.matrix_basis.to_quaternion()
            for pb in arm.pose.bones
        }
        if arm.animation_data and motion_kind != "hero_walk_turn":
            arm.animation_data_clear()
    else:
        # Retarget frame 16 of donor walk to Carla rig to get authentic mocap finger/wrist baseline
        apply_walk_to_rig(walk_src, arm, [16], source_frames=[16])
        scene.frame_set(16)
        bpy.context.view_layer.update()
        baseline = {
            pb.name: pb.rotation_quaternion.copy()
            for pb in arm.pose.bones
        }
        if arm.animation_data and motion_kind != "hero_walk_turn":
            arm.animation_data_clear()
    
    # Rig empty pivot
    rig = bpy.data.objects.new("people_rig", None)
    scene.collection.objects.link(rig)
    for obj in [o for o in scene.objects if o.parent is None and o is not rig]:
        obj.parent = rig

    # Apply animation / poses
    if motion_kind == "hero_walk_turn":
        # Freeze/replace action only AFTER source poses are saved; clear native action on Nathan
        if arm.animation_data:
            arm.animation_data_clear()
        new_act = bpy.data.actions.new(name=f"{profile_name}_action")
        arm.animation_data_create().action = new_act
        
        # Apply baked walk poses 10..41 to output frames 1..32 for both Nathan and Carla
        apply_walk_to_rig(walk_src, arm, list(range(1, 33)))
        apply_hero_motion(arm, rig, meshes, person, frame_count, cfg["turn_dir"], baseline)
    elif motion_kind == "seated_talk":
        new_act = bpy.data.actions.new(name=f"{profile_name}_action")
        arm.animation_data_create().action = new_act
        apply_seated_pose(arm, rig, meshes, person, frame_count, cfg["turn_dir"], baseline)
    else:
        new_act = bpy.data.actions.new(name=f"{profile_name}_action")
        arm.animation_data_create().action = new_act
        apply_standing_pose(arm, rig, meshes, person, frame_count, motion_kind, baseline)

    # Camera setup & fixed union fit across every frame
    CAM_FROM, CAM_AT = cfg["cam_from"], cfg["cam_at"]
    look = CAM_AT - CAM_FROM
    rot = look.to_track_quat("-Z", "Y").to_matrix()
    right, up = rot.col[0].copy(), rot.col[1].copy()
    elevation = math.atan2(-look.z, Vector((look.x, look.y)).length)
    R = np.array(rot)

    frames = list(range(1, frame_count + 1))
    cam_pts = []
    for f in frames:
        scene.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        pts = []
        for obj in meshes:
            ev = obj.evaluated_get(dg)
            me = ev.to_mesh()
            arr = np.empty(len(me.vertices) * 3)
            me.vertices.foreach_get("co", arr)
            mw = np.array(ev.matrix_world)
            pts.append(arr.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3])
            ev.to_mesh_clear()
        cam_pts.append((np.vstack(pts) - np.array(CAM_FROM)) @ R)
    
    allpts = np.vstack(cam_pts)
    xmin, ymin = allpts[:, :2].min(axis=0)
    xmax, ymax = allpts[:, :2].max(axis=0)
    w_m = float(xmax - xmin)
    h_m = float(ymax - ymin)

    # Dynamic union fit with safety padding: never clip head, feet, or sides
    if fh == 256:  # Hero (192x256)
        pad_top, pad_bottom, pad_side = 14.0, 14.0, 14.0
        target_foot_row = fh - pad_bottom  # 242.0
        avail_h = fh - pad_top - pad_bottom # 228.0
        avail_w = fw - 2.0 * pad_side       # 164.0
    else:          # Interiors (256x384)
        pad_top, pad_bottom, pad_side = 20.0, 20.0, 20.0
        target_foot_row = fh - pad_bottom  # 364.0
        avail_h = fh - pad_top - pad_bottom # 344.0
        avail_w = fw - 2.0 * pad_side       # 216.0

    ortho_h = h_m * fh / avail_h
    ortho_w = w_m * fh / avail_w
    # Never force hardcoded 1.9765: compute required fit and pad generously (2% margin)
    computed_ortho = float(max(ortho_h, ortho_w, 1.85) * 1.02)
    if cfg["lock_ortho"] > 0:
        ortho = float(max(cfg["lock_ortho"], computed_ortho))
    else:
        ortho = computed_ortho

    cx = float((xmin + xmax) / 2.0)
    dy = float(ymin + (target_foot_row - fh / 2.0) * ortho / fh)
    px_per_m = float(fh / ortho)

    cam_data = bpy.data.cameras.new(f"cam_{profile_name}")
    cam_data.type, cam_data.sensor_fit, cam_data.ortho_scale = "ORTHO", "VERTICAL", ortho
    cam_data.clip_start, cam_data.clip_end = 0.1, 100.0
    cam = bpy.data.objects.new(f"cam_{profile_name}", cam_data)
    scene.collection.objects.link(cam)
    cam.matrix_world = Matrix.Translation(CAM_FROM + right * cx + up * dy) @ rot.to_4x4()
    scene.camera = cam

    # Compute seat anchor if seated
    seat_anchor = None
    if cfg["is_seated"]:
        scene.frame_set(frame_count if cfg.get("final_seat") else 1)
        hip = find_hip(arm)
        hip_w = arm.matrix_world @ hip.head
        hip_c = (np.array(hip_w) - np.array(cam.location)) @ R
        seat_x = round(float(hip_c[0] * px_per_m + fw / 2.0), 1)
        seat_y = round(float(fh / 2.0 - hip_c[1] * px_per_m), 1)
        seat_anchor = [seat_x, seat_y]

    # Ground shadow anchor from the actual final planted ankles, projected onto Z=0.
    scene.frame_set(frame_count)
    feet=[arm.matrix_world @ get_bone(arm, "foot_"+side).head for side in ("l","r")]
    ground=(feet[0]+feet[1])*.5;ground.z=0
    gc=(np.array(ground)-np.array(cam.location)) @ R
    ground_anchor=[round(float(gc[0]*px_per_m+fw/2),1),round(float(fh/2-gc[1]*px_per_m),1)]

    # Lighting setup: warm soft key sun + neutral warm ambient
    sun = bpy.data.lights.new(f"sun_{profile_name}", "SUN")
    sun.energy, sun.color, sun.angle = 2.1, (1.0, 0.91, 0.80), math.radians(18)
    sun_obj = bpy.data.objects.new(f"sun_{profile_name}", sun)
    scene.collection.objects.link(sun_obj)
    fwd_vec = Vector((look.x, look.y, 0.0)).normalized()
    sun_obj.rotation_euler = (right * 0.6 + fwd_vec * 0.5 - Vector((0, 0, 1.2))).to_track_quat("-Z", "Y").to_euler()

    world = bpy.data.worlds.new(f"world_{profile_name}")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.92, 0.88, 0.82, 1.0)
    bg.inputs[1].default_value = 0.75
    scene.world = world

    # Render settings
    rnd = scene.render
    for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            rnd.engine = eng
            break
        except TypeError:
            continue
    rnd.resolution_x, rnd.resolution_y, rnd.resolution_percentage = fw, fh, 100
    rnd.film_transparent, rnd.filter_size = True, 1.5
    rnd.image_settings.file_format, rnd.image_settings.color_mode, rnd.image_settings.color_depth = "PNG", "RGBA", "8"
    rnd.image_settings.compression = 60
    scene.eevee.taa_render_samples = samples
    scene.view_settings.view_transform, scene.view_settings.look = "Standard", "None"

    # Enhanced preview mode: frames 1, 32, 48, 64 for hero; frames 1, 16, 32 for interiors
    if preview:
        if cfg.get("final_seat"):
            preview_frames = [1, 80, 104, 128, frame_count]
        elif frame_count == 64:
            preview_frames = [1, 32, 48, 64]
        else:
            preview_frames = [1, frame_count//2, frame_count]

        rendered_previews = {}
        for pf in preview_frames:
            scene.frame_set(pf)
            fpath = rendered_dir / f"preview_f{pf:02d}.png"
            rnd.filepath = str(fpath)
            bpy.ops.render.render(write_still=True)
            rendered_previews[str(pf)] = str(fpath)
            if pf == 1:
                # preview.png aliases frame 1
                p1_path = rendered_dir / "preview.png"
                rnd.filepath = str(p1_path)
                bpy.ops.render.render(write_still=True)

        if HAS_PIL:
            try:
                imgs = [Image.open(rendered_dir / f"preview_f{pf:02d}.png") for pf in preview_frames]
                tot_w = sum(im.width for im in imgs)
                max_h = max(im.height for im in imgs)
                comp = Image.new("RGBA", (tot_w, max_h), (0, 0, 0, 0))
                x_off = 0
                for im in imgs:
                    comp.paste(im, (x_off, 0))
                    x_off += im.width
                comp.save(rendered_dir / "preview_strip.png")
            except Exception as e:
                pass

        prev_meta = {
            "profile": profile_name,
            "preview_png": str(rendered_dir / "preview.png"),
            "preview_frames": preview_frames,
            "rendered_previews": rendered_previews,
            "ortho_scale": round(float(ortho), 4),
            "px_per_m": round(float(px_per_m), 2),
            "seat_anchor": seat_anchor,
            "camera_elevation": round(float(math.degrees(elevation)), 2)
        }
        (rendered_dir / "preview-info.json").write_text(json.dumps(prev_meta, indent=2) + "\n")
        print(f"PREVIEW OK: {profile_name} frames {preview_frames} -> {rendered_dir}")
        return

    # Render all frames
    for i, f in enumerate(frames):
        scene.frame_set(f)
        rnd.filepath = str(rendered_dir / f"frame_{i:02d}.png")
        bpy.ops.render.render(write_still=True)
        if (i + 1) % 8 == 0 or (i + 1) == len(frames):
            print(f"  Frame {i + 1}/{len(frames)} rendered.")

    # Assemble into strip
    boxes = assemble_strip(rendered_dir, out_png, frame_count, fw, fh)
    digest = hashlib.sha256(out_png.read_bytes()).hexdigest()
    
    body = {
        "top": int(min(b["top"] for b in boxes)),
        "bottom": int(max(b["bottom"] for b in boxes)),
        "left": int(min(b["left"] for b in boxes)),
        "right": int(max(b["right"] for b in boxes)),
    }
    vis_h = int(body["bottom"] - body["top"] + 1)
    foot_row = int(body["bottom"] + 1)

    meta = {
        "file": out_png.name,
        "person": person,
        "frame_count": int(frame_count),
        "frame_width": int(fw),
        "frame_height": int(fh),
        "strip_width": int(fw * frame_count),
        "strip_height": int(fh),
        "fps": 30.0,
        "clip_seconds": 4.4,
        "body": body,
        "visible_body_height": vis_h,
        "foot_anchor": foot_row,
        "ground_anchor": ground_anchor,
        "frames": boxes,
        "camera": {
            "from": [round(float(v), 3) for v in cam.location],
            "at": [round(float(v), 3) for v in CAM_AT],
            "ortho_scale": round(float(ortho), 4),
            "elevation_deg": round(float(math.degrees(elevation)), 2),
            "px_per_m": round(float(px_per_m), 2)
        },
        "renderer": f"Blender {bpy.app.version_string} {rnd.engine} {samples} samples, film transparent",
        "source": f"Renderpeople licensed model {person} rendered; raw 3D data private",
        "sha256": digest
    }
    if seat_anchor is not None:
        meta["seat_anchor"] = [float(seat_anchor[0]), float(seat_anchor[1])]

    out_json.write_text(json.dumps(meta, indent=2) + "\n")

    # Update provenance.json
    prov = json.loads(PROVENANCE_FILE.read_text()) if PROVENANCE_FILE.is_file() else {}
    prov.setdefault("outputs", {})[out_png.name] = {
        "sha256": digest,
        "width": int(fw * frame_count),
        "height": int(fh),
        "frame_count": int(frame_count),
        "frame_width": int(fw),
        "frame_height": int(fh),
        "metadata": out_json.name,
        "operation": f"Rendered in Blender {bpy.app.version_string} ({rnd.engine}, {samples} samples, RGBA); packed into one strip"
    }
    PROVENANCE_FILE.write_text(json.dumps(prov, indent=2) + "\n")
    print(f"STRIP BUILT: {out_png} ({vis_h}px visual height, sha256={digest[:16]}...)")


def main():
    args = parse_args()
    SCENES_DIR.mkdir(parents=True, exist_ok=True)
    RENDERED_BASE.mkdir(parents=True, exist_ok=True)

    if args["profile"]:
        if args["profile"] not in PROFILES:
            raise SystemExit(f"Unknown profile: {args['profile']}. Choices: {list(PROFILES.keys())}")
        targets = [args["profile"]]
    else:
        targets = list(PROFILES.keys())

    print(f"Wargame Scene People Builder: Blender {bpy.app.version_string}")
    print(f"Targets ({len(targets)}): {targets}")
    print(f"Options: preview={args['preview']}, resume={args['resume']}, samples={args['samples']}")

    for name in targets:
        render_profile(name, PROFILES[name], preview=args["preview"], samples=args["samples"], resume=args["resume"])

    print("\nAll selected scene people profiles completed successfully.")


if __name__ == "__main__":
    main()
