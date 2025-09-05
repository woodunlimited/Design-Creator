import json, yaml
from pydantic import BaseModel
from typing import List, Optional, Literal

Units = Literal['norm','px']

class WarpCfg(BaseModel):
    type: Literal['none','cylindrical'] = 'cylindrical'
    strength: float = 0.18
    direction: Literal['vertical','horizontal'] = 'vertical'

class StainlessCfg(BaseModel):
    preset: Literal['stainless_brushed_vertical'] = 'stainless_brushed_vertical'
    grain: Literal['vertical','horizontal'] = 'vertical'
    texture_path: Optional[str] = None

class Area(BaseModel):
    id: str
    shape: Literal['rect'] = 'rect'
    units: Units = 'norm'
    rect: dict  # {x,y,w,h}
    fit: Literal['contain','cover'] = 'contain'
    padding_ratio: float = 0.05
    align: Literal['center'] = 'center'
    warp: WarpCfg = WarpCfg()
    stainless: StainlessCfg = StainlessCfg()

class BaseSpec(BaseModel):
    image: str
    variants: List[str] = []
    areas: List[Area]

def load_yaml(path:str):
    with open(path, 'r', encoding='utf-8-sig') as f:
        return yaml.safe_load(f)

def load_json(path:str):
    with open(path, 'r', encoding='utf-8-sig') as f:
        return json.load(f)

