import bpy
import bmesh
import math
import os
import base64
from mathutils import Vector, Matrix, Euler

BASE_DIR = r"c:\Users\yukis\Downloads\car-chase"
MODEL_DIR = os.path.join(BASE_DIR, "assets", "models")
os.makedirs(MODEL_DIR, exist_ok=True)
OUT_GLB = os.path.join(MODEL_DIR, "touge_cars.glb")

bpy.ops.wm.read_factory_settings(use_empty=True)

# ==============================================================================
# 1. AUTOMOTIVE PBR MATERIALS
# ==============================================================================
def make_mat(name, color, metallic=0.1, roughness=0.2, coat=0.0, coat_rough=0.05,
             emission=None, emission_strength=0.0, alpha=1.0):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if "Coat Weight" in bsdf.inputs:
        bsdf.inputs["Coat Weight"].default_value = coat
        bsdf.inputs["Coat Roughness"].default_value = coat_rough
    if emission and emission_strength > 0:
        if "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = (*emission, 1.0)
        if "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value = emission_strength
    if alpha < 1.0:
        bsdf.inputs["Alpha"].default_value = alpha
        if hasattr(mat, "blend_method"):
            mat.blend_method = 'BLEND'
    return mat

mats = {
    # Automotive Clearcoat Paints
    "AE86_White": make_mat("AE86_White", (0.95, 0.96, 0.97), metallic=0.08, roughness=0.14, coat=1.0, coat_rough=0.03),
    "AE86_PandaBlack": make_mat("AE86_PandaBlack", (0.022, 0.024, 0.028), metallic=0.06, roughness=0.24, coat=0.7, coat_rough=0.08),
    "R32_Gunmetal": make_mat("R32_Gunmetal", (0.17, 0.19, 0.22), metallic=0.84, roughness=0.17, coat=1.0, coat_rough=0.03),
    "RX7_Yellow": make_mat("RX7_Yellow", (0.98, 0.72, 0.03), metallic=0.32, roughness=0.14, coat=1.0, coat_rough=0.03),
    "EK9_White": make_mat("EK9_White", (0.94, 0.95, 0.93), metallic=0.06, roughness=0.13, coat=1.0, coat_rough=0.03),
    "GC8_Blue": make_mat("GC8_Blue", (0.03, 0.16, 0.68), metallic=0.85, roughness=0.14, coat=1.0, coat_rough=0.03),
    "TypeR_Red": make_mat("TypeR_Red", (0.86, 0.05, 0.05), metallic=0.25, roughness=0.18, coat=0.8),
    "STi_Cherry": make_mat("STi_Cherry", (0.88, 0.06, 0.35), metallic=0.22, roughness=0.20),

    # Trim, Rubber, Grille, Chrome
    "Trim_MatteBlack": make_mat("Trim_MatteBlack", (0.015, 0.017, 0.020), metallic=0.05, roughness=0.52),
    "Grille_Dark": make_mat("Grille_Dark", (0.008, 0.010, 0.012), metallic=0.15, roughness=0.45),
    "Chrome": make_mat("Chrome", (0.92, 0.94, 0.97), metallic=0.98, roughness=0.06),

    # Glass & Mirrors
    "Glass_Tinted": make_mat("Glass_Tinted", (0.03, 0.055, 0.075), metallic=0.15, roughness=0.03, coat=1.0, coat_rough=0.01, alpha=0.46),
    "Mirror_Glass": make_mat("Mirror_Glass", (0.90, 0.95, 0.98), metallic=1.0, roughness=0.02),

    # Interior Cabin
    "Interior_Dark": make_mat("Interior_Dark", (0.03, 0.033, 0.040), metallic=0.05, roughness=0.72),
    "Seat_Fabric": make_mat("Seat_Fabric", (0.05, 0.045, 0.050), metallic=0.02, roughness=0.85),
    "Seat_RedAccent": make_mat("Seat_RedAccent", (0.32, 0.055, 0.055), metallic=0.02, roughness=0.80),

    # Wheels, Tires & Brakes
    "Tire_Rubber": make_mat("Tire_Rubber", (0.020, 0.022, 0.025), metallic=0.03, roughness=0.76),
    "Watanabe_Gunmetal": make_mat("Watanabe_Gunmetal", (0.10, 0.105, 0.115), metallic=0.78, roughness=0.26),
    "Rim_PolishedLip": make_mat("Rim_PolishedLip", (0.90, 0.92, 0.95), metallic=0.97, roughness=0.08),
    "Rim_R32_Forged": make_mat("Rim_R32_Forged", (0.30, 0.32, 0.35), metallic=0.86, roughness=0.20),
    "Rim_RX7_Silver": make_mat("Rim_RX7_Silver", (0.82, 0.85, 0.89), metallic=0.92, roughness=0.15),
    "Rim_EK9_White": make_mat("Rim_EK9_White", (0.94, 0.95, 0.93), metallic=0.10, roughness=0.18, coat=0.6),
    "Rim_Subaru_Gold": make_mat("Rim_Subaru_Gold", (0.88, 0.72, 0.20), metallic=0.88, roughness=0.18, coat=0.8),
    "Brake_Rotor": make_mat("Brake_Rotor", (0.50, 0.52, 0.55), metallic=0.88, roughness=0.28),
    "Caliper_Gold": make_mat("Caliper_Gold", (0.85, 0.58, 0.08), metallic=0.75, roughness=0.25),
    "Caliper_Red": make_mat("Caliper_Red", (0.82, 0.06, 0.06), metallic=0.65, roughness=0.25),

    # Lamps & Plates
    "Headlight_Warm": make_mat("Headlight_Warm", (1.0, 0.96, 0.84), metallic=0.1, roughness=0.05,
                               emission=(1.0, 0.93, 0.74), emission_strength=6.5),
    "Fog_Yellow": make_mat("Fog_Yellow", (1.0, 0.82, 0.06), metallic=0.1, roughness=0.06,
                           emission=(1.0, 0.78, 0.04), emission_strength=6.2),
    "Turn_Amber": make_mat("Turn_Amber", (1.0, 0.44, 0.02), metallic=0.1, roughness=0.10,
                           emission=(1.0, 0.40, 0.01), emission_strength=3.6),
    "Taillight_Red": make_mat("Taillight_Red", (0.92, 0.03, 0.03), metallic=0.1, roughness=0.10,
                              emission=(1.0, 0.05, 0.03), emission_strength=4.8),
    "Reverse_White": make_mat("Reverse_White", (0.90, 0.93, 0.96), metallic=0.2, roughness=0.15,
                              emission=(0.9, 0.95, 1.0), emission_strength=1.5),
    "Plate_White": make_mat("Plate_White", (0.93, 0.95, 0.91), metallic=0.05, roughness=0.32),
}


# ==============================================================================
# 2. GEOMETRY HELPERS
# ==============================================================================
def wheel_arch_offset(y, z, fy=-1.30, ry=1.26, r_arch=0.37, z_center=0.33):
    for cy in (fy, ry):
        dy = y - cy
        if abs(dy) < r_arch:
            arch_top = z_center + math.sqrt(max(0.0, r_arch * r_arch - dy * dy))
            if z < arch_top:
                return arch_top
    return z


def add_box(bm, mat_idx, center, scale, rot_deg=(0, 0, 0)):
    rot = Euler([math.radians(a) for a in rot_deg], 'XYZ').to_matrix().to_4x4()
    m = Matrix.Translation(center) @ rot @ Matrix.Diagonal((*scale, 1.0))
    res = bmesh.ops.create_cube(bm, size=1.0, matrix=m)
    for v in res["verts"]:
        for f in v.link_faces:
            f.material_index = mat_idx
    return res


def add_cyl(bm, mat_idx, center, radius1, radius2, depth, segments=20, rot_deg=(0, 0, 0), cap=True):
    rot = Euler([math.radians(a) for a in rot_deg], 'XYZ').to_matrix().to_4x4()
    m = Matrix.Translation(center) @ rot
    res = bmesh.ops.create_cone(
        bm, cap_ends=cap, segments=segments,
        radius1=radius1, radius2=radius2, depth=depth, matrix=m
    )
    for v in res["verts"]:
        for f in v.link_faces:
            f.material_index = mat_idx
    return res


def add_strut(bm, mat_idx, p0, p1, w=0.04, h=0.04):
    """
    Creates an exact 3D rectangular beam connecting 3D point p0 to 3D point p1,
    guaranteed to align with the car's A-pillar, B-pillar, C-pillar, or wiper!
    """
    v0 = Vector(p0)
    v1 = Vector(p1)
    mid = (v0 + v1) * 0.5
    diff = v1 - v0
    length = diff.length
    if length < 1e-4:
        return
    quat = diff.to_track_quat('Y', 'Z')
    m = Matrix.Translation(mid) @ quat.to_matrix().to_4x4() @ Matrix.Diagonal((w, length, h, 1.0))
    res = bmesh.ops.create_cube(bm, size=1.0, matrix=m)
    for v in res["verts"]:
        for f in v.link_faces:
            f.material_index = mat_idx


def build_wheel_arch_flare(bm, mat_idx, cx_sign, cy, cz=0.33, radius=0.365, width_x=0.81, flare_out=0.045, thickness=0.042):
    steps = 18
    arch_rings = []
    for s in range(steps + 1):
        ang = math.pi * (s / steps)
        py = cy + math.cos(ang) * radius
        pz = cz + math.sin(ang) * radius
        py_out = cy + math.cos(ang) * (radius + thickness)
        pz_out = cz + math.sin(ang) * (radius + thickness)

        x_inner = cx_sign * (width_x - 0.16)
        x_body = cx_sign * width_x
        x_lip = cx_sign * (width_x + flare_out)

        v_in = bm.verts.new((x_inner, py, pz))
        v_lip_b = bm.verts.new((x_lip, py, pz))
        v_lip_t = bm.verts.new((x_lip * 0.99, py_out, pz_out))
        v_body = bm.verts.new((x_body * 0.985, py_out, pz_out + 0.015))
        arch_rings.append((v_in, v_lip_b, v_lip_t, v_body))

    for s in range(steps):
        a0, b0, c0, d0 = arch_rings[s]
        a1, b1, c1, d1 = arch_rings[s + 1]
        for quad in ((a0, b0, b1, a1), (b0, c0, c1, b1), (c0, d0, d1, c1)):
            try:
                f = bm.faces.new(quad if cx_sign > 0 else tuple(reversed(quad)))
                f.material_index = mat_idx
            except ValueError:
                pass


def build_interior_cabin(bm, idx_interior, idx_seat, idx_accent, idx_chrome, idx_mirror):
    # Cabin floor & rear parcel shelf
    add_box(bm, idx_interior, (0.0, 0.25, 0.34), (1.34, 1.60, 0.06))
    add_box(bm, idx_interior, (0.0, 1.22, 0.68), (1.28, 0.68, 0.07), rot_deg=(-6, 0, 0))
    add_box(bm, idx_interior, (0.0, 0.05, 0.44), (0.20, 1.30, 0.17))

    # Dashboard & RHD instrument binnacle (Right-Hand Drive = -X when car faces -Y)
    rhd_x = -0.35
    add_box(bm, idx_interior, (0.0, -0.45, 0.71), (1.34, 0.36, 0.20), rot_deg=(10, 0, 0))
    add_box(bm, idx_interior, (rhd_x, -0.39, 0.80), (0.32, 0.22, 0.11), rot_deg=(6, 0, 0))

    # RHD Steering Column & 3-Spoke Steering Wheel
    add_cyl(bm, idx_interior, (rhd_x, -0.29, 0.74), 0.032, 0.038, 0.26, segments=12, rot_deg=(68, 0, 0))
    sw_center = Vector((rhd_x, -0.17, 0.78))
    sw_r = 0.145
    for i in range(16):
        a0 = (i / 16) * math.tau
        px = sw_center.x + math.cos(a0) * sw_r
        pz = sw_center.z + math.sin(a0) * sw_r * 0.92
        py = sw_center.y + math.sin(a0) * sw_r * 0.35
        add_box(bm, idx_interior, (px, py, pz), (0.025, 0.025, 0.058), rot_deg=(22, math.degrees(a0), 0))
    for sp_ang in (-20, 90, 200):
        rad = math.radians(sp_ang)
        add_box(bm, idx_chrome,
                (sw_center.x + math.cos(rad) * 0.07, sw_center.y + math.sin(rad) * 0.02, sw_center.z + math.sin(rad) * 0.065),
                (0.020, 0.014, 0.13), rot_deg=(20, sp_ang, 0))

    # Gear Shifter
    add_cyl(bm, idx_chrome, (0.0, -0.14, 0.57), 0.011, 0.011, 0.15, segments=8, rot_deg=(-12, 0, 0))
    add_cyl(bm, idx_interior, (0.0, -0.16, 0.65), 0.024, 0.020, 0.045, segments=12)

    # Left & Right Sports Bucket Seats
    for sx in (-0.35, 0.35):
        add_box(bm, idx_seat, (sx, 0.22, 0.44), (0.42, 0.46, 0.09), rot_deg=(-6, 0, 0))
        for bx in (-0.18, 0.18):
            add_box(bm, idx_accent, (sx + bx, 0.20, 0.48), (0.065, 0.42, 0.08), rot_deg=(-6, 0, 0))
        add_box(bm, idx_seat, (sx, 0.43, 0.70), (0.40, 0.09, 0.48), rot_deg=(-16, 0, 0))
        for bx in (-0.18, 0.18):
            add_box(bm, idx_accent, (sx + bx, 0.39, 0.70), (0.065, 0.13, 0.44), rot_deg=(-16, 0, 0))
        add_box(bm, idx_seat, (sx, 0.50, 0.99), (0.22, 0.08, 0.16), rot_deg=(-12, 0, 0))

    # Interior Rear-View Mirror
    add_box(bm, idx_interior, (0.0, -0.18, 1.17), (0.025, 0.025, 0.07))
    add_box(bm, idx_mirror, (0.0, -0.16, 1.13), (0.19, 0.022, 0.05))


def finalize_smooth_with_sharp_creases(bm, mesh, angle_deg=36.0):
    """
    Splits edges sharper than `angle_deg` so smooth shading gives silky curved body panels
    AND crisp automotive creases on bumpers, pop-up lights, window frames, and spokes!
    """
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    sharp_edges = [
        e for e in bm.edges
        if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > math.radians(angle_deg)
    ]
    if sharp_edges:
        bmesh.ops.split_edges(bm, edges=sharp_edges)
    bm.to_mesh(mesh)
    bm.free()
    for p in mesh.polygons:
        p.use_smooth = True


def build_detailed_wheel(name, style="watanabe", is_left=True):
    bm = bmesh.new()
    spoke_mat = (
        mats["Watanabe_Gunmetal"] if style == "watanabe"
        else mats["Rim_R32_Forged"] if style == "r32"
        else mats["Rim_EK9_White"] if style == "ek9"
        else mats["Rim_Subaru_Gold"] if style == "subaru"
        else mats["Rim_RX7_Silver"]
    )
    caliper_mat = mats["Caliper_Red"] if style in ("rx7", "ek9") else mats["Caliper_Gold"]
    out_sign = -1.0 if is_left else 1.0

    # 1. Rounded-Shoulder Radial Tire
    tire_prof = [
        (0.205, -0.105),
        (0.245, -0.118),
        (0.295, -0.118),
        (0.322, -0.102),
        (0.328, -0.065),
        (0.328,  0.065),
        (0.322,  0.102),
        (0.295,  0.118),
        (0.245,  0.118),
        (0.205,  0.105),
    ]
    segs = 36
    ring_verts = []
    for s in range(segs):
        ang = (s / segs) * math.tau
        ca, sa = math.cos(ang), math.sin(ang)
        ring = [bm.verts.new((px, ca * r, sa * r)) for (r, px) in tire_prof]
        ring_verts.append(ring)

    for s in range(segs):
        r0 = ring_verts[s]
        r1 = ring_verts[(s + 1) % segs]
        for i in range(len(tire_prof) - 1):
            f = bm.faces.new((r0[i], r0[i + 1], r1[i + 1], r1[i]))
            f.material_index = 0

    # 2. Stepped Deep-Dish Polished Rim Lip
    rim_prof = [
        (0.210, out_sign * 0.110),
        (0.202, out_sign * 0.102),
        (0.188, out_sign * 0.082),
        (0.184, out_sign * 0.042),
        (0.184, -out_sign * 0.095),
    ]
    rim_rings = []
    for s in range(segs):
        ang = (s / segs) * math.tau
        ca, sa = math.cos(ang), math.sin(ang)
        ring = [bm.verts.new((px, ca * r, sa * r)) for (r, px) in rim_prof]
        rim_rings.append(ring)

    for s in range(segs):
        r0 = rim_rings[s]
        r1 = rim_rings[(s + 1) % segs]
        for i in range(len(rim_prof) - 1):
            quad = (r0[i], r0[i + 1], r1[i + 1], r1[i])
            f = bm.faces.new(quad if out_sign < 0 else tuple(reversed(quad)))
            f.material_index = 1

    # 3. Hub, Center Cap & Spokes
    add_cyl(bm, 2, (out_sign * 0.048, 0, 0), 0.068, 0.068, 0.045, segments=20, rot_deg=(0, 90, 0))
    add_cyl(bm, 5, (out_sign * 0.068, 0, 0), 0.028, 0.026, 0.025, segments=16, rot_deg=(0, 90, 0))

    if style == "watanabe":
        for k in range(8):
            ang = (k / 8) * math.tau
            cy, cz = math.cos(ang) * 0.122, math.sin(ang) * 0.122
            add_box(bm, 2, (out_sign * 0.056, cy, cz), (0.026, 0.128, 0.034), rot_deg=(math.degrees(ang), 0, out_sign * 6))
        for k in range(4):
            ang = (k / 4) * math.tau + 0.39
            add_cyl(bm, 5, (out_sign * 0.066, math.cos(ang) * 0.046, math.sin(ang) * 0.046),
                    0.009, 0.009, 0.018, segments=8, rot_deg=(0, 90, 0))
    elif style == "r32":
        for k in range(5):
            ang = (k / 5) * math.tau
            cy, cz = math.cos(ang) * 0.124, math.sin(ang) * 0.124
            add_box(bm, 2, (out_sign * 0.062, cy, cz), (0.028, 0.132, 0.052), rot_deg=(math.degrees(ang), 0, 0))
    elif style == "ek9":
        for k in range(5):
            ang = (k / 5) * math.tau
            cy, cz = math.cos(ang) * 0.124, math.sin(ang) * 0.124
            add_box(bm, 2, (out_sign * 0.060, cy, cz), (0.026, 0.128, 0.044), rot_deg=(math.degrees(ang), 0, 0))
            add_box(bm, 2, (out_sign * 0.063, cy * 0.88, cz * 0.88), (0.016, 0.065, 0.022), rot_deg=(math.degrees(ang), 0, 0))
        for k in range(5):
            ang = (k / 5) * math.tau + 0.314
            add_cyl(bm, 5, (out_sign * 0.066, math.cos(ang) * 0.046, math.sin(ang) * 0.046),
                    0.008, 0.008, 0.018, segments=8, rot_deg=(0, 90, 0))
    elif style == "subaru":
        for k in range(10):
            ang = (k / 10) * math.tau
            cy, cz = math.cos(ang) * 0.124, math.sin(ang) * 0.124
            add_box(bm, 2, (out_sign * 0.058, cy, cz), (0.024, 0.126, 0.028), rot_deg=(math.degrees(ang), 0, out_sign * 3))
        for k in range(5):
            ang = (k / 5) * math.tau
            add_cyl(bm, 5, (out_sign * 0.066, math.cos(ang) * 0.046, math.sin(ang) * 0.046),
                    0.008, 0.008, 0.018, segments=8, rot_deg=(0, 90, 0))
    else:
        for k in range(5):
            for offset_ang in (-0.11, 0.11):
                ang = (k / 5) * math.tau + offset_ang
                cy, cz = math.cos(ang) * 0.125, math.sin(ang) * 0.125
                add_box(bm, 2, (out_sign * 0.062, cy, cz), (0.024, 0.134, 0.024), rot_deg=(math.degrees(ang), 0, 0))

    # 4. Brake Rotor, Backing Dust Shield & Caliper
    add_cyl(bm, 3, (out_sign * 0.012, 0, 0), 0.152, 0.152, 0.022, segments=24, rot_deg=(0, 90, 0))
    add_cyl(bm, 0, (-out_sign * 0.015, 0, 0), 0.175, 0.175, 0.015, segments=24, rot_deg=(0, 90, 0))
    add_box(bm, 4, (out_sign * 0.022, 0.105, 0.065), (0.048, 0.075, 0.115), rot_deg=(-32, 0, 0))

    w_mesh = bpy.data.meshes.new(name)
    for m in (mats["Tire_Rubber"], mats["Rim_PolishedLip"], spoke_mat, mats["Brake_Rotor"], caliper_mat, mats["Chrome"]):
        w_mesh.materials.append(m)
    finalize_smooth_with_sharp_creases(bm, w_mesh, angle_deg=38.0)
    return w_mesh


# ==============================================================================
# 3. CAR #1: TOYOTA AE86 SPRINTER TRUENO GT-APEX 3-DOOR (Reference Photo Match!)
# ==============================================================================
def build_car_ae86():
    parent = bpy.data.objects.new("Car_AE86", None)
    bpy.context.collection.objects.link(parent)

    bm = bmesh.new()
    body_mats = [
        mats["AE86_White"], mats["AE86_PandaBlack"], mats["Trim_MatteBlack"],
        mats["Glass_Tinted"], mats["Headlight_Warm"], mats["Fog_Yellow"],
        mats["Turn_Amber"], mats["Taillight_Red"], mats["Reverse_White"],
        mats["Plate_White"], mats["Chrome"], mats["Mirror_Glass"],
        mats["Interior_Dark"], mats["Seat_Fabric"], mats["Seat_RedAccent"]
    ]

    stations = [
        (-2.12, 0.24, 0.49, 0.56, 0.57, 0.72, 0.76, 0.74, 0.68, 'nose'),
        (-2.00, 0.22, 0.50, 0.61, 0.63, 0.76, 0.80, 0.78, 0.71, 'nose'),
        (-1.72, 0.21, 0.52, 0.67, 0.70, 0.78, 0.83, 0.80, 0.73, 'hood'),
        (-1.50, 0.21, 0.53, 0.71, 0.74, 0.79, 0.84, 0.81, 0.74, 'hood'),
        (-1.30, 0.21, 0.54, 0.74, 0.77, 0.79, 0.84, 0.82, 0.75, 'hood'),
        (-1.08, 0.21, 0.54, 0.76, 0.79, 0.79, 0.84, 0.82, 0.75, 'hood'),
        (-0.72, 0.20, 0.54, 0.78, 0.82, 0.80, 0.84, 0.82, 0.76, 'hood'),
        (-0.62, 0.20, 0.54, 0.79, 0.84, 0.80, 0.84, 0.82, 0.75, 'windshield'),
        (-0.18, 0.20, 0.54, 0.80, 1.27, 0.80, 0.84, 0.82, 0.65, 'cabin'),
        ( 0.28, 0.20, 0.54, 0.81, 1.28, 0.80, 0.84, 0.82, 0.65, 'cabin'),
        ( 0.78, 0.20, 0.55, 0.82, 1.26, 0.80, 0.84, 0.82, 0.65, 'cabin'),
        ( 1.06, 0.21, 0.55, 0.83, 1.17, 0.79, 0.84, 0.81, 0.66, 'hatch'),
        ( 1.26, 0.21, 0.56, 0.84, 1.08, 0.79, 0.84, 0.81, 0.68, 'hatch'),
        ( 1.56, 0.22, 0.56, 0.84, 0.96, 0.79, 0.84, 0.80, 0.69, 'hatch'),
        ( 1.88, 0.24, 0.56, 0.83, 0.85, 0.77, 0.81, 0.78, 0.70, 'tail'),
        ( 2.10, 0.27, 0.56, 0.79, 0.81, 0.74, 0.78, 0.75, 0.68, 'tail'),
    ]

    rings = []
    for (y, zb, zp, zs, zr, wb, wf, ws, wr, zone) in stations:
        zb_arch = wheel_arch_offset(y, zb, fy=-1.30, ry=1.26, r_arch=0.365, z_center=0.33)
        zp_arch = max(zp, zb_arch + 0.03)
        pts = [
            (-wb * 0.70, y, 0.22),
            ( wb * 0.70, y, 0.22),
            ( wb,        y, zb_arch),
            ( wf,        y, zp_arch),
            ( ws,        y, zs - 0.04),
            ( ws * 0.98, y, zs),
            ( wr,        y, zr),
            ( 0.0,       y, zr + 0.022),
            (-wr,        y, zr),
            (-ws * 0.98, y, zs),
            (-ws,        y, zs - 0.04),
            (-wf,        y, zp_arch),
            (-wb,        y, zb_arch),
        ]
        rings.append(([bm.verts.new(p) for p in pts], zone))

    n_ring = len(rings[0][0])
    for r in range(len(rings) - 1):
        r0, z0 = rings[r]
        r1, z1 = rings[r + 1]
        for i in range(n_ring):
            v1, v2, v3, v4 = r0[i], r0[(i + 1) % n_ring], r1[(i + 1) % n_ring], r1[i]
            f = bm.faces.new((v1, v2, v3, v4))
            if i in (0, 12):
                f.material_index = 2
            elif i in (1, 2, 11):
                f.material_index = 1  # Panda lower black
            elif i in (5, 8):
                if (z0 == 'windshield' and z1 == 'cabin') or (z0 == 'cabin' and z1 in ('cabin', 'hatch')) or (z0 == 'hatch' and z1 == 'hatch'):
                    f.material_index = 3  # Side glass windows
                else:
                    f.material_index = 0
            elif i in (6, 7):
                if (z0 == 'windshield' and z1 == 'cabin') or (z0 == 'cabin' and z1 == 'hatch') or (z0 == 'hatch' and z1 == 'hatch'):
                    f.material_index = 3  # Windshield & Rear Hatch Glass
                else:
                    f.material_index = 0  # Solid White Hood & Solid White Roof!
            else:
                f.material_index = 0

    f_front = bm.faces.new(reversed(rings[0][0]))
    f_front.material_index = 1
    f_rear = bm.faces.new(rings[-1][0])
    f_rear.material_index = 1

    # Inner dark wheelhouse boxes + Sculpted Black Fender Arch Flares
    for wy in (-1.30, 1.26):
        add_box(bm, 2, (0.0, wy, 0.38), (1.30, 0.74, 0.44))
    for sx in (-1.0, 1.0):
        build_wheel_arch_flare(bm, 1, sx, -1.30, cz=0.33, radius=0.365, width_x=0.81, flare_out=0.045)
        build_wheel_arch_flare(bm, 1, sx,  1.26, cz=0.33, radius=0.365, width_x=0.81, flare_out=0.045)

    # Black Side Rub Strip (`サイドモール`) & Door Handle + Keyhole
    for sx in (-0.842, 0.842):
        add_box(bm, 1, (sx, -0.02, 0.555), (0.018, 1.75, 0.042))
        add_box(bm, 2, (sx * 0.995, 0.32, 0.73), (0.024, 0.13, 0.034))
        add_cyl(bm, 10, (sx * 1.002, 0.36, 0.68), 0.008, 0.008, 0.015, segments=8, rot_deg=(0, 90, 0))

    # Precision-Aligned Greenhouse Pillars & Window Frames using `add_strut`!
    for sx in (-1.0, 1.0):
        # A-pillar: connects (-0.80, -0.62, 0.80) at base of windshield to (-0.65, -0.18, 1.27) at front roof corner!
        add_strut(bm, 0, (sx * 0.80, -0.62, 0.80), (sx * 0.65, -0.18, 1.27), w=0.046, h=0.044)
        add_strut(bm, 2, (sx * 0.79, -0.62, 0.79), (sx * 0.64, -0.18, 1.26), w=0.052, h=0.028)
        # Roof side rail & smoked rain visor: connects (-0.65, -0.18, 1.27) to (-0.65, 0.78, 1.26)
        add_strut(bm, 0, (sx * 0.65, -0.18, 1.27), (sx * 0.65, 0.78, 1.26), w=0.045, h=0.036)
        add_strut(bm, 2, (sx * 0.675, -0.36, 1.12), (sx * 0.67, 0.34, 1.25), w=0.024, h=0.028)
        # B-pillar: vertical black pillar dividing front door window and rear quarter window at y = 0.32
        add_strut(bm, 2, (sx * 0.80, 0.32, 0.81), (sx * 0.65, 0.34, 1.27), w=0.034, h=0.068)
        # Rear quarter window diagonal divider (matching AE86 3-door quarter glass!)
        add_strut(bm, 2, (sx * 0.79, 1.26, 0.84), (sx * 0.65, 0.78, 1.26), w=0.032, h=0.048)
        # Wide White AE86 Hatchback C-pillar: connects (0.65, 0.78, 1.26) to (0.78, 1.62, 0.92)
        add_strut(bm, 0, (sx * 0.65, 0.78, 1.26), (sx * 0.78, 1.62, 0.92), w=0.055, h=0.095)
        # Lower window weatherstrip sill along door & quarter window
        add_strut(bm, 2, (sx * 0.805, -0.60, 0.80), (sx * 0.795, 1.26, 0.84), w=0.024, h=0.024)

        # Side Wing Mirrors (`ドアミラー`) mounted cleanly at front corner of door window
        add_box(bm, 2, (sx * 0.82, -0.46, 0.83), (0.08, 0.05, 0.032))
        add_box(bm, 1, (sx * 0.89, -0.44, 0.85), (0.14, 0.085, 0.092))
        add_box(bm, 11, (sx * 0.89, -0.395, 0.85), (0.115, 0.01, 0.072))

    # Top & Bottom Windshield Black Rubber Trim + Twin Wipers
    add_strut(bm, 2, (-0.65, -0.18, 1.27), (0.65, -0.18, 1.27), w=0.035, h=0.028)
    add_strut(bm, 2, (-0.79, -0.62, 0.82), (0.79, -0.62, 0.82), w=0.042, h=0.025)
    # Twin Windshield Wipers lying flush against lower windshield
    add_strut(bm, 2, (-0.52, -0.60, 0.83), (-0.04, -0.52, 0.90), w=0.022, h=0.018)
    add_strut(bm, 2, ( 0.02, -0.60, 0.83), ( 0.50, -0.52, 0.90), w=0.022, h=0.018)
    # Hood washer nozzles
    for nx in (-0.26, 0.26):
        add_box(bm, 2, (nx, -0.95, 0.79), (0.018, 0.025, 0.014))

    # ICONIC AE86 POP-UP RETRACTABLE HEADLIGHTS (`リトラクタブル・ヘッドライト`)
    for sx in (-0.52, 0.52):
        # Matte black pop-up housing & white top cover lid
        add_box(bm, 2, (sx, -1.93, 0.66), (0.24, 0.22, 0.145), rot_deg=(3, 0, 0))
        add_box(bm, 0, (sx, -1.92, 0.738), (0.25, 0.23, 0.020), rot_deg=(4, 0, 0))
        # Chrome inner reflector rim & warm halogen glowing bulb lens
        add_box(bm, 10, (sx, -2.042, 0.658), (0.20, 0.015, 0.115))
        add_box(bm, 4,  (sx, -2.048, 0.658), (0.175, 0.015, 0.095))

    # Front Wrap-Around Bumper (front face at y = -2.18) + White Bumper Stripe + Lower Chin Lip
    add_box(bm, 1, (0.0, -2.11, 0.42), (1.54, 0.14, 0.20))
    # White body-colored bumper band (`白ライン`) proud on the upper bumper
    add_box(bm, 0, (0.0, -2.13, 0.485), (1.52, 0.12, 0.052))
    # Lower black chin spoiler (`チンスポイラー`)
    add_box(bm, 1, (0.0, -2.10, 0.27), (1.46, 0.12, 0.08))

    # Proud Front Fascia Details at y = -2.195 so they are 100% visible!
    # Center "TRUENO" grille slot & white lettering badge
    add_box(bm, 2, (0.0, -2.188, 0.485), (0.56, 0.02, 0.044))
    add_box(bm, 9, (0.0, -2.198, 0.485), (0.16, 0.01, 0.020))

    for sx in (-1.0, 1.0):
        # Corner amber blinker wrapping front fender next to pop-up headlight
        add_box(bm, 6, (sx * 0.735, -1.97, 0.585), (0.09, 0.15, 0.052))
        # Front bumper amber turn signal lamp embedded in white bumper stripe!
        add_box(bm, 6, (sx * 0.50, -2.192, 0.485), (0.18, 0.02, 0.044))
        # Yellow CIBIE Fog Lamps mounted below the bumper (`黄色フォグランプ` matching reference photo!)
        add_box(bm, 2, (sx * 0.41, -2.155, 0.325), (0.165, 0.06, 0.092))
        add_box(bm, 5, (sx * 0.41, -2.188, 0.325), (0.142, 0.015, 0.074))

    # Front & Rear Japanese License Plates
    add_box(bm, 2, (0.0, -2.185, 0.365), (0.34, 0.02, 0.165), rot_deg=(6, 0, 0))
    add_box(bm, 9, (0.0, -2.195, 0.365), (0.32, 0.015, 0.150), rot_deg=(6, 0, 0))
    add_box(bm, 9, (0.0,  2.135, 0.52),  (0.32, 0.015, 0.150))

    # Rear Bumper, Sprinter Trueno Taillights, Rear Ducktail Lip & Exhaust Muffler
    add_box(bm, 1, (0.0, 2.08, 0.43), (1.52, 0.12, 0.20))
    add_box(bm, 2, (0.0, 2.105, 0.69), (1.44, 0.03, 0.14))
    for sx in (-0.50, 0.50):
        add_box(bm, 7, (sx, 2.122, 0.71), (0.36, 0.02, 0.075))
        add_box(bm, 6, (sx, 2.122, 0.64), (0.22, 0.02, 0.052))
        add_box(bm, 8, (sx * 0.66, 2.122, 0.64), (0.11, 0.02, 0.052))
    add_box(bm, 1, (0.0, 1.98, 0.855), (1.36, 0.11, 0.042), rot_deg=(-8, 0, 0))
    add_cyl(bm, 10, (-0.46, 2.02, 0.27), 0.052, 0.052, 0.28, segments=16, rot_deg=(88, 0, 0))

    # Full RHD Interior Cabin
    build_interior_cabin(bm, 12, 13, 14, 10, 11)

    mesh = bpy.data.meshes.new("Car_AE86_Body")
    for m in body_mats:
        mesh.materials.append(m)
    finalize_smooth_with_sharp_creases(bm, mesh, angle_deg=35.0)

    body_obj = bpy.data.objects.new("Car_AE86_Body", mesh)
    bpy.context.collection.objects.link(body_obj)
    body_obj.parent = parent

    w_mesh_L = build_detailed_wheel("AE86_Watanabe_L", style="watanabe", is_left=True)
    w_mesh_R = build_detailed_wheel("AE86_Watanabe_R", style="watanabe", is_left=False)
    for tag, wx, wy, wz, m_w in (
        ("FL", -0.75, -1.30, 0.328, w_mesh_L),
        ("FR",  0.75, -1.30, 0.328, w_mesh_R),
        ("RL", -0.75,  1.26, 0.328, w_mesh_L),
        ("RR",  0.75,  1.26, 0.328, w_mesh_R),
    ):
        w_obj = bpy.data.objects.new(f"Car_AE86_Wheel_{tag}", m_w)
        bpy.context.collection.objects.link(w_obj)
        w_obj.location = (wx, wy, wz)
        w_obj.parent = parent

    return parent


# ==============================================================================
# 4. CAR #2: NISSAN SKYLINE GT-R (BNR32) - GUNMETAL GREY METALLIC
# ==============================================================================
def build_car_r32():
    parent = bpy.data.objects.new("Car_R32", None)
    bpy.context.collection.objects.link(parent)

    bm = bmesh.new()
    body_mats = [
        mats["R32_Gunmetal"], mats["Trim_MatteBlack"], mats["Grille_Dark"],
        mats["Glass_Tinted"], mats["Headlight_Warm"], mats["Turn_Amber"],
        mats["Taillight_Red"], mats["Reverse_White"], mats["Plate_White"],
        mats["Chrome"], mats["Mirror_Glass"], mats["Interior_Dark"],
        mats["Seat_Fabric"], mats["Seat_RedAccent"]
    ]

    stations = [
        (-2.14, 0.22, 0.48, 0.58, 0.60, 0.78, 0.83, 0.80, 0.74, 'nose'),
        (-1.96, 0.21, 0.50, 0.64, 0.67, 0.81, 0.86, 0.83, 0.76, 'nose'),
        (-1.60, 0.20, 0.52, 0.70, 0.74, 0.83, 0.88, 0.85, 0.78, 'hood'),
        (-1.30, 0.20, 0.53, 0.73, 0.77, 0.83, 0.89, 0.86, 0.79, 'hood'),
        (-0.98, 0.20, 0.53, 0.75, 0.79, 0.83, 0.88, 0.86, 0.79, 'hood'),
        (-0.60, 0.20, 0.54, 0.78, 0.83, 0.83, 0.87, 0.85, 0.78, 'windshield'),
        (-0.12, 0.20, 0.54, 0.79, 1.25, 0.83, 0.87, 0.85, 0.67, 'cabin'),
        ( 0.42, 0.20, 0.54, 0.80, 1.26, 0.83, 0.87, 0.85, 0.67, 'cabin'),
        ( 0.86, 0.20, 0.55, 0.81, 1.22, 0.83, 0.88, 0.85, 0.68, 'cabin'),
        ( 1.26, 0.21, 0.56, 0.83, 0.86, 0.84, 0.89, 0.86, 0.78, 'trunk'),
        ( 1.72, 0.22, 0.56, 0.82, 0.85, 0.82, 0.87, 0.84, 0.77, 'trunk'),
        ( 2.12, 0.25, 0.56, 0.78, 0.82, 0.78, 0.82, 0.80, 0.74, 'tail'),
    ]

    rings = []
    for (y, zb, zp, zs, zr, wb, wf, ws, wr, zone) in stations:
        zb_arch = wheel_arch_offset(y, zb, fy=-1.30, ry=1.26, r_arch=0.37, z_center=0.33)
        zp_arch = max(zp, zb_arch + 0.03)
        pts = [
            (-wb * 0.70, y, 0.21),
            ( wb * 0.70, y, 0.21),
            ( wb,        y, zb_arch),
            ( wf,        y, zp_arch),
            ( ws,        y, zs - 0.04),
            ( ws * 0.98, y, zs),
            ( wr,        y, zr),
            ( 0.0,       y, zr + 0.02),
            (-wr,        y, zr),
            (-ws * 0.98, y, zs),
            (-ws,        y, zs - 0.04),
            (-wf,        y, zp_arch),
            (-wb,        y, zb_arch),
        ]
        rings.append(([bm.verts.new(p) for p in pts], zone))

    n_ring = len(rings[0][0])
    for r in range(len(rings) - 1):
        r0, z0 = rings[r]
        r1, z1 = rings[r + 1]
        for i in range(n_ring):
            v1, v2, v3, v4 = r0[i], r0[(i + 1) % n_ring], r1[(i + 1) % n_ring], r1[i]
            f = bm.faces.new((v1, v2, v3, v4))
            if i in (0, 12):
                f.material_index = 1
            elif i in (5, 8) and ((z0 == 'windshield' and z1 == 'cabin') or (z0 == 'cabin' and z1 in ('cabin', 'trunk'))):
                f.material_index = 3
            elif i in (6, 7) and ((z0 == 'windshield' and z1 == 'cabin') or (z0 == 'cabin' and z1 == 'trunk')):
                f.material_index = 3
            else:
                f.material_index = 0

    f_front = bm.faces.new(reversed(rings[0][0]))
    f_front.material_index = 0
    f_rear = bm.faces.new(rings[-1][0])
    f_rear.material_index = 0

    for wy in (-1.30, 1.26):
        add_box(bm, 1, (0.0, wy, 0.38), (1.36, 0.76, 0.44))
    for sx in (-1.0, 1.0):
        build_wheel_arch_flare(bm, 0, sx, -1.30, cz=0.33, radius=0.37, width_x=0.84, flare_out=0.042)
        build_wheel_arch_flare(bm, 0, sx,  1.26, cz=0.33, radius=0.37, width_x=0.84, flare_out=0.045)
        # Precision-aligned R32 A/B/C pillars & roof rail
        add_strut(bm, 0, (sx * 0.83, -0.60, 0.78), (sx * 0.67, -0.12, 1.25), w=0.046, h=0.044)
        add_strut(bm, 0, (sx * 0.67, -0.12, 1.25), (sx * 0.68,  0.86, 1.22), w=0.046, h=0.036)
        add_strut(bm, 1, (sx * 0.83,  0.35, 0.80), (sx * 0.67,  0.36, 1.25), w=0.034, h=0.068)
        add_strut(bm, 0, (sx * 0.68,  0.86, 1.22), (sx * 0.84,  1.26, 0.83), w=0.055, h=0.088)
        add_box(bm, 0, (sx * 0.92, -0.44, 0.84), (0.15, 0.09, 0.09))
        add_box(bm, 10, (sx * 0.92, -0.394, 0.84), (0.12, 0.01, 0.07))

    # Front GT-R Grille, Intercooler Opening, Headlights & Corner Blinkers
    add_box(bm, 2, (0.0, -2.155, 0.60), (0.64, 0.05, 0.08))
    add_box(bm, 2, (0.0, -2.155, 0.35), (0.86, 0.08, 0.16))
    add_box(bm, 9, (0.0, -2.14,  0.35), (0.72, 0.04, 0.13))
    for sx in (-1.0, 1.0):
        add_box(bm, 4, (sx * 0.52, -2.15, 0.60), (0.32, 0.06, 0.105))
        add_box(bm, 5, (sx * 0.73, -2.11, 0.60), (0.12, 0.10, 0.105))

    # Iconic R32 Quad Round Taillights + Rear GT-R Wing + Twin Exhaust
    for sx in (-0.64, -0.43, 0.43, 0.64):
        add_cyl(bm, 1, (sx, 2.13, 0.69), 0.082, 0.082, 0.05, segments=20, rot_deg=(90, 0, 0))
        add_cyl(bm, 6, (sx, 2.142, 0.69), 0.070, 0.070, 0.04, segments=20, rot_deg=(90, 0, 0))
    add_box(bm, 8, (0.0, -2.17, 0.44), (0.33, 0.02, 0.15))
    add_box(bm, 8, (0.0,  2.14, 0.50), (0.33, 0.02, 0.15))

    add_box(bm, 0, (0.0, 1.98, 1.02), (1.52, 0.25, 0.042), rot_deg=(5, 0, 0))
    for sx in (-0.68, 0.68):
        add_box(bm, 0, (sx, 1.98, 0.92), (0.048, 0.24, 0.19))
    for ex in (-0.54, -0.42):
        add_cyl(bm, 9, (ex, 2.06, 0.27), 0.045, 0.045, 0.26, segments=16, rot_deg=(88, 0, 0))

    build_interior_cabin(bm, 11, 12, 13, 9, 10)

    mesh = bpy.data.meshes.new("Car_R32_Body")
    for m in body_mats:
        mesh.materials.append(m)
    finalize_smooth_with_sharp_creases(bm, mesh, angle_deg=35.0)

    body_obj = bpy.data.objects.new("Car_R32_Body", mesh)
    bpy.context.collection.objects.link(body_obj)
    body_obj.parent = parent

    w_mesh_L = build_detailed_wheel("R32_Wheel_L", style="r32", is_left=True)
    w_mesh_R = build_detailed_wheel("R32_Wheel_R", style="r32", is_left=False)
    for tag, wx, wy, wz, m_w in (
        ("FL", -0.78, -1.30, 0.328, w_mesh_L),
        ("FR",  0.78, -1.30, 0.328, w_mesh_R),
        ("RL", -0.78,  1.26, 0.328, w_mesh_L),
        ("RR",  0.78,  1.26, 0.328, w_mesh_R),
    ):
        w_obj = bpy.data.objects.new(f"Car_R32_Wheel_{tag}", m_w)
        bpy.context.collection.objects.link(w_obj)
        w_obj.location = (wx, wy, wz)
        w_obj.parent = parent

    return parent


# ==============================================================================
# 5. CAR #3: MAZDA RX-7 (FD3S TYPE R) - COMPETITION YELLOW MICA
# ==============================================================================
def build_car_rx7():
    parent = bpy.data.objects.new("Car_RX7", None)
    bpy.context.collection.objects.link(parent)

    bm = bmesh.new()
    body_mats = [
        mats["RX7_Yellow"], mats["Trim_MatteBlack"], mats["Grille_Dark"],
        mats["Glass_Tinted"], mats["Headlight_Warm"], mats["Turn_Amber"],
        mats["Taillight_Red"], mats["Plate_White"], mats["Chrome"],
        mats["Mirror_Glass"], mats["Interior_Dark"], mats["Seat_Fabric"],
        mats["Seat_RedAccent"]
    ]

    stations = [
        (-2.14, 0.22, 0.42, 0.50, 0.52, 0.72, 0.78, 0.75, 0.66, 'nose'),
        (-1.92, 0.20, 0.45, 0.57, 0.60, 0.78, 0.84, 0.81, 0.72, 'nose'),
        (-1.55, 0.19, 0.48, 0.65, 0.69, 0.82, 0.89, 0.86, 0.76, 'hood'),
        (-1.30, 0.19, 0.50, 0.69, 0.73, 0.83, 0.90, 0.87, 0.78, 'hood'),
        (-0.92, 0.19, 0.51, 0.72, 0.76, 0.82, 0.88, 0.86, 0.78, 'hood'),
        (-0.52, 0.19, 0.52, 0.74, 0.79, 0.82, 0.87, 0.85, 0.76, 'windshield'),
        ( 0.04, 0.19, 0.52, 0.75, 1.19, 0.82, 0.88, 0.85, 0.63, 'cabin'),
        ( 0.58, 0.20, 0.53, 0.76, 1.18, 0.83, 0.89, 0.86, 0.63, 'cabin'),
        ( 1.02, 0.20, 0.54, 0.78, 1.06, 0.84, 0.90, 0.87, 0.66, 'hatch'),
        ( 1.26, 0.20, 0.55, 0.79, 0.96, 0.84, 0.90, 0.87, 0.69, 'hatch'),
        ( 1.68, 0.22, 0.55, 0.78, 0.84, 0.81, 0.86, 0.83, 0.72, 'tail'),
        ( 2.08, 0.25, 0.54, 0.73, 0.77, 0.75, 0.80, 0.77, 0.68, 'tail'),
    ]

    rings = []
    for (y, zb, zp, zs, zr, wb, wf, ws, wr, zone) in stations:
        zb_arch = wheel_arch_offset(y, zb, fy=-1.30, ry=1.26, r_arch=0.37, z_center=0.33)
        zp_arch = max(zp, zb_arch + 0.03)
        pts = [
            (-wb * 0.70, y, 0.20),
            ( wb * 0.70, y, 0.20),
            ( wb,        y, zb_arch),
            ( wf,        y, zp_arch),
            ( ws,        y, zs - 0.03),
            ( ws * 0.98, y, zs),
            ( wr,        y, zr),
            ( 0.0,       y, zr + 0.025),
            (-wr,        y, zr),
            (-ws * 0.98, y, zs),
            (-ws,        y, zs - 0.03),
            (-wf,        y, zp_arch),
            (-wb,        y, zb_arch),
        ]
        rings.append(([bm.verts.new(p) for p in pts], zone))

    n_ring = len(rings[0][0])
    for r in range(len(rings) - 1):
        r0, z0 = rings[r]
        r1, z1 = rings[r + 1]
        for i in range(n_ring):
            v1, v2, v3, v4 = r0[i], r0[(i + 1) % n_ring], r1[(i + 1) % n_ring], r1[i]
            f = bm.faces.new((v1, v2, v3, v4))
            if i in (0, 12):
                f.material_index = 1
            elif i in (5, 8) and ((z0 == 'windshield' and z1 == 'cabin') or (z0 == 'cabin' and z1 in ('cabin', 'hatch'))):
                f.material_index = 3
            elif i in (6, 7) and ((z0 == 'windshield' and z1 == 'cabin') or (z0 == 'cabin' and z1 == 'hatch') or (z0 == 'hatch' and z1 == 'hatch')):
                f.material_index = 3
            else:
                f.material_index = 0

    f_front = bm.faces.new(reversed(rings[0][0]))
    f_front.material_index = 0
    f_rear = bm.faces.new(rings[-1][0])
    f_rear.material_index = 0

    for wy in (-1.30, 1.26):
        add_box(bm, 1, (0.0, wy, 0.38), (1.36, 0.76, 0.44))
    for sx in (-1.0, 1.0):
        build_wheel_arch_flare(bm, 0, sx, -1.30, cz=0.33, radius=0.37, width_x=0.85, flare_out=0.038)
        build_wheel_arch_flare(bm, 0, sx,  1.26, cz=0.33, radius=0.37, width_x=0.85, flare_out=0.042)
        # Precision-aligned FD3S A/B/C pillars & roof rail
        add_strut(bm, 1, (sx * 0.83, -0.52, 0.74), (sx * 0.63, 0.04, 1.19), w=0.042, h=0.040)
        add_strut(bm, 0, (sx * 0.63,  0.04, 1.19), (sx * 0.63, 0.58, 1.18), w=0.044, h=0.034)
        add_strut(bm, 1, (sx * 0.84,  0.46, 0.76), (sx * 0.63, 0.48, 1.18), w=0.034, h=0.064)
        add_strut(bm, 0, (sx * 0.63,  0.58, 1.18), (sx * 0.81, 1.48, 0.88), w=0.052, h=0.075)
        add_box(bm, 0, (sx * 0.91, -0.38, 0.79), (0.14, 0.09, 0.075), rot_deg=(0, 0, sx * 8))
        add_box(bm, 9, (sx * 0.91, -0.334, 0.79), (0.11, 0.01, 0.058))

    # Front nose mouth, black chin splitter, combination lamps & license plate
    add_box(bm, 2, (0.0, -2.13, 0.34), (0.76, 0.08, 0.13))
    add_box(bm, 1, (0.0, -2.14, 0.24), (1.48, 0.14, 0.05))
    add_box(bm, 7, (0.0, -2.16, 0.39), (0.32, 0.02, 0.145), rot_deg=(8, 0, 0))
    for sx in (-1.0, 1.0):
        add_box(bm, 4, (sx * 0.54, -2.11, 0.46), (0.24, 0.06, 0.065), rot_deg=(0, 0, sx * -10))
        add_box(bm, 5, (sx * 0.68, -2.06, 0.46), (0.10, 0.06, 0.065), rot_deg=(0, 0, sx * -14))
        add_box(bm, 2, (sx * 0.58, -2.09, 0.32), (0.22, 0.08, 0.09))

    # Rear FD3S Smoked Capsule Taillight Bar + High Rear Wing + Exhaust
    add_box(bm, 1, (0.0, 2.09, 0.68), (1.42, 0.05, 0.11))
    for sx in (-0.48, 0.48):
        add_box(bm, 6, (sx, 2.102, 0.68), (0.34, 0.03, 0.075))
    add_box(bm, 7, (0.0, 2.10, 0.46), (0.32, 0.02, 0.15))

    add_box(bm, 0, (0.0, 1.94, 0.96), (1.44, 0.22, 0.04), rot_deg=(6, 0, 0))
    for sx in (-0.58, 0.58):
        add_box(bm, 0, (sx, 1.94, 0.86), (0.045, 0.20, 0.17))
    add_cyl(bm, 8, (0.48, 2.04, 0.26), 0.055, 0.055, 0.26, segments=16, rot_deg=(88, 0, 0))

    build_interior_cabin(bm, 10, 11, 12, 8, 9)

    mesh = bpy.data.meshes.new("Car_RX7_Body")
    for m in body_mats:
        mesh.materials.append(m)
    finalize_smooth_with_sharp_creases(bm, mesh, angle_deg=35.0)

    body_obj = bpy.data.objects.new("Car_RX7_Body", mesh)
    bpy.context.collection.objects.link(body_obj)
    body_obj.parent = parent

    w_mesh_L = build_detailed_wheel("RX7_Wheel_L", style="rx7", is_left=True)
    w_mesh_R = build_detailed_wheel("RX7_Wheel_R", style="rx7", is_left=False)
    for tag, wx, wy, wz, m_w in (
        ("FL", -0.78, -1.30, 0.328, w_mesh_L),
        ("FR",  0.78, -1.30, 0.328, w_mesh_R),
        ("RL", -0.78,  1.26, 0.328, w_mesh_L),
        ("RR",  0.78,  1.26, 0.328, w_mesh_R),
    ):
        w_obj = bpy.data.objects.new(f"Car_RX7_Wheel_{tag}", m_w)
        bpy.context.collection.objects.link(w_obj)
        w_obj.location = (wx, wy, wz)
        w_obj.parent = parent

    return parent


# ==============================================================================
# 6. CAR #4: HONDA CIVIC TYPE R (EK9) - CHAMPIONSHIP WHITE HOT-HATCH
# ==============================================================================
def build_car_ek9():
    parent = bpy.data.objects.new("Car_EK9", None)
    bpy.context.collection.objects.link(parent)

    bm = bmesh.new()
    body_mats = [
        mats["EK9_White"], mats["Trim_MatteBlack"], mats["Grille_Dark"],
        mats["Glass_Tinted"], mats["Headlight_Warm"], mats["Turn_Amber"],
        mats["Taillight_Red"], mats["Reverse_White"], mats["Plate_White"],
        mats["Chrome"], mats["Mirror_Glass"], mats["Interior_Dark"],
        mats["Seat_Fabric"], mats["Seat_RedAccent"], mats["TypeR_Red"]
    ]

    stations = [
        (-2.02, 0.22, 0.44, 0.54, 0.58, 0.74, 0.78, 0.76, 0.70, 'nose'),
        (-1.80, 0.21, 0.48, 0.60, 0.64, 0.77, 0.81, 0.79, 0.72, 'nose'),
        (-1.52, 0.20, 0.50, 0.66, 0.70, 0.79, 0.83, 0.81, 0.74, 'hood'),
        (-1.26, 0.20, 0.51, 0.70, 0.74, 0.80, 0.84, 0.82, 0.75, 'hood'),
        (-0.92, 0.20, 0.51, 0.72, 0.76, 0.80, 0.84, 0.82, 0.75, 'hood'),
        (-0.52, 0.20, 0.52, 0.75, 0.80, 0.80, 0.84, 0.82, 0.74, 'windshield'),
        (-0.06, 0.20, 0.52, 0.76, 1.25, 0.80, 0.84, 0.82, 0.65, 'cabin'),
        ( 0.46, 0.20, 0.52, 0.77, 1.26, 0.80, 0.84, 0.82, 0.65, 'cabin'),
        ( 0.94, 0.20, 0.53, 0.78, 1.24, 0.81, 0.85, 0.82, 0.65, 'cabin'),
        ( 1.22, 0.21, 0.54, 0.79, 1.21, 0.81, 0.85, 0.82, 0.65, 'hatch'),
        ( 1.50, 0.22, 0.55, 0.78, 1.02, 0.79, 0.84, 0.81, 0.67, 'hatch'),
        ( 1.80, 0.25, 0.55, 0.75, 0.78, 0.76, 0.80, 0.78, 0.70, 'tail'),
    ]

    rings = []
    for (y, zb, zp, zs, zr, wb, wf, ws, wr, zone) in stations:
        zb_arch = wheel_arch_offset(y, zb, fy=-1.26, ry=1.20, r_arch=0.36, z_center=0.33)
        zp_arch = max(zp, zb_arch + 0.03)
        pts = [
            (-wb * 0.70, y, 0.21),
            ( wb * 0.70, y, 0.21),
            ( wb,        y, zb_arch),
            ( wf,        y, zp_arch),
            ( ws,        y, zs - 0.04),
            ( ws * 0.98, y, zs),
            ( wr,        y, zr),
            ( 0.0,       y, zr + 0.02),
            (-wr,        y, zr),
            (-ws * 0.98, y, zs),
            (-ws,        y, zs - 0.04),
            (-wf,        y, zp_arch),
            (-wb,        y, zb_arch),
        ]
        rings.append(([bm.verts.new(p) for p in pts], zone))

    n_ring = len(rings[0][0])
    for r in range(len(rings) - 1):
        r0, z0 = rings[r]
        r1, z1 = rings[r + 1]
        for i in range(n_ring):
            v1, v2, v3, v4 = r0[i], r0[(i + 1) % n_ring], r1[(i + 1) % n_ring], r1[i]
            f = bm.faces.new((v1, v2, v3, v4))
            if i in (0, 12):
                f.material_index = 1
            elif i in (5, 8) and ((z0 == 'windshield' and z1 == 'cabin') or (z0 == 'cabin' and z1 in ('cabin', 'hatch'))):
                f.material_index = 3
            elif i in (6, 7) and ((z0 == 'windshield' and z1 == 'cabin') or (z0 == 'hatch' and z1 == 'tail')):
                f.material_index = 3
            else:
                f.material_index = 0

    f_front = bm.faces.new(reversed(rings[0][0]))
    f_front.material_index = 0
    f_rear = bm.faces.new(rings[-1][0])
    f_rear.material_index = 0

    for wy in (-1.26, 1.20):
        add_box(bm, 1, (0.0, wy, 0.38), (1.34, 0.74, 0.44))
    for sx in (-1.0, 1.0):
        build_wheel_arch_flare(bm, 0, sx, -1.26, cz=0.33, radius=0.36, width_x=0.81, flare_out=0.038)
        build_wheel_arch_flare(bm, 0, sx,  1.20, cz=0.33, radius=0.36, width_x=0.81, flare_out=0.040)
        # Civic Pillars
        add_strut(bm, 0, (sx * 0.80, -0.52, 0.75), (sx * 0.65, -0.06, 1.25), w=0.044, h=0.042)
        add_strut(bm, 0, (sx * 0.65, -0.06, 1.25), (sx * 0.65,  1.22, 1.21), w=0.044, h=0.034)
        add_strut(bm, 1, (sx * 0.81,  0.42, 0.77), (sx * 0.65,  0.42, 1.25), w=0.034, h=0.065)
        # Rear Hatch Strut
        add_strut(bm, 0, (sx * 0.65,  1.22, 1.21), (sx * 0.78,  1.80, 0.76), w=0.052, h=0.082)
        # Side Mirrors
        add_box(bm, 0, (sx * 0.90, -0.38, 0.82), (0.14, 0.08, 0.08))
        add_box(bm, 10, (sx * 0.90, -0.334, 0.82), (0.11, 0.01, 0.06))

    # EK9 Front Fascia: Angled Composite Headlights + Honeycomb Grille + Red 'H' Badge
    for sx in (-1.0, 1.0):
        add_box(bm, 4, (sx * 0.50, -2.00, 0.58), (0.30, 0.08, 0.11), rot_deg=(-4, 0, sx * -10))
        add_box(bm, 5, (sx * 0.68, -1.94, 0.58), (0.10, 0.10, 0.10), rot_deg=(-4, 0, sx * -10))

    # Front Grille with Red Honda Type R Badge
    add_box(bm, 2, (0.0, -2.03, 0.55), (0.44, 0.05, 0.075))
    add_box(bm, 14, (0.0, -2.05, 0.55), (0.09, 0.02, 0.06))

    # Lower front air dam & Type R front chin spoiler
    add_box(bm, 2, (0.0, -2.01, 0.36), (0.76, 0.06, 0.11))
    add_box(bm, 0, (0.0, -2.04, 0.24), (1.46, 0.10, 0.042))

    # Iconic EK9 Type R High-Rise Roof Spoiler
    add_box(bm, 0, (0.0, 1.34, 1.28), (1.18, 0.28, 0.038), rot_deg=(-8, 0, 0))
    for sx in (-0.56, 0.56):
        add_box(bm, 0, (sx, 1.32, 1.24), (0.04, 0.22, 0.10))

    # Rear Vertical EK9 Taillights + License Plate + Sport Exhaust
    for sx in (-0.62, 0.62):
        add_box(bm, 6, (sx, 1.815, 0.68), (0.17, 0.03, 0.12))
        add_box(bm, 7, (sx, 1.815, 0.58), (0.17, 0.03, 0.06))
    add_box(bm, 8, (0.0, -2.045, 0.42), (0.32, 0.02, 0.14))
    add_box(bm, 8, (0.0,  1.82, 0.50), (0.32, 0.02, 0.14))
    add_box(bm, 14, (0.0, 1.82, 0.66), (0.08, 0.015, 0.055))

    # Single large-bore racing exhaust on right
    add_cyl(bm, 9, (0.44, 1.78, 0.26), 0.048, 0.048, 0.22, segments=16, rot_deg=(88, 0, 0))

    # Red Recaro Sports Bucket Seats & Cabin
    build_interior_cabin(bm, 11, 12, 13, 9, 10)

    mesh = bpy.data.meshes.new("Car_EK9_Body")
    for m in body_mats:
        mesh.materials.append(m)
    finalize_smooth_with_sharp_creases(bm, mesh, angle_deg=35.0)

    body_obj = bpy.data.objects.new("Car_EK9_Body", mesh)
    bpy.context.collection.objects.link(body_obj)
    body_obj.parent = parent

    w_mesh_L = build_detailed_wheel("EK9_Wheel_L", style="ek9", is_left=True)
    w_mesh_R = build_detailed_wheel("EK9_Wheel_R", style="ek9", is_left=False)
    for tag, wx, wy, wz, m_w in (
        ("FL", -0.76, -1.26, 0.325, w_mesh_L),
        ("FR",  0.76, -1.26, 0.325, w_mesh_R),
        ("RL", -0.76,  1.20, 0.325, w_mesh_L),
        ("RR",  0.76,  1.20, 0.325, w_mesh_R),
    ):
        w_obj = bpy.data.objects.new(f"Car_EK9_Wheel_{tag}", m_w)
        bpy.context.collection.objects.link(w_obj)
        w_obj.location = (wx, wy, wz)
        w_obj.parent = parent

    return parent


# ==============================================================================
# 7. CAR #5: SUBARU IMPREZA WRX STI (GC8) - WR BLUE MICA & GOLD RALLY WHEELS
# ==============================================================================
def build_car_gc8():
    parent = bpy.data.objects.new("Car_GC8", None)
    bpy.context.collection.objects.link(parent)

    bm = bmesh.new()
    body_mats = [
        mats["GC8_Blue"], mats["Trim_MatteBlack"], mats["Grille_Dark"],
        mats["Glass_Tinted"], mats["Headlight_Warm"], mats["Turn_Amber"],
        mats["Taillight_Red"], mats["Reverse_White"], mats["Plate_White"],
        mats["Chrome"], mats["Mirror_Glass"], mats["Interior_Dark"],
        mats["Seat_Fabric"], mats["Seat_RedAccent"], mats["STi_Cherry"]
    ]

    stations = [
        (-2.14, 0.22, 0.46, 0.56, 0.60, 0.77, 0.82, 0.80, 0.74, 'nose'),
        (-1.96, 0.21, 0.48, 0.62, 0.66, 0.80, 0.86, 0.83, 0.76, 'nose'),
        (-1.60, 0.20, 0.51, 0.68, 0.73, 0.82, 0.88, 0.85, 0.78, 'hood'),
        (-1.28, 0.20, 0.52, 0.71, 0.76, 0.83, 0.89, 0.86, 0.79, 'hood'),
        (-0.95, 0.20, 0.52, 0.73, 0.78, 0.83, 0.88, 0.86, 0.79, 'hood'),
        (-0.58, 0.20, 0.53, 0.76, 0.82, 0.83, 0.87, 0.85, 0.78, 'windshield'),
        (-0.10, 0.20, 0.53, 0.77, 1.25, 0.83, 0.87, 0.85, 0.67, 'cabin'),
        ( 0.44, 0.20, 0.53, 0.78, 1.26, 0.83, 0.87, 0.85, 0.67, 'cabin'),
        ( 0.88, 0.20, 0.54, 0.79, 1.22, 0.83, 0.88, 0.85, 0.68, 'cabin'),
        ( 1.24, 0.21, 0.55, 0.81, 0.86, 0.84, 0.89, 0.86, 0.78, 'trunk'),
        ( 1.70, 0.22, 0.55, 0.80, 0.84, 0.82, 0.87, 0.84, 0.77, 'trunk'),
        ( 2.10, 0.25, 0.55, 0.76, 0.80, 0.78, 0.82, 0.80, 0.74, 'tail'),
    ]

    rings = []
    for (y, zb, zp, zs, zr, wb, wf, ws, wr, zone) in stations:
        zb_arch = wheel_arch_offset(y, zb, fy=-1.28, ry=1.24, r_arch=0.37, z_center=0.33)
        zp_arch = max(zp, zb_arch + 0.03)
        pts = [
            (-wb * 0.70, y, 0.21),
            ( wb * 0.70, y, 0.21),
            ( wb,        y, zb_arch),
            ( wf,        y, zp_arch),
            ( ws,        y, zs - 0.04),
            ( ws * 0.98, y, zs),
            ( wr,        y, zr),
            ( 0.0,       y, zr + 0.02),
            (-wr,        y, zr),
            (-ws * 0.98, y, zs),
            (-ws,        y, zs - 0.04),
            (-wf,        y, zp_arch),
            (-wb,        y, zb_arch),
        ]
        rings.append(([bm.verts.new(p) for p in pts], zone))

    n_ring = len(rings[0][0])
    for r in range(len(rings) - 1):
        r0, z0 = rings[r]
        r1, z1 = rings[r + 1]
        for i in range(n_ring):
            v1, v2, v3, v4 = r0[i], r0[(i + 1) % n_ring], r1[(i + 1) % n_ring], r1[i]
            f = bm.faces.new((v1, v2, v3, v4))
            if i in (0, 12):
                f.material_index = 1
            elif i in (5, 8) and ((z0 == 'windshield' and z1 == 'cabin') or (z0 == 'cabin' and z1 in ('cabin', 'trunk'))):
                f.material_index = 3
            elif i in (6, 7) and ((z0 == 'windshield' and z1 == 'cabin') or (z0 == 'cabin' and z1 == 'trunk')):
                f.material_index = 3
            else:
                f.material_index = 0

    f_front = bm.faces.new(reversed(rings[0][0]))
    f_front.material_index = 0
    f_rear = bm.faces.new(rings[-1][0])
    f_rear.material_index = 0

    for wy in (-1.28, 1.24):
        add_box(bm, 1, (0.0, wy, 0.38), (1.36, 0.76, 0.44))
    for sx in (-1.0, 1.0):
        # 22B Style Widebody Flared Arches
        build_wheel_arch_flare(bm, 0, sx, -1.28, cz=0.33, radius=0.37, width_x=0.84, flare_out=0.048)
        build_wheel_arch_flare(bm, 0, sx,  1.24, cz=0.33, radius=0.37, width_x=0.84, flare_out=0.052)
        # GC8 Pillars
        add_strut(bm, 0, (sx * 0.83, -0.58, 0.76), (sx * 0.67, -0.10, 1.25), w=0.046, h=0.044)
        add_strut(bm, 0, (sx * 0.67, -0.10, 1.25), (sx * 0.68,  0.88, 1.22), w=0.046, h=0.036)
        add_strut(bm, 1, (sx * 0.83,  0.35, 0.78), (sx * 0.67,  0.36, 1.25), w=0.034, h=0.068)
        add_strut(bm, 0, (sx * 0.68,  0.88, 1.22), (sx * 0.84,  1.24, 0.81), w=0.055, h=0.088)
        # Side Mirrors
        add_box(bm, 0, (sx * 0.92, -0.42, 0.84), (0.15, 0.09, 0.09))
        add_box(bm, 10, (sx * 0.92, -0.374, 0.84), (0.12, 0.01, 0.07))

    # Prominent Subaru WRX STi Functional Hood Scoop
    add_box(bm, 0, (0.0, -1.14, 0.83), (0.42, 0.36, 0.08), rot_deg=(-6, 0, 0))
    add_box(bm, 2, (0.0, -1.30, 0.81), (0.34, 0.06, 0.045))
    # Dual hood extractor vents
    for sx in (-0.38, 0.38):
        add_box(bm, 2, (sx, -1.40, 0.74), (0.16, 0.22, 0.015), rot_deg=(-5, 0, sx * 8))

    # Front Grille & Rectangular Rally Headlights
    add_box(bm, 2, (0.0, -2.13, 0.58), (0.58, 0.04, 0.085))
    add_box(bm, 14, (0.14, -2.145, 0.58), (0.09, 0.02, 0.045))
    for sx in (-1.0, 1.0):
        add_box(bm, 4, (sx * 0.52, -2.12, 0.58), (0.28, 0.06, 0.105))
        add_box(bm, 5, (sx * 0.72, -2.08, 0.58), (0.11, 0.09, 0.105))

    # Giant Circular Rally Fog Light Covers with STi Branding
    for sx in (-0.52, 0.52):
        add_cyl(bm, 0, (sx, -2.09, 0.40), 0.11, 0.11, 0.04, segments=20, rot_deg=(90, 0, 0))
        add_cyl(bm, 14, (sx, -2.115, 0.40), 0.05, 0.05, 0.015, segments=12, rot_deg=(90, 0, 0))

    # Front Lower Air Dam & Lip Splitter
    add_box(bm, 2, (0.0, -2.11, 0.34), (0.80, 0.06, 0.12))
    add_box(bm, 0, (0.0, -2.14, 0.24), (1.50, 0.10, 0.04))

    # WRC High-Rise Rear Wing Spoiler
    for sx in (-0.48, 0.48):
        add_box(bm, 0, (sx, 1.84, 1.05), (0.045, 0.24, 0.38), rot_deg=(10, 0, 0))
    add_box(bm, 0, (0.0, 1.88, 1.25), (1.40, 0.26, 0.042), rot_deg=(5, 0, 0))
    for sx in (-0.70, 0.70):
        add_box(bm, 0, (sx, 1.88, 1.22), (0.035, 0.30, 0.18))

    # Distinct GC8 Trapezoidal Taillights & Plates
    for sx in (-0.56, 0.56):
        add_box(bm, 6, (sx, 2.11, 0.66), (0.34, 0.03, 0.12))
        add_box(bm, 7, (sx, 2.11, 0.58), (0.16, 0.03, 0.06))
    add_box(bm, 8, (0.0, -2.15, 0.44), (0.33, 0.02, 0.15))
    add_box(bm, 8, (0.0,  2.12, 0.50), (0.33, 0.02, 0.15))
    add_box(bm, 14, (0.34, 2.12, 0.66), (0.08, 0.02, 0.045))

    # Stainless Rally Exhaust on Right
    add_cyl(bm, 9, (0.50, 2.05, 0.26), 0.055, 0.055, 0.25, segments=16, rot_deg=(88, 0, 0))

    build_interior_cabin(bm, 11, 12, 13, 9, 10)

    mesh = bpy.data.meshes.new("Car_GC8_Body")
    for m in body_mats:
        mesh.materials.append(m)
    finalize_smooth_with_sharp_creases(bm, mesh, angle_deg=35.0)

    body_obj = bpy.data.objects.new("Car_GC8_Body", mesh)
    bpy.context.collection.objects.link(body_obj)
    body_obj.parent = parent

    w_mesh_L = build_detailed_wheel("GC8_Wheel_L", style="subaru", is_left=True)
    w_mesh_R = build_detailed_wheel("GC8_Wheel_R", style="subaru", is_left=False)
    for tag, wx, wy, wz, m_w in (
        ("FL", -0.78, -1.28, 0.328, w_mesh_L),
        ("FR",  0.78, -1.28, 0.328, w_mesh_R),
        ("RL", -0.78,  1.24, 0.328, w_mesh_L),
        ("RR",  0.78,  1.24, 0.328, w_mesh_R),
    ):
        w_obj = bpy.data.objects.new(f"Car_GC8_Wheel_{tag}", m_w)
        bpy.context.collection.objects.link(w_obj)
        w_obj.location = (wx, wy, wz)
        w_obj.parent = parent

    return parent


# Build & Export all 5 cars
ae86 = build_car_ae86()
r32 = build_car_r32()
rx7 = build_car_rx7()
ek9 = build_car_ek9()
gc8 = build_car_gc8()

bpy.ops.export_scene.gltf(
    filepath=OUT_GLB,
    export_format='GLB',
    export_apply=True,
    export_materials='EXPORT'
)
print("Exported high-detail touge_cars.glb:", os.path.getsize(OUT_GLB), "bytes")

with open(OUT_GLB, "rb") as f:
    touge_b64 = base64.b64encode(f.read()).decode("ascii")

bundle_path = os.path.join(BASE_DIR, "assets", "game_bundle.js")
with open(bundle_path, "r", encoding="utf-8") as f:
    lines = [ln for ln in f.read().splitlines() if not ln.startswith("window.__TOUGE_CARS_B64__")]

lines.append(f'window.__TOUGE_CARS_B64__ = "{touge_b64}";')
with open(bundle_path, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")

print("Updated window.__TOUGE_CARS_B64__ in assets/game_bundle.js")
