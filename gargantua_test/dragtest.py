import asyncio
from playwright.async_api import async_playwright
async def m():
    async with async_playwright() as pw:
        b = await pw.chromium.launch(executable_path='/usr/bin/chromium', args=['--enable-unsafe-swiftshader','--no-sandbox','--disable-dev-shm-usage'])
        p = await (await b.new_context(viewport={'width':320,'height':180})).new_page()
        await p.goto('http://127.0.0.1:8791/?q=standard&steps=60', wait_until='domcontentloaded')
        await p.wait_for_function("document.body.classList.contains('ready')", timeout=240000)
        print('mode0:', await p.text_content('#deck-mode'), flush=True)
        await p.mouse.move(160, 90); await p.mouse.down(); await p.mouse.move(200, 95, steps=2); await p.mouse.up()
        for i in range(40):
            mode = await p.text_content('#deck-mode')
            hint = await p.evaluate("document.getElementById('deck-hint').classList.contains('show')")
            if i % 5 == 0 or mode == 'NAVIGATION': print(i, mode, 'hint', hint, flush=True)
            if mode == 'NAVIGATION': break
            await asyncio.sleep(1)
        # 直接派发合成事件验证处理器注册
        r = await p.evaluate("""(() => {
          const c = document.getElementById('view');
          c.dispatchEvent(new PointerEvent('pointerdown', {bubbles:true}));
          return document.getElementById('deck-mode').textContent;
        })()""")
        print('synthetic:', r, flush=True)
        await b.close()
asyncio.run(m())
