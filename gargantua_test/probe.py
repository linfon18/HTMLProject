#!/usr/bin/env python3
import asyncio, sys
from playwright.async_api import async_playwright

async def main():
    url = sys.argv[1]
    wait_s = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(executable_path='/usr/bin/chromium', args=[
            '--enable-unsafe-swiftshader', '--use-gl=angle', '--use-angle=swiftshader',
            '--disable-dev-shm-usage', '--no-sandbox'])
        page = await browser.new_page(viewport={'width': 480, 'height': 270})
        page.on('console', lambda m: print('CON[' + m.type + ']', m.text[:400], flush=True))
        page.on('pageerror', lambda e: print('PAGEERROR', str(e)[:600], flush=True))
        await page.goto(url, wait_until='domcontentloaded')
        for i in range(wait_s):
            await asyncio.sleep(1)
            st = await page.evaluate("""() => ({
                title: document.title,
                fatal: document.getElementById('fatal').classList.contains('show'),
                fatalMsg: document.getElementById('fatal-msg').textContent.slice(0,300),
                ready: document.body.classList.contains('ready'),
            })""")
            print(i, st, flush=True)
            if st['title'] == 'SHOT_OK' or st['fatal']:
                break
        gl = await page.evaluate("""() => {
            const c = document.createElement('canvas');
            const g = c.getContext('webgl2');
            if (!g) return 'NO WEBGL2';
            return g.getParameter(g.RENDERER) + ' | ' + g.getParameter(g.VERSION);
        }""")
        print('WEBGL2:', gl, flush=True)
        await page.screenshot(path='/mnt/agents/output/gargantua_test/probe.png')
        await browser.close()

asyncio.run(main())
