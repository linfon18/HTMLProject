"""Section II/VII acceptance: WebGL context loss -> halt + fatal; restore -> single
reload; RETRY; LOWER QUALITY; no uncaught errors."""
import sys, time
sys.path.insert(0, '/mnt/agents/output/gargantua_test')
from v2_common import launch, watch, wait_ready, raf_pending, report, V2, RAF_PROBE
from playwright.sync_api import sync_playwright

R = []

def lose(page):
    return page.evaluate("""() => {
      const c = document.getElementById('view');
      const gl = c.getContext('webgl2') || c.getContext('webgl');
      const ext = gl && gl.getExtension('WEBGL_lose_context');
      if (!ext) return false;
      window.__loseExt = ext;
      ext.loseContext();
      return true;
    }""")

with sync_playwright() as pw:
    errs = []
    browser, ctx = launch(pw)
    page = ctx.new_page(); watch(page, errs)
    page.goto(V2 + '/?q=standard&steps=60&nocine', wait_until='domcontentloaded')
    wait_ready(page)
    p0 = raf_pending(page)

    ok = lose(page)
    R.append(report('G0 WEBGL_lose_context available', ok))
    page.wait_for_selector('#fatal.show', timeout=30000)
    title = page.text_content('#fatal-title')
    msg = page.text_content('#fatal-msg')
    time.sleep(1.5)
    p1 = raf_pending(page)
    f1 = page.evaluate("window.__rafStats.completed")
    time.sleep(2)
    f2 = page.evaluate("window.__rafStats.completed")
    R.append(report('G1 lost: fatal shown, RAF stopped, no re-render',
                    title == 'WEBGL CONTEXT LOST' and p1 == 0 and f1 == f2,
                    f'title={title!r} pending={p1} frames {f1}->{f2}'))
    R.append(report('G1b message mentions RETRY and LOWER QUALITY',
                    'RETRY' in msg and 'LOWER QUALITY' in msg))
    R.append(report('G1c no uncaught errors so far', not errs, f'{errs[:3]}'))

    # restore -> exactly one reload -> healthy again
    page.evaluate("window.__preRestore = 1; window.__loseExt.restoreContext()")
    page.wait_for_function("window.__preRestore === undefined", timeout=30000)  # reloaded
    wait_ready(page, timeout=300000)
    p2 = raf_pending(page)
    fatal = page.evaluate("document.getElementById('fatal').classList.contains('show')")
    R.append(report('G2 restore: single reload, renders again, no fatal',
                    p2 == 1 and not fatal, f'pending={p2} fatal={fatal}'))

    # RETRY button
    lose(page)
    page.wait_for_selector('#fatal.show', timeout=30000)
    page.evaluate("window.__preRetry = 1")
    page.click('#fatal-retry')
    page.wait_for_function("window.__preRetry === undefined", timeout=30000)
    wait_ready(page, timeout=300000)
    R.append(report('G3 RETRY reloads to healthy state',
                    raf_pending(page) == 1 and not page.evaluate(
                        "document.getElementById('fatal').classList.contains('show')")))
    ctx.close()

    # LOWER QUALITY button: default cinematic -> ?q=high
    errs = []
    ctx = browser.new_context(viewport={'width': 480, 'height': 270})
    ctx.add_init_script(RAF_PROBE)
    page = ctx.new_page(); watch(page, errs)
    page.goto(V2 + '/?steps=60&nocine', wait_until='domcontentloaded')  # cinematic
    wait_ready(page)
    lose(page)
    page.wait_for_selector('#fatal.show', timeout=30000)
    page.click('#fatal-lower')
    page.wait_for_function("location.search.includes('q=high')", timeout=60000)
    R.append(report('G4 LOWER QUALITY navigates to q=high', 'q=high' in page.url, page.url))
    wait_ready(page, timeout=300000)
    R.append(report('G4b lowered page renders', raf_pending(page) == 1))
    R.append(report('G5 no errors across WebGL tests', not errs, f'{errs[:3]}'))
    ctx.close()
    browser.close()

print('---')
n_ok = sum(1 for x in R if x)
print(f'WEBGL: {n_ok}/{len(R)} passed')
sys.exit(0 if n_ok == len(R) else 1)
