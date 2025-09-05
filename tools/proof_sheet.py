import os, sys, argparse, io, json
from PIL import Image, ImageDraw
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(ROOT, 'src'))

from mockup.config import load_json, BaseSpec
from mockup.render import rasterize_design, render_design_on_base
from mockup.geometry import fit_contain
from mockup.masking import alpha_mask, knockout_white_mask

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base-dir', required=True)
    ap.add_argument('--designs', default=None)
    ap.add_argument('--design', default=None)
    ap.add_argument('--out', required=True)
    ap.add_argument('--stainless', default=None)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    spec = BaseSpec(**load_json(os.path.join(args.base_dir, 'print_areas.json')))
    base_files = [spec.image] + spec.variants
    base_files = [f for f in base_files if os.path.isfile(os.path.join(args.base_dir, f))]

    # pick design
    if args.design and os.path.isfile(args.design):
        dpath = args.design
    else:
        if not args.designs:
            raise SystemExit('Provide --design or --designs')
        cand = [f for f in os.listdir(args.designs) if os.path.splitext(f)[1].lower() in ('.svg','.png','.jpg','.jpeg')]
        if not cand:
            raise SystemExit('No designs found in --designs')
        dpath = os.path.join(args.designs, cand[0])

    print('Using design:', dpath)

    for bf in base_files:
        base_img = Image.open(os.path.join(args.base_dir, bf)).convert('RGBA')
        area = spec.areas[0]
        W, H = base_img.size
        if area.units == 'norm':
            x = int(area.rect['x'] * W); y = int(area.rect['y'] * H)
            w = int(area.rect['w'] * W); h = int(area.rect['h'] * H)
        else:
            x = int(area.rect['x']); y = int(area.rect['y'])
            w = int(area.rect['w']); h = int(area.rect['h'])

        # rasterize + plan fit
        target_w = max(64, int(W * area.rect['w'] * (1 - 2 * area.padding_ratio)))
        design_img = rasterize_design(dpath, target_w)
        fit_w, fit_h, off_x, off_y = fit_contain(design_img.width, design_img.height, w, h, area.padding_ratio)
        design_fit = design_img.resize((fit_w, fit_h), Image.Resampling.LANCZOS)

        # mask diagnostics
        mask = alpha_mask(design_fit)
        try:
            a_min, a_max = mask.getextrema()
        except Exception:
            a_min = a_max = 0
        thresh = getattr(getattr(area, 'stainless', object()), 'knockout_white', None)
        if (a_min == 255 and a_max == 255) or isinstance(thresh, (int, float)):
            mask = knockout_white_mask(design_fit, int(thresh) if thresh is not None else 245)
            a_min, a_max = mask.getextrema()
        print(f"[{bf}] fit={fit_w}x{fit_h} off=({off_x},{off_y}) mask_extrema=({a_min},{a_max})")

        # composite using the engine
        comp = render_design_on_base(base_img, area, design_img, args.stainless)

        # guides
        draw = ImageDraw.Draw(comp)
        # red: outer rect
        draw.rectangle([x, y, x+w, y+h], outline=(255,0,0,255), width=max(2, int(min(W,H)*0.003)))
        # green: padded inner
        pad = area.padding_ratio
        px = int(w*pad); py = int(h*pad)
        draw.rectangle([x+px, y+py, x+w-px, y+h-py], outline=(0,200,0,255), width=max(2, int(min(W,H)*0.003)))
        # yellow: planned fit box
        dx1, dy1 = x+off_x, y+off_y
        dx2, dy2 = dx1+fit_w, dy1+fit_h
        draw.rectangle([dx1, dy1, dx2, dy2], outline=(255,215,0,255), width=max(2, int(min(W,H)*0.003)))

        out_path = os.path.join(args.out, f'PROOF_{os.path.splitext(bf)[0]}.png')
        comp.save(out_path)
        print('Wrote', out_path)

        # debug dumps (first base only)
        dbg_dir = os.path.join(args.out, '_debug')
        os.makedirs(dbg_dir, exist_ok=True)
        design_fit.save(os.path.join(dbg_dir, 'design_fit.png'))
        mask.convert('L').save(os.path.join(dbg_dir, 'mask.png'))

if __name__ == '__main__':
    main()