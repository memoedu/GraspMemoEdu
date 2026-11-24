import assert from 'node:assert/strict';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import os from 'node:os';
import path from 'node:path';
import {launchAcceptanceChrome} from './launch_acceptance_chrome.mjs';

const [output, fixture, base='http://127.0.0.1:18891'] = process.argv.slice(2);
const require = createRequire(path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/_entry.cjs'));
const engine = process.env.CLIPPER_BROWSER || 'chrome', mobile = process.env.CLIPPER_MOBILE === '1';
const browser = engine === 'chrome' ? await launchAcceptanceChrome(require) : await require('playwright')[engine].launch();
const ctx = await browser.newContext({viewport:mobile ? {width:390,height:844}:{width:1280,height:900},
  locale:'zh-CN', hasTouch:mobile, ...(mobile && engine !== 'firefox' ? {isMobile:true}:{})});
ctx.setDefaultTimeout(30000);
const page = await ctx.newPage(), errors=[], checks=[];
const route=base+'/#/subjects/math/topic/synthetic-course', panel=page.locator('.clipperWorkspace');
const toggle=page.locator('[data-question-tool="clipper"]'), chooser=page.locator('.clipperActions');
const invitations=JSON.parse(await readFile(path.join(fixture,'browser-fixtures.json'),'utf8'));
ctx.on('page',p=>p.on('pageerror',e=>errors.push(e.message)));
page.on('pageerror',e=>errors.push(e.message));
if(process.env.CLIPPER_FALLBACK==='1')await ctx.addInitScript(()=>{
  Object.defineProperty(HTMLElement.prototype,'showPopover',{value:undefined});
  Object.defineProperty(window,'open',{value:()=>null});
});
await mkdir(output,{recursive:true});
async function enter(){
  await page.goto(route);
  const marker=page.locator('p').filter({hasText:'Capture the sequence'}).first();
  await Promise.race([marker.waitFor(),page.getByRole('button',{name:'重试',exact:true}).waitFor()]);
  if(!await marker.isVisible())await page.getByRole('button',{name:'重试',exact:true}).click();
  await marker.waitFor();
}
async function login(invite){
  await page.locator('#userMenuButton').click();await page.locator('#identityButton').click();
  const dialog=page.locator('#identityDialog');await dialog.locator('input').fill(invite);
  await dialog.locator('form').evaluate(f=>f.requestSubmit());await dialog.waitFor({state:'hidden'});await toggle.waitFor();
}
async function select(kind, occurrence='last'){
  const text=kind==='mixed'?'与下方代码':kind==='formula'?'Capture the sequence':'另一结论成立';
  const target=page.locator('p').filter({hasText:text}).first();await target.scrollIntoViewIfNeeded();
  await target.evaluate((p,{kind,occurrence})=>{
    const r=document.createRange();
    if(kind==='mixed'){r.setStartBefore(p);r.setEndAfter(p.nextElementSibling.nextElementSibling);}
    else if(kind==='formula')r.selectNode(p.querySelector('[data-tex]'));
    else {
      const texts=[...p.childNodes].filter(n=>n.nodeType===3&&n.data.includes('成立'));
      const n=occurrence==='last'?texts.at(-1):texts[0], k=n.data.indexOf('成立');
      r.setStart(n,k);r.setEnd(n,k+2);
    }
    const s=getSelection();s.removeAllRanges();s.addRange(r);
  },{kind,occurrence});
  await chooser.waitFor();
}
async function operation(label){
  await chooser.getByRole('button',{name:label,exact:true}).click();
  const handle=await panel.locator('.clipperPanel:not([hidden]) .clipperFeatureFrame').elementHandle({timeout:45000});
  const f=await handle.contentFrame();await f.locator('#content > *').first().waitFor({state:'attached',timeout:75000});
  return f;
}
async function view(f,condition){
  const until=Date.now()+45000;
  let state;
  do{
    state=await f.evaluate(async()=>JSON.parse(await DotNet.invokeMethodAsync('KnowledgeClipper.Browser','View')));
    if(state.shared.error)throw Error(state.shared.error);
    if(!state.shared.working&&condition(state))return state;
    await new Promise(resolve=>setTimeout(resolve,120));
  }while(Date.now()<until);
  throw Error('The workflow did not reach its expected state: '+state.shared.screen+' '+state.shared.speechError+' '+state.shared.lookupError);
}
async function close(){await panel.getByRole('button',{name:'关闭',exact:true}).click();await panel.waitFor({state:'detached'});}
try{
  await enter();assert.equal(await toggle.isVisible(),false);await login(invitations[0]);
  await toggle.click();assert.equal(await toggle.getAttribute('aria-pressed'),'true');assert.equal(await panel.count(),0);
  const sample=page.locator('p').filter({hasText:'Capture the sequence'}).first();
  await sample.scrollIntoViewIfNeeded();
  if(!mobile){
    const box=await sample.boundingBox();await page.mouse.move(box.x+2,box.y+box.height/2);await page.mouse.down();
    await page.mouse.move(box.x+86,box.y+box.height/2,{steps:10});await page.mouse.up();await chooser.waitFor();
    await page.evaluate(()=>getSelection().removeAllRanges());await sample.locator('[data-tex]').first().hover();
    await page.keyboard.press('Alt+Shift+s');await chooser.waitFor();await page.keyboard.press('Alt+Shift+c');
    await page.waitForFunction(()=>document.activeElement?.matches('.clipperActions button:first-child'));
    checks.push('native drag and keyboard selection');
  }else{await sample.locator('[data-tex]').first().tap();await chooser.waitFor();checks.push('tap selection');}
  await select('mixed');const excerpt=await operation('摘');
  const captured=await view(excerpt,s=>s.shared.receipt);
  assert.match(captured.shared.text,/比较 \\\(a\^2\+b\^2\\\)/);
  assert.ok(!captured.shared.text.includes('\n\npython\n\n'));
  assert.ok(captured.shared.text.includes('if x > 0:\n    print(x)'));
  assert.match(captured.shared.text,/!\[方块\]\(asset:[a-f0-9]{64}\)/);
  const article=excerpt.locator('article').first();
  await article.locator('.katex').first().waitFor({state:'attached'});
  await article.locator('img[src^="blob:"]').first().waitFor();
  assert.match(await article.locator('pre').first().innerText(),/    print\(x\)/);
  const linePositions=await article.locator('pre code>span').evaluateAll(lines=>lines.map(line=>line.getBoundingClientRect().top));
  assert.ok(linePositions.length>=2 && linePositions[1]>linePositions[0], 'Source lines should occupy distinct visual lines');
  await page.screenshot({path:path.join(output,'excerpt.png')});checks.push('native rich excerpt, original TeX, indented code and in-place PNG');
  await panel.getByRole('button',{name:'最小化',exact:true}).click();
  await page.evaluate(()=>scrollBy(0,220));await panel.getByRole('button',{name:'恢复',exact:true}).click();
  await panel.getByRole('button',{name:'铺满标签页',exact:true}).click();await panel.getByRole('button',{name:'还原',exact:true}).click();
  if(!mobile&&process.env.CLIPPER_FALLBACK!=='1'){
    const event=page.waitForEvent('popup');await panel.getByRole('button',{name:'普通窗口',exact:true}).click();
    const popup=await event;const nested=popup.frameLocator('.clipperFeatureFrame');
    await nested.locator('article .katex').first().waitFor({state:'attached',timeout:65000});
    const closed=popup.waitForEvent('close');
    await popup.getByRole('button',{name:'在当前页置顶',exact:true}).click().catch(error=>{
      if(!popup.isClosed())throw error;
    });
    await closed;
    await page.frameLocator('.clipperFeatureFrame').locator('article .katex').first().waitFor({state:'attached',timeout:65000});
  }
  await close();checks.push('ordinary window, pinned workspace and size controls');
  await page.evaluate(()=>getSelection().removeAllRanges());
  const picture=page.getByRole('img',{name:'方块',exact:true}).first();
  if(mobile)await picture.tap();else await picture.click();
  const images=await operation('图');
  await images.locator('figure img[src^="blob:"]').waitFor();
  const role=images.locator('figure select').first();
  await role.selectOption('answer');
  await view(images,s=>s.collection[0].role==='answer');
  await role.selectOption('question');
  await view(images,s=>s.collection[0].role==='question');
  const format=images.locator('select').filter({has:images.locator('option[value="original"]')});
  await format.selectOption('original');
  await view(images,s=>s.original);
  const routeChoice=images.locator('select').filter({has:images.locator('option[value="image-excerpt"]')});
  await routeChoice.selectOption('image-excerpt');
  await images.getByRole('button',{name:'处理图片',exact:true}).click();
  const imageDraft=await view(images,s=>s.shared.screen==='excerpt'&&s.cards.some(c=>c.frontImages.length===1));
  if(!imageDraft.shared.receipt){
    await images.getByRole('button',{name:'保存到个人自由学习',exact:true}).first().click();
  }
  await view(images,s=>s.shared.receipt);await close();checks.push('single image opens canonical collection, front/back roles and original image excerpt');
  await select('sentence');const reading=await operation('读');const initial=await view(reading,s=>s.shared.audio&&s.shared.lookup&&s.cards.length);
  const sentence='若 \\(x^2=0.25\\)，另一结论成立。';
  assert.equal(initial.shared.context,sentence);assert.equal(sentence.slice(initial.shared.start,initial.shared.start+2),'成立');
  assert.equal(initial.shared.lookup.contextText,sentence);assert.equal(initial.cards[0].front,sentence);
  await close();await select('sentence');const repeat=await operation('读');
  const repeated=await view(repeat,s=>s.shared.audio&&s.shared.replayOnly);
  assert.equal(repeated.shared.audio,initial.shared.audio);assert.equal(repeated.cards.length,0);await close();
  await select('sentence','first');const different=await operation('读');
  const changed=await view(different,s=>s.shared.audio&&s.shared.lookup);
  assert.equal(changed.shared.context,'若 \\(x>0\\)，结论成立。');await close();
  const requests=(await readFile(path.join(fixture,'provider-inputs.jsonl'),'utf8')).trim().split('\n').map(JSON.parse);
  const speech=requests.filter(r=>r.path==='/audio/speech').map(r=>r.payload.input);
  assert.ok(speech.some(t=>t.includes('平方')&&t.includes('0.25')&&t.includes('另一结论成立')));
  assert.ok(speech.some(t=>/大[於于]/.test(t)&&t.includes('结论成立')&&!t.includes('另一')));
  checks.push('exact occurrence, complete math sentence, saved language cards, scoped recording replay');
  await select('formula');const card=await operation('卡');const editor=card.frameLocator('iframe[title]');
  const front=editor.getByRole('textbox',{name:'卡片正面',exact:true}),back=editor.getByRole('textbox',{name:'卡片背面',exact:true});
  await front.fill('验收 \\(x^2\\)');await back.fill('保留公式和原始选区');
  await editor.getByRole('button',{name:'保存到个人自由学习',exact:true}).click();
  await view(card,s=>s.shared.receipt);await close();
  await select('formula');const ask=await operation('问');
  await ask.frameLocator('iframe[title]').getByText('测试回答：保留题干条件。',{exact:false}).first().waitFor();await close();
  checks.push('shared chat editor, manual card, send-once question');
  await page.goto(base+'/#/settings/knowledge-clipper');const scope=page.locator('[name=contextGranularity]');
  const localToggle=page.getByRole('checkbox',{name:'在此浏览器启用选区工具'});
  await localToggle.uncheck();assert.equal(await toggle.getAttribute('aria-pressed'),'false');
  await localToggle.check();assert.equal(await toggle.getAttribute('aria-pressed'),'true');
  await scope.selectOption('paragraph');await page.getByRole('button',{name:'保存设置',exact:true}).click();
  await page.getByText('已保存，新选区使用这些设置。').waitFor();await enter();
  await select('sentence');const contextual=await operation('摘');
  const para=await view(contextual,s=>s.shared.receipt);assert.ok(para.shared.context.includes('若 \\(x>0\\)')&&para.shared.context.includes('后一段。'));await close();
  await page.goto(base+'/#/free-study');await page.getByRole('button',{name:'翻看背面',exact:true}).click();
  await page.getByRole('button',{name:'良好',exact:true}).click();
  await page.getByRole('button',{name:'摘录',exact:true}).click();await page.locator('.clipperLibraryItem .katex').first().waitFor({state:'attached'});
  for(const name of ['导出今天','导出全部']){
    const event=page.waitForEvent('download');await page.getByRole('button',{name,exact:true}).click();
    const download=await event;assert.match(download.suggestedFilename(),/\.zip$/);
    await download.saveAs(path.join(output,name+'.zip'));
  }
  await page.screenshot({path:path.join(output,'personal-study.png')});checks.push('settings, paragraph scope, FSRS and day/all rich media exports');
  await login(invitations[1]);assert.equal(await toggle.getAttribute('aria-pressed'),'false');
  await page.getByRole('button',{name:'摘录',exact:true}).click();await page.getByText('这里还没有内容。').waitFor();
  checks.push('account isolation');assert.deepEqual(errors,[]);console.log('PASS',checks.length,'browser scenarios');
} finally{
  await writeFile(path.join(output,'clipper-browser.json'),JSON.stringify({engine,mobile,checks,errors},null,2));
  await browser.close();
}
