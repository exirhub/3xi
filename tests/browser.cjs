/* Real browser interaction checks. Run with Node and Playwright installed. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
let chromium;
try { ({chromium} = require('playwright')); }
catch { ({chromium} = require(process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES + '/playwright')); }
const root = path.resolve(__dirname, '../website');
const types = {'.html':'text/html','.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml','.webp':'image/webp','.mp3':'audio/mpeg','.mp4':'video/mp4'};
const server = http.createServer((req,res) => {
  const name = decodeURIComponent(new URL(req.url,'http://localhost').pathname);
  const file = path.resolve(root,'.'+(name === '/' ? '/index.html' : name));
  if(!file.startsWith(root + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) { res.writeHead(404).end(); return; }
  const size = fs.statSync(file).size;
  const headers = {'Content-Type':types[path.extname(file)] || 'application/octet-stream','Accept-Ranges':'bytes'};
  const range = /^bytes=(\d+)-(\d*)$/.exec(req.headers.range || '');
  let start = 0, end = size-1;
  if(range) { start = Number(range[1]); end = range[2] ? Math.min(Number(range[2]),end) : end; if(start > end) {res.writeHead(416).end();return;} headers['Content-Range'] = `bytes ${start}-${end}/${size}`; }
  headers['Content-Length'] = end-start+1; res.writeHead(range ? 206 : 200, headers);
  if(req.method === 'HEAD') res.end(); else fs.createReadStream(file,{start,end}).pipe(res);
});
(async () => {
  await new Promise(resolve => server.listen(0,'127.0.0.1',resolve));
  const launch = {headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu']};
  if(process.env.THREEXI_CHROMIUM_PATH) launch.executablePath = process.env.THREEXI_CHROMIUM_PATH;
  const browser = await chromium.launch(launch);
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1024}});
    const errors = [], badResponses = [], media = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('response', response => { if(response.status() >= 400) badResponses.push(response.url()); });
    page.on('request', request => { if(/\.(mp3|mp4)$/.test(request.url())) media.push(request.url()); });
    await page.goto(`http://127.0.0.1:${server.address().port}`,{waitUntil:'networkidle'});
    assert.equal(media.length,0,'Media must not start downloading before interaction');
    assert.match(await page.title(), /3xi Atlas/);
    const snapshots = process.env.THREEXI_SCREENSHOTS;
    if(snapshots) { fs.mkdirSync(snapshots,{recursive:true}); await page.screenshot({path:path.join(snapshots,'desktop.png'),fullPage:true}); }
    await page.locator('[data-filter="design"]').click();
    assert.equal(await page.locator('.collection-card:visible').count(),1);
    await page.locator('[data-filter="all"]').click();
    await page.locator('[data-save="forest"]').click();
    assert.equal(await page.locator('#saved-count').textContent(),'1');
    await page.reload({waitUntil:'networkidle'});
    assert.equal(await page.locator('[data-save="forest"]').getAttribute('aria-pressed'),'true');
    await page.locator('.image-open[data-gallery="forest"]').click();
    assert.equal(await page.locator('#gallery-dialog').evaluate(d => d.open),true);
    await page.keyboard.press('ArrowRight');
    assert.equal(await page.locator('#gallery-position').textContent(),'2 / 3');
    await page.keyboard.press('Escape');
    await page.locator('[data-track="0"]').click();
    await page.waitForFunction(() => !document.querySelector('#ambient-audio').paused && document.querySelector('#ambient-audio').currentTime > .1);
    await page.locator('#audio-next').click();
    await page.waitForFunction(() => document.querySelector('#dock-title').textContent === 'Canopy' && document.querySelector('#ambient-audio').readyState >= 2);
    await page.locator('#audio-seek').evaluate(input => {input.value=20;input.dispatchEvent(new Event('input',{bubbles:true}));});
    assert.ok(await page.locator('#ambient-audio').evaluate(a => a.currentTime >= 19));
    await page.locator('.film-poster[data-film="space"]').click();
    await page.waitForFunction(() => document.querySelector('#film-player').readyState >= 2);
    assert.equal(await page.locator('#ambient-audio').evaluate(a => a.paused),true);
    assert.ok(await page.locator('#film-player').evaluate(v => v.duration > 15));
    await page.keyboard.press('Escape');
    await page.waitForFunction(() => !document.querySelector('#film-player').hasAttribute('src'));
    assert.equal(await page.locator('#film-player').getAttribute('src'),null);
    await page.locator('.journal-image[data-article="attention"]').click();
    assert.ok((await page.locator('#reading-content').textContent()).length > 1800);
    await page.keyboard.press('Escape');
    await page.locator('#open-saved').click();
    assert.equal(await page.locator('.saved-item').count(),1);
    await page.locator('.saved-item > button:last-child').click();
    assert.equal(await page.locator('.saved-item').count(),0);
    await page.keyboard.press('Escape');
    await page.locator('#motion-toggle').click();
    assert.equal(await page.locator('#motion-toggle').getAttribute('aria-pressed'),'true');
    await page.setViewportSize({width:390,height:844}); await page.goto(`http://127.0.0.1:${server.address().port}`,{waitUntil:'networkidle'});
    await page.locator('#menu-toggle').click();
    assert.equal(await page.locator('#menu-toggle').getAttribute('aria-expanded'),'true');
    await page.locator('#main-nav a[href="#films"]').click();
    assert.equal(await page.locator('#menu-toggle').getAttribute('aria-expanded'),'false');
    await page.evaluate(() => scrollTo(0,0));
    if(snapshots) await page.screenshot({path:path.join(snapshots,'mobile.png'),fullPage:true});
    for(const width of [320,390,768,1440]) {
      await page.setViewportSize({width,height:900});
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),true,`Horizontal overflow at ${width}px`);
    }
    assert.deepEqual(errors,[]); assert.deepEqual(badResponses,[]);
    console.log('PASS: desktop/mobile layout, filtering, saved persistence, gallery keyboard navigation, audio playback/seek, video decoding, journal, reduced motion and navigation.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode=1; }).finally(() => server.close());
