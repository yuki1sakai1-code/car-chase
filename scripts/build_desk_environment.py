import os
import math
import time
import bpy
import bmesh
from mathutils import Vector, Euler, Matrix

TEX_DIR = r"c:\Users\yukis\Downloads\car-chase\assets\textures"
MODEL_DIR = r"c:\Users\yukis\Downloads\car-chase\assets\models"
os.makedirs(MODEL_DIR, exist_ok=True)
OUT_GLB = os.path.join(MODEL_DIR, "desk_environment.glb")

# Clear existing objects, meshes, materials
bpy.ops.wm.read_factory_settings(use_empty=True)

# ---------------------------------------------------------
# Helper Functions for Materials & Geometry
# ---------------------------------------------------------
def load_image(filename, is_data=False):
    path = os.path.join(TEX_DIR, filename)
    img = bpy.data.images.load(path, check_existing=True)
    img.colorspace_settings.name = 'Non-Color' if is_data else 'sRGB'
    return img

def create_textured_pbr_mat(name, albedo_file, normal_file=None, rough_file=None, emissive_file=None,
                            uv_scale=(1.0, 1.0), metallic=0.0, rough_val=0.6, normal_strength=1.0,
                            emissive_strength=1.0):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    out = nodes.new('ShaderNodeOutputMaterial')
    out.location = (600, 0)

    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (250, 0)
    bsdf.inputs['Metallic'].default_value = metallic
    bsdf.inputs['Roughness'].default_value = rough_val
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])

    tex_coord = nodes.new('ShaderNodeTexCoord')
    tex_coord.location = (-700, 0)
    mapping = nodes.new('ShaderNodeMapping')
    mapping.location = (-500, 0)
    mapping.inputs['Scale'].default_value = (uv_scale[0], uv_scale[1], 1.0)
    links.new(tex_coord.outputs['UV'], mapping.inputs['Vector'])

    if albedo_file:
        tex_alb = nodes.new('ShaderNodeTexImage')
        tex_alb.location = (-200, 250)
        tex_alb.image = load_image(albedo_file, is_data=False)
        links.new(mapping.outputs['Vector'], tex_alb.inputs['Vector'])
        links.new(tex_alb.outputs['Color'], bsdf.inputs['Base Color'])

    if rough_file:
        tex_rgh = nodes.new('ShaderNodeTexImage')
        tex_rgh.location = (-200, -20)
        tex_rgh.image = load_image(rough_file, is_data=True)
        links.new(mapping.outputs['Vector'], tex_rgh.inputs['Vector'])
        links.new(tex_rgh.outputs['Color'], bsdf.inputs['Roughness'])

    if normal_file:
        tex_nrm = nodes.new('ShaderNodeTexImage')
        tex_nrm.location = (-250, -300)
        tex_nrm.image = load_image(normal_file, is_data=True)
        nrm_node = nodes.new('ShaderNodeNormalMap')
        nrm_node.location = (20, -300)
        nrm_node.inputs['Strength'].default_value = normal_strength
        links.new(mapping.outputs['Vector'], tex_nrm.inputs['Vector'])
        links.new(tex_nrm.outputs['Color'], nrm_node.inputs['Color'])
        links.new(nrm_node.outputs['Normal'], bsdf.inputs['Normal'])

    if emissive_file:
        tex_emi = nodes.new('ShaderNodeTexImage')
        tex_emi.location = (-200, -550)
        tex_emi.image = load_image(emissive_file, is_data=False)
        links.new(mapping.outputs['Vector'], tex_emi.inputs['Vector'])
        links.new(tex_emi.outputs['Color'], bsdf.inputs['Emission Color'])
        bsdf.inputs['Emission Strength'].default_value = emissive_strength

    return mat

def create_solid_pbr_mat(name, color=(0.5, 0.5, 0.5, 1.0), metallic=0.0, roughness=0.5,
                         emissive_color=None, emissive_strength=0.0):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    bsdf.inputs['Base Color'].default_value = color
    bsdf.inputs['Metallic'].default_value = metallic
    bsdf.inputs['Roughness'].default_value = roughness
    if emissive_color is not None and emissive_strength > 0.0:
        bsdf.inputs['Emission Color'].default_value = emissive_color
        bsdf.inputs['Emission Strength'].default_value = emissive_strength
    return mat

def hex_to_rgba(hex_str, alpha=1.0):
    h = hex_str.lstrip('#')
    r = int(h[0:2], 16) / 255.0
    g = int(h[2:4], 16) / 255.0
    b = int(h[4:6], 16) / 255.0
    # sRGB to linear approximation for Blender shader input
    return (pow(r, 2.2), pow(g, 2.2), pow(b, 2.2), alpha)

def assign_mat(obj, mat):
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)

def add_beveled_box(name, size, location, rotation=(0, 0, 0), bevel_width=0.08, segments=2, mat=None, uv_scale=None):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location, rotation=rotation)
    obj = bpy.context.active_object
    obj.name = name
    obj.data.name = name
    obj.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel_width > 0:
        mod = obj.modifiers.new(name="Bevel", type='BEVEL')
        mod.width = bevel_width
        mod.segments = segments
        mod.limit_method = 'ANGLE'
        bpy.ops.object.modifier_apply(modifier=mod.name)
    if segments >= 2:
        bpy.ops.object.shade_smooth()
        # Weighted normal or auto smooth via edge split / shade auto smooth
    if uv_scale is not None:
        # Scale UVs inside mesh
        me = obj.data
        if me.uv_layers.active:
            uv_layer = me.uv_layers.active.data
            for poly in me.polygons:
                n = poly.normal
                for loop_idx in poly.loop_indices:
                    co = me.vertices[me.loops[loop_idx].vertex_index].co
                    # Box projection based on dominant normal axis
                    if abs(n.z) > 0.5:
                        u = (co.x / size[0] + 0.5) * uv_scale[0]
                        v = (co.y / size[1] + 0.5) * uv_scale[1]
                    elif abs(n.y) > 0.5:
                        u = (co.x / size[0] + 0.5) * uv_scale[0]
                        v = (co.z / size[2] + 0.5) * uv_scale[1]
                    else:
                        u = (co.y / size[1] + 0.5) * uv_scale[0]
                        v = (co.z / size[2] + 0.5) * uv_scale[1]
                    uv_layer[loop_idx].uv = (u, v)
    if mat:
        assign_mat(obj, mat)
    return obj

def add_cylinder(name, radius, depth, location, rotation=(0, 0, 0), vertices=32, mat=None):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=location, rotation=rotation)
    obj = bpy.context.active_object
    obj.name = name
    obj.data.name = name
    if mat:
        assign_mat(obj, mat)
    return obj

# ---------------------------------------------------------
# Create PBR Materials
# ---------------------------------------------------------
print("Creating PBR Materials...")
mat_desk_wood = create_textured_pbr_mat(
    "Mat_DeskWood_2K",
    albedo_file="desk_wood_albedo_2k.png",
    normal_file="desk_wood_normal_2k.png",
    rough_file="desk_wood_roughness_2k.png",
    uv_scale=(1.0, 1.0),
    metallic=0.04,
    normal_strength=1.2
)

mat_mousepad = create_textured_pbr_mat(
    "Mat_Mousepad_2K",
    albedo_file="mousepad_fabric_albedo_2k.png",
    normal_file="mousepad_fabric_normal_2k.png",
    rough_file="mousepad_fabric_roughness_2k.png",
    uv_scale=(1.0, 1.0),
    metallic=0.02,
    normal_strength=1.1
)

mat_keyboard_top = create_textured_pbr_mat(
    "Mat_KeyboardTop_2K",
    albedo_file="keyboard_top_albedo_2k.png",
    emissive_file="keyboard_top_emissive_2k.png",
    uv_scale=(1.0, 1.0),
    metallic=0.25,
    rough_val=0.38,
    emissive_strength=2.8
)

mat_cyan_led = create_solid_pbr_mat(
    "Mat_CyanLED",
    color=hex_to_rgba("#00f5ff"),
    metallic=0.0,
    roughness=0.15,
    emissive_color=hex_to_rgba("#00f5ff"),
    emissive_strength=4.5
)

mat_magenta_led = create_solid_pbr_mat(
    "Mat_MagentaLED",
    color=hex_to_rgba("#ff2a85"),
    metallic=0.0,
    roughness=0.2,
    emissive_color=hex_to_rgba("#ff2a85"),
    emissive_strength=3.5
)

mat_warm_lamp = create_solid_pbr_mat(
    "Mat_WarmLampGlow",
    color=hex_to_rgba("#ffbe66"),
    metallic=0.0,
    roughness=0.2,
    emissive_color=hex_to_rgba("#ffaa44"),
    emissive_strength=5.5
)

mat_edison_filament = create_solid_pbr_mat(
    "Mat_EdisonFilament",
    color=hex_to_rgba("#ffd280"),
    metallic=0.0,
    roughness=0.1,
    emissive_color=hex_to_rgba("#ff9922"),
    emissive_strength=8.0
)

mat_edison_glass = create_solid_pbr_mat(
    "Mat_EdisonAmberGlass",
    color=hex_to_rgba("#ffae42", 0.35),
    metallic=0.1,
    roughness=0.12,
    emissive_color=hex_to_rgba("#ff9b30"),
    emissive_strength=1.8
)

mat_dark_metal = create_solid_pbr_mat(
    "Mat_DarkAnodizedMetal",
    color=hex_to_rgba("#181a22"),
    metallic=0.82,
    roughness=0.32
)

mat_gunmetal = create_solid_pbr_mat(
    "Mat_Gunmetal",
    color=hex_to_rgba("#2a2e3b"),
    metallic=0.88,
    roughness=0.26
)

mat_brass = create_solid_pbr_mat(
    "Mat_BrushedBrass",
    color=hex_to_rgba("#c89d54"),
    metallic=0.90,
    roughness=0.28
)

mat_keycap_dark = create_textured_pbr_mat(
    "Mat_KeycapDarkPBT",
    albedo_file="keyboard_top_albedo_2k.png",
    emissive_file="keyboard_top_emissive_2k.png",
    uv_scale=(1.0, 1.0),
    metallic=0.15,
    rough_val=0.32,
    emissive_strength=3.2
)

mat_keycap_wasd = create_solid_pbr_mat(
    "Mat_KeycapWASD",
    color=hex_to_rgba("#00b8d4"),
    metallic=0.15,
    roughness=0.35,
    emissive_color=hex_to_rgba("#00e5ff"),
    emissive_strength=1.2
)

mat_keycap_esc = create_solid_pbr_mat(
    "Mat_KeycapESC",
    color=hex_to_rgba("#ff5522"),
    metallic=0.15,
    roughness=0.35,
    emissive_color=hex_to_rgba("#ff4411"),
    emissive_strength=1.4
)

mat_monitor_screen = create_solid_pbr_mat(
    "Mat_MonitorScreen",
    color=hex_to_rgba("#0f172a"),
    metallic=0.15,
    roughness=0.12,
    emissive_color=hex_to_rgba("#1b2a4a"),
    emissive_strength=0.9
)

mat_wall_terracotta = create_solid_pbr_mat(
    "Mat_WallTerracotta",
    color=hex_to_rgba("#c86b28"),
    metallic=0.0,
    roughness=0.78,
    emissive_color=hex_to_rgba("#d97426"),
    emissive_strength=0.42
)

mat_wall_trim = create_solid_pbr_mat(
    "Mat_WallTrimDarkWood",
    color=hex_to_rgba("#381f14"),
    metallic=0.05,
    roughness=0.58
)

mat_door_wood = create_solid_pbr_mat(
    "Mat_DoorPanelWood",
    color=hex_to_rgba("#6e3b26"),
    metallic=0.05,
    roughness=0.55,
    emissive_color=hex_to_rgba("#5c2e1c"),
    emissive_strength=0.22
)

mat_sofa_fabric = create_solid_pbr_mat(
    "Mat_SofaFabric",
    color=hex_to_rgba("#6e5c5b"),
    metallic=0.0,
    roughness=0.82,
    emissive_color=hex_to_rgba("#524240"),
    emissive_strength=0.18
)

mat_plant_pot = create_solid_pbr_mat(
    "Mat_CeramicPot",
    color=hex_to_rgba("#d8cfc4"),
    metallic=0.05,
    roughness=0.42
)

mat_plant_leaf = create_solid_pbr_mat(
    "Mat_PlantFoliage",
    color=hex_to_rgba("#2d6a3e"),
    metallic=0.02,
    roughness=0.55
)

mat_mug_ceramic = create_solid_pbr_mat(
    "Mat_CoffeeMugCeramic",
    color=hex_to_rgba("#e8ded1"),
    metallic=0.08,
    roughness=0.22
)

mat_coffee_liquid = create_solid_pbr_mat(
    "Mat_CoffeeLiquid",
    color=hex_to_rgba("#1f0f07"),
    metallic=0.05,
    roughness=0.08
)

mat_book_red = create_solid_pbr_mat("Mat_BookCoverRed", color=hex_to_rgba("#8c2d2d"), roughness=0.65)
mat_book_blue = create_solid_pbr_mat("Mat_BookCoverBlue", color=hex_to_rgba("#1f4068"), roughness=0.60)
mat_book_gold = create_solid_pbr_mat("Mat_BookCoverAmber", color=hex_to_rgba("#b87333"), roughness=0.55)
mat_paper_pages = create_solid_pbr_mat("Mat_PaperPages", color=hex_to_rgba("#f2eadc"), roughness=0.80)
mat_sticky_note = create_solid_pbr_mat(
    "Mat_StickyNoteYellow",
    color=hex_to_rgba("#ffd966"),
    roughness=0.75,
    emissive_color=hex_to_rgba("#ffaa33"),
    emissive_strength=0.25
)

# ---------------------------------------------------------
# 1. Giant Wooden Desk
# Top surface at Z_blender = 0 (Y_three = 0)
# Spanning X from -140 to +140 (width 280), Y_blender from -105 to +105 (depth 210), thickness 5
# ---------------------------------------------------------
print("Building Giant Wooden Desk...")
desk_top = add_beveled_box(
    "Desk_Surface_Top",
    size=(280.0, 210.0, 5.0),
    location=(0.0, 0.0, -2.5),
    bevel_width=0.45,
    segments=3,
    mat=mat_desk_wood,
    uv_scale=(2.0, 1.5)
)

# Sturdy industrial metallic desk frame & legs extending down
leg_positions = [
    (-128.0, -92.0),
    (128.0, -92.0),
    (-128.0, 92.0),
    (128.0, 92.0),
]
for idx, (lx, ly) in enumerate(leg_positions):
    add_beveled_box(
        f"Desk_Leg_{idx+1}",
        size=(6.5, 6.5, 95.0),
        location=(lx, ly, -52.5),
        bevel_width=0.3,
        segments=2,
        mat=mat_dark_metal
    )
# Under-desk steel apron crossbars
add_beveled_box("Desk_Apron_Front", size=(262.0, 4.0, 4.5), location=(0.0, -92.0, -7.2), bevel_width=0.2, mat=mat_dark_metal)
add_beveled_box("Desk_Apron_Back", size=(262.0, 4.0, 4.5), location=(0.0, 92.0, -7.2), bevel_width=0.2, mat=mat_dark_metal)

# ---------------------------------------------------------
# 2. Giant Purple RGB Gaming Desk Mat / Mousepad
# Resting on desk (Z_blender = 0.0 to 0.35)
# Spanning X from -108 to +108 (width = 216), Y_blender from -75 to +68 (depth = 143)
# Center at X = 0, Y_blender = (-75 + 68)/2 = -3.5, Z_blender = 0.175
# ---------------------------------------------------------
print("Building Giant Purple RGB Gaming Desk Mat...")
pad_w = 216.0
pad_d = 143.0
pad_h = 0.35
pad_cx = 0.0
pad_cy = -3.5
pad_cz = pad_h * 0.5

mousepad = add_beveled_box(
    "Gaming_Mousepad_Surface",
    size=(pad_w, pad_d, pad_h),
    location=(pad_cx, pad_cy, pad_cz),
    bevel_width=0.10,
    segments=2,
    mat=mat_mousepad,
    uv_scale=(1.0, 1.0)
)

# Bright glowing cyan (#00f5ff) emissive LED tube border around perimeter
tube_r = 0.28
tube_z = 0.22
# Front & Back LED tubes along X
add_cylinder(
    "Mousepad_RGB_Edge_Front",
    radius=tube_r, depth=pad_w + 0.4,
    location=(pad_cx, pad_cy - pad_d * 0.5, tube_z),
    rotation=(0, math.pi * 0.5, 0),
    vertices=16, mat=mat_cyan_led
)
add_cylinder(
    "Mousepad_RGB_Edge_Back",
    radius=tube_r, depth=pad_w + 0.4,
    location=(pad_cx, pad_cy + pad_d * 0.5, tube_z),
    rotation=(0, math.pi * 0.5, 0),
    vertices=16, mat=mat_cyan_led
)
# Left & Right LED tubes along Y
add_cylinder(
    "Mousepad_RGB_Edge_Left",
    radius=tube_r, depth=pad_d + 0.4,
    location=(pad_cx - pad_w * 0.5, pad_cy, tube_z),
    rotation=(math.pi * 0.5, 0, 0),
    vertices=16, mat=mat_cyan_led
)
add_cylinder(
    "Mousepad_RGB_Edge_Right",
    radius=tube_r, depth=pad_d + 0.4,
    location=(pad_cx + pad_w * 0.5, pad_cy, tube_z),
    rotation=(math.pi * 0.5, 0, 0),
    vertices=16, mat=mat_cyan_led
)
# RGB power controller clip on top-left edge of mousepad
add_beveled_box(
    "Mousepad_RGB_ControllerBox",
    size=(4.5, 2.8, 0.85),
    location=(pad_cx - pad_w * 0.5 + 8.0, pad_cy + pad_d * 0.5, 0.42),
    bevel_width=0.12, mat=mat_dark_metal
)

# ---------------------------------------------------------
# 3. Giant RGB Backlit Mechanical Gaming Keyboard
# Positioned in center of desk around X_blender = -6, Y_blender = 12 (Z_three = -12), Z_blender = 0.35
# Angled slightly (10 deg), size ~58 x 22 x 3.2
# ---------------------------------------------------------
print("Building Giant RGB Mechanical Gaming Keyboard with 3D Sculpted Keycaps...")
kb_cx, kb_cy, kb_cz = -6.0, 12.0, 0.35
kb_w, kb_d, kb_h = 58.0, 22.0, 2.2
kb_yaw = math.radians(10.0)
kb_tilt = math.radians(4.5) # Slight ergonomic typing tilt toward front

kb_parts = []

# Matte-black anodized aluminum keyboard chassis
kb_chassis = add_beveled_box(
    "Keyboard_Chassis_Base",
    size=(kb_w, kb_d, kb_h),
    location=(0.0, 0.0, kb_h * 0.5),
    bevel_width=0.35,
    segments=3,
    mat=mat_dark_metal
)
kb_parts.append(kb_chassis)

# Glowing cyan LED underglow diffuser plate & side lightbars
kb_underglow = add_beveled_box(
    "Keyboard_Cyan_SwitchPlate",
    size=(kb_w - 2.4, kb_d - 2.4, 0.25),
    location=(0.0, 0.0, kb_h + 0.05),
    bevel_width=0.05,
    segments=1,
    mat=mat_keyboard_top,
    uv_scale=(1.0, 1.0)
)
kb_parts.append(kb_underglow)

# Glowing cyan perimeter underglow strip around keyboard base
kb_side_glow = add_beveled_box(
    "Keyboard_Underglow_Ring",
    size=(kb_w + 0.3, kb_d + 0.3, 0.32),
    location=(0.0, 0.0, 0.28),
    bevel_width=0.08,
    segments=1,
    mat=mat_cyan_led
)
kb_parts.append(kb_side_glow)

# Build 3D sculpted rows of keycaps in a single BMesh for optimal performance & crisp silhouette
bm_keys_dark = bmesh.new()
bm_keys_wasd = bmesh.new()
bm_keys_esc = bmesh.new()
bm_keys_glow = bmesh.new()

def add_sculpted_keycap_to_bm(bm_cap, bm_glow_collar, x, y, z, w, d, h):
    # Glowing cyan translucent stem/pudding-keycap skirt clearly visible around every keycap
    bmesh.ops.create_cube(
        bm_glow_collar,
        size=1.0,
        matrix=Matrix.Translation((x, y, z + 0.34)) @ Matrix.Diagonal((w * 1.02, d * 1.02, 0.58, 1.0))
    )
    # Tapered keycap frustum (sits atop the glowing cyan pudding skirt)
    hw_b, hd_b = w * 0.44, d * 0.44
    hw_t, hd_t = w * 0.36, d * 0.35
    z0 = z + 0.52
    z1 = z + 0.38 + h
    v0 = bm_cap.verts.new((x - hw_b, y - hd_b, z0))
    v1 = bm_cap.verts.new((x + hw_b, y - hd_b, z0))
    v2 = bm_cap.verts.new((x + hw_b, y + hd_b, z0))
    v3 = bm_cap.verts.new((x - hw_b, y + hd_b, z0))
    v4 = bm_cap.verts.new((x - hw_t, y - hd_t, z1))
    v5 = bm_cap.verts.new((x + hw_t, y - hd_t, z1))
    v6 = bm_cap.verts.new((x + hw_t, y + hd_t, z1))
    v7 = bm_cap.verts.new((x - hw_t, y + hd_t, z1))
    bm_cap.faces.new((v0, v3, v2, v1)) # bottom
    f_top = bm_cap.faces.new((v4, v5, v6, v7)) # top
    bm_cap.faces.new((v0, v1, v5, v4)) # front
    bm_cap.faces.new((v1, v2, v6, v5)) # right
    bm_cap.faces.new((v2, v3, v7, v6)) # back
    bm_cap.faces.new((v3, v0, v4, v7)) # left
    # Also add a thin glowing cyan rim frame on top of each keycap so legends/borders pop from every angle
    bmesh.ops.create_cube(
        bm_glow_collar,
        size=1.0,
        matrix=Matrix.Translation((x, y, z1 - 0.02)) @ Matrix.Diagonal((hw_t * 2.02, hd_t * 2.02, 0.06, 1.0))
    )
    bmesh.ops.create_cube(
        bm_cap,
        size=1.0,
        matrix=Matrix.Translation((x, y, z1 + 0.01)) @ Matrix.Diagonal((hw_t * 1.68, hd_t * 1.68, 0.05, 1.0))
    )

row_configs = [
    # (y_offset, row_height, key_unit_widths)
    (-7.8, 0.95, [1.25, 1.25, 1.25, 6.25, 1.25, 1.25, 1.25, 1.25, 0.4, 1.0, 1.0, 1.0, 0.4, 2.0, 1.0]), # Bottom row + Spacebar + Arrows + Numpad 0
    (-4.7, 0.90, [2.25, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2.75, 0.4, 0.0, 1.0, 0.0, 0.4, 1.0, 1.0, 1.0]),  # Shift row + Up arrow + Numpad 1-3
    (-1.6, 0.88, [1.75, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2.25, 0.4, 1.0, 1.0, 1.0, 0.4, 1.0, 1.0, 1.0]), # Caps + ASDF (WASD!)
    (1.5,  0.92, [1.5, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1.5, 0.4, 1.0, 1.0, 1.0, 0.4, 1.0, 1.0, 1.0]), # Tab + QWERTY (W!)
    (4.6,  0.98, [1.0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2.0, 0.4, 1.0, 1.0, 1.0, 0.4, 1.0, 1.0, 1.0]), # Number row
    (7.8,  1.05, [1.1, 0.6, 1, 1, 1, 1, 0.45, 1, 1, 1, 1, 0.45, 1, 1, 1, 1, 0.4, 1.0, 1.0, 1.0, 0.4, 3.0]), # ESC + F1-F12 + Volume roller gap
]

x_span = 53.6
x_left = -x_span * 0.5
key_d = 2.65

for r_i, (ry, kh, units) in enumerate(row_configs):
    tot_u = sum(u if u > 0 else 1.0 for u in units)
    cur_x = x_left
    for k_i, u_w in enumerate(units):
        actual_u = u_w if u_w > 0 else 1.0
        kw = (actual_u / tot_u) * x_span
        cx = cur_x + kw * 0.5
        cur_x += kw
        # Skip spacer gaps (u_w in (0.0, 0.4, 0.45, 0.6) or volume roller slot)
        if u_w in (0.0, 0.4, 0.45, 0.6) or (r_i == 5 and k_i == len(units) - 1):
            continue
        is_esc = (r_i == 5 and k_i == 0)
        is_wasd = (r_i == 2 and k_i in (1, 2, 3)) or (r_i == 3 and k_i == 2)
        target_bm = bm_keys_esc if is_esc else (bm_keys_wasd if is_wasd else bm_keys_dark)
        add_sculpted_keycap_to_bm(target_bm, bm_keys_glow, cx, ry, kb_h, kw - 0.28, key_d, kh)

def bm_to_obj(bm, name, mat):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    assign_mat(obj, mat)
    return obj

kb_parts.append(bm_to_obj(bm_keys_dark, "Keyboard_Keycaps_Main", mat_keycap_dark))
kb_parts.append(bm_to_obj(bm_keys_wasd, "Keyboard_Keycaps_WASD", mat_keycap_wasd))
kb_parts.append(bm_to_obj(bm_keys_esc, "Keyboard_Keycap_ESC", mat_keycap_esc))
kb_parts.append(bm_to_obj(bm_keys_glow, "Keyboard_Keycaps_BacklightCollars", mat_cyan_led))

# Knurled aluminum volume roller on top-right of keyboard
vol_roller = add_cylinder(
    "Keyboard_Volume_Roller",
    radius=0.85, depth=4.8,
    location=(x_span * 0.5 - 2.8, 7.8, kb_h + 0.55),
    rotation=(0, math.pi * 0.5, 0),
    vertices=20, mat=mat_gunmetal
)
kb_parts.append(vol_roller)

# Group and transform all keyboard parts to (kb_cx, kb_cy, kb_cz) with 10 deg yaw and ergonomic tilt
# Seated on a sleek pink/cyan-lit desk riser mat on the desk surface (Z_bl = 0.35, well below elevated track Y >= 4.2)
kb_riser_pad = add_beveled_box(
    "Keyboard_Desk_Riser_Mat",
    size=(78.0, 38.0, 0.35),
    location=(8.0, 16.0, 0.35),
    rotation=(0, 0, kb_yaw),
    bevel_width=0.12,
    segments=2,
    mat=create_solid_pbr_mat(
        "Mat_PinkDeskPad",
        color=hex_to_rgba("#9c5878"),
        roughness=0.65,
        emissive_color=hex_to_rgba("#ff85a2"),
        emissive_strength=0.35
    )
)
kb_riser_edge = add_beveled_box(
    "Keyboard_Desk_Riser_CyanEdge",
    size=(78.5, 38.5, 0.18),
    location=(8.0, 16.0, 0.48),
    rotation=(0, 0, kb_yaw),
    bevel_width=0.06,
    segments=1,
    mat=mat_cyan_led
)

kb_mat = Matrix.Translation((8.0, 16.0, 0.52)) @ Euler((kb_tilt, 0.0, kb_yaw), 'XYZ').to_matrix().to_4x4() @ Matrix.Diagonal((1.08, 1.08, 0.52, 1.0))
for p in kb_parts:
    # Also duplicate a second RGB keyboard right alongside the Start/Finish straight (outside right curb at Y_bl = -73.0)
    # with low profile Z so the FINISH modal (Screenshot 2) looks down across glowing cyan RGB keycaps on the right!
    p_copy = p.copy()
    p_copy.data = p.data.copy()
    bpy.context.collection.objects.link(p_copy)
    kb2_mat = Matrix.Translation((20.0, -73.5, 0.35)) @ Euler((math.radians(6.0), 0.0, math.radians(1.5)), 'XYZ').to_matrix().to_4x4() @ Matrix.Diagonal((1.05, 1.05, 0.55, 1.0))
    p_copy.matrix_world = kb2_mat @ p.matrix_world

    p.matrix_world = kb_mat @ p.matrix_world

# Braided USB-C keyboard cable snaking from back of keyboard toward monitor
bpy.ops.curve.primitive_bezier_curve_add(location=(0, 0, 0))
cable_obj = bpy.context.active_object
cable_obj.name = "Keyboard_Coiled_Cable"
cable_obj.data.bevel_depth = 0.32
cable_obj.data.bevel_resolution = 4
sp = cable_obj.data.splines[0]
sp.bezier_points[0].co = (kb_cx - 2.0, kb_cy + 11.2, 0.65)
sp.bezier_points[0].handle_right = (kb_cx - 4.0, kb_cy + 24.0, 0.65)
sp.bezier_points[1].co = (28.0, 56.0, 0.65)
sp.bezier_points[1].handle_left = (10.0, 38.0, 0.65)
assign_mat(cable_obj, mat_dark_metal)
bpy.ops.object.convert(target='MESH')

# ---------------------------------------------------------
# 4. Wireless Gaming Mouse
# Positioned to the right of the keyboard (X_blender = 36, Y_blender = 10 / Z_three = -10)
# Ergonomic shape with glowing cyan scroll wheel & RGB tail strip
# ---------------------------------------------------------
print("Building Wireless Gaming Mouse...")
mx, my, mz = 36.0, 10.0, 0.35
mouse_yaw = math.radians(-8.0)

# Sculpted ergonomic mouse shell
bpy.ops.mesh.primitive_uv_sphere_add(segments=28, ring_count=16, radius=1.0, location=(0, 0, 0))
mouse_body = bpy.context.active_object
mouse_body.name = "Gaming_Mouse_Body"
mouse_body.scale = (3.4, 5.8, 2.35)
bpy.ops.object.transform_apply(scale=True)
# Flatten bottom of mouse shell (z < 0)
for v in mouse_body.data.vertices:
    if v.co.z < 0.0:
        v.co.z = 0.0
    else:
        # Taper front and hump slightly toward back
        if v.co.y < 0:
            v.co.z *= 1.08
bpy.ops.object.shade_smooth()
assign_mat(mouse_body, mat_dark_metal)

# Glowing cyan RGB tail strip around mouse base
bpy.ops.mesh.primitive_cylinder_add(vertices=28, radius=1.0, depth=0.35, location=(0, -0.2, 0.22))
mouse_rgb = bpy.context.active_object
mouse_rgb.name = "Gaming_Mouse_RGB_Tail"
mouse_rgb.scale = (3.38, 5.75, 1.0)
bpy.ops.object.transform_apply(scale=True)
assign_mat(mouse_rgb, mat_cyan_led)

# Glowing cyan scroll wheel
mouse_wheel = add_cylinder(
    "Gaming_Mouse_ScrollWheel",
    radius=0.65, depth=0.45,
    location=(0.0, 2.4, 2.05),
    rotation=(0, math.pi * 0.5, 0),
    vertices=20, mat=mat_cyan_led
)

# DPI button
mouse_dpi = add_beveled_box(
    "Gaming_Mouse_DPI_Button",
    size=(0.55, 0.9, 0.35),
    location=(0.0, 0.9, 2.28),
    bevel_width=0.05, mat=mat_gunmetal
)

mouse_mat = Matrix.Translation((mx, my, mz)) @ Euler((0, 0, mouse_yaw), 'XYZ').to_matrix().to_4x4()
for mp in (mouse_body, mouse_rgb, mouse_wheel, mouse_dpi):
    mp.matrix_world = mouse_mat @ mp.matrix_world

# ---------------------------------------------------------
# 5. Ultrawide Curved Gaming Monitor
# Positioned near back-right/center of desk (X_blender = 38, Y_blender = 58 / Z_three = -58, Z_blender = 0.35)
# Heavy V-shaped metallic stand, sleek bezel, subtle ambient screen wallpaper glow, rear RGB ring
# ---------------------------------------------------------
print("Building Ultrawide Curved Gaming Monitor...")
mon_x, mon_y, mon_z = 38.0, 58.0, 0.35
mon_yaw = math.radians(-14.0) # Angled slightly toward center of desk

mon_parts = []

# Heavy V-shaped metallic stand legs
v_leg_l = add_beveled_box(
    "Monitor_Stand_Leg_L",
    size=(24.0, 3.2, 1.2),
    location=(-10.5, -4.5, 0.6),
    rotation=(0, 0, math.radians(26.0)),
    bevel_width=0.25, mat=mat_gunmetal
)
v_leg_r = add_beveled_box(
    "Monitor_Stand_Leg_R",
    size=(24.0, 3.2, 1.2),
    location=(10.5, -4.5, 0.6),
    rotation=(0, 0, math.radians(-26.0)),
    bevel_width=0.25, mat=mat_gunmetal
)
# Cyan accent strips on V-stand legs
v_acc_l = add_beveled_box(
    "Monitor_Stand_Accent_L",
    size=(20.0, 0.4, 0.3),
    location=(-10.5, -4.5, 1.25),
    rotation=(0, 0, math.radians(26.0)),
    bevel_width=0.04, mat=mat_cyan_led
)
v_acc_r = add_beveled_box(
    "Monitor_Stand_Accent_R",
    size=(20.0, 0.4, 0.3),
    location=(10.5, -4.5, 1.25),
    rotation=(0, 0, math.radians(-26.0)),
    bevel_width=0.04, mat=mat_cyan_led
)
# Vertical pillar column & arm
mon_pillar = add_beveled_box(
    "Monitor_Stand_Pillar",
    size=(4.8, 4.2, 34.0),
    location=(0.0, 2.5, 17.0),
    rotation=(math.radians(-6.0), 0, 0),
    bevel_width=0.4, mat=mat_gunmetal
)
mon_parts.extend([v_leg_l, v_leg_r, v_acc_l, v_acc_r, mon_pillar])

# Curved Ultrawide Monitor Panel (built across 18 arc segments for authentic 1800R curvature)
panel_w = 82.0
panel_h = 34.0
panel_z_center = 29.5
curve_radius = 115.0
segs = 18

bm_bezel = bmesh.new()
bm_screen = bmesh.new()

half_angle = (panel_w / curve_radius) * 0.5
angles = [-half_angle + (2.0 * half_angle * i / segs) for i in range(segs + 1)]

for i in range(segs):
    a0, a1 = angles[i], angles[i + 1]
    x0 = curve_radius * math.sin(a0)
    y0 = curve_radius * (1.0 - math.cos(a0)) - 3.5
    x1 = curve_radius * math.sin(a1)
    y1 = curve_radius * (1.0 - math.cos(a1)) - 3.5

    # Outer bezel box segment (thickness 2.2 in Y)
    z_bot = panel_z_center - panel_h * 0.5
    z_top = panel_z_center + panel_h * 0.5
    v_b0 = bm_bezel.verts.new((x0, y0, z_bot))
    v_b1 = bm_bezel.verts.new((x1, y1, z_bot))
    v_b2 = bm_bezel.verts.new((x1, y1 + 2.4, z_bot))
    v_b3 = bm_bezel.verts.new((x0, y0 + 2.4, z_bot))
    v_t0 = bm_bezel.verts.new((x0, y0, z_top))
    v_t1 = bm_bezel.verts.new((x1, y1, z_top))
    v_t2 = bm_bezel.verts.new((x1, y1 + 2.4, z_top))
    v_t3 = bm_bezel.verts.new((x0, y0 + 2.4, z_top))
    bm_bezel.faces.new((v_b0, v_b3, v_b2, v_b1))
    bm_bezel.faces.new((v_t0, v_t1, v_t2, v_t3))
    bm_bezel.faces.new((v_b0, v_b1, v_t1, v_t0))
    bm_bezel.faces.new((v_b2, v_b3, v_t3, v_t2))
    if i == 0:
        bm_bezel.faces.new((v_b3, v_b0, v_t0, v_t3))
    if i == segs - 1:
        bm_bezel.faces.new((v_b1, v_b2, v_t2, v_t1))

    # Glowing curved display screen surface slightly proud of front face
    s_bot = z_bot + 1.1
    s_top = z_top - 0.8
    sv0 = bm_screen.verts.new((x0 * 0.985, y0 - 0.12, s_bot))
    sv1 = bm_screen.verts.new((x1 * 0.985, y1 - 0.12, s_bot))
    sv2 = bm_screen.verts.new((x1 * 0.985, y1 - 0.12, s_top))
    sv3 = bm_screen.verts.new((x0 * 0.985, y0 - 0.12, s_top))
    bm_screen.faces.new((sv0, sv1, sv2, sv3))

mon_parts.append(bm_to_obj(bm_bezel, "Monitor_Curved_Chassis", mat_dark_metal))
mon_parts.append(bm_to_obj(bm_screen, "Monitor_Curved_Display", mat_monitor_screen))

# Rear RGB core ring & bottom status LED bar on monitor
bpy.ops.mesh.primitive_torus_add(
    major_radius=7.5, minor_radius=0.45,
    location=(0.0, 2.5, panel_z_center),
    rotation=(math.pi * 0.5, 0, 0)
)
mon_ring = bpy.context.active_object
mon_ring.name = "Monitor_Rear_RGB_Ring"
assign_mat(mon_ring, mat_cyan_led)
mon_parts.append(mon_ring)

mon_bottom_led = add_beveled_box(
    "Monitor_UnderGlow_Strip",
    size=(32.0, 0.5, 0.3),
    location=(0.0, -3.2, panel_z_center - panel_h * 0.5 - 0.15),
    bevel_width=0.05, mat=mat_magenta_led
)
mon_parts.append(mon_bottom_led)

mon_mat = Matrix.Translation((mon_x, mon_y, mon_z)) @ Euler((0, 0, mon_yaw), 'XYZ').to_matrix().to_4x4()
for mp in mon_parts:
    mp.matrix_world = mon_mat @ mp.matrix_world

# ---------------------------------------------------------
# 6. Warm Glowing Cylindrical Column Lamp & Vintage Edison Bulb Lamp
# Positioned on back-right (X_blender = 82, Y_blender = 45 / Z_three = -45)
# Plus small potted plant on a dark credenza/riser (matching Screenshots 1, 3, 5)
# ---------------------------------------------------------
print("Building Warm Glowing Cylindrical Lamp, Vintage Edison Lamp, Credenza Riser & Potted Plant...")

# Dark walnut/metal riser shelf / credenza against the back wall (matching Screenshot 5)
riser_x, riser_y = 24.0, 82.0
riser_w, riser_d, riser_h = 54.0, 22.0, 14.5
add_beveled_box(
    "Desk_Corner_Credenza_Top",
    size=(riser_w, riser_d, 1.4),
    location=(riser_x, riser_y, riser_h),
    rotation=(0, 0, math.radians(-4.0)),
    bevel_width=0.2, mat=mat_dark_metal
)
add_beveled_box(
    "Desk_Corner_Credenza_Base",
    size=(riser_w - 2.0, riser_d - 2.0, riser_h - 0.7),
    location=(riser_x, riser_y, (riser_h - 0.7) * 0.5),
    rotation=(0, 0, math.radians(-4.0)),
    bevel_width=0.2, mat=mat_dark_metal
)

# 6a. Tall Warm Glowing Cylindrical Column Lamp right beside the elevated ramp (matching Screenshot 3)
lamp_x, lamp_y, lamp_z = 66.0, 34.0, 0.35
# Brass/Dark Metal Base
add_cylinder("ColumnLamp_Base_Metal", radius=6.2, depth=2.4, location=(lamp_x, lamp_y, lamp_z + 1.2), vertices=36, mat=mat_dark_metal)
add_cylinder("ColumnLamp_Base_BrassRing", radius=6.4, depth=0.6, location=(lamp_x, lamp_y, lamp_z + 2.4), vertices=36, mat=mat_brass)
# Tall Warm Golden-White Glowing Cylinder Diffuser Column (emission #ffaa44)
lamp_col = add_cylinder(
    "ColumnLamp_Warm_Diffuser",
    radius=5.8, depth=38.0,
    location=(lamp_x, lamp_y, lamp_z + 20.4),
    vertices=40, mat=mat_warm_lamp
)
bpy.ops.object.shade_smooth()
# Top cap ring
add_cylinder("ColumnLamp_Top_Cap", radius=6.0, depth=1.2, location=(lamp_x, lamp_y, lamp_z + 39.8), vertices=36, mat=mat_brass)

# 6b. Vintage Edison Bulb Lamp on the credenza next to the plant (matching Screenshot 5)
ed_x, ed_y, ed_z = 38.0, 78.0, riser_h + 0.7
add_cylinder("EdisonLamp_WoodBase", radius=4.2, depth=2.2, location=(ed_x, ed_y, ed_z + 1.1), vertices=28, mat=mat_dark_metal)
add_cylinder("EdisonLamp_BrassSocket", radius=2.1, depth=3.2, location=(ed_x, ed_y, ed_z + 3.5), vertices=24, mat=mat_brass)
# Vintage toggle switch on brass socket
add_cylinder("EdisonLamp_TurnKnob", radius=0.45, depth=2.4, location=(ed_x + 1.8, ed_y, ed_z + 3.6), rotation=(0, math.pi*0.5, 0), vertices=12, mat=mat_brass)
# Glowing Edison filament core
add_cylinder("EdisonLamp_Filament_Left", radius=0.18, depth=4.2, location=(ed_x - 0.6, ed_y, ed_z + 7.5), vertices=8, mat=mat_edison_filament)
add_cylinder("EdisonLamp_Filament_Right", radius=0.18, depth=4.2, location=(ed_x + 0.6, ed_y, ed_z + 7.5), vertices=8, mat=mat_edison_filament)
add_cylinder("EdisonLamp_Filament_Spiral", radius=0.85, depth=2.6, location=(ed_x, ed_y, ed_z + 8.6), vertices=16, mat=mat_edison_filament)
# Outer warm amber glass bulb
bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=16, radius=3.4, location=(ed_x, ed_y, ed_z + 8.2))
bulb_glass = bpy.context.active_object
bulb_glass.name = "EdisonLamp_GlassBulb"
bulb_glass.scale = (1.0, 1.0, 1.35)
bpy.ops.object.transform_apply(scale=True)
bpy.ops.object.shade_smooth()
assign_mat(bulb_glass, mat_edison_glass)

# 6c. Potted Plant on the credenza/riser (matching Screenshot 5)
pl_x, pl_y, pl_z = 8.0, 79.0, riser_h + 0.7
add_cylinder("PottedPlant_CeramicPot", radius=4.4, depth=7.5, location=(pl_x, pl_y, pl_z + 3.75), vertices=24, mat=mat_plant_pot)
add_cylinder("PottedPlant_Soil", radius=4.1, depth=0.6, location=(pl_x, pl_y, pl_z + 7.3), vertices=24, mat=mat_wall_trim)

# Lush indoor succulent / monstera leaves radiating from the pot
leaf_count = 11
for i in range(leaf_count):
    ang = (2.0 * math.pi * i) / leaf_count + (0.25 if i % 2 else 0.0)
    tilt = math.radians(32.0 + (i % 3) * 14.0)
    dist = 2.2 + (i % 2) * 1.1
    lx = pl_x + math.cos(ang) * dist
    ly = pl_y + math.sin(ang) * dist
    lz = pl_z + 8.5 + (i % 3) * 1.2
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, radius=1.0, location=(lx, ly, lz))
    leaf = bpy.context.active_object
    leaf.name = f"PottedPlant_Leaf_{i+1}"
    leaf.scale = (1.6, 3.8, 0.35)
    leaf.rotation_euler = (tilt, 0.0, ang - math.pi * 0.5)
    bpy.ops.object.transform_apply(scale=True, rotation=False)
    bpy.ops.object.shade_smooth()
    assign_mat(leaf, mat_plant_leaf)

# ---------------------------------------------------------
# 7. Desk Accessories (Outside Racetrack Footprint)
# Ceramic coffee mug, stack of hardcover books/notebooks, pen cup with pens/pencils
# Note: The racetrack runs inside the mousepad (roughly X in [-75, +65], Y in [-55, +45]).
# Place accessories on the outer desk corners / edges outside the racetrack!
# ---------------------------------------------------------
print("Building Desk Accessories (Coffee Mug, Hardcover Books, Pen Cup)...")

# 7a. Ceramic Coffee Mug + Coaster (front-left / mid-left edge of desk, X = -92, Y = 38)
mug_x, mug_y, mug_z = -92.0, 38.0, 0.35
add_cylinder("Desk_Cork_Coaster", radius=4.8, depth=0.35, location=(mug_x, mug_y, mug_z + 0.18), vertices=28, mat=mat_book_gold)
add_cylinder("CoffeeMug_Body", radius=3.8, depth=8.6, location=(mug_x, mug_y, mug_z + 4.5), vertices=32, mat=mat_mug_ceramic)
add_cylinder("CoffeeMug_Liquid", radius=3.45, depth=0.4, location=(mug_x, mug_y, mug_z + 8.65), vertices=28, mat=mat_coffee_liquid)
bpy.ops.mesh.primitive_torus_add(
    major_radius=2.3, minor_radius=0.55,
    location=(mug_x + 3.9, mug_y, mug_z + 4.6),
    rotation=(math.pi * 0.5, 0, 0)
)
mug_handle = bpy.context.active_object
mug_handle.name = "CoffeeMug_Handle"
assign_mat(mug_handle, mat_mug_ceramic)

# 7b. Stack of Hardcover Books & Notebook (back-left desk corner, X = -102, Y = 68)
bk_x, bk_y = -102.0, 68.0
# Bottom Book (Blue Oversized Art Book)
add_beveled_box("Book_Stack_1_Cover", size=(24.0, 18.0, 2.8), location=(bk_x, bk_y, 1.4), rotation=(0, 0, math.radians(15.0)), bevel_width=0.18, mat=mat_book_blue)
add_beveled_box("Book_Stack_1_Pages", size=(23.2, 17.2, 2.3), location=(bk_x + 0.2, bk_y - 0.2, 1.4), rotation=(0, 0, math.radians(15.0)), bevel_width=0.05, mat=mat_paper_pages)
# Middle Book (Crimson Design Hardcover)
add_beveled_box("Book_Stack_2_Cover", size=(21.0, 15.5, 2.4), location=(bk_x + 0.8, bk_y + 0.5, 4.0), rotation=(0, 0, math.radians(6.0)), bevel_width=0.18, mat=mat_book_red)
add_beveled_box("Book_Stack_2_Pages", size=(20.2, 14.8, 1.9), location=(bk_x + 1.0, bk_y + 0.3, 4.0), rotation=(0, 0, math.radians(6.0)), bevel_width=0.05, mat=mat_paper_pages)
# Top Book (Amber Leather Moleskine Notebook)
add_beveled_box("Book_Stack_3_Notebook", size=(17.5, 12.5, 1.6), location=(bk_x - 0.5, bk_y + 0.2, 6.0), rotation=(0, 0, math.radians(22.0)), bevel_width=0.15, mat=mat_book_gold)

# 7c. Pen Cup with Pens & Pencils (back-left near monitor/books, X = -76, Y = 74)
pc_x, pc_y = -76.0, 74.0
add_cylinder("Stationery_PenCup", radius=3.4, depth=8.8, location=(pc_x, pc_y, 4.4), vertices=24, mat=mat_dark_metal)
pen_specs = [
    (-1.1, -0.8, 12.5, (math.radians(10), math.radians(-8), 0), mat_book_red),
    (1.2, -0.6, 13.2, (math.radians(-8), math.radians(11), 0), mat_cyan_led),
    (0.2, 1.3, 11.8, (math.radians(12), math.radians(5), 0), mat_book_gold),
    (-0.9, 1.0, 12.8, (math.radians(-6), math.radians(-10), 0), mat_brass),
]
for idx, (dx, dy, plen, prot, pmat) in enumerate(pen_specs):
    add_cylinder(
        f"Stationery_Pen_{idx+1}",
        radius=0.38, depth=plen,
        location=(pc_x + dx, pc_y + dy, 3.0 + plen * 0.5),
        rotation=prot, vertices=12, mat=pmat
    )

# ---------------------------------------------------------
# 8. Studio Room Backdrop (Walls, Door, Door Handle, Light Switch, Framed Art, Low Sofa/Headboard)
# Back wall at Y_blender = 105 (Z_three = -105)
# Left wall at X_blender = -140
# Painted warm terracotta/amber-lit studio tones
# ---------------------------------------------------------
print("Building Studio Room Walls, Door, Metallic Handle, Light Switch, Framed Art & Low Sofa...")

# Back Wall (Y_blender = 105, spanning X from -142 to +160, Z from -60 to +145)
add_beveled_box(
    "Studio_Back_Wall",
    size=(304.0, 4.0, 205.0),
    location=(9.0, 107.0, 42.5),
    bevel_width=0.1, mat=mat_wall_terracotta
)
# Left Wall (X_blender = -140, spanning Y from -108 to +108, Z from -60 to +145)
add_beveled_box(
    "Studio_Left_Wall",
    size=(4.0, 218.0, 205.0),
    location=(-142.0, 0.0, 42.5),
    bevel_width=0.1, mat=mat_wall_terracotta
)

# Baseboard / Wainscoting trim along walls
add_beveled_box("Studio_Back_Wall_Trim", size=(300.0, 1.2, 8.0), location=(9.0, 104.6, 2.0), bevel_width=0.15, mat=mat_wall_trim)
add_beveled_box("Studio_Left_Wall_Trim", size=(1.2, 214.0, 8.0), location=(-139.6, 0.0, 2.0), bevel_width=0.15, mat=mat_wall_trim)

# Bedroom / Office Door on the back wall (matching Screenshots 1 & 5)
door_x, door_y = -32.0, 104.5
door_w, door_h = 48.0, 118.0
door_cz = 18.0
# Door outer frame casing
add_beveled_box("Studio_Door_Frame_Left", size=(3.8, 2.8, door_h + 4.0), location=(door_x - door_w*0.5 - 1.5, door_y, door_cz), bevel_width=0.2, mat=mat_wall_trim)
add_beveled_box("Studio_Door_Frame_Right", size=(3.8, 2.8, door_h + 4.0), location=(door_x + door_w*0.5 + 1.5, door_y, door_cz), bevel_width=0.2, mat=mat_wall_trim)
add_beveled_box("Studio_Door_Frame_Top", size=(door_w + 10.8, 2.8, 4.2), location=(door_x, door_y, door_cz + door_h*0.5 + 2.0), bevel_width=0.2, mat=mat_wall_trim)
# Main Door Panel
add_beveled_box("Studio_Door_MainPanel", size=(door_w, 1.8, door_h), location=(door_x, door_y + 0.2, door_cz), bevel_width=0.25, mat=mat_door_wood)
# Recessed decorative door molding panels
add_beveled_box("Studio_Door_UpperInset", size=(door_w - 12.0, 2.3, 46.0), location=(door_x, door_y + 0.1, door_cz + 34.0), bevel_width=0.3, mat=mat_desk_wood)
add_beveled_box("Studio_Door_LowerInset", size=(door_w - 12.0, 2.3, 42.0), location=(door_x, door_y + 0.1, door_cz - 24.0), bevel_width=0.3, mat=mat_desk_wood)

# Metallic Lever Door Handle (visible above the desk surface at Z = 22)
handle_x = door_x + door_w * 0.5 - 5.5
handle_z = 22.0
add_cylinder("Studio_Door_Handle_Rosette", radius=2.4, depth=0.8, location=(handle_x, door_y - 0.9, handle_z), rotation=(math.pi*0.5, 0, 0), vertices=24, mat=mat_brass)
add_cylinder("Studio_Door_Handle_Stem", radius=0.85, depth=3.2, location=(handle_x, door_y - 2.2, handle_z), rotation=(math.pi*0.5, 0, 0), vertices=16, mat=mat_brass)
add_beveled_box("Studio_Door_Handle_Lever", size=(8.5, 1.2, 1.4), location=(handle_x - 3.6, door_y - 3.6, handle_z), bevel_width=0.3, mat=mat_brass)

# Wall Light Switch Plate next to the door (X = -2.0, Y = 104.6, Z = 24)
sw_x, sw_z = -2.0, 24.0
add_beveled_box("Studio_Wall_LightSwitch_Plate", size=(5.2, 0.7, 6.2), location=(sw_x, 104.6, sw_z), bevel_width=0.15, mat=mat_wall_trim)
add_beveled_box("Studio_Wall_LightSwitch_Rocker", size=(2.2, 1.1, 3.2), location=(sw_x, 104.3, sw_z), rotation=(math.radians(8.0), 0, 0), bevel_width=0.1, mat=mat_mug_ceramic)

# Sticky Note / Notice on the Wall (matching Screenshot 1)
add_beveled_box("Studio_Door_StickyNote", size=(6.5, 0.3, 8.5), location=(16.0, door_y - 0.9, 32.0), rotation=(0, math.radians(-4.0), 0), bevel_width=0.05, mat=mat_sticky_note)

# Move Monitor to the right-back of the keyboard so it doesn't block the door/credenza view
for mp in mon_parts:
    mp.location.x += 52.0
    mp.location.y += 18.0

# Framed Wall Art / Floating Shelf on Back Wall above monitor (X = 18, Y = 104.5, Z = 72)
art_x, art_z = 18.0, 74.0
add_beveled_box("Studio_WallArt_Frame", size=(44.0, 2.2, 28.0), location=(art_x, 104.4, art_z), bevel_width=0.25, mat=mat_wall_trim)
add_beveled_box("Studio_WallArt_Canvas", size=(40.0, 2.4, 24.0), location=(art_x, 104.3, art_z), bevel_width=0.05, mat=mat_book_gold)

# Floating Wall Shelf on Back-Right Wall (X = 84, Y = 100, Z = 68)
add_beveled_box("Studio_Floating_WallShelf", size=(52.0, 12.0, 2.2), location=(84.0, 99.0, 68.0), bevel_width=0.2, mat=mat_desk_wood)

# Long Low Sofa / Padded Headboard Silhouette along the Back Wall (matching Screenshots 1 & 5)
# Positioned right in front of the back wall (X from -35 to +85, Y = 96, Z from 0 to 24)
sofa_cx, sofa_cy = 24.0, 95.5
add_beveled_box("Studio_BackWall_Headboard_Base", size=(116.0, 14.0, 18.0), location=(sofa_cx, sofa_cy, 9.0), bevel_width=1.2, segments=3, mat=mat_sofa_fabric)
# Tufted backrest cushions along the back wall
for c_i in range(4):
    cx = sofa_cx - 42.0 + c_i * 28.0
    add_beveled_box(
        f"Studio_BackWall_Cushion_{c_i+1}",
        size=(26.5, 6.5, 22.0),
        location=(cx, 100.5, 14.0),
        rotation=(math.radians(-6.0), 0, 0),
        bevel_width=1.4, segments=3, mat=mat_sofa_fabric
    )

# ---------------------------------------------------------
# Export Complete Scene to GLB
# ---------------------------------------------------------
# Ensure all mesh data blocks match object names for clean glTF node/mesh naming
for o in bpy.data.objects:
    if o.type == 'MESH' and o.data:
        o.data.name = o.name

print(f"Exporting GLB to {OUT_GLB}...")
t_exp = time.time()
bpy.ops.export_scene.gltf(
    filepath=OUT_GLB,
    export_format='GLB',
    export_apply=True,
    export_texcoords=True,
    export_normals=True,
    export_materials='EXPORT',
    export_image_format='AUTO'
)
print(f"Exported {OUT_GLB} successfully in {time.time() - t_exp:.2f}s! Size: {os.path.getsize(OUT_GLB):,} bytes")
