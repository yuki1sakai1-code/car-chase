import bpy
import math
import os
from mathutils import Vector

GLB_PATH = r"c:\Users\yukis\Downloads\car-chase\assets\models\touge_cars.glb"
OUT_DIR = r"C:\Users\yukis\.gemini\antigravity\brain\a7fa3ca4-5441-4310-b9b2-8667e442a327"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB_PATH)

scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.view_settings.view_transform = 'AgX'

# World dusk mountain parking lot lighting
world = bpy.data.worlds.new("TougeWorld")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
bg.inputs[0].default_value = (0.09, 0.12, 0.16, 1.0)
bg.inputs[1].default_value = 1.4

# Asphalt ground plane + white parking lines
bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0))
ground = bpy.context.active_object
gmat = bpy.data.materials.new("Asphalt")
gmat.use_nodes = True
bsdf = gmat.node_tree.nodes.get("Principled BSDF")
bsdf.inputs["Base Color"].default_value = (0.07, 0.075, 0.085, 1.0)
bsdf.inputs["Roughness"].default_value = 0.65
ground.data.materials.append(gmat)

# Position the 3 cars for showcase
ae86 = bpy.data.objects.get("Car_AE86")
r32 = bpy.data.objects.get("Car_R32")
rx7 = bpy.data.objects.get("Car_RX7")

if ae86:
    ae86.location = (0.0, 0.0, 0.0)
if r32:
    r32.location = (3.2, 1.6, 0.0)
    r32.rotation_euler = (0, 0, math.radians(-18))
if rx7:
    rx7.location = (-3.2, 1.6, 0.0)
    rx7.rotation_euler = (0, 0, math.radians(18))

# Studio + Touge Key/Rim lights
for name, loc, energy, color in [
    ("KeyLight", (-4.5, -5.5, 4.2), 900.0, (0.95, 0.97, 1.0)),
    ("FillLight", (5.0, -4.0, 3.0), 450.0, (0.80, 0.88, 1.0)),
    ("RimLight", (0.0, 5.5, 4.0), 750.0, (1.0, 0.92, 0.80)),
]:
    ld = bpy.data.lights.new(name=name, type='AREA')
    ld.energy = energy
    ld.size = 4.5
    ld.color = color
    lo = bpy.data.objects.new(name=name, object_data=ld)
    bpy.context.collection.objects.link(lo)
    lo.location = loc
    direction = Vector((0, 0, 0.6)) - Vector(loc)
    lo.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()

# Camera matching the front-right 3/4 reference photo of AE86
cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = 42
cam_obj = bpy.data.objects.new("Cam", cam_data)
bpy.context.collection.objects.link(cam_obj)
scene.camera = cam_obj

# 1. Close-up of AE86 (same angle as user's reference photo!)
if r32: r32.hide_render = True
if rx7: rx7.hide_render = True
cam_obj.location = (-2.35, -3.45, 1.25)
direction = Vector((0.0, -0.15, 0.62)) - cam_obj.location
cam_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
scene.render.filepath = os.path.join(OUT_DIR, "qa_ae86_closeup.png")
bpy.ops.render.render(write_still=True)

# 2. 3-Car Lineup (AE86, R32, RX-7)
if r32: r32.hide_render = False
if rx7: rx7.hide_render = False
cam_obj.location = (0.0, -5.8, 1.65)
direction = Vector((0.0, 0.4, 0.65)) - cam_obj.location
cam_obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
scene.render.filepath = os.path.join(OUT_DIR, "qa_touge_lineup.png")
bpy.ops.render.render(write_still=True)
print("Rendered QA previews successfully!")

