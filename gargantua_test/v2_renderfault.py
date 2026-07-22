"""RENDER FAULT acceptance: force composer.render() to throw via GL prototype
poisoning -> RAF stops, single RENDER FAULT overlay, no per-frame respam,
no uncaught exceptions. Plus post-edit smoke of two shot URLs."""
import sys, time
sys.path.insert(0, '/mnt/agents/output/gargantua_test')
from v2_common import launch, watch, wait_ready, raf_pending, report, V2
from playwright.sync_api import sync_playwright

R = []

with sync_playwright() as pw:
    errs = []
    browser, ctx = launch(pw)
    page = ctx.new_page(); watch(page, errs)
    page.goto(V2 + '/?q=standard&steps=60&nocine', wait_until='domcontentloaded')
    wait_ready(page)
    time.sleep(0.5)
    page.evaluate("""() => {
      const gl = document.getElementById('view').getContext('webgl2');
      const proto = Object.getPrototypeOf(gl);
      proto.drawElements = function () { throw new Error('forced GL fault (test)'); };
    }""")
    page.wait_for_selector('#fatal.show', timeout=60000)
    title = page.text_content('#fatal-title')
    msg = page.text_content('#fatal-msg')
    time.sleep(2)
    p1 = raf_pending(page)
    f1 = page.evaluate("window.__rafStats.completed")
    msg1 = page.text_content('#fatal-msg')
    time.sleep(2)
    f2 = page.evaluate("window.__rafStats.completed")
    msg2 = page.text_content('#fatal-msg')
    R.append(report('RF1 render throw -> RENDER FAULT overlay, RAF stopped, no re-render',
                    title == 'RENDER FAULT' and p1 == 0 and f1 == f2,
                    f'title={title!r} pending={p1} frames {f1}->{f2}'))
    R.append(report('RF2 overlay mentions RETRY + LOWER QUALITY, not respammed',
                    'RETRY' in msg and 'LOWER QUALITY' in msg and msg1 == msg2))
    R.append(report('RF3 error contains cause, no uncaught pageerrors',
                    'forced GL fault' in msg and not errs, f'errs={errs[:3]}'))
    ctx.close()

    # post-edit smoke: two shot URLs still clean
    for name, path in (('smoke_poster', '/?shot&cam=poster&q=cinematic'),
                       ('smoke_dbg3', '/?shot&cam=poster&q=standard&debug=3')):
        errs = []
        ctx = browser.new_context(viewport={'width': 560, 'height': 315})
        page = ctx.new_page(); watch(page, errs)
        page.goto(V2 + path, wait_until='domcontentloaded')
        ok = True
        try:
            page.wait_for_function("document.title === 'SHOT_OK'", timeout=480000)
        except Exception as e:
            ok = False
            errs.append(str(e)[:150])
        R.append(report(f'RF4 smoke {name}: SHOT_OK, zero errors', ok and not errs, f'{errs[:2]}'))
        ctx.close()
    browser.close()

print('---')
n_ok = sum(1 for x in R if x)
print(f'RENDERFAULT: {n_ok}/{len(R)} passed')
sys.exit(0 if n_ok == len(R) else 1)
