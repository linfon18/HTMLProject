import asyncio
from playwright.async_api import async_playwright
async def m():
    async with async_playwright() as pw:
        b = await pw.chromium.launch(executable_path='/usr/bin/chromium', args=['--enable-unsafe-swiftshader','--no-sandbox','--disable-dev-shm-usage'])
        p = await (await b.new_context(viewport={'width':320,'height':180})).new_page()
        await p.goto('http://127.0.0.1:8791/?q=standard&steps=60', wait_until='domcontentloaded')
        await p.wait_for_function("document.body.classList.contains('ready')", timeout=240000)
        el = await p.evaluate("document.elementFromPoint(160,90).id || document.elementFromPoint(160,90).tagName")
        print('elementFromPoint:', el, flush=True)
        # 监听 pointerdown 计数
        await p.evaluate("""window.__pds=0; document.getElementById('view').addEventListener('pointerdown',()=>window.__pds++);""")
        await p.mouse.click(160, 90)
        await asyncio.sleep(3)
        print('pointerdowns after click:', await p.evaluate('window.__pds'), flush=True)
        print('mode:', await p.text_content('#deck-mode'), flush=True)
        await b.close()
asyncio.run(m())
