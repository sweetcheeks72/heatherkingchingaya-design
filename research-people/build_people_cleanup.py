"""Direct Codex cleanup: relaxed hands, scene-oriented sitting, planted feet, softer lighting."""
import sys,json,math
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
import people_cleanup_support as bsp
import build_authored_motion_review as review
review.bsp=bsp
OUT=ROOT/'people-cleanup'

def planted(rig,meshes,n):
    scene=bpy.context.scene;values={}
    for f in range(1,n+1):
        scene.frame_set(f);bpy.context.view_layer.update();dg=bpy.context.evaluated_depsgraph_get();zs=[]
        for ob in meshes:
            ev=ob.evaluated_get(dg);me=ev.to_mesh();a=np.empty(len(me.vertices)*3);me.vertices.foreach_get('co',a)
            mw=np.array(ev.matrix_world);zs.append(float((a.reshape(-1,3)@mw[:3,:3].T+mw[:3,3])[:,2].min()));ev.to_mesh_clear()
        values[f]=(rig.location.copy(),min(zs))
    for f,(loc,z) in values.items():
        scene.frame_set(f);rig.location=loc+Vector((0,0,-z));rig.keyframe_insert('location',frame=f)

def seated(arm,rig,meshes,person,n,turn_dir,baseline=None):
    scene=bpy.context.scene
    if arm.animation_data:arm.animation_data_clear()
    # Preserve captured torso/face motion; fit resting limbs to the actual seat orientation.
    bsp.apply_walk_to_rig(review.get_idle_donor_src(),arm,list(range(1,n+1)),source_frames=[40+round(i*95/(n-1)) for i in range(n)])
    hip=bsp.find_hip(arm)
    for f in range(1,n+1):
        scene.frame_set(f);hip.location=(0,0,0);hip.keyframe_insert('location',frame=f)
        for side,sign in [('l',1),('r',-1)]:
            bsp.set_bone_direction_world(arm,'upperleg_'+side,Vector((sign*.06,-.995,.02)),frame=f)
            bsp.set_bone_direction_world(arm,'lowerleg_'+side,Vector((sign*.02,-.06,-.998)),frame=f)
            bsp.set_bone_direction_world(arm,'foot_'+side,Vector((sign*.03,-.999,0)),frame=f)
            bsp.set_bone_direction_world(arm,'upperarm_'+side,Vector((-sign*.08,-.14,-.985)),frame=f)
            bsp.set_bone_direction_world(arm,'lowerarm_'+side,Vector((sign*.10,-.93,-.35)),frame=f)
            bsp.set_bone_direction_world(arm,'hand_'+side,Vector((sign*.07,-.96,-.25)),frame=f)
        # Retain gentle head movement without the exaggerated permanent sideways turn.
        review.turn_head_world(arm,math.radians(8 if person=='Carla' else -8))
    planted(rig,meshes,n)

def standing(arm,rig,meshes,person,n,stance,baseline=None):
    if arm.animation_data:arm.animation_data_clear()
    start={'standing_idle':40,'standing_terrace':70,'standing_vanity':110,'standing_counter':40}[stance]
    bsp.apply_walk_to_rig(review.get_idle_donor_src(),arm,list(range(1,n+1)),source_frames=[start+round(i*95/(n-1)) for i in range(n)])
    for f in range(1,n+1):
        bpy.context.scene.frame_set(f)
        hip=bsp.find_hip(arm);hip.location=(0,0,0);hip.keyframe_insert('location',frame=f)
        for side,sign in [('l',1),('r',-1)]:
            bsp.set_bone_direction_world(arm,'upperleg_'+side,Vector((sign*.035,.01,-.999)),frame=f)
            bsp.set_bone_direction_world(arm,'lowerleg_'+side,Vector((-sign*.01,-.01,-.999)),frame=f)
            bsp.set_bone_direction_world(arm,'foot_'+side,Vector((sign*.09,-.995,0)),frame=f)
            if '--native-arms' in sys.argv:continue
            bsp.set_bone_direction_world(arm,'upperarm_'+side,Vector((-sign*.16,-.02,-.987)),frame=f)
            bsp.set_bone_direction_world(arm,'lowerarm_'+side,Vector((sign*.14,-.18,-.973)),frame=f)
            bsp.set_bone_direction_world(arm,'hand_'+side,Vector((sign*.04,-.10,-.994)),frame=f)
    planted(rig,meshes,n)

def main():
    args=bsp.parse_args();bsp.SCENES_DIR=OUT/'assets';bsp.RENDERED_BASE=OUT/'frames';bsp.PROVENANCE_FILE=OUT/'assets/provenance.json'
    bsp.SCENES_DIR.mkdir(parents=True,exist_ok=True);bsp.RENDERED_BASE.mkdir(parents=True,exist_ok=True)
    bsp.apply_seated_pose=seated;bsp.apply_standing_pose=standing
    bpy.ops.wm.read_factory_settings(use_empty=True);review.get_idle_donor_src();bsp.get_walk_src()
    profiles={k:dict(v) for k,v in review.REVIEW_PROFILES.items() if not k.startswith('hero-')}
    profiles['carla-seated-sofa']=dict(profiles['carla-seated-talk-right'])
    profiles['carla-seated-talk-right']['cam_from']=Vector((-8,-5,3.25))
    profiles['nathan-seated-talk-left']['cam_from']=Vector((8,-5,3.25))
    profiles['carla-seated-sofa']['cam_from']=Vector((5.5,-8,4.25))
    profiles['carla-standing-terrace']['cam_from']=Vector((5,7.5,3.0))
    for name,cfg in profiles.items():
        if args['profile'] and args['profile']!=name:continue
        cfg.update(frame_w=320,frame_h=480,description='Scene-oriented relaxed posture, native subtle torso motion, grounded soles and softer warm lighting.')
        bsp.render_profile(name,cfg,preview=args['preview'],samples=args['samples'],resume=args['resume'])
        if not args['preview']:
            p=bsp.SCENES_DIR/(name+'.json');m=json.loads(p.read_text());m.update(clip_seconds=8.8,fps=96/8.8,cleanup='Codex: planted soles, relaxed hands, scene-oriented seating, measured ground anchor; original scan materials.')
            p.write_text(json.dumps(m,indent=2)+'\n')

if __name__=='__main__':main()
