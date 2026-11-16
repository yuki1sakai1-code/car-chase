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

# Let's inspect char_takumi_avatar.png, char_bunta_avatar.png, char_mogi_avatar.png
processed_dir = r"c:\Users\yukis\Downloads\car-chase\assets\character\processed"
for name in ["char_takumi_avatar.png", "char_bunta_avatar.png", "char_mogi_avatar.png"]:
    p = os.path.join(processed_dir, name)
    img = load_png(p)
    h, w, _ = img.shape
    print(f"=== {name} ({w}x{h}) ===")
    
    # Let's locate the eyes: dark pixels (pupil/iris) surrounded by skin or sclera in upper half
    # Find min brightness in row range y: [0.35*h, 0.6*h]
    y_min, y_max = int(0.35 * h), int(0.6 * h)
    gray = (img[:, :, 0].astype(float) + img[:, :, 1].astype(float) + img[:, :, 2].astype(float)) / 3.0
    
    # Eye row: row with darkest pupils
    pupil_row = y_min + np.argmin(gray[y_min:y_max, int(0.25*w):int(0.75*w)].mean(axis=1))
    print(f"Estimated eye center row: y={pupil_row} (~{pupil_row/h:.2f}h)")
    
    # Mouth row: row with red/lip hue in range [0.65*h, 0.85*h]
    m_y_min, m_y_max = int(0.65 * h), int(0.85 * h)
    # lips have higher red than green
    lip_diff = (img[m_y_min:m_y_max, int(0.35*w):int(0.65*w), 0].astype(float) - 
                img[m_y_min:m_y_max, int(0.35*w):int(0.65*w), 1].astype(float))
    # Mouth line is dark
    mouth_row = m_y_min + np.argmin(gray[m_y_min:m_y_max, int(0.35*w):int(0.65*w)].mean(axis=1))
    print(f"Estimated mouth center row: y={mouth_row} (~{mouth_row/h:.2f}h)")

