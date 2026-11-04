# Neighbor photo tumbler (IGES 2026): white 20oz, black shows through

**Blank:** LTM7281 WHITE-BLACK (white powder coat over a black base).
**Machine:** OneLaser Vertigo, 20oz full-wrap layout (278.3 x 110.456 mm, top of the art faces LEFT in LightBurn).
**Layer C03 (Image):** Stucki dither, 317 LPI (0.0801262 mm), angle 180, speed 500, power 80, optimize by layer.

## Why this is set up differently from a normal photo tumbler
- On a black cup the laser exposes bright steel, so the art is **inverted**. On this cup the laser exposes **black**,
  so the burn is the dark part of the photo. **Do NOT tick "Negative Image".** This works like a white tile
  (Norton method).
- Powder coat is either removed or it isn't, so there is no true greyscale. Grey comes from **dot density**, which
  is why the layer uses Stucki dithering.
- The files already include: sky and highlights clipped to pure white (no stray dots), local contrast on the faces,
  a midtone lift because burned dots spread wider than one pixel, sharpening, and a soft fade to white at the edges.
  Leave LightBurn's Gamma, Contrast and Brightness at the defaults.

## Versions
| Folder | Crop | Panel | Faces | Notes |
|---|---|---|---|---|
| V1 WAIST UP | waist up | 101 x 102 mm | ~19 mm | **Recommended**: the most facial detail |
| V2 WAIST UP - PEOPLE POP | waist up | 101 x 102 mm | ~19 mm | Background softened and lightened so the couple stands out |
| V3 KNEES UP WITH OCEAN | knees up | 92 x 102 mm | ~14 mm | More ocean and palm trees |
| V4 FULL LENGTH | whole photo | 80 x 104 mm | ~9 mm | Comparison only: faces are too small |
| V0 TEST CARD | grey ramp and faces | - | - | Run this on a scrap white cup first |

The photo sits in the centre of the wrap (the front of the cup), with the seam at the back.

## Before the real cup
1. Open the .lbrn2 file and check it against a known-good 20oz Vertigo full wrap (orientation and layer settings).
   This file was rebuilt from your settings notes, not copied byte for byte from the golden file.
   If anything looks off, drag the "engrave greyscale" PNG onto C03 in your golden template instead.
2. Burn **V0 TEST CARD** on a scrap white cup. If the 10-30 % steps vanish, add power. If the 70-90 % steps fill in
   solid, lower power. Then pick the darker, middle or lighter face. The middle face matches V1-V4.
3. The source is a 927x1385 phone screenshot, so V1/V2 are upscaled 1.8x. **Get the original full-resolution
   photo from the neighbor** if you can, and re-run `python tools/photo_engrave_white_black.py <photo> <out>`
   with it (the crop boxes are in source pixels, so scale them up).
