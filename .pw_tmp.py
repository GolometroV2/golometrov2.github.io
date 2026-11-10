import subprocess, time
from playwright.sync_api import sync_playwright
srv = subprocess.Popen(['python3', '-m', 'http.server', '8123'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={'width': 390, 'height': 900})
        err = []
        pg.on('pageerror', lambda e: err.append(str(e)))
        pg.on('console', lambda m: err.append(m.text) if m.type == 'error' else None)
        pg.goto('http://localhost:8123/index.html')
        pg.wait_for_selector('#sincap', state='attached', timeout=15000)
        time.sleep(2)
        el = pg.query_selector('#sincap')
        print(el.inner_text())
        el.scroll_into_view_if_needed()
        time.sleep(1)
        el.screenshot(path='/tmp/sincap.png')
        print('overflow', pg.evaluate('document.documentElement.scrollWidth > innerWidth'))
        print('errores', err)
        b.close()
finally:
    srv.terminate()
