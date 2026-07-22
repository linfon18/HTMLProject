"""Section X.C visual regression: poster 1440x900, edge 1920x1080 vs v1 finals;
mobile 390x844 layout. Structural diff + layout assertions."""
import sys, time, io
sys.path.insert(0, '/mnt/agents/output/gargantua_test')
from v2_common import launch, watch, report, V2
from playwright.sync_api import sync_playwright
from PIL import Image
import numpy as np

R = []
OUT = '/mnt/agents/output/gargantua_test/'

def grab(pw, url, w, h, name, timeout=480000):
    browser, ctx = launch(pw, viewport={'width': w, 'height': h})
    page = ctx.new_page()
    errs = []
    watch(page, errs)
    page.goto(url, wait_until='domcontentloaded')
    page.wait_for_function("document.title === 'SHOT_OK'", timeout=timeout)
    buf = page.screenshot(timeout=180000)
    with open(OUT + name, 'wb') as f:
        f.write(buf)
    browser.close()
    return np.asarray(Image.open(io.BytesIO(buf)).convert('RGB'), dtype=np.float32), errs

def blur_down(img, size=(60, 34)):
    im = Image.fromarray(img.astype(np.uint8)).resize(size, Image.LANCZOS)
    return np.asarray(im, dtype=np.float32)

with sync_playwright() as pw:
    # ---- poster 1440x900 (matches v1 final_poster_1440.png) ----
    img, errs = grab(pw, V2 + '/?shot&cam=poster&q=cinematic', 1440, 900, 'v2_poster_1440.png')
    R.append(report('C1 poster 1440x900 renders, zero errors', not errs, f'{errs[:3]}'))
    v1 = np.asarray(Image.open(OUT + 'final_poster_1440.png').convert('RGB'), dtype=np.float32)
    mad = float(np.abs(blur_down(img) - blur_down(v1)).mean())
    R.append(report('C1b poster matches v1 (structure)', mad < 8.0, f'mean|diff|={mad:.2f}'))

    # ---- edge 1920x1080 (matches v1 final_edge_1920.png) ----
    img, errs = grab(pw, V2 + '/?shot&cam=edge&q=cinematic', 1920, 1080, 'v2_edge_1920.png')
    R.append(report('C2 edge 1920x1080 renders, zero errors', not errs, f'{errs[:3]}'))
    v1 = np.asarray(Image.open(OUT + 'final_edge_1920.png').convert('RGB'), dtype=np.float32)
    mad = float(np.abs(blur_down(img) - blur_down(v1)).mean())
    R.append(report('C2b edge matches v1 (structure)', mad < 8.0, f'mean|diff|={mad:.2f}'))

    # ---- mobile 390x844 layout ----
    browser, ctx = launch(pw, viewport={'width': 390, 'height': 844},
                          user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15',
                          has_touch=True, is_mobile=True)
    page = ctx.new_page()
    errs = []
    watch(page, errs)
    page.goto(V2 + '/?q=standard&steps=60', wait_until='domcontentloaded')
    page.wait_for_function("document.body.classList.contains('ready')", timeout=300000)
    time.sleep(1)
    buf = page.screenshot(timeout=120000)
    with open(OUT + 'v2_mobile_390.png', 'wb') as f:
        f.write(buf)
    lay = page.evaluate("""() => {
      const r = el => { const b = el.getBoundingClientRect(); return {x: b.x, y: b.y, w: b.width, h: b.height}; };
      const overlap = (a, b) => !(a.x + a.w <= b.x || b.x + b.w <= a.x || a.y + a.h <= b.y || b.y + b.h <= a.y);
      const deck = r(document.getElementById('deck'));
      const tele = r(document.getElementById('telemetry'));
      const title = r(document.getElementById('title-block'));
      const clock = r(document.getElementById('clock-block'));
      const c = r(document.getElementById('view'));
      return { deck, tele, title, clock,
        deckInView: deck.x >= 0 && deck.y >= 0 && deck.x + deck.w <= 390 && deck.y + deck.h <= 844,
        teleDeckOverlap: overlap(tele, deck), titleClockOverlap: overlap(title, clock),
        titleDeckOverlap: overlap(title, deck) };
    }""")
    R.append(report('C3 mobile: deck fully in viewport, no HUD overlaps',
                    lay['deckInView'] and not lay['teleDeckOverlap'] and not lay['titleClockOverlap']
                    and not lay['titleDeckOverlap'], str({k: v for k, v in lay.items() if not isinstance(v, dict)})))
    # touch targets >= 40px on visible deck buttons
    small = page.evaluate("""() => {
      const bad = [];
      document.querySelectorAll('#deck .btn').forEach(b => {
        const r = b.getBoundingClientRect();
        if (r.width > 0 && (r.width < 40 || r.height < 40)) bad.push([b.id, Math.round(r.width), Math.round(r.height)]);
      });
      return bad;
    }""")
    R.append(report('C3b mobile touch targets >= 40px', not small, str(small)))
    # params panel opens and scrolls without covering deck badly
    page.tap('#btn-params'); time.sleep(0.5)
    pan = page.evaluate("""() => {
      const p = document.getElementById('params');
      const b = p.getBoundingClientRect();
      return { hidden: p.classList.contains('hidden'), x: b.x, y: b.y, w: b.width, h: b.height,
               scrollable: p.scrollHeight > p.clientHeight || document.getElementById('p-rows').scrollHeight > 0,
               inView: b.x >= 0 && b.x + b.width <= 390 };
    }""")
    R.append(report('C3c params panel opens in-viewport on mobile',
                    not pan['hidden'] and pan['inView'], str(pan)))
    buf = page.screenshot(timeout=120000)
    with open(OUT + 'v2_mobile_params.png', 'wb') as f:
        f.write(buf)
    R.append(report('C3d mobile: no console/page errors', not errs, f'{errs[:3]}'))
    browser.close()

print('---')
n_ok = sum(1 for x in R if x)
print(f'VISUAL: {n_ok}/{len(R)} passed')
sys.exit(0 if n_ok == len(R) else 1)
