import asyncio, json
from playwright.async_api import async_playwright
async def m():
    async with async_playwright() as pw:
        b = await pw.chromium.launch(executable_path='/usr/bin/chromium', args=['--enable-unsafe-swiftshader','--no-sandbox','--disable-dev-shm-usage'])
        p = await (await b.new_context(viewport={'width':390,'height':844})).new_page()
        p.set_default_timeout(240000)
        await p.goto('http://127.0.0.1:8791/?q=standard&steps=60&nocine', wait_until='domcontentloaded')
        await p.wait_for_function("document.body.classList.contains('ready')")
        small = await p.evaluate("""[...document.querySelectorAll('.btn')].map(b=>{const r=b.getBoundingClientRect();return {id:b.id,w:Math.round(r.width),h:Math.round(r.height)}}).filter(x=>x.w<40||x.h<40)""")
        print('small buttons:', json.dumps(small), flush=True)
        await p.screenshot(path='/mnt/agents/output/gargantua_test/mobile2.png')
        await b.close()
asyncio.run(m())
