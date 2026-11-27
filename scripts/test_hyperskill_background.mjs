import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {setTimeout as delay} from 'node:timers/promises';
import {deferredSubmissionReader,readSubmission,sshSubmissionReader} from './hyperskill_background.mjs';
import {Bridge} from './hyperskill_bridge.mjs';

const expectedUserId = 7;
const body = {choices:[true,false]};
const row = {id:91,step:10,user_id:7,attempt:40,status:'wrong',time:'2026-11-27T00:00:01Z',reply:body};
let reads = 0;
const get = async route => {
  reads++;
  if (route === '/profiles/current') return {profiles:[{id:7}]};
  assert.match(route,/^\/submissions(?:\/91|\?step=10&page_size=100&order=desc&user=7)$/);
  return {submissions:[row,{...row,user_id:8}],meta:{has_next:false}};
};
await assert.rejects(readSubmission('/attempts', {get,expectedUserId}),/Unsupported/);
assert.equal(reads,0);
await assert.rejects(readSubmission('/submissions/91', {get,expectedUserId:8}),/mismatch/);
assert.equal((await readSubmission('/submissions/91', {get,expectedUserId})).submissions.length,1);

const remote = process.env.HYPERSKILL_TEST_READER ? JSON.parse(process.env.HYPERSKILL_TEST_READER) : null;
const network = remote ? sshSubmissionReader(remote,expectedUserId) :
  (method,route)=>readSubmission(route,{get,expectedUserId});
const unreachable = remote ? sshSubmissionReader({...remote,host:'invalid.invalid'},expectedUserId) :
  async()=>{throw Error('disconnected');};
const directory = await fs.mkdtemp(path.join(os.tmpdir(),'hyperskill-background-'));
try {
  const events = [], stored = new Set();
  const options = {directory, expectedUserId, hyperskill:()=>assert.fail('foreground transport was used'),
    cloud: async (route,_ticket,message) => {
      assert.equal(route,'event');
      const event=message.event;
      events.push(event);
      if (!stored.has(event.id)) {stored.add(event.id);throw Error('ack lost after commit');}
      return {closed:false};
    }};
  const bridge = new Bridge(options);
  const id = 'r'.repeat(38);
  await bridge.save({id,ticket:'fixture',binding:{step_id:10,type:'choice'},sequence:1,last:null,
    attempt:{id:40,dataset:{options:['A','B']}},pending:{request_id:'fixture-request',attempt_id:40,
      value:{reply:body,display:'A',semantic:'A'},before:[],started_at:'2026-11-27T00:00:00Z',
      submission_id:null,posted:true,event:null}});
  await assert.rejects(unreachable('GET','/submissions/91'));
  bridge.backgroundReader=unreachable;
  await bridge.serial(()=>bridge.flush());
  assert.equal((await bridge.load(id)).pending.submission_id,null);
  let resume = ()=>{};
  bridge.backgroundReader=deferredSubmissionReader(network,()=>resume());
  const stale = Date.now()+15000;
  while (!(await bridge.load(id)).pending?.event && Date.now()<stale) {
    const response = new Promise(resolve=>{resume=resolve;});
    await bridge.serial(()=>bridge.flush());
    if (!(await bridge.load(id)).pending?.event) await Promise.race([response,delay(100)]);
  }
  const pending=(await bridge.load(id)).pending;
  assert.equal(pending.event.receipt.submission_id,91);
  assert.equal(events.length,1);
  const restarted = new Bridge({...options,backgroundReader:unreachable});
  await restarted.serial(()=>restarted.flush());
  assert.deepEqual(events.map(event=>event.id),[pending.event.id,pending.event.id]);
  assert.equal(stored.size,1);
  assert.equal((await restarted.load(id)).sequence,2);
  assert.equal((await restarted.load(id)).pending,null);
  console.log(`PASS ${remote?'Windows–Mac SSH':'local'} lookup, disconnected journal, replayed acknowledgement, one stored event`);
} finally {await fs.rm(directory,{recursive:true,force:true});}
