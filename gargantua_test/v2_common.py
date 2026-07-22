"""Shared helpers for GARGANTUA v2 acceptance tests."""
import json, time, sys
from playwright.sync_api import sync_playwright

ARGS = ['--enable-unsafe-swiftshader', '--disable-dev-shm-usage', '--no-sandbox']

V2 = 'http://127.0.0.1:8791'
V1 = 'http://127.0.0.1:8792'

# RAF probe: counts outstanding animation frames to detect leaks/duplicates.
RAF_PROBE = """
(() => {
  const s = { requested: 0, canceled: 0, completed: 0 };
  window.__rafStats = s;
  const oraf = window.requestAnimationFrame.bind(window);
  const ocaf = window.cancelAnimationFrame.bind(window);
  window.requestAnimationFrame = (cb) => {
    s.requested++;
    return oraf((t) => { s.completed++; cb(t); });
  };
  window.cancelAnimationFrame = (id) => { s.canceled++; ocaf(id); };
})();
"""

def launch(pw, **ctxkw):
    browser = pw.chromium.launch(args=ARGS)
    ctxkw.setdefault('viewport', {'width': 480, 'height': 270})
    context = browser.new_context(**ctxkw)
    context.add_init_script(RAF_PROBE)
    return browser, context

def watch(page, errs, allow_resource=False):
    def on_console(m):
        if m.type != 'error':
            return
        if allow_resource and 'Failed to load resource' in m.text:
            return
        errs.append('console: ' + m.text)
    page.on('console', on_console)
    page.on('pageerror', lambda e: errs.append('pageerror: ' + str(e)))

def wait_ready(page, timeout=240000):
    page.wait_for_function("document.body.classList.contains('ready')", timeout=timeout)

def raf_pending(page):
    s = page.evaluate("window.__rafStats")
    return s['requested'] - s['canceled'] - s['completed']

def frames_done(page):
    return page.evaluate("window.__rafStats")['completed']

def wait_frames(page, n, timeout=120):
    """Wait until n more RAF callbacks completed."""
    start = frames_done(page)
    t0 = time.time()
    while time.time() - t0 < timeout:
        if frames_done(page) >= start + n:
            return True
        time.sleep(0.5)
    return False

def set_slider(page, key, value):
    """Drive a params-panel range input like a user drag (value + input event)."""
    page.evaluate("""([key, value]) => {
      const el = document.getElementById('p-in-' + key);
      el.value = String(value);
      el.dispatchEvent(new Event('input', { bubbles: true }));
    }""", [key, value])

def slider_state(page):
    """Return {key: (inputValue, valText)} for all 21 params."""
    return page.evaluate("""() => {
      const out = {};
      document.querySelectorAll('#p-rows input').forEach(el => {
        const key = el.id.replace('p-in-', '');
        out[key] = [el.value, document.getElementById('p-val-' + key).textContent];
      });
      return out;
    }""")

def get_storage(page):
    return page.evaluate("localStorage.getItem('gargantua.params.v1')")

def report(name, ok, detail=''):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ''))
    return ok
