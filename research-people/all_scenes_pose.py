"""One-pair reference-led study. Never writes live site assets."""
import sys, math, json
from pathlib import Path
import bpy
from mathutils import Vector, Quaternion
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import build_people_cleanup as clean
import all_scenes_support as bsp
review=clean.review
review.bsp=bsp
POSE_KIND="cafe"
OUT=ROOT/'all-scenes-natural'

def point(arm,name):
    return arm.matrix_world @ bsp.get_bone(arm,name).head

def rotate_joint_world(arm,pb,axis,angle):
    b=pb.bone;axis=(arm.matrix_world.to_3x3().inverted() @ Vector(axis)).normalized()
    desired=(Quaternion(axis,angle).to_matrix() @ pb.matrix.to_3x3()).to_4x4()
    basis=b.matrix_local.inverted() @ desired
    if b.parent:basis=b.matrix_local.inverted() @ b.parent.matrix_local @ arm.pose.bones[b.parent.name].matrix.inverted() @ desired
    pb.rotation_quaternion=basis.to_quaternion();bpy.context.view_layer.update()

def rest_hand_on_thigh(arm,side,frame,person):
    shoulder=point(arm,'upperarm_'+side);elbow=point(arm,'lowerarm_'+side);wrist=point(arm,'hand_'+side)
    hip=point(arm,'upperleg_'+side);knee=point(arm,'lowerleg_'+side)
    fraction=(.45 if side=='l' else .30) if person=='Nathan' else .50
    target=hip+(knee-hip)*fraction+Vector((0,0,.16 if person=='Nathan' else .14))
    if person=='Nathan' and side=='r':target+=Vector((.08,0,.02))
    a=(elbow-shoulder).length;b=(wrist-elbow).length
    ray=target-shoulder;dist=min(ray.length,a+b-.002);u=ray.normalized()
    along=(a*a-b*b+dist*dist)/(2*dist)
    pole=Vector((-.7,0,-.2)) if person=='Nathan' and side=='r' else Vector((.18 if side=='l' else -.18,.85,-.25))
    perp=(pole-u*pole.dot(u)).normalized()
    desired_elbow=shoulder+u*along+perp*math.sqrt(max(0,a*a-along*along))
    bsp.set_bone_direction_world(arm,'upperarm_'+side,desired_elbow-shoulder,frame=frame)
    bsp.set_bone_direction_world(arm,'lowerarm_'+side,target-point(arm,'lowerarm_'+side),frame=frame)
    hand_dir=Vector((.4,-.8,-.05)) if person=='Nathan' and side=='r' else (knee-hip)+Vector((0,0,.05))
    bsp.set_bone_direction_world(arm,'hand_'+side,hand_dir,frame=frame)
    if frame==1:print('HAND CONTACT',person,side,'reach',round(ray.length,3),'segments',round(a+b,3),'error',round((point(arm,'hand_'+side)-target).length,4))

def seated(arm,rig,meshes,person,n,turn_dir,baseline=None):
    if arm.animation_data:arm.animation_data_clear()
    start=70 if person=='Carla' else 150
    bsp.apply_walk_to_rig(review.get_idle_donor_src(),arm,list(range(1,n+1)),source_frames=[start+round(min(i,n-9)*95/(n-9)) for i in range(n)])
    hip=bsp.find_hip(arm)
    bpy.context.scene.frame_set(1);bpy.context.view_layer.update()
    if person=='Nathan':
        rotate_joint_world(arm,hip,(1,0,0),math.radians(-4))
        rotate_joint_world(arm,hip,(0,0,1),math.radians(-3))
    hip_rotation=hip.rotation_quaternion.copy()
    for f in range(1,n+1):
        bpy.context.scene.frame_set(f)
        hip.location=(0,0,0);hip.keyframe_insert('location',frame=f)
        hip.rotation_quaternion=hip_rotation;hip.keyframe_insert('rotation_quaternion',frame=f)
        bpy.context.view_layer.update()
        # Seat-aligned lower body: unequal knees and offset shins, fixed through the take.
        if person=='Carla':
            legs={'l':[(.10,-1,-.07),(.02,.20,-1),(.09,-1,0)],'r':[(-.04,-1,-.035),(-.03,-.18,-1),(-.08,-1,0)]}
            spine=(.02,.10,1) if POSE_KIND in ['sofa','outdoor'] else (.015,-.045,1)
            arms={'l':[(.12,-.10,-1),(-.22,-.87,-.43),(-.12,-.92,-.32)],
                  'r':[(-.09,-.26,-1),(.13,-.77,.57),(.04,-.91,.16)]}
        else:
            legs={'l':[(.20,-1,-.055),(.05,-.16,-1),(.16,-1,0)],'r':[(-.12,-1,-.04),(-.06,.18,-1),(-.10,-1,0)]}
            spine=(-.018,.035,1)
            arms={'l':[(.08,-.12,-1),(-.40,-.85,-.30),(-.38,-.89,-.20)],
                  'r':[(-.10,-.12,-1),(.21,-.93,-.27),(.10,-.98,-.14)]}
        # Small, supported spinal curves rather than a rigid upright stack.
        if person=='Nathan':
            for b,d,twist in [('spine_01',(-.035,.15,1),-3),('spine_02',(-.02,.10,1),-5),('spine_03',(-.015,-.025,1),-6)]:
                bsp.set_bone_direction_world(arm,b,Vector(d),frame=f,twist_rad=math.radians(twist))
            # Lower one shoulder modestly; retain the original shoulder breadth.
            clavicle=bsp.get_bone(arm,'clavicle_r')
            if clavicle:
                rotate_joint_world(arm,clavicle,(0,1,0),math.radians(-4))
                clavicle.keyframe_insert('rotation_quaternion',frame=f)
        else:
            for b in ['spine_01','spine_02']:
                bsp.set_bone_direction_world(arm,b,Vector(spine),frame=f)
        for side in ['l','r']:
            for part,d in zip(['upperleg','lowerleg','foot'],legs[side]):
                bsp.set_bone_direction_world(arm,part+'_'+side,Vector(d),frame=f)
            for part,d in zip(['upperarm','lowerarm','hand'],arms[side]):
                # One quiet speaker gesture, the listener's hands keep resting.
                v=Vector(d)
                if person=='Carla' and side=='r' and part in ['lowerarm','hand']:
                    t=(f-1)/(n-1);v.x+=.035*math.sin(math.pi*t)**2;v.z+=.045*math.sin(math.pi*t)**2
                bsp.set_bone_direction_world(arm,part+'_'+side,v,frame=f)
        for side in (['l'] if person=='Carla' else ['l','r']):
            rest_hand_on_thigh(arm,side,f,person)
        if person=='Carla':
            names=['upperarm_r','lowerarm_r','hand_r']
            gesture={b:bsp.get_bone(arm,b).rotation_quaternion.copy() for b in names}
            rest_hand_on_thigh(arm,'r',f,person)
            t=(f-1)/(n-1)
            a,b,c,d=(.30,.43,.62,.78) if POSE_KIND=='booth' else (.12,.25,.52,.68)
            smooth=lambda x:max(0,min(1,x))**2*(3-2*max(0,min(1,x)))
            weight=min(smooth((t-a)/(b-a)),1-smooth((t-c)/(d-c))) if POSE_KIND in ['cafe','booth'] else 0
            for name in names:
                bone=bsp.get_bone(arm,name);bone.rotation_quaternion=bone.rotation_quaternion.slerp(gesture[name],weight);bone.keyframe_insert('rotation_quaternion',frame=f)
            bpy.context.view_layer.update()
        review.turn_head_world(arm,math.radians((8 if POSE_KIND in ['sofa','outdoor'] else 24) if person=='Carla' else -24))
    # Constant grounding preserves the seated pelvis instead of bobbing with a shoe vertex.
    bsp.ground_rig_to_floor(rig,meshes,n)
    anchors=[]
    for f in range(1,n+1):
        bpy.context.scene.frame_set(f);bpy.context.view_layer.update()
        anchors.append([point(arm,'foot_'+s).copy() for s in ['l','r']])
    drift=max((a[i]-anchors[0][i]).length for a in anchors for i in range(2))
    print('ANKLE DRIFT METRES',person,drift)
    assert drift<.001, 'Seated ankle drift exceeds 1mm'
