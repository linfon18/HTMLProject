"""Section VI audio acceptance: sting->main hand-off, cine alignment, re-entry
realignment, OFF/ON discipline, blocked-state recovery, no unhandled rejections."""
import sys, time, json
sys.path.insert(0, '/mnt/agents/output/gargantua_test')
from v2_common import launch, watch, wait_ready, report, V2
from playwright.sync_api import sync_playwright

R = []

# Delay the very first RAF by 3s so the harness can click SOUND while the intro
# is still up (SwiftShader's blocked main thread otherwise races us to ready).
DELAY_FIRST_FRAME = """
(() => {
  const oraf = window.requestAnimationFrame.bind(window);
  let first = true;
  window.requestAnimationFrame = (cb) => {
    if (first) { first = false; return setTimeout(() => oraf(cb), 3000); }
    return oraf(cb);
  };
})();
"""

def audio_state(page):
    return page.evaluate("""() => {
      const auds = [...document.querySelectorAll('audio')];
      const intro = auds.find(a => a.src.includes('intro'));
      const main = auds.find(a => a.src.includes('main'));
      return {
        count: auds.length,
        introPaused: intro ? intro.paused : null,
        mainPaused: main ? main.paused : null,
        mainCt: main ? main.currentTime : null,
        mainVol: main ? main.volume : null,
        mainLoop: main ? main.loop : null,
        btn: document.getElementById('btn-sound').textContent,
        btnActive: document.getElementById('btn-sound').classList.contains('active'),
        btnAria: document.getElementById('btn-sound').getAttribute('aria-pressed'),
      };
    }""")

with sync_playwright() as pw:
    # ---------- F1: sound at intro -> sting -> main aligned to cineTime ----------
    errs = []
    browser, ctx = launch(pw)
    ctx.add_init_script(DELAY_FIRST_FRAME)
    page = ctx.new_page(); watch(page, errs)
    page.goto(V2 + '/?q=standard&steps=60', wait_until='domcontentloaded')  # cine on
    page.dispatch_event('#btn-sound', 'click')  # before first frame -> intro visible
    time.sleep(1.0)
    s1 = audio_state(page)
    R.append(report('F1 sting plays after sound ON at intro',
                    s1['introPaused'] is False and s1['mainPaused'] is True and s1['count'] == 2,
                    f"introPaused={s1['introPaused']} mainPaused={s1['mainPaused']}"))
    # wait for sting to end (7.03s) and main to take over
    t0 = time.time()
    handed = False
    while time.time() - t0 < 25:
        s = audio_state(page)
        if s['introPaused'] and not s['mainPaused']:
            handed = True
            break
        time.sleep(0.4)
    s2 = audio_state(page)
    R.append(report('F1b sting ended -> main loop playing', handed and s2['mainLoop'], f"mainCt={s2['mainCt']:.2f}"))
    # hand-off lands at cineTime ~ sting length here, so it cannot discriminate
    # old vs new by value — F2 (ctime=120) is the discriminator. Just check sane.
    R.append(report('F1c main starts at sane cine-aligned position',
                    handed and s2['mainCt'] is not None and 0 <= s2['mainCt'] < 30,
                    f"mainCt={s2['mainCt']:.2f}"))
    t0 = time.time()
    vol = 0
    while time.time() - t0 < 12:  # fade timer needs main-thread slots in slow env
        vol = audio_state(page)['mainVol'] or 0
        if vol > 0.75:
            break
        time.sleep(0.5)
    R.append(report('F1d volume ramps toward 0.85', vol > 0.75, f"vol={vol:.2f}"))
    ctx.close()

    # ---------- F2: sting hand-off with ctime=120 (discriminates old fixed 7.03) ----------
    errs = []
    ctx = browser.new_context(viewport={'width': 480, 'height': 270})
    ctx.add_init_script(DELAY_FIRST_FRAME)
    page = ctx.new_page(); watch(page, errs)
    page.goto(V2 + '/?q=standard&steps=60&ctime=120', wait_until='domcontentloaded')
    page.dispatch_event('#btn-sound', 'click')  # pre-ready: takes the sting branch
    t0 = time.time()
    handed = False
    while time.time() - t0 < 30:
        s = audio_state(page)
        if s['introPaused'] and not s['mainPaused']:
            handed = True
            break
        time.sleep(0.4)
    s = audio_state(page)
    R.append(report('F2 sting branch aligns main to cineTime~120 (not 7.03)',
                    handed and 118.0 <= s['mainCt'] <= 140.0, f"mainCt={s['mainCt']:.2f}"))
    ctx.close()

    # F3: exit cine (music drifts with wall clock), re-enter (must snap back)
    errs = []
    ctx = browser.new_context(viewport={'width': 480, 'height': 270})
    page = ctx.new_page(); watch(page, errs)
    page.goto(V2 + '/?q=standard&steps=60&ctime=120', wait_until='domcontentloaded')
    page.dispatch_event('#btn-sound', 'click')
    t0 = time.time()
    while time.time() - t0 < 20:
        s = audio_state(page)
        if s['introPaused'] and not s['mainPaused']:
            break
        time.sleep(0.4)
    page.dispatch_event('#btn-poster', 'click')   # exit cinematic -> no forced jump
    time.sleep(0.8)
    ct_exit = audio_state(page)['mainCt']
    time.sleep(3.0)             # music keeps drifting naturally
    ct_before = audio_state(page)['mainCt']
    R.append(report('F3 exiting cine does not force-jump music',
                    ct_before > ct_exit + 1.5, f'{ct_exit:.2f} -> {ct_before:.2f}'))
    page.dispatch_event('#btn-cine', 'click')     # re-enter -> realign to cineTime%176
    time.sleep(0.6)
    ct_after = audio_state(page)['mainCt']
    R.append(report('F3b re-entering cine realigns music to cineTime',
                    ct_after < ct_before - 2.0 and 117.0 <= ct_after <= 130.0,
                    f'{ct_before:.2f} -> {ct_after:.2f}'))

    # F4: OFF/ON cycles — single instances, no overlap, resume sensibly
    page.dispatch_event('#btn-sound', 'click'); time.sleep(0.5)   # OFF
    s_off = audio_state(page)
    R.append(report('F4 OFF pauses both, button state correct',
                    s_off['introPaused'] and s_off['mainPaused'] and not s_off['btnActive']
                    and s_off['btnAria'] == 'false' and s_off['btn'] == '🔇 SOUND: OFF', s_off['btn']))
    page.dispatch_event('#btn-sound', 'click'); time.sleep(0.8)   # ON again
    s_on = audio_state(page)
    R.append(report('F4b ON resumes main only, realigned to cine window',
                    s_on['introPaused'] and not s_on['mainPaused'] and s_on['count'] == 2
                    and 115.0 <= s_on['mainCt'] <= 135.0 and s_on['btnAria'] == 'true',
                    f"mainCt={s_on['mainCt']:.2f}"))
    for i in range(2):                           # rapid toggles stay consistent
        page.dispatch_event('#btn-sound', 'click'); time.sleep(0.4)
        page.dispatch_event('#btn-sound', 'click'); time.sleep(0.6)
    s_end = audio_state(page)
    R.append(report('F4c repeated OFF/ON: still one main playing, no dup instances',
                    s_end['count'] == 2 and not s_end['mainPaused'] and s_end['introPaused']))
    ctx.close()

    # ---------- F5: blocked audio -> ON -> BLOCKED -> OFF (MutationObserver log) ----------
    errs = []
    ctx = browser.new_context(viewport={'width': 480, 'height': 270})
    ctx.route('**/audio/*', lambda r: r.abort())
    page = ctx.new_page(); watch(page, errs, allow_resource=True)
    page.goto(V2 + '/?q=standard&steps=60', wait_until='domcontentloaded')
    page.evaluate("""() => {
      window.__log = [];
      const b = document.getElementById('btn-sound');
      new MutationObserver(() => window.__log.push(b.textContent))
        .observe(b, { childList: true, characterData: true, subtree: true });
    }""")
    page.dispatch_event('#btn-sound', 'click')
    time.sleep(6)
    log = page.evaluate("window.__log")
    s = audio_state(page)
    seq_ok = ('🔊 SOUND: ON' in log and '⚠ SOUND: BLOCKED' in log
              and log.index('⚠ SOUND: BLOCKED') > log.index('🔊 SOUND: ON')
              and log[-1] == '🔇 SOUND: OFF')
    R.append(report('F5 blocked play: ON -> ⚠ BLOCKED -> OFF, aria false, both paused',
                    seq_ok and s['btn'] == '🔇 SOUND: OFF' and s['btnAria'] == 'false'
                    and not s['btnActive'] and s['introPaused'] and s['mainPaused'],
                    f'log={log}'))
    ctx.close()

    R.append(report('F6 no pageerrors / unhandled rejections across audio tests', not errs, f'{errs[:3]}'))
    browser.close()

print('---')
n_ok = sum(1 for x in R if x)
print(f'AUDIO: {n_ok}/{len(R)} passed')
sys.exit(0 if n_ok == len(R) else 1)
