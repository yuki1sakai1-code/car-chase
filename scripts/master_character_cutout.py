import bpy
import os
import struct
import zlib
import base64
import numpy as np
from collections import deque

src_dir = r"c:\Users\yukis\Downloads\car-chase\assets\character"
out_dir = r"c:\Users\yukis\Downloads\car-chase\assets\character\processed"
brain_dir = r"C:\Users\yukis\.gemini\antigravity\brain\a7fa3ca4-5441-4310-b9b2-8667e442a327"
bundle_js_path = r"c:\Users\yukis\Downloads\car-chase\assets\character_bundle.js"
os.makedirs(out_dir, exist_ok=True)

configs = [
    {
        "src": "Gemini_Generated_Image_49me5q49me5q49me.jpe",
        "tag": "takumi",
        "bust_name": "char_takumi_bust.png",
        "avatar_name": "char_takumi_avatar.png"
    },
    {
        "src": "Gemini_Generated_Image_gr4kh5gr4kh5gr4k.jpe",
        "tag": "bunta",
        "bust_name": "char_bunta_bust.png",
        "avatar_name": "char_bunta_avatar.png"
    },
    {
        "src": "Gemini_Generated_Image_nw7erjnw7erjnw7e.jpe",
        "tag": "mogi",
        "bust_name": "char_mogi_bust.png",
        "avatar_name": "char_mogi_avatar.png"
    }
]

def write_png_rgba(filepath, rgba_uint8):
    h, w, c = rgba_uint8.shape
    assert c == 4, "Must be RGBA"
    
    def chunk(tag, data):
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data))
        
    sig = b'\x89PNG\r\n\x1a\n'
    ihdr = chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
    
    raw_lines = bytearray()
    raw_bytes = rgba_uint8.tobytes()
    stride = w * 4
    for y in range(h):
        raw_lines.append(0) # filter type 0
        raw_lines.extend(raw_bytes[y * stride : (y + 1) * stride])
        
    idat = chunk(b'IDAT', zlib.compress(bytes(raw_lines), level=6))
    iend = chunk(b'IEND', b'')
    
    with open(filepath, 'wb') as f:
        f.write(sig + ihdr + idat + iend)

generated_files = {}

for cfg in configs:
    src_path = os.path.join(src_dir, cfg["src"])
    img = bpy.data.images.load(src_path)
    w, h = img.size
    print(f"=== Processing {cfg['src']} ({w}x{h}) ===")
    
    arr = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(arr)
    arr = arr.reshape((h, w, 4))
    # Flip vertically to top-to-bottom standard coordinate system
    arr = np.flipud(arr)
    
    r = arr[:, :, 0]
    g = arr[:, :, 1]
    b = arr[:, :, 2]
    
    # 1. Background checkerboard condition:
    # JPEG artifacts mean grayscale difference is up to 0.048, brightness is >= 0.72
    diff = np.maximum(np.maximum(r, g), b) - np.minimum(np.minimum(r, g), b)
    brightness = (r + g + b) / 3.0
    is_checker_candidate = (diff < 0.05) & (brightness > 0.72)
    
    # 2. Strict Exterior Flood-Fill (BFS) ONLY from outer borders:
    # Character interior (sclera/whites of eyes, teeth, white shirt collar, skin specular)
    # is completely isolated by the dark silhouette of hair, pupils, jawline, clothing.
    # Therefore, ONLY exterior background will be reached!
    bg_mask = np.zeros((h, w), dtype=bool)
    q = deque()
    
    # Seed top border (100% background)
    for x in range(w):
        if is_checker_candidate[0, x]:
            bg_mask[0, x] = True
            q.append((0, x))
            
    # Seed left and right borders
    for y in range(h):
        if is_checker_candidate[y, 0] and not bg_mask[y, 0]:
            bg_mask[y, 0] = True
            q.append((y, 0))
        if is_checker_candidate[y, w-1] and not bg_mask[y, w-1]:
            bg_mask[y, w-1] = True
            q.append((y, w-1))
            
    # Seed bottom corners where shoulders do not reach
    for x in range(int(w * 0.20)):
        if is_checker_candidate[h-1, x] and not bg_mask[h-1, x]:
            bg_mask[h-1, x] = True
            q.append((h-1, x))
    for x in range(int(w * 0.80), w):
        if is_checker_candidate[h-1, x] and not bg_mask[h-1, x]:
            bg_mask[h-1, x] = True
            q.append((h-1, x))
            
    # BFS propagation
    while q:
        cy, cx = q.popleft()
        for dy, dx in ((-1,0), (1,0), (0,-1), (0,1)):
            ny, nx = cy + dy, cx + dx
            if 0 <= ny < h and 0 <= nx < w:
                if not bg_mask[ny, nx] and is_checker_candidate[ny, nx]:
                    bg_mask[ny, nx] = True
                    q.append((ny, nx))
                    
    # Special: For characters with hair loops/curls (like Mogi's bob hair),
    # include checkerboard islands outside the face corridor (x < 1080 or x > 1680, y < 900)
    # The eyes/face are strictly inside x in [1120, 1640], so this safely clears the hair gap!
    if cfg["tag"] == "mogi":
        hair_gap_checker = is_checker_candidate & (brightness > 0.74)
        hair_gap_checker[900:, :] = False
        hair_gap_checker[:, 1080:1680] = False
        bg_mask |= hair_gap_checker

    # Foreground mask is the EXACT inverse of the exterior background
    fg_mask = (~bg_mask).astype(np.float32)
    
    # 3. Antialiased Edge Feathering & Defringing:
    # Fast separable blur on mask
    def box_blur(m, iters=2):
        res = m.copy()
        for _ in range(iters):
            pad_h = np.pad(res, ((0,0), (1,1)), mode='edge')
            res = (pad_h[:, :-2] + 2*pad_h[:, 1:-1] + pad_h[:, 2:]) * 0.25
            pad_v = np.pad(res, ((1,1), (0,0)), mode='edge')
            res = (pad_v[:-2, :] + 2*pad_v[1:-1, :] + pad_v[2:, :]) * 0.25
        return res
        
    blurred = box_blur(fg_mask, iters=2)
    
    # Sharp cut right at the silhouette to completely eliminate checkerboard gray/white fringe:
    # Pixels where blurred < 0.40 become 0 (transparent)
    # Pixels where blurred > 0.85 become 1 (fully opaque)
    alpha = np.clip((blurred - 0.38) / 0.47, 0.0, 1.0)
    
    # Subtle 1-tap antialiasing on alpha
    alpha = box_blur(alpha, iters=1)
    
    # 4. Color Decontamination (Defringe):
    # Where alpha is fractional (0.02 to 0.98), the color had checkerboard tint.
    # Unmultiply the estimated background (0.90) and decontaminate:
    edge_zone = (alpha > 0.02) & (alpha < 0.98)
    rgb_clean = arr[:, :, :3].copy()
    bg_color = 0.90
    for c in range(3):
        col = rgb_clean[:, :, c]
        decontam = (col - bg_color * (1.0 - alpha)) / np.maximum(alpha, 0.25)
        col[edge_zone] = np.clip(decontam[edge_zone], 0.0, 1.0)
        # Clear RGB to 0 where alpha is 0
        col[alpha <= 0.005] = 0.0
        rgb_clean[:, :, c] = col
        
    final_rgba = np.zeros((h, w, 4), dtype=np.uint8)
    for c in range(3):
        final_rgba[:, :, c] = np.clip(rgb_clean[:, :, c] * 255.0, 0, 255).astype(np.uint8)
    final_rgba[:, :, 3] = np.clip(alpha * 255.0, 0, 255).astype(np.uint8)
    
    # 5. Crop dimensions
    ys, xs = np.where(final_rgba[:, :, 3] > 64)
    top_y = ys.min()
    bot_y = ys.max()
    left_x = xs.min()
    right_x = xs.max()
    center_x = (left_x + right_x) // 2
    
    # BUST: From just above head down to bottom of image (full chest and shoulders)
    bust_top = max(0, top_y - 30)
    bust_bot = h
    bust_w = int((right_x - left_x) * 1.15)
    bust_left = max(0, center_x - bust_w // 2)
    bust_right = min(w, center_x + bust_w // 2)
    bust_crop = final_rgba[bust_top:bust_bot, bust_left:bust_right].copy()
    
    # AVATAR: Centered on head, face, jaw and collar (72% of total height to comfortably include chin & neck)
    face_span = int((bot_y - top_y) * 0.72)
    av_top = max(0, top_y - 25)
    av_bot = av_top + face_span
    av_half = face_span // 2
    av_left = max(0, center_x - av_half)
    av_right = min(w, center_x + av_half)
    avatar_crop = final_rgba[av_top:av_bot, av_left:av_right].copy()
    
    # Save files
    bust_p1 = os.path.join(out_dir, cfg["bust_name"])
    bust_p2 = os.path.join(brain_dir, cfg["bust_name"])
    write_png_rgba(bust_p1, bust_crop)
    write_png_rgba(bust_p2, bust_crop)
    generated_files[cfg["bust_name"]] = bust_p1
    
    av_p1 = os.path.join(out_dir, cfg["avatar_name"])
    av_p2 = os.path.join(brain_dir, cfg["avatar_name"])
    write_png_rgba(av_p1, avatar_crop)
    write_png_rgba(av_p2, avatar_crop)
    generated_files[cfg["avatar_name"]] = av_p1
    
    print(f"  -> Saved {cfg['bust_name']} ({bust_crop.shape[1]}x{bust_crop.shape[0]})")
    print(f"  -> Saved {cfg['avatar_name']} ({avatar_crop.shape[1]}x{avatar_crop.shape[0]})")
    bpy.data.images.remove(img)

# 6. Re-bundle into assets/character_bundle.js so the browser receives the flawless images instantly!
print("Re-generating assets/character_bundle.js...")
bundle_dict = {}
for fname, fpath in generated_files.items():
    with open(fpath, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode('ascii')
        bundle_dict[fname] = f"data:image/png;base64,{b64}"

with open(bundle_js_path, 'w', encoding='utf-8') as f:
    f.write("window.__CHARACTERS__ = {\n")
    items = list(bundle_dict.items())
    for i, (k, v) in enumerate(items):
        comma = "," if i < len(items) - 1 else ""
        f.write(f'  "{k}": "{v}"{comma}\n')
    f.write("};\n")

print(f"Updated {bundle_js_path} successfully!")
print("ALL DONE!")
