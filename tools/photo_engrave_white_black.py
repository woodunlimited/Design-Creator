"""Prep a photo for laser engraving on a WHITE-over-BLACK powder-coated 20oz tumbler (OneLaser Vertigo).

How the material works: the laser removes the white coat and exposes the black layer under it.
So the burn is the dark part of the picture. This is a POSITIVE image: dark photo pixels = laser on =
black shows. That is the same logic as a white tile (Norton method), not the "inverted" files used on
black tumblers. Powder coat is either removed or not, so grey comes only from dot density (dithering).
LightBurn does the dither (Stucki @ 317 LPI on layer C03). This script makes the greyscale it dithers.

Pipeline per version:
  crop -> greyscale -> Lanczos upscale to final px -> light denoise (stops JPEG noise turning into dots)
  -> CLAHE local contrast (faces) -> levels (sky clipped to pure white = no burn)
  -> midtone gamma (dot-gain comp: burned dots print bigger than the pixel) -> unsharp mask
  -> soft vignette that fades to white (no burn) -> centred on the white 2752x1278 full-wrap canvas.

Output .lbrn2 uses Louie's 20oz full-wrap Vertigo layout (same bitmap size, XForm and C03 layer values
as the IGES full-wrap builds: 278.3 x 110.456 mm, top of art faces LEFT in LightBurn).

Usage: python tools/photo_engrave_white_black.py <photo> <out_dir>
"""
import base64
import json
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

PHYS_W, PHYS_H = 278.3, 110.456          # 20oz full wrap, mm
BW, BH = 2752, 1278                      # bitmap px (same as golden full-wrap builds)
PX_MM = BW / PHYS_W                      # ~9.889 px/mm
XFORM = "-4.4203774e-09 0.10112645 -0.086428799 -3.7779229e-09 223.43387 147.4137"
DATE = "11.04.2026"
BLANK = "LTM7281 WHITE-BLACK"

# Vertigo / Polar Camel powder coat (Louie, 2026-10-21) + photo layer from the golden full wraps
VERTIGO = dict(speed=500, power=80, interval=0.0801262, angle=180, dither="stucki", dpi=317)

# crop boxes in source px (x0, y0, x1, y1) for the 927x1385 phone screenshot
VERSIONS = [
    dict(key="V1", name="WAIST UP", box=(205, 300, 770, 870), panel_h_mm=102, fade="oval", pop=False,
         note="Recommended. Faces ~19 mm tall, the most detail for a 20oz cup."),
    dict(key="V2", name="WAIST UP - PEOPLE POP", box=(205, 300, 770, 870), panel_h_mm=102, fade="oval", pop=True,
         note="Same crop as V1, background lightened and softened so the couple stands out."),
    dict(key="V3", name="KNEES UP WITH OCEAN", box=(120, 290, 860, 1110), panel_h_mm=102, fade="rect", pop=False,
         note="More ocean and palms. Faces ~14 mm tall."),
    dict(key="V4", name="FULL LENGTH", box=(60, 255, 905, 1350), panel_h_mm=104, fade="rect", pop=False,
         note="Whole photo. Faces only ~9 mm tall, so facial detail will be soft. Comparison only."),
]


def load_rgb(path):
    im = Image.open(path).convert("RGB")
    return np.array(im)


def people_mask(rgb_crop):
    """GrabCut foreground estimate of the two people (soft mask 0..1)."""
    h, w = rgb_crop.shape[:2]
    mask = np.zeros((h, w), np.uint8)
    rect = (int(w * 0.08), int(h * 0.04), int(w * 0.84), int(h * 0.95))
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(cv2.cvtColor(rgb_crop, cv2.COLOR_RGB2BGR), mask, rect, bgd, fgd, 6, cv2.GC_INIT_WITH_RECT)
    fg = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 1.0, 0.0).astype(np.float32)
    # keep the largest blob, close holes, feather
    n, lab, stats, _ = cv2.connectedComponentsWithStats((fg > 0).astype(np.uint8))
    if n > 1:
        big = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        fg = (lab == big).astype(np.float32)
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    return cv2.GaussianBlur(fg, (0, 0), 6)


def tone(gray):
    """gray float 0..255 -> engrave-ready grey 0..255."""
    g = gray.astype(np.uint8)
    g = cv2.bilateralFilter(g, 7, 18, 7)                         # kill JPEG blocks, keep edges
    clahe = cv2.createCLAHE(clipLimit=2.4, tileGridSize=(8, 8))
    g = clahe.apply(g).astype(np.float32)
    lo, hi = 4.0, 243.0                                          # sky / bright ocean -> pure white
    g = np.clip((g - lo) / (hi - lo), 0, 1)
    g = g ** 0.97                                                # lift mids: dot-gain compensation
    g = g * 255.0
    blur = cv2.GaussianBlur(g, (0, 0), 2.2)
    g = np.clip(g + 0.9 * (g - blur), 0, 255)                    # unsharp mask
    g[g > 249] = 255                                             # no stray dots in the sky
    return g


def fade_mask(h, w, kind):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    if kind == "oval":
        nx, ny = (xx - w / 2) / (w * 0.52), (yy - h * 0.40) / (h * 0.68)
        r = np.sqrt(nx ** 2 + ny ** 2)
        m = np.clip((1.0 - r) / 0.22, 0, 1)
    else:
        e = 0.11
        mx = np.minimum(xx / (w * e), (w - 1 - xx) / (w * e))
        my = np.minimum(yy / (h * e * 0.7), (h - 1 - yy) / (h * e * 0.7))
        m = np.clip(np.minimum(mx, my), 0, 1)
    m = m * m * (3 - 2 * m)                                      # smoothstep
    return m


def build_panel(rgb, v):
    x0, y0, x1, y1 = v["box"]
    crop = rgb[y0:y1, x0:x1]
    ph = int(round(v["panel_h_mm"] * PX_MM))
    pw = int(round(crop.shape[1] * ph / crop.shape[0]))
    up = cv2.resize(crop, (pw, ph), interpolation=cv2.INTER_LANCZOS4)
    lab = cv2.cvtColor(up, cv2.COLOR_RGB2LAB)
    gray = lab[:, :, 0].astype(np.float32) * 1.0
    g = tone(gray)
    if v["pop"]:
        pm = people_mask(crop)
        pm = cv2.resize(pm, (pw, ph), interpolation=cv2.INTER_LINEAR)
        bg = cv2.GaussianBlur(g, (0, 0), 3.0)
        bg = 255 - (255 - bg) * 0.45                             # background at ~45 % ink
        g = g * pm + bg * (1 - pm)
    m = fade_mask(ph, pw, v["fade"])
    g = 255 - (255 - g) * m
    return np.clip(g, 0, 255).astype(np.uint8)


def place_on_wrap(panel):
    canvas = np.full((BH, BW), 255, np.uint8)
    ph, pw = panel.shape
    if pw > BW:
        raise ValueError("panel wider than wrap")
    x = (BW - pw) // 2
    y = (BH - ph) // 2
    canvas[y:y + ph, x:x + pw] = panel
    return canvas, (x, y, pw, ph)


def lbrn2(wrap_png_bytes, notes):
    s = VERTIGO
    b64 = base64.b64encode(wrap_png_bytes).decode()
    notes = notes.replace("&", "and").replace('"', "'").replace("<", "(").replace(">", ")")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<LightBurnProject AppVersion="1.7.08" FormatVersion="1" MaterialHeight="0" MirrorX="True" MirrorY="False" DeviceName="VERTIGO">
    <VariableText>
        <Start Value="0"/>
        <End Value="999"/>
        <Current Value="0"/>
        <Increment Value="1"/>
        <AutoAdvance Value="0"/>
    </VariableText>
    <UIPrefs>
        <Optimize_ByLayer Value="0"/>
        <Optimize_ByGroup Value="-1"/>
        <Optimize_ByPriority Value="-1"/>
        <Optimize_WhichDirection Value="0"/>
        <Optimize_InnerToOuter Value="1"/>
        <Optimize_ByDirection Value="0"/>
        <Optimize_ReduceTravel Value="1"/>
        <Optimize_HideBacklash Value="0"/>
        <Optimize_ReduceDirChanges Value="0"/>
        <Optimize_ChooseCorners Value="0"/>
        <Optimize_AllowReverse Value="1"/>
        <Optimize_RemoveOverlaps Value="0"/>
        <Optimize_OptimalEntryPoint Value="1"/>
        <Optimize_OverlapDist Value="0.025"/>
    </UIPrefs>
    <CutSetting_Img type="Image">
        <index Value="3"/>
        <name Value="C03"/>
        <maxPower Value="{s['power']}"/>
        <maxPower2 Value="{s['power']}"/>
        <speed Value="{s['speed']}"/>
        <priority Value="0"/>
        <interval Value="{s['interval']}"/>
        <angle Value="{s['angle']}"/>
        <bidir Value="1"/>
        <ditherMode Value="{s['dither']}"/>
        <dpi Value="{s['dpi']}"/>
    </CutSetting_Img>
    <Shape Type="Bitmap" CutIndex="3" W="{BW}" H="{BH}" Gamma="1" Contrast="0" Brightness="0" EnhanceAmount="0" EnhanceRadius="0" EnhanceDenoise="0" File="" SourceHash="0" Data="{b64}">
        <XForm>{XFORM}</XForm>
    </Shape>
    <Notes ShowOnLoad="0" Notes="{notes}"/>
</LightBurnProject>
""".replace("\n", "\r\n")


def dither_preview(gray_u8):
    """Simulate the 317 LPI binary burn (PIL Floyd-Steinberg; LightBurn's Stucki is a close cousin)."""
    h_rows = int(round(PHYS_H * VERTIGO["dpi"] / 25.4))
    w_cols = int(round(PHYS_W * VERTIGO["dpi"] / 25.4))
    im = Image.fromarray(gray_u8).resize((w_cols, h_rows), Image.LANCZOS)
    return np.array(im.convert("1"), dtype=np.uint8)  # 0 = burn, 1 = keep white


COAT = np.array([244, 244, 241], np.float32)    # white powder coat
INK = np.array([30, 30, 32], np.float32)        # exposed black layer


def colourise(binary):
    keep = binary.astype(np.float32)[..., None]
    return (COAT * keep + INK * (1 - keep)).astype(np.uint8)


def mockup(binary, out_path, title):
    """Front half of the cup on a simple shaded cylinder."""
    flat = colourise(binary)
    H, W = flat.shape[:2]
    half = W // 2
    front = flat[:, W // 2 - half // 2: W // 2 + half // 2]       # 139 mm (half the cup) centred on the art
    fh, fw = front.shape[:2]
    out_w = 900
    out_h = int(out_w * fh / fw * (np.pi / 2))
    xs = np.linspace(-1, 1, out_w)
    theta = np.arcsin(np.clip(xs, -1, 1))
    src_x = ((theta / (np.pi / 2)) * 0.5 + 0.5) * (fw - 1)
    src_y = np.linspace(0, fh - 1, out_h)
    mx, my = np.meshgrid(src_x.astype(np.float32), src_y.astype(np.float32))
    warped = cv2.remap(front, mx, my, cv2.INTER_AREA if False else cv2.INTER_LINEAR)
    shade = 0.80 + 0.22 * np.cos(theta) - 0.06 * np.clip(xs, 0, 1)
    spec = np.exp(-((xs + 0.38) / 0.06) ** 2) * 0.10
    warped = np.clip(warped.astype(np.float32) * shade[None, :, None] + 255 * spec[None, :, None], 0, 255).astype(np.uint8)
    pad, lid_h, base_h = 60, 70, 40
    canvas = Image.new("RGB", (out_w + pad * 2, out_h + lid_h + base_h + pad * 2 + 50), (226, 229, 233))
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle([pad - 6, pad, pad + out_w + 6, pad + lid_h], 14, fill=(52, 52, 56))  # lid
    canvas.paste(Image.fromarray(warped), (pad, pad + lid_h))
    d.rounded_rectangle([pad, pad + lid_h + out_h, pad + out_w, pad + lid_h + out_h + base_h], 10,
                        fill=tuple(int(c) for c in COAT * 0.86))
    try:
        f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
    except OSError:
        f = ImageFont.load_default()
    d.text((pad, canvas.height - 50), title, fill=(40, 40, 40), font=f)
    canvas.save(out_path)


def test_card(rgb, out_dir):
    """Scrap-cup calibration: 11-step grey ramp (0..100 % ink) + the V1 faces at 3 brightness levels."""
    canvas = np.full((BH, BW), 255, np.uint8)
    step_w, step_h = int(8 * PX_MM), int(14 * PX_MM)
    x0 = (BW - 11 * step_w) // 2
    y0 = int(8 * PX_MM)
    for i in range(11):
        canvas[y0:y0 + step_h, x0 + i * step_w:x0 + (i + 1) * step_w - 6] = int(round(255 * (1 - i / 10)))
    faces = rgb[330:560, 300:600]                       # both faces, source px
    fh = int(40 * PX_MM)
    fw = int(faces.shape[1] * fh / faces.shape[0])
    up = cv2.resize(faces, (fw, fh), interpolation=cv2.INTER_LANCZOS4)
    g = tone(cv2.cvtColor(up, cv2.COLOR_RGB2LAB)[:, :, 0].astype(np.float32))
    gap = int(6 * PX_MM)
    xs = (BW - 3 * fw - 2 * gap) // 2
    for k, gam in enumerate((1.25, 1.0, 0.8)):          # darker / as built / lighter
        t = 255 * (g / 255) ** gam
        canvas[y0 + step_h + gap:y0 + step_h + gap + fh, xs + k * (fw + gap):xs + k * (fw + gap) + fw] = t.astype(np.uint8)
    d = os.path.join(out_dir, "V0 TEST CARD - run on a scrap white cup first")
    os.makedirs(d, exist_ok=True)
    png = cv2.imencode(".png", canvas, [cv2.IMWRITE_PNG_COMPRESSION, 9])[1].tobytes()
    notes = ("TEST CARD for white-over-black photo engraving. Top: 11 grey steps 0..100 % ink. Bottom: faces "
             "left = darker, middle = as built in V1-V4, right = lighter. Pick the face that looks best; if the "
             "light steps (10-30 %) merge into white or the 70-90 % steps merge into solid black, adjust power or "
             "the gamma before burning the gift.")
    base = f"TUMBLER 20oz FULL WRAP - PHOTO TEST CARD - {BLANK} - IGES - {DATE}"
    with open(os.path.join(d, base + ".lbrn2"), "w", newline="") as fh_:
        fh_.write(lbrn2(png, notes))
    Image.fromarray(colourise(dither_preview(canvas))).save(os.path.join(d, "TEST CARD - as engraved preview (flat wrap).png"))


def main(photo, out_dir):
    rgb = load_rgb(photo)
    os.makedirs(out_dir, exist_ok=True)
    report = []
    for v in VERSIONS:
        label = f"{v['key']} {v['name']}"
        d = os.path.join(out_dir, label)
        os.makedirs(d, exist_ok=True)
        panel = build_panel(rgb, v)
        wrap, (px, py, pw, ph) = place_on_wrap(panel)
        png = cv2.imencode(".png", wrap, [cv2.IMWRITE_PNG_COMPRESSION, 9])[1].tobytes()
        notes = (f"IGES 2026 neighbor photo gift - {label}. 20oz FULL WRAP on {BLANK} (white coat over black). "
                 f"POSITIVE image: dark = burn = black shows. Do NOT invert. Layer C03 Image, Stucki 317 LPI, "
                 f"angle 180, speed {VERTIGO['speed']}, power {VERTIGO['power']} (Polar Camel). Photo panel "
                 f"{pw / PX_MM:.1f} x {ph / PX_MM:.1f} mm centred on the wrap (front of the cup = centre of the "
                 f"wrap, seam at the ends). Run the test card on a scrap white cup first. {v['note']}")
        base = f"TUMBLER 20oz FULL WRAP - PHOTO {label} - {BLANK} - IGES - {DATE}"
        with open(os.path.join(d, base + ".lbrn2"), "w", newline="") as fh:
            fh.write(lbrn2(png, notes))
        with open(os.path.join(d, f"{label} - engrave greyscale (import onto C03 if needed).png"), "wb") as fh:
            fh.write(png)
        binary = dither_preview(wrap)
        Image.fromarray(colourise(binary)).save(os.path.join(d, f"{label} - as engraved preview (flat wrap).png"))
        mockup(binary, os.path.join(d, f"{label} - mockup on white 20oz.png"), f"{label}  -  white coat, black shows through")
        report.append(dict(version=label, crop_src_px=v["box"], panel_mm=[round(pw / PX_MM, 1), round(ph / PX_MM, 1)],
                           upscale=round(ph / (v["box"][3] - v["box"][1]), 2), lbrn2=base + ".lbrn2", note=v["note"]))
        print("OK", label, report[-1]["panel_mm"], "upscale", report[-1]["upscale"])
    test_card(rgb, out_dir)
    report.append(dict(settings=VERTIGO, blank=BLANK, wrap_mm=[PHYS_W, PHYS_H], bitmap_px=[BW, BH], xform=XFORM))
    with open(os.path.join(out_dir, "_build-report.json"), "w") as fh:
        json.dump(report, fh, indent=2)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
