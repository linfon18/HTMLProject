import asyncio
from playwright.async_api import async_playwright
async def m():
    async with async_playwright() as pw:
        b = await pw.chromium.launch(executable_path='/usr/bin/chromium', args=['--enable-unsafe-swiftshader','--no-sandbox','--disable-dev-shm-usage'])
        ctx = await b.new_context(viewport={'width':480,'height':270})
        p = await ctx.new_page()
        p.on('console', lambda m: print('CON', m.type, m.text[:150]))
        p.on('pageerror', lambda e: print('PERR', str(e)[:200]))
        r = await p.goto('http://127.0.0.1:8791/?q=standard', wait_until='domcontentloaded')
        print('status', r.status)
        await asyncio.sleep(3)
        html = await p.content()
        print('len', len(html), 'has_deck', 'id="deck"' in html)
        print('title', await p.title())
        await b.close()
asyncio.run(m())
