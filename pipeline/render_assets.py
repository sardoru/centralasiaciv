"""Verify CentralAsiaCiv in headless Chromium and render favicon PNGs, custom 1200x630 OG image, and README screenshots."""

from __future__ import annotations

import base64
import functools
import http.server
import socketserver
import sys
import threading
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
DOCS_IMG = ROOT / "docs" / "images"
CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


def start_server():
    handler = functools.partial(QuietHandler, directory=str(WEB_DIR))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd, port


def find_browser_exe() -> str | None:
    if Path(CHROME_PATH).exists():
        return CHROME_PATH
    cache = Path.home() / "Library/Caches/ms-playwright"
    for pat in ("chromium-*/chrome-mac*/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
                "chromium_headless_shell-*/chrome-headless-shell-mac*/chrome-headless-shell"):
        matches = sorted(cache.glob(pat))
        if matches:
            return str(matches[-1])
    return None


def main() -> None:
    DOCS_IMG.mkdir(parents=True, exist_ok=True)
    httpd, port = start_server()
    base_url = f"http://127.0.0.1:{port}"
    exe = find_browser_exe()
    print(f"Serving {WEB_DIR} at {base_url} (browser: {exe or 'default'})", flush=True)

    errors: list[str] = []
    with sync_playwright() as p:
        launch_kw = {"headless": True}
        if exe:
            launch_kw["executable_path"] = exe
        browser = p.chromium.launch(**launch_kw)

        # 1. Render crisp PNG favicons from web/favicon.svg
        svg_text = (WEB_DIR / "favicon.svg").read_text(encoding="utf-8")
        for size, fname in ((64, "favicon.png"), (180, "apple-touch-icon.png")):
            pg = browser.new_page(viewport={"width": size, "height": size}, device_scale_factor=2)
            pg.set_content(f"""<!doctype html><html><body style="margin:0;background:transparent;display:grid;place-items:center;width:{size}px;height:{size}px;overflow:hidden;">
                <div style="width:{size}px;height:{size}px">{svg_text}</div></body></html>""")
            pg.screenshot(path=str(WEB_DIR / fname), omit_background=True)
            # Resize from 2x to exact target size with LANCZOS for crisp antialiasing
            im = Image.open(WEB_DIR / fname).resize((size, size), Image.Resampling.LANCZOS)
            im.save(WEB_DIR / fname)
            pg.close()
        print("Rendered favicon.png (64x64) and apple-touch-icon.png (180x180)", flush=True)

        # 2. Load live CentralAsiaCiv app & verify everything works cleanly
        page = browser.new_page(viewport={"width": 1440, "height": 860}, device_scale_factor=2)
        page.on("pageerror", lambda err: errors.append(f"PAGEERROR: {err}"))
        page.on("console", lambda msg: errors.append(f"CONSOLE {msg.type}: {msg.text}") if msg.type == "error" else None)

        page.goto(base_url + "/", wait_until="networkidle")
        page.wait_for_function("() => { const el = document.getElementById('loading'); return !el || el.hidden || getComputedStyle(el).display === 'none'; }", timeout=20000)
        page.wait_for_timeout(1600)

        # Verify topbar stats rendered
        yields_text = page.locator("#yields").inner_text()
        print("Topbar yields:", yields_text.replace("\n", " | "), flush=True)

        # Capture clean map-only render for our custom 1200x630 OG card using the live map canvas!
        og_map_dataurl = page.evaluate("""() => {
            const app = window.__app;
            const c = document.createElement('canvas');
            c.width = 2400; c.height = 1260;
            // Use the live map canvas cropped cleanly, or render directly via snapshot if available
            const src = document.getElementById('map');
            const ctx = c.getContext('2d');
            ctx.fillStyle = '#0d2238';
            ctx.fillRect(0, 0, c.width, c.height);
            // Cover-fit live high-DPI map canvas (ignoring topbar/dock)
            const sw = src.width, sh = src.height;
            const scale = Math.max(c.width / sw, c.height / sh);
            const dw = sw * scale, dh = sh * scale;
            ctx.drawImage(src, (c.width - dw) / 2, (c.height - dh) / 2 - 20, dw, dh);
            return c.toDataURL('image/png');
        }""")

        # Hero screenshot (full app UI)
        hero_png = DOCS_IMG / "hero.png"
        page.screenshot(path=str(hero_png))
        Image.open(hero_png).convert("RGB").resize((1440, 860), Image.Resampling.LANCZOS).save(DOCS_IMG / "hero.jpg", quality=88)
        hero_png.unlink()
        print("Saved docs/images/hero.jpg", flush=True)

        # Zoom into Uzbekistan + Samarkand + Fergana + Tashkent
        page.select_option("#country-picker", "focus:UZ")
        page.wait_for_timeout(1200)
        uz_png = DOCS_IMG / "uz.png"
        page.screenshot(path=str(uz_png))
        Image.open(uz_png).convert("RGB").resize((1440, 860), Image.Resampling.LANCZOS).save(DOCS_IMG / "uzbekistan.jpg", quality=88)
        uz_png.unlink()
        print("Saved docs/images/uzbekistan.jpg", flush=True)

        # Open City View for Tashkent (click OPEN CITY VIEW button to verify full citizens + districts view!)
        page.goto(base_url + "/#city=uz-tashkent", wait_until="networkidle")
        page.wait_for_timeout(1200)
        btn_cv = page.locator("button:has-text('Open City View'), button:has-text('OPEN CITY VIEW')").first
        if btn_cv.count() > 0:
            btn_cv.click()
            page.wait_for_timeout(1400)
        cv_png = DOCS_IMG / "cv.png"
        page.screenshot(path=str(cv_png))
        Image.open(cv_png).convert("RGB").resize((1440, 860), Image.Resampling.LANCZOS).save(DOCS_IMG / "city-view-tashkent.jpg", quality=88)
        cv_png.unlink()
        print("Saved docs/images/city-view-tashkent.jpg", flush=True)

        # Open Income / GDP per capita lens
        page.goto(base_url + "/#lens=grp_pc", wait_until="networkidle")
        page.wait_for_timeout(1400)
        ln_png = DOCS_IMG / "ln.png"
        page.screenshot(path=str(ln_png))
        Image.open(ln_png).convert("RGB").resize((1440, 860), Image.Resampling.LANCZOS).save(DOCS_IMG / "lens-income.jpg", quality=88)
        ln_png.unlink()
        print("Saved docs/images/lens-income.jpg", flush=True)

        # Smoke-test key Advisors (Energy, Culture, Commerce, Military, Explorer)
        for adv_id in ("energy", "culture", "commerce", "military", "explorer"):
            page.goto(base_url + f"/#advisor={adv_id}", wait_until="networkidle")
            page.wait_for_timeout(900)
        print("Smoke-tested Advisors (energy, culture, commerce, military, explorer)", flush=True)

        # 3. Render custom-designed 1200x630 Open Graph Social Card (web/og-image.png)
        # Re-open clean home view, hide UI overlays, frame the map generously for the OG backdrop!
        page.goto(base_url + "/", wait_until="networkidle")
        page.wait_for_timeout(1400)
        clean_map_b64 = page.evaluate("""() => {
            document.getElementById('topbar').style.display = 'none';
            document.getElementById('lens-area').style.display = 'none';
            document.getElementById('minimap-wrap').style.display = 'none';
            const src = document.getElementById('map');
            return src.toDataURL('image/png');
        }""")
        # Wait one frame and capture crisp full-bleed canvas
        page.wait_for_timeout(200)
        raw_map_path = ROOT / "data" / "og_raw_map.png"
        raw_map_path.parent.mkdir(parents=True, exist_ok=True)
        page.locator("#map").screenshot(path=str(raw_map_path))
        raw_b64 = base64.b64encode(raw_map_path.read_bytes()).decode("ascii")
        raw_map_path.unlink(missing_ok=True)
        page.close()

        og_page = browser.new_page(viewport={"width": 1200, "height": 630}, device_scale_factor=2)
        og_html = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    width: 1200px; height: 630px; overflow: hidden; position: relative;
    background: radial-gradient(circle at 52% 42%, #1a3048 0%, #0d1d2f 62%, #08121e 100%);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
    color: #f6ecd4;
  }}
  .map-bg {{
    position: absolute; left: 0; top: -18px;
    width: 1200px; height: 550px;
    object-fit: contain; object-position: center center;
    filter: saturate(1.12) contrast(1.06) brightness(0.98);
    -webkit-mask-image: linear-gradient(90deg, transparent 8%, black 22%, black 78%, transparent 92%);
    mask-image: linear-gradient(90deg, transparent 8%, black 22%, black 78%, transparent 92%);
  }}
  /* Editorial cartographic vignette — keeps all 5 Central Asian republics crisp above the title band */
  .vignette {{
    position: absolute; inset: 0;
    background:
      radial-gradient(ellipse 68% 58% at 50% 42%, rgba(10,22,36,0.0) 48%, rgba(8,16,26,0.62) 100%),
      linear-gradient(180deg, rgba(8,16,26,0.42) 0%, rgba(8,16,26,0.0) 16%, rgba(8,16,26,0.0) 70%, rgba(8,15,24,0.92) 86%, rgba(7,13,22,0.99) 100%);
  }}
  /* Ornate antique-gold double border frame (Timurid / 4X atlas style) */
  .frame-outer {{
    position: absolute; inset: 14px;
    border: 2px solid rgba(217, 178, 95, 0.72);
    border-radius: 6px;
    pointer-events: none;
  }}
  .frame-inner {{
    position: absolute; inset: 20px;
    border: 1px solid rgba(217, 178, 95, 0.28);
    border-radius: 3px;
    pointer-events: none;
  }}
  /* Corner gold accents */
  .corner {{
    position: absolute; width: 18px; height: 18px;
    border-color: #ecd08e; border-style: solid;
  }}
  .c-tl {{ top: 10px; left: 10px; border-width: 3px 0 0 3px; }}
  .c-tr {{ top: 10px; right: 10px; border-width: 3px 3px 0 0; }}
  .c-bl {{ bottom: 10px; left: 10px; border-width: 0 0 3px 3px; }}
  .c-br {{ bottom: 10px; right: 10px; border-width: 0 3px 3px 0; }}

  /* Top subtle badge */
  .top-pill {{
    position: absolute; top: 32px; left: 38px;
    display: inline-flex; align-items: center; gap: 10px;
    padding: 7px 16px; border-radius: 999px;
    background: rgba(12, 24, 38, 0.82);
    border: 1px solid rgba(217, 178, 95, 0.45);
    box-shadow: 0 6px 20px rgba(0,0,0,0.45);
    font-size: 13px; letter-spacing: 1.6px; text-transform: uppercase;
    color: #ecd08e; font-weight: 600;
  }}
  .top-dot {{
    width: 8px; height: 8px; border-radius: 50%;
    background: #3cd4c4; box-shadow: 0 0 10px #3cd4c4;
  }}

  .flags-bar {{
    position: absolute; top: 32px; right: 38px;
    display: flex; align-items: center; gap: 8px;
    padding: 7px 14px; border-radius: 999px;
    background: rgba(12, 24, 38, 0.82);
    border: 1px solid rgba(217, 178, 95, 0.38);
    font-size: 13px; letter-spacing: 0.6px; color: #dbe5f0; font-weight: 500;
  }}
  .flags-bar span {{ opacity: 0.95; }}
  .sep {{ color: rgba(217, 178, 95, 0.55); }}

  /* Bottom editorial title band */
  .footer {{
    position: absolute; left: 38px; right: 38px; bottom: 26px;
    display: flex; align-items: flex-end; justify-content: space-between; gap: 24px;
  }}
  .brand-lockup {{
    display: flex; align-items: center; gap: 18px;
  }}
  .emblem {{
    width: 72px; height: 72px; flex: 0 0 72px;
    filter: drop-shadow(0 8px 18px rgba(0,0,0,0.65));
  }}
  .title {{
    font-family: "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif;
    font-size: 46px; font-weight: 700; line-height: 1.02;
    letter-spacing: 2.5px;
    background: linear-gradient(180deg, #fff5d6 0%, #ecd08e 58%, #c79a44 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    filter: drop-shadow(0 3px 12px rgba(0,0,0,0.75));
  }}
  .subtitle {{
    margin-top: 6px;
    font-size: 18px; color: #d5e2ee; font-weight: 400; letter-spacing: 0.3px;
    text-shadow: 0 2px 8px rgba(0,0,0,0.85);
  }}
  .subtitle strong {{ color: #67e6d8; font-weight: 600; }}

  .stats {{
    display: flex; gap: 10px; align-items: center; padding-bottom: 4px;
  }}
  .stat {{
    background: rgba(14, 28, 44, 0.86);
    border: 1px solid rgba(217, 178, 95, 0.38);
    border-radius: 8px;
    padding: 9px 14px;
    text-align: center;
    min-width: 88px;
    box-shadow: 0 6px 18px rgba(0,0,0,0.45);
  }}
  .stat-v {{
    font-family: "Palatino Linotype", Palatino, Georgia, serif;
    font-size: 20px; font-weight: 700; color: #f6dd9c; line-height: 1.1;
  }}
  .stat-k {{
    margin-top: 2px; font-size: 10.5px; letter-spacing: 1px;
    text-transform: uppercase; color: #9eb4c8; font-weight: 600;
  }}
</style>
</head>
<body>
  <img class="map-bg" src="data:image/png;base64,{raw_b64}" alt="">
  <div class="vignette"></div>
  <div class="frame-outer"></div>
  <div class="frame-inner"></div>
  <div class="corner c-tl"></div>
  <div class="corner c-tr"></div>
  <div class="corner c-bl"></div>
  <div class="corner c-br"></div>

  <div class="top-pill"><span class="top-dot"></span>4X Interactive Atlas · 25 km Hex Grid</div>
  <div class="flags-bar">
    <span>UZ</span><span class="sep">·</span>
    <span>KZ</span><span class="sep">·</span>
    <span>KG</span><span class="sep">·</span>
    <span>TJ</span><span class="sep">·</span>
    <span>TM</span>
  </div>

  <div class="footer">
    <div class="brand-lockup">
      <div class="emblem">{svg_text}</div>
      <div>
        <div class="title">CENTRALASIACIV</div>
        <div class="subtitle"><strong>Uzbekistan, Kazakhstan &amp; Central Asia</strong> as a 4X Strategy-Game Map</div>
      </div>
    </div>
    <div class="stats">
      <div class="stat"><div class="stat-v">83.6M</div><div class="stat-k">People</div></div>
      <div class="stat"><div class="stat-v">$543B</div><div class="stat-k">GDP</div></div>
      <div class="stat"><div class="stat-v">76</div><div class="stat-k">Cities</div></div>
      <div class="stat"><div class="stat-v">38</div><div class="stat-k">Wonders</div></div>
    </div>
  </div>
</body>
</html>"""
        og_page.set_content(og_html)
        og_page.wait_for_timeout(300)
        og_tmp = WEB_DIR / "og-image-2x.png"
        og_page.screenshot(path=str(og_tmp))
        Image.open(og_tmp).convert("RGB").resize((1200, 630), Image.Resampling.LANCZOS).save(WEB_DIR / "og-image.png", optimize=True)
        og_tmp.unlink()
        og_page.close()
        print("Rendered custom 1200x630 web/og-image.png", flush=True)

        browser.close()
    httpd.shutdown()

    if errors:
        print("ERRORS FOUND:", file=sys.stderr)
        for e in errors:
            print(" ", e, file=sys.stderr)
        sys.exit(1)
    print("ALL CHECKS PASSED WITH ZERO CONSOLE/PAGE ERRORS!")


if __name__ == "__main__":
    main()
