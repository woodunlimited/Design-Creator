import os, io, json, shutil, subprocess, tempfile
from PIL import Image, ImageDraw

BASE_DIR = r'.\bases\tumblers\tumbler20'
DESIGN   = r'.\designs\A Truly Great Nurse.svg'
OUT_DIR  = r'.\proofs'
os.makedirs(OUT_DIR, exist_ok=True)

# Load spec & base
spec_path = os.path.join(BASE_DIR, 'print_areas.json')
with open(spec_path, 'r', encoding='utf-8-sig') as f:
    spec = json.load(f)
base_path = os.path.join(BASE_DIR, spec['image'])
base = Image.open(base_path).convert('RGBA')
W, H = base.size
area = spec['areas'][0]
if area.get('units','norm') == 'norm':
    x = int(area['rect']['x'] * W); y = int(area['rect']['y'] * H)
    w = int(area['rect']['w'] * W); h = int(area['rect']['h'] * H)
else:
    x = int(area['rect']['x']); y = int(area['rect']['y'])
    w = int(area['rect']['w']); h = int(area['rect']['h'])

pad = float(area.get('padding_ratio', 0.01))
inner_w = max(1, int(w * (1 - 2*pad)))
inner_h = max(1, int(h * (1 - 2*pad)))

# Rasterize design (SVG via cairosvg or inkscape; fallback to placeholder if neither found)
def rasterize(design_path, target_w):
    ext = os.path.splitext(design_path)[1].lower()
    if ext == '.svg':
        try:
            import cairosvg
            png_bytes = cairosvg.svg2png(url=design_path, output_width=int(target_w))
            return Image.open(io.BytesIO(png_bytes)).convert('RGBA')
        except Exception:
            exe = shutil.which('inkscape')
            if exe:
                with tempfile.TemporaryDirectory() as td:
                    out_png = os.path.join(td, 'tmp.png')
                    cmd = [exe, design_path, '--export-type=png', f'--export-width={int(target_w)}', f'--export-filename={out_png}']
                    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return Image.open(out_png).convert('RGBA')
            # hard fallback: obvious magenta block so you can SEE it
            ph = Image.new('RGBA', (int(target_w), int(target_w*0.6)), (255, 0, 255, 200))
            return ph
    img = Image.open(design_path).convert('RGBA')
    if img.width != target_w:
        h = int(img.height * (target_w / img.width))
        img = img.resize((int(target_w), h), Image.Resampling.LANCZOS)
    return img

# Fit contain
def fit_contain(dw, dh, bw, bh, pad_ratio):
    iw = max(1, int(bw * (1 - 2*pad_ratio)))
    ih = max(1, int(bh * (1 - 2*pad_ratio)))
    scale = min(iw / dw, ih / dh)
    out_w = max(1, int(dw * scale)); out_h = max(1, int(dh * scale))
    off_x = (bw - out_w) // 2; off_y = (bh - out_h) // 2
    return out_w, out_h, off_x, off_y

target_w = max(64, int(W * area['rect']['w'] * (1 - 2*pad)))
design = rasterize(DESIGN, target_w)
fw, fh, ox, oy = fit_contain(design.width, design.height, w, h, pad)
design_fit = design.resize((fw, fh), Image.Resampling.LANCZOS)

# Composite with 85% opacity (no stainless/mask)
overlay = design_fit.copy()
a = overlay.split()[-1].point(lambda v: int(v*0.85))
overlay.putalpha(a)

comp = base.copy()
comp.alpha_composite(overlay, dest=(x + ox, y + oy))

# Draw guides (red outer, green padded, yellow placed)
draw = ImageDraw.Draw(comp)
th = max(2, int(min(W, H) * 0.003))
draw.rectangle([x, y, x+w, y+h], outline=(255,0,0,255), width=th)
px = int(w*pad); py = int(h*pad)
draw.rectangle([x+px, y+py, x+w-px, y+h-py], outline=(0,200,0,255), width=th)
draw.rectangle([x+ox, y+oy, x+ox+fw, y+oy+fh], outline=(255,215,0,255), width=th)

out_path = os.path.join(OUT_DIR, 'DIAG_20oz.png')
comp.save(out_path)
print('W,H=', W, H)
print('rect px=', x, y, w, h, 'pad=', pad)
print('fit=', fw, fh, 'off=', (ox, oy))
print('Wrote', out_path)