import os, json
from PIL import Image, ImageDraw

base_dir = r'.\bases\tumblers\tumbler20'
spec_path = os.path.join(base_dir, 'print_areas.json')
with open(spec_path, 'r', encoding='utf-8-sig') as f:
    spec = json.load(f)

img_path = os.path.join(base_dir, spec['image'])
im = Image.open(img_path).convert('RGBA')
W, H = im.size

area = spec['areas'][0]
if area.get('units','norm') == 'norm':
    x = int(area['rect']['x'] * W); y = int(area['rect']['y'] * H)
    w = int(area['rect']['w'] * W); h = int(area['rect']['h'] * H)
else:
    x = int(area['rect']['x']); y = int(area['rect']['y'])
    w = int(area['rect']['w']); h = int(area['rect']['h'])

pad = area.get('padding_ratio', 0.0)
px = int(w*pad); py = int(h*pad)

draw = ImageDraw.Draw(im)
th = max(2, int(min(W,H)*0.003))
draw.rectangle([x, y, x+w, y+h], outline=(255,0,0,255), width=th)               # red outer
draw.rectangle([x+px, y+py, x+w-px, y+h-py], outline=(0,200,0,255), width=th)   # green inner

os.makedirs(r'.\proofs', exist_ok=True)
out_path = os.path.join(r'.\proofs', 'PROOF_RECT_DEBUG.png')
im.save(out_path)
print('Image:', W, 'x', H)
print('Rect px:', x, y, w, h)
print('Padded px:', x+px, y+py, (x+w-px), (y+h-py))
print('Wrote:', out_path)