import asyncio
from playwright.async_api import async_playwright
async def m():
    async with async_playwright() as pw:
        b = await pw.chromium.launch(executable_path='/usr/bin/chromium', args=['--enable-unsafe-swiftshader','--no-sandbox','--disable-dev-shm-usage'])
        p = await (await b.new_context(viewport={'width':480,'height':270})).new_page()
        await p.goto('http://127.0.0.1:8791/?q=standard&steps=60', wait_until='domcontentloaded')
        await p.wait_for_function("document.body.classList.contains('ready')", timeout=240000)
        r = await p.evaluate("""(() => {
          const c = document.getElementById('view');
          c.dispatchEvent(new PointerEvent('pointerdown', {bubbles:true}));
          return {
            mode: document.getElementById('deck-mode').textContent,
            hint: document.getElementById('deck-hint').classList.contains('show')
          };
        })()""")
        print('immediately after takeover:', r, flush=True)
        # 6 秒后应自动隐藏
        for i in range(30):
            h = await p.evaluate("document.getElementById('deck-hint').classList.contains('show')")
            if not h:
                print(f'hint auto-hidden (poll {i})', flush=True); break
            await asyncio.sleep(1)
        else:
            print('hint NEVER hidden', flush=True)
        await b.close()
asyncio.run(m())
