import os
import base64
import glob

chapters_dir = r'assets\chapters'
jpg_files = sorted(glob.glob(os.path.join(chapters_dir, 'chapter_*.jpg')))
print(f'Found {len(jpg_files)} thumbnail files.')

out_js = 'window.__CHAPTER_THUMBS__ = {\n'
for fpath in jpg_files:
    fname = os.path.basename(fpath)
    with open(fpath, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode('ascii')
    out_js += f"  '{fname}': 'data:image/jpeg;base64,{b64}',\n"
out_js += '};\n'

bundle_path = r'assets\chapter_bundle.js'
with open(bundle_path, 'w', encoding='utf-8') as f:
    f.write(out_js)

print(f'Wrote {bundle_path} ({os.path.getsize(bundle_path)} bytes).')
