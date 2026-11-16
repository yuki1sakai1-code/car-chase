import bpy
import os
import numpy as np

src_dir = r"c:\Users\yukis\Downloads\car-chase\assets\character"

for name in sorted(os.listdir(src_dir)):
    if not name.endswith('.jpe'):
        continue
    p = os.path.join(src_dir, name)
    img = bpy.data.images.load(p)
    w, h = img.size
    arr = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(arr)
    arr = arr.reshape((h, w, 4))
    arr = np.flipud(arr) # Standard image coordinates: y=0 top, y=h-1 bottom
    
    r = arr[:, :, 0]
    g = arr[:, :, 1]
    b = arr[:, :, 2]
    
    # Check the checkerboard periodicity and color values
    # Look at top 100 lines (which is pure background)
    top_strip = arr[0:100, 0:500, :3]
    diff = np.max(top_strip, axis=2) - np.min(top_strip, axis=2)
    brightness = np.mean(top_strip, axis=2)
    
    print(f"=== {name} ===")
    print(f"Top strip: max diff={diff.max():.4f}, mean diff={diff.mean():.4f}")
    print(f"Brightness range: {brightness.min():.4f} to {brightness.max():.4f}")
    
    # Histograms of brightness in top strip
    hist, bin_edges = np.histogram(brightness, bins=10)
    for b_idx in range(len(hist)):
        print(f"  [{bin_edges[b_idx]:.3f} - {bin_edges[b_idx+1]:.3f}]: {hist[b_idx]} px")
        
    bpy.data.images.remove(img)

