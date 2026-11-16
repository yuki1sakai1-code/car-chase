import bpy
import os
import numpy as np

src_dir = r"c:\Users\yukis\Downloads\car-chase\assets\character"
for name in sorted(os.listdir(src_dir)):
    if name.endswith('.jpe'):
        p = os.path.join(src_dir, name)
        img = bpy.data.images.load(p)
        w, h = img.size
        arr = np.empty(w * h * 4, dtype=np.float32)
        img.pixels.foreach_get(arr)
        arr = arr.reshape((h, w, 4))
        # Top-left corner in standard top-to-bottom coordinates
        arr_flipped = np.flipud(arr)
        corner = arr_flipped[0:50, 0:50, :3]
        print(f"=== {name} ({w}x{h}) ===")
        print("R range:", corner[:, :, 0].min(), corner[:, :, 0].max())
        print("G range:", corner[:, :, 1].min(), corner[:, :, 1].max())
        print("B range:", corner[:, :, 2].min(), corner[:, :, 2].max())
        # Check saturation/diff
        diff = np.maximum(np.maximum(corner[:, :, 0], corner[:, :, 1]), corner[:, :, 2]) - np.minimum(np.minimum(corner[:, :, 0], corner[:, :, 1]), corner[:, :, 2])
        print("Max RGB diff in corner 50x50:", diff.max())
        # Sample of colors in top row
        print("Row 0 colors (every 5 pixels):")
        for x in range(0, 50, 5):
            print(f"  x={x}: rgb=({corner[0, x, 0]:.3f}, {corner[0, x, 1]:.3f}, {corner[0, x, 2]:.3f})")
        bpy.data.images.remove(img)

