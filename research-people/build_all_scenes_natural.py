"""Direct Codex reference-led poses, scene illumination and finite paced takes."""
import sys,json,math
from pathlib import Path
import bpy
from mathutils import Vector
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
import all_scenes_pose as pose
bsp=pose.bsp;review=pose.review
OUT=ROOT/'all-scenes-natural'
LIGHTS={
 'outdoor':dict(key=(1,.95,.88),ambient=(.93,.95,.90),energy=1.8,fill=.7,exposure=-.15,side=-.6),
 'sofa':dict(key=(1,.86,.72),ambient=(1,.93,.83),energy=1.5,fill=.65,exposure=-.20,side=-.8),
 'elevation':dict(key=(1,.98,.94),ambient=(.95,.95,.95),energy=1.5,fill=.8,exposure=-.15),
 'terrace':dict(key=(1,.83,.63),ambient=(.86,.90,.93),energy=1.4,fill=.6,exposure=-.15,side=-.8),
 'bedroom':dict(key=(1,.92,.80),ambient=(.93,.87,.76),energy=1.7,fill=.70,exposure=-.1,side=-.8),
 'bath':dict(key=(1,.94,.85),ambient=(.96,.92,.85),energy=1.4,fill=.75,exposure=-.1,side=-.7),
 'cafe':dict(key=(1,.95,.88),ambient=(1,.88,.73),energy=1.6,fill=.75,exposure=-.2,side=-.5),
 'booth':dict(key=(1,.78,.55),ambient=(1,.89,.70),energy=1.2,fill=.65,exposure=-.05,side=.7),
 'counter':dict(key=(1,.85,.65),ambient=(1,.90,.75),energy=1.5,fill=.7,exposure=-.2,side=.5),
}

def standing(arm,rig,meshes,person,n,stance,baseline=None):
    if arm.animation_data:arm.animation_data_clear()
    start={'standing_idle':44,'standing_terrace':60,'standing_vanity':90,'standing_counter':40}[stance]
    bsp.apply_walk_to_rig(review.get_idle_donor_src(),arm,list(range(1,n+1)),source_frames=[start+round(min(i,n-9)*95/(n-9)) for i in range(n)])
    hip=bsp.find_hip(arm);bpy.context.scene.frame_set(1);q=hip.rotation_quaternion.copy()
    for f in range(1,n+1):
        bpy.context.scene.frame_set(f);hip.location=(0,0,0);hip.rotation_quaternion=q
        hip.keyframe_insert('location',frame=f);hip.keyframe_insert('rotation_quaternion',frame=f);bpy.context.view_layer.update()
        for side,dirs in {'l':[(.035,.01,-1),(-.015,-.015,-1),(.09,-1,0)],'r':[(-.075,-.01,-1),(.03,.08,-1),(-.12,-1,0)]}.items():
            for part,d in zip(['upperleg','lowerleg','foot'],dirs):bsp.set_bone_direction_world(arm,part+'_'+side,Vector(d),frame=f)
    bsp.ground_rig_to_floor(rig,meshes,n)
    values=[]
    for f in range(1,n+1):
        bpy.context.scene.frame_set(f);bpy.context.view_layer.update();values.append([pose.point(arm,'foot_'+s).copy() for s in ['l','r']])
    drift=max((v[i]-values[0][i]).length for v in values for i in range(2));assert drift<.001
    print('STANDING ANKLE DRIFT',person,stance,drift)

PROFILES=[
 ('carla-seated-sofa','carla-seated-talk-right','sofa',(5.5,-8,4.25)),
 ('nathan-standing-idle','nathan-standing-idle','elevation',None),
 ('carla-standing-terrace','carla-standing-terrace','terrace',(5,7.5,3)),
 ('nathan-seated-bedroom','nathan-seated-talk-left','bedroom',(8,-5,3.25)),
 ('carla-vanity-back','carla-vanity-back','bath',None),
 ('carla-seated-talk-right','carla-seated-talk-right','cafe',(-2.3,-8,3.25)),
 ('nathan-seated-talk-left','nathan-seated-talk-left','cafe',(2.3,-8,3.25)),
 ('carla-seated-booth','carla-seated-talk-right','booth',(-8,-5,3.25)),
 ('nathan-seated-booth','nathan-seated-talk-left','booth',(8,-5,3.25)),
 ('nathan-counter-idle','nathan-counter-idle','counter',None),
]

def main():
    args=bsp.parse_args();bsp.SCENES_DIR=OUT/'assets';bsp.RENDERED_BASE=OUT/'frames';bsp.PROVENANCE_FILE=OUT/'assets/provenance.json'
    bsp.SCENES_DIR.mkdir(parents=True,exist_ok=True);bsp.RENDERED_BASE.mkdir(parents=True,exist_ok=True)
    bsp.apply_seated_pose=pose.seated;bsp.apply_standing_pose=standing
    bpy.ops.wm.read_factory_settings(use_empty=True);review.get_idle_donor_src();bsp.get_walk_src()
    for name,base,kind,cam in PROFILES:
        if args['profile'] and args['profile']!=name:continue
        pose.POSE_KIND=kind
        cfg=dict(review.REVIEW_PROFILES[base]);cfg.update(frame_w=320,frame_h=480,lighting=LIGHTS[kind],description='Reference-based supported pose, individual timing and scene-specific illumination; original scan textures.')
        if cam:cfg['cam_from']=Vector(cam)
        bsp.render_profile(name,cfg,preview=args['preview'],samples=args['samples'],resume=args['resume'])
        if not args['preview']:
            p=bsp.SCENES_DIR/(name+'.json');m=json.loads(p.read_text());m.update(clip_seconds=8.8,fps=96/8.8,lighting=LIGHTS[kind],pose_kind=kind,timing='Smooth low gesture where appropriate, captured quiet motion, final eight frames held.');p.write_text(json.dumps(m,indent=2)+'\n')
if __name__=='__main__':main()
