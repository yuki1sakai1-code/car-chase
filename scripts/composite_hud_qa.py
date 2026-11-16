import bpy
import json
import math
import os
import numpy as np

WORKSPACE = r"c:\Users\yukis\Downloads\car-chase"
ARTIFACT_DIR = r"C:\Users\yukis\.gemini\antigravity\brain\a7fa3ca4-5441-4310-b9b2-8667e442a327"

with open(os.path.join(WORKSPACE, "assets", "track_data.json"), "r") as f:
    track_data = json.load(f)
pts = track_data["points"]

# Simple 5x7 bitmap font for crisp futuristic italic HUD rendering in numpy
FONT_5X7 = {
    'A': ["01110","10001","10001","11111","10001","10001","10001"],
    'B': ["11110","10001","10001","11110","10001","10001","11110"],
    'C': ["01111","10000","10000","10000","10000","10000","01111"],
    'D': ["11110","10001","10001","10001","10001","10001","11110"],
    'E': ["11111","10000","10000","11110","10000","10000","11111"],
    'F': ["11111","10000","10000","11110","10000","10000","10000"],
    'G': ["01111","10000","10000","10011","10001","10001","01111"],
    'H': ["10001","10001","10001","11111","10001","10001","10001"],
    'I': ["11111","00100","00100","00100","00100","00100","11111"],
    'K': ["10001","10010","10100","11000","10100","10010","10001"],
    'L': ["10000","10000","10000","10000","10000","10000","11111"],
    'M': ["10001","11011","10101","10101","10001","10001","10001"],
    'N': ["10001","11001","10101","10011","10001","10001","10001"],
    'O': ["01110","10001","10001","10001","10001","10001","01110"],
    'P': ["11110","10001","10001","11110","10000","10000","10000"],
    'R': ["11110","10001","10001","11110","10100","10010","10001"],
    'S': ["01111","10000","10000","01110","00001","00001","11110"],
    'T': ["11111","00100","00100","00100","00100","00100","00100"],
    'U': ["10001","10001","10001","10001","10001","10001","01110"],
    '0': ["01110","10001","10011","10101","11001","10001","01110"],
    '1': ["00100","01100","00100","00100","00100","00100","01110"],
    '2': ["01110","10001","00001","01110","10000","10000","11111"],
    '3': ["11110","00001","00001","01110","00001","00001","11110"],
    '4': ["10010","10010","10010","11111","00010","00010","00010"],
    '5': ["11111","10000","10000","11110","00001","00001","11110"],
    '6': ["01111","10000","10000","11110","10001","10001","01110"],
    '7': ["11111","00001","00010","00100","01000","01000","01000"],
    '8': ["01110","10001","10001","01110","10001","10001","01110"],
    '9': ["01110","10001","10001","01111","00001","00001","11110"],
    ':': ["00000","00100","00100","00000","00100","00100","00000"],
    '.': ["00000","00000","00000","00000","00000","01100","01100"],
    '/': ["00001","00010","00100","00100","01000","10000","10000"],
    '-': ["00000","00000","00000","11111","00000","00000","00000"],
    ' ': ["00000","00000","00000","00000","00000","00000","00000"],
}

def blend_rect(img, x0, y0, x1, y1, color_rgba):
    H, W, _ = img.shape
    xa, xb = max(0, int(x0)), min(W, int(x1))
    # Note: in Blender image buffer, y=0 is bottom, so convert from top-down y
    ya, yb = max(0, int(H - y1)), min(H, int(H - y0))
    if xa >= xb or ya >= yb:
        return
    alpha = color_rgba[3]
    c = np.array(color_rgba[:3], dtype=np.float32)
    img[ya:yb, xa:xb, :3] = img[ya:yb, xa:xb, :3] * (1.0 - alpha) + c * alpha

def draw_text(img, text, x_top_left, y_top_left, scale=3, color=(1, 1, 1, 1), italic=True, shadow=True):
    if shadow:
        draw_text(img, text, x_top_left + max(1, scale // 2), y_top_left + max(1, scale // 2), scale=scale, color=(0.03, 0.04, 0.07, 0.88), italic=italic, shadow=False)
    cx = x_top_left
    for ch in text.upper():
        glyph = FONT_5X7.get(ch, FONT_5X7[' '])
        for r_idx, row_str in enumerate(glyph):
            skew = int((6 - r_idx) * (scale * 0.28)) if italic else 0
            for c_idx, bit in enumerate(row_str):
                if bit == '1':
                    px0 = cx + c_idx * scale + skew
                    py0 = y_top_left + r_idx * scale
                    blend_rect(img, px0, py0, px0 + scale, py0 + scale, color)
        cx += 6 * scale + max(1, scale // 2)

def draw_line_topdown(img, x0, y0, x1, y1, radius, color_rgba):
    steps = int(max(abs(x1 - x0), abs(y1 - y0)) * 1.5) + 1
    for s in range(steps + 1):
        t = s / float(steps)
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t
        blend_rect(img, x - radius, y - radius, x + radius, y + radius, color_rgba)

def draw_minimap(img, frac):
    min_x = min(p["x"] for p in pts)
    max_x = max(p["x"] for p in pts)
    min_z = min(p["z"] for p in pts)
    max_z = max(p["z"] for p in pts)

    box_x, box_y, box_w, box_h = 34, 720 - 155, 200, 125
    scale = min((box_w - 24) / (max_x - min_x), (box_h - 24) / (max_z - min_z))

    def to_mm(p):
        mx = box_x + 12 + (p["x"] - min_x) * scale
        my = box_y + 12 + (p["z"] - min_z) * scale
        return mx, my

    # Outer dark border pass
    for i in range(0, len(pts), 2):
        p0 = pts[i]
        p1 = pts[(i + 2) % len(pts)]
        x0, y0 = to_mm(p0)
        x1, y1 = to_mm(p1)
        draw_line_topdown(img, x0, y0, x1, y1, 3.8, (0.04, 0.06, 0.10, 0.92))

    # Inner crisp white track ribbon
    for i in range(0, len(pts), 2):
        p0 = pts[i]
        p1 = pts[(i + 2) % len(pts)]
        x0, y0 = to_mm(p0)
        x1, y1 = to_mm(p1)
        draw_line_topdown(img, x0, y0, x1, y1, 1.8, (0.90, 0.94, 0.98, 0.95))

    # Player cyan dot
    cur_idx = int((frac % 1.0) * len(pts)) % len(pts)
    px, py = to_mm(pts[cur_idx])
    blend_rect(img, px - 5, py - 5, px + 5, py + 5, (0.0, 0.92, 1.0, 0.45))
    blend_rect(img, px - 3, py - 3, px + 3, py + 3, (0.18, 0.96, 1.0, 1.0))

def draw_tachometer_and_speed(img, speed_kmh):
    # Curved segmented bar in bottom-right
    base_x = 1280 - 275
    base_y = 720 - 115
    total_segs = 18
    active = int(round((speed_kmh / 112.0) * total_segs))

    for i in range(total_segs):
        if i < 5:
            t = i / 5.0
            sx = base_x + 18 + t * 28
            sy = base_y + 78 - t * 40
        else:
            t = (i - 5) / 13.0
            sx = base_x + 50 + t * 185
            sy = base_y + 35 - t * 25
        if i < active:
            col = (0.75 - 0.65 * (i / 17.0), 0.95, 1.0, 0.95)
        else:
            col = (0.10, 0.16, 0.24, 0.65)
        blend_rect(img, sx, sy, sx + 8, sy + 12, col)

    draw_text(img, "KM/H", 1280 - 102, 720 - 82, scale=2, color=(0.55, 0.82, 0.92, 0.95))
    s_str = str(speed_kmh)
    draw_text(img, s_str, 1280 - 42 - len(s_str) * 28, 720 - 62, scale=5, color=(1.0, 1.0, 1.0, 1.0))

def composite_hud_on_file(in_name, out_name, timer_str, speed_kmh, frac, is_finish=False):
    in_path = os.path.join(ARTIFACT_DIR, in_name)
    out_path = os.path.join(ARTIFACT_DIR, out_name)
    bl_img = bpy.data.images.load(in_path)
    W, H = bl_img.size[0], bl_img.size[1]
    buf = np.zeros((H * W * 4,), dtype=np.float32)
    bl_img.pixels.foreach_get(buf)
    img = buf.reshape((H, W, 4))

    if is_finish:
        # Slightly dim background for finish modal
        img[:, :, :3] *= 0.45

    # 1. Top-Left Title: DESK RACER
    draw_text(img, "DESK RACER", 36, 28, scale=4, color=(1.0, 0.62, 0.24, 1.0))

    # 2. Top-Right: LAP 3/3 + Timer + Sound Button
    draw_text(img, "LAP", 1280 - 195, 24, scale=2, color=(0.95, 0.97, 1.0, 1.0))
    draw_text(img, "3", 1280 - 142, 24, scale=2, color=(0.15, 0.92, 1.0, 1.0))
    draw_text(img, "/3", 1280 - 126, 24, scale=2, color=(0.95, 0.97, 1.0, 1.0))
    draw_text(img, timer_str, 1280 - 285, 45, scale=4, color=(1.0, 1.0, 1.0, 1.0))

    # Sound button box
    blend_rect(img, 1280 - 68, 24, 1280 - 34, 54, (0.06, 0.08, 0.12, 0.85))

    # 3. Bottom-Left Minimap
    draw_minimap(img, frac)

    # 4. Bottom-Right Speedometer
    draw_tachometer_and_speed(img, speed_kmh)

    # 5. Center FINISH Modal (if is_finish)
    if is_finish:
        mw, mh = 430, 310
        mx0, my0 = (W - mw) // 2, (H - mh) // 2
        blend_rect(img, mx0, my0, mx0 + mw, my0 + mh, (0.04, 0.07, 0.12, 0.94))
        # Top cyan highlight bar
        blend_rect(img, mx0, my0, mx0 + mw, my0 + 3, (0.25, 0.92, 1.0, 1.0))
        draw_text(img, "DESKTOP CIRCUIT - 3 LAPS COMPLETE", mx0 + 48, my0 + 28, scale=1, color=(0.30, 0.90, 1.0, 1.0), shadow=False)
        draw_text(img, "FINISH", mx0 + 138, my0 + 54, scale=4, color=(1.0, 0.78, 0.45, 1.0))
        draw_text(img, "00:51.23", mx0 + 88, my0 + 102, scale=5, color=(1.0, 1.0, 1.0, 1.0))
        draw_text(img, "BEST LAP 00:16.66", mx0 + 132, my0 + 154, scale=1, color=(0.45, 0.82, 0.95, 1.0), shadow=False)

        # Button 1: RACE AGAIN [ENTER]
        bx0, by0, bw, bh = mx0 + 85, my0 + 184, 260, 42
        blend_rect(img, bx0, by0, bx0 + bw, by0 + bh, (0.12, 0.24, 0.32, 0.92))
        blend_rect(img, bx0, by0, bx0 + bw, by0 + 2, (0.28, 0.88, 1.0, 1.0))
        draw_text(img, "RACE AGAIN  ENTER", bx0 + 24, by0 + 14, scale=2, color=(1.0, 1.0, 1.0, 1.0), shadow=False)

        # Button 2: AUTO-PILOT [P]
        by1 = my0 + 240
        blend_rect(img, bx0, by1, bx0 + bw, by1 + bh, (0.08, 0.18, 0.25, 0.92))
        blend_rect(img, bx0, by1, bx0 + bw, by1 + 2, (0.28, 0.88, 1.0, 0.85))
        draw_text(img, "AUTO-PILOT  P", bx0 + 48, by1 + 14, scale=2, color=(1.0, 1.0, 1.0, 1.0), shadow=False)

    out_img = bpy.data.images.new("OutHUD", width=W, height=H, alpha=True)
    out_img.pixels.foreach_set(img.ravel())
    out_img.filepath_raw = out_path
    out_img.file_format = 'PNG'
    out_img.save()
    print(f"Saved HUD composite: {out_path}")

configs = [
    ("qa_1_curbs.png", "qa_hud_1_curbs.png", "00:42.98", 94, 0.54, False),
    ("qa_2_finish_bg.png", "qa_hud_2_finish.png", "00:51.23", 0, 0.03, True),
    ("qa_3_ramp.png", "qa_hud_3_ramp.png", "00:44.77", 68, 0.14, False),
    ("qa_4_keyboard.png", "qa_hud_4_keyboard.png", "00:46.47", 87, 0.43, False),
    ("qa_5_descent.png", "qa_hud_5_descent.png", "00:49.05", 83, 0.91, False),
]

for cfg in configs:
    composite_hud_on_file(*cfg)

