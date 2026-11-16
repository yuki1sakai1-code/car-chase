import os, struct, zlib, numpy as np

def load_png(path):
    with open(path, 'rb') as f:
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
    return rgba

def write_png(filepath, rgba_uint8):
    h, w, _ = rgba_uint8.shape
    def chunk(tag, data):
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data))
    sig = b'\x89PNG\r\n\x1a\n'
    ihdr = chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
    raw_lines = bytearray()
    raw_bytes = rgba_uint8.tobytes()
    stride = w * 4
    for y in range(h):
        raw_lines.append(0)
        raw_lines.extend(raw_bytes[y * stride : (y + 1) * stride])
    idat = chunk(b'IDAT', zlib.compress(bytes(raw_lines)))
    iend = chunk(b'IEND', b'')
    with open(filepath, 'wb') as f:
        f.write(sig + ihdr + idat + iend)

def draw_rect(arr, x0, y0, x1, y1, col=(255, 0, 0, 255)):
    arr[y0:y1, x0:x0+2] = col
    arr[y0:y1, x1-2:x1] = col
    arr[y0:y0+2, x0:x1] = col
    arr[y1-2:y1, x0:x1] = col

p = r"c:\Users\yukis\Downloads\car-chase\assets\character\processed\char_takumi_avatar.png"
img = load_png(p).copy()
h, w, _ = img.shape
print("Dimensions:", w, h)

# Left eye (viewer's left):
draw_rect(img, 245, 595, 410, 680, (0, 255, 0, 255))
# Right eye (viewer's right):
draw_rect(img, 490, 595, 655, 680, (0, 255, 0, 255))
# Mouth:
draw_rect(img, 340, 890, 560, 960, (255, 0, 0, 255))

write_png(r"C:\Users\yukis\.gemini\antigravity\brain\a7fa3ca4-5441-4310-b9b2-8667e442a327\test_features_takumi2.png", img)
print("Saved test_features_takumi2.png")
