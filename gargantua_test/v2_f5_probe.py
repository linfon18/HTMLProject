"""F5 standalone probe: trace button text + soundOn transitions with aborted audio."""
import sys, time
sys.path.insert(0, '/mnt/agents/output/gargantua_test')
from v2_common import launch, watch, V2
from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    errs = []
    browser, ctx = launch(pw)
    ctx.route('**/audio/*', lambda r: r.abort())
    page = ctx.new_page(); watch(page, errs, allow_resource=True)
    page.goto(V2 + '/?q=standard&steps=60', wait_until='domcontentloaded')
    print('goto done', flush=True)
    # instrument: record every button text change
    page.evaluate("""() => {
      window.__log = [];
      const b = document.getElementById('btn-sound');
      new MutationObserver(() => window.__log.push([performance.now()|0, b.textContent]))
        .observe(b, { childList: true, characterData: true, subtree: true });
    }""")
    page.dispatch_event('#btn-sound', 'click')
    t0 = time.time()
    while time.time() - t0 < 12:
        st = page.evaluate("""() => ({
          log: window.__log,
          auds: [...document.querySelectorAll('audio')].map(a => ({
            src: a.src.split('/').pop(), paused: a.paused, rs: a.readyState,
            err: a.error ? a.error.code : null })),
        })""")
        print(f"t={time.time()-t0:.1f}", st, flush=True)
        time.sleep(1.5)
    print('errs:', errs, flush=True)
    browser.close()
