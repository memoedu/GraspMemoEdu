/** One source Topic -> ordered theory sections and a native practice group. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {renderSourceHtml} from './render_mathacademy.mjs';
import {embedSourceImages} from './hyperskill_media.mjs';
import {fileURLToPath} from 'node:url';
import {splitTheory,bankFingerprint} from './hyperskill_sections.mjs';
import {preparePresentation,upstreamOnly} from './hyperskill_presentation.mjs';

export async function prepareTopic(translatedPath, livePath, output) {
if (!output) throw Error('Usage: prepare_hyperskill.mjs translated.json live-source.json output');
const translatedRaw = await fs.readFile(translatedPath);
const liveRaw = await fs.readFile(livePath);
const translated = JSON.parse(translatedRaw), live = JSON.parse(liveRaw);
if (translated.topic.id !== live.topic.id || translated.topic.theory !== live.theory.id)
  throw Error('Theory and practice identities differ');
if(live.practices.some(p=>!upstreamOnly(p) && !p.presentation_source))
  throw Error('Capture complete problem presentations before importing');
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const encode = value => JSON.stringify(value, null, 2) + '\n';
await fs.mkdir(output, {recursive:true});
if ((await fs.readdir(output)).length) throw Error('Output must be empty');
const topicId = `hyperskill-topic-${live.topic.id}`;
const media = await embedSourceImages([translated.step.block.text,...live.practices.map(p=>p.block.text)],{
  directory:path.join(output,'assets'),manifest:path.join(path.dirname(translatedPath),'assets.json'),
  base_url:translated.source_url,
});
const rendered = renderSourceHtml(media.html[0]);
const introductions = splitTheory(media.html[0],topicId).map(({source_html,...section}) =>
  ({...section,html:renderSourceHtml(source_html).html}));
const escape=value=>String(value).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const samples=p=>(p.block.options?.samples||[]).map((sample,i)=>
  `<section><h5>示例 ${i+1}</h5><p>输入</p><pre><code>${escape(sample[0])}</code></pre><p>输出</p><pre><code>${escape(sample[1])}</code></pre></section>`).join('');
const topic = {
  id: topicId, title: translated.topic.title, subject_id:'cs', source_adapter:'hyperskill',
  source_url:translated.source_url, training_mode:'paradigm', topic_format_version:2,
  topic_kind:'introduction',
  hyperskill:{topic_id:live.topic.id,theory_id:live.theory.id},
  introductions, content_order:introductions.map(i=>({kind:'introduction',id:i.id})),
  math_css:rendered.css || '',
  modules:[], memory_chunks:[], memory_points:[], flashcards:[],
};
const practiceGroup = {id:topicId,title:topic.title,questions:[]};
const notes = [], order = [];
for (const [index, p] of live.practices.entries()) {
  if (!Number.isSafeInteger(p.id) || p.id <= 0 || p.topic !== live.topic.id) throw Error('Practice identity differs');
  const id = `hyperskill-step-${p.id}`;
  const source = `https://hyperskill.org/learn/step/${p.id}`;
  const html = renderSourceHtml(media.html[index + 1] + samples(p)).html;
  if (upstreamOnly(p)) {
    const starter = Object.entries(p.block.options?.code_templates || {}).map(([language, code]) =>
      typeof code === 'string' && code.trim() ? `<h5>${escape(language)} 起始代码</h5><pre><code>${escape(code)}</code></pre>` : '').join('');
    const original = `<p><a href="${source}" target="_blank" rel="noopener noreferrer">在 Hyperskill 完成此题</a></p>`;
    notes.push({id, title:p.title, text:p.block.text, html:html + starter + original, source_url:source});
    order.push({type:'introduction',id});
    continue;
  }
  practiceGroup.questions.push({
    id:`hyperskill-step-${p.id}`, title:p.title, question:p.block.text,
    html,
    reference_answer:'', explanation_html:'', answer_type:'external',
    constraints:'由 Hyperskill 判题；选项与答案绑定当前练习实例。',
    source_url:`https://hyperskill.org/learn/step/${p.id}`,
    hyperskill:{...topic.hyperskill,step_id:p.id,type:p.type},
    hyperskill_presentation:await preparePresentation(p.type,p.presentation_source.dataset,
      p.presentation_source.code_options,{directory:path.join(output,'assets')}),
  });
  order.push({type:'question',id});
}
if (notes.length) Object.assign(practiceGroup, {introductions:notes,content_order:order});
topic.content_version=hash(encode(introductions));
if (order.length) {
  topic.practice_group={bank_id:'hyperskill-practice',group_id:topicId};
  topic.content_order.push({kind:'bank_practice',id:topicId});
  topic.content_version=hash(encode({reading:topic.content_version, practice:topic.practice_group}));
}
topic.version = hash(encode(topic));
const units = translated.knowledge_graph.path.map((p,i,rows)=>({
  id:`hyperskill-group-${p.id}`, title:p.title,
  parent_id:i ? `hyperskill-group-${rows[i-1].id}` : null,
  topic_ids:i===rows.length-1 ? [topicId] : [],
}));
const course = {id:'hyperskill',title:'Hyperskill',description:'',
  topics:[{id:topicId,path:`topics/${topicId}.json`,prerequisites:[]}],units};
const bank = {schema:1,id:'hyperskill-practice',title:'Hyperskill',subject_id:'cs',description:'',
  math_css:topic.math_css,groups:[
    ...units.map(({topic_ids,...u})=>({...u,questions:[]})),
    {...practiceGroup,parent_id:units.at(-1)?.id || null},
  ]};
bank.version=bankFingerprint(bank);
const report = {topic_id:topicId,practice_count:order.length,native_practice_count:practiceGroup.questions.length,
  upstream_practice_count:notes.length,introduction_count:introductions.length,memory_chunks:0,
  theory_sha256:hash(translatedRaw),practice_source_sha256:hash(liveRaw),
  source_hierarchy:translated.knowledge_graph.path_text,
  learner_progress_imported:false,answer_keys_invented:false};
if(Object.keys(media.assets).length)report.assets=media.assets;
const files = {
  [`topics/${topicId}.json`]:encode(topic),'catalog.json':encode({courses:[course]}),
  'training-banks/hyperskill-practice.json':encode(bank),
  'report.json':encode(report),
  [`sources/${topicId}.translated.json`]:translatedRaw,
  [`sources/${topicId}.practices.json`]:liveRaw,
};
for (const [name,body] of Object.entries(files)) {
  await fs.mkdir(path.dirname(path.join(output,name)),{recursive:true});
  await fs.writeFile(path.join(output,name),body,{flag:'wx'});
}
const hashes=Object.fromEntries(Object.entries(files).map(([name,body])=>[name,hash(body)]));
for(const name of await fs.readdir(path.join(output,'assets')).catch(()=>[]))
  hashes['assets/'+name]=hash(await fs.readFile(path.join(output,'assets',name)));
await fs.writeFile(path.join(output,'manifest.json'),encode({
  schema:1,adapter:'hyperskill',topic_format_version:2,
  test_materials:{topics:[topicId],banks:[bank.id]},
  files:hashes,
}),{flag:'wx'});
console.log(JSON.stringify({topic_id:topicId,practice_count:report.practice_count,images:Object.keys(media.assets).length}));
return {topic,course,bank,report};
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))
  await prepareTopic(...process.argv.slice(2));
