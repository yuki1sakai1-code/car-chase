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

for cfg in configs:
    src_path = os.path.join(src_dir, cfg["src"])
    img = bpy.data.images.load(src_path)
    w, h = img.size
    print(f"Loaded {cfg['src']} ({w}x{h})")

    arr = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(arr)
    arr = arr.reshape((h, w, 4))
    
    # Flip vertically so Y=0 is TOP and Y=h-1 is BOTTOM
    arr = np.flipud(arr)
    
    r = arr[:, :, 0]
    g = arr[:, :, 1]
    b = arr[:, :, 2]
    
    diff = np.maximum(np.maximum(r, g), b) - np.minimum(np.minimum(r, g), b)
    is_checker_gray = (diff < 0.04) & (r > 0.72)
    
    # Flood-fill background mask from borders (top, left, right)
    bg_mask = np.zeros((h, w), dtype=bool)
    from collections import deque
    q = deque()
    
    # Top border (always checkerboard)
    for x in range(w):
        if is_checker_gray[0, x]:
            bg_mask[0, x] = True
            q.append((0, x))
            
    # Left and Right borders
    for y in range(h):
        if is_checker_gray[y, 0] and not bg_mask[y, 0]:
            bg_mask[y, 0] = True
            q.append((y, 0))
        if is_checker_gray[y, w - 1] and not bg_mask[y, w - 1]:
            bg_mask[y, w - 1] = True
            q.append((y, w - 1))
            
    # BFS
    while q:
        cy, cx = q.popleft()
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ny, nx = cy + dy, cx + dx
            if 0 <= ny < h and 0 <= nx < w:
                if not bg_mask[ny, nx] and is_checker_gray[ny, nx]:
                    bg_mask[ny, nx] = True
                    q.append((ny, nx))
                    
    # Character mask
    char_mask = ~bg_mask
    
    # Set alpha: 0 where bg_mask, 1 where character
    arr[:, :, 3] = char_mask.astype(np.float32)
    
    # Find head top and shoulders
    ys, xs = np.where(char_mask)
    top_y = ys.min()
    bot_y = ys.max()
    left_x = xs.min()
    right_x = xs.max()
    center_x = (left_x + right_x) // 2
    
    print(f"{cfg['tag']}: top_y={top_y}, bot_y={bot_y}, left_x={left_x}, right_x={right_x}, center_x={center_x}")
    
    # 1. BUST CROP:
    # From top_y - 20 down to bottom of image (full torso / shoulders)
    bust_top = max(0, top_y - 25)
    bust_bot = h
    bust_left = max(0, left_x - 30)
    bust_right = min(w, right_x + 30)
    bust_crop = arr[bust_top:bust_bot, bust_left:bust_right].copy()
    
    # 2. AVATAR CROP:
    # Square / circle portrait focusing on head & face
    # From head top down to upper collar/chest
    face_height = int((bot_y - top_y) * 0.54)
    av_top = max(0, top_y - 25)
    av_bot = av_top + face_height
    half_w = face_height // 2
    av_left = max(0, center_x - half_w)
    av_right = min(w, center_x + half_w)
    avatar_crop = arr[av_top:av_bot, av_left:av_right].copy()
    
    def save_png(crop, filename):
        ch, cw, _ = crop.shape
        # Flip back to Blender bottom-to-top layout
        flipped = np.flipud(crop)
        out_img = bpy.data.images.new(filename, width=cw, height=ch, alpha=True)
        out_img.pixels.foreach_set(flipped.flatten())
        out_img.file_format = 'PNG'
        out_path = os.path.join(out_dir, filename)
        out_img.filepath_raw = out_path
        out_img.save()
        
        # Also copy to brain dir for review
        brain_path = os.path.join(brain_dir, filename)
        out_img.filepath_raw = brain_path
        out_img.save()
        
        bpy.data.images.remove(out_img)
        print(f"Saved {filename} ({cw}x{ch})")
        
    save_png(bust_crop, cfg["bust_name"])
    save_png(avatar_crop, cfg["avatar_name"])
    bpy.data.images.remove(img)

print("All character portraits successfully generated!")
