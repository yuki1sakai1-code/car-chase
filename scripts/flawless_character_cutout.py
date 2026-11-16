import bpy
import os
import struct
import zlib
import numpy as np
from collections import deque

src_dir = r"c:\Users\yukis\Downloads\car-chase\assets\character"
out_dir = r"c:\Users\yukis\Downloads\car-chase\assets\character\processed"
brain_dir = r"C:\Users\yukis\.gemini\antigravity\brain\a7fa3ca4-5441-4310-b9b2-8667e442a327"
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
        raw_lines.append(0) # filter type 0 (None)
        raw_lines.extend(raw_bytes[y * stride : (y + 1) * stride])
        
    idat = chunk(b'IDAT', zlib.compress(bytes(raw_lines), level=6))
    iend = chunk(b'IEND', b'')
    
    with open(filepath, 'wb') as f:
        f.write(sig + ihdr + idat + iend)

def process_character(cfg):
    src_path = os.path.join(src_dir, cfg["src"])
    img = bpy.data.images.load(src_path)
    w, h = img.size
    print(f"Loading {cfg['src']} ({w}x{h})...")
    
    arr = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(arr)
    arr = arr.reshape((h, w, 4))
    # Flip vertically to standard image space (y=0 is top)
    arr = np.flipud(arr)
    
    r = arr[:, :, 0]
    g = arr[:, :, 1]
    b = arr[:, :, 2]
    
    # 1. Detect checkerboard tiles:
    # Difference between channels is very low (neutral gray/white)
    diff = np.maximum(np.maximum(r, g), b) - np.minimum(np.minimum(r, g), b)
    brightness = (r + g + b) / 3.0
    
    # Background checkerboard is neutral gray or white:
    # Grey tile is ~0.82, white tile is ~1.00. Lowest JPEG corner is ~0.76.
    is_checker = (diff < 0.048) & (brightness > 0.72)
    
    # 2. Flood Fill from boundaries to find exterior background
    bg_mask = np.zeros((h, w), dtype=bool)
    q = deque()
    
    # Seed top border (guaranteed background)
    for x in range(w):
        if is_checker[0, x]:
            bg_mask[0, x] = True
            q.append((0, x))
            
    # Seed left and right borders
    for y in range(h):
        if is_checker[y, 0] and not bg_mask[y, 0]:
            bg_mask[y, 0] = True
            q.append((y, 0))
        if is_checker[y, w-1] and not bg_mask[y, w-1]:
            bg_mask[y, w-1] = True
            q.append((y, w-1))
            
    # Seed bottom corners (leaving center where torso sits)
    for x in range(int(w * 0.22)):
        if is_checker[h-1, x] and not bg_mask[h-1, x]:
            bg_mask[h-1, x] = True
            q.append((h-1, x))
    for x in range(int(w * 0.78), w):
        if is_checker[h-1, x] and not bg_mask[h-1, x]:
            bg_mask[h-1, x] = True
            q.append((h-1, x))
            
    # BFS
    while q:
        cy, cx = q.popleft()
        for dy, dx in ((-1,0), (1,0), (0,-1), (0,1)):
            ny, nx = cy + dy, cx + dx
            if 0 <= ny < h and 0 <= nx < w:
                if not bg_mask[ny, nx] and is_checker[ny, nx]:
                    bg_mask[ny, nx] = True
                    q.append((ny, nx))
                    
    # Also catch any isolated checkerboard islands above the shoulders (e.g. between hair locks):
    # Any checkerboard region where brightness > 0.75 and diff < 0.035 that is above the neckline
    # can be checked
    neck_level = int(h * 0.7)
    upper_checker = (diff < 0.038) & (brightness > 0.75)
    upper_checker[neck_level:, :] = False
    bg_mask |= upper_checker
    
    # 3. Create initial foreground mask (inverted background)
    fg_mask = (~bg_mask).astype(np.float32)
    
    # 4. Morphological smoothing to avoid jagged pixel steps & remove white halo:
    # 2D separable box filter
    def box_blur(m, iters=2):
        res = m.copy()
        for _ in range(iters):
            pad_h = np.pad(res, ((0,0), (1,1)), mode='edge')
            res = (pad_h[:, :-2] + 2*pad_h[:, 1:-1] + pad_h[:, 2:]) * 0.25
            pad_v = np.pad(res, ((1,1), (0,0)), mode='edge')
            res = (pad_v[:-2, :] + 2*pad_v[1:-1, :] + pad_v[2:, :]) * 0.25
        return res
        
    blurred_mask = box_blur(fg_mask, iters=3)
    
    # Strict cut to eradicate white fringe:
    # Shift threshold so the outer 1-2 pixels of mixed checkerboard are pushed to 0 alpha
    alpha = np.clip((blurred_mask - 0.38) / 0.50, 0.0, 1.0)
    
    # Smooth the final alpha edge with a subtle 1-tap pass for clean antialiasing
    alpha = box_blur(alpha, iters=1)
    
    # 5. Professional Color Decontamination / Defringing:
    # Along the boundary (0.01 < alpha < 0.98), pixels received light from the white/grey checkerboard tiles.
    # We unmultiply the estimated background (~0.90) and clamp to solid interior color.
    edge_zone = (alpha > 0.01) & (alpha < 0.98)
    bg_color = 0.90
    
    # For color bleeding: sample slightly interior color to prevent white halo
    solid_interior = (alpha >= 0.98)
    
    rgb_clean = arr[:, :, :3].copy()
    for c in range(3):
        col = rgb_clean[:, :, c]
        # Unmultiply background color from mixed edge pixels:
        decontam = (col - bg_color * (1.0 - alpha)) / np.maximum(alpha, 0.2)
        # Apply decontaminated color to edge zone
        col[edge_zone] = np.clip(decontam[edge_zone], 0.0, 1.0)
        rgb_clean[:, :, c] = col
        
    # Construct final RGBA uint8 image
    final_rgba = np.zeros((h, w, 4), dtype=np.uint8)
    for c in range(3):
        final_rgba[:, :, c] = np.clip(rgb_clean[:, :, c] * 255.0, 0, 255).astype(np.uint8)
    final_rgba[:, :, 3] = np.clip(alpha * 255.0, 0, 255).astype(np.uint8)
    
    # 6. Locate character bounds
    ys, xs = np.where(final_rgba[:, :, 3] > 64)
    top_y = ys.min()
    bot_y = ys.max()
    left_x = xs.min()
    right_x = xs.max()
    center_x = (left_x + right_x) // 2
    
    print(f"Character {cfg['tag']}: top_y={top_y}, bot_y={bot_y}, left_x={left_x}, right_x={right_x}")
    
    # 7. Cropping:
    # BUST: From just above head down to bottom of image (full chest and shoulders)
    bust_top = max(0, top_y - 25)
    bust_bot = h
    bust_w = int((right_x - left_x) * 1.15)
    bust_left = max(0, center_x - bust_w // 2)
    bust_right = min(w, center_x + bust_w // 2)
    bust_crop = final_rgba[bust_top:bust_bot, bust_left:bust_right].copy()
    
    # AVATAR: Centered on head and face down to collar
    face_span = int((bot_y - top_y) * 0.54)
    av_top = max(0, top_y - 25)
    av_bot = av_top + face_span
    av_half = face_span // 2
    av_left = max(0, center_x - av_half)
    av_right = min(w, center_x + av_half)
    avatar_crop = final_rgba[av_top:av_bot, av_left:av_right].copy()
    
    # Save using Pure Python lossless 32-bit RGBA PNG encoder
    bust_path1 = os.path.join(out_dir, cfg["bust_name"])
    bust_path2 = os.path.join(brain_dir, cfg["bust_name"])
    write_png_rgba(bust_path1, bust_crop)
    write_png_rgba(bust_path2, bust_crop)
    print(f"Saved {cfg['bust_name']} ({bust_crop.shape[1]}x{bust_crop.shape[0]})")
    
    av_path1 = os.path.join(out_dir, cfg["avatar_name"])
    av_path2 = os.path.join(brain_dir, cfg["avatar_name"])
    write_png_rgba(av_path1, avatar_crop)
    write_png_rgba(av_path2, avatar_crop)
    print(f"Saved {cfg['avatar_name']} ({avatar_crop.shape[1]}x{avatar_crop.shape[0]})")
    
    bpy.data.images.remove(img)

for cfg in configs:
    process_character(cfg)

print("ALL CHARACTER IMAGES FLAWLESSLY EXTRACTED!")

