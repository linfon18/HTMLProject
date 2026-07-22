"""Mobile layout: compare overlap geometry v2 vs v1 (regression), text-level
collision check, touch targets, params panel open/scroll, screenshots."""
import sys, time
sys.path.insert(0, '/mnt/agents/output/gargantua_test')
from v2_common import launch, watch, wait_ready, report, V2, V1
from playwright.sync_api import sync_playwright

R = []
GEO = """() => {
  const r = el => { const b = el.getBoundingClientRect(); return {x: b.x, y: b.y, w: b.width, h: b.height}; };
  const overlap = (a, b) => !(a.x + a.w <= b.x || b.x + b.w <= a.x || a.y + a.h <= b.y || b.y + b.h <= a.y);
  const deck = r(document.getElementById('deck'));
  const tele = r(document.getElementById('telemetry'));
  const title = r(document.getElementById('title-block'));
  const clock = r(document.getElementById('clock-block'));
  const h1 = r(document.querySelector('#title-block h1'));
  const cv = r(document.getElementById('clock-val'));
  return { deck, tele, title, clock, h1, cv,
    deckInView: deck.x >= 0 && deck.y >= 0 && deck.x + deck.w <= 390 && deck.y + deck.h <= 844,
    teleDeckOverlap: overlap(tele, deck), titleClockOverlap: overlap(title, clock),
    h1ClockTextOverlap: overlap(h1, cv), titleDeckOverlap: overlap(title, deck) };
}"""

with sync_playwright() as pw:
    results = {}
    for tag, base in (('v2', V2), ('v1', V1)):
        browser, ctx = launch(pw, viewport={'width': 390, 'height': 844},
                              user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15',
                              has_touch=True, is_mobile=True)
        page = ctx.new_page()
        errs = []
        watch(page, errs)
        page.goto(base + '/?q=standard&steps=60', wait_until='domcontentloaded')
        wait_ready(page, timeout=300000)
        time.sleep(0.5)
        results[tag] = page.evaluate(GEO)
        if tag == 'v2':
            buf = page.screenshot(timeout=120000)
            open('/mnt/agents/output/gargantua_test/v2_mobile_390.png', 'wb').write(buf)
            small = page.evaluate("""() => {
              const bad = [];
              document.querySelectorAll('#deck .btn').forEach(b => {
                const r = b.getBoundingClientRect();
                if (r.width > 0 && (r.width < 40 || r.height < 40)) bad.push([b.id, Math.round(r.width), Math.round(r.height)]);
              });
              return bad;
            }""")
            R.append(report('M1 touch targets >= 40px', not small, str(small)))
            page.dispatch_event('#btn-params', 'click')
            time.sleep(0.6)
            pan = page.evaluate("""() => {
              const p = document.getElementById('params');
              const b = p.getBoundingClientRect();
              const rows = document.getElementById('p-rows');
              return { hidden: p.classList.contains('hidden'),
                inView: b.x >= 0 && b.x + b.width <= 390 && b.y >= 0,
                maxH: p.style.maxHeight, scrollable: rows.scrollHeight > p.clientHeight,
                rowCount: rows.children.length };
            }""")
            R.append(report('M2 params panel opens in-viewport, scrollable, 21 rows',
                            not pan['hidden'] and pan['inView'] and pan['rowCount'] == 21, str(pan)))
            buf = page.screenshot(timeout=120000)
            open('/mnt/agents/output/gargantua_test/v2_mobile_params.png', 'wb').write(buf)
            R.append(report('M3 no console/page errors on mobile', not errs, f'{errs[:3]}'))
        browser.close()

    v1, v2 = results['v1'], results['v2']
    same = (v1['titleClockOverlap'] == v2['titleClockOverlap']
            and v1['deckInView'] == v2['deckInView']
            and abs(v1['title']['w'] - v2['title']['w']) < 1
            and abs(v1['deck']['w'] - v2['deck']['w']) < 1)
    R.append(report('M4 mobile geometry identical to v1 (regression-free)', same,
                    f"v1 titleClockOverlap={v1['titleClockOverlap']} v2={v2['titleClockOverlap']}"))
    R.append(report('M5 deck in viewport, no text-level HUD collisions',
                    v2['deckInView'] and not v2['teleDeckOverlap'] and not v2['titleDeckOverlap']
                    and not v2['h1ClockTextOverlap'],
                    f"h1ClockTextOverlap={v2['h1ClockTextOverlap']} teleDeck={v2['teleDeckOverlap']}"))

print('---')
n_ok = sum(1 for x in R if x)
print(f'MOBILE: {n_ok}/{len(R)} passed')
sys.exit(0 if n_ok == len(R) else 1)
