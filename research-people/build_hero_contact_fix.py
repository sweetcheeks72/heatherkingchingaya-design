"""Isolated hero contact correction: stepping turn and fixed-foot sit."""
import sys, math, json
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector,Quaternion
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import build_all_scenes_natural as natural
import build_walk_to_chairs as chair
bsp=natural.bsp;pose=natural.pose
chair.bsp=bsp;chair.review.bsp=bsp;chair.review.authored_seated_pose=pose.seated
pose.POSE_KIND='outdoor'
OUT=ROOT/'hero-contact-fix';OUT.mkdir(exist_ok=True)
smooth=chair.smooth

def motion(arm,rig,meshes,person,n,turn_dir,baseline=None):
    chair.motion(arm,rig,meshes,person,n,turn_dir,baseline)
    sc=bpy.context.scene;hip=bsp.find_hip(arm)
    def pt(name):return arm.matrix_world@bsp.get_bone(arm,name).head
    sc.frame_set(n);bpy.context.view_layer.update()
    endhip=arm.matrix_world@hip.head
    ankles={s:pt('foot_'+s).copy() for s in ['l','r']}
    end_foot_rot={s:(arm.matrix_world@bsp.get_bone(arm,'foot_'+s).matrix).to_quaternion() for s in ['l','r']}
    def sole_minima():
        dg=bpy.context.evaluated_depsgraph_get();values={s:[] for s in ['l','r']}
        for obj in meshes:
            ev=obj.evaluated_get(dg);me=ev.to_mesh();a=np.empty(len(me.vertices)*3);me.vertices.foreach_get('co',a);mw=np.array(ev.matrix_world);v=a.reshape(-1,3)@mw[:3,:3].T+mw[:3,3]
            ds={side:np.linalg.norm(v[:,:2]-np.array(pt('foot_'+side))[:2],axis=1) for side in ['l','r']}
            for side,other in [('l','r'),('r','l')]:
                mask=(ds[side]<.26)&(ds[side]<ds[other])&(v[:,2]<pt('foot_'+side).z+.06)
                if np.any(mask):values[side].append(float(v[mask,2].min()))
            ev.to_mesh_clear()
        return {s:min(values[s]) for s in values}
    initial_soles=sole_minima()
    for s in ankles:ankles[s].z-=initial_soles[s]
    knees={s:pt('lowerleg_'+s).copy() for s in ['l','r']}
    endrot=rig.rotation_euler.copy()
    forward=Quaternion(Vector((0,0,1)),endrot.z)@Vector((0,-1,0))
    lengths={s:((pt('upperleg_'+s)-pt('lowerleg_'+s)).length,(pt('lowerleg_'+s)-pt('foot_'+s)).length) for s in ['l','r']}
    saved={}
    for f in range(1,n+1):
        sc.frame_set(f);bpy.context.view_layer.update()
        saved[f]=dict(bones={p.name:(p.rotation_quaternion.copy(),p.location.copy()) for p in arm.pose.bones},loc=rig.location.copy(),rot=rig.rotation_euler.copy(),hip=(arm.matrix_world@hip.head).copy(),feet={s:pt('foot_'+s).copy() for s in ['l','r']},foot_rot={s:(arm.matrix_world@bsp.get_bone(arm,'foot_'+s).matrix).to_quaternion() for s in ['l','r']})
    sc.frame_set(80);bpy.context.view_layer.update();turn_start_soles=sole_minima();walk_lower=min(turn_start_soles.values())
    for f in range(1,81):
        drop=Vector((0,0,-walk_lower*smooth((f-64)/16)))
        saved[f]['loc']+=drop;saved[f]['hip']+=drop
        for side in ['l','r']:saved[f]['feet'][side]+=drop
        saved[f]['loc']+=forward*.36
        saved[f]['hip']+=forward*.36
        for side in ['l','r']:saved[f]['feet'][side]+=forward*.36
    # Full lower-body contact solve replaces the previous rotational pose morph.
    errors=[];pelvis=[];foot_matrices=[]
    for f in range(1,n+1):
        sc.frame_set(f)
        if f<=80:
            rig.location=saved[f]['loc'];rig.keyframe_insert('location',frame=f)
            chair.review.turn_head_world(arm,math.radians((9 if person=='Carla' else -9)*math.sin(math.pi*(f-1)/79)**2))
            continue
        src=saved[min(f,150)]
        for p in arm.pose.bones:p.rotation_quaternion,p.location=src['bones'][p.name]
        rig.location=src['loc'];rig.rotation_euler=src['rot'];bpy.context.view_layer.update()
        # Stand in front of seat while turning, then send pelvis backward over cushion.
        stand=endhip+forward*.36+Vector((0,0,.35))
        if f<=106:target=saved[80]['hip'].lerp(stand,smooth((f-80)/26))
        else:target=stand.lerp(endhip,smooth((f-106)/36))
        rig.location+=target-(arm.matrix_world@hip.head);bpy.context.view_layer.update()
        lean=math.sin(math.pi*smooth((f-100)/42))*math.radians(18)
        if lean:pose.rotate_joint_world(arm,bsp.get_bone(arm,'spine_01'),Vector((0,0,1)).cross(forward),lean)
        for s in ['l','r']:
            # Two separately weighted steps, not a planted-foot rotation through the floor.
            start,stop=(80,93) if s=='l' else (93,106)
            u=max(0,min(1,(f-start)/(stop-start)))
            goal=saved[80]['feet'][s].lerp(ankles[s],smooth(u));goal.z+=.075*math.sin(math.pi*u)
            root=pt('upperleg_'+s);a,b=lengths[s];ray=goal-root;d=min(ray.length,a+b-.00001);axis=ray.normalized()
            along=(a*a-b*b+d*d)/(2*d)
            knee_forward=Quaternion(Vector((0,0,1)),rig.rotation_euler.z)@Vector((0,-1,0))
            pole=knee_forward-axis*knee_forward.dot(axis)
            if pole.length<.001:pole=Vector((1,0,0))
            knee=root+axis*along+pole.normalized()*math.sqrt(max(0,a*a-along*along))
            bsp.set_bone_direction_world(arm,'upperleg_'+s,knee-root,frame=f)
            bsp.set_bone_direction_world(arm,'lowerleg_'+s,goal-pt('lowerleg_'+s),frame=f)
            direction=Quaternion(Vector((0,0,1)),rig.rotation_euler.z)@Vector((.09 if s=='l' else -.09,-1,0))
            foot=bsp.get_bone(arm,'foot_'+s);b=foot.bone
            q=saved[80]['foot_rot'][s].slerp(end_foot_rot[s],smooth(u))
            desired=arm.matrix_world.to_3x3().inverted()@q.to_matrix()
            basis=b.matrix_local.inverted()@b.parent.matrix_local@arm.pose.bones[b.parent.name].matrix.inverted()@desired.to_4x4()
            foot.rotation_quaternion=basis.to_quaternion();bpy.context.view_layer.update()
            if f>=106:errors.append((pt('foot_'+s)-ankles[s]).length)
        for p in arm.pose.bones:
            if any(word in p.name.lower() for word in ['toe','ball']):
                side='l' if p.name.endswith('_l') else 'r';start,stop=(80,93) if side=='l' else (93,106)
                p.rotation_quaternion=saved[80]['bones'][p.name][0].slerp(saved[n]['bones'][p.name][0],smooth((f-start)/(stop-start)))
        bpy.context.view_layer.update()
        if f>=106:
            foot_matrices.append([arm.matrix_world @ bsp.get_bone(arm,'foot_'+s).matrix for s in ['l','r']])
        for p in arm.pose.bones:p.keyframe_insert('rotation_quaternion',frame=f);p.keyframe_insert('location',frame=f)
        rig.keyframe_insert('location',frame=f);rig.keyframe_insert('rotation_euler',frame=f)
        pelvis.append([f,*target])
    foot_drift=max(abs(m[r][c]-foot_matrices[0][i][r][c]) for pair in foot_matrices for i,m in enumerate(pair) for r in range(4) for c in range(4))
    sole_checks=[]
    for f in list(range(80,107))+[118,130,142,160]:
        sc.frame_set(f);bpy.context.view_layer.update();sole_checks.append(dict(frame=f,soles=sole_minima()))
    diagnostic=dict(person=person,initial_sole_z=initial_soles,turn_start_soles=turn_start_soles,walk_support_correction_m=walk_lower,sole_checks=sole_checks,max_planted_foot_matrix_difference=foot_drift,max_planted_ankle_error_m=max(errors),plant_frame=106,sit_end_frame=142,final_hip=list(endhip),final_ankles={s:list(v) for s,v in ankles.items()},pelvis=pelvis)
    (OUT/(person.lower()+'-contact.json')).write_text(json.dumps(diagnostic,indent=2))
    print('CONTACT DIAGNOSTIC',person,max(errors),flush=True)
    assert foot_drift<.0001,'Planted foot orientation changed'
    assert max(errors)<.003,'Foot target unreachable'

def main():
    args=bsp.parse_args();bsp.SCENES_DIR=OUT/'assets';bsp.RENDERED_BASE=OUT/'frames';bsp.PROVENANCE_FILE=OUT/'assets/provenance.json'
    bsp.SCENES_DIR.mkdir(exist_ok=True);bsp.RENDERED_BASE.mkdir(exist_ok=True)
    bsp.apply_hero_motion=motion
    bpy.ops.wm.read_factory_settings(use_empty=True)
    chair.review.get_idle_donor_src();bsp.get_walk_src()
    for name in ['hero-nathan-walk-turn','hero-carla-walk-turn']:
        if args['profile'] and args['profile']!=name:continue
        cfg=dict(chair.review.REVIEW_PROFILES[name]);cfg.update(final_seat=True,is_seated=True,lighting=natural.LIGHTS['outdoor'],description='Walk together, alternate turn steps, feet planted while pelvis travels back and lowers to seat.')
        bsp.render_profile(name,cfg,preview=args['preview'],samples=args['samples'],resume=args['resume'])
        p=bsp.SCENES_DIR/(name+'.json')
        if p.exists():
            m=json.loads(p.read_text());m.update(clip_seconds=8.8,fps=160/8.8,motion='Walk 1–80; two turn steps 81–106; planted-foot sit 107–142; supported rest 143–160.');p.write_text(json.dumps(m,indent=2)+'\n')
if __name__=='__main__':main()
