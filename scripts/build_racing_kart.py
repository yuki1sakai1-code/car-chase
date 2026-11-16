import bpy
import bmesh
import math
import os
import numpy as np
from mathutils import Vector, Matrix, Euler

# ==============================================================================
# OUTPUT PATHS
# ==============================================================================
BASE_DIR = r"c:\Users\yukis\Downloads\car-chase"
TEX_DIR = os.path.join(BASE_DIR, "assets", "textures")
MODEL_DIR = os.path.join(BASE_DIR, "assets", "models")
os.makedirs(TEX_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)

ALBEDO_PATH = os.path.join(TEX_DIR, "kart_albedo_2k.png")
ROUGHNESS_PATH = os.path.join(TEX_DIR, "kart_roughness_2k.png")
NORMAL_PATH = os.path.join(TEX_DIR, "kart_normal_2k.png")
EMISSIVE_PATH = os.path.join(TEX_DIR, "kart_emissive_2k.png")
METALLIC_PATH = os.path.join(TEX_DIR, "kart_metallic_2k.png")
GLB_PATH = os.path.join(MODEL_DIR, "racing_kart.glb")

# ==============================================================================
# 1. GENERATE 2048x2048 PBR TEXTURE ATLASES
# ==============================================================================
# Atlas Quadrant / Grid Layout (4x4 grid of 512x512 tiles in 2048x2048 image)
# Note: In Blender images, row 0 is bottom (V=0.0) and row 2047 is top (V=1.0).
# Let's define tiles by (col, row) where col in 0..3 (U = col*0.25 .. (col+1)*0.25)
# and row in 0..3 (V = row*0.25 .. (row+1)*0.25):
#
# (0, 0): Red Paint (#d92525) with white & yellow racing stripe accents
# (1, 0): Yellow/Gold Paint (#f5b82e)
# (2, 0): Crisp White Paint (#f6f7f9)
# (3, 0): Carbon Fiber Weave (dark satin weave with micro-normal)
# (0, 1): Tire Rubber Tread (matte dark rubber with tread groove normal)
# (1, 1): Chrome / Brushed Silver Metal (high metallic, low roughness)
# (2, 1): Helmet Livery (White base with bold central Red stripe along V, yellow pin-stripe)
# (3, 1): Dark Glossy Visor (deep tinted black/blue-grey, roughness 0.05)
# (0, 2): Engine Ribbed Cooling Fins (black anodized metal with horizontal fin normal grooves)
# (1, 2): Red Glowing Tail Light LED (vivid red emissive)
# (2, 2): Cyan Telemetry Dashboard LED (bright cyan emissive)
# (3, 2): Racing Suit Red/White Fabric (satin cloth weave)
# (0, 3): Dark Charcoal Seat / Gloves Suede (matte grip texture)
# (1, 3): Brake Caliper Red Metallic
# (2, 3): Wing White/Silver Top with Number "01" Livery
# (3, 3): Gold / Brass Rim Accent

def save_np_image(name, filepath, rgba_float_array, is_data=False):
    h, w, c = rgba_float_array.shape
    img = bpy.data.images.new(name=name, width=w, height=h, alpha=True, is_data=is_data)
    img.pixels.foreach_set(rgba_float_array.astype(np.float32).ravel())
    img.filepath_raw = filepath
    img.file_format = 'PNG'
    img.save()
    return img

def generate_2k_pbr_textures():
    print("Generating 2048x2048 PBR texture maps...")
    N = 2048
    albedo = np.zeros((N, N, 4), dtype=np.float32)
    albedo[:, :, 3] = 1.0
    rough = np.full((N, N, 4), 0.5, dtype=np.float32)
    rough[:, :, 3] = 1.0
    metal = np.zeros((N, N, 4), dtype=np.float32)
    metal[:, :, 3] = 1.0
    emissive = np.zeros((N, N, 4), dtype=np.float32)
    emissive[:, :, 3] = 1.0
    # Default flat tangent space normal: (0.5, 0.5, 1.0)
    normal = np.zeros((N, N, 4), dtype=np.float32)
    normal[:, :, 0] = 0.5
    normal[:, :, 1] = 0.5
    normal[:, :, 2] = 1.0
    normal[:, :, 3] = 1.0

    # Coordinate grids for a 512x512 tile
    T = 512
    yy, xx = np.meshgrid(np.arange(T, dtype=np.float32), np.arange(T, dtype=np.float32), indexing='ij')
    u = xx / T
    v = yy / T

    def set_tile(col, row, alb_rgb, r_val, m_val, em_rgb=None, norm_dx=None, norm_dy=None):
        y0, y1 = row * T, (row + 1) * T
        x0, x1 = col * T, (col + 1) * T
        albedo[y0:y1, x0:x1, :3] = alb_rgb
        rough[y0:y1, x0:x1, :3] = r_val[..., None] if isinstance(r_val, np.ndarray) else r_val
        metal[y0:y1, x0:x1, :3] = m_val[..., None] if isinstance(m_val, np.ndarray) else m_val
        if em_rgb is not None:
            emissive[y0:y1, x0:x1, :3] = em_rgb
        if norm_dx is not None and norm_dy is not None:
            nx = np.clip(0.5 + norm_dx * 0.5, 0.0, 1.0)
            ny = np.clip(0.5 + norm_dy * 0.5, 0.0, 1.0)
            nz = np.sqrt(np.maximum(0.0, 1.0 - (nx - 0.5)**2 - (ny - 0.5)**2))
            normal[y0:y1, x0:x1, 0] = nx
            normal[y0:y1, x0:x1, 1] = ny
            normal[y0:y1, x0:x1, 2] = nz
        # Add subtle panel border seam around tile outer 4px so UV-mapped panels get crisp micro-seams
        seam_dx = np.zeros((T, T), dtype=np.float32)
        seam_dy = np.zeros((T, T), dtype=np.float32)
        seam_dx[:, :4] = -0.15
        seam_dx[:, -4:] = 0.15
        seam_dy[:4, :] = -0.15
        seam_dy[-4:, :] = 0.15
        normal[y0:y1, x0:x1, 0] = np.clip(normal[y0:y1, x0:x1, 0] + seam_dx, 0.0, 1.0)
        normal[y0:y1, x0:x1, 1] = np.clip(normal[y0:y1, x0:x1, 1] + seam_dy, 0.0, 1.0)

    # Tile (0,0): Vibrant Racing Red (#d92525) with subtle metallic flake & racing stripe edge
    red_alb = np.zeros((T, T, 3), dtype=np.float32)
    red_alb[:, :] = [0.851, 0.145, 0.145]
    # Add crisp white & yellow racing stripe along top edge of tile (v > 0.82)
    stripe_w = (v > 0.82) & (v < 0.90)
    stripe_y = (v >= 0.90) & (v < 0.95)
    red_alb[stripe_w] = [0.97, 0.97, 0.98]
    red_alb[stripe_y] = [0.961, 0.722, 0.180]
    set_tile(0, 0, red_alb, 0.18, 0.08)

    # Tile (1,0): Yellow / Gold Accents (#f5b82e)
    yel_alb = np.full((T, T, 3), [0.961, 0.722, 0.180], dtype=np.float32)
    set_tile(1, 0, yel_alb, 0.20, 0.15)

    # Tile (2,0): Crisp White Paint (#f6f7f9)
    wht_alb = np.full((T, T, 3), [0.965, 0.969, 0.976], dtype=np.float32)
    set_tile(2, 0, wht_alb, 0.18, 0.05)

    # Tile (3,0): Carbon Fiber Weave (2x2 twill pattern)
    cf_period = 16.0
    cx = (xx % cf_period) / cf_period
    cy = (yy % cf_period) / cf_period
    checker = (((xx // (cf_period / 2)) + (yy // (cf_period / 2))) % 2 == 0)
    cf_shade = np.where(checker, 0.14 + 0.05 * np.sin(cx * 2 * np.pi), 0.09 + 0.05 * np.sin(cy * 2 * np.pi))
    cf_alb = np.stack([cf_shade, cf_shade, cf_shade * 1.05], axis=-1)
    cf_rough = np.where(checker, 0.32, 0.38).astype(np.float32)
    cf_dx = np.where(checker, np.cos(cx * 2 * np.pi) * 0.45, 0.0).astype(np.float32)
    cf_dy = np.where(~checker, np.cos(cy * 2 * np.pi) * 0.45, 0.0).astype(np.float32)
    set_tile(3, 0, cf_alb, cf_rough, 0.15, norm_dx=cf_dx, norm_dy=cf_dy)

    # Tile (0,1): Tire Rubber Tread (matte rubber 0.78 with chevron/circumferential tread grooves)
    tread_grooves = (np.sin(u * 18.0 * np.pi) > 0.75) | (np.sin((u * 8.0 + np.abs(v - 0.5) * 6.0) * np.pi) > 0.82)
    tire_val = np.where(tread_grooves, 0.06, 0.11).astype(np.float32)
    tire_alb = np.stack([tire_val, tire_val, tire_val * 1.03], axis=-1)
    tire_rough = np.where(tread_grooves, 0.88, 0.78).astype(np.float32)
    tire_dx = np.cos(u * 18.0 * np.pi) * 0.6
    tire_dy = np.sin((v - 0.5) * 12.0 * np.pi) * 0.35
    set_tile(0, 1, tire_alb, tire_rough, 0.02, norm_dx=tire_dx, norm_dy=tire_dy)

    # Tile (1,1): Chrome / Brushed Silver Metal (roughness 0.12, metallic 0.96)
    brush = 0.86 + 0.04 * np.sin(yy * 0.7) * np.cos(xx * 0.05)
    chrome_alb = np.stack([brush, brush * 1.01, brush * 1.03], axis=-1)
    chrome_dy = np.cos(yy * 0.7) * 0.08
    set_tile(1, 1, chrome_alb, 0.12, 0.96, norm_dx=np.zeros_like(chrome_dy), norm_dy=chrome_dy)

    # Tile (2,1): Helmet Livery (White base with bold central Red stripe in U in [0.36, 0.64] and gold pinstripes)
    helm_alb = np.full((T, T, 3), [0.965, 0.969, 0.976], dtype=np.float32)
    center_red = (u >= 0.36) & (u <= 0.64)
    pin_gold = ((u >= 0.32) & (u < 0.35)) | ((u > 0.65) & (u <= 0.68))
    helm_alb[center_red] = [0.851, 0.145, 0.145]
    helm_alb[pin_gold] = [0.961, 0.722, 0.180]
    helm_dx = np.zeros((T, T), dtype=np.float32)
    helm_dx[( np.abs(u - 0.36) < 0.008 ) | ( np.abs(u - 0.64) < 0.008 )] = 0.35
    set_tile(2, 1, helm_alb, 0.16, 0.08, norm_dx=helm_dx, norm_dy=np.zeros_like(helm_dx))

    # Tile (3,1): Ultra-Glossy Dark Visor (roughness 0.05, metallic 0.85)
    visor_alb = np.full((T, T, 3), [0.04, 0.05, 0.08], dtype=np.float32)
    set_tile(3, 1, visor_alb, 0.05, 0.85)

    # Tile (0,2): Engine Ribbed Cooling Fins (dark metal with strong horizontal fin normal grooves)
    fin_wave = np.sin(v * 36.0 * np.pi)
    fin_shade = 0.12 + 0.08 * (fin_wave * 0.5 + 0.5)
    fin_alb = np.stack([fin_shade, fin_shade, fin_shade * 1.04], axis=-1)
    fin_dy = np.cos(v * 36.0 * np.pi) * 0.85
    set_tile(0, 2, fin_alb, 0.35, 0.80, norm_dx=np.zeros_like(fin_dy), norm_dy=fin_dy)

    # Tile (1,2): Glowing Dual Red LED Tail-Light Strips
    led_pulse = 0.85 + 0.15 * np.sin(u * 24.0 * np.pi)
    led_alb = np.stack([np.full_like(u, 1.0), np.full_like(u, 0.12), np.full_like(u, 0.08)], axis=-1)
    led_em = np.stack([led_pulse * 1.0, led_pulse * 0.08, led_pulse * 0.05], axis=-1)
    set_tile(1, 2, led_alb, 0.10, 0.10, em_rgb=led_em)

    # Tile (2,2): Subtle Cyan Dashboard / Steering Wheel Telemetry LEDs
    dash_alb = np.full((T, T, 3), [0.05, 0.18, 0.22], dtype=np.float32)
    bar_mask = ((v > 0.25) & (v < 0.75) & (np.sin(u * 16.0 * np.pi) > 0.2))
    dash_em = np.zeros((T, T, 3), dtype=np.float32)
    dash_em[bar_mask] = [0.05, 0.88, 1.0]
    dash_alb[bar_mask] = [0.15, 0.92, 1.0]
    set_tile(2, 2, dash_alb, 0.15, 0.20, em_rgb=dash_em)

    # Tile (3,2): Driver Racing Suit (Red & White racing suit with fabric micro-normal)
    suit_alb = np.full((T, T, 3), [0.851, 0.145, 0.145], dtype=np.float32)
    epaulet = (u > 0.38) & (u < 0.62)
    suit_alb[epaulet] = [0.95, 0.96, 0.97]
    suit_gold = ((u >= 0.35) & (u <= 0.38)) | ((u >= 0.62) & (u <= 0.65))
    suit_alb[suit_gold] = [0.961, 0.722, 0.180]
    fab_dx = np.sin(xx * 1.2) * 0.18
    fab_dy = np.cos(yy * 1.2) * 0.18
    set_tile(3, 2, suit_alb, 0.52, 0.02, norm_dx=fab_dx, norm_dy=fab_dy)

    # Tile (0,3): Dark Charcoal Bucket Seat / Racing Gloves Suede
    suede_noise = 0.14 + 0.02 * (np.sin(xx * 0.9) * np.cos(yy * 0.9))
    suede_alb = np.stack([suede_noise, suede_noise, suede_noise * 1.02], axis=-1)
    set_tile(0, 3, suede_alb, 0.72, 0.03, norm_dx=np.sin(xx)*0.15, norm_dy=np.cos(yy)*0.15)

    # Tile (1,3): Red Anodized Brake Caliper
    cal_alb = np.full((T, T, 3), [0.88, 0.08, 0.08], dtype=np.float32)
    set_tile(1, 3, cal_alb, 0.22, 0.82)

    # Tile (2,3): White/Silver Aero Wing Livery with Red/Black Racing Trim
    wing_alb = np.full((T, T, 3), [0.95, 0.96, 0.98], dtype=np.float32)
    wing_trim = (v < 0.18) | (v > 0.82)
    wing_alb[wing_trim] = [0.851, 0.145, 0.145]
    set_tile(2, 3, wing_alb, 0.18, 0.15)

    # Tile (3,3): Metallic Gold / Brass Hub Accent
    gold_alb = np.full((T, T, 3), [0.94, 0.74, 0.24], dtype=np.float32)
    set_tile(3, 3, gold_alb, 0.18, 0.90)

    img_alb = save_np_image("Kart_Albedo_2K", ALBEDO_PATH, albedo, is_data=False)
    img_rgh = save_np_image("Kart_Roughness_2K", ROUGHNESS_PATH, rough, is_data=True)
    img_nrm = save_np_image("Kart_Normal_2K", NORMAL_PATH, normal, is_data=True)
    img_emi = save_np_image("Kart_Emissive_2K", EMISSIVE_PATH, emissive, is_data=False)
    img_met = save_np_image("Kart_Metallic_2K", METALLIC_PATH, metal, is_data=True)
    print("Saved all 2048x2048 PBR maps to:", TEX_DIR)
    return img_alb, img_rgh, img_nrm, img_emi, img_met

# ==============================================================================
# 2. MATERIAL BUILDER
# ==============================================================================
def create_kart_pbr_material(name, imgs):
    img_alb, img_rgh, img_nrm, img_emi, img_met = imgs
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (450, 0)

    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (100, 0)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    tex_alb = nt.nodes.new("ShaderNodeTexImage")
    tex_alb.image = img_alb
    tex_alb.location = (-350, 300)
    nt.links.new(tex_alb.outputs["Color"], bsdf.inputs["Base Color"])

    tex_met = nt.nodes.new("ShaderNodeTexImage")
    tex_met.image = img_met
    tex_met.location = (-350, 50)
    nt.links.new(tex_met.outputs["Color"], bsdf.inputs["Metallic"])

    tex_rgh = nt.nodes.new("ShaderNodeTexImage")
    tex_rgh.image = img_rgh
    tex_rgh.location = (-350, -200)
    nt.links.new(tex_rgh.outputs["Color"], bsdf.inputs["Roughness"])

    tex_emi = nt.nodes.new("ShaderNodeTexImage")
    tex_emi.image = img_emi
    tex_emi.location = (-350, -450)
    if "Emission Color" in bsdf.inputs:
        nt.links.new(tex_emi.outputs["Color"], bsdf.inputs["Emission Color"])
        bsdf.inputs["Emission Strength"].default_value = 3.5
    elif "Emission" in bsdf.inputs:
        nt.links.new(tex_emi.outputs["Color"], bsdf.inputs["Emission"])

    tex_nrm = nt.nodes.new("ShaderNodeTexImage")
    tex_nrm.image = img_nrm
    tex_nrm.location = (-600, -700)
    nrm_node = nt.nodes.new("ShaderNodeNormalMap")
    nrm_node.location = (-250, -700)
    nrm_node.inputs["Strength"].default_value = 1.0
    nt.links.new(tex_nrm.outputs["Color"], nrm_node.inputs["Color"])
    nt.links.new(nrm_node.outputs["Normal"], bsdf.inputs["Normal"])

    return mat

# ==============================================================================
# 3. BMesh GEOMETRY HELPERS (WITH AUTOMATIC UV TILE PACKING + RIG WEIGHTS)
# ==============================================================================
TILE_MAP = {
    "RED_PAINT": (0, 0),
    "YELLOW_PAINT": (1, 0),
    "WHITE_PAINT": (2, 0),
    "CARBON": (3, 0),
    "TIRE": (0, 1),
    "CHROME": (1, 1),
    "HELMET": (2, 1),
    "VISOR": (3, 1),
    "ENGINE_FINS": (0, 2),
    "LED_RED": (1, 2),
    "LED_CYAN": (2, 2),
    "SUIT": (3, 2),
    "SUEDE": (0, 3),
    "CALIPER": (1, 3),
    "WING_TOP": (2, 3),
    "GOLD": (3, 3),
}

def map_bm_uvs_to_tile(bm, tile_key, mode="BOX", axis_u=0, axis_v=1):
    col, row = TILE_MAP[tile_key]
    u0, v0 = col * 0.25 + 0.015, row * 0.25 + 0.015
    span = 0.22
    uv_layer = bm.loops.layers.uv.verify()

    if mode == "SPHERE_HELMET":
        # Project X across U (so central red stripe runs front-to-back along Y & Z at X=0!)
        # Wait: in our helmet tile (2,1), the red stripe is at u in [0.36, 0.64]!
        # Since kart faces -Y and X is left-right (-R to +R), mapping X -> U puts X=0 right in the center (u=0.5)!
        verts = [v.co for v in bm.verts]
        min_x = min(v.x for v in verts) if verts else -0.2
        max_x = max(v.x for v in verts) if verts else 0.2
        min_y = min(v.y for v in verts) if verts else -0.2
        max_y = max(v.y for v in verts) if verts else 0.2
        dx = max(max_x - min_x, 1e-4)
        dy = max(max_y - min_y, 1e-4)
        for f in bm.faces:
            for loop in f.loops:
                co = loop.vert.co
                nu = np.clip((co.x - min_x) / dx, 0.0, 1.0)
                nv = np.clip((co.y - min_y) / dy, 0.0, 1.0)
                loop[uv_layer].uv = (u0 + nu * span, v0 + nv * span)
        return

    verts = [v.co for v in bm.verts]
    if not verts:
        return
    mins = [min(v[i] for v in verts) for i in range(3)]
    maxs = [max(v[i] for v in verts) for i in range(3)]
    dims = [max(maxs[i] - mins[i], 1e-4) for i in range(3)]

    for f in bm.faces:
        n = f.normal
        for loop in f.loops:
            co = loop.vert.co
            if mode == "CYLINDER_X":
                # Good for wheels whose axis is X
                angle = (math.atan2(co.z, co.y) + math.pi) / (2.0 * math.pi)
                nx = (co.x - mins[0]) / dims[0]
                loop[uv_layer].uv = (u0 + angle * span, v0 + nx * span)
            else:
                # Box projection
                if abs(n.z) >= abs(n.x) and abs(n.z) >= abs(n.y):
                    nu = (co.x - mins[0]) / dims[0]
                    nv = (co.y - mins[1]) / dims[1]
                elif abs(n.x) >= abs(n.y):
                    nu = (co.y - mins[1]) / dims[1]
                    nv = (co.z - mins[2]) / dims[2]
                else:
                    nu = (co.x - mins[0]) / dims[0]
                    nv = (co.z - mins[2]) / dims[2]
                loop[uv_layer].uv = (u0 + nu * span, v0 + nv * span)

def create_part_mesh(name, bm, tile_key, mat, bone_name, armature_obj, uv_mode="BOX", smooth=True):
    map_bm_uvs_to_tile(bm, tile_key, mode=uv_mode)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()

    for p in mesh.polygons:
        p.use_smooth = smooth

    mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)

    # Bind to KartArmature with 100% weight to `bone_name`
    vg = obj.vertex_groups.new(name=bone_name)
    vg.add(list(range(len(mesh.vertices))), 1.0, 'REPLACE')

    obj.parent = armature_obj
    mod = obj.modifiers.new(name="Armature", type='ARMATURE')
    mod.object = armature_obj
    return obj

def make_loft_bm(sections, close_caps=True, bevel_edges=False):
    """
    sections: list of (y_pos, z_center, half_width_bottom, half_width_top, height)
    Creates a sleek aerodynamic quad-lofted fuselage/pod along Y.
    """
    bm = bmesh.new()
    rings = []
    for (y, zc, w_bot, w_top, h) in sections:
        z_bot = zc - h * 0.5
        z_top = zc + h * 0.5
        w_mid = max(w_bot, w_top) * 1.08
        z_mid = zc
        # 8-vertex octagonal cross section for smooth aerodynamic silhouette
        pts = [
            (-w_bot * 0.75, y, z_bot),
            ( w_bot * 0.75, y, z_bot),
            ( w_bot,        y, z_bot + h * 0.2),
            ( w_mid,        y, z_mid),
            ( w_top,        y, z_top - h * 0.15),
            ( w_top * 0.70, y, z_top),
            (-w_top * 0.70, y, z_top),
            (-w_top,        y, z_top - h * 0.15),
            (-w_mid,        y, z_mid),
            (-w_bot,        y, z_bot + h * 0.2),
        ]
        ring = [bm.verts.new(p) for p in pts]
        rings.append(ring)

    n = len(rings[0])
    for r in range(len(rings) - 1):
        for i in range(n):
            v1 = rings[r][i]
            v2 = rings[r][(i + 1) % n]
            v3 = rings[r + 1][(i + 1) % n]
            v4 = rings[r + 1][i]
            bm.faces.new((v1, v2, v3, v4))

    if close_caps:
        bm.faces.new(reversed(rings[0]))
        bm.faces.new(rings[-1])

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm

# ==============================================================================
# 4. BUILD ARMATURE (`KartArmature`)
# ==============================================================================
def build_kart_armature():
    bpy.ops.object.add(type='ARMATURE', enter_editmode=True, location=(0, 0, 0))
    arm_obj = bpy.context.active_object
    arm_obj.name = "KartArmature"
    arm = arm_obj.data
    arm.name = "KartArmatureData"

    def add_bone(name, head, tail, parent_name=None):
        b = arm.edit_bones.new(name)
        b.head = Vector(head)
        b.tail = Vector(tail)
        if parent_name and parent_name in arm.edit_bones:
            b.parent = arm.edit_bones[parent_name]
            b.use_connect = False
        return b

    # Coordinate system: Front is -Y, Rear is +Y, Up is +Z, Tire bottoms at Z=0
    add_bone("Root", (0.0, 0.0, 0.0), (0.0, -0.5, 0.0), None)
    add_bone("Chassis", (0.0, 0.0, 0.28), (0.0, -0.6, 0.28), "Root")

    # Steering wheel column bone: angled from dashboard towards driver
    add_bone("SteeringWheel", (0.0, -0.48, 0.78), (0.0, -0.68, 0.62), "Chassis")

    # Driver hierarchy
    add_bone("DriverTorso", (0.0, 0.12, 0.48), (0.0, 0.16, 1.05), "Chassis")
    add_bone("DriverHead", (0.0, 0.16, 1.08), (0.0, 0.16, 1.62), "DriverTorso")
    add_bone("Arm_L", (-0.26, 0.08, 0.94), (-0.18, -0.45, 0.78), "DriverTorso")
    add_bone("Arm_R", ( 0.26, 0.08, 0.94), ( 0.18, -0.45, 0.78), "DriverTorso")

    # Front steering knuckles & all 4 wheel hubs
    # Front wheels at Y = -1.02, Z = 0.30 (radius 0.30 -> bottom at Z = 0.0)
    # Rear wheels at Y = +0.96, Z = 0.36 (radius 0.36 -> bottom at Z = 0.0)
    add_bone("Steer_FL", (-0.84, -1.02, 0.30), (-0.84, -1.25, 0.30), "Chassis")
    add_bone("Steer_FR", ( 0.84, -1.02, 0.30), ( 0.84, -1.25, 0.30), "Chassis")

    add_bone("Wheel_FL", (-0.84, -1.02, 0.30), (-1.12, -1.02, 0.30), "Steer_FL")
    add_bone("Wheel_FR", ( 0.84, -1.02, 0.30), ( 1.12, -1.02, 0.30), "Steer_FR")
    add_bone("Wheel_RL", (-0.88,  0.96, 0.36), (-1.18,  0.96, 0.36), "Chassis")
    add_bone("Wheel_RR", ( 0.88,  0.96, 0.36), ( 1.18,  0.96, 0.36), "Chassis")

    # Exhaust bone for engine high-frequency vibration
    add_bone("Exhaust", (0.0, 1.15, 0.48), (0.0, 1.52, 0.56), "Chassis")

    bpy.ops.object.mode_set(mode='OBJECT')
    return arm_obj

# ==============================================================================
# 5. BUILD DETAILED KART & DRIVER GEOMETRY
# ==============================================================================
def build_kart_meshes(arm_obj, mat_main, mat_visor, mat_emissive):
    created_objs = []

    # --------------------------------------------------------------------------
    # A. MAIN AERODYNAMIC FLOORPAN & CARBON UNDERBODY
    # --------------------------------------------------------------------------
    bm_floor = make_loft_bm([
        (-1.48, 0.14, 0.38, 0.42, 0.06),
        (-1.05, 0.15, 0.52, 0.56, 0.07),
        (-0.35, 0.15, 0.78, 0.82, 0.08),
        ( 0.45, 0.16, 0.80, 0.84, 0.08),
        ( 1.15, 0.18, 0.62, 0.66, 0.08),
        ( 1.42, 0.22, 0.48, 0.52, 0.07),
    ])
    created_objs.append(create_part_mesh("Kart_CarbonFloor", bm_floor, "CARBON", mat_main, "Chassis", arm_obj))

    # --------------------------------------------------------------------------
    # B. FRONT NOSE CONE & MULTI-ELEMENT FRONT SPOILER WING
    # --------------------------------------------------------------------------
    bm_nose = make_loft_bm([
        (-1.58, 0.20, 0.26, 0.18, 0.10),
        (-1.32, 0.28, 0.36, 0.28, 0.18),
        (-0.95, 0.42, 0.42, 0.34, 0.26),
        (-0.52, 0.56, 0.44, 0.36, 0.30),
        (-0.25, 0.48, 0.42, 0.34, 0.22),
    ])
    created_objs.append(create_part_mesh("Kart_FrontNose", bm_nose, "RED_PAINT", mat_main, "Chassis", arm_obj))

    # Front nose central white/yellow racing crest panel
    bm_crest = make_loft_bm([
        (-1.55, 0.25, 0.12, 0.10, 0.04),
        (-1.25, 0.36, 0.15, 0.13, 0.05),
        (-0.85, 0.52, 0.17, 0.15, 0.05),
        (-0.50, 0.68, 0.16, 0.14, 0.04),
    ])
    created_objs.append(create_part_mesh("Kart_NoseStripe", bm_crest, "WHITE_PAINT", mat_main, "Chassis", arm_obj))

    # Front Main Wing Element (wide low aerodynamic splitter + red/white flaps + yellow endplates)
    bm_fwing = make_loft_bm([
        (-1.62, 0.14, 0.82, 0.84, 0.05),
        (-1.38, 0.19, 0.86, 0.88, 0.07),
        (-1.22, 0.22, 0.78, 0.80, 0.05),
    ])
    created_objs.append(create_part_mesh("Kart_FrontWing", bm_fwing, "WING_TOP", mat_main, "Chassis", arm_obj))

    # Front wing endplates (Left & Right)
    bm_fep = bmesh.new()
    for sx in (-1.0, 1.0):
        bmesh.ops.create_cube(bm_fep, size=1.0, matrix=Matrix.Translation((sx * 0.86, -1.42, 0.22)) @ Matrix.Diagonal((0.04, 0.44, 0.22, 1.0)))
    created_objs.append(create_part_mesh("Kart_FrontWingEndplates", bm_fep, "YELLOW_PAINT", mat_main, "Chassis", arm_obj))

    # --------------------------------------------------------------------------
    # C. SIDE PODS WITH AIR INTAKES & YELLOW BARGEBOARDS
    # --------------------------------------------------------------------------
    bm_pods = bmesh.new()
    for sx in (-1.0, 1.0):
        pod_bm = make_loft_bm([
            (-0.68, 0.34, 0.20, 0.16, 0.24),
            (-0.45, 0.38, 0.26, 0.22, 0.32),
            ( 0.05, 0.40, 0.28, 0.24, 0.36),
            ( 0.52, 0.42, 0.26, 0.20, 0.34),
            ( 0.72, 0.38, 0.18, 0.14, 0.24),
        ])
        bmesh.ops.transform(pod_bm, matrix=Matrix.Translation((sx * 0.64, 0.0, 0.0)), verts=pod_bm.verts)
        for f in pod_bm.faces:
            bm_pods.faces.new([bm_pods.verts.new(v.co) for v in f.verts])
        pod_bm.free()
    bmesh.ops.remove_doubles(bm_pods, verts=bm_pods.verts, dist=1e-4)
    bmesh.ops.recalc_face_normals(bm_pods, faces=bm_pods.faces)
    created_objs.append(create_part_mesh("Kart_SidePods", bm_pods, "RED_PAINT", mat_main, "Chassis", arm_obj))

    # Side pod yellow lower accent trim & dark intake mouths
    bm_intakes = bmesh.new()
    for sx in (-1.0, 1.0):
        bmesh.ops.create_cube(bm_intakes, size=1.0, matrix=Matrix.Translation((sx * 0.64, -0.69, 0.36)) @ Matrix.Diagonal((0.30, 0.05, 0.20, 1.0)))
    created_objs.append(create_part_mesh("Kart_SideIntakes", bm_intakes, "ENGINE_FINS", mat_main, "Chassis", arm_obj))

    bm_side_trim = bmesh.new()
    for sx in (-1.0, 1.0):
        bmesh.ops.create_cube(bm_side_trim, size=1.0, matrix=Matrix.Translation((sx * 0.88, -0.05, 0.24)) @ Matrix.Diagonal((0.06, 1.15, 0.08, 1.0)))
    created_objs.append(create_part_mesh("Kart_SideYellowTrim", bm_side_trim, "YELLOW_PAINT", mat_main, "Chassis", arm_obj))

    # --------------------------------------------------------------------------
    # D. RACING BUCKET SEAT & COCKPIT COWLING
    # --------------------------------------------------------------------------
    bm_seat = make_loft_bm([
        (-0.18, 0.26, 0.30, 0.32, 0.12),
        ( 0.12, 0.32, 0.32, 0.34, 0.18),
        ( 0.28, 0.58, 0.30, 0.32, 0.42),
        ( 0.36, 0.92, 0.24, 0.26, 0.46),
    ])
    created_objs.append(create_part_mesh("Kart_BucketSeat", bm_seat, "SUEDE", mat_main, "Chassis", arm_obj))

    # --------------------------------------------------------------------------
    # E. REAR ENGINE BAY WITH BLACK RIBBED COOLING LOUVERS/FINS (BEHIND SEAT)
    # --------------------------------------------------------------------------
    # Main rear engine cowl (Red & White housing around the central black ribbed louver block)
    bm_ecowl = make_loft_bm([
        ( 0.32, 0.56, 0.44, 0.36, 0.44),
        ( 0.68, 0.62, 0.46, 0.38, 0.48),
        ( 1.08, 0.56, 0.40, 0.32, 0.42),
        ( 1.36, 0.46, 0.32, 0.24, 0.30),
    ])
    created_objs.append(create_part_mesh("Kart_EngineCowl", bm_ecowl, "RED_PAINT", mat_main, "Chassis", arm_obj))

    # Prominent Black Ribbed Cooling Louvers / Fins Block directly behind the driver's back (clearly visible in TPS view!)
    bm_fins = bmesh.new()
    # Base core block
    bmesh.ops.create_cube(bm_fins, size=1.0, matrix=Matrix.Translation((0.0, 0.78, 0.68)) @ Matrix.Diagonal((0.52, 0.68, 0.42, 1.0)))
    # 9 individual sculpted horizontal/angled cooling louver fins stacked behind the seat
    for i in range(9):
        t = i / 8.0
        fy = 0.46 + t * 0.62
        fz = 0.88 - t * 0.14
        rot_x = Matrix.Rotation(math.radians(22.0), 4, 'X')
        mat_fin = Matrix.Translation((0.0, fy, fz)) @ rot_x @ Matrix.Diagonal((0.56, 0.045, 0.12, 1.0))
        bmesh.ops.create_cube(bm_fins, size=1.0, matrix=mat_fin)
    created_objs.append(create_part_mesh("Kart_EngineCoolingFins", bm_fins, "ENGINE_FINS", mat_main, "Chassis", arm_obj))

    # Chrome cylinder head / turbocharger detail on engine block
    bm_cyl = bmesh.new()
    for sx in (-0.22, 0.22):
        bmesh.ops.create_cone(bm_cyl, cap_ends=True, cap_tris=False, segments=16, radius1=0.09, radius2=0.08, depth=0.32,
                              matrix=Matrix.Translation((sx, 1.05, 0.76)) @ Matrix.Rotation(math.radians(25), 4, 'X'))
    created_objs.append(create_part_mesh("Kart_EngineChromeHeads", bm_cyl, "CHROME", mat_main, "Chassis", arm_obj))

    # --------------------------------------------------------------------------
    # F. DUAL SILVER/CHROME CURVED EXHAUST PIPES (ATTACHED TO `Exhaust` BONE)
    # --------------------------------------------------------------------------
    bm_exh = bmesh.new()
    for sx in (-0.24, 0.24):
        # Multi-segment curved exhaust pipe sweeps backward & upward from engine bay
        pipe_pts = [
            (sx, 0.98, 0.50, 0.055),
            (sx, 1.15, 0.48, 0.060),
            (sx, 1.32, 0.52, 0.068),
            (sx, 1.48, 0.58, 0.078),
            (sx, 1.56, 0.61, 0.082),
            (sx, 1.54, 0.60, 0.062), # inner lip bevel
        ]
        rings = []
        segs = 16
        for (px, py, pz, rad) in pipe_pts:
            ring = []
            for s in range(segs):
                ang = (s / segs) * 2.0 * math.pi
                ring.append(bm_exh.verts.new((px + math.cos(ang) * rad, py, pz + math.sin(ang) * rad)))
            rings.append(ring)
        for r in range(len(rings) - 1):
            for s in range(segs):
                v1 = rings[r][s]
                v2 = rings[r][(s + 1) % segs]
                v3 = rings[r + 1][(s + 1) % segs]
                v4 = rings[r + 1][s]
                bm_exh.faces.new((v1, v2, v3, v4))
        bm_exh.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm_exh, faces=bm_exh.faces)
    created_objs.append(create_part_mesh("Kart_DualExhaust", bm_exh, "CHROME", mat_main, "Exhaust", arm_obj))

    # --------------------------------------------------------------------------
    # G. REAR SPOILER WING ON TWIN ANGLED STRUTS + COMPACT ENDPLATES
    # --------------------------------------------------------------------------
    # Twin angled struts (compact, positioned behind engine cooling fins)
    bm_struts = bmesh.new()
    for sx in (-0.24, 0.24):
        s_pts = [
            (sx, 1.04, 0.56, 0.022, 0.10),
            (sx, 1.16, 0.68, 0.022, 0.09),
            (sx, 1.26, 0.78, 0.022, 0.08),
        ]
        s_rings = []
        for (px, py, pz, hw, hl) in s_pts:
            s_rings.append([
                bm_struts.verts.new((px - hw, py - hl, pz)),
                bm_struts.verts.new((px + hw, py - hl, pz)),
                bm_struts.verts.new((px + hw, py + hl, pz)),
                bm_struts.verts.new((px - hw, py + hl, pz)),
            ])
        for r in range(len(s_rings) - 1):
            for i in range(4):
                bm_struts.faces.new((s_rings[r][i], s_rings[r][(i+1)%4], s_rings[r+1][(i+1)%4], s_rings[r+1][i]))
    bmesh.ops.recalc_face_normals(bm_struts, faces=bm_struts.faces)
    created_objs.append(create_part_mesh("Kart_RearWingStruts", bm_struts, "CARBON", mat_main, "Chassis", arm_obj))

    # Rear Wing Main Plane (Compact low-profile silver/white kart spoiler matching reference screenshots)
    bm_rwing = make_loft_bm([
        ( 1.14, 0.77, 0.54, 0.56, 0.042),
        ( 1.26, 0.80, 0.56, 0.58, 0.048),
        ( 1.38, 0.83, 0.55, 0.57, 0.040),
    ])
    created_objs.append(create_part_mesh("Kart_RearWingMain", bm_rwing, "WING_TOP", mat_main, "Chassis", arm_obj))

    # Rear Wing Angled Black Endplates (Left & Right, sleek low-profile)
    bm_rep = bmesh.new()
    for sx in (-1.0, 1.0):
        mat_ep = Matrix.Translation((sx * 0.57, 1.26, 0.78)) @ Matrix.Rotation(math.radians(-12), 4, 'X') @ Matrix.Rotation(math.radians(sx * 14), 4, 'Y') @ Matrix.Diagonal((0.028, 0.30, 0.14, 1.0))
        bmesh.ops.create_cube(bm_rep, size=1.0, matrix=mat_ep)
    created_objs.append(create_part_mesh("Kart_RearWingEndplates", bm_rep, "CARBON", mat_main, "Chassis", arm_obj))

    # --------------------------------------------------------------------------
    # H. DUAL GLOWING RED LED TAIL-LIGHTS AT REAR BUMPER
    # --------------------------------------------------------------------------
    bm_rbump = make_loft_bm([
        ( 1.28, 0.32, 0.62, 0.64, 0.14),
        ( 1.50, 0.34, 0.58, 0.60, 0.14),
    ])
    created_objs.append(create_part_mesh("Kart_RearBumper", bm_rbump, "CARBON", mat_main, "Chassis", arm_obj))

    bm_tail_leds = bmesh.new()
    for sx in (-0.36, 0.36):
        bmesh.ops.create_cube(bm_tail_leds, size=1.0, matrix=Matrix.Translation((sx, 1.52, 0.36)) @ Matrix.Diagonal((0.32, 0.04, 0.075, 1.0)))
    # Also central F1 rain light between exhausts
    bmesh.ops.create_cube(bm_tail_leds, size=1.0, matrix=Matrix.Translation((0.0, 1.52, 0.36)) @ Matrix.Diagonal((0.10, 0.04, 0.10, 1.0)))
    created_objs.append(create_part_mesh("Kart_TailLightsLED", bm_tail_leds, "LED_RED", mat_emissive, "Chassis", arm_obj))

    # --------------------------------------------------------------------------
    # I. SUSPENSION WISHBONES & REAR AXLE + BRAKE CALIPERS
    # --------------------------------------------------------------------------
    bm_susp = bmesh.new()
    # Front upper/lower wishbone struts
    for sx in (-1.0, 1.0):
        for dz in (-0.05, 0.05):
            bmesh.ops.create_cube(bm_susp, size=1.0, matrix=Matrix.Translation((sx * 0.56, -1.02, 0.30 + dz)) @ Matrix.Diagonal((0.52, 0.04, 0.03, 1.0)))
    # Rear solid axle tube
    bmesh.ops.create_cone(bm_susp, cap_ends=True, segments=12, radius1=0.045, radius2=0.045, depth=1.72,
                          matrix=Matrix.Translation((0.0, 0.96, 0.36)) @ Matrix.Rotation(math.radians(90), 4, 'Y'))
    created_objs.append(create_part_mesh("Kart_SuspensionAxles", bm_susp, "CHROME", mat_main, "Chassis", arm_obj))

    # Red Brake Calipers (front calipers on Steer_FL/Steer_FR, rear calipers on Chassis)
    for bname, wx, wy, wz in [
        ("Steer_FL", -0.74, -0.92, 0.36),
        ("Steer_FR",  0.74, -0.92, 0.36),
        ("Chassis",  -0.76,  0.84, 0.42),
        ("Chassis",   0.76,  0.84, 0.42),
    ]:
        bm_cal = bmesh.new()
        bmesh.ops.create_cube(bm_cal, size=1.0, matrix=Matrix.Translation((wx, wy, wz)) @ Matrix.Diagonal((0.08, 0.14, 0.16, 1.0)))
        created_objs.append(create_part_mesh(f"Kart_Caliper_{bname}_{'L' if wx<0 else 'R'}", bm_cal, "CALIPER", mat_main, bname, arm_obj))

    # --------------------------------------------------------------------------
    # J. 4 WIDE RACING SLICK TIRES WITH DEEP RIMS & METALLIC HUBS
    # --------------------------------------------------------------------------
    wheel_specs = [
        ("Wheel_FL", -0.88, -1.02, 0.30, 0.30, 0.32),
        ("Wheel_FR",  0.88, -1.02, 0.30, 0.30, 0.32),
        ("Wheel_RL", -0.92,  0.96, 0.36, 0.36, 0.40),
        ("Wheel_RR",  0.92,  0.96, 0.36, 0.36, 0.40),
    ]
    for w_name, wx, wy, wz, rad, width in wheel_specs:
        # 1. Wide Rubber Slick Tire with beveled shoulders
        bm_tire = bmesh.new()
        segs = 32
        half_w = width * 0.5
        r_inner = rad * 0.58
        profile = [
            (-half_w * 0.82, r_inner),
            (-half_w * 0.96, rad * 0.88),
            (-half_w,        rad * 0.97),
            (-half_w * 0.65, rad),
            ( 0.0,           rad * 1.01),
            ( half_w * 0.65, rad),
            ( half_w,        rad * 0.97),
            ( half_w * 0.96, rad * 0.88),
            ( half_w * 0.82, r_inner),
        ]
        rings = []
        for (px, pr) in profile:
            ring = []
            for s in range(segs):
                ang = (s / segs) * 2.0 * math.pi
                ring.append(bm_tire.verts.new((wx + px, wy + math.cos(ang) * pr, wz + math.sin(ang) * pr)))
            rings.append(ring)
        for r in range(len(rings) - 1):
            for s in range(segs):
                bm_tire.faces.new((rings[r][s], rings[r][(s+1)%segs], rings[r+1][(s+1)%segs], rings[r+1][s]))
        # Close inner bead ring
        for s in range(segs):
            bm_tire.faces.new((rings[-1][s], rings[-1][(s+1)%segs], rings[0][(s+1)%segs], rings[0][s]))
        bmesh.ops.recalc_face_normals(bm_tire, faces=bm_tire.faces)
        created_objs.append(create_part_mesh(f"{w_name}_Tire", bm_tire, "TIRE", mat_main, w_name, arm_obj, uv_mode="CYLINDER_X"))

        # 2. Deep Metallic Rim & 6-Spoke Star Hub + Gold Center Lock Nut
        bm_rim = bmesh.new()
        rot_y = Matrix.Rotation(math.radians(90), 4, 'Y')
        # Outer rim barrel
        bmesh.ops.create_cone(bm_rim, cap_ends=True, segments=24, radius1=r_inner * 1.02, radius2=r_inner * 1.02, depth=width * 0.72,
                              matrix=Matrix.Translation((wx, wy, wz)) @ rot_y)
        # 6 spokes so wheel spin is visually unmistakable in motion!
        out_sign = -1.0 if wx < 0 else 1.0
        for sp in range(6):
            ang = sp * (math.pi / 3.0)
            rot_sp = Matrix.Rotation(ang, 4, 'X')
            mat_sp = Matrix.Translation((wx + out_sign * width * 0.22, wy, wz)) @ rot_sp @ Matrix.Diagonal((0.05, r_inner * 0.96, 0.045, 1.0))
            bmesh.ops.create_cube(bm_rim, size=1.0, matrix=mat_sp)
        created_objs.append(create_part_mesh(f"{w_name}_Rim", bm_rim, "CHROME", mat_main, w_name, arm_obj))

        # Red/Gold Wheel Center Lock Nut (asymmetrical visual marker for spin clarity)
        bm_nut = bmesh.new()
        bmesh.ops.create_cone(bm_nut, cap_ends=True, segments=6, radius1=rad * 0.20, radius2=rad * 0.14, depth=0.10,
                              matrix=Matrix.Translation((wx + out_sign * width * 0.36, wy, wz)) @ rot_y)
        created_objs.append(create_part_mesh(f"{w_name}_HubNut", bm_nut, "GOLD", mat_main, w_name, arm_obj))

    # --------------------------------------------------------------------------
    # K. STEERING COLUMN & WHEEL WITH CYAN TELEMETRY LED DISPLAY
    # --------------------------------------------------------------------------
    # Fixed steering column shroud (on Chassis)
    bm_col = bmesh.new()
    rot_col = Matrix.Rotation(math.radians(38), 4, 'X')
    bmesh.ops.create_cone(bm_col, cap_ends=True, segments=16, radius1=0.06, radius2=0.045, depth=0.42,
                          matrix=Matrix.Translation((0.0, -0.60, 0.68)) @ rot_col)
    created_objs.append(create_part_mesh("Kart_SteeringColumn", bm_col, "CARBON", mat_main, "Chassis", arm_obj))

    # Rotating Steering Wheel Rim & Grips (on `SteeringWheel` bone)
    bm_sw = bmesh.new()
    sw_center = Vector((0.0, -0.46, 0.80))
    # Build torus-like F1 butterfly steering wheel in local plane tilted by 38 deg around X
    segs_ring = 24
    segs_tube = 10
    R_maj = 0.17
    R_min = 0.024
    sw_rings = []
    for i in range(segs_ring):
        theta = (i / segs_ring) * 2.0 * math.pi
        cx = math.cos(theta) * R_maj
        cz = math.sin(theta) * R_maj * 0.86
        ring = []
        for j in range(segs_tube):
            phi = (j / segs_tube) * 2.0 * math.pi
            vx = cx + math.cos(theta) * math.cos(phi) * R_min
            vz = cz + math.sin(theta) * math.cos(phi) * R_min
            vy = math.sin(phi) * R_min
            pt = Matrix.Translation(sw_center) @ rot_col @ Vector((vx, vy, vz))
            ring.append(bm_sw.verts.new(pt))
        sw_rings.append(ring)
    for i in range(segs_ring):
        for j in range(segs_tube):
            bm_sw.faces.new((
                sw_rings[i][j],
                sw_rings[i][(j+1)%segs_tube],
                sw_rings[(i+1)%segs_ring][(j+1)%segs_tube],
                sw_rings[(i+1)%segs_ring][j]
            ))
    # Center hub plate
    bmesh.ops.create_cube(bm_sw, size=1.0, matrix=Matrix.Translation(sw_center) @ rot_col @ Matrix.Diagonal((0.28, 0.03, 0.12, 1.0)))
    bmesh.ops.recalc_face_normals(bm_sw, faces=bm_sw.faces)
    created_objs.append(create_part_mesh("Kart_SteeringWheelMesh", bm_sw, "CARBON", mat_main, "SteeringWheel", arm_obj))

    # Cyan Telemetry LED Display on Steering Wheel
    bm_dash = bmesh.new()
    bmesh.ops.create_cube(bm_dash, size=1.0, matrix=Matrix.Translation(sw_center + Vector((0, 0.015, 0.02))) @ rot_col @ Matrix.Diagonal((0.14, 0.02, 0.07, 1.0)))
    created_objs.append(create_part_mesh("Kart_TelemetryDisplayLED", bm_dash, "LED_CYAN", mat_emissive, "SteeringWheel", arm_obj))

    # --------------------------------------------------------------------------
    # L. DRIVER CHARACTER: TORSO, ARMS/GLOVES, ICONIC WHITE HELMET WITH RED STRIPE & VISOR
    # --------------------------------------------------------------------------
    # 1. Driver Torso & Racing Suit with Shoulder Pads (on `DriverTorso`)
    bm_torso = make_loft_bm([
        ( 0.08, 0.46, 0.20, 0.22, 0.24),
        ( 0.12, 0.66, 0.23, 0.25, 0.28),
        ( 0.15, 0.88, 0.27, 0.29, 0.26),
        ( 0.16, 1.04, 0.14, 0.12, 0.16),
    ])
    # Rotate torso slightly upright along Z
    created_objs.append(create_part_mesh("Driver_TorsoSuit", bm_torso, "SUIT", mat_main, "DriverTorso", arm_obj))

    # Driver White/Gold Shoulder Pads & Collar
    bm_collar = bmesh.new()
    bmesh.ops.create_cone(bm_collar, cap_ends=True, segments=20, radius1=0.16, radius2=0.13, depth=0.10,
                          matrix=Matrix.Translation((0.0, 0.15, 1.05)))
    created_objs.append(create_part_mesh("Driver_NeckCollar", bm_collar, "WHITE_PAINT", mat_main, "DriverTorso", arm_obj))

    # Driver Legs in Cockpit (on `Chassis`)
    bm_legs = bmesh.new()
    for sx in (-0.13, 0.13):
        mat_leg = Matrix.Translation((sx, -0.26, 0.42)) @ Matrix.Rotation(math.radians(-12), 4, 'X') @ Matrix.Diagonal((0.15, 0.56, 0.15, 1.0))
        bmesh.ops.create_cube(bm_legs, size=1.0, matrix=mat_leg)
    created_objs.append(create_part_mesh("Driver_Legs", bm_legs, "SUIT", mat_main, "Chassis", arm_obj))

    # 2. Driver Left & Right Arms + Gloves reaching forward to grip steering wheel (`Arm_L`, `Arm_R`)
    for side, sx, bname in [("L", -1.0, "Arm_L"), ("R", 1.0, "Arm_R")]:
        bm_arm = bmesh.new()
        arm_pts = [
            (sx * 0.27,  0.12, 0.93, 0.078), # Shoulder
            (sx * 0.28, -0.08, 0.84, 0.068), # Upper arm
            (sx * 0.25, -0.24, 0.78, 0.062), # Elbow
            (sx * 0.19, -0.38, 0.79, 0.054), # Forearm
        ]
        rings = []
        segs = 14
        for (px, py, pz, rad) in arm_pts:
            ring = []
            for s in range(segs):
                ang = (s / segs) * 2.0 * math.pi
                ring.append(bm_arm.verts.new((px + math.cos(ang) * rad, py, pz + math.sin(ang) * rad)))
            rings.append(ring)
        for r in range(len(rings) - 1):
            for s in range(segs):
                bm_arm.faces.new((rings[r][s], rings[r][(s+1)%segs], rings[r+1][(s+1)%segs], rings[r+1][s]))
        bm_arm.faces.new(reversed(rings[0]))
        bm_arm.faces.new(rings[-1])
        bmesh.ops.recalc_face_normals(bm_arm, faces=bm_arm.faces)
        created_objs.append(create_part_mesh(f"Driver_Arm_{side}", bm_arm, "SUIT", mat_main, bname, arm_obj))

        # Glove gripping the steering wheel
        bm_glove = bmesh.new()
        bmesh.ops.create_icosphere(bm_glove, subdivisions=2, radius=0.068,
                                   matrix=Matrix.Translation((sx * 0.16, -0.45, 0.80)) @ Matrix.Diagonal((0.9, 1.3, 0.9, 1.0)))
        created_objs.append(create_part_mesh(f"Driver_Glove_{side}", bm_glove, "SUEDE", mat_main, bname, arm_obj))

    # 3. Iconic Large Rounded White Racing Helmet with Bold Central Red Stripe & Dark Visor (on `DriverHead`)
    # Center at (0.0, 0.14, 1.36), radius ~0.28m so top reaches ~1.65m and is super prominent from rear TPS camera!
    helm_center = Vector((0.0, 0.14, 1.35))
    bm_helm = bmesh.new()
    bmesh.ops.create_uvsphere(bm_helm, u_segments=36, v_segments=24, radius=0.275)
    # Shape into authentic full-face aerodynamic racing helmet (slightly elongated front-to-back, chin bar at -Y, aero spoiler at +Y)
    for v in bm_helm.verts:
        x, y, z = v.co.x, v.co.y, v.co.z
        # Flatten bottom neck opening
        if z < -0.18:
            z = -0.18 + (z + 0.18) * 0.25
        # Extend chin guard slightly forward (-Y)
        if y < 0 and z < 0.02:
            y *= 1.14
        # Subtle rear aero helmet ridge (+Y)
        if y > 0.12 and z > -0.05:
            y *= 1.08
        v.co = helm_center + Vector((x * 0.96, y * 1.08, z * 1.04))
    bmesh.ops.recalc_face_normals(bm_helm, faces=bm_helm.faces)
    # Use SPHERE_HELMET UV projection so X maps across U=[0..1], placing the bold red stripe (U in [0.36, 0.64]) dead-center over the top & back!
    created_objs.append(create_part_mesh("Driver_Helmet", bm_helm, "HELMET", mat_main, "DriverHead", arm_obj, uv_mode="SPHERE_HELMET"))

    # Dark Glossy Wrap-Around Tinted Visor on the front (-Y) of the helmet
    bm_visor = bmesh.new()
    u_segs = 24
    v_segs = 10
    v_rings = []
    for iv in range(v_segs + 1):
        vz_ang = math.radians(-12.0 + (iv / v_segs) * 38.0) # vertical band across front face
        ring = []
        for iu in range(u_segs + 1):
            # Front azimuth (-Y is -90 deg)
            az = math.radians(-90.0 - 62.0 + (iu / u_segs) * 124.0)
            rx = 0.272 * math.cos(vz_ang) * math.cos(az)
            ry = 0.305 * math.cos(vz_ang) * math.sin(az)
            rz = 0.285 * math.sin(vz_ang) + 0.02
            ring.append(bm_visor.verts.new(helm_center + Vector((rx, ry, rz))))
        v_rings.append(ring)
    for iv in range(v_segs):
        for iu in range(u_segs):
            bm_visor.faces.new((v_rings[iv][iu], v_rings[iv][iu+1], v_rings[iv+1][iu+1], v_rings[iv+1][iu]))
    # Solidify visor slightly outward
    bmesh.ops.recalc_face_normals(bm_visor, faces=bm_visor.faces)
    created_objs.append(create_part_mesh("Driver_HelmetVisor", bm_visor, "VISOR", mat_visor, "DriverHead", arm_obj))

    return created_objs

# ==============================================================================
# 6. ANIMATIONS (BAKED TO NLA TRACKS FOR GLTF EXPORT)
# ==============================================================================
def set_linear_fcurves(action):
    # Compatible with both legacy Action.fcurves and Blender 5.0+ layered/slotted actions
    if hasattr(action, "fcurves"):
        for fc in action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'
    if hasattr(action, "layers"):
        for layer in action.layers:
            for strip in layer.strips:
                if hasattr(strip, "channelbags"):
                    for bag in strip.channelbags:
                        for fc in bag.fcurves:
                            for kp in fc.keyframe_points:
                                kp.interpolation = 'LINEAR'

def reset_pose(arm_obj):
    for pb in arm_obj.pose.bones:
        pb.rotation_mode = 'XYZ'
        pb.location = (0.0, 0.0, 0.0)
        pb.rotation_euler = (0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)

def key_all_bones(arm_obj, frame):
    for pb in arm_obj.pose.bones:
        pb.keyframe_insert(data_path="location", frame=frame)
        pb.keyframe_insert(data_path="rotation_euler", frame=frame)

def build_kart_animations(arm_obj):
    arm_obj.animation_data_create()
    pb = arm_obj.pose.bones
    for b in pb:
        b.rotation_mode = 'XYZ'

    actions_created = []

    # --------------------------------------------------------------------------
    # 1. `Idle` (frames 1-60): High-frequency engine/exhaust vibration + gentle driver head scan
    # --------------------------------------------------------------------------
    act_idle = bpy.data.actions.new(name="Idle")
    arm_obj.animation_data.action = act_idle
    reset_pose(arm_obj)

    for f in range(1, 61, 2):
        t = (f - 1) / 59.0
        ang = t * 2.0 * math.pi
        vib = math.sin(f * 1.8)
        pb["Chassis"].location = (0.0, 0.0, 0.004 * vib)
        pb["Chassis"].rotation_euler = (0.003 * vib, 0.004 * math.cos(f * 1.8), 0.0)
        pb["Exhaust"].location = (0.003 * vib, 0.0, -0.006 * vib)
        pb["Exhaust"].rotation_euler = (0.025 * vib, 0.0, 0.015 * math.cos(f * 2.1))
        pb["DriverTorso"].rotation_euler = (0.015 * math.sin(ang), 0.0, 0.0)
        pb["DriverHead"].rotation_euler = (0.02 * math.sin(ang * 2.0), 0.0, 0.08 * math.sin(ang))
        key_all_bones(arm_obj, f)

    # Ensure exact loop at frame 60
    f = 60
    pb["Chassis"].location = (0.0, 0.0, 0.0)
    pb["Chassis"].rotation_euler = (0.0, 0.0, 0.0)
    pb["Exhaust"].location = (0.0, 0.0, 0.0)
    pb["Exhaust"].rotation_euler = (0.0, 0.0, 0.0)
    pb["DriverTorso"].rotation_euler = (0.0, 0.0, 0.0)
    pb["DriverHead"].rotation_euler = (0.0, 0.0, 0.0)
    key_all_bones(arm_obj, 60)
    actions_created.append(act_idle)

    # --------------------------------------------------------------------------
    # 2. `Drive` (frames 1-60): Continuous 360-deg wheel rotation on all 4 wheels + suspension micro-bounce
    # --------------------------------------------------------------------------
    act_drive = bpy.data.actions.new(name="Drive")
    arm_obj.animation_data.action = act_drive
    reset_pose(arm_obj)

    # Note: Wheel bones point outwards along -X (left) and +X (right).
    # Or even simpler: let's keyframe all frames every 5 frames so quaternion slerp never flips!
    for f in [1, 15, 30, 45, 60]:
        frac = (f - 1) / 59.0
        spin = frac * 2.0 * math.pi
        # Left wheel bone local +Y is world -X, so rotating around local Y spins the wheel around world X!
        # Let's check: in Blender, a bone pointing from (-0.84, -1.02, 0.30) to (-1.12, -1.02, 0.30) has its local Y axis along (-1, 0, 0) (the bone axis!).
        # Rotating around a bone's lengthwise axis in Pose Mode is ALWAYS local Y (`rotation_euler[1]`)!
        pb["Wheel_FL"].rotation_euler = (0.0,  spin, 0.0)
        pb["Wheel_RL"].rotation_euler = (0.0,  spin, 0.0)
        pb["Wheel_FR"].rotation_euler = (0.0, -spin, 0.0)
        pb["Wheel_RR"].rotation_euler = (0.0, -spin, 0.0)

        bounce = math.sin(frac * 4.0 * math.pi)
        pb["Chassis"].location = (0.0, 0.0, 0.012 * bounce)
        pb["Chassis"].rotation_euler = (0.008 * math.cos(frac * 4.0 * math.pi), 0.0, 0.0)
        pb["Exhaust"].location = (0.0, 0.0, -0.008 * bounce)
        pb["DriverHead"].rotation_euler = (-0.025 * bounce, 0.0, 0.0)
        key_all_bones(arm_obj, f)

    set_linear_fcurves(act_drive)
    actions_created.append(act_drive)

    # --------------------------------------------------------------------------
    # 3. `SteerLeft` (frames 1-30): Steer_FL/FR turned left, SteeringWheel turned left, DriverTorso & DriverHead lean left
    # --------------------------------------------------------------------------
    act_left = bpy.data.actions.new(name="SteerLeft")
    arm_obj.animation_data.action = act_left
    reset_pose(arm_obj)
    key_all_bones(arm_obj, 1)

    for f, weight in [(15, 1.0), (30, 1.0)]:
        # Front wheel steering knuckles point along -Y (horizontal), so local Z is vertical yaw!
        pb["Steer_FL"].rotation_euler = (0.0, 0.0, math.radians(28.0) * weight)
        pb["Steer_FR"].rotation_euler = (0.0, 0.0, math.radians(28.0) * weight)
        # SteeringWheel bone local Y is along the steering column axis
        pb["SteeringWheel"].rotation_euler = (0.0, math.radians(-55.0) * weight, 0.0)
        # Chassis slight roll right (centrifugal) while driver leans into the left turn
        pb["Chassis"].rotation_euler = (0.0, math.radians(-3.5) * weight, 0.0)
        pb["DriverTorso"].rotation_euler = (0.0, math.radians(-12.0) * weight, math.radians(8.0) * weight)
        pb["DriverHead"].rotation_euler = (0.0, math.radians(-10.0) * weight, math.radians(18.0) * weight)
        pb["Arm_L"].rotation_euler = (math.radians(-10.0) * weight, 0.0, math.radians(8.0) * weight)
        pb["Arm_R"].rotation_euler = (math.radians(12.0) * weight, 0.0, math.radians(8.0) * weight)
        key_all_bones(arm_obj, f)
    actions_created.append(act_left)

    # --------------------------------------------------------------------------
    # 4. `SteerRight` (frames 1-30): Steer_FL/FR turned right, SteeringWheel turned right, DriverTorso & DriverHead lean right
    # --------------------------------------------------------------------------
    act_right = bpy.data.actions.new(name="SteerRight")
    arm_obj.animation_data.action = act_right
    reset_pose(arm_obj)
    key_all_bones(arm_obj, 1)

    for f, weight in [(15, 1.0), (30, 1.0)]:
        pb["Steer_FL"].rotation_euler = (0.0, 0.0, math.radians(-28.0) * weight)
        pb["Steer_FR"].rotation_euler = (0.0, 0.0, math.radians(-28.0) * weight)
        pb["SteeringWheel"].rotation_euler = (0.0, math.radians(55.0) * weight, 0.0)
        pb["Chassis"].rotation_euler = (0.0, math.radians(3.5) * weight, 0.0)
        pb["DriverTorso"].rotation_euler = (0.0, math.radians(12.0) * weight, math.radians(-8.0) * weight)
        pb["DriverHead"].rotation_euler = (0.0, math.radians(10.0) * weight, math.radians(-18.0) * weight)
        pb["Arm_L"].rotation_euler = (math.radians(12.0) * weight, 0.0, math.radians(-8.0) * weight)
        pb["Arm_R"].rotation_euler = (math.radians(-10.0) * weight, 0.0, math.radians(-8.0) * weight)
        key_all_bones(arm_obj, f)
    actions_created.append(act_right)

    # --------------------------------------------------------------------------
    # 5. `Boost` (frames 1-30): Nose-up acceleration squat, rapid wheel spin & exhaust vibration
    # --------------------------------------------------------------------------
    act_boost = bpy.data.actions.new(name="Boost")
    arm_obj.animation_data.action = act_boost
    reset_pose(arm_obj)
    for f in [1, 8, 15, 22, 30]:
        frac = (f - 1) / 29.0
        spin = frac * 4.0 * math.pi
        pb["Wheel_FL"].rotation_euler = (0.0,  spin, 0.0)
        pb["Wheel_RL"].rotation_euler = (0.0,  spin, 0.0)
        pb["Wheel_FR"].rotation_euler = (0.0, -spin, 0.0)
        pb["Wheel_RR"].rotation_euler = (0.0, -spin, 0.0)
        pb["Chassis"].rotation_euler = (math.radians(-3.5), 0.0, 0.0)
        pb["Chassis"].location = (0.0, 0.0, 0.015 * math.sin(frac * 6.0 * math.pi))
        pb["DriverHead"].rotation_euler = (math.radians(-6.0), 0.0, 0.0)
        pb["Exhaust"].location = (0.0, 0.0, 0.012 * math.cos(frac * 8.0 * math.pi))
        key_all_bones(arm_obj, f)
    set_linear_fcurves(act_boost)
    actions_created.append(act_boost)

    # Push all actions to NLA tracks so GLTF exporter exports every clip cleanly
    reset_pose(arm_obj)
    arm_obj.animation_data.action = None
    for act in actions_created:
        track = arm_obj.animation_data.nla_tracks.new()
        track.name = act.name
        strip = track.strips.new(act.name, int(act.frame_range[0]), act)
        strip.name = act.name
        track.mute = False

    return actions_created

# ==============================================================================
# 7. MAIN BUILD & GLB EXPORT + VERIFICATION
# ==============================================================================
def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    imgs = generate_2k_pbr_textures()

    mat_main = create_kart_pbr_material("Kart_Main_PBR_2K", imgs)
    mat_visor = create_kart_pbr_material("Kart_Visor_PBR_2K", imgs)
    mat_emissive = create_kart_pbr_material("Kart_LED_Emissive_2K", imgs)

    arm_obj = build_kart_armature()
    objs = build_kart_meshes(arm_obj, mat_main, mat_visor, mat_emissive)
    actions = build_kart_animations(arm_obj)

    # Compute overall bounding box to verify dimensions (~2.2m wide, ~3.2m long, ~1.75m tall, Z_min ~ 0.0)
    bpy.context.view_layer.update()
    all_pts = []
    for o in objs:
        for v in o.bound_box:
            all_pts.append(o.matrix_world @ Vector(v))
    min_x = min(p.x for p in all_pts)
    max_x = max(p.x for p in all_pts)
    min_y = min(p.y for p in all_pts)
    max_y = max(p.y for p in all_pts)
    min_z = min(p.z for p in all_pts)
    max_z = max(p.z for p in all_pts)
    print(f"KART BOUNDS: X=[{min_x:.3f}, {max_x:.3f}] (W={max_x-min_x:.3f}m), "
          f"Y=[{min_y:.3f}, {max_y:.3f}] (L={max_y-min_y:.3f}m), "
          f"Z=[{min_z:.3f}, {max_z:.3f}] (H={max_z-min_z:.3f}m)")

    # Export to GLB
    bpy.ops.export_scene.gltf(
        filepath=GLB_PATH,
        export_format='GLB',
        export_apply=False,
        export_animations=True,
        export_animation_mode='NLA_TRACKS',
        export_nla_strips_merged_animation_name='Animation',
        export_def_bones=False,
        export_yup=True,
        export_texcoords=True,
        export_normals=True,
        export_materials='EXPORT',
    )
    print("Successfully exported GLB:", GLB_PATH)
    print("BONES:", [b.name for b in arm_obj.data.bones])
    print("MESHES:", [o.name for o in objs])
    print("MATERIALS:", [m.name for m in bpy.data.materials])
    print("ACTIONS:", [a.name for a in actions])

if __name__ == "__main__":
    main()
