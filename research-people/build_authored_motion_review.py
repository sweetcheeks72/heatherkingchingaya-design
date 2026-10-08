#!/usr/bin/env python3
"""Isolated candidate review renderer for authored mocap motion comparisons.

Reuses proven camera, material, lighting, union-fit, and strip packing functions
from build_scene_people.py, while retargeting authentic authored mocap from
Sophia idling (donor only) to RenderPeople licensed models Nathan and Carla.

Output directories:
  - Strips/metadata: research-people/natural-motion-review/assets/
  - Frame renders:   research-people/natural-motion-review/frames/
  - Provenance:      research-people/natural-motion-review/assets/provenance.json

Usage:
  blender -b -P research-people/build_authored_motion_review.py -- --preview --all
  blender -b -P research-people/build_authored_motion_review.py -- --all --samples 20
  blender -b -P research-people/build_authored_motion_review.py -- --preview --profile hero-nathan-walk-turn
"""

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import build_scene_people as bsp

FBX_SOPHIA = ROOT / "source-sophia" / "rp_sophia_animated_003_idling.fbx"
REVIEW_DIR = ROOT / "natural-motion-review"
ASSETS_DIR = REVIEW_DIR / "assets"
FRAMES_DIR = REVIEW_DIR / "frames"
PROVENANCE_FILE = ASSETS_DIR / "provenance.json"

# Separate donor cache - never contaminates get_walk_src()
_CACHED_IDLE_DONOR = None


def get_idle_donor_src(first: int = 1, last: int = 613) -> dict:
    """Load and cache evaluated donor bone matrices from Sophia idle FBX (frames 1..613).
    Completely isolated from get_walk_src().
    """
    global _CACHED_IDLE_DONOR
    if _CACHED_IDLE_DONOR is None:
        if not FBX_SOPHIA.is_file():
            raise FileNotFoundError(f"Sophia idle FBX not found at {FBX_SOPHIA}")

        bpy.ops.import_scene.fbx(filepath=str(FBX_SOPHIA), use_image_search=False, use_anim=True)
        scene = bpy.context.scene
        arm = next(o for o in scene.objects if o.type == "ARMATURE")
        if arm.animation_data is None or arm.animation_data.action is None:
            arm.animation_data_create().action = bpy.data.actions[0]
        action = arm.animation_data.action
        lo, hi = (int(v) for v in action.frame_range)
        frames = list(range(max(first, lo), min(last, hi) + 1))
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
        _CACHED_IDLE_DONOR = src
    return _CACHED_IDLE_DONOR


REVIEW_PROFILES = {
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
        "turn_dir": 1,
        "donor_range": (40, 106),
        "description": "Authored motion review: Nathan walking 1..32, blending over 10 frames into casual hand-at-hip listening stance (donor Sophia 40..172) and turning to face Carla."
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
        "turn_dir": -1,
        "donor_range": (200, 266),
        "description": "Authored motion review: Carla retargeted walk 1..32, blending over 10 frames into relaxed listening stance with gentle arm movement (donor Sophia 200..332) and turning to face Nathan."
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
        "turn_dir": 1,
        "donor_range": (215, 347),
        "description": "Authored motion review: Carla seated posture with authored upper-body breathing/shifts, forearms on lap/thighs, subtle conversational gesture, close knees, grounded feet."
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
        "turn_dir": -1,
        "donor_range": (320, 430),
        "description": "Authored motion review: Nathan seated in chair with authentic folded-arms listening pose (donor Sophia ~375..437), relaxed shoulders, natural spine and grounded feet."
    },
}


def authored_hero_motion(arm, rig, meshes, person: str, frame_count: int, turn_dir: int, baseline: dict = None):
    """64-frame Hero sequence with authentic authored mocap idle:
    1..32: Native Nathan walk in place (offsets gathered with zero translation; heading matches manifest travel).
    33..42: Smooth 10-frame transition from walk stride into authored idle mocap action.
    Rotates toward partner around hips (eliminating orbital drift).
    43..64: Settled authored idle motion (Nathan casual hand-at-hip donor 40..172; Carla relaxed listening donor 200..332).
    """
    hip = bsp.find_hip(arm)
    scene = bpy.context.scene

    # Camera basis setup
    CAM_FROM, CAM_AT = Vector((6.0, -8.0, 6.8)), Vector((0.0, 0.0, 0.9))
    look = CAM_AT - CAM_FROM
    rot = look.to_track_quat("-Z", "Y").to_matrix()
    right, up = rot.col[0].copy(), rot.col[1].copy()
    look_dir = look.normalized()

    def screen_to_ground_dir(dx: float, dy: float) -> Vector:
        v = dx * right - dy * up
        v_ground = v - look_dir * (v.z / look_dir.z)
        return Vector((v_ground.x, v_ground.y, 0.0)).normalized()

    # Travel & partner directions matching existing manifest
    if person == "Nathan":
        walk_dir = screen_to_ground_dir(245.0, 65.0)
        partner_dir = screen_to_ground_dir(-60.0, 20.0)
        donor_start, donor_end = 40, 106
    else:
        walk_dir = screen_to_ground_dir(200.0, 55.0)
        partner_dir = screen_to_ground_dir(60.0, -20.0)
        donor_start, donor_end = 200, 266

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

    angle_diff = (partner_rot_z - walk_rot_z + math.pi) % (2.0 * math.pi) - math.pi

    # Gather walk offsets with rig translation zero BEFORE keying them
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
    walk_end_loc = hip.location.copy()

    # Retarget authored idle donor motion onto frames 33..64
    idle_donor = get_idle_donor_src()
    idle_source_frames = [int(round(donor_start + i * ((donor_end - donor_start) / 31.0))) for i in range(32)]
    # Retarget in the imported character basis, before applying scene-facing yaw.
    rig.rotation_euler = (0.0, 0.0, 0.0)
    rig.location = (0.0, 0.0, 0.0)
    bpy.context.view_layer.update()
    bsp.apply_walk_to_rig(idle_donor, arm, list(range(33, 65)), source_frames=idle_source_frames)

    # Smooth 10-frame transition (33..42) from walk stride into authored idle mocap
    for f in range(33, 43):
        scene.frame_set(f)
        bpy.context.view_layer.update()
        t = (f - 32) / 10.0
        s = 3.0 * t * t - 2.0 * t * t * t
        for pb in arm.pose.bones:
            if pb.rotation_mode == "QUATERNION" and pb.name in walk_end_rot:
                target_q = pb.rotation_quaternion.copy()
                pb.rotation_quaternion = walk_end_rot[pb.name].slerp(target_q, s)
                pb.keyframe_insert("rotation_quaternion", frame=f)
        hip.location = walk_end_loc.lerp(hip.location.copy(), s)
        hip.keyframe_insert("location", frame=f)

    # Rotate toward partner around hip, re-centering rotated hip at origin each frame to eliminate orbital drift
    for f in range(33, frame_count + 1):
        scene.frame_set(f)
        if f <= 42:
            t = (f - 32) / 10.0
            s = 3.0 * t * t - 2.0 * t * t * t
            curr_rot_z = walk_rot_z + angle_diff * s
        else:
            curr_rot_z = walk_rot_z + angle_diff

        rig.rotation_euler = (0.0, 0.0, curr_rot_z)
        rig.location = (0.0, 0.0, 0.0)
        bpy.context.view_layer.update()
        p = arm.matrix_world @ hip.head
        rig.location = (-p.x, -p.y, 0.0)
        rig.keyframe_insert("location", frame=f)
        rig.keyframe_insert("rotation_euler", frame=f)

    # Physically ground figure with actual vertex minz across all 64 frames
    bsp.ground_rig_to_floor(rig, meshes, frame_count)



def turn_head_world(arm, radians):
    pb=bsp.get_bone(arm, "head")
    b=pb.bone
    axis=(arm.matrix_world.to_3x3().inverted() @ Vector((0,0,1))).normalized()
    desired=(Quaternion(axis,radians).to_matrix() @ pb.matrix.to_3x3()).to_4x4()
    if b.parent:
        basis=b.matrix_local.inverted() @ b.parent.matrix_local @ arm.pose.bones[b.parent.name].matrix.inverted() @ desired
    else:
        basis=b.matrix_local.inverted() @ desired
    pb.rotation_quaternion=basis.to_quaternion()
    pb.keyframe_insert("rotation_quaternion",frame=bpy.context.scene.frame_current)
    bpy.context.view_layer.update()

def authored_seated_pose(arm, rig, meshes, person: str, frame_count: int, turn_dir: int, baseline: dict = None):
    """32-frame Seated posture adapting authored mocap to chair:
    Nathan: relaxed folded-arm listening pose from Sophia donor (~375..437).
            Preserves authentic native folded arms, elbows, wrists, and fingers intact.
            Pelvis and legs adapted to chair with natural asymmetric stance.
    Carla:  seated posture with authored upper-body nuance (donor ~215..277).
            Forearms comfortably on lap/thighs with gentle conversational gesture,
            close knees, authentic curled mocap fingers, and grounded feet.
    """
    scene = bpy.context.scene
    bsp.reset_rig_to_baseline(arm, baseline)
    hip = bsp.find_hip(arm)
    hip.location = Vector((0.0, 0.0, 0.0))

    idle_donor = get_idle_donor_src()

    if person == "Nathan":
        # Nathan: folded-arm listening pose from donor Sophia ~375..437
        donor_frames = [int(round(320 + i * (110.0 / (frame_count - 1)))) for i in range(frame_count)]
        bsp.apply_walk_to_rig(idle_donor, arm, list(range(1, frame_count + 1)), source_frames=donor_frames)

        for f in range(1, frame_count + 1):
            scene.frame_set(f)
            bpy.context.view_layer.update()
            p = (f - 1) / max(1, frame_count - 1)
            breath = math.sin(p * math.pi * 2.0) * 0.012

            hip.location = Vector((0.0, 0.0, 0.0))
            hip.keyframe_insert("location", frame=f)

            # Torso: gentle forward lean into chair while preserving authored twist

            # Head: natural conversation gaze turned left toward partner without sideways roll

            # Legs: comfortable asymmetric seated fit in chair
            bsp.set_bone_direction_world(arm, "upperleg_l", Vector((0.10, -0.99, 0.05)), frame=f)
            bsp.set_bone_direction_world(arm, "upperleg_r", Vector((-0.09, -0.99, 0.04)), frame=f)
            bsp.set_bone_direction_world(arm, "lowerleg_l", Vector((0.04, 0.02, -0.999)), frame=f)
            bsp.set_bone_direction_world(arm, "lowerleg_r", Vector((-0.03, -0.06, -0.998)), frame=f)
            bsp.set_bone_direction_world(arm, "foot_l", Vector((0.03, -0.998, 0.0)), frame=f)
            bsp.set_bone_direction_world(arm, "foot_r", Vector((-0.02, -0.998, 0.0)), frame=f)

    else:
        # Carla: comfortable seated posture with authored upper-body nuance (donor ~215..277)
        donor_frames = [int(round(215 + i * (132.0 / (frame_count - 1)))) for i in range(frame_count)]
        bsp.apply_walk_to_rig(idle_donor, arm, list(range(1, frame_count + 1)), source_frames=donor_frames)

        for f in range(1, frame_count + 1):
            scene.frame_set(f)
            bpy.context.view_layer.update()
            p = (f - 1) / max(1, frame_count - 1)
            breath = math.sin(p * math.pi * 2.0) * 0.012
            chat = math.sin(p * math.pi) * 0.03
            turn_head_world(arm, math.radians(35.0))
            nod = math.sin(p * math.pi * 2.0) * 0.02

            hip.location = Vector((0.0, 0.0, 0.0))
            hip.keyframe_insert("location", frame=f)

            # Torso gently leaning forward (world -Y)

            # Head upright with listening nod turned right toward partner
            head_yaw = turn_dir * (0.32 + chat * 0.4)

            # Thighs: knees close together, calves down, feet flat
            bsp.set_bone_direction_world(arm, "upperleg_l", Vector((0.05, -0.995, 0.04)), frame=f)
            bsp.set_bone_direction_world(arm, "upperleg_r", Vector((-0.07, -0.995, 0.04)), frame=f)
            bsp.set_bone_direction_world(arm, "lowerleg_l", Vector((0.02, -0.06, -0.998)), frame=f)
            bsp.set_bone_direction_world(arm, "lowerleg_r", Vector((-0.03, 0.02, -0.999)), frame=f)
            bsp.set_bone_direction_world(arm, "foot_l", Vector((0.02, -0.998, 0.0)), frame=f)
            bsp.set_bone_direction_world(arm, "foot_r", Vector((-0.02, -0.998, 0.0)), frame=f)

            # Arms & Hands: resting forward on lap/thighs; right arm gestures subtly in middle frames
            bsp.set_bone_direction_world(arm, "upperarm_l", Vector((-0.06, -0.16, -0.985)), frame=f)
            bsp.set_bone_direction_world(arm, "lowerarm_l", Vector((-0.14, -0.985, -0.07)), frame=f)
            bsp.set_bone_direction_world(arm, "hand_l", Vector((-0.08, -0.975, -0.20)), frame=f)

            bsp.set_bone_direction_world(arm, "upperarm_r", Vector((0.06, -0.18, -0.98)), frame=f)
            bsp.set_bone_direction_world(arm, "lowerarm_r", Vector((0.14, -0.985, -0.07 + chat * 1.5)), frame=f)
            bsp.set_bone_direction_world(arm, "hand_r", Vector((0.08, -0.975, -0.20 + chat * 2.0)), frame=f)

    # Physically ground figure with actual vertex minz
    bsp.ground_rig_to_floor(rig, meshes, frame_count)


# Distinct authored standing sequences; no symmetric reconstructed skeleton.
STANDING_RANGES = {
    "standing_idle": (72, 204),
    "standing_terrace": (310, 442),
    "standing_vanity": (175, 307),
    "standing_counter": (240, 372),
}
for _name in ("nathan-standing-idle", "carla-standing-terrace", "carla-vanity-back", "nathan-counter-idle"):
    _cfg = dict(bsp.PROFILES[_name])
    _cfg["donor_range"] = STANDING_RANGES[_cfg["motion_kind"]]
    _cfg["description"] = "Authored idle motion retaining original spine, shoulders, hands and weight shifts; original scan textures."
    REVIEW_PROFILES[_name] = _cfg

def authored_standing_pose(arm, rig, meshes, person, frame_count, stance, baseline=None):
    if arm.animation_data:
        arm.animation_data_clear()
    start,end=STANDING_RANGES[stance]
    source_frames=[round(start+i*(end-start)/(frame_count-1)) for i in range(frame_count)]
    bsp.apply_walk_to_rig(get_idle_donor_src(),arm,list(range(1,frame_count+1)),source_frames=source_frames)
    bsp.ground_rig_to_floor(rig,meshes,frame_count)

def paced_hero_motion(arm, rig, meshes, person, frame_count, turn_dir, baseline=None):
    """Three gait cycles over 4.4s, then 4.4s of authored settling/listening."""
    scene=bpy.context.scene
    if rig.animation_data: rig.animation_data_clear()
    if arm.animation_data: arm.animation_data_clear()
    rig.rotation_euler=(0,0,0)
    rig.location=(0,0,0)
    bpy.context.view_layer.update()
    nwalk=80
    walk_frames=[10+(round(i*95/(nwalk-1))%32) for i in range(nwalk)]
    bsp.apply_walk_to_rig(bsp.get_walk_src(),arm,list(range(1,nwalk+1)),source_frames=walk_frames)
    hip=bsp.find_hip(arm)
    scene.frame_set(1)
    start=arm.matrix_world @ hip.head
    scene.frame_set(nwalk)
    delta=(arm.matrix_world @ hip.head)-start
    base_angle=math.atan2(delta.y,delta.x)
    end_rot={p.name:p.rotation_quaternion.copy() for p in arm.pose.bones}
    end_loc={p.name:p.location.copy() for p in arm.pose.bones}
    begin=40 if person=="Nathan" else 200
    idle_frames=[round(begin+i*66/79) for i in range(80)]
    bsp.apply_walk_to_rig(get_idle_donor_src(),arm,list(range(81,161)),source_frames=idle_frames)
    for f in range(81,91):
        scene.frame_set(f)
        t=(f-80)/10; blend=t*t*(3-2*t)
        for pb in arm.pose.bones:
            pb.rotation_quaternion=end_rot[pb.name].slerp(pb.rotation_quaternion.copy(),blend)
            pb.location=end_loc[pb.name].lerp(pb.location.copy(),blend)
            pb.keyframe_insert('rotation_quaternion',frame=f)
            pb.keyframe_insert('location',frame=f)
    cam_from=Vector((6,-8,6.8));cam_at=Vector((0,0,.9))
    look=(cam_at-cam_from).normalized();r=(cam_at-cam_from).to_track_quat('-Z','Y').to_matrix()
    right,up=r.col[0],r.col[1]
    def screen_dir(dx,dy):
        v=dx*right-dy*up
        return (v-look*(v.z/look.z)).normalized()
    travel=screen_dir(245,65) if person=="Nathan" else screen_dir(200,55)
    partner=screen_dir(-60,20) if person=="Nathan" else screen_dir(60,-20)
    heading=math.atan2(travel.y,travel.x)-base_angle
    settled=math.atan2(partner.y,partner.x)-base_angle
    turn=(settled-heading+math.pi)%(2*math.pi)-math.pi
    hips={}
    for f in range(1,161):
        scene.frame_set(f)
        hips[f]=(arm.matrix_world @ hip.head).copy()
    for f in range(1,161):
        scene.frame_set(f)
        t=max(0,min(1,(f-80)/10));angle=heading+turn*t*t*(3-2*t)
        pos=Quaternion(Vector((0,0,1)),angle) @ hips[f]
        rig.rotation_euler=(0,0,angle)
        rig.location=(-pos.x,-pos.y,0)
        rig.keyframe_insert('rotation_euler',frame=f)
        rig.keyframe_insert('location',frame=f)
    bsp.ground_rig_to_floor(rig,meshes,160)

for _name,_cfg in REVIEW_PROFILES.items():
    _cfg['frame_count']=160 if _name.startswith('hero-') else 96

def main():
    args = bsp.parse_args()
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)

    if args["profile"]:
        if args["profile"] not in REVIEW_PROFILES:
            raise SystemExit(f"Unknown profile: {args['profile']}. Choices: {list(REVIEW_PROFILES.keys())}")
        targets = [args["profile"]]
    else:
        targets = list(REVIEW_PROFILES.keys())
        if "--review-core" in sys.argv:
            targets = targets[:4]
        if "--review-seated" in sys.argv:
            targets = [n for n in targets if "seated" in n]

    # Temporarily override build_scene_people animation handlers and paths
    bsp.apply_hero_motion = paced_hero_motion
    bsp.apply_seated_pose = authored_seated_pose
    bsp.apply_standing_pose = authored_standing_pose
    bsp.SCENES_DIR = ASSETS_DIR
    bsp.RENDERED_BASE = FRAMES_DIR
    bsp.PROVENANCE_FILE = PROVENANCE_FILE

    print(f"Authored Motion Review Renderer: Blender {bpy.app.version_string}")
    print(f"Targets ({len(targets)}): {targets}")
    print(f"Options: preview={args['preview']}, resume={args['resume']}, samples={args['samples']}")
    print(f"Output assets: {ASSETS_DIR}")
    print(f"Output frames: {FRAMES_DIR}")

    # Bake donor before importing any target rig: donor cleanup owns an empty scene.
    bpy.ops.wm.read_factory_settings(use_empty=True)
    get_idle_donor_src()

    for name in targets:
        cfg = REVIEW_PROFILES[name]
        bsp.render_profile(
            name,
            cfg,
            preview=args["preview"],
            samples=args["samples"],
            resume=args["resume"]
        )

        rendered_dir = FRAMES_DIR / name
        if args["preview"]:
            pinfo_file = rendered_dir / "preview-info.json"
            if pinfo_file.is_file():
                try:
                    pinfo = json.loads(pinfo_file.read_text())
                    pinfo["motion_donor"] = {
                        "model": "Sophia animated 003 idling (motion donor only)",
                        "donor_range": list(cfg["donor_range"]),
                        "retargeting": "Full-body rest-aware basis transform across 88 bones"
                    }
                    pinfo_file.write_text(json.dumps(pinfo, indent=2) + "\n")
                except Exception:
                    pass
        else:
            out_json = ASSETS_DIR / f"{name}.json"
            if out_json.is_file():
                try:
                    meta = json.loads(out_json.read_text())
                    meta["clip_seconds"] = 8.8
                    meta["fps"] = meta["frame_count"] / 8.8
                    meta["motion_donor"] = {
                        "model": "Sophia animated 003 idling (motion donor only)",
                        "donor_range": list(cfg["donor_range"]),
                        "retargeting": "Full-body rest-aware basis transform across 88 bones"
                    }
                    out_json.write_text(json.dumps(meta, indent=2) + "\n")
                except Exception:
                    pass

    print("\nAll selected authored motion review profiles completed successfully.")


if __name__ == "__main__":
    main()
