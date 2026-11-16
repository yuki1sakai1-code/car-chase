import bpy
import json
import math
import os
import numpy as np
from mathutils import Vector, Matrix

WORKSPACE = r"c:\Users\yukis\Downloads\car-chase"
ARTIFACT_DIR = r"C:\Users\yukis\.gemini\antigravity\brain\a7fa3ca4-5441-4310-b9b2-8667e442a327"
os.makedirs(ARTIFACT_DIR, exist_ok=True)

# 1. Reset scene
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# Load track_data.json
with open(os.path.join(WORKSPACE, "assets", "track_data.json"), "r") as f:
    track_data = json.load(f)

points = track_data["points"]
N = len(points)
total_len = track_data["totalLength"]

# Import the 3 actual GLB files exported for Three.js
bpy.ops.import_scene.gltf(filepath=os.path.join(WORKSPACE, "assets", "models", "desk_environment.glb"))
bpy.ops.import_scene.gltf(filepath=os.path.join(WORKSPACE, "assets", "models", "race_track.glb"))

existing_objs = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=os.path.join(WORKSPACE, "assets", "models", "racing_kart.glb"))
kart_objs = [o for o in bpy.data.objects if o not in existing_objs]

kart_parent = bpy.data.objects.new("QA_Kart_Wrapper", None)
scene.collection.objects.link(kart_parent)
for o in kart_objs:
    if o.parent is None:
        o.parent = kart_parent

kart_parent.scale = (1.08, 1.08, 1.08)

# Bind 2K asphalt PBR texture to Mat_Asphalt
asphalt_albedo_path = os.path.join(WORKSPACE, "assets", "textures", "track_asphalt_albedo_2k.png")
if os.path.exists(asphalt_albedo_path):
    img_asphalt = bpy.data.images.load(asphalt_albedo_path)
    for mat in bpy.data.materials:
        if mat.name.startswith("Mat_Asphalt") and mat.use_nodes:
            nt = mat.node_tree
            bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
            if bsdf:
                tex = nt.nodes.new('ShaderNodeTexImage')
                tex.image = img_asphalt
                nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])

# Setup World & Studio Lighting matching Three.js scene
world = bpy.data.worlds.new("QA_World")
scene.world = world
world.use_nodes = True
bg_node = world.node_tree.nodes.get("Background")
if bg_node:
    bg_node.inputs[0].default_value = (0.07, 0.04, 0.09, 1.0)
    bg_node.inputs[1].default_value = 1.1

def three_to_blender_pos(v):
    return Vector((v[0], -v[2], v[1]))

def add_light(name, ltype, pos_three, color, energy, size=2.0):
    ld = bpy.data.lights.new(name=name, type=ltype)
    ld.color = color
    ld.energy = energy
    if ltype == 'POINT':
        ld.shadow_soft_size = size
    elif ltype == 'SUN':
        ld.angle = math.radians(8.0)
    lo = bpy.data.objects.new(name=name, object_data=ld)
    scene.collection.objects.link(lo)
    lo.location = three_to_blender_pos(pos_three)
    return lo

sun = add_light("WarmSun", 'SUN', (66, 48, -34), (1.0, 0.68, 0.36), 3.4)
sun.rotation_euler = (math.radians(48), math.radians(15), math.radians(28))

add_light("WarmLampPoint", 'POINT', (66, 22, -34), (1.0, 0.58, 0.22), 22000.0, size=4.5)
add_light("EdisonPoint", 'POINT', (38, 22, -78), (1.0, 0.62, 0.25), 14000.0, size=3.5)
add_light("KeyboardCyan", 'POINT', (-6, 10, -12), (0.0, 0.94, 1.0), 8500.0, size=5.0)
add_light("FinishKeyboardCyan", 'POINT', (22, 6, 66), (0.0, 0.94, 1.0), 6500.0, size=4.0)
add_light("MatPurple", 'POINT', (-45, 16, 30), (0.78, 0.22, 1.0), 7500.0, size=6.0)
add_light("FrontFill", 'POINT', (0, 28, 65), (0.85, 0.90, 1.0), 5500.0, size=8.0)

# Create Camera
cam_data = bpy.data.cameras.new("QA_Camera")
cam_data.lens = 28.0
cam_data.clip_start = 0.2
cam_data.clip_end = 500.0
cam_obj = bpy.data.objects.new("QA_Camera", cam_data)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj

scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.resolution_percentage = 100
scene.view_settings.view_transform = 'AgX' if 'AgX' in ['Standard', 'AgX', 'Filmic'] else 'Filmic'

def place_kart_and_camera(fraction, lat_offset=0.0, steer_yaw=0.0, look_pitch_offset=0.0):
    idx = int((fraction % 1.0) * N) % N
    p = points[idx]

    pos_th = Vector((p["x"], p["y"], p["z"]))
    tan_th = Vector((p["tx"], p["ty"], p["tz"])).normalized()
    nrm_th = Vector((p["nx"], p["ny"], p["nz"])).normalized()
    bin_th = Vector((p["bx"], p["by"], p["bz"])).normalized()

    kart_pos_th = pos_th + bin_th * lat_offset + nrm_th * 0.02

    pos_bl = three_to_blender_pos(kart_pos_th)
    fwd_bl = three_to_blender_pos(tan_th).normalized()
    up_bl = three_to_blender_pos(nrm_th).normalized()
    right_bl = fwd_bl.cross(up_bl).normalized()
    up_bl = right_bl.cross(fwd_bl).normalized()

    col_x = -right_bl
    col_y = -fwd_bl
    col_z = up_bl

    rot_mat = Matrix((
        (col_x.x, col_y.x, col_z.x),
        (col_x.y, col_y.y, col_z.y),
        (col_x.z, col_y.z, col_z.z)
    ))
    kart_parent.location = pos_bl
    kart_parent.rotation_mode = 'QUATERNION'
    kart_parent.rotation_quaternion = rot_mat.to_quaternion()

    cam_pos_bl = pos_bl - fwd_bl * 3.75 + up_bl * 1.78 + right_bl * (steer_yaw * 0.35)
    look_target_bl = pos_bl + fwd_bl * 5.0 + up_bl * (0.68 + look_pitch_offset)

    cam_obj.location = cam_pos_bl
    direction = (look_target_bl - cam_pos_bl).normalized()
    cam_quat = direction.to_track_quat('-Z', 'Y')
    cam_obj.rotation_mode = 'QUATERNION'
    cam_obj.rotation_quaternion = cam_quat

shots = [
    ("qa_1_curbs.png", 0.54, -0.3, -0.25, -0.10),
    ("qa_2_finish_bg.png", 0.03, 0.9, 0.0, -0.15),
    ("qa_3_ramp.png", 0.14, 0.6, 0.22, 0.32),
    ("qa_4_keyboard.png", 0.43, -0.4, -0.38, -0.45),
    ("qa_5_descent.png", 0.91, -0.3, 0.18, 0.15),
]

for fname, frac, lat, steer, pitch in shots:
    place_kart_and_camera(frac, lat, steer, pitch)
    art_path = os.path.join(ARTIFACT_DIR, fname)
    scene.render.filepath = art_path
    bpy.ops.render.render(write_still=True)
    print(f"Rendered {art_path}")
