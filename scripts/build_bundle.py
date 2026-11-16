import base64
import os

base = r"c:\Users\yukis\Downloads\car-chase"
with open(os.path.join(base, "assets", "track_data.json"), "r", encoding="utf-8") as f:
    track_json = f.read()

def b64_file(rel_path):
    p = os.path.join(base, rel_path)
    with open(p, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")

kart_b64 = b64_file(r"assets\models\racing_kart.glb")
track_b64 = b64_file(r"assets\models\race_track.glb")
desk_b64 = b64_file(r"assets\models\desk_environment.glb")

out_js = os.path.join(base, "assets", "game_bundle.js")
with open(out_js, "w", encoding="utf-8") as f:
    f.write("window.__TRACK_DATA__ = " + track_json + ";\n")
    f.write("window.__GLB_B64__ = {\n")
    f.write('  kart: "' + kart_b64 + '",\n')
    f.write('  track: "' + track_b64 + '",\n')
    f.write('  desk: "' + desk_b64 + '"\n')
    f.write("};\n")

print("Created game_bundle.js:", os.path.getsize(out_js), "bytes")

