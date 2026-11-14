from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={'width': 390, 'height': 800}); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.on('console', lambda m: m.type == 'error' and errs.append(m.text))
    pg.goto('http://localhost:8765/index.html')
    pg.wait_for_selector('[data-sincap-comp]', state='attached', timeout=20000)
    pg.click('[data-sincap-comp]'); pg.wait_for_selector('#estudio img', timeout=20000)
    pg.locator('#estudio img').first.screenshot(path='sc.png')
    print(errs, pg.evaluate('document.documentElement.scrollWidth'))
