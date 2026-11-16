import bpy, numpy as np

p = r"c:\Users\yukis\Downloads\car-chase\assets\character\Gemini_Generated_Image_nw7erjnw7erjnw7e.jpe"
img = bpy.data.images.load(p)
w, h = img.size
arr = np.empty(w * h * 4, dtype=np.float32)
img.pixels.foreach_get(arr)
arr = arr.reshape((h, w, 4))
arr = np.flipud(arr)

r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
diff = np.maximum(np.maximum(r, g), b) - np.minimum(np.minimum(r, g), b)
brightness = (r + g + b) / 3.0

# Checkerboard in the hole near neck
# Let's inspect region around x: 800-1100, y: 500-1000 (left hole) and x: 1600-1900, y: 500-1000 (right hole)
is_checker = (diff < 0.048) & (brightness > 0.72)

# Check connected components of is_checker
visited = np.zeros((h, w), dtype=bool)
components = []
for y in range(h):
    for x in range(w):
        if is_checker[y, x] and not visited[y, x]:
            comp = []
            q = [(y, x)]
            visited[y, x] = True
            touches_border = False
            while q:
                cy, cx = q.pop()
                comp.append((cy, cx))
                if cy == 0 or cy == h-1 or cx == 0 or cx == w-1:
                    touches_border = True
                for dy, dx in ((-1,0), (1,0), (0,-1), (0,1)):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < h and 0 <= nx < w:
                        if is_checker[ny, nx] and not visited[ny, nx]:
                            visited[ny, nx] = True
                            q.append((ny, nx))
            if not touches_border and len(comp) > 500:
                ys = [p[0] for p in comp]
                xs = [p[1] for p in comp]
                print(f"Internal checkerboard island: count={len(comp)}, y=[{min(ys)}, {max(ys)}], x=[{min(xs)}, {max(xs)}]")

bpy.data.images.remove(img)
