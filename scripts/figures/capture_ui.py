"""Capture LANTERN UI screenshots (headless chromium via Playwright), then compose the two Figure 1 panels (D, E).
Both panels are COMPOSITES OF REAL CROPS of the running app (element screenshots of the banner, metrics, table,
histogram and 3D viewer, stitched side by side); nothing is drawn or retyped. The app is forced to a LIGHT look
(streamlit light theme + injected CSS: DejaVu Sans, white background) so the panels match the matplotlib figures.
Optional tool: needs `playwright` (+ chromium) and a runnable app (streamlit). No LLM credentials are needed.

Usage (from anywhere):
  python scripts/figures/capture_ui.py [--repo REPO] --out SCRATCH_DIR [--port 8790] [--stage 1|2|both] [--publish]
    --out      where raw_*.png and ui_shortlist.png / ui_explorer.png are written (default: docs/figures/paper/screens;
               use a scratch dir: raw captures are large and must stay out of the repo)
    --publish  also copy the two final PNGs into docs/figures/paper/screens/
Panel D: 'Ask' answer for "what proteins should I try for capturing Ce3+" (banner, metrics, rule table, 3D viewer of the
Dy site of 8FNR, light viewer background). Panel E: Explorer coordination-number histogram with the CN>=9 bar selected,
its site table with a selected row, the viewer for that row (light) and a small inset of the same viewer on the dark
background (the 'Viewer background' radio switched to Dark). Emoji glyphs (tofu in headless chromium) are kept out of the
crops by cropping, never by editing data text. The app's layout is narrowed with CSS so that UI text stays >= ~5 pt when
the panel is printed 3.25-3.4 in wide."""
import argparse, pathlib, subprocess, sys, time, urllib.request
from PIL import Image, ImageDraw, ImageFont

REPO = pathlib.Path(__file__).resolve().parents[2]
OUT = REPO / "docs/figures/paper/screens"
URL = "http://localhost:8790"
BG = (255, 255, 255)
DSF = 3
Q = "what proteins should I try for capturing Ce3+"
ARGS = ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]
CSS = """*:not([data-testid='stIconMaterial']) { font-family: 'DejaVu Sans', sans-serif !important; }
body, .stApp, header { background: #ffffff !important }
[data-testid=stSidebar], [data-testid=stSidebarCollapsedControl], [data-testid=stHeader], [data-testid=stToolbar] { display:none !important }
.hero { display:none !important }
[data-testid=stMainBlockContainer] { padding:8px 60px 8px 8px !important; margin:0 auto !important }
[data-testid=stVegaLiteChart], .vega-embed, .vega-embed svg, .vega-embed canvas { overflow:visible !important }"""


def new_page(ctx):
    pg = ctx.new_page()
    pg.on("console", lambda m: print("console:", m.type, m.text[:200]) if m.type == "error" else None)
    pg.goto(URL); pg.wait_for_timeout(3000)
    pg.add_style_tag(content=CSS)
    pg.add_style_tag(content="/**/").evaluate("e => e.id = 'wcss'")
    return pg


def set_width(pg, w):
    pg.evaluate("w => document.getElementById('wcss').textContent = "
                "'[data-testid=stMainBlockContainer]{max-width:' + (w + 68) + 'px !important}'", w)
    pg.wait_for_timeout(2500)


def shot(pg, loc, name):
    loc.scroll_into_view_if_needed(); pg.mouse.move(2, 2); pg.wait_for_timeout(500)
    loc.screenshot(path=str(OUT / name)); print("wrote", name)


def viewer(pg, name, clicks=2):
    fr = pg.locator("iframe").first
    fr.scroll_into_view_if_needed(); pg.wait_for_timeout(2500)
    bb = fr.bounding_box()
    pg.mouse.move(bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2)
    for _ in range(clicks):
        pg.mouse.wheel(0, 120); pg.wait_for_timeout(150)
    pg.wait_for_timeout(2000); pg.mouse.move(2, 2); pg.wait_for_timeout(300)
    fr.screenshot(path=str(OUT / name)); print("wrote", name, bb)


def click(pg, x, y):
    """hover first, then press: vega-lite and the data grid ignore a bare synthetic click"""
    pg.mouse.move(x - 4, y); pg.wait_for_timeout(300); pg.mouse.move(x, y); pg.wait_for_timeout(400)
    pg.mouse.down(); pg.mouse.up()


def theme_radio(pg, which):
    pg.locator('[data-testid="stRadio"]').get_by_text(which, exact=True).first.click(); pg.wait_for_timeout(6000)


def stage1():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(args=ARGS)
        ctx = b.new_context(viewport={"width": 1000, "height": 1300}, device_scale_factor=DSF, color_scheme="light")
        pg = new_page(ctx); set_width(pg, 440)
        box = pg.get_by_test_id("stTextInputField").first
        box.wait_for(timeout=60000)
        box.fill(Q); box.press("Enter"); pg.wait_for_timeout(1500)
        pg.get_by_role("button", name="Ask", exact=True).click(); pg.wait_for_timeout(20000)
        shot(pg, pg.locator("[data-testid=stMain] [data-testid=stAlert]").first, "raw_ask_banner.png")
        set_width(pg, 700)
        shot(pg, pg.get_by_test_id("stMetric").first, "raw_ask_metric1.png")
        shot(pg, pg.get_by_test_id("stMetric").nth(1), "raw_ask_metric2.png")
        shot(pg, pg.get_by_test_id("stDataFrame").first, "raw_ask_table.png")
        set_width(pg, 440)
        theme_radio(pg, "Light")
        viewer(pg, "raw_ask_viewer.png")
        pg.close()
        pg = new_page(ctx); set_width(pg, 440)
        pg.get_by_text("Explorer", exact=True).first.wait_for(timeout=60000)
        pg.get_by_text("Explorer", exact=True).first.click(); pg.wait_for_timeout(9000)
        ch = pg.get_by_test_id("stVegaLiteChart").first
        ch.scroll_into_view_if_needed(); pg.wait_for_timeout(1000)
        cb = ch.bounding_box()
        shot(pg, ch, "raw_exp_hist_unselected.png")
        # CN=9 natural-Ln bar: located by fraction of the chart box (tuned on the 440 px layout; see raw_exp_hist.png)
        click(pg, cb["x"] + cb["width"] * BAR[0], cb["y"] + cb["height"] * BAR[1]); pg.wait_for_timeout(6000)
        shot(pg, ch, "raw_exp_hist.png")
        tb = pg.get_by_test_id("stDataFrame").first
        tb.scroll_into_view_if_needed(); pg.wait_for_timeout(1000)
        t = tb.bounding_box()
        click(pg, t["x"] + 16, t["y"] + 36 + 35 * 4 + 17); pg.wait_for_timeout(8000)   # row 5: 8FNR Dy 201 A
        shot(pg, pg.get_by_test_id("stDataFrame").first, "raw_exp_table.png")
        theme_radio(pg, "Light")
        viewer(pg, "raw_exp_viewer_light.png")
        theme_radio(pg, "Dark")
        viewer(pg, "raw_exp_viewer_dark.png")
        b.close()


BAR = (0.64, 0.5)


PW, PH = 2040, 1140            # 3.4 in x 1.9 in at 600 dpi
GAP = 12


def fit_w(im, w):
    return im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)


def cover(im, w, h, cy=0.5):
    """scale to cover w x h, crop the overflow (vertical centre cy)"""
    f = max(w / im.width, h / im.height)
    im = im.resize((round(im.width * f), round(im.height * f)), Image.LANCZOS)
    x0 = (im.width - w) // 2; y0 = round((im.height - h) * cy)
    return im.crop((x0, y0, x0 + w, y0 + h))


def canvas_of(png):
    """the 3D canvas of a viewer capture (drop the button / legend strip below it)"""
    v = Image.open(OUT / png).convert("RGB")
    return v.crop((14, 14, v.width - 14, int(v.height * 0.79) - 6))


def stage2():
    # ---- D: banner + rule table (left), light 3D viewer (right)
    ban = Image.open(OUT / "raw_ask_banner.png").convert("RGB")
    tab = Image.open(OUT / "raw_ask_table.png").convert("RGB")
    # real crops of two table columns stitched: Protein | Rules passed (Accession and the per-rule columns are cut)
    prot = tab.crop((155, 0, 992, tab.height)); rules = tab.crop((1312, 0, 1636, tab.height))
    st = Image.new("RGB", (prot.width + rules.width, tab.height), BG); st.paste(prot, (0, 0)); st.paste(rules, (prot.width, 0))
    LW = 1120
    ban, st = fit_w(ban, LW), fit_w(st, LW)
    used = ban.height + GAP + st.height
    print("D left stack", used, "of", PH)
    d = Image.new("RGB", (PW, PH), BG)
    d.paste(ban, (0, 0)); d.paste(st, (0, ban.height + GAP))
    d.paste(cover(canvas_of("raw_ask_viewer.png"), PW - LW - GAP, PH), (LW + GAP, 0))
    d.save(OUT / "ui_shortlist.png")
    # ---- E: histogram + site-table strip (left), light viewer with dark inset (right)
    hist = Image.open(OUT / "raw_exp_hist.png").convert("RGB")
    hist = hist.crop((0, 0, hist.width, 915))
    tb = Image.open(OUT / "raw_exp_table.png").convert("RGB")
    HDR, ROW = 108, 105
    rows = [tb.crop((0, 0, 1100, HDR))] + [tb.crop((0, HDR + ROW * k, 1100, HDR + ROW * (k + 1))) for k in (4,)]
    strip = Image.new("RGB", (1100, sum(r.height for r in rows)), BG); y = 0
    for r in rows: strip.paste(r, (0, y)); y += r.height
    f = 0.95
    hist = hist.resize((round(hist.width * f), round(hist.height * f)), Image.LANCZOS)
    strip = strip.resize((round(strip.width * f), round(strip.height * f)), Image.LANCZOS)
    LWE = max(hist.width, strip.width)
    print("E left stack", hist.height + GAP + strip.height, "of", PH, "width", LWE)
    e = Image.new("RGB", (PW, PH), BG)
    e.paste(hist, (0, 0)); e.paste(strip, (0, hist.height + GAP))
    vw = PW - LWE - GAP
    e.paste(cover(canvas_of("raw_exp_viewer_light.png"), vw, PH), (LWE + GAP, 0))
    # inset: the same site on the dark background, bottom-right corner, thin border, tiny label
    iw = ih = 300
    ins = cover(canvas_of("raw_exp_viewer_dark.png"), iw, ih)
    dr = ImageDraw.Draw(ins); dr.rectangle((0, 0, iw - 1, ih - 1), outline=(120, 128, 140), width=3)
    try: fnt = ImageFont.truetype("DejaVuSans.ttf", 34)
    except OSError: fnt = ImageFont.load_default()
    dr.text((14, 8), "dark", fill=(235, 240, 245), font=fnt)
    e.paste(ins, (PW - iw - 10, PH - ih - 10))
    e.save(OUT / "ui_explorer.png")
    print("wrote ui_shortlist.png, ui_explorer.png", d.size, e.size)


def start_app(repo, port):
    proc = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "app.py", "--server.port", str(port),
                             "--server.headless", "true", "--browser.gatherUsageStats", "false", "--theme.base", "light",
                             "--theme.backgroundColor", "#ffffff", "--theme.secondaryBackgroundColor", "#f0f4f6",
                             "--theme.textColor", "#1b2a35", "--theme.primaryColor", "#20A78B", "--theme.font", "DejaVu Sans"],
                            cwd=repo, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            urllib.request.urlopen(f"http://localhost:{port}", timeout=2); return proc
        except Exception:
            time.sleep(1)
    proc.terminate(); raise SystemExit("streamlit app did not come up; check `streamlit run app.py` in " + str(repo))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=str(REPO)); ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--port", type=int, default=8790); ap.add_argument("--publish", action="store_true")
    ap.add_argument("--stage", choices=["1", "2", "both"], default="both")
    a = ap.parse_args()
    OUT = pathlib.Path(a.out); OUT.mkdir(parents=True, exist_ok=True); URL = f"http://localhost:{a.port}"
    if a.stage in ("1", "both"):
        proc = start_app(pathlib.Path(a.repo), a.port)
        try: stage1()
        finally: proc.terminate()
    if a.stage in ("2", "both"): stage2()
    if a.publish:
        import shutil
        dst = REPO / "docs/figures/paper/screens"; dst.mkdir(parents=True, exist_ok=True)
        for n in ("ui_shortlist.png", "ui_explorer.png"): shutil.copy(OUT / n, dst / n)
