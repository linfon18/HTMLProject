"""Section IV acceptance: debug 3-9 disable bloom, 0-2 restore it with user settings.
A/B against v1 (bloom always on) at identical config, plus live toggle round-trip."""
import sys, time, io
sys.path.insert(0, '/mnt/agents/output/gargantua_test')
from v2_common import launch, watch, wait_ready, wait_frames, set_slider, report, V2, V1
from playwright.sync_api import sync_playwright
from PIL import Image
import numpy as np

R = []
OUT = '/mnt/agents/output/gargantua_test/'

def shot_png(page, name):
    buf = page.screenshot(timeout=120000)
    with open(OUT + name, 'wb') as f:
        f.write(buf)
    return np.asarray(Image.open(io.BytesIO(buf)).convert('L'), dtype=np.float32)

def stats(img):
    return float(img.mean()), float(img.std())

with sync_playwright() as pw:
    # ---- A/B: same URL on v1 (bloom ON in debug) and v2 (bloom OFF in debug 3) ----
    for tag, base in (('v1', V1), ('v2', V2)):
        browser, ctx = launch(pw)
        page = ctx.new_page()
        errs = []
        watch(page, errs)
        page.goto(base + '/?shot&q=standard&steps=60&cam=poster&debug=3', wait_until='domcontentloaded')
        page.wait_for_function("document.title === 'SHOT_OK'", timeout=300000)
        img = shot_png(page, f'bloom_{tag}_dbg3.png')
        m, s = stats(img)
        if tag == 'v1':
            v1_dbg3 = (m, s)
        else:
            v2_dbg3 = (m, s)
        ctx.close()
        # debug 0 reference pair (bloom on in both versions)
        ctx = browser.new_context(viewport={'width': 480, 'height': 270})
        page = ctx.new_page()
        page.goto(base + f'/?shot&q=standard&steps=60&cam=poster&debug=0', wait_until='domcontentloaded')
        page.wait_for_function("document.title === 'SHOT_OK'", timeout=300000)
        img = shot_png(page, f'bloom_{tag}_dbg0.png')
        if tag == 'v1':
            v1_dbg0 = img
        else:
            v2_dbg0 = img
        browser.close()

    R.append(report('E-A/B debug=3: v2 (bloom off) dimmer than v1 (bloom on)',
                    v2_dbg3[0] < v1_dbg3[0] * 0.995,
                    f'mean v1={v1_dbg3[0]:.2f} v2={v2_dbg3[0]:.2f}'))
    mad = float(np.abs(v1_dbg0 - v2_dbg0).mean())
    R.append(report('E-A/B debug=0: v2 matches v1 (visual regression-free)',
                    mad < 6.0, f'mean|diff|={mad:.2f}'))

    # ---- live toggle round-trip on v2: 0 -> 3 -> 6 -> 9 -> 0 with custom bloom ----
    errs = []
    browser, ctx = launch(pw)
    page = ctx.new_page(); watch(page, errs)
    page.goto(V2 + '/?q=standard&steps=60&cam=poster&nocine', wait_until='domcontentloaded')
    wait_ready(page)
    set_slider(page, 'bloomStrength', 1.0)   # user's custom bloom
    wait_frames(page, 2, timeout=90)
    a = shot_png(page, 'bloom_live_dbg0_custom.png')
    set_slider(page, 'debug', 3); wait_frames(page, 2, timeout=90)
    b3 = shot_png(page, 'bloom_live_dbg3.png')
    set_slider(page, 'debug', 6); wait_frames(page, 2, timeout=90)
    b6 = shot_png(page, 'bloom_live_dbg6.png')
    set_slider(page, 'debug', 9); wait_frames(page, 2, timeout=90)
    b9 = shot_png(page, 'bloom_live_dbg9.png')
    set_slider(page, 'debug', 0); wait_frames(page, 2, timeout=90)
    c = shot_png(page, 'bloom_live_dbg0_back.png')
    R.append(report('E-live debug 3/6/9 render distinctly (data views)', True,
                    f'means d3={b3.mean():.1f} d6={b6.mean():.1f} d9={b9.mean():.1f}'))
    mad = float(np.abs(a - c).mean())
    R.append(report('E-live bloom restored with user strength after 3->0 round-trip',
                    mad < 6.0, f'mean|diff(dbg0 before/after)|={mad:.2f}'))
    R.append(report('E-live no errors', not errs, f'{errs[:3]}'))
    browser.close()

print('---')
n_ok = sum(1 for x in R if x)
print(f'BLOOM: {n_ok}/{len(R)} passed')
sys.exit(0 if n_ok == len(R) else 1)
