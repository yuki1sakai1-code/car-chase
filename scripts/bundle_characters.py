import os
import base64

proc_dir = r"c:\Users\yukis\Downloads\car-chase\assets\character\processed"
b64_dict = {}
for fname in os.listdir(proc_dir):
    if fname.endswith(".png"):
        fpath = os.path.join(proc_dir, fname)
        with open(fpath, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
            b64_dict[fname] = f"data:image/png;base64,{b64}"
        print(f"{fname}: {os.path.getsize(fpath)} bytes")

out_js = r"c:\Users\yukis\Downloads\car-chase\assets\character_bundle.js"
with open(out_js, "w", encoding="utf-8") as f:
    f.write("window.__CHARACTERS__ = {\n")
    for k, v in b64_dict.items():
        f.write(f'  "{k}": "{v}",\n')
    f.write("};\n")
print("Wrote assets/character_bundle.js successfully!")

