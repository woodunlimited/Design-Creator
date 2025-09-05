import os, io, subprocess, shutil, tempfile, click
from PIL import Image

from .config import load_json, BaseSpec
from .textures import load_stainless_texture, inner_bevel_from_mask
from .masking import alpha_mask, knockout_white_mask
from .geometry import fit_contain, cylindrical_warp

try:
    import cairosvg
    HAS_CAIROSVG = True
except Exception:
    HAS_CAIROSVG = False

def _inkscape_path():
    return shutil.which('inkscape')

def _rasterize_svg_with_inkscape(svg_path: str, out_w: int) -> Image.Image:
    exe = _inkscape_path()
    if not exe:
        raise RuntimeError('SVG rasterization failed: CairoSVG unavailable and Inkscape not found.')
    with tempfile.TemporaryDirectory() as td:
        out_png = os.path.join(td, 'tmp.png')
        cmd = [exe, svg_path, '--export-type=png', f'--export-width={int(out_w)}', f'--export-filename={out_png}']
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return Image.open(out_png).convert('RGBA')

def rasterize_design(path: str, target_w: int) -> Image.Image:
    ext = os.path.splitext(path)[1].lower()
    if ext == '.svg':
        if HAS_CAIROSVG:
            png_bytes = cairosvg.svg2png(url=path, output_width=int(target_w))
            return Image.open(io.BytesIO(png_bytes)).convert('RGBA')
        else:
            return _rasterize_svg_with_inkscape(path, int(target_w))
    img = Image.open(path).convert('RGBA')
    if img.width != target_w:
        h = int(img.height * (target_w / img.width))
        img = img.resize((int(target_w), h), Image.Resampling.LANCZOS)
    return img

def render_design_on_base(base_img: Image.Image, area, design_img: Image.Image, stainless_tex_path: str | None = None) -> Image.Image:
    W, H = base_img.size
    if area.units == 'norm':
        x = int(area.rect['x'] * W); y = int(area.rect['y'] * H)
        w = int(area.rect['w'] * W); h = int(area.rect['h'] * H)
    else:
        x = int(area.rect['x']); y = int(area.rect['y'])
        w = int(area.rect['w']); h = int(area.rect['h'])

    out_w, out_h, off_x, off_y = fit_contain(design_img.width, design_img.height, w, h, area.padding_ratio)
    design_fit = design_img.resize((out_w, out_h), Image.Resampling.LANCZOS)

    if getattr(area, 'warp', None) and area.warp.type == 'cylindrical' and area.warp.strength > 0:
        vertical = (area.warp.direction == 'vertical')
        design_fit = cylindrical_warp(design_fit, area.warp.strength, vertical=vertical)

    mask = alpha_mask(design_fit)
    try:
        a_min, a_max = mask.getextrema()
    except Exception:
        a_min, a_max = (255, 255)
    thresh = getattr(getattr(area, 'stainless', object()), 'knockout_white', None)
    if (a_min == 255 and a_max == 255) or isinstance(thresh, (int, float)):
        mask = knockout_white_mask(design_fit, int(thresh) if thresh is not None else 245)

    tex_path = getattr(area.stainless, 'texture_path', None) or stainless_tex_path
    grain = getattr(area.stainless, 'grain', 'vertical')
    steel = load_stainless_texture(tex_path, (design_fit.width, design_fit.height), grain=grain)
    steel.putalpha(mask)

    bevel = inner_bevel_from_mask(mask, edge=max(1, int(min(out_w, out_h) * 0.012)))

    comp = base_img.copy()
    dest = (x + off_x, y + off_y)
    comp.alpha_composite(steel, dest=dest)
    comp.alpha_composite(bevel, dest=dest)
    return comp

@click.group()
def app():
    pass

@app.command()
@click.option('--bases', type=click.Path(exists=True), required=True)
@click.option('--designs', type=click.Path(exists=True), required=True)
@click.option('--out', type=click.Path(), required=True)
@click.option('--size', default=2400, show_default=True)
@click.option('--quality', default=92, show_default=True)
@click.option('--margin', default=0.06, show_default=True)
@click.option('--stainless', 'stainless_path', type=click.Path(exists=False), default=None)
def batch(bases, designs, out, size, quality, margin, stainless_path):
    os.makedirs(out, exist_ok=True)
    for root, dirs, files in os.walk(bases):
        if 'print_areas.json' not in files:
            continue
        base_dir = root
        spec_path = os.path.join(base_dir, 'print_areas.json')
        raw = load_json(spec_path)
        spec = BaseSpec(**raw)

        # per-base override: raw.get('output', {}).get('views')
        views_raw = raw.get('output', {}).get('views') if isinstance(raw, dict) else None
        if isinstance(views_raw, list) and views_raw:
            views = [(str(v.get('name','view')), float(v.get('margin', margin))) for v in views_raw]
        else:
            views = [('tight', margin), ('wide', 0.18)]

        base_id = os.path.relpath(base_dir, bases).replace(os.sep, '__')
        base_images = [spec.image] + spec.variants
        base_images = [p for p in base_images if os.path.isfile(os.path.join(base_dir, p))]
        for base_file in base_images:
            base_img = Image.open(os.path.join(base_dir, base_file)).convert('RGBA')
            for design_file in os.listdir(designs):
                name_lower = design_file.lower()
                if (os.path.splitext(design_file)[1].lower() not in ['.svg', '.png', '.jpg', '.jpeg']) or ('stainless' in name_lower) or ('texture' in name_lower):
                    continue
                design_slug = os.path.splitext(design_file)[0]
                area = spec.areas[0]
                target_w = max(64, int(base_img.width * area.rect['w'] * (1 - 2 * area.padding_ratio)))
                design_img = rasterize_design(os.path.join(designs, design_file), target_w)
                comp = render_design_on_base(base_img, area, design_img, stainless_tex_path=stainless_path)

                for suffix, m in views:
                    canvas = Image.new('RGBA', (size, size), (255, 255, 255, 255))
                    margin_px = int(size * m)
                    scale = min((size - 2 * margin_px) / comp.width, (size - 2 * margin_px) / comp.height)
                    new_size = (int(comp.width * scale), int(comp.height * scale))
                    comp_r = comp.resize(new_size, Image.Resampling.LANCZOS)
                    cx = (size - new_size[0]) // 2; cy = (size - new_size[1]) // 2
                    canvas.alpha_composite(comp_r, dest=(cx, cy))

                    dest_dir = os.path.join(out, design_slug, base_id)
                    os.makedirs(dest_dir, exist_ok=True)
                    out_name = f"{os.path.splitext(base_file)[0]}__{design_slug}__{suffix}.jpg"
                    canvas.convert('RGB').save(os.path.join(dest_dir, out_name), quality=quality, subsampling=1, optimize=True)
    click.echo('Done.')