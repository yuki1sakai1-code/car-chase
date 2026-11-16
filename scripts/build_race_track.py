import bpy
import bmesh
import json
import math
import os
from mathutils import Vector

# ==============================================================================
# OUTPUT PATHS
# ==============================================================================
WORKSPACE_DIR = r"c:\Users\yukis\Downloads\car-chase"
GLB_OUT_PATH = os.path.join(WORKSPACE_DIR, "assets", "models", "race_track.glb")
JSON_OUT_PATH = os.path.join(WORKSPACE_DIR, "assets", "track_data.json")
ASPHALT_TEX_PATH = os.path.join(WORKSPACE_DIR, "assets", "textures", "track_asphalt_2k.png")

TRACK_WIDTH = 11.0
HALF_WIDTH = TRACK_WIDTH * 0.5  # 5.5m
ROAD_THICKNESS = 0.45
CURB_WIDTH = 0.85
CURB_HEIGHT = 0.22
RAIL_HEIGHT = 1.05  # height above curb
DESK_SURFACE_Y = 0.35
NUM_SAMPLES = 600


# ==============================================================================
# 1. COORDINATE CONVERSION & SPLINE MATH
# ==============================================================================
# Three.js (x, y, z) -> Blender (x_bl = x, y_bl = -z, z_bl = y)
# When exported by Blender's glTF exporter (+Y Up enabled), Blender (x_bl, y_bl, z_bl)
# becomes glTF/Three.js (x_bl, z_bl, -y_bl) = (x, y, z) with 100.0% precision!
def th_to_bl(v):
    return Vector((v[0], -v[2], v[1]))


def catmull_rom_point(p0, p1, p2, p3, t):
    """Standard uniform Catmull-Rom interpolation on Vector inputs."""
    t2 = t * t
    t3 = t2 * t
    return 0.5 * (
        (2.0 * p1)
        + (-p0 + p2) * t
        + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t2
        + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t3
    )


def smooth_periodic_vec(vecs, passes=6):
    arr = [v.copy() for v in vecs]
    n = len(arr)
    for _ in range(passes):
        arr = [
            0.25 * arr[(i - 1) % n] + 0.5 * arr[i] + 0.25 * arr[(i + 1) % n]
            for i in range(n)
        ]
    return arr


def smooth_periodic(values, passes=8):
    arr = list(values)
    n = len(arr)
    for _ in range(passes):
        arr = [
            0.25 * arr[(i - 1) % n] + 0.5 * arr[i] + 0.25 * arr[(i + 1) % n]
            for i in range(n)
        ]
    return arr


def build_spline_data(num_samples=NUM_SAMPLES):
    # Control points in Three.js (x, y, z) space:
    # Start/Finish is at index 0: (0, 0.55, 54) facing +X (1, 0, 0).
    # Apexes are shaped so minimum turn radius > 9.5m everywhere (zero inner curb pinching)
    # and all non-adjacent segments have > 18m clearance.
    control_points_th = [
        # 1. Main Start/Finish Straight (フラットなメイン直線ストレート: Z=54, Y=0.55)
        (-30.0, 0.55, 54.0),
        (-10.0, 0.55, 54.0),
        (10.0, 0.55, 54.0),
        (30.0, 0.55, 54.0),
        (50.0, 0.55, 54.0),

        # 2. Corner 1: East Sweeper (第1コーナー・上りアプローチ)
        (70.0, 1.2, 52.0),
        (85.0, 2.8, 42.0),
        (92.0, 4.8, 26.0),

        # 3. Straight 2: East Hillclimb Straight (東側・登り急坂ストレート: X=92)
        (92.0, 7.5, 10.0),
        (92.0, 11.0, -8.0),
        (92.0, 14.5, -26.0),
        (90.0, 16.8, -42.0),

        # 4. Corner 2: Summit Hairpin (山頂ヘアピン)
        (82.0, 17.8, -58.0),
        (68.0, 18.2, -68.0),
        (50.0, 18.2, -70.0),

        # 5. Straight 3: Summit Ridge Straight (山頂フラットストレート: Z=-70, Y=18)
        (30.0, 18.0, -70.0),
        (10.0, 18.0, -70.0),
        (-10.0, 17.8, -70.0),
        (-30.0, 17.2, -68.0),

        # 6. Corner 3: Mountain Technical Hairpin (山腹ヘアピン・S字)
        (-48.0, 16.0, -62.0),
        (-62.0, 14.5, -50.0),
        (-58.0, 13.2, -34.0),
        (-68.0, 11.8, -20.0),

        # 7. Straight 4: West Downhill Plunge Straight (西側・急坂下りストレート: X=-72)
        (-72.0, 10.2, -6.0),
        (-72.0, 6.8, 12.0),
        (-72.0, 3.5, 30.0),
        (-70.0, 1.8, 42.0),

        # 8. Corner 4: Final Sweeper (最終コーナー)
        (-62.0, 1.2, 50.0),
        (-48.0, 0.75, 54.0),
    ]

    cps = [Vector(pt) for pt in control_points_th]
    num_cp = len(cps)

    # 1. Oversample closed Catmull-Rom curve
    substeps = 240
    dense_pts = []
    for i in range(num_cp):
        p0 = cps[(i - 1) % num_cp]
        p1 = cps[i]
        p2 = cps[(i + 1) % num_cp]
        p3 = cps[(i + 2) % num_cp]
        for s in range(substeps):
            t = s / float(substeps)
            dense_pts.append(catmull_rom_point(p0, p1, p2, p3, t))

    # 2. First uniform arc-length resampling
    num_dense = len(dense_pts)
    cum_len = [0.0] * (num_dense + 1)
    for i in range(num_dense):
        cum_len[i + 1] = cum_len[i] + (dense_pts[(i + 1) % num_dense] - dense_pts[i]).length
    total_len_raw = cum_len[num_dense]

    sampled_pos = []
    idx = 0
    for k in range(num_samples):
        target_s = (k / float(num_samples)) * total_len_raw
        while idx < num_dense - 1 and cum_len[idx + 1] < target_s:
            idx += 1
        seg_len = cum_len[idx + 1] - cum_len[idx]
        alpha = (target_s - cum_len[idx]) / seg_len if seg_len > 1e-8 else 0.0
        sampled_pos.append(dense_pts[idx].lerp(dense_pts[(idx + 1) % num_dense], alpha))

    # Apply gentle C2 curvature relaxation away from the Start/Finish straight
    # plus targeted apex relaxation so minimum radius of curvature is > 9.0m everywhere
    # (preventing any inner curb/guardrail pinching at 6.35m offset).
    smoothed = smooth_periodic_vec(sampled_pos, passes=18)
    for i in range(num_samples):
        dist_from_start = min(i, num_samples - i)
        w = min(1.0, (dist_from_start / 20.0) ** 2)
        sampled_pos[i] = sampled_pos[i].lerp(smoothed[i], w)

    for _ in range(45):
        next_pos = [p.copy() for p in sampled_pos]
        for i in range(num_samples):
            if min(i, num_samples - i) < 12:
                continue
            p_prev = sampled_pos[(i - 3) % num_samples]
            p_curr = sampled_pos[i]
            p_next = sampled_pos[(i + 3) % num_samples]
            v1 = p_curr - p_prev
            v2 = p_next - p_curr
            if v1.length > 1e-5 and v2.length > 1e-5:
                local_k = (v2.normalized() - v1.normalized()).length / (0.5 * (v1.length + v2.length))
                if local_k > 0.095:
                    mid = 0.5 * (sampled_pos[(i - 1) % num_samples] + sampled_pos[(i + 1) % num_samples])
                    next_pos[i] = p_curr.lerp(mid, 0.45)
        sampled_pos = next_pos

    # Re-parameterize by exact arc length after smoothing so step spacing is 100% uniform
    re_cum = [0.0] * (num_samples + 1)
    for i in range(num_samples):
        re_cum[i + 1] = re_cum[i] + (sampled_pos[(i + 1) % num_samples] - sampled_pos[i]).length
    total_length = re_cum[num_samples]

    uniform_pos = []
    sampled_s = []
    idx = 0
    for k in range(num_samples):
        target_s = (k / float(num_samples)) * total_length
        while idx < num_samples - 1 and re_cum[idx + 1] < target_s:
            idx += 1
        seg_len = re_cum[idx + 1] - re_cum[idx]
        alpha = (target_s - re_cum[idx]) / seg_len if seg_len > 1e-8 else 0.0
        uniform_pos.append(sampled_pos[idx].lerp(sampled_pos[(idx + 1) % num_samples], alpha))
        sampled_s.append(target_s)

    sampled_pos = uniform_pos

    # 3. Compute tangents, unbanked normals/binormals, curvature, and smooth banking
    tangents = []
    b0_list = []
    n0_list = []
    world_up = Vector((0.0, 1.0, 0.0))

    for i in range(num_samples):
        p_prev = sampled_pos[(i - 1) % num_samples]
        p_next = sampled_pos[(i + 1) % num_samples]
        t_vec = (p_next - p_prev).normalized()
        tangents.append(t_vec)

        b0 = t_vec.cross(world_up)
        if b0.length < 1e-6:
            b0 = Vector((0.0, 0.0, 1.0))
        else:
            b0.normalize()
        n0 = b0.cross(t_vec).normalized()
        b0_list.append(b0)
        n0_list.append(n0)

    ds = total_length / float(num_samples)
    raw_curvatures = []
    raw_banks = []
    max_bank = 0.175  # rad (~10 deg), within ±0.18 rad

    for i in range(num_samples):
        t_prev = tangents[(i - 2) % num_samples]
        t_next = tangents[(i + 2) % num_samples]
        dt_ds = (t_next - t_prev) / (4.0 * ds)
        curv = dt_ds.dot(b0_list[i])
        raw_curvatures.append(curv)

        target_bank = max(-max_bank, min(max_bank, -curv * 3.8))
        raw_banks.append(target_bank)

    curvatures = smooth_periodic(raw_curvatures, passes=8)
    banks = smooth_periodic(raw_banks, passes=24)

    # Keep Start/Finish straight completely flat (bank = 0)
    for i in range(num_samples):
        dist_from_start = min(i, num_samples - i)
        if dist_from_start < 18:
            fade = (dist_from_start / 18.0) ** 2
            banks[i] *= fade

    points_data = []
    for i in range(num_samples):
        pos = sampled_pos[i]
        t_vec = tangents[i]
        b0 = b0_list[i]
        n0 = n0_list[i]
        bank = banks[i]
        cb = math.cos(bank)
        sb = math.sin(bank)

        b_vec = (b0 * cb + n0 * sb).normalized()
        n_vec = (-b0 * sb + n0 * cb).normalized()

        points_data.append({
            "pos": pos,
            "t": t_vec,
            "n": n_vec,
            "b": b_vec,
            "s": sampled_s[i],
            "bank": bank,
            "curvature": curvatures[i],
        })

    return points_data, total_length


# ==============================================================================
# 2. PROCEDURAL 2K ASPHALT TEXTURE & PBR MATERIALS
# ==============================================================================
def generate_asphalt_texture(filepath):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    width, height = 1024, 1024
    img = bpy.data.images.new("Asphalt_2K_Tex", width=width, height=height, alpha=False)

    # Create dark, fine-grained asphalt texture with subtle aggregate variation
    # and slightly darker wheel-track wear bands
    pixels = [0.0] * (width * height * 4)
    for y in range(height):
        for x in range(width):
            u = x / float(width)
            # Deterministic fast hash noise for asphalt grain
            h1 = ((x * 374761393 + y * 668265263) ^ 0x5BF03635) & 0xFFFFFFFF
            h1 = ((h1 ^ (h1 >> 13)) * 1274126177) & 0xFFFFFFFF
            noise1 = ((h1 & 0xFFFF) / 65535.0) - 0.5

            x2, y2 = x // 2, y // 2
            h2 = ((x2 * 1103515245 + y2 * 12345) ^ 0x31415926) & 0xFFFFFFFF
            h2 = ((h2 ^ (h2 >> 11)) * 2654435761) & 0xFFFFFFFF
            noise2 = ((h2 & 0xFFFF) / 65535.0) - 0.5

            # Subtle racing line / tire wear darkening around u=0.28 and u=0.72
            wear1 = math.exp(-((u - 0.28) / 0.14) ** 2)
            wear2 = math.exp(-((u - 0.72) / 0.14) ** 2)
            wear = 1.0 - 0.12 * max(wear1, wear2)

            base = (0.125 + 0.032 * noise1 + 0.018 * noise2) * wear
            # Occasional bright micro-aggregate fleck
            if (h1 & 0xFF) > 248:
                base += 0.045

            r = max(0.04, min(0.30, base * 0.96))
            g = max(0.04, min(0.30, base * 0.98))
            b = max(0.04, min(0.32, base * 1.04))

            idx = (y * width + x) * 4
            pixels[idx] = r
            pixels[idx + 1] = g
            pixels[idx + 2] = b
            pixels[idx + 3] = 1.0

    img.pixels.foreach_set(pixels)
    img.filepath_raw = filepath
    img.file_format = "PNG"
    img.save()
    img.pack()
    return img


def make_pbr_material(name, base_color, roughness=0.5, metallic=0.0, emission_color=None, emission_strength=0.0, base_tex=None):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    out_node = nodes.new(type="ShaderNodeOutputMaterial")
    out_node.location = (400, 0)

    bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
    bsdf.location = (100, 0)
    bsdf.inputs["Base Color"].default_value = (*base_color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic

    if emission_color is not None and emission_strength > 0.0:
        if "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = (*emission_color, 1.0)
        elif "Emission" in bsdf.inputs:
            bsdf.inputs["Emission"].default_value = (*emission_color, 1.0)
        if "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value = emission_strength

    if base_tex is not None:
        tex_node = nodes.new(type="ShaderNodeTexImage")
        tex_node.image = base_tex
        tex_node.location = (-250, 0)
        links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])

    links.new(bsdf.outputs["BSDF"], out_node.inputs["Surface"])
    return mat


def create_all_materials():
    asphalt_img = generate_asphalt_texture(ASPHALT_TEX_PATH)
    mats = {
        "Mat_Asphalt": make_pbr_material(
            "Mat_Asphalt", (0.12, 0.125, 0.14), roughness=0.82, metallic=0.04, base_tex=asphalt_img
        ),
        "Mat_LaneLine_White": make_pbr_material(
            "Mat_LaneLine_White", (0.95, 0.96, 0.98), roughness=0.32, metallic=0.05,
            emission_color=(0.92, 0.95, 1.0), emission_strength=0.18
        ),
        "Mat_Road_Underside": make_pbr_material(
            "Mat_Road_Underside", (0.05, 0.055, 0.068), roughness=0.42, metallic=0.78
        ),
        "Mat_Curb_Red": make_pbr_material(
            "Mat_Curb_Red", (0.902, 0.180, 0.145), roughness=0.38, metallic=0.06  # #e62e25
        ),
        "Mat_Curb_White": make_pbr_material(
            "Mat_Curb_White", (0.957, 0.957, 0.973), roughness=0.35, metallic=0.05  # #f4f4f8
        ),
        "Mat_Guardrail_Metal": make_pbr_material(
            "Mat_Guardrail_Metal", (0.28, 0.25, 0.34), roughness=0.28, metallic=0.85
        ),
        "Mat_Guardrail_Neon_Cyan": make_pbr_material(
            "Mat_Guardrail_Neon_Cyan", (0.78, 0.72, 0.92), roughness=0.20, metallic=0.65,
            emission_color=(0.55, 0.45, 0.85), emission_strength=0.65
        ),
        "Mat_Guardrail_Neon_Orange": make_pbr_material(
            "Mat_Guardrail_Neon_Orange", (0.85, 0.72, 0.88), roughness=0.20, metallic=0.65,
            emission_color=(0.75, 0.48, 0.82), emission_strength=0.65
        ),
        "Mat_Guardrail_Neon_Purple": make_pbr_material(
            "Mat_Guardrail_Neon_Purple", (0.80, 0.65, 0.95), roughness=0.20, metallic=0.65,
            emission_color=(0.68, 0.42, 0.92), emission_strength=0.75
        ),
        "Mat_Support_Truss": make_pbr_material(
            "Mat_Support_Truss", (0.14, 0.155, 0.19), roughness=0.36, metallic=0.86
        ),
        "Mat_Start_White": make_pbr_material(
            "Mat_Start_White", (0.97, 0.97, 0.99), roughness=0.25, metallic=0.05,
            emission_color=(0.95, 0.97, 1.0), emission_strength=0.25
        ),
        "Mat_Start_Black": make_pbr_material(
            "Mat_Start_Black", (0.04, 0.04, 0.05), roughness=0.35, metallic=0.10
        ),
        "Mat_Gantry_Frame": make_pbr_material(
            "Mat_Gantry_Frame", (0.10, 0.11, 0.14), roughness=0.30, metallic=0.90
        ),
        "Mat_Neon_Cyan": make_pbr_material(
            "Mat_Neon_Cyan", (0.05, 0.95, 1.00), roughness=0.12, metallic=0.1,
            emission_color=(0.05, 0.92, 1.00), emission_strength=4.5
        ),
        "Mat_Neon_Orange": make_pbr_material(
            "Mat_Neon_Orange", (1.00, 0.45, 0.05), roughness=0.12, metallic=0.1,
            emission_color=(1.00, 0.40, 0.04), emission_strength=4.2
        ),
        "Mat_RaceLight_Red": make_pbr_material(
            "Mat_RaceLight_Red", (1.00, 0.10, 0.08), roughness=0.15, metallic=0.1,
            emission_color=(1.00, 0.08, 0.06), emission_strength=5.0
        ),
        "Mat_RaceLight_Green": make_pbr_material(
            "Mat_RaceLight_Green", (0.10, 1.00, 0.32), roughness=0.15, metallic=0.1,
            emission_color=(0.08, 1.00, 0.28), emission_strength=5.0
        ),
    }
    return mats


# ==============================================================================
# 3. MESH BUILDERS
# ==============================================================================
def finalize_bmesh_object(bm, name, materials):
    mesh = bpy.data.meshes.new(name)
    for mat in materials:
        mesh.materials.append(mat)
    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()

    for poly in mesh.polygons:
        poly.use_smooth = False

    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def add_quad_with_uv(bm, uv_layer, v0, v1, v2, v3, uv0, uv1, uv2, uv3, mat_index=0):
    try:
        face = bm.faces.new((v0, v1, v2, v3))
    except ValueError:
        return None
    face.material_index = mat_index
    loops = face.loops
    loops[0][uv_layer].uv = uv0
    loops[1][uv_layer].uv = uv1
    loops[2][uv_layer].uv = uv2
    loops[3][uv_layer].uv = uv3
    return face


def add_box_th(bm, uv_layer, p0_th, p1_th, axis_u_th, axis_v_th, half_u, half_v, mat_index=0):
    """Add a 3D strut/beam between p0_th and p1_th in Three.js coordinates."""
    u0 = axis_u_th * half_u
    v0 = axis_v_th * half_v

    c0 = [
        th_to_bl(p0_th - u0 - v0),
        th_to_bl(p0_th + u0 - v0),
        th_to_bl(p0_th + u0 + v0),
        th_to_bl(p0_th - u0 + v0),
    ]
    c1 = [
        th_to_bl(p1_th - u0 - v0),
        th_to_bl(p1_th + u0 - v0),
        th_to_bl(p1_th + u0 + v0),
        th_to_bl(p1_th - u0 + v0),
    ]
    bv0 = [bm.verts.new(co) for co in c0]
    bv1 = [bm.verts.new(co) for co in c1]

    for k in range(4):
        kn = (k + 1) % 4
        add_quad_with_uv(
            bm, uv_layer,
            bv0[k], bv0[kn], bv1[kn], bv1[k],
            (0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0),
            mat_index=mat_index,
        )
    # End caps
    add_quad_with_uv(
        bm, uv_layer,
        bv0[3], bv0[2], bv0[1], bv0[0],
        (0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0),
        mat_index=mat_index,
    )
    add_quad_with_uv(
        bm, uv_layer,
        bv1[0], bv1[1], bv1[2], bv1[3],
        (0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0),
        mat_index=mat_index,
    )


def build_track_road(points_data, total_length, mats):
    """
    Build Track_Road:
    - Smooth asphalt ribbon (width = 11.0, thickness = 0.45)
    - UVs: U across road width 0..1, V tiled along track length
    - Crisp 0.3m white inner lane lines near both edges
    - Subtle center dashed line markings
    - Solid dark metallic underside and beveled bottom slab
    """
    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new("UVMap")

    # Cross-section profile in Three.js local (offset_b, offset_n):
    # Top surface spans x_b in [-5.5, +5.5] across 7 strips:
    # 0: -5.50 -> -5.00 (outer left asphalt margin)
    # 1: -5.00 -> -4.70 (0.30m crisp white left lane line, raised +0.004m)
    # 2: -4.70 -> -0.10 (left lane asphalt)
    # 3: -0.10 -> +0.10 (0.20m center line strip: dashed white / asphalt)
    # 4: +0.10 -> +4.70 (right lane asphalt)
    # 5: +4.70 -> +5.00 (0.30m crisp white right lane line, raised +0.004m)
    # 6: +5.00 -> +5.50 (outer right asphalt margin)
    # Plus side walls and solid 0.45m underside slab:
    # 7: (+5.50, 0.0) -> (+5.38, -0.45) right side wall
    # 8: (+5.38, -0.45) -> (-5.38, -0.45) solid bottom underside
    # 9: (-5.38, -0.45) -> (-5.50, 0.0) left side wall
    profile_pts = [
        (-5.50, 0.000),
        (-5.00, 0.002),
        (-4.70, 0.005),
        (-2.40, 0.012),
        (-0.10, 0.015),
        (0.10, 0.015),
        (2.40, 0.012),
        (4.70, 0.005),
        (5.00, 0.002),
        (5.50, 0.000),
        (5.38, -ROAD_THICKNESS),
        (-5.38, -ROAD_THICKNESS),
    ]
    # UV U-coordinate across road width 0..1 for the top surface vertices (0..9),
    # and clean UVs for the underside vertices (10..11)
    profile_u = [
        (x_b + HALF_WIDTH) / TRACK_WIDTH for (x_b, _) in profile_pts[:10]
    ] + [0.95, 0.05]

    n_pts = len(points_data)
    n_prof = len(profile_pts)
    v_tile_scale = 1.0 / 11.0  # 1 UV tile per 11m road square

    rings = []
    for i in range(n_pts):
        p = points_data[i]["pos"]
        b_vec = points_data[i]["b"]
        n_vec = points_data[i]["n"]
        ring_verts = []
        for x_b, y_n in profile_pts:
            world_th = p + b_vec * x_b + n_vec * y_n
            ring_verts.append(bm.verts.new(th_to_bl(world_th)))
        rings.append(ring_verts)

    # Connect rings around the closed loop
    # Material slots: 0 = Mat_Asphalt, 1 = Mat_LaneLine_White, 2 = Mat_Road_Underside
    for i in range(n_pts):
        i_next = (i + 1) % n_pts
        r0 = rings[i]
        r1 = rings[i_next]

        s0 = points_data[i]["s"]
        s1 = points_data[i_next]["s"] if i_next > 0 else total_length
        v0_uv = s0 * v_tile_scale
        v1_uv = s1 * v_tile_scale

        # Top surface strips (k = 0..8)
        for k in range(9):
            u_a = profile_u[k]
            u_b = profile_u[k + 1]

            # Determine material slot:
            # k == 1 (-5.00..-4.70) and k == 7 (+4.70..+5.00) are continuous crisp 0.30m white lane edge lines
            # Center of road is pure uninterrupted racing asphalt (matching reference screenshots)
            if k in (1, 7):
                mat_idx = 1
            else:
                mat_idx = 0

            # Winding order: in Three.js, B points right (+u) and T points forward (+v),
            # so (r0[k+1], r0[k], r1[k], r1[k+1]) has outward normal +N = B x T (upwards!).
            add_quad_with_uv(
                bm, uv_layer,
                r0[k + 1], r0[k], r1[k], r1[k + 1],
                (u_b, v0_uv), (u_a, v0_uv), (u_a, v1_uv), (u_b, v1_uv),
                mat_index=mat_idx,
            )

        # Underside & side edges of road slab:
        # Right wall: 9 -> 10, Bottom slab: 10 -> 11, Left wall: 11 -> 0
        underside_pairs = [(9, 10, 0.0, 0.15), (10, 11, 0.15, 0.85), (11, 0, 0.85, 1.0)]
        for k_a, k_b, u_a, u_b in underside_pairs:
            add_quad_with_uv(
                bm, uv_layer,
                r0[k_b], r0[k_a], r1[k_a], r1[k_b],
                (u_b, v0_uv), (u_a, v0_uv), (u_a, v1_uv), (u_b, v1_uv),
                mat_index=2,
            )

    obj = finalize_bmesh_object(
        bm,
        "Track_Road",
        [mats["Mat_Asphalt"], mats["Mat_LaneLine_White"], mats["Mat_Road_Underside"]],
    )
    # Enable smooth shading on road surface
    for poly in obj.data.polygons:
        if poly.material_index in (0, 1):
            poly.use_smooth = True
    return obj


def build_track_curbs(points_data, mats):
    """
    Build Track_Curbs_Red and Track_Curbs_White:
    - Raised 3D beveled curbstones (width = 0.85m, height = 0.22m)
    - Running continuously along both left and right edges of the road
    - Alternating red (#e62e25) and white (#f4f4f8) every 2 spline segments (~2.0m)
    """
    bm_red = bmesh.new()
    uv_red = bm_red.loops.layers.uv.new("UVMap")

    bm_white = bmesh.new()
    uv_white = bm_white.loops.layers.uv.new("UVMap")

    n_pts = len(points_data)

    # Right curb profile (x_b > 0) in (offset_b, offset_n):
    # Starts at road edge (5.50), rises with a beveled rumble lip to (5.68, 0.22),
    # extends across top to (6.25, 0.22), and steps down to outer skirt (6.35, -0.10)
    right_curb_prof = [
        (5.48, -0.04),
        (5.52, 0.12),
        (5.68, CURB_HEIGHT),
        (6.24, CURB_HEIGHT),
        (6.35, 0.08),
        (6.35, -0.15),
    ]
    # Left curb profile (mirror across x_b = 0, reversed order so winding is outward +N)
    left_curb_prof = [(-x_b, y_n) for (x_b, y_n) in reversed(right_curb_prof)]

    curb_block_steps = 2  # ~2.09m per curbstone block

    for block_start in range(0, n_pts, curb_block_steps):
        block_idx = block_start // curb_block_steps
        is_red = (block_idx % 2 == 0)
        bm = bm_red if is_red else bm_white
        uv_layer = uv_red if is_red else uv_white

        steps_in_block = min(curb_block_steps, n_pts - block_start)

        for side_prof in (right_curb_prof, left_curb_prof):
            ring_list = []
            for s_off in range(steps_in_block + 1):
                idx = (block_start + s_off) % n_pts
                p = points_data[idx]["pos"]
                b_vec = points_data[idx]["b"]
                n_vec = points_data[idx]["n"]
                # Add subtle 0.015m bevel notch at segment boundaries for 3D curbstone look
                bevel_drop = -0.018 if s_off in (0, steps_in_block) else 0.0
                verts = []
                for k_p, (x_b, y_n) in enumerate(side_prof):
                    yn_adj = y_n + (bevel_drop if 1 <= k_p <= 4 else 0.0)
                    world_th = p + b_vec * x_b + n_vec * yn_adj
                    verts.append(bm.verts.new(th_to_bl(world_th)))
                ring_list.append(verts)

            # Side faces along the block
            n_prof = len(side_prof)
            for s_off in range(steps_in_block):
                r0 = ring_list[s_off]
                r1 = ring_list[s_off + 1]
                v0_u = s_off / float(steps_in_block)
                v1_u = (s_off + 1) / float(steps_in_block)
                for k in range(n_prof):
                    kn = (k + 1) % n_prof
                    u0 = k / float(n_prof)
                    u1 = (k + 1) / float(n_prof)
                    add_quad_with_uv(
                        bm, uv_layer,
                        r0[kn], r0[k], r1[k], r1[kn],
                        (u1, v0_u), (u0, v0_u), (u0, v1_u), (u1, v1_u),
                        mat_index=0,
                    )

            # Front and back end-caps of each curb block so 3D bevel joints are watertight
            r_front = ring_list[0]
            r_back = ring_list[-1]
            add_quad_with_uv(
                bm, uv_layer,
                r_front[1], r_front[2], r_front[3], r_front[4],
                (0, 0), (1, 0), (1, 1), (0, 1),
                mat_index=0,
            )
            add_quad_with_uv(
                bm, uv_layer,
                r_back[4], r_back[3], r_back[2], r_back[1],
                (0, 0), (1, 0), (1, 1), (0, 1),
                mat_index=0,
            )

    obj_red = finalize_bmesh_object(bm_red, "Track_Curbs_Red", [mats["Mat_Curb_Red"]])
    obj_white = finalize_bmesh_object(bm_white, "Track_Curbs_White", [mats["Mat_Curb_White"]])
    return obj_red, obj_white


def build_track_guardrails(points_data, mats):
    """
    Build Track_Guardrails:
    - Raised metallic/neon safety rails (height = 1.05m above the curbs -> top at y_n = 1.27m)
    - Supported by vertical stanchion posts every ~4.0m (every 4 spline steps) along both outer edges
    - Glowing purple/cyan/orange emissive top rail strip that catches the light
    """
    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new("UVMap")

    # Materials on Track_Guardrails:
    # 0: Mat_Guardrail_Metal
    # 1: Mat_Guardrail_Neon_Cyan
    # 2: Mat_Guardrail_Neon_Orange
    # 3: Mat_Guardrail_Neon_Purple
    n_pts = len(points_data)

    # Sleek open single-beam guardrail on slim vertical posts (so keyboard & studio props are clearly visible through/over the rail, matching Screenshots 1-5)
    for side_sign in (1.0, -1.0):
        # Upper sleek metallic/lavender-lit safety rail at height 0.72m..0.84m above road
        top_prof = [
            (side_sign * 6.16, 0.72),
            (side_sign * 6.16, 0.84),
            (side_sign * 6.28, 0.84),
            (side_sign * 6.28, 0.72),
        ]
        if side_sign < 0:
            top_prof = list(reversed(top_prof))

        top_rings = []
        for i in range(n_pts):
            p = points_data[i]["pos"]
            b_vec = points_data[i]["b"]
            n_vec = points_data[i]["n"]
            top_rings.append([
                bm.verts.new(th_to_bl(p + b_vec * xb + n_vec * yn))
                for (xb, yn) in top_prof
            ])

        for i in range(n_pts):
            inext = (i + 1) % n_pts
            r0, r1 = top_rings[i], top_rings[inext]
            zone = (i // 40) % 3
            neon_mat = 1 + zone

            for k in range(4):
                kn = (k + 1) % 4
                is_neon_face = (k in (0, 1)) if side_sign > 0 else (k in (1, 2))
                m_idx = neon_mat if is_neon_face else 0
                add_quad_with_uv(
                    bm, uv_layer,
                    r0[kn], r0[k], r1[k], r1[kn],
                    (0, 0), (1, 0), (1, 1), (0, 1),
                    mat_index=m_idx,
                )

        # Slim vertical stanchion posts every 6 steps (~6.0m) along both outer edges
        for i in range(0, n_pts, 6):
            p = points_data[i]["pos"]
            t_vec = points_data[i]["t"]
            b_vec = points_data[i]["b"]
            n_vec = points_data[i]["n"]

            p_bot = p + b_vec * (side_sign * 6.22) + n_vec * 0.15
            p_top = p + b_vec * (side_sign * 6.22) + n_vec * 0.76
            add_box_th(bm, uv_layer, p_bot, p_top, t_vec, b_vec, 0.055, 0.055, mat_index=0)

    return finalize_bmesh_object(
        bm,
        "Track_Guardrails",
        [
            mats["Mat_Guardrail_Metal"],
            mats["Mat_Guardrail_Neon_Cyan"],
            mats["Mat_Guardrail_Neon_Orange"],
            mats["Mat_Guardrail_Neon_Purple"],
        ],
    )


def build_track_support_trusses(points_data, mats):
    """
    Build Track_SupportTrusses:
    - Wherever track elevation y > 1.2, generate realistic 3D metallic lattice truss pillars
      (4 corner vertical struts + horizontal tie frames + X-diagonal cross-bracing every ~14m)
      extending straight down from the underside of the road to the desk/mousepad surface (y = 0.35),
      avoiding intersecting lower track segments or the keyboard (X in [-35, 23], Z in [-23, -1]).
    """
    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new("UVMap")

    n_pts = len(points_data)
    pillar_step = 13  # ~13.6m spacing along spline

    for i in range(0, n_pts, pillar_step):
        p = points_data[i]["pos"]
        if p.y <= 1.25:
            continue

        # Check if this pillar position is over the keyboard (X in [-36.5, 24.5], Z in [-24.5, 0.5])
        # or if it is too close in XZ to any lower track segment
        in_keyboard = (-36.5 <= p.x <= 24.5 and -24.5 <= p.z <= 0.5)

        hits_lower_track = False
        for j in range(n_pts):
            if abs(i - j) < 25 or abs(i - j) > n_pts - 25:
                continue
            pj = points_data[j]["pos"]
            if pj.y < p.y - 1.0:
                dist_xz = math.hypot(p.x - pj.x, p.z - pj.z)
                if dist_xz < 9.5:
                    hits_lower_track = True
                    break

        if hits_lower_track:
            continue

        t_vec = points_data[i]["t"]
        b_vec = points_data[i]["b"]
        n_vec = points_data[i]["n"]

        # Horizontal axes in XZ plane aligned with track direction at i
        t_horiz = Vector((t_vec.x, 0.0, t_vec.z))
        if t_horiz.length < 1e-5:
            t_horiz = Vector((1.0, 0.0, 0.0))
        else:
            t_horiz.normalize()
        b_horiz = Vector((-t_horiz.z, 0.0, t_horiz.x))  # horizontal right vector
        up_world = Vector((0.0, 1.0, 0.0))

        # Pier cap cradle directly underneath the road slab
        cap_center = p - n_vec * (ROAD_THICKNESS + 0.18)
        cap_left = cap_center - b_vec * 4.8
        cap_right = cap_center + b_vec * 4.8
        add_box_th(bm, uv_layer, cap_left, cap_right, t_vec, n_vec, 0.42, 0.22, mat_index=0)

        if in_keyboard:
            # Wide straddle portal frame or skip vertical central tower over keyboard keys:
            # Skip vertical legs directly inside keyboard keys so no truss pierces the keyboard!
            continue

        # Tower top & bottom elevations
        y_top = cap_center.y + 0.05
        y_bot = DESK_SURFACE_Y
        tower_h = y_top - y_bot
        if tower_h < 0.45:
            continue

        half_w = 2.85  # half-width across road (B direction)
        half_d = 1.15  # half-depth along road (T direction)
        strut_r = 0.14
        brace_r = 0.085

        corner_offsets = [
            (-half_w, -half_d),
            (half_w, -half_d),
            (half_w, half_d),
            (-half_w, half_d),
        ]

        # 4 vertical corner struts + base foot pads on desk surface
        top_corners = []
        bot_corners = []
        for ox, oz in corner_offsets:
            horiz_off = b_horiz * ox + t_horiz * oz
            c_top = Vector((p.x, y_top, p.z)) + horiz_off * 0.88
            c_bot = Vector((p.x, y_bot, p.z)) + horiz_off * 1.08
            top_corners.append(c_top)
            bot_corners.append(c_bot)

            add_box_th(bm, uv_layer, c_bot, c_top, t_horiz, b_horiz, strut_r, strut_r, mat_index=0)
            # Base pad on desk surface
            pad_top = c_bot + Vector((0.0, 0.14, 0.0))
            add_box_th(bm, uv_layer, c_bot, pad_top, t_horiz, b_horiz, 0.34, 0.34, mat_index=0)

        # Diagonal knee braces from upper tower corners out to the wide road pier cap ends
        add_box_th(bm, uv_layer, top_corners[0].lerp(bot_corners[0], 0.15), cap_left, t_horiz, up_world, 0.12, 0.12, mat_index=0)
        add_box_th(bm, uv_layer, top_corners[1].lerp(bot_corners[1], 0.15), cap_right, t_horiz, up_world, 0.12, 0.12, mat_index=0)

        # Horizontal tie frames & X-diagonal cross-bracing bays down the tower height
        num_bays = max(1, int(round(tower_h / 2.8)))
        for bay in range(num_bays):
            f0 = bay / float(num_bays)
            f1 = (bay + 1) / float(num_bays)
            ring0 = [top_corners[c].lerp(bot_corners[c], f0) for c in range(4)]
            ring1 = [top_corners[c].lerp(bot_corners[c], f1) for c in range(4)]

            # Horizontal tie bars at top of bay and bottom of last bay
            for c in range(4):
                cn = (c + 1) % 4
                axis_perp = up_world
                add_box_th(bm, uv_layer, ring0[c], ring0[cn], axis_perp, (ring0[cn] - ring0[c]).normalized().cross(axis_perp), brace_r, brace_r, mat_index=0)
                if bay == num_bays - 1:
                    add_box_th(bm, uv_layer, ring1[c], ring1[cn], axis_perp, (ring1[cn] - ring1[c]).normalized().cross(axis_perp), brace_r, brace_r, mat_index=0)

                # X-diagonal cross-bracing on all 4 faces of the lattice tower
                d1 = (ring1[cn] - ring0[c]).normalized()
                p_u1 = d1.cross(b_horiz if c in (0, 2) else t_horiz).normalized()
                p_v1 = d1.cross(p_u1).normalized()
                add_box_th(bm, uv_layer, ring0[c], ring1[cn], p_u1, p_v1, brace_r * 0.85, brace_r * 0.85, mat_index=0)

                d2 = (ring1[c] - ring0[cn]).normalized()
                p_u2 = d2.cross(b_horiz if c in (0, 2) else t_horiz).normalized()
                p_v2 = d2.cross(p_u2).normalized()
                add_box_th(bm, uv_layer, ring0[cn], ring1[c], p_u2, p_v2, brace_r * 0.85, brace_r * 0.85, mat_index=0)

    return finalize_bmesh_object(bm, "Track_SupportTrusses", [mats["Mat_Support_Truss"]])


def build_track_start_line(points_data, mats):
    """
    Build Track_StartLine:
    - Checkered black-and-white Start/Finish strip across the road at index 0
    - Overhead futuristic Start/Finish gantry arch with glowing cyan/orange signage
      and red/green race lights at the Start/Finish point
    """
    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new("UVMap")

    # Material slots:
    # 0: Mat_Start_White
    # 1: Mat_Start_Black
    # 2: Mat_Gantry_Frame
    # 3: Mat_Neon_Cyan
    # 4: Mat_Neon_Orange
    # 5: Mat_RaceLight_Red
    # 6: Mat_RaceLight_Green

    p0 = points_data[0]["pos"]
    t_vec = points_data[0]["t"]
    b_vec = points_data[0]["b"]
    n_vec = points_data[0]["n"]

    # 1. Checkered Black & White Start/Finish Strip across the road surface
    # Spans x_b in [-4.70, +4.70] (between the white lane lines), 3 rows x 16 columns
    num_rows = 3
    num_cols = 16
    strip_len = 2.25  # along T
    strip_w = 9.40    # across B
    y_lift = 0.022    # flush just above road crown

    for r in range(num_rows):
        t0 = -0.5 * strip_len + (r / float(num_rows)) * strip_len
        t1 = -0.5 * strip_len + ((r + 1) / float(num_rows)) * strip_len
        for c in range(num_cols):
            b0 = -0.5 * strip_w + (c / float(num_cols)) * strip_w
            b1 = -0.5 * strip_w + ((c + 1) / float(num_cols)) * strip_w

            mat_idx = 0 if (r + c) % 2 == 0 else 1
            v00 = bm.verts.new(th_to_bl(p0 + t_vec * t0 + b_vec * b0 + n_vec * y_lift))
            v10 = bm.verts.new(th_to_bl(p0 + t_vec * t0 + b_vec * b1 + n_vec * y_lift))
            v11 = bm.verts.new(th_to_bl(p0 + t_vec * t1 + b_vec * b1 + n_vec * y_lift))
            v01 = bm.verts.new(th_to_bl(p0 + t_vec * t1 + b_vec * b0 + n_vec * y_lift))

            add_quad_with_uv(
                bm, uv_layer,
                v10, v00, v01, v11,
                (1, 0), (0, 0), (0, 1), (1, 1),
                mat_index=mat_idx,
            )

    # 2. Futuristic Overhead Start/Finish Gantry Arch
    gantry_half_span = 6.95  # outside curbs and guardrails
    gantry_height = 6.40     # clear height above road surface
    gantry_depth = 1.30

    for side_sign in (-1.0, 1.0):
        base_b = side_sign * gantry_half_span
        top_b = side_sign * (gantry_half_span - 0.55)

        for z_sign in (-0.5, 0.5):
            t_off = z_sign * gantry_depth
            col_bot = p0 + b_vec * base_b + t_vec * t_off + n_vec * (-0.20)
            col_top = p0 + b_vec * top_b + t_vec * t_off + n_vec * gantry_height
            add_box_th(bm, uv_layer, col_bot, col_top, t_vec, b_vec, 0.18, 0.18, mat_index=2)

            # Glowing vertical neon accent strip along the inner face of the front column
            if z_sign < 0:
                neon_bot = p0 + b_vec * (base_b - side_sign * 0.20) + t_vec * t_off + n_vec * 0.50
                neon_top = p0 + b_vec * (top_b - side_sign * 0.20) + t_vec * t_off + n_vec * (gantry_height - 0.35)
                add_box_th(bm, uv_layer, neon_bot, neon_top, t_vec, b_vec, 0.06, 0.06, mat_index=3)

        # Cross rungs & diagonal bracing on side gantry columns
        for h_frac in (0.2, 0.45, 0.7, 0.95):
            b_lerp = base_b + (top_b - base_b) * h_frac
            y_lerp = -0.20 + (gantry_height + 0.20) * h_frac
            r_front = p0 + b_vec * b_lerp - t_vec * (0.5 * gantry_depth) + n_vec * y_lerp
            r_back = p0 + b_vec * b_lerp + t_vec * (0.5 * gantry_depth) + n_vec * y_lerp
            add_box_th(bm, uv_layer, r_front, r_back, b_vec, n_vec, 0.12, 0.12, mat_index=2)

    # Overhead horizontal bridge beams & truss chords spanning across the track
    span_b = gantry_half_span - 0.45
    for y_off in (gantry_height - 0.75, gantry_height + 0.15):
        for t_off in (-0.5 * gantry_depth, 0.5 * gantry_depth):
            left_pt = p0 - b_vec * span_b + t_vec * t_off + n_vec * y_off
            right_pt = p0 + b_vec * span_b + t_vec * t_off + n_vec * y_off
            add_box_th(bm, uv_layer, left_pt, right_pt, t_vec, n_vec, 0.16, 0.16, mat_index=2)

    # Overhead truss struts connecting upper & lower bridge beams
    num_bridge_bays = 8
    for k in range(num_bridge_bays + 1):
        bx = -span_b + (2.0 * span_b * k) / float(num_bridge_bays)
        for t_off in (-0.5 * gantry_depth, 0.5 * gantry_depth):
            p_low = p0 + b_vec * bx + t_vec * t_off + n_vec * (gantry_height - 0.75)
            p_high = p0 + b_vec * bx + t_vec * t_off + n_vec * (gantry_height + 0.15)
            add_box_th(bm, uv_layer, p_low, p_high, t_vec, b_vec, 0.10, 0.10, mat_index=2)
        # Top & bottom cross ties
        p_front = p0 + b_vec * bx - t_vec * (0.5 * gantry_depth) + n_vec * (gantry_height + 0.15)
        p_back = p0 + b_vec * bx + t_vec * (0.5 * gantry_depth) + n_vec * (gantry_height + 0.15)
        add_box_th(bm, uv_layer, p_front, p_back, b_vec, n_vec, 0.10, 0.10, mat_index=2)

    # Futuristic central signage board on both front (-T) and back (+T) of the gantry
    board_half_w = 4.60
    board_y_center = gantry_height - 0.30
    for face_sign in (-1.0, 1.0):
        t_board = face_sign * (0.5 * gantry_depth + 0.16)
        b_left = p0 - b_vec * board_half_w + t_vec * t_board + n_vec * board_y_center
        b_right = p0 + b_vec * board_half_w + t_vec * t_board + n_vec * board_y_center
        # Dark metallic backing panel
        add_box_th(bm, uv_layer, b_left, b_right, t_vec, n_vec, 0.10, 0.52, mat_index=2)

        # Glowing top Cyan neon bar & bottom Orange neon bar across signage
        t_neon = face_sign * (0.5 * gantry_depth + 0.27)
        c_left = p0 - b_vec * (board_half_w - 0.15) + t_vec * t_neon + n_vec * (board_y_center + 0.38)
        c_right = p0 + b_vec * (board_half_w - 0.15) + t_vec * t_neon + n_vec * (board_y_center + 0.38)
        add_box_th(bm, uv_layer, c_left, c_right, t_vec, n_vec, 0.05, 0.08, mat_index=3)

        o_left = p0 - b_vec * (board_half_w - 0.15) + t_vec * t_neon + n_vec * (board_y_center - 0.38)
        o_right = p0 + b_vec * (board_half_w - 0.15) + t_vec * t_neon + n_vec * (board_y_center - 0.38)
        add_box_th(bm, uv_layer, o_left, o_right, t_vec, n_vec, 0.05, 0.08, mat_index=4)

        # 5 Race Starting Light Pods suspended below the gantry beam
        for pod_idx, pod_b in enumerate((-3.0, -1.5, 0.0, 1.5, 3.0)):
            pod_center = p0 + b_vec * pod_b + t_vec * (face_sign * 0.45) + n_vec * (gantry_height - 1.18)
            pod_L = pod_center - b_vec * 0.28
            pod_R = pod_center + b_vec * 0.28
            # Pod housing
            add_box_th(bm, uv_layer, pod_L, pod_R, t_vec, n_vec, 0.20, 0.34, mat_index=2)

            # Upper Red race light & Lower Green race light
            light_t = pod_center + t_vec * (face_sign * 0.21)
            red_L = light_t - b_vec * 0.18 + n_vec * 0.13
            red_R = light_t + b_vec * 0.18 + n_vec * 0.13
            add_box_th(bm, uv_layer, red_L, red_R, t_vec, n_vec, 0.05, 0.10, mat_index=5)

            grn_L = light_t - b_vec * 0.18 - n_vec * 0.13
            grn_R = light_t + b_vec * 0.18 - n_vec * 0.13
            add_box_th(bm, uv_layer, grn_L, grn_R, t_vec, n_vec, 0.05, 0.10, mat_index=6)

    return finalize_bmesh_object(
        bm,
        "Track_StartLine",
        [
            mats["Mat_Start_White"],
            mats["Mat_Start_Black"],
            mats["Mat_Gantry_Frame"],
            mats["Mat_Neon_Cyan"],
            mats["Mat_Neon_Orange"],
            mats["Mat_RaceLight_Red"],
            mats["Mat_RaceLight_Green"],
        ],
    )


# ==============================================================================
# 4. EXPORT JSON & GLB
# ==============================================================================
def write_track_json(points_data, total_length, filepath):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    serialized_points = []
    for pt in points_data:
        pos = pt["pos"]
        t = pt["t"]
        n = pt["n"]
        b = pt["b"]
        serialized_points.append({
            "x": round(pos.x, 5),
            "y": round(pos.y, 5),
            "z": round(pos.z, 5),
            "tx": round(t.x, 6),
            "ty": round(t.y, 6),
            "tz": round(t.z, 6),
            "nx": round(n.x, 6),
            "ny": round(n.y, 6),
            "nz": round(n.z, 6),
            "bx": round(b.x, 6),
            "by": round(b.y, 6),
            "bz": round(b.z, 6),
            "s": round(pt["s"], 5),
            "bank": round(pt["bank"], 6),
            "curvature": round(pt["curvature"], 6),
        })

    payload = {
        "trackWidth": TRACK_WIDTH,
        "totalLength": round(total_length, 4),
        "startIndex": 0,
        "checkpoints": [0, 150, 300, 450],
        "points": serialized_points,
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def main():
    # Clear existing scene
    bpy.ops.wm.read_factory_settings(use_empty=True)

    points_data, total_length = build_spline_data(NUM_SAMPLES)

    # Verify spline clearances & curvature
    max_curv = max(abs(p["curvature"]) for p in points_data)
    min_nonadj_dist = 999.0
    min_kbd_y = 999.0
    for i in range(len(points_data)):
        pi = points_data[i]["pos"]
        if -35.0 <= pi.x <= 23.0 and -23.0 <= pi.z <= -1.0:
            min_kbd_y = min(min_kbd_y, pi.y)
        for j in range(i + 35, len(points_data) - 35):
            if abs(i - j) < 35 or abs(i - j) > len(points_data) - 35:
                continue
            d = (pi - points_data[j]["pos"]).length
            if d < min_nonadj_dist:
                min_nonadj_dist = d

    print(f"[TrackVerify] totalLength = {total_length:.4f}m")
    print(f"[TrackVerify] max |curvature| = {max_curv:.5f} (min turn radius = {1.0/max_curv:.2f}m)")
    print(f"[TrackVerify] min non-adjacent 3D distance = {min_nonadj_dist:.2f}m")
    print(f"[TrackVerify] min Y over keyboard zone = {min_kbd_y:.2f}m")
    print(f"[TrackVerify] start pos = {tuple(round(v, 4) for v in points_data[0]['pos'])}")
    print(f"[TrackVerify] start tangent = {tuple(round(v, 4) for v in points_data[0]['t'])}")

    # Create materials & build meshes
    mats = create_all_materials()
    build_track_road(points_data, total_length, mats)
    build_track_curbs(points_data, mats)
    build_track_guardrails(points_data, mats)
    build_track_support_trusses(points_data, mats)
    build_track_start_line(points_data, mats)

    # Export JSON
    write_track_json(points_data, total_length, JSON_OUT_PATH)

    # Export GLB
    os.makedirs(os.path.dirname(GLB_OUT_PATH), exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=GLB_OUT_PATH,
        export_format="GLB",
        export_yup=True,
        export_apply=True,
    )

    print(f"[TrackExport] Exported GLB: {GLB_OUT_PATH} ({os.path.getsize(GLB_OUT_PATH)} bytes)")
    print(f"[TrackExport] Exported JSON: {JSON_OUT_PATH} ({os.path.getsize(JSON_OUT_PATH)} bytes)")
    print("[TrackExport] Objects:", [obj.name for obj in bpy.data.objects])
    print("[TrackExport] Materials:", [m.name for m in bpy.data.materials])


if __name__ == "__main__":
    main()
