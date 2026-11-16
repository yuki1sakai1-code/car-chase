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
    x0, x1 = max(0, int(x0)), min(arr.shape[1], int(x1))
    y0, y1 = max(0, int(y0)), min(arr.shape[0], int(y1))
    arr[y0:y1, x0:x0+2] = col
    arr[y0:y1, x1-2:x1] = col
    arr[y0:y0+2, x0:x1] = col
    arr[y1-2:y1, x0:x1] = col

processed_dir = r"c:\Users\yukis\Downloads\car-chase\assets\character\processed"

# 1. Takumi Avatar
takumi = load_png(os.path.join(processed_dir, "char_takumi_avatar.png")).copy()
draw_rect(takumi, 185, 430, 360, 520, (0, 255, 0, 255)) # Left eye
draw_rect(takumi, 415, 430, 590, 520, (0, 255, 0, 255)) # Right eye
draw_rect(takumi, 290, 690, 485, 755, (255, 0, 0, 255)) # Mouth
write_png(r"C:\Users\yukis\.gemini\antigravity\brain\a7fa3ca4-5441-4310-b9b2-8667e442a327\calib_takumi.png", takumi)

# 2. Bunta Avatar
bunta = load_png(os.path.join(processed_dir, "char_bunta_avatar.png")).copy()
bh, bw, _ = bunta.shape
# Bunta's face in avatar
draw_rect(bunta, 205, 300, 375, 385, (0, 255, 0, 255)) # Left eye
draw_rect(bunta, 405, 300, 575, 385, (0, 255, 0, 255)) # Right eye
draw_rect(bunta, 320, 465, 460, 520, (255, 0, 0, 255)) # Mouth
write_png(r"C:\Users\yukis\.gemini\antigravity\brain\a7fa3ca4-5441-4310-b9b2-8667e442a327\calib_bunta.png", bunta)

# 3. Mogi Avatar
mogi = load_png(os.path.join(processed_dir, "char_mogi_avatar.png")).copy()
mh, mw, _ = mogi.shape
draw_rect(mogi, 260, 310, 385, 380, (0, 255, 0, 255)) # Left eye
draw_rect(mogi, 400, 310, 525, 380, (0, 255, 0, 255)) # Right eye
draw_rect(mogi, 325, 460, 455, 510, (255, 0, 0, 255)) # Mouth
write_png(r"C:\Users\yukis\.gemini\antigravity\brain\a7fa3ca4-5441-4310-b9b2-8667e442a327\calib_mogi.png", mogi)

print("Calibration images saved!")

