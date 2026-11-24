/** Isolated real Chrome verification. No OS installation, no learning writes. */
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import http from 'node:http';
import {createRequire} from 'node:module';
import {launchAcceptanceChrome} from './launch_acceptance_chrome.mjs';
const [target, output] = process.argv.slice(2);
assert.ok(target && output, 'Usage: node scripts/pwa_acceptance.mjs <export-directory|https-url> <evidence-directory>');
await fs.mkdir(output, {recursive:true});
let server;
let base = target;
if (!/^https:\/\//.test(target)) {
  const root = path.resolve(target);
  server = http.createServer(async (request, response) => {
    const url = new URL(request.url, 'http://localhost');
    const pathname = decodeURIComponent(url.pathname).replace(/^\/GraspMemoEdu-Pages\//, '');
    const relative = !pathname || pathname.endsWith('/') ? pathname + 'index.html' : pathname;
    const file = path.resolve(root, relative);
    if (!file.startsWith(root + path.sep)) {response.writeHead(404).end(); return;}
    try {
      const content = await fs.readFile(file);
      const types = {'.html':'text/html; charset=utf-8','.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml','.png':'image/png','.webmanifest':'application/manifest+json','.json':'application/json'};
      const cache = /\.(?:m?js|css|svg)$/.test(file) && url.searchParams.has('v') ? 'public, max-age=0' : 'no-store';
      response.writeHead(200, {'Content-Type':types[path.extname(file)] || 'application/octet-stream','Cache-Control':cache}).end(content);
    } catch {response.writeHead(404).end();}
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  base = `http://127.0.0.1:${server.address().port}/GraspMemoEdu-Pages/`;
}
base = new URL('./', base).href;
const require = createRequire(path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/_entry.cjs'));
const {chromium} = require('playwright');
const profile = await fs.mkdtemp(path.join(path.resolve(output),'chrome-profile-'));
const contextOptions = {viewport:{width:1365,height:950},locale:'zh-CN'};
const context = process.env.CHROME_EXECUTABLE
  ? await chromium.launchPersistentContext(profile,{headless:true,executablePath:process.env.CHROME_EXECUTABLE,...contextOptions})
  : await launchAcceptanceChrome(require, [], {profile, ...contextOptions});
const report = {base,checks:[],errors:[],badResponses:[],learningWrites:[],os_installation_tested:false,api_mocked:false};
const workerReads = [];
context.on('request', request => { if (request.serviceWorker()) workerReads.push(new URL(request.url()).pathname); });
const awaitCached = (page, selector) => page.waitForFunction(async selector => {
  const asset = document.querySelector(selector);
  if (!asset) return false;
  const url = asset.href || asset.src;
  for (const key of await caches.keys()) {
    if (key.startsWith('graspmemoedu-static:') && await (await caches.open(key)).match(url)) return true;
  }
  return false;
}, selector);
const pass = label=>{report.checks.push(label);console.log('PASS '+label);};
try {
  const page = await context.newPage();
  page.setDefaultTimeout(25000);
  page.on('pageerror',e=>report.errors.push(e.message));
  page.on('response',r=>{if(r.status()>=400 && new URL(r.url()).origin===new URL(base).origin) report.badResponses.push({url:r.url(),status:r.status()});});
  page.on('request',r=>{if(r.method()==='POST' && /\/api\/(submit|choose|continue|select|pause|review\/|training\/)/.test(new URL(r.url()).pathname)) report.learningWrites.push(r.url());});
  assert.equal((await page.goto(new URL('download.html',base).href)).status(),200);
  await page.evaluate(async()=>{await navigator.serviceWorker.ready;});
  await page.waitForFunction(()=>!!navigator.serviceWorker.controller);
  const cdp = await context.newCDPSession(page);
  await cdp.send('Page.enable');
  const manifest = await cdp.send('Page.getAppManifest');
  assert.equal(manifest.errors.length,0,JSON.stringify(manifest.errors));
  const data = JSON.parse(manifest.data);
  assert.equal(data.display,'standalone');
  assert.equal(new URL(data.start_url,manifest.url).href,base);
  report.manifest = {url:manifest.url,name:data.name,start_url:data.start_url,scope:data.scope,display:data.display};
  const installability = await cdp.send('Page.getInstallabilityErrors');
  report.installability = installability.installabilityErrors;
  assert.deepEqual(report.installability,[]);
  pass('Chromium recognizes an installable PWA with correct subdirectory scope');
  for (const width of [320,375,414,768,1365]) {
    await page.setViewportSize({width,height:950});
    const size = await page.evaluate(()=>({scroll:document.documentElement.scrollWidth,width:innerWidth}));
    assert.ok(size.scroll<=size.width,`overflow at ${width}`);
    for(const platform of ['ios','android','windows']) assert.ok(await page.locator(`#${platform}`).isVisible());
    assert.equal(await page.locator('a,button').evaluateAll(nodes=>nodes.filter(node=>getComputedStyle(node).display!=='none' && getComputedStyle(node).whiteSpace!=='nowrap' && node.getClientRects().length>1).length),0);
    await page.screenshot({path:path.join(output,`install-${width}.png`),fullPage:true});
  }
  pass('Installation instructions render at 320/375/414/768/1365 pixels');
  // A synthetic prompt tests UI state only, never pretends an OS install happened.
  await page.evaluate(()=>{
    window.promptCalls=0;
    const event=new Event('beforeinstallprompt',{cancelable:true});
    event.prompt=async()=>{window.promptCalls++;}; event.userChoice=Promise.resolve({outcome:'dismissed'});
    dispatchEvent(event);
  });
  await page.locator('[data-pwa-install]').click();
  await page.waitForFunction(()=>document.querySelector('[data-pwa-install]').hidden);
  assert.equal(await page.evaluate(()=>window.promptCalls),1);
  pass('Install prompt dismissal returns to manual instructions (synthetic event)');
  await page.evaluate(async()=>{
    const input=document.createElement('textarea');input.id='unsent-canary';input.value='未提交答案';document.body.append(input);
    window.updateCanary='same-document';await (await navigator.serviceWorker.ready).update();
  });
  assert.equal(await page.locator('#unsent-canary').inputValue(),'未提交答案');
  assert.equal(await page.evaluate(()=>window.updateCanary),'same-document');
  pass('Worker update keeps the document and unsent input intact');
  await context.setOffline(true);
  const offline=await page.goto(new URL('download.html',base).href);
  assert.equal(offline.status(),503);
  await page.getByRole('heading',{name:'暂时无法连接'}).waitFor();
  assert.equal(await page.getByRole('link',{name:'重新连接'}).getAttribute('href'),base);
  await page.screenshot({path:path.join(output,'offline.png'),fullPage:true});
  await context.setOffline(false);
  await page.goto(new URL('download.html',base).href);
  await page.getByRole('heading',{name:'把学习放到桌面。'}).waitFor();
  await awaitCached(page, 'link[href*="install.css?v="]');
  const installReads = workerReads.filter(name => name.endsWith('/install.css')).length;
  pass('Controlled offline navigation shows retry and recovers online');
  report.badResponses=report.badResponses.filter(r=>r.status!==503);
  const {appId: rootId} = await cdp.send('Page.getAppId');
  assert.ok(rootId);
  const appIds = new Set([rootId]);
  report.scoped = {};
  for (const [app, title] of Object.entries({'free-study':'安装自由学习', 'math-courses':'安装数学课程'})) {
    const home = new URL('pwa-' + app + '/', base).href;
    const install = new URL('install.html', home).href;
    assert.equal((await page.goto(install)).status(), 200);
    await page.getByRole('heading', {name: title, exact: true}).waitFor();
    await page.getByText('应用只恢复其范围内的页面', {exact: false}).waitFor();
    assert.equal(await page.evaluate(async () => (await navigator.serviceWorker.ready).scope), base);
    const variant = await cdp.send('Page.getAppManifest');
    assert.deepEqual(variant.errors, []);
    const manifest = JSON.parse(variant.data);
    const {appId} = await cdp.send('Page.getAppId');
    assert.equal(appId, new URL('/GraspMemoEdu/' + app, base).href);
    assert.ok(!appIds.has(appId));
    appIds.add(appId);
    assert.equal(new URL(manifest.scope, variant.url).href, home);
    assert.equal(new URL(manifest.start_url, variant.url).href, home);
    assert.deepEqual((await cdp.send('Page.getInstallabilityErrors')).installabilityErrors, []);
    for (const width of [320, 375, 414, 768]) {
      await page.setViewportSize({width, height: 850});
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
        `${app} installation instructions overflow at ${width}px`);
    }
    await page.setViewportSize({width: 375, height: 850});
    await page.screenshot({path: path.join(output, app + '-install.png'), fullPage: true});
    report.scoped[app] = {appId, home, install};
  }
  pass('Chrome recognizes two scoped install pages with unique IDs and a shared worker');
  assert.equal(workerReads.filter(name => name.endsWith('/install.css')).length, installReads);
  pass('Scoped installers reuse the verified stylesheet with zero additional worker network reads');
  // Use the real API only on the deployed origin, where CORS allows it.
  if (!server) {
    await page.goto(base,{waitUntil:'networkidle'});
    await page.locator('.subjectCard').first().waitFor();
    report.subjects=await page.locator('.subjectCard').count();
    await awaitCached(page, 'script[src*="app.js?v="]');
    const appReads = workerReads.filter(name => name.endsWith('/app.js')).length;
    await page.locator('#userMenuButton').click();
    await page.locator('a[data-i18n="pwa.install"]').waitFor({state:'visible'});
    await page.locator('a[data-i18n="pwa.install"]').click();
    assert.equal(new URL(page.url()).pathname,new URL('download.html',base).pathname);
    pass('Live learning home and account-menu installation entry work with real API');
    for (const [app, hash, heading, label] of [
      ['free-study', '#/free-study', '自由学习', '安装自由学习'],
      ['math-courses', '#/subjects/math/courses', '课程', '安装数学课程'],
    ]) {
      const {home, install} = report.scoped[app];
      await page.goto(home);
      await page.locator('#portalContent h1').filter({hasText: heading}).first().waitFor();
      assert.equal(new URL(page.url()).hash, hash);
      await page.locator('#userMenuButton').click();
      assert.equal(await page.getByRole('link', {name: label, exact: true}).getAttribute('href'), install);
      await page.goto(new URL(hash, base).href);
      await page.locator('#portalContent h1').filter({hasText: heading}).first().waitFor();
      await page.locator('#userMenuButton').click();
      assert.equal(await page.getByRole('link', {name: label, exact: true}).getAttribute('href'), install);
    }
    pass('Both scoped first launches and install links use their live learning routes');
    assert.equal(workerReads.filter(name => name.endsWith('/app.js')).length, appReads);
    pass('All three learning entries reuse app.js with zero additional worker network reads');
  }
  assert.deepEqual(report.errors,[]);
  assert.deepEqual(report.badResponses,[]);
  assert.deepEqual(report.learningWrites,[]);
  pass('No script errors, failed online assets, or learning mutations');
  report.status='passed';
} catch(error) {report.status='failed';report.failure=String(error.stack||error);throw error;}
finally {
  await fs.writeFile(path.join(output,'report.json'),JSON.stringify(report,null,2));
  await context.close();
  if(server) await new Promise(resolve=>server.close(resolve));
}
