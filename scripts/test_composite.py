import os
import struct
import zlib
import numpy as np

# Load our generated PNG and composite it on a dark touge night background
p = r"c:\Users\yukis\Downloads\car-chase\assets\character\processed\char_takumi_bust.png"
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

# Composite onto dark slate/midnight background (rgb: 15, 22, 35)
bg = np.array([15, 22, 35], dtype=np.float32)
comp = np.zeros((h, w, 3), dtype=np.uint8)
a = rgba[:, :, 3].astype(np.float32) / 255.0
for c in range(3):
    comp[:, :, c] = np.clip(rgba[:, :, c].astype(np.float32) * a + bg[c] * (1.0 - a), 0, 255).astype(np.uint8)

# Write to test_composite.png
def write_rgb_png(filepath, rgb_uint8):
    ch, cw, _ = rgb_uint8.shape
    def chunk(tag, d):
        return struct.pack('>I', len(d)) + tag + d + struct.pack('>I', zlib.crc32(tag + d))
    sig = b'\x89PNG\r\n\x1a\n'
    ihdr = chunk(b'IHDR', struct.pack('>IIBBBBB', cw, ch, 8, 2, 0, 0, 0)) # type 2 = RGB
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

write_rgb_png(r"c:\Users\yukis\Downloads\car-chase\test_composite.png", comp)
print("Composite created on dark background!")

