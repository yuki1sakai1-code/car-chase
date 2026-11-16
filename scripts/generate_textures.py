import os
import time
import numpy as np
import bpy

TEX_DIR = r"c:\Users\yukis\Downloads\car-chase\assets\textures"
os.makedirs(TEX_DIR, exist_ok=True)

RES = 2048

def save_rgba_png(filepath, rgba_float, is_data=False):
    """
    rgba_float: numpy array of shape (H, W, 4) in [0, 1] float32.
    Row 0 is bottom in Blender images, or top if flipped. Let's keep standard orientation.
    """
    t0 = time.time()
    name = os.path.basename(filepath)
    if name in bpy.data.images:
        bpy.data.images.remove(bpy.data.images[name])
    img = bpy.data.images.new(name=name, width=RES, height=RES, alpha=True, float_buffer=False)
    if is_data:
        img.colorspace_settings.name = 'Non-Color'
    else:
        img.colorspace_settings.name = 'sRGB'
    
    flat = np.clip(rgba_float, 0.0, 1.0).astype(np.float32).ravel()
    img.pixels.foreach_set(flat)
    img.filepath_raw = filepath
    img.file_format = 'PNG'
    img.save()
    print(f"Saved {filepath} ({RES}x{RES}) in {time.time() - t0:.2f}s")

def height_to_normal(height_map, strength=3.0):
    """
    Compute tangent space normal map (R, G, B, 1) from height_map (H, W) in [0, 1].
    Uses periodic boundary conditions (np.roll) so tileable textures have tileable normals.
    """
    dy = (np.roll(height_map, -1, axis=0) - np.roll(height_map, 1, axis=0)) * 0.5 * strength
    dx = (np.roll(height_map, -1, axis=1) - np.roll(height_map, 1, axis=1)) * 0.5 * strength
    dz = np.ones_like(height_map)
    norm = np.sqrt(dx*dx + dy*dy + dz*dz)
    nx = (-dx / norm) * 0.5 + 0.5
    ny = (dy / norm) * 0.5 + 0.5
    nz = (dz / norm) * 0.5 + 0.5
    rgba = np.ones((RES, RES, 4), dtype=np.float32)
    rgba[..., 0] = nx
    rgba[..., 1] = ny
    rgba[..., 2] = nz
    return rgba

def tileable_fbm(res, freqs=(4, 8, 16, 32, 64), weights=(0.35, 0.25, 0.2, 0.12, 0.08), seed=42):
    """
    Fast FFT-based or multi-harmonic tileable noise on (res, res).
    Using FFT filtering of white noise guarantees 100% seamless periodicity and is super fast!
    """
    rng = np.random.default_rng(seed)
    white = rng.standard_normal((res, res)).astype(np.float32)
    f_white = np.fft.rfft2(white)
    
    ky = np.fft.fftfreq(res)[:, None] * res
    kx = np.fft.rfftfreq(res)[None, :] * res
    k2 = kx*kx + ky*ky
    k = np.sqrt(k2)
    
    # Power-law pink/brown spectrum band-limited
    envelope = np.zeros_like(k, dtype=np.float32)
    for f, w in zip(freqs, weights):
        envelope += w * np.exp(-0.5 * ((k - f) / (f * 0.45 + 1.0))**2)
    
    filtered = np.fft.irfft2(f_white * envelope, s=(res, res))
    mn, mx = filtered.min(), filtered.max()
    return (filtered - mn) / (mx - mn + 1e-8)

def generate_track_asphalt():
    print("Generating 2K Track Asphalt PBR textures...")
    rng = np.random.default_rng(101)
    
    # Coordinates u in [0, 1] across X (columns), v in [0, 1] along Y (rows)
    u = np.linspace(0.0, 1.0, RES, endpoint=False, dtype=np.float32)[None, :]
    v = np.linspace(0.0, 1.0, RES, endpoint=False, dtype=np.float32)[:, None]
    
    # Micro-grain aggregate noise (high frequency) + macro variation
    macro = tileable_fbm(RES, freqs=(3, 7, 15, 35), weights=(0.4, 0.3, 0.2, 0.1), seed=102)
    micro1 = rng.random((RES, RES), dtype=np.float32)
    # Smooth micro1 slightly via rolls
    micro_smooth = (
        micro1 * 0.4 +
        np.roll(micro1, 1, axis=0) * 0.15 +
        np.roll(micro1, -1, axis=0) * 0.15 +
        np.roll(micro1, 1, axis=1) * 0.15 +
        np.roll(micro1, -1, axis=1) * 0.15
    )
    # Sharp aggregate pebbles (top percentile of noise)
    pebbles = np.clip((micro_smooth - 0.55) * 3.0, 0.0, 1.0)
    
    # Base asphalt height
    height = 0.45 * macro + 0.40 * micro_smooth + 0.15 * pebbles
    
    # Base dark anthracite asphalt color (#1c1d22 to #2b2d34)
    base_val = 0.11 + 0.05 * macro + 0.06 * (micro_smooth - 0.5) + 0.07 * pebbles
    
    # Subtle rubber tire tracks down the center (two racing wheel grooves around u=0.38 and u=0.62, plus center wear)
    tire_left = np.exp(-0.5 * ((u - 0.37) / 0.065)**2)
    tire_right = np.exp(-0.5 * ((u - 0.63) / 0.065)**2)
    tire_center = 0.35 * np.exp(-0.5 * ((u - 0.50) / 0.14)**2)
    # Streak modulation along v
    streak = tileable_fbm(RES, freqs=(2, 6, 18), weights=(0.5, 0.3, 0.2), seed=105)
    skid_mask = np.clip((tire_left + tire_right + tire_center) * (0.75 + 0.45 * streak), 0.0, 1.0)
    
    # Darken albedo where rubber is laid down, and lower roughness slightly (polished rubber sheen)
    base_val = base_val * (1.0 - 0.28 * skid_mask)
    
    # Crisp white sideline stripes near u=0.06 and u=0.94 (width ~0.022)
    line_half_w = 0.012
    edge_soft = 0.002
    left_stripe = np.clip(1.0 - (np.abs(u - 0.06) - line_half_w) / edge_soft, 0.0, 1.0)
    right_stripe = np.clip(1.0 - (np.abs(u - 0.94) - line_half_w) / edge_soft, 0.0, 1.0)
    stripe_mask = np.maximum(left_stripe, right_stripe)
    # Slight paint wear from micro noise
    paint_mask = stripe_mask * (0.90 + 0.10 * macro)
    
    # Subtle red/cyan apex rumble curb edge hint on very outer edge u < 0.02 or u > 0.98
    outer_edge = np.clip((0.022 - u) / 0.004, 0.0, 1.0) + np.clip((u - 0.978) / 0.004, 0.0, 1.0)
    
    r = base_val * 0.96
    g = base_val * 0.98
    b = base_val * 1.05
    
    # Blend white sideline paint (#f2f4f8)
    r = r * (1.0 - paint_mask) + 0.94 * paint_mask
    g = g * (1.0 - paint_mask) + 0.95 * paint_mask
    b = b * (1.0 - paint_mask) + 0.97 * paint_mask
    
    # Subtle warm dark shoulder on outer 2%
    r = r * (1.0 - 0.2 * outer_edge) + 0.18 * outer_edge
    
    albedo = np.ones((RES, RES, 4), dtype=np.float32)
    albedo[..., 0] = r
    albedo[..., 1] = g
    albedo[..., 2] = b
    
    # Raise paint thickness slightly in height map
    height_total = height * (1.0 - 0.25 * skid_mask) + 0.12 * stripe_mask
    normal = height_to_normal(height_total, strength=6.5)
    
    # Roughness: base asphalt ~0.82, rubber tracks ~0.58, white paint ~0.48
    rough = 0.80 + 0.12 * (1.0 - pebbles) - 0.22 * skid_mask - 0.30 * stripe_mask + 0.06 * (macro - 0.5)
    rough = np.clip(rough, 0.25, 0.96)
    rough_rgba = np.ones((RES, RES, 4), dtype=np.float32)
    rough_rgba[..., 0] = rough
    rough_rgba[..., 1] = rough
    rough_rgba[..., 2] = rough
    
    save_rgba_png(os.path.join(TEX_DIR, "track_asphalt_albedo_2k.png"), albedo, is_data=False)
    save_rgba_png(os.path.join(TEX_DIR, "track_asphalt_normal_2k.png"), normal, is_data=True)
    save_rgba_png(os.path.join(TEX_DIR, "track_asphalt_roughness_2k.png"), rough_rgba, is_data=True)

def generate_desk_wood():
    print("Generating 2K Desk Wood (Walnut) PBR textures...")
    u = np.linspace(0.0, 1.0, RES, endpoint=False, dtype=np.float32)[None, :]
    v = np.linspace(0.0, 1.0, RES, endpoint=False, dtype=np.float32)[:, None]
    
    # Anisotropic noise stretched along U (horizontal wood planks)
    n1 = tileable_fbm(RES, freqs=(2, 5, 11), weights=(0.5, 0.35, 0.15), seed=201)
    n2 = tileable_fbm(RES, freqs=(8, 18, 40), weights=(0.5, 0.3, 0.2), seed=202)
    
    # Plank seams along V (8 wide walnut Butcher-block planks across V)
    num_planks = 8.0
    plank_id = np.floor(v * num_planks)
    plank_v = (v * num_planks) % 1.0
    seam_v = np.exp(-0.5 * (np.minimum(plank_v, 1.0 - plank_v) / 0.008)**2)
    
    # Per-plank phase shift and tone variation
    plank_shift = np.sin(plank_id * 2.17 + 0.5) * 0.35
    plank_tone = 0.90 + 0.18 * np.cos(plank_id * 3.71 + 1.1)
    
    # Wood ring pattern distorted by organic noise
    grain_coord = (v * num_planks * 3.2) + 1.4 * n1 + 0.35 * n2 + plank_shift
    rings = 0.5 + 0.5 * np.sin(grain_coord * 2.0 * np.pi)
    # Sharpen dark growth rings
    rings_sharp = np.power(rings, 0.65)
    
    # Fine wood pores / fibers stretched horizontally along U
    rng = np.random.default_rng(203)
    raw_pores = rng.random((RES, RES), dtype=np.float32)
    # Blur heavily along U (axis=1) using FFT
    f_pores = np.fft.rfft2(raw_pores)
    ky = np.fft.fftfreq(RES)[:, None] * RES
    kx = np.fft.rfftfreq(RES)[None, :] * RES
    pore_filter = np.exp(-0.5 * (kx / 18.0)**2 - 0.5 * (ky / 260.0)**2)
    pores = np.fft.irfft2(f_pores * pore_filter, s=(RES, RES))
    pores = (pores - pores.min()) / (pores.max() - pores.min() + 1e-8)
    
    wood_factor = np.clip(0.62 * rings_sharp + 0.23 * pores + 0.15 * n1, 0.0, 1.0)
    
    # Rich warm dark walnut palette (matching reference screenshots: warm amber-brown walnut)
    # Dark grain: (#24130b) -> (0.14, 0.075, 0.043)
    # Light warm heartwood: (#5e341e) -> (0.37, 0.205, 0.118)
    r = (0.14 + 0.25 * wood_factor) * plank_tone * (1.0 - 0.45 * seam_v)
    g = (0.075 + 0.14 * wood_factor) * plank_tone * (1.0 - 0.45 * seam_v)
    b = (0.042 + 0.08 * wood_factor) * plank_tone * (1.0 - 0.45 * seam_v)
    
    albedo = np.ones((RES, RES, 4), dtype=np.float32)
    albedo[..., 0] = np.clip(r, 0.0, 1.0)
    albedo[..., 1] = np.clip(g, 0.0, 1.0)
    albedo[..., 2] = np.clip(b, 0.0, 1.0)
    
    # Height map: wood pores, ring valleys, and plank seams
    height = 0.55 * pores + 0.30 * rings_sharp - 0.45 * seam_v
    normal = height_to_normal(height, strength=4.0)
    
    # Satin varnished wood roughness (0.35 on smooth heartwood, 0.58 in pores/seams)
    rough = 0.38 + 0.18 * (1.0 - pores) + 0.10 * (1.0 - rings_sharp) + 0.20 * seam_v
    rough = np.clip(rough, 0.25, 0.85)
    rough_rgba = np.ones((RES, RES, 4), dtype=np.float32)
    rough_rgba[..., 0] = rough
    rough_rgba[..., 1] = rough
    rough_rgba[..., 2] = rough
    
    save_rgba_png(os.path.join(TEX_DIR, "desk_wood_albedo_2k.png"), albedo, is_data=False)
    save_rgba_png(os.path.join(TEX_DIR, "desk_wood_normal_2k.png"), normal, is_data=True)
    save_rgba_png(os.path.join(TEX_DIR, "desk_wood_roughness_2k.png"), rough_rgba, is_data=True)

def generate_mousepad_fabric():
    print("Generating 2K Mousepad Fabric (#3b1560) PBR textures...")
    u = np.linspace(0.0, 1.0, RES, endpoint=False, dtype=np.float32)[None, :]
    v = np.linspace(0.0, 1.0, RES, endpoint=False, dtype=np.float32)[:, None]
    
    # Micro-woven gaming cloth pattern (high-frequency diagonal/cross weave)
    freq = 320.0 * 2.0 * np.pi
    warp = np.sin(u * freq) * np.cos(v * freq * 0.5)
    weft = np.cos(u * freq * 0.5) * np.sin(v * freq)
    weave = 0.5 + 0.25 * warp + 0.25 * weft
    
    # Subtle macro sheen variation and border stitch vignette
    macro = tileable_fbm(RES, freqs=(3, 8, 20), weights=(0.5, 0.3, 0.2), seed=301)
    
    # Deep purple-violet #3b1560 -> sRGB (59/255, 21/255, 96/255) = (0.231, 0.082, 0.376)
    shade = 0.88 + 0.16 * weave + 0.08 * (macro - 0.5)
    r = 0.231 * shade
    g = 0.082 * shade
    b = 0.376 * shade
    
    # Subtle glowing cyan reflection tint near the very outer UV border (stitching zone)
    border_dist = np.minimum(np.minimum(u, 1.0 - u), np.minimum(v, 1.0 - v))
    stitch_zone = np.clip((0.012 - border_dist) / 0.004, 0.0, 1.0)
    stitch_rib = 0.5 + 0.5 * np.sin((u + v) * 480.0 * 2.0 * np.pi)
    
    r = r * (1.0 - 0.4 * stitch_zone) + 0.10 * stitch_zone * stitch_rib
    g = g * (1.0 - 0.4 * stitch_zone) + 0.55 * stitch_zone * stitch_rib
    b = b * (1.0 - 0.4 * stitch_zone) + 0.65 * stitch_zone * stitch_rib
    
    albedo = np.ones((RES, RES, 4), dtype=np.float32)
    albedo[..., 0] = np.clip(r, 0.0, 1.0)
    albedo[..., 1] = np.clip(g, 0.0, 1.0)
    albedo[..., 2] = np.clip(b, 0.0, 1.0)
    
    height = weave * 0.7 + macro * 0.3 + stitch_zone * stitch_rib * 0.4
    normal = height_to_normal(height, strength=4.5)
    
    rough = 0.78 + 0.12 * (1.0 - weave) - 0.06 * macro
    rough = np.clip(rough, 0.55, 0.95)
    rough_rgba = np.ones((RES, RES, 4), dtype=np.float32)
    rough_rgba[..., 0] = rough
    rough_rgba[..., 1] = rough
    rough_rgba[..., 2] = rough
    
    save_rgba_png(os.path.join(TEX_DIR, "mousepad_fabric_albedo_2k.png"), albedo, is_data=False)
    save_rgba_png(os.path.join(TEX_DIR, "mousepad_fabric_normal_2k.png"), normal, is_data=True)
    save_rgba_png(os.path.join(TEX_DIR, "mousepad_fabric_roughness_2k.png"), rough_rgba, is_data=True)

def generate_keyboard_top():
    print("Generating 2K Keyboard Top Albedo & Emissive textures...")
    # Create a crisp 2048x2048 mechanical keyboard layout deck with glowing cyan (#00f5ff) keycap borders & legends
    albedo = np.zeros((RES, RES, 4), dtype=np.float32)
    emissive = np.zeros((RES, RES, 4), dtype=np.float32)
    
    # Anodized matte-black aluminum frame base (#14161d)
    u = np.linspace(0.0, 1.0, RES, endpoint=False, dtype=np.float32)[None, :]
    v = np.linspace(0.0, 1.0, RES, endpoint=False, dtype=np.float32)[:, None]
    brushed = 0.08 + 0.015 * np.sin(u * 900.0)
    albedo[..., 0] = brushed * 0.95
    albedo[..., 1] = brushed * 1.00
    albedo[..., 2] = brushed * 1.15
    albedo[..., 3] = 1.0
    emissive[..., 3] = 1.0
    
    # Define 6 rows of mechanical keys in UV space
    # v from 0.10 (bottom row) to 0.88 (top function row)
    # Wait: in Blender/OpenGL UV, v=0 is bottom (front of keyboard), v=1 is top (back of keyboard)
    row_defs = [
        # (v_min, v_max, key_widths_list)
        (0.10, 0.21, [1.25, 1.25, 1.25, 6.25, 1.25, 1.25, 1.25, 1.25, 0.5, 1.0, 1.0, 1.0]), # Bottom row (Ctrl, Win, Alt, Space, Arrows)
        (0.23, 0.34, [2.25, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2.75, 0.5, 1.0, 1.0, 1.0]),      # Shift ZXCV row
        (0.36, 0.47, [1.75, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2.25, 0.5, 1.0, 1.0, 1.0]),   # Caps ASDF row (WASD!)
        (0.49, 0.60, [1.5, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1.5, 0.5, 1.0, 1.0, 1.0]),  # Tab QWERTY row
        (0.62, 0.73, [1.0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2.0, 0.5, 1.0, 1.0, 1.0]),  # Number row 1-0
        (0.77, 0.88, [1.2, 0.8, 1, 1, 1, 1, 0.5, 1, 1, 1, 1, 0.5, 1, 1, 1, 1, 0.5, 2.5]),  # ESC + F1-F12 + Volume roller
    ]
    
    # Outer cyan LED edge strip around the keyboard deck
    frame_border = (
        ((u > 0.025) & (u < 0.975) & (v > 0.04) & (v < 0.94)) &
        ~((u > 0.033) & (u < 0.967) & (v > 0.052) & (v < 0.928))
    )
    emissive[frame_border, 0] = 0.0
    emissive[frame_border, 1] = 0.96
    emissive[frame_border, 2] = 1.0
    albedo[frame_border, 0] = 0.0
    albedo[frame_border, 1] = 0.96
    albedo[frame_border, 2] = 1.0

    u_start = 0.05
    u_end = 0.95
    total_u_span = u_end - u_start

    for r_idx, (vmin, vmax, widths) in enumerate(row_defs):
        y0 = int(vmin * RES)
        y1 = int(vmax * RES)
        total_units = sum(widths)
        cur_u = u_start
        for k_idx, w in enumerate(widths):
            du = (w / total_units) * total_u_span
            # Spacer gap if w == 0.5
            if w == 0.5:
                cur_u += du
                continue
            x0 = int((cur_u + 0.003) * RES)
            x1 = int((cur_u + du - 0.003) * RES)
            cur_u += du
            if x1 <= x0 or y1 <= y0:
                continue
            
            # Keycap trench / backlit switch plate glow around keycap perimeter
            pad = 7
            emissive[y0:y1, x0:x1, 0] = 0.0
            emissive[y0:y1, x0:x1, 1] = 0.96
            emissive[y0:y1, x0:x1, 2] = 1.0
            
            albedo[y0:y1, x0:x1, 0] = 0.05
            albedo[y0:y1, x0:x1, 1] = 0.85
            albedo[y0:y1, x0:x1, 2] = 0.95
            
            # Inner keycap top surface (dark PBT #1b1e28, or special accent for ESC / WASD)
            ix0, ix1 = x0 + pad, x1 - pad
            iy0, iy1 = y0 + pad, y1 - pad
            if ix1 > ix0 and iy1 > iy0:
                is_wasd = (r_idx == 2 and k_idx in (1, 2, 3)) or (r_idx == 3 and k_idx == 2)
                is_esc = (r_idx == 5 and k_idx == 0)
                if is_esc:
                    # Bright cyan/orange accent key
                    albedo[iy0:iy1, ix0:ix1, 0] = 0.02
                    albedo[iy0:iy1, ix0:ix1, 1] = 0.65
                    albedo[iy0:iy1, ix0:ix1, 2] = 0.78
                    emissive[iy0:iy1, ix0:ix1, 0] = 0.0
                    emissive[iy0:iy1, ix0:ix1, 1] = 0.35
                    emissive[iy0:iy1, ix0:ix1, 2] = 0.45
                elif is_wasd:
                    albedo[iy0:iy1, ix0:ix1, 0] = 0.08
                    albedo[iy0:iy1, ix0:ix1, 1] = 0.25
                    albedo[iy0:iy1, ix0:ix1, 2] = 0.35
                    emissive[iy0:iy1, ix0:ix1, 0] = 0.0
                    emissive[iy0:iy1, ix0:ix1, 1] = 0.15
                    emissive[iy0:iy1, ix0:ix1, 2] = 0.22
                else:
                    albedo[iy0:iy1, ix0:ix1, 0] = 0.11
                    albedo[iy0:iy1, ix0:ix1, 1] = 0.12
                    albedo[iy0:iy1, ix0:ix1, 2] = 0.16
                    emissive[iy0:iy1, ix0:ix1, 0] = 0.0
                    emissive[iy0:iy1, ix0:ix1, 1] = 0.02
                    emissive[iy0:iy1, ix0:ix1, 2] = 0.04
                
                # Glowing cyan key legend glyph in upper-center of keycap
                ly0 = iy0 + int((iy1 - iy0) * 0.52)
                ly1 = iy0 + int((iy1 - iy0) * 0.76)
                lx0 = ix0 + int((ix1 - ix0) * 0.32)
                lx1 = ix0 + int((ix1 - ix0) * 0.68)
                if lx1 > lx0 and ly1 > ly0:
                    emissive[ly0:ly1, lx0:lx1, 0] = 0.05
                    emissive[ly0:ly1, lx0:lx1, 1] = 0.96
                    emissive[ly0:ly1, lx0:lx1, 2] = 1.0
                    albedo[ly0:ly1, lx0:lx1, 0] = 0.20
                    albedo[ly0:ly1, lx0:lx1, 1] = 0.98
                    albedo[ly0:ly1, lx0:lx1, 2] = 1.0

    save_rgba_png(os.path.join(TEX_DIR, "keyboard_top_albedo_2k.png"), albedo, is_data=False)
    save_rgba_png(os.path.join(TEX_DIR, "keyboard_top_emissive_2k.png"), emissive, is_data=False)

if __name__ == "__main__":
    t_start = time.time()
    generate_track_asphalt()
    generate_desk_wood()
    generate_mousepad_fabric()
    generate_keyboard_top()
    print(f"All 11 2K PBR textures generated successfully in {time.time() - t_start:.2f}s!")
