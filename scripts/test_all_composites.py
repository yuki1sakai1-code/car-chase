import os, struct, zlib, numpy as np

def composite_check(fname, out_name):
    p = os.path.join(r"c:\Users\yukis\Downloads\car-chase\assets\character\processed", fname)
    with open(p, 'rb') as f:
        data = f.read()

    idx = 8
    w, h = 0, 0
    raw_idat = bytearray()
    while idx < len(data):
        length = int.from_bytes(data[idx:idx+4], 'big')
        tag = data[idx+4:idx+8]
        if tag == b'IHDR':
            w = int.from_bytes(data[idx+8:idx+12], 'big')
            h = int.from_bytes(data[idx+12:idx+16], 'big')
        elif tag == b'IDAT':
            raw_idat.extend(data[idx+8:idx+8+length])
        idx += 8 + length + 4

    raw = zlib.decompress(bytes(raw_idat))
    stride = w * 4 + 1
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    for y in range(h):
        line = raw[y * stride + 1 : (y + 1) * stride]
        rgba[y, :, :] = np.frombuffer(line, dtype=np.uint8).reshape((w, 4))

    bg = np.array([18, 25, 38], dtype=np.float32)
    comp = np.zeros((h, w, 3), dtype=np.uint8)
    a = rgba[:, :, 3].astype(np.float32) / 255.0
    for c in range(3):
        comp[:, :, c] = np.clip(rgba[:, :, c].astype(np.float32) * a + bg[c] * (1.0 - a), 0, 255).astype(np.uint8)

    def write_rgb_png(filepath, rgb_uint8):
        ch, cw, _ = rgb_uint8.shape
        def chunk(tag, d):
            return struct.pack('>I', len(d)) + tag + d + struct.pack('>I', zlib.crc32(tag + d))
        sig = b'\x89PNG\r\n\x1a\n'
        ihdr = chunk(b'IHDR', struct.pack('>IIBBBBB', cw, ch, 8, 2, 0, 0, 0))
        raw_lines = bytearray()
        raw_b = rgb_uint8.tobytes()
        st = cw * 3
        for y in range(ch):
            raw_lines.append(0)
            raw_lines.extend(raw_b[y*st : (y+1)*st])
        idat = chunk(b'IDAT', zlib.compress(bytes(raw_lines)))
        iend = chunk(b'IEND', b'')
        with open(filepath, 'wb') as f:
            f.write(sig + ihdr + idat + iend)

    out_p = os.path.join(r"C:\Users\yukis\.gemini\antigravity\brain\a7fa3ca4-5441-4310-b9b2-8667e442a327", out_name)
    write_rgb_png(out_p, comp)
    print(f"Created {out_name}")

composite_check("char_bunta_bust.png", "test_comp_bunta.png")
composite_check("char_mogi_bust.png", "test_comp_mogi.png")

