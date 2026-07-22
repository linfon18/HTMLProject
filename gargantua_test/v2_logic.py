"""V2 logic acceptance: boot health, URL/localStorage/RESET priority, tier cycle,
AUTO-ORBIT vs cinematic, visibility/RAF discipline.
Interactions use synthetic-visibility pause + dispatched events so SwiftShader's
blocked main thread cannot stall the harness."""
import sys, time, json, io
sys.path.insert(0, '/mnt/agents/output/gargantua_test')
from v2_common import (launch, watch, wait_ready, raf_pending, frames_done,
                       wait_frames, set_slider, slider_state, get_storage, report, V2,
                       RAF_PROBE)
from playwright.sync_api import sync_playwright
from PIL import Image
import numpy as np

R = []
DEFAULTS = {  # expected range-input value strings at q=standard (step-snapped)
    'steps': '200', 'din': '2.75', 'dout': '40', 'dopMax': '1.85', 'opNear': '0.9',
    'opFar': '0.8', 'diskBright': '1', 'starBright': '1', 'skyFloor': '0.04',
    'rotSpeed': '1', 'bloomStrength': '0.55', 'bloomRadius': '0.35',
    'bloomThreshold': '0.55', 'vignette': '1', 'grain': '0.045', 'ca': '0.003',
    'fov': '44', 'maxDist': '150', 'orbitSpeed': '0.12', 'cineSeg': '11', 'debug': '0',
}

def pause_render(page):
    page.evaluate("""() => {
      Object.defineProperty(document, 'hidden', { get: () => true, configurable: true });
      document.dispatchEvent(new Event('visibilitychange'));
    }""")

def resume_render(page):
    page.evaluate("""() => {
      Object.defineProperty(document, 'hidden', { get: () => false, configurable: true });
      document.dispatchEvent(new Event('visibilitychange'));
    }""")

def click(page, sel):
    page.dispatch_event(sel, 'click')

with sync_playwright() as pw:
    browser, _ = launch(pw)

    # ---------- T0: normal boot health (B) ----------
    errs = []
    ctx = browser.new_context(viewport={'width': 480, 'height': 270})
    ctx.add_init_script("""
      const s = { requested: 0, canceled: 0, completed: 0 };
      window.__rafStats = s;
      const oraf = window.requestAnimationFrame.bind(window);
      const ocaf = window.cancelAnimationFrame.bind(window);
      window.requestAnimationFrame = (cb) => { s.requested++; return oraf((t) => { s.completed++; cb(t); }); };
      window.cancelAnimationFrame = (id) => { s.canceled++; ocaf(id); };
    """)
    ctx.set_default_timeout(180000)
    page = ctx.new_page(); watch(page, errs)
    page.goto(V2 + '/?q=standard&steps=60&nocine', wait_until='domcontentloaded')
    wait_ready(page)
    time.sleep(1)
    fatal = page.evaluate("document.getElementById('fatal').classList.contains('show')")
    R.append(report('T0 boot: ready, no fatal, no console/page errors',
                    not fatal and not errs, f'fatal={fatal} errs={errs[:3]}'))
    p = raf_pending(page)
    R.append(report('T0b steady-state single RAF', p == 1, f'pending={p}'))
    buf = page.screenshot(timeout=120000)
    black = float(np.asarray(Image.open(io.BytesIO(buf)).convert('L'), dtype=np.float32).mean())
    R.append(report('T0c not a black screen', black > 2, f'mean lum={black:.2f}'))
    ctx.close()

    # ---------- T1: URL override beats storage; override not persisted ----------
    errs = []
    ctx = browser.new_context(viewport={'width': 480, 'height': 270})
    ctx.add_init_script("""
      if (!sessionStorage.getItem('__seeded')) {
        sessionStorage.setItem('__seeded', '1');
        localStorage.setItem('gargantua.params.v1', JSON.stringify({steps: 500, debug: 2, diskBright: 1.2}));
      }
    """)
    ctx.set_default_timeout(180000)
    page = ctx.new_page(); watch(page, errs)
    page.goto(V2 + '/?q=standard&steps=320&debug=6&nocine', wait_until='domcontentloaded')
    wait_ready(page)
    hud_steps = page.text_content('#t-steps')
    st = slider_state(page)
    R.append(report('T1 URL 320/6 overrides stored 500/2',
                    hud_steps == '320' and st['steps'][0] == '320' and st['debug'][0] == '6',
                    f'hud={hud_steps} steps={st["steps"][0]} debug={st["debug"][0]}'))
    pause_render(page)  # main thread free -> instant interactions from here
    set_slider(page, 'diskBright', 1.5)
    time.sleep(0.3)
    stored = json.loads(get_storage(page))
    R.append(report('T1b override values not persisted (old stored kept), manual field persisted',
                    stored.get('steps') == 500 and stored.get('debug') == 2
                    and stored.get('diskBright') == 1.5,
                    f'steps={stored.get("steps")} debug={stored.get("debug")} diskBright={stored.get("diskBright")}'))

    # ---------- T2: RESET keeps URL overrides ----------
    page.keyboard.press('p')  # open panel
    time.sleep(0.3)
    click(page, '#btn-reset')
    time.sleep(0.5)
    st = slider_state(page)
    hud_steps = page.text_content('#t-steps')
    R.append(report('T2 RESET keeps URL 320/6',
                    st['steps'][0] == '320' and st['debug'][0] == '6' and hud_steps == '320',
                    f'steps={st["steps"][0]} debug={st["debug"][0]} hud={hud_steps}'))
    R.append(report('T2b RESET cleared storage', get_storage(page) is None))

    # ---------- T3: manual slider move takes over + persists ----------
    set_slider(page, 'steps', 300)
    time.sleep(0.3)
    stored = json.loads(get_storage(page) or '{}')
    R.append(report('T3 manual steps=300 now persisted, debug override not written',
                    stored.get('steps') == 300 and 'debug' not in stored,
                    f'steps={stored.get("steps")} debug_absent={"debug" not in stored}'))
    hud_steps = page.text_content('#t-steps')
    R.append(report('T3b HUD follows manual steps', hud_steps == '300', f'hud={hud_steps}'))
    page.goto(V2 + '/?q=standard&nocine', wait_until='domcontentloaded')
    wait_ready(page)
    st = slider_state(page)
    R.append(report('T3c reload: manual 300 kept, debug back to default 0',
                    st['steps'][0] == '300' and st['debug'][0] == '0',
                    f'steps={st["steps"][0]} debug={st["debug"][0]}'))
    R.append(report('T3z no errors in T1-T3', not errs, f'{errs[:3]}'))

    # ---------- T4: RESET to full defaults (no URL params) ----------
    pause_render(page)
    page.keyboard.press('p'); time.sleep(0.3)
    click(page, '#btn-reset'); time.sleep(0.5)
    st = slider_state(page)
    bad = {k: v[0] for k, v in st.items() if k in DEFAULTS and v[0] != DEFAULTS[k]}
    R.append(report('T4 RESET restores all 21 defaults (standard: steps=200, debug=0)',
                    not bad, f'mismatches={bad}'))
    R.append(report('T4b HUD steps=200', page.text_content('#t-steps') == '200'))
    ctx.close()

    # ---------- T5: quality tier cycles steps + DPR ----------
    errs = []
    ctx = browser.new_context(viewport={'width': 480, 'height': 270}, device_scale_factor=2)
    ctx.set_default_timeout(180000)
    page = ctx.new_page(); watch(page, errs)
    page.goto(V2 + '/?steps=60&nocine', wait_until='domcontentloaded')
    wait_ready(page)
    pause_render(page)
    def cw(): return page.evaluate("document.getElementById('view').width")
    seq = [('CINEMATIC', page.text_content('#t-steps'), cw())]
    click(page, '#btn-quality'); time.sleep(0.4)
    seq.append(('STANDARD', page.text_content('#t-steps'), cw()))
    click(page, '#btn-quality'); time.sleep(0.4)
    seq.append(('HIGH', page.text_content('#t-steps'), cw()))
    exp = {'CINEMATIC': ('60', 960), 'STANDARD': ('200', 480), 'HIGH': ('320', 720)}
    ok = all(seq[i][1] == exp[seq[i][0]][0] and seq[i][2] == exp[seq[i][0]][1] for i in range(3))
    R.append(report('T5 tier cycle steps+DPR', ok, f'{seq}'))
    R.append(report('T5b no errors', not errs, f'{errs[:3]}'))
    ctx.close()

    # ---------- T6: AUTO-ORBIT inside cinematic (section V) ----------
    errs = []
    ctx = browser.new_context(viewport={'width': 480, 'height': 270})
    ctx.add_init_script(RAF_PROBE)
    ctx.set_default_timeout(180000)
    page = ctx.new_page(); watch(page, errs)
    page.goto(V2 + '/?q=standard&steps=60', wait_until='domcontentloaded')  # cine ON
    wait_ready(page)
    pause_render(page)
    def deck():
        return page.evaluate("""() => ({
          mode: document.getElementById('deck-mode').textContent,
          cine: document.getElementById('btn-cine').classList.contains('active'),
          cineAria: document.getElementById('btn-cine').getAttribute('aria-pressed'),
          orbit: document.getElementById('btn-orbit').classList.contains('active'),
          orbitAria: document.getElementById('btn-orbit').getAttribute('aria-pressed'),
        })""")
    d0 = deck()
    R.append(report('T6 boot in cinematic', d0['mode'] == 'CINEMATIC SEQUENCE' and d0['cine'] and not d0['orbit'], str(d0)))
    click(page, '#btn-orbit'); time.sleep(0.3)
    d1 = deck()
    R.append(report('T6 orbit click in cine -> breaks cine + orbiting',
                    d1['mode'] == 'NAVIGATION' and d1['orbit'] and d1['orbitAria'] == 'true'
                    and not d1['cine'] and d1['cineAria'] == 'false', str(d1)))
    click(page, '#btn-cine'); time.sleep(0.3)  # re-enter cine must force orbit off
    d2 = deck()
    R.append(report('T6 re-enter cine forces autoRotate off',
                    d2['mode'] == 'CINEMATIC SEQUENCE' and d2['cine'] and not d2['orbit'] and d2['orbitAria'] == 'false', str(d2)))
    click(page, '#btn-orbit'); time.sleep(0.3)  # works every time
    d3 = deck()
    R.append(report('T6 orbit click again breaks cine again', d3['orbit'] and not d3['cine'], str(d3)))

    # ---------- T7: visibility / RAF discipline (section VII) ----------
    resume_render(page); time.sleep(1.5)
    p0 = raf_pending(page)
    pause_render(page); time.sleep(0.5)
    p1 = raf_pending(page)
    resume_render(page); time.sleep(1.5)
    p2 = raf_pending(page)
    pause_render(page); time.sleep(0.3)
    resume_render(page); time.sleep(1.5)
    p3 = raf_pending(page)
    R.append(report('T7 hide stops RAF, show resumes exactly one',
                    p0 == 1 and p1 == 0 and p2 == 1 and p3 == 1,
                    f'pending {p0}->{p1}->{p2}->{p3}'))
    R.append(report('T7b no errors in T6-T7', not errs, f'{errs[:3]}'))
    ctx.close()

    # ---------- T8: shot mode never restarts RAF after backgrounding ----------
    errs = []
    ctx = browser.new_context(viewport={'width': 480, 'height': 270})
    ctx.add_init_script(RAF_PROBE)
    ctx.set_default_timeout(180000)
    page = ctx.new_page(); watch(page, errs)
    page.goto(V2 + '/?shot&q=standard&steps=60&cam=poster', wait_until='domcontentloaded')
    page.wait_for_function("document.title === 'SHOT_OK'", timeout=300000)
    p0 = raf_pending(page)
    pause_render(page); time.sleep(0.5)
    resume_render(page); time.sleep(2)
    p1 = raf_pending(page)
    title = page.title()
    R.append(report('T8 shot done: background/foreground never restarts RAF',
                    p0 == 0 and p1 == 0 and title == 'SHOT_OK' and not errs,
                    f'pending {p0}->{p1} title={title} errs={errs[:2]}'))
    ctx.close()

    browser.close()

print('---')
n_ok = sum(1 for x in R if x)
print(f'LOGIC: {n_ok}/{len(R)} passed')
sys.exit(0 if n_ok == len(R) else 1)
