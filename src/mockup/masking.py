from PIL import Image
import numpy as np

def alpha_mask(img: Image.Image) -> Image.Image:
    return img.split()[-1]

def knockout_white_mask(img: Image.Image, thresh: int = 245) -> Image.Image:
    # Mask = pixels that are NOT near-white
    rgb = img.convert('RGB')
    arr = np.array(rgb, dtype=np.uint8)
    # distance from white
    dist = 255 - np.min(arr, axis=2)
    mask = (dist > (255 - thresh)).astype(np.uint8) * 255
    return Image.fromarray(mask, 'L')
