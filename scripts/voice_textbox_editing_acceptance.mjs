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
let transcript = '', began;
const errors=[];
page.on('pageerror',e=>errors.push(String(e)));
await page.route(/\/api\/voice-input\/stream(?:\?|$)/, async route => {
  const packet = route.request().postDataJSON();
  if (packet.op === 'open') {
    began = packet;
    assert.equal(began.manual, true);
  }
  const offset = (packet.offset || 0) + Buffer.from(packet.pcm || '', 'base64').length;
  const boundary = packet.op === 'cut' || packet.op === 'finish';
  await route.fulfill({json: boundary ? {offset, text: transcript} : {offset}});
});
async function cut(text) {
  transcript=text;
  await page.waitForTimeout(230);
  await button('转写').click();
}
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
  await start(math); await cut('+4');
  const mirror=root.locator('math-field[aria-hidden="true"]');
  await mirror.waitFor();
  assert.equal(began.context.textbox.before,latex);
  assert.equal(began.context.textbox.selected,'');
  assert.equal(began.context.textbox.after,'');
  assert.ok((await mirror.evaluate(m=>m.value)).includes('4'));
  assert.equal(await source.inputValue(),before);
  await button('取消').click();
  assert.equal(await math.evaluate(m=>m.value),latex);
  assert.equal(await source.inputValue(),before);
  await math.focus(); await math.evaluate(m=>{m.position=m.lastOffset;});
  await start(math); await cut('+5'); await mirror.waitFor();
  transcript=''; await button('结束录音').click();
  await page.waitForFunction(el=>el.value.includes('5'),await source.elementHandle());
  await math.focus(); await math.press('Control+z'); await hasValue(source,before);
  await root.focus(); await root.press('Control+End');
  await start(root); await cut('定稿');
  await root.getByText('定稿',{exact:true}).waitFor();
  assert.equal(began.context.textbox.before,before);
  assert.equal(await source.inputValue(),before);
  transcript=''; await button('结束录音').click();
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
  await start(chat); await cut('定稿'); await chat.getByText('定稿',{exact:true}).waitFor();
  assert.deepEqual(began.context.textbox,{before:'首',selected:'',after:'尾'});
  assert.equal(await chatSource.inputValue(),'首尾');
  transcript=''; await button('结束录音').click(); await hasValue(chatSource,'首定稿尾');
  await chat.focus(); await chat.press('Control+z'); await hasValue(chatSource,'首尾');
  console.log('PASS CodeMirror inline preview, preserved source and single-step undo');
  assert.deepEqual(errors,[]);
} finally {await browser.close();}
