import cv2, numpy as np, PIL.Image

def fit_contain(src_w, src_h, box_w, box_h, pad_ratio=0.0):
    pad_w = box_w * pad_ratio
    pad_h = box_h * pad_ratio
    box_w2 = max(1, box_w - 2*pad_w)
    box_h2 = max(1, box_h - 2*pad_h)
    scale = min(box_w2/src_w, box_h2/src_h)
    out_w, out_h = int(src_w*scale), int(src_h*scale)
    off_x = int((box_w - out_w)/2)
    off_y = int((box_h - out_h)/2)
    return out_w, out_h, off_x, off_y

def cylindrical_warp(pil_rgba, strength=0.18, vertical=True):
    img = np.array(pil_rgba)
    h, w = img.shape[:2]
    if vertical:
        x = np.linspace(-1,1,w, dtype=np.float32)
        bend = np.sqrt(1 - (x**2)*min(strength,0.4))
        map_x = np.tile(((x+1)/2*(w-1)), (h,1)).astype(np.float32)
        map_y = (np.linspace(0,h-1,h)[:,None] * bend).astype(np.float32)
    else:
        y = np.linspace(-1,1,h, dtype=np.float32)
        bend = np.sqrt(1 - (y**2)*min(strength,0.4))
        map_x = (np.linspace(0,w-1,w)[None,:] * bend[:,None]).astype(np.float32)
        map_y = np.tile(((y+1)/2*(h-1))[:,None], (1,w)).astype(np.float32)
    warped = cv2.remap(img, map_x, map_y, interpolation=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_TRANSPARENT)
    return PIL.Image.fromarray(warped, 'RGBA')
