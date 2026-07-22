"""Section VIII acceptance: all 7 shot URLs must reach SHOT_OK with zero errors."""
import sys, time, json, threading
sys.path.insert(0, '/mnt/agents/output/gargantua_test')
from v2_common import launch, watch, V2
from playwright.sync_api import sync_playwright

URLS = [
    ('shot_poster_cine', '/?shot&cam=poster&q=cinematic'),
    ('shot_edge_std',    '/?shot&cam=edge&q=standard'),
    ('shot_polar_high',  '/?shot&cam=polar&q=high'),
    ('shot_close_cine',  '/?shot&cam=close&q=cinematic'),
    ('shot_poster_dbg3', '/?shot&cam=poster&q=standard&debug=3'),
    ('shot_poster_dbg6', '/?shot&cam=poster&q=standard&debug=6'),
    ('shot_poster_dbg9', '/?shot&cam=poster&q=standard&debug=9'),
]
OUT = '/mnt/agents/output/gargantua_test/'
results = {}
lock = threading.Lock()

def worker(jobs):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            args=['--enable-unsafe-swiftshader', '--disable-dev-shm-usage', '--no-sandbox'])
        for name, path in jobs:
            errs = []
            ctx = browser.new_context(viewport={'width': 560, 'height': 315})
            page = ctx.new_page()
            watch(page, errs)
            t0 = time.time()
            ok = False
            try:
                page.goto(V2 + path, wait_until='domcontentloaded')
                page.wait_for_function("document.title === 'SHOT_OK'", timeout=480000)
                ok = True
            except Exception as e:
                errs.append('wait: ' + str(e)[:200])
            try:
                page.screenshot(path=OUT + name + '.png', timeout=120000)
            except Exception as e:
                errs.append('screenshot: ' + str(e)[:200])
            with lock:
                results[name] = {'ok': ok, 'errors': errs, 'secs': round(time.time() - t0, 1)}
                print(json.dumps({name: results[name]}), flush=True)
            ctx.close()
        browser.close()

chunks = [URLS[0:3], URLS[3:5], URLS[5:7]]
threads = [threading.Thread(target=worker, args=(c,)) for c in chunks]
for t in threads: t.start()
for t in threads: t.join()

allok = all(r['ok'] and not r['errors'] for r in results.values())
print('ALL_SHOTS_OK' if allok else 'SHOT_FAILURES', json.dumps(results, indent=1))
