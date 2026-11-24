const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto').webcrypto;
const script = fs.readFileSync(path.join(__dirname, '../web/sw.js'), 'utf8');
const version = /const ASSET_VERSION = "([a-f0-9]+)";/.exec(script)[1];
const appUrl = 'https://example.test/GraspMemoEdu-Pages/app.js?v=' + version;
const appSource = fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8');
function worker(fetchImpl, caches) {
  const events = {};
  const self = {location:{href:'https://example.test/GraspMemoEdu-Pages/sw.js'},
    addEventListener:(name, fn) => {events[name] = fn;}, skipWaiting:async()=>{}, clients:{claim:async()=>{}}};
  vm.runInNewContext(script, {self, URL, Response, fetch:fetchImpl, caches, crypto, TextEncoder});
  return events;
}
test('offline navigation has a scoped retry and no stale learning data', async () => {
  const events = worker(async()=>{throw new Error('offline');});
  let result;
  events.fetch({request:{method:'GET',mode:'navigate',url:'https://example.test/GraspMemoEdu-Pages/'},respondWith:p=>{result=p;}});
  const response = await result;
  assert.equal(response.status,503);
  assert.equal(response.headers.get('Cache-Control'),'no-store');
  assert.match(await response.text(),/href="https:\/\/example.test\/GraspMemoEdu-Pages\/"/);
  events.fetch({
    request:{method:'GET',mode:'navigate',url:'https://example.test/GraspMemoEdu-Pages/pwa-free-study/install.html'},
    respondWith:p=>{result=p;},
  });
  assert.match(await (await result).text(), /href="https:\/\/example.test\/GraspMemoEdu-Pages\/pwa-free-study\/"/);
});
test('API reads, mutations, foreign scopes and unversioned assets pass untouched', () => {
  const events = worker(()=>{throw new Error('must not intercept');});
  for (const request of [
    {method:'POST',mode:'cors',url:'https://example.test/api/submit'},
    {method:'GET',mode:'cors',url:'https://api.example.test/api/state'},
    {method:'GET',mode:'navigate',url:'https://example.test/other/'},
    {method:'GET',mode:'cors',url:'https://example.test/GraspMemoEdu-Pages/app.js',destination:'script'},
    {method:'GET',mode:'cors',url:appUrl+'&extra=1',destination:'script'},
    {method:'GET',mode:'cors',url:appUrl,destination:'script',cache:'reload'},
    {method:'GET',mode:'cors',url:appUrl,destination:'script',headers:new Headers({Range:'bytes=0-10'})},
    {method:'GET',mode:'cors',url:appUrl,destination:'script',headers:new Headers({Authorization:'private'})}
  ]) events.fetch({request,respondWith:()=>assert.fail('unexpected interception')});
});
test('online navigation preserves the original response', async () => {
  const response = new Response('current page');
  const events = worker(async(request, options)=>{
    assert.equal(options.cache,'no-store','offline navigation must not fall back to HTTP disk cache');
    return response;
  });
  let result;
  events.fetch({request:{method:'GET',mode:'navigate',url:'https://example.test/GraspMemoEdu-Pages/download.html'},respondWith:p=>{result=p;}});
  assert.equal(await result,response);
});

function staticCache() {
  const entries = new Map();
  return {
    entries,
    open: async () => ({
      match: async url => entries.get(url)?.clone(),
      put: async (url, response) => { entries.set(url, response); },
    }),
  };
}

async function requestAsset(events, referrer) {
  let result, storage;
  events.fetch({
    request:{method:'GET',mode:'cors',url:appUrl,destination:'script',referrer,headers:new Headers()},
    respondWith:promise => { result = promise; },
    waitUntil:promise => { storage = promise; },
  });
  const response = await result;
  await storage;
  return response.text();
}

test('three apps reuse the verified static response from one shared cache', async () => {
  const cache = staticCache();
  let reads = 0;
  const events = worker(async (request, options) => {
    assert.equal(options.credentials, 'omit');
    reads++;
    return new Response(appSource);
  }, cache);
  for (const entry of ['', 'pwa-free-study/', 'pwa-math-courses/']) {
    assert.equal(await requestAsset(events, 'https://example.test/GraspMemoEdu-Pages/' + entry), appSource);
  }
  assert.equal(reads, 1);
  assert.equal(cache.entries.size, 1);
});

test('rollout mismatches, errors and private responses never persist', async () => {
  const cache = staticCache();
  const responses = [
    new Response('new bytes on an old URL'),
    new Response('missing', {status:404}),
    new Response(appSource, {headers:{'Cache-Control':'private, no-store'}}),
  ];
  const events = worker(async () => responses.shift(), cache);
  for (let i = 0; i < 3; i++) await requestAsset(events);
  assert.equal(cache.entries.size, 0);
  assert.equal(responses.length, 0);
});

test('unavailable cache does not prevent static resources from loading', async () => {
  const events = worker(async () => new Response(appSource.replace(/\r\n/g, '\n')), {
    open: async () => { throw Error('storage unavailable'); },
  });
  assert.equal(await requestAsset(events), appSource.replace(/\r\n/g, '\n'));
});
