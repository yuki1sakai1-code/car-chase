import bpy
import numpy as np

p = r"c:\Users\yukis\Downloads\car-chase\assets\character\Gemini_Generated_Image_49me5q49me5q49me.jpe"
img = bpy.data.images.load(p)
w, h = img.size
arr = np.empty(w * h * 4, dtype=np.float32)
img.pixels.foreach_get(arr)
arr = arr.reshape((h, w, 4))
arr = np.flipud(arr)

# Top row: check periodicity of brightness
row0 = (arr[0, :300, 0] + arr[0, :300, 1] + arr[0, :300, 2]) / 3.0
# Find transitions between dark and light
transitions = []
for x in range(1, 300):
    if abs(row0[x] - row0[x-1]) > 0.08:
        transitions.append(x)
print("Horizontal transitions in first 300px:", transitions)
if len(transitions) >= 2:
    diffs = np.diff(transitions)
    print("Grid sizes (widths):", diffs)

# Vertical transitions
col0 = (arr[:300, 0, 0] + arr[:300, 0, 1] + arr[:300, 0, 2]) / 3.0
v_transitions = []
for y in range(1, 300):
    if abs(col0[y] - col0[y-1]) > 0.08:
        v_transitions.append(y)
print("Vertical transitions in first 300px:", v_transitions)
if len(v_transitions) >= 2:
    v_diffs = np.diff(v_transitions)
    print("Grid sizes (heights):", v_diffs)

bpy.data.images.remove(img)

