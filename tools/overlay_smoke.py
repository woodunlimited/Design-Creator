import os, sys, io, json, subprocess, shutil, tempfile
from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(ROOT, 'src'))

from mockup.geometry import fit_contain

def _inkscape_path():
    return shutil.which('inkscape')

def rasterize_design(path: str, target_w: int) -> Image.Image:
    ext = os.path.splitext(path)[1].lower()
    if ext == '.svg':
        try:
            import cairosvg
            png_bytes = cairosvg.svg2png(url=path, output_width=int(target_w))
            return Image.open(io.BytesIO(png_bytes)).convert('RGBA')
        except Exception:
            exe = _inkscape_path()
            if not exe:
                raise
            with tempfile.TemporaryDirectory() as td:
                out_png = os.path.join(td, 'tmp.png')
                cmd = [exe, path, '--export-type=png', f'--export-width={int(target_w)}', f'--export-filename={out_png}']
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return Image.open(out_png).convert('RGBA')
    img = Image.open(path).convert('RGBA')
    if img.width != target_w:
        h = int(img.height * (target_w / img.width))
        img = img.resize((int(target_w), h), Image.Resampling.LANCZOS)
    return img

base_dir = r'.\bases\tumblers\tumbler20'
design_path = r'.\designs\A Truly Great Nurse.svg'

with open(os.path.join(base_dir, 'print_areas.json'), 'r', encoding='utf-8-sig') as f:
    spec = json.load(f)

base = Image.open(os.path.join(base_dir, spec['image'])).convert('RGBA')
W,H = base.size
area = spec['areas'][0]
if area.get('units','norm') == 'norm':
    x = int(area['rect']['x']*W); y = int(area['rect']['y']*H)
    w = int(area['rect']['w']*W); h = int(area['rect']['h']*H)
else:
    x = int(area['rect']['x']); y = int(area['rect']['y'])
    w = int(area['rect']['w']); h = int(area['rect']['h'])

pad = area.get('padding_ratio', 0.01)
target_w = max(64, int(W * area['rect']['w'] * (1 - 2*pad)))
design = rasterize_design(design_path, target_w)
fit_w, fit_h, off_x, off_y = fit_contain(design.width, design.height, w, h, pad)
design_fit = design.resize((fit_w, fit_h), Image.Resampling.LANCZOS)

# paste with 80% opacity so it's clearly visible (no masking)
overlay = design_fit.copy()
alpha = overlay.split()[-1].point(lambda a: int(a*0.8))
overlay.putalpha(alpha)

comp = base.copy()
comp.alpha_composite(overlay, dest=(x+off_x, y+off_y))

os.makedirs(r'.\proofs', exist_ok=True)
out_path = os.path.join(r'.\proofs', 'PROOF_OVERLAY_SMOKE.png')
comp.save(out_path)
print('Wrote:', out_path)