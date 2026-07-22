"""Decisive bloom-toggle proof: at debug 3/6/9, swapping bloomStrength 0<->1.5 must
change NOTHING (bloom disabled); at debug 0 the same swap must change a LOT
(bloom enabled and using user values). Also verifies round-trip restoration."""
import sys, time, io
sys.path.insert(0, '/mnt/agents/output/gargantua_test')
from v2_common import launch, watch, wait_ready, wait_frames, set_slider, report, V2
from playwright.sync_api import sync_playwright
from PIL import Image
import numpy as np

R = []

def grab(page):
    buf = page.screenshot(timeout=120000)
    return np.asarray(Image.open(io.BytesIO(buf)).convert('L'), dtype=np.float32)

def mad(a, b):
    return float(np.abs(a - b).mean())

with sync_playwright() as pw:
    errs = []
    browser, ctx = launch(pw)
    page = ctx.new_page(); watch(page, errs)
    page.goto(V2 + '/?q=standard&steps=60&cam=poster&nocine', wait_until='domcontentloaded')
    wait_ready(page)

    def cycle_debug(dbg):
        set_slider(page, 'debug', dbg)
        set_slider(page, 'bloomStrength', 0)
        wait_frames(page, 2, timeout=90)
        off = grab(page)
        set_slider(page, 'bloomStrength', 1.5)
        wait_frames(page, 2, timeout=90)
        on = grab(page)
        return mad(off, on)

    d0 = cycle_debug(0)
    R.append(report('E2 debug=0: bloom strength swap has big effect (bloom ON)',
                    d0 > 1.0, f'mean|diff|={d0:.3f}'))
    d3 = cycle_debug(3)
    R.append(report('E2 debug=3: strength swap zero effect (bloom OFF)',
                    d3 < 0.05, f'mean|diff|={d3:.3f}'))
    d6 = cycle_debug(6)
    R.append(report('E2 debug=6: strength swap zero effect (bloom OFF)',
                    d6 < 0.05, f'mean|diff|={d6:.3f}'))
    d9 = cycle_debug(9)
    R.append(report('E2 debug=9: strength swap zero effect (bloom OFF)',
                    d9 < 0.05, f'mean|diff|={d9:.3f}'))

    # round-trip: back to 0 -> bloom restored with user's CURRENT values (1.5 now)
    set_slider(page, 'debug', 0)
    set_slider(page, 'bloomStrength', 1.5)
    wait_frames(page, 2, timeout=90)
    a15 = grab(page)
    set_slider(page, 'bloomStrength', 0.55)
    wait_frames(page, 2, timeout=90)
    a055 = grab(page)
    R.append(report('E2b back to debug=0: bloom ON again and follows user strength',
                    mad(a15, a055) > 0.5, f'mean|diff|={mad(a15, a055):.3f}'))
    R.append(report('E2c no errors', not errs, f'{errs[:3]}'))
    browser.close()

print('---')
n_ok = sum(1 for x in R if x)
print(f'BLOOM2: {n_ok}/{len(R)} passed')
sys.exit(0 if n_ok == len(R) else 1)
