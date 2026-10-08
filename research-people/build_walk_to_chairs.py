"""Codex-authored walk, turn, lower onto the two existing backyard chairs.

Private Blender source. Rendered pixels only enter the website.
"""
import sys, math, json
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector, Quaternion
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import build_chair_support as bsp
import build_authored_motion_review as review
review.bsp=bsp
OUT=ROOT/'walk-to-chairs'

def smooth(t):
    t=max(0,min(1,t));return t*t*(3-2*t)

def motion(arm,rig,meshes,person,n,turn_dir,baseline=None):
    scene=bpy.context.scene
    # Sample the seated endpoint before rebuilding the walk. Native finger/torso motion stays intact.
    review.authored_seated_pose(arm,rig,meshes,person,n,turn_dir,baseline)
    seated={}
    for f in range(1,n+1):
        scene.frame_set(f)
        seated[f]={p.name:(p.rotation_quaternion.copy(),p.location.copy()) for p in arm.pose.bones}
    arm.animation_data_clear();rig.animation_data_clear()
    rig.location=(0,0,0);rig.rotation_euler=(0,0,0)
    bsp.apply_walk_to_rig(bsp.get_walk_src(),arm,list(range(1,81)),source_frames=[10+round(i*95/79)%32 for i in range(80)])
    hip=bsp.find_hip(arm)
    scene.frame_set(1);start=(arm.matrix_world@hip.head).copy()
    scene.frame_set(80);delta=arm.matrix_world@hip.head-start
    walk_base=math.atan2(delta.y,delta.x)
    last={p.name:(p.rotation_quaternion.copy(),p.location.copy()) for p in arm.pose.bones}
    bsp.apply_walk_to_rig(review.get_idle_donor_src(),arm,list(range(81,n+1)),source_frames=[200+round(i*66/79) for i in range(80)])
    for f in range(81,n+1):
        scene.frame_set(f)
        settle=smooth((f-80)/16)
        sit=smooth((f-104)/30)
        for p in arm.pose.bones:
            q,loc=last[p.name];sq,sloc=seated[f][p.name]
            p.rotation_quaternion=q.slerp(p.rotation_quaternion.copy(),settle).slerp(sq,sit)
            p.location=loc.lerp(p.location.copy(),settle).lerp(sloc,sit)
            p.keyframe_insert('rotation_quaternion',frame=f);p.keyframe_insert('location',frame=f)
    look=Vector((-6,8,-5.9));r=look.to_track_quat('-Z','Y').to_matrix()
    def screen_dir(dx,dy):
        v=dx*r.col[0]-dy*r.col[1]
        return (v-look*(v.z/look.z)).normalized()
    direction=screen_dir(-260,-30)
    walk_angle=math.atan2(direction.y,direction.x)-walk_base
    facing=screen_dir(18,18)
    # Seated pose faces native -Y; turn around the pelvis, then lower with both feet planted.
    seat_angle=math.atan2(facing.y,facing.x)+math.pi/2
    turn=(seat_angle-walk_angle+math.pi)%(2*math.pi)-math.pi
    hips={}
    for f in range(1,n+1):
        scene.frame_set(f);hips[f]=(arm.matrix_world@hip.head).copy()
    for f in range(1,n+1):
        scene.frame_set(f)
        angle=walk_angle+turn*smooth((f-80)/24)
        pos=Quaternion(Vector((0,0,1)),angle)@hips[f]
        rig.rotation_euler=(0,0,angle);rig.location=(-pos.x,-pos.y,0)
        rig.keyframe_insert('rotation_euler',frame=f);rig.keyframe_insert('location',frame=f)
    # Measured mesh soles set the actual ground plane; gather before writing keys.
    lows={};locations={}
    for f in range(1,n+1):
        scene.frame_set(f);bpy.context.view_layer.update()
        locations[f]=rig.location.copy();vals=[]
        dg=bpy.context.evaluated_depsgraph_get()
        for obj in meshes:
            ev=obj.evaluated_get(dg);me=ev.to_mesh();a=np.empty(len(me.vertices)*3)
            me.vertices.foreach_get('co',a);mw=np.array(ev.matrix_world)
            vals.append(float((a.reshape(-1,3)@mw[:3,:3].T+mw[:3,3])[:,2].min()));ev.to_mesh_clear()
        lows[f]=min(vals)
    floor=min(lows[f] for f in range(1,81))
    for f in range(1,n+1):
        scene.frame_set(f);t=smooth((f-80)/16)
        rig.location=locations[f]+Vector((0,0,-((1-t)*floor+t*lows[f])))
        rig.keyframe_insert('location',frame=f)

def main():
    args=bsp.parse_args();OUT.mkdir(exist_ok=True)
    bsp.SCENES_DIR=OUT/'assets';bsp.RENDERED_BASE=OUT/'frames';bsp.PROVENANCE_FILE=OUT/'assets/provenance.json'
    bsp.SCENES_DIR.mkdir(exist_ok=True);bsp.RENDERED_BASE.mkdir(exist_ok=True)
    bsp.apply_hero_motion=motion
    bpy.ops.wm.read_factory_settings(use_empty=True)
    review.get_idle_donor_src();bsp.get_walk_src()
    for name in ['hero-nathan-walk-turn','hero-carla-walk-turn']:
        if args['profile'] and args['profile']!=name:continue
        cfg=dict(review.REVIEW_PROFILES[name]);cfg.update(final_seat=True,is_seated=True,description='Walk to backyard chairs, turn and sit, then rest.')
        bsp.render_profile(name,cfg,preview=args['preview'],samples=args['samples'],resume=args['resume'])
        p=bsp.SCENES_DIR/(name+'.json')
        if not args['preview']:
            m=json.loads(p.read_text());m.update(clip_seconds=8.8,fps=160/8.8,motion='80 frames walking, 24 turning, 30 sitting, 26 settling; final hip anchor measured in Blender.')
            p.write_text(json.dumps(m,indent=2)+'\n')

if __name__=='__main__':main()
