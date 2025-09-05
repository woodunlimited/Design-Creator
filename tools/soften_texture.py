from PIL import Image, ImageEnhance, ImageFilter
import argparse
ap = argparse.ArgumentParser()
ap.add_argument('--inp', required=True)
ap.add_argument('--out', required=True)
ap.add_argument('--contrast', type=float, default=0.8)   # <1.0 = softer
ap.add_argument('--brightness', type=float, default=1.05) # >1.0 = lighter
ap.add_argument('--blur', type=float, default=0.7)        # small Gaussian
args = ap.parse_args()

img = Image.open(args.inp).convert('RGB')
if args.blur>0: img = img.filter(ImageFilter.GaussianBlur(args.blur))
img = ImageEnhance.Contrast(img).enhance(args.contrast)
img = ImageEnhance.Brightness(img).enhance(args.brightness)
img.save(args.out, quality=95)
print('Wrote', args.out)