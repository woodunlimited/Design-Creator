import os, sys, json, tempfile, shutil, pathlib, subprocess
import streamlit as st

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

DESIGNS_DIR = ROOT / "designs"
BASES_ROOT  = ROOT / "bases"
OUTPUTS_DIR = ROOT / "outputs"

def find_designs():
    exts = {".svg",".png",".jpg",".jpeg"}
    if not DESIGNS_DIR.exists(): return []
    return sorted([p for p in DESIGNS_DIR.iterdir() if p.is_file() and p.suffix.lower() in exts], key=lambda p: p.name.lower())

def find_bases():
    out = []
    for p in BASES_ROOT.rglob("print_areas.json"):
        out.append(p.parent)
    return sorted(out, key=lambda p: str(p.relative_to(BASES_ROOT)).lower())

def prep_design_subset(selected_names):
    all_names = [p.name for p in design_files]
    if set(selected_names) == set(all_names):
        return str(DESIGNS_DIR), None
    td = pathlib.Path(tempfile.mkdtemp(prefix="design_subset_"))
    for name in selected_names:
        src = DESIGNS_DIR / name
        if src.exists():
            shutil.copy2(src, td / name)
    return str(td), td

def _image_size_for_spec(spec_dir, j):
    from PIL import Image
    img_path = pathlib.Path(spec_dir) / j.get("image","")
    try:
        with Image.open(img_path) as im:
            return float(im.width), float(im.height)
    except Exception:
        return None, None

def prep_bases_with_overrides(selected_labels, fill_pct, warp_override, warp_strength, warp_dir, nudge_x_px, nudge_y_px):
    need_temp = (fill_pct != 0) or bool(warp_override) or (nudge_x_px != 0) or (nudge_y_px != 0)
    if not need_temp:
        return None, {}
    temp_root = pathlib.Path(tempfile.mkdtemp(prefix="bases_overrides_"))
    label_to_dir = {}
    for lbl in selected_labels:
        src_dir = BASES_ROOT / lbl
        dst_dir = temp_root / lbl
        dst_dir.mkdir(parents=True, exist_ok=True)
        for item in src_dir.iterdir():
            if item.is_file():
                shutil.copy2(item, dst_dir / item.name)
        spec_path = dst_dir / "print_areas.json"
        if not spec_path.exists():
            label_to_dir[lbl] = str(src_dir)
            continue
        try:
            with open(spec_path, "r", encoding="utf-8-sig") as f:
                j = json.load(f)
            if isinstance(j.get("areas"), list):
                pr = round(-float(fill_pct)/100.0, 4)  # +fill => overfill; -fill => underfill
                for a in j["areas"]:
                    a["padding_ratio"] = pr
                    a.setdefault("stainless", {})
                    a["stainless"].setdefault("grain", "vertical")
                    a["stainless"].setdefault("knockout_white", 245)
                    if warp_override:
                        a.setdefault("warp", {})
                        a["warp"]["type"] = "cylindrical"
                        a["warp"]["direction"] = warp_dir
                        a["warp"]["strength"] = float(warp_strength)
                if nudge_x_px != 0 or nudge_y_px != 0:
                    W,H = _image_size_for_spec(dst_dir, j)
                    if W and H:
                        for a in j["areas"]:
                            r = a.get("rect", {})
                            x = float(r.get("x", 0)); y = float(r.get("y", 0))
                            w = float(r.get("w", 0)); h = float(r.get("h", 0))
                            dx = float(nudge_x_px) / W
                            dy = float(nudge_y_px) / H
                            nx = max(0.0, min(x + dx, 1.0 - w))
                            ny = max(0.0, min(y + dy, 1.0 - h))
                            r["x"] = nx; r["y"] = ny
                            a["rect"] = r
            with open(spec_path, "w", encoding="utf-8") as f:
                json.dump(j, f, ensure_ascii=False, indent=2)
            label_to_dir[lbl] = str(dst_dir)
        except Exception:
            label_to_dir[lbl] = str(src_dir)
    return str(temp_root), label_to_dir

st.set_page_config(page_title="Mockup Batch UI", layout="centered")
st.title("Mockup Batch UI")

design_files = find_designs()
design_names = [p.name for p in design_files]
if not design_names:
    st.warning("No designs found in ./designs (svg/png/jpg).")

base_dirs = find_bases()
base_labels = [str(p.relative_to(BASES_ROOT)) for p in base_dirs]
if not base_dirs:
    st.error("No bases found under ./bases (missing print_areas.json).")

sel_designs = st.multiselect("Designs", design_names, default=design_names)
sel_bases   = st.multiselect("Items (bases)", base_labels, default=base_labels)

col1, col2 = st.columns(2)
with col1:
    size = st.number_input("Output size (px, square)", 1200, 4096, 2400, 100)
with col2:
    quality = st.slider("JPEG quality", 80, 100, 92)

st.caption("Leave blank to use stainless from each base JSON, or paste a full path to override all.")
stainless_override = st.text_input("Stainless override (optional full path)", "")

fill_pct = st.slider("Fill adjustment (%) — + expands, – shrinks", -30, 30, 0)

warp_override = st.checkbox("Override curvature (legacy cylindrical warp)", False)
if warp_override:
    colw1, colw2 = st.columns(2)
    with colw1:
        warp_strength = st.number_input("Warp strength", 0.00, 0.50, 0.05, 0.01, format="%.2f")
    with colw2:
        warp_dir = st.selectbox("Warp direction", ["vertical", "horizontal"], index=0)
else:
    warp_strength = 0.05
    warp_dir = "vertical"

coln1, coln2 = st.columns(2)
with coln1:
    nudge_x_px = st.number_input("Nudge X (px, +right / -left)", -1000, 1000, 0, 1)
with coln2:
    nudge_y_px = st.number_input("Nudge Y (px, +down / -up)", -1000, 1000, 0, 1)

st.subheader("Preview")
prev_size = st.number_input("Preview size (px)", 600, 2400, 1200, 100)
preview_btn = st.button("Preview selected designs on selected items")
run_btn = st.button("Render (full)")

def run_batch(base_map, designs_path, out_dir, size_px, jpg_q, margin_val):
    cmd_base = [
        sys.executable, "-m", "mockup", "batch",
        "--designs", designs_path,
        "--size", str(int(size_px)),
        "--quality", str(int(jpg_q)),
        "--margin", str(margin_val),
        "--out", out_dir
    ]
    if stainless_override.strip():
        cmd_base += ["--stainless", stainless_override.strip()]
    logs = []; errs = 0; total = len(sel_bases); progress = st.progress(0.0, text="")
    for i, lbl in enumerate(sel_bases, start=1):
        bdir = base_map.get(lbl, str(BASES_ROOT / lbl))
        cmd = cmd_base[:] + ["--bases", bdir]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        ok = (proc.returncode == 0)
        if not ok: errs += 1
        progress.progress(i/total, text=f"{lbl} — {'OK' if ok else 'ERROR'}")
        logs.append((lbl, proc.stdout))
    return errs, logs

if preview_btn:
    if not sel_designs: st.error("Pick at least one design."); st.stop()
    if not sel_bases:   st.error("Pick at least one base.");   st.stop()
    designs_path, tmp_designs = prep_design_subset(sel_designs)
    tmp_bases_root, override_map = prep_bases_with_overrides(sel_bases, fill_pct, warp_override, warp_strength, warp_dir, nudge_x_px, nudge_y_px)
    preview_out = pathlib.Path(tempfile.mkdtemp(prefix="preview_outputs_"))
    errs, logs = run_batch(override_map, designs_path, str(preview_out), prev_size, quality, 0.06)
    st.write("Preview images:")
    imgs = sorted([str(p) for p in preview_out.rglob("*.jpg")])[:60]
    if imgs: st.image(imgs, caption=[pathlib.Path(p).name for p in imgs], width=360)
    else:    st.info("No preview images found.")
    if errs == 0: st.success("Preview complete.")
    else:        st.warning(f"Preview finished with {errs} error(s). See logs below.")
    with st.expander("Logs"):
        for lbl, logtxt in logs: st.write(f"**{lbl}**"); st.code(logtxt)
    st.caption(f"Preview files were saved in: {preview_out}")

if run_btn:
    if not sel_designs: st.error("Pick at least one design."); st.stop()
    if not sel_bases:   st.error("Pick at least one base.");   st.stop()
    designs_path, tmp_designs = prep_design_subset(sel_designs)
    tmp_bases_root, override_map = prep_bases_with_overrides(sel_bases, fill_pct, warp_override, warp_strength, warp_dir, nudge_x_px, nudge_y_px)
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    errs, logs = run_batch(override_map, designs_path, str(OUTPUTS_DIR), size, quality, 0.06)
    if errs == 0: st.success(f"Done. Outputs in: {OUTPUTS_DIR}")
    else:         st.warning(f"Finished with {errs} error(s). See logs below.")
    with st.expander("Logs"):
        for lbl, logtxt in logs: st.write(f"**{lbl}**"); st.code(logtxt)