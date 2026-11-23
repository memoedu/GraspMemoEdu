/** Deterministic revision, rollback and undo checks using the site's real editing surfaces. */
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import os from 'node:os';
import path from 'node:path';
const [fixture, base] = process.argv.slice(2);
assert.ok(['localhost','127.0.0.1'].includes(new URL(base).hostname));
const require = createRequire(path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/_entry.cjs'));
const {chromium} = require('playwright');
const browser = await chromium.launch({headless:true,channel:'chrome',args:['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream']});
const page = await browser.newPage({locale:'zh-CN',permissions:['microphone']});
page.setDefaultTimeout(10000);
const button = name=>page.getByRole('button',{name,exact:true});
let preview='', confirmed='', delayFinish, began;
let audioCount=0;
const errors=[];
page.on('pageerror',e=>errors.push(String(e)));
await page.route('**/api/voice-input/stream?*',async route=>{
  const p=route.request().postDataJSON();
  let response={};
  if(p.op==='open') {began=p; response.offset=0;}
  if(['audio','finish','pause'].includes(p.op)) {
    response.offset=p.offset+Buffer.from(p.pcm,'base64').length;
    if(p.op==='finish') {if(delayFinish) await delayFinish; response.text=confirmed;}
    else {audioCount++;response.preview=preview;}
  }
  await route.fulfill({json:response});
});
async function start(field) {
  began=null;
  await field.focus();
  await button('录音输入').click();
  await button('结束录音').waitFor();
}
async function hasValue(field,text) {
  await page.waitForFunction(([el,t])=>el.value===t,[await field.elementHandle(),text]);
}
try {
  await page.goto(base+'/#/subjects/math/courses');
  await page.locator('#userMenuButton').click();
  await page.locator('#identityButton').click();
  await page.locator('#invitationCode').fill((await readFile(path.join(fixture,'fixture-invitation.txt'),'utf8')).trim());
  await page.locator('#identitySubmitButton').click();
  await page.locator('#identitySubmitButton').waitFor({state:'hidden'});
  await page.goto(base+'/#/settings');
  const name=page.locator('#profileDisplayName');
  await name.fill('前旧后');
  await name.evaluate(el=>{el.setSelectionRange(1,2);window.commits=0;el.addEventListener('input',()=>window.commits++);});
  preview='初稿'; confirmed='终稿';
  await start(name); await hasValue(name,'前初稿后'); assert.equal(began.live,true);
  assert.deepEqual(began.context.textbox,{before:'前', selected:'旧', after:'后'});
  preview='新版'; await hasValue(name,'前新版后');
  preview=''; await hasValue(name,'前旧后');
  preview='新版'; await hasValue(name,'前新版后');
  await button('取消').click(); await hasValue(name,'前旧后');
  assert.equal(await page.evaluate(()=>window.commits),0);
  await start(name); await hasValue(name,'前新版后');
  await name.press('k'); await hasValue(name,'前k后');
  await button('结束录音').click();
  await button('插入转写文字').waitFor(); await hasValue(name,'前k后');
  await button('取消').click();
  await name.evaluate(el=>el.setSelectionRange(1,2));
  await start(name); await hasValue(name,'前新版后'); await button('结束录音').click();
  await hasValue(name,'前终稿后');
  assert.equal(await page.evaluate(()=>window.commits),2);
  let release;
  delayFinish=new Promise(resolve=>{release=resolve;});
  preview='待取消';confirmed='过期结果';
  await name.evaluate(el=>el.setSelectionRange(1,3));
  await start(name); await hasValue(name,'前待取消后');
  await button('结束录音').click();
  await button('取消').click(); await hasValue(name,'前终稿后');
  release(); delayFinish=null;
  console.log('PASS native range replacement, retraction, cancellation, manual edits and single commit');

  await page.goto(base+'/#/subjects/math/banks/isolated-bank/group-a?question=voice-algebra');
  const source=page.locator('#trainingAnswer');
  await source.fill('x^2');
  await source.focus();
  await source.press('End');
  // The normal keyboard path promotes the expression to its editable math field.
  await source.press('+');
  const root=page.locator('.ProseMirror:visible').first();
  await root.waitFor();
  const math=root.locator('math-field').first();
  await math.waitFor();
  await math.focus(); await math.evaluate(m=>{m.position=m.lastOffset;});
  await math.press('1');
  await hasValue(source,'x^2+1');
  await math.focus(); await math.evaluate(m=>{m.position=m.lastOffset;});
  const before=await source.inputValue(), latex=await math.evaluate(m=>m.value);
  preview='+4'; confirmed='+5';
  await start(math);
  const mirror=root.locator('math-field[aria-hidden="true"]');
  await mirror.waitFor();
  assert.equal(began.context.textbox.before,latex);
  assert.equal(began.context.textbox.selected,'');
  assert.equal(began.context.textbox.after,'');
  assert.ok((await mirror.evaluate(m=>m.value)).includes('4'));
  assert.equal(await source.inputValue(),before);
  preview='+6';
  await page.waitForFunction(m=>m.value.includes('6'),await mirror.elementHandle());
  assert.ok(!(await mirror.evaluate(m=>m.value)).includes('4'));
  await button('取消').click();
  assert.equal(await math.evaluate(m=>m.value),latex);
  assert.equal(await source.inputValue(),before);
  await math.focus(); await math.evaluate(m=>{m.position=m.lastOffset;});
  await start(math); await mirror.waitFor(); await button('结束录音').click();
  await page.waitForFunction(el=>el.value.includes('5'),await source.elementHandle());
  await math.focus(); await math.press('Control+z'); await hasValue(source,before);
  await root.focus(); await root.press('Control+End');
  preview='初稿';confirmed='定稿';
  await start(root);
  await root.getByText('初稿',{exact:true}).waitFor();
  assert.equal(began.context.textbox.before,before);
  assert.equal(await source.inputValue(),before);
  preview='修正文字';
  await root.getByText('修正文字',{exact:true}).waitFor();
  await button('结束录音').click();
  await page.waitForFunction(el=>el.value.endsWith('定稿'),await source.elementHandle());
  await root.focus(); await root.press('Control+z');
  await hasValue(source,before);
  console.log('PASS MathLive atom positions, ProseMirror revisions and one-step undo');
  await page.goto(base+'/#/settings');
  await page.locator('#profileDisplayName').waitFor();
  // Mount the same optional Markdown composer used by portal.js, with its normal formula adapter.
  await page.evaluate(async ()=>{
    const asset=name=>performance.getEntriesByType('resource').find(e=>new URL(e.name).pathname.endsWith('/'+name))?.name;
    const formulaUrl=asset('formula-input.js');
    const chatUrl=new URL('./vendor/chat/chat.js',formulaUrl);
    chatUrl.search=new URL(formulaUrl).search;
    const [{attachFormulaEditing},{attachChatEditor}]=await Promise.all([import(formulaUrl),import(chatUrl.href)]);
    const field=document.createElement('textarea');
    field.id='voice-test-chat';field.value='首尾';
    document.querySelector('#profileDisplayName').after(field);
    attachChatEditor(field,{editor:'合成答疑',hint:'',math:'公式',preview:'预览'},{attachFormula:attachFormulaEditing});
  });
  const chat=page.locator('.cm-content:visible'), chatSource=page.locator('#voice-test-chat');
  await chat.focus(); await chat.press('Home'); await chat.press('ArrowRight');
  preview='中间';confirmed='定稿';
  await start(chat); await chat.getByText('中间',{exact:true}).waitFor();
  assert.deepEqual(began.context.textbox,{before:'首',selected:'',after:'尾'});
  assert.equal(await chatSource.inputValue(),'首尾');
  preview='已改'; await chat.getByText('已改',{exact:true}).waitFor();
  await button('结束录音').click(); await hasValue(chatSource,'首定稿尾');
  await chat.focus(); await chat.press('Control+z'); await hasValue(chatSource,'首尾');
  console.log('PASS CodeMirror inline preview, preserved source and single-step undo');
  assert.ok(audioCount>=5);
  assert.deepEqual(errors,[]);
} finally {await browser.close();}
