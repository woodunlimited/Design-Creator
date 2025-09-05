import os, numpy as np
from PIL import Image, ImageFilter

def load_stainless_texture(path: str | None, size: tuple[int, int], grain: str = 'vertical') -> Image.Image:
    w, h = size
    if path and os.path.exists(path):
        tex = Image.open(path).convert('L')
        # enforce grain orientation if the asset is sideways
        if grain == 'vertical':
            if tex.width > tex.height:
                tex = tex.transpose(Image.Transpose.ROTATE_90)
        else:
            if tex.height > tex.width:
                tex = tex.transpose(Image.Transpose.ROTATE_90)
        return tex.resize((w, h), Image.Resampling.LANCZOS).convert('RGBA')

    # procedural fallback
    if grain == 'vertical':
        x = np.linspace(0, 1, w, dtype=np.float32).reshape(1, w)
        base = 0.5 + 0.3*np.sin(6*np.pi*x) + 0.2*x
        base = np.tile(base, (h, 1))
    else:
        y = np.linspace(0, 1, h, dtype=np.float32).reshape(h, 1)
        base = 0.5 + 0.3*np.sin(6*np.pi*y) + 0.2*y
    noise = np.random.default_rng(7).normal(0, 0.03, (h, w)).astype(np.float32)
    arr = (np.clip(base + noise, 0, 1) * 255).astype(np.uint8)
    return Image.fromarray(arr, 'L').convert('RGBA')

def inner_bevel_from_mask(mask, edge=2):
    blur = mask.filter(ImageFilter.GaussianBlur(edge))
    sh = Image.new('RGBA', mask.size, (0,0,0,0))
    hl = Image.new('RGBA', mask.size, (255,255,255,0))
    a = np.array(blur, dtype=np.uint8)
    sh.putalpha(Image.fromarray((a*0.18).astype(np.uint8),'L'))
    hl.putalpha(Image.fromarray((a*0.10).astype(np.uint8),'L'))
    return Image.alpha_composite(sh, hl)