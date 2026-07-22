#!/usr/bin/env python3
import asyncio, json
from playwright.async_api import async_playwright

BASE = 'http://127.0.0.1:8791/?q=standard&steps=60'
ARGS = ['--enable-unsafe-swiftshader', '--disable-dev-shm-usage', '--no-sandbox',
        '--autoplay-policy=no-user-gesture-required']
R = {}
def rec(name, ok, info=''):
    R[name] = {'ok': bool(ok)}
    print(('PASS ' if ok else 'FAIL ') + name + ' :: ' + str(info)[:180], flush=True)

async def wait_ready(page, t=240000):
    await page.wait_for_function("document.body.classList.contains('ready')", timeout=t)

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(executable_path='/usr/bin/chromium', args=ARGS)
        ctx = await browser.new_context(viewport={'width': 480, 'height': 270})
        page = await ctx.new_page()
        page.set_default_timeout(120000)
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        await page.goto(BASE, wait_until='domcontentloaded')
        await wait_ready(page)

        rec('default_cine_on', (await page.text_content('#deck-mode')) == 'CINEMATIC SEQUENCE')

        # drag breaks cine + deck hint appears (poll within 6s window)
        await page.mouse.move(160, 90); await page.mouse.down()
        await page.mouse.move(210, 95, steps=2); await page.mouse.up()
        hint_seen = False
        for _ in range(20):
            if await page.evaluate("document.getElementById('deck-hint').classList.contains('show')"):
                hint_seen = True; break
            await asyncio.sleep(0.4)
        nav = (await page.text_content('#deck-mode')) == 'NAVIGATION'
        if nav and not hint_seen:
            for _ in range(15):
                if await page.evaluate("document.getElementById('deck-hint').classList.contains('show')"):
                    hint_seen = True; break
                await asyncio.sleep(0.4)
        rec('drag_breaks_cine', nav)
        rec('deck_hint_after_takeover', hint_seen)

        # keyboard 1 -> poster flight (slow frames: poll up to 90s)
        await page.keyboard.press('1')
        poster_ok = False
        for _ in range(90):
            d = await page.text_content('#t-dist')
            if d.startswith('24.0'): poster_ok = True; break
            await asyncio.sleep(1)
        rec('key1_poster_flight', poster_ok, d)

        await page.keyboard.press('c'); await asyncio.sleep(1)
        rec('key_c_cine', (await page.text_content('#deck-mode')) == 'CINEMATIC SEQUENCE')
        await page.keyboard.press('c'); await asyncio.sleep(1)

        await page.keyboard.press('p'); await asyncio.sleep(0.5)
        n = await page.eval_on_selector_all('#p-rows input[type=range]', 'e=>e.length')
        rec('params_panel_21', (await page.is_visible('#params')) and n == 21, f'sliders={n}')

        await page.focus('#p-in-din'); await page.keyboard.press('h'); await asyncio.sleep(0.5)
        rec('keys_ignored_in_input', not await page.evaluate("document.getElementById('hud').classList.contains('off')"))

        await page.eval_on_selector('#p-in-din', "e=>{e.value='3.20';e.dispatchEvent(new Event('input',{bubbles:true}))}")
        await asyncio.sleep(0.3)
        stored = await page.evaluate("localStorage.getItem('gargantua.params.v1')")
        rec('storage_saved', stored and '3.2' in stored)

        await page.reload(wait_until='domcontentloaded'); await wait_ready(page)
        await page.keyboard.press('p'); await asyncio.sleep(0.5)
        v = await page.eval_on_selector('#p-val-din', 'e=>e.textContent')
        rec('storage_retained_after_reload', v == '3.20', v)

        await page.click('#btn-reset'); await asyncio.sleep(0.5)
        v = await page.eval_on_selector('#p-val-din', 'e=>e.textContent')
        stored = await page.evaluate("localStorage.getItem('gargantua.params.v1')")
        rec('reset_restores', v == '2.75' and stored is None, f'val={v} stored={stored}')

        await page.keyboard.press('p'); await asyncio.sleep(0.5)
        # quality: storage was cleared; tier from URL standard -> click -> high
        prof0 = await page.text_content('#t-prof')
        await page.click('#btn-quality'); await asyncio.sleep(1)
        prof = await page.text_content('#t-prof'); steps = await page.text_content('#t-steps')
        rec('quality_cycle', prof0 == 'STANDARD' and prof == 'HIGH' and steps == '320', f'{prof0}->{prof}/{steps}')

        await page.keyboard.press('h'); await asyncio.sleep(0.5)
        off1 = await page.evaluate("document.getElementById('hud').classList.contains('off')")
        await page.keyboard.press('h'); await asyncio.sleep(0.5)
        off2 = await page.evaluate("document.getElementById('hud').classList.contains('off')")
        rec('hud_toggle', off1 and not off2)

        await page.click('#btn-sound'); await asyncio.sleep(2)
        auds = await page.evaluate("[...document.querySelectorAll('audio')].map(a=>({src:a.src.split('/').pop(),paused:a.paused,vol:+a.volume.toFixed(2),loop:a.loop}))")
        label = await page.text_content('#btn-sound')
        main_aud = next((a for a in auds if 'main' in a['src']), None)
        rec('sound_on_opus', main_aud and not main_aud['paused'] and 'opus' in main_aud['src'] and 'ON' in label, json.dumps(auds))

        await page.click('#btn-sound'); await asyncio.sleep(0.5)
        rec('sound_off_pauses', await page.evaluate("[...document.querySelectorAll('audio')].every(a=>a.paused)"))

        await page.set_viewport_size({'width': 500, 'height': 300}); await asyncio.sleep(2)
        rec('resize_no_errors', len(errors) == 0, ';'.join(errors)[:150])

        ctx2 = await browser.new_context(viewport={'width': 480, 'height': 270}, reduced_motion='reduce')
        page2 = await ctx2.new_page(); page2.set_default_timeout(120000)
        await page2.goto(BASE, wait_until='domcontentloaded'); await wait_ready(page2)
        rec('reduced_motion_no_cine', (await page2.text_content('#deck-mode')) == 'NAVIGATION')
        await ctx2.close()

        ctx3 = await browser.new_context(viewport={'width': 390, 'height': 844})
        page3 = await ctx3.new_page(); page3.set_default_timeout(120000)
        await page3.goto(BASE + '&nocine', wait_until='domcontentloaded'); await wait_ready(page3)
        await asyncio.sleep(1)
        boxes = await page3.evaluate("""(() => {
          const r = id => { const b = document.getElementById(id).getBoundingClientRect(); return {x:b.x,y:b.y,w:b.width,h:b.height}; };
          return { tel: r('telemetry'), deck: r('deck') };
        })()""")
        ov = not (boxes['tel']['x'] + boxes['tel']['w'] <= boxes['deck']['x'] + 1 or
                  boxes['deck']['x'] + boxes['deck']['w'] <= boxes['tel']['x'] + 1 or
                  boxes['tel']['y'] + boxes['tel']['h'] <= boxes['deck']['y'] + 1 or
                  boxes['deck']['y'] + boxes['deck']['h'] <= boxes['tel']['y'] + 1)
        rec('mobile_390_no_overlap', not ov, json.dumps(boxes)[:150])
        await page3.screenshot(path='/mnt/agents/output/gargantua_test/mobile.png')
        small = await page3.evaluate("""[...document.querySelectorAll('.btn')].filter(b=>{const r=b.getBoundingClientRect();return r.height<40||r.width<40}).length""")
        rec('touch_targets_40px', small == 0, f'small={small}')
        await ctx3.close()

        await browser.close()
        fails = [k for k, v in R.items() if not v['ok']]
        print('==== %d/%d PASS ====' % (len(R) - len(fails), len(R)))
        if fails: print('FAILED:', fails)

asyncio.run(main())
