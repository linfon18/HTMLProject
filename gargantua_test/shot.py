#!/usr/bin/env python3
"""Headless acceptance harness for GARGANTUA."""
import asyncio, sys, json
from playwright.async_api import async_playwright

BASE = 'http://127.0.0.1:8791'

GL_ARGS = [
    '--enable-unsafe-swiftshader',
    '--disable-dev-shm-usage',
    '--no-sandbox',
]

async def run(jobs):
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(executable_path='/usr/bin/chromium', args=GL_ARGS)
        results = {}
        for job in jobs:
            name = job['name']
            url = job['url']
            w, h = job.get('size', (1280, 720))
            timeout = job.get('timeout', 420000)
            page = await browser.new_page(viewport={'width': w, 'height': h})
            errors, failures = [], []
            page.on('pageerror', lambda e, errors=errors: errors.append('PAGEERROR: ' + str(e)))
            page.on('console', lambda m, errors=errors: errors.append('CONSOLE.ERROR: ' + m.text) if m.type == 'error' else None)
            page.on('requestfailed', lambda r, failures=failures: failures.append(r.url + ' :: ' + (r.failure or '')))
            resp_status = {}
            page.on('response', lambda r, rs=resp_status: rs.setdefault(r.url, r.status))
            try:
                await page.goto(url, wait_until='domcontentloaded', timeout=60000)
                await page.wait_for_function("document.title==='SHOT_OK' || document.title==='BG_OK' || document.title.startsWith('ERR') || document.title==='LINKERR'", timeout=timeout)
                await page.screenshot(path=job['out'], timeout=240000)
                hud = await page.evaluate("""() => ({
                    dist: document.getElementById('t-dist').textContent,
                    inc: document.getElementById('t-inc').textContent,
                    steps: document.getElementById('t-steps').textContent,
                    prof: document.getElementById('t-prof').textContent,
                })""")
                results[name] = {'ok': True, 'hud': hud, 'errors': errors, 'failures': failures,
                                 'status': {k: v for k, v in resp_status.items() if v >= 400}}
            except Exception as e:
                results[name] = {'ok': False, 'err': str(e)[:500], 'errors': errors, 'failures': failures}
            await page.close()
            print(f"[{name}] ->", json.dumps(results[name], ensure_ascii=False)[:800], flush=True)
        await browser.close()
        return results

if __name__ == '__main__':
    jobs = json.load(open(sys.argv[1]))
    asyncio.run(run(jobs))
