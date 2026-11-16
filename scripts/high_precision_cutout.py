import bpy
import os
import numpy as np

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

from collections import deque

def process_image(cfg):
    src_path = os.path.join(src_dir, cfg["src"])
    img = bpy.data.images.load(src_path)
    w, h = img.size
    print(f"Processing {cfg['src']} ({w}x{h})...")
    
    arr = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(arr)
    arr = arr.reshape((h, w, 4))
    arr = np.flipud(arr) # y=0 top, y=h-1 bottom
    
    rgb = arr[:, :, :3]
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    
    # 1. Color saturation (max - min) and brightness
    c_max = np.maximum(np.maximum(r, g), b)
    c_min = np.minimum(np.minimum(r, g), b)
    diff = c_max - c_min
    brightness = (r + g + b) / 3.0
    
    # Background checkerboard is pure neutral gray/white with brightness >= 0.75
    # Even in JPEG artifacts, diff is <= 0.05 and brightness >= 0.74
    is_bg_candidate = (diff < 0.045) & (brightness > 0.74)
    
    # 2. Flood Fill from all borders to find definite exterior background
    bg_mask = np.zeros((h, w), dtype=bool)
    q = deque()
    
    # Top border & bottom corners
    for x in range(w):
        if is_bg_candidate[0, x]:
            bg_mask[0, x] = True
            q.append((0, x))
        if is_bg_candidate[h-1, x] and (x < w * 0.2 or x > w * 0.8):
            bg_mask[h-1, x] = True
            q.append((h-1, x))
            
    # Left & Right borders
    for y in range(h):
        if is_bg_candidate[y, 0] and not bg_mask[y, 0]:
            bg_mask[y, 0] = True
            q.append((y, 0))
        if is_bg_candidate[y, w-1] and not bg_mask[y, w-1]:
            bg_mask[y, w-1] = True
            q.append((y, w-1))
            
    while q:
        cy, cx = q.popleft()
        for dy, dx in ((-1,0), (1,0), (0,-1), (0,1)):
            ny, nx = cy + dy, cx + dx
            if 0 <= ny < h and 0 <= nx < w:
                if not bg_mask[ny, nx] and is_bg_candidate[ny, nx]:
                    bg_mask[ny, nx] = True
                    q.append((ny, nx))
                    
    # Also find any isolated checkerboard islands inside hair loops or near edges:
    # A region where brightness > 0.76 and diff < 0.035 is definitely checkerboard background
    pure_checker = (diff < 0.032) & (brightness > 0.76)
    # If it is connected to pure checker pixels, treat as bg
    bg_mask |= pure_checker

    # 3. Create high-quality smooth alpha matte
    # Foreground mask: inverted background mask
    fg_mask = (~bg_mask).astype(np.float32)
    
    alpha = fg_mask.copy()
    
    # Custom fast separable 2D box/gaussian blur for smooth alpha & defringe
    def fast_blur(img2d, r=1.5):
        # 3-pass separable box blur approximates Gaussian blur closely
        res = img2d.copy()
        k_size = int(r * 2) + 1
        # Simple kernel [1, 2, 1] / 4 or 5-tap
        for _ in range(2):
            # Horizontal pass
            padded = np.pad(res, ((0,0), (1,1)), mode='edge')
            res = (padded[:, :-2] + 2*padded[:, 1:-1] + padded[:, 2:]) * 0.25
            # Vertical pass
            padded = np.pad(res, ((1,1), (0,0)), mode='edge')
            res = (padded[:-2, :] + 2*padded[1:-1, :] + padded[2:, :]) * 0.25
        return res

    # 4. Color Defringing (Crucial for removing the white fringe along hair strands!):
    # Where alpha is between 0.05 and 0.95, the pixel color was blended with background (checkerboard ~0.9).
    # We estimate unblended foreground color by color decontamination.
    # Erode the foreground by 1-2 pixels to find confident foreground colors, then bleed inward.
    
    # Smooth alpha slightly for antialiased subpixel edge
    alpha_smooth = fast_blur(alpha, r=1.2)
    
    # Strict thresholding to cut off checkerboard fringe:
    # Any pixel with alpha_smooth < 0.35 becomes 0
    # Any pixel with alpha_smooth > 0.85 becomes 1.0
    alpha_clean = np.clip((alpha_smooth - 0.25) / 0.55, 0.0, 1.0)
    
    # Color decontamination:
    # Darken pixels near the edge that caught white/gray checkerboard reflections
    edge_zone = (alpha_clean > 0.01) & (alpha_clean < 0.95)
    # Estimate background color (checkerboard average ~0.90)
    bg_est = 0.90
    for c in range(3):
        # unmultiply: fg = (pixel - bg*(1-a)) / a
        col = arr[:, :, c]
        # Only decontaminate if color was brightened by background
        decontam = (col - bg_est * (1.0 - alpha_clean)) / np.maximum(alpha_clean, 0.15)
        # Blend decontaminated color into edge zone
        arr[edge_zone, c] = np.clip(decontam[edge_zone], 0.0, 1.0)

    arr[:, :, 3] = alpha_clean
    
    # 5. Crop dimensions
    ys, xs = np.where(alpha_clean > 0.5)
    top_y = ys.min()
    bot_y = ys.max()
    left_x = xs.min()
    right_x = xs.max()
    center_x = (left_x + right_x) // 2
    
    print(f"Bounds for {cfg['tag']}: y=[{top_y}, {bot_y}], x=[{left_x}, {right_x}], center={center_x}")
    
    # Bust crop: upper chest/shoulders to top of head with comfortable margin
    bust_top = max(0, top_y - 30)
    bust_bot = h
    bust_left = max(0, left_x - 30)
    bust_right = min(w, right_x + 30)
    bust_crop = arr[bust_top:bust_bot, bust_left:bust_right].copy()
    
    # Avatar crop: square portrait of face and hair
    face_h = int((bot_y - top_y) * 0.55)
    av_top = max(0, top_y - 25)
    av_bot = av_top + face_h
    half_w = face_h // 2
    av_left = max(0, center_x - half_w)
    av_right = min(w, center_x + half_w)
    avatar_crop = arr[av_top:av_bot, av_left:av_right].copy()
    
    def save_crop(crop_data, filename):
        ch, cw, _ = crop_data.shape
        flipped = np.flipud(crop_data)
        out_img = bpy.data.images.new(filename, width=cw, height=ch, alpha=True)
        out_img.pixels.foreach_set(flipped.flatten())
        out_img.file_format = 'PNG'
        out_path = os.path.join(out_dir, filename)
        out_img.filepath_raw = out_path
        out_img.save()
        brain_path = os.path.join(brain_dir, filename)
        out_img.filepath_raw = brain_path
        out_img.save()
        bpy.data.images.remove(out_img)
        print(f"Saved {filename} ({cw}x{ch})")
        
    save_crop(bust_crop, cfg["bust_name"])
    save_crop(avatar_crop, cfg["avatar_name"])
    bpy.data.images.remove(img)

for cfg in configs:
    process_image(cfg)

print("HIGH PRECISION CUTOUT COMPLETED!")
