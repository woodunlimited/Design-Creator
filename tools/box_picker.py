import os, json, argparse
from PIL import Image, ImageTk, ImageDraw
import tkinter as tk

ENC = 'utf-8'
def clamp(v,a,b): return a if v<a else b if v>b else v

def load_spec(base_dir):
    p = os.path.join(base_dir, 'print_areas.json')
    with open(p, 'r', encoding='utf-8-sig') as f:
        j = json.load(f)
    return p, j

def rect_px_from_norm(r, W, H):
    return [int(r['x']*W), int(r['y']*H), int((r['x']+r['w'])*W), int((r['y']+r['h'])*H)]

def norm_from_rect_px(x1,y1,x2,y2,W,H):
    x = x1/W; y = y1/H; w = (x2-x1)/W; h = (y2-y1)/H
    return {'x': round(x,4), 'y': round(y,4), 'w': round(w,4), 'h': round(h,4)}

class Picker:
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.spec_path, self.spec = load_spec(base_dir)
        img_path = os.path.join(base_dir, self.spec['image'])
        self.base = Image.open(img_path).convert('RGBA')
        self.W, self.H = self.base.size

        # initial rect from spec (first area)
        area = self.spec['areas'][0]
        r = area['rect']
        x1,y1,x2,y2 = rect_px_from_norm(r, self.W, self.H)

        # window scale (fit large images)
        maxw, maxh = 1200, 1200
        self.scale = min(maxw/self.W, maxh/self.H, 1.0)
        disp = self.base.resize((int(self.W*self.scale), int(self.H*self.scale)), Image.Resampling.LANCZOS)

        self.root = tk.Tk()
        self.root.title(f'Box Picker – {os.path.basename(self.base_dir)}  ({self.W}×{self.H})')
        self.canvas = tk.Canvas(self.root, width=disp.width, height=disp.height, bd=0, highlightthickness=0, cursor="cross")
        self.canvas.pack()
        self.tkimg = ImageTk.PhotoImage(disp)
        self.canvas.create_image(0,0,anchor='nw',image=self.tkimg)

        self.rect = [x1,y1,x2,y2]  # in image px coords
        self.drag = None
        self._draw()

        self.canvas.bind('<Button-1>', self.on_down)
        self.canvas.bind('<B1-Motion>', self.on_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_up)
        self.root.bind('<Escape>', lambda e: self.root.destroy())
        self.root.bind('<Return>', lambda e: self.save_and_quit())
        self.root.bind('s', lambda e: self.save_and_quit())

        # nudge keys
        self.root.bind('<Left>',  lambda e:self.nudge(-5,0))
        self.root.bind('<Right>', lambda e:self.nudge(5,0))
        self.root.bind('<Up>',    lambda e:self.nudge(0,-5))
        self.root.bind('<Down>',  lambda e:self.nudge(0,5))
        # size adjust
        self.root.bind('[', lambda e:self.resize(-5,0))
        self.root.bind(']', lambda e:self.resize(5,0))
        self.root.bind(';', lambda e:self.resize(0,-5))
        self.root.bind("'", lambda e:self.resize(0,5))

        info = tk.Label(self.root, text="Drag to draw. Arrows=move, [ ] = width, ; ' = height, Enter/S=save, Esc=cancel")
        info.pack(pady=4)
        self.status = tk.Label(self.root, text='', fg='#555')
        self.status.pack()

        self.update_status()
        self.root.mainloop()

    def img_to_canvas(self, x, y):
        return int(x*self.scale), int(y*self.scale)
    def canvas_to_img(self, x, y):
        return int(x/self.scale), int(y/self.scale)

    def _draw(self):
        self.canvas.delete('rect')
        x1,y1,x2,y2 = self.rect
        cx1,cy1 = self.img_to_canvas(x1,y1)
        cx2,cy2 = self.img_to_canvas(x2,y2)
        self.canvas.create_rectangle(cx1,cy1,cx2,cy2, outline='#ff0000', width=2, tags='rect')
        pad = 0  # inner guide optional
        if pad>0:
            self.canvas.create_rectangle(cx1+pad,cy1+pad,cx2-pad,cy2-pad, outline='#00c800', width=1, tags='rect')

    def on_down(self, e):
        self.drag = (e.x, e.y)
        x,y = self.canvas_to_img(e.x, e.y)
        self.rect = [x,y,x,y]
        self._draw()

    def on_drag(self, e):
        if not self.drag: return
        x0,y0 = self.canvas_to_img(*self.drag)
        x1,y1 = self.canvas_to_img(e.x, e.y)
        x1 = clamp(x1,0,self.W); y1 = clamp(y1,0,self.H)
        self.rect = [min(x0,x1), min(y0,y1), max(x0,x1), max(y0,y1)]
        self._draw()
        self.update_status()

    def on_up(self, e):
        self.drag = None
        self._draw()
        self.update_status()

    def nudge(self, dx, dy):
        x1,y1,x2,y2 = self.rect
        x1 = clamp(x1+dx,0,self.W); y1 = clamp(y1+dy,0,self.H)
        x2 = clamp(x2+dx,0,self.W); y2 = clamp(y2+dy,0,self.H)
        self.rect = [x1,y1,x2,y2]
        self._draw(); self.update_status()

    def resize(self, dw, dh):
        x1,y1,x2,y2 = self.rect
        x2 = clamp(x2+dw, x1+10, self.W)
        y2 = clamp(y2+dh, y1+10, self.H)
        self.rect = [x1,y1,x2,y2]
        self._draw(); self.update_status()

    def update_status(self):
        x1,y1,x2,y2 = self.rect
        r = norm_from_rect_px(x1,y1,x2,y2,self.W,self.H)
        self.status.config(text=f"Rect px: ({x1},{y1})–({x2},{y2})  |  norm: x={r['x']}, y={r['y']}, w={r['w']}, h={r['h']}")

    def save_and_quit(self):
        x1,y1,x2,y2 = self.rect
        if x2-x1 < 10 or y2-y1 < 10:
            self.root.destroy(); return
        r = norm_from_rect_px(x1,y1,x2,y2,self.W,self.H)
        self.spec['areas'][0]['rect'] = r
        with open(self.spec_path, 'w', encoding=ENC) as f:
            json.dump(self.spec, f, ensure_ascii=False, indent=2)
        # write a quick proof with guides
        out_dir = os.path.join(os.path.dirname(self.base_dir), '..', 'proofs')
        out_dir = os.path.abspath(out_dir)
        os.makedirs(out_dir, exist_ok=True)
        comp = self.base.copy()
        d = ImageDraw.Draw(comp)
        d.rectangle([x1,y1,x2,y2], outline=(255,0,0,255), width=max(2,int(min(self.W,self.H)*0.003)))
        comp.save(os.path.join(out_dir, 'DIAG_PICKED.png'))
        print('Saved rect to', self.spec_path)
        print('Wrote proof to', os.path.join(out_dir, 'DIAG_PICKED.png'))
        self.root.destroy()

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--base-dir', required=True, help='Folder containing print_areas.json and base PNGs')
    args = ap.parse_args()
    Picker(args.base_dir)