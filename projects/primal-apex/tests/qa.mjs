import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url);
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const {LuaFactory}=require(process.env.PRIMAL_APEX_WASMOON||'../../battle-sim-lua/.qa-web/node_modules/wasmoon');
const jsonSource=await fs.readFile(path.join(root,'../../projects/battle-sim-lua/qa-output/risu-json.lua'),'utf8');
const manifest=JSON.parse(await fs.readFile(path.join(root,'release/manifest.json'),'utf8'));
const names=Object.keys(manifest.modules);
const codes={};
for(const name of names) codes[name]=await fs.readFile(path.join(root,'generated',manifest.modules[name].file.replace('.risum','.lua')),'utf8');
await fs.mkdir(path.join(root,'qa'),{recursive:true});
let saved=new Map(),chats=[{role:'char',data:'Primal Apex'}],inputs=[],alerts=[],llmMode='opening',llmCalls=[],yieldCount=0,stopped=false;
const engines={}; let order=[...names];
const key='__primal_apex_state_v1';
const state=()=>JSON.parse(saved.get(key)||'null');
const put=s=>saved.set(key,JSON.stringify(s));
const original=()=>saved.get(key);
const host=`
json=require 'json'
PRIMAL_APEX_TEST=true
function getState(id,k) return json.decode(getChatVar(id,'__'..k)) end
function setState(id,k,v) setChatVar(id,'__'..k,json.encode(v)) end
function getFullChat(id) return json.decode(chatJSON()) end
local listeners={editDisplay={},editRequest={}}
function listenEdit(kind,fn) table.insert(listeners[kind],fn) end
function async(callback)
 return function(...)
  local co=coroutine.create(callback)
  local safe,result=coroutine.resume(co,...)
  return Promise.create(function(resolve,reject)
   local checkresult
   local step=function()
    if coroutine.status(co)=='dead' then local send=safe and resolve or reject; return send(result) end
    safe,result=coroutine.resume(co); checkresult()
   end
   checkresult=function() if safe and result==Promise.resolve(result) then result:finally(step) else step() end end
   checkresult()
  end)
 end
end
function LLM(id,prompt,multimodal,options) return json.decode(LLMMain(id,json.encode(prompt)):await()) end
callListenMain=async(function(kind,id,value,meta)
 local data=json.decode(value); local m=json.decode(meta)
 for _,fn in ipairs(listeners[kind]) do data=fn(id,data,m) end
 return json.encode(data)
end)
`;
async function open(name){
 engines[name]?.global.close();
 const factory=new LuaFactory();await factory.mountFile('json.lua',jsonSource);
 const lua=await factory.createEngine({injectObjects:true}); engines[name]=lua;
 lua.global.set('getChatVar',(_id,k)=>saved.get(k)??'null');
 lua.global.set('setChatVar',(_id,k,v)=>{JSON.parse(v);saved.set(k,v)});
 lua.global.set('getChatLength',()=>chats.length);
 lua.global.set('chatJSON',()=>JSON.stringify(chats));
 lua.global.set('addChat',(_id,role,data)=>chats.push({role,data}));
 lua.global.set('removeChat',(_id,i)=>chats.splice(i,1));
 lua.global.set('reloadDisplay',()=>{});
 lua.global.set('stopChat',()=>{stopped=true});
 lua.global.set('alertNormal',(_id,msg)=>alerts.push(msg));
 lua.global.set('alertInput',async()=>inputs.shift()??null);
 lua.global.set('log',msg=>{throw new Error(String(msg))});
 lua.global.set('sleep',async()=>{yieldCount++;return true});
 lua.global.set('LLMMain',async(_id,raw)=>{
   const prompt=JSON.parse(raw);llmCalls.push(prompt);
   if(llmMode==='fail') return JSON.stringify({success:false,result:'test outage'});
   return JSON.stringify({success:true,result:llmMode==='finish'?packet(state().session,{reward:'TRAINING_SMALL',lead:'REMATCH_PROMISE'}):'선수가 당신을 바라보며 말을 건넨다. 어떤 이야기를 나누고 싶은가?'});
 });
 await lua.doString(host+codes[name]);
}
async function invoke(name,event,...args){
 const lua=engines[name];
 const fn=lua.global.get(event);if(fn)return await fn(...args);
}
async function rawButton(code){for(const name of order) await invoke(name,'onButtonClick','qa',code)}
async function click(owner,action,value='') {await rawButton(`pa;${owner};${state()?.revision??0};${action};${value}`)}
async function edit(kind,data,index=chats.length-1){
 for(const name of order) data=JSON.parse(await invoke(name,'callListenMain',kind,'qa',JSON.stringify(data),JSON.stringify({index})));
 return data;
}
async function render(){return edit('editDisplay',chats.at(-1)?.data??'Primal Apex')}
async function output(text){chats.push({role:'char',data:text});for(const name of order) await invoke(name,'onOutput','qa')}
async function start(text){chats.push({role:'user',data:text});for(const name of order) await invoke(name,'onStart','qa')}
function packet(q,fields={}){
 const at=fields.at??q.startedAt+30;
 const f={scene:q.id,end_day:String(Math.floor(at/1440)+1),end_time:`${String(Math.floor(at%1440/60)).padStart(2,'0')}:${String(at%60).padStart(2,'0')}`,affinity:'UP_SMALL',respect:'NONE',reward:'NONE',lead:'NONE',...fields}; delete f.at;
 return '<PA_SUMMARY>선수와 훈련과 재대결을 이야기했다.</PA_SUMMARY>\n<STORY_END|'+Object.entries(f).map(([k,v])=>`${k}=${v}`).join('|')+'>';
}
function onePanel(html,name){const panels=[...html.matchAll(/data-pa-module="([a-z]+)"/g)].map(x=>x[1]);assert.deepEqual(panels,[name])}
const fixtures={},report={};
async function fixture(name,module){const html=await render();onePanel(html,module);fixtures[name]=html;return html}
function permutations(xs){return xs.length?xs.flatMap((x,i)=>permutations(xs.filter((_,j)=>j!==i)).map(t=>[x,...t])):[[]]}
try{
 for(const name of names) {console.log('Loading',name);await open(name);}
 console.log('Testing module activation orders');
 for(const seq of permutations(names)){
  order=seq;saved=new Map();
  onePanel(await render(),'hub');assert.equal(state(),null,'render must not write');
  await click('hub','open','matchmaking');onePanel(await render(),'matchmaking');assert.equal(state().revision,1);
  await click('matchmaking','back');onePanel(await render(),'hub');
 }
 report.moduleOrderPermutations=24;order=[...names];saved=new Map();console.log('Testing campaign');
 await fixture('hub','hub');
 await click('hub','open','training');await fixture('training','training');
 const beforeTime=state().calendar.now;const token=`pa;training;${state().revision};upgrade;measured_strike`;
 await rawButton(token);assert.equal(state().player.trainingPoints,1);assert.equal(state().player.skills.find(x=>x.id==='measured_strike').level,2);assert.equal(state().calendar.now,beforeTime);
 const trained=original();await rawButton(token);assert.equal(original(),trained);
 await click('training','upgrade','measured_strike');assert.equal(original(),trained,'insufficient resources');
 await click('training','back');await click('hub','open','story');await fixture('map','story');
 llmMode='fail';await click('story','begin','rookie_cycle:CHALLENGE');assert.equal(state().session.kind,'story');assert.ok(state().notice.includes('실패'));
 await fixture('story-failure','story');
 llmMode='opening';await click('story','retry');await fixture('story','story');
 const q=state().session;assert.equal(state().calendar.now,q.startedAt);
 const request=await edit('editRequest',[{role:'user',content:'대전 이야기를 나눈다.'}]);assert.ok(request.at(-1).content.includes(q.id));assert.ok(request.at(-1).content.includes('REMATCH_PROMISE'));
 const valid=packet(q,{reward:'TRAINING_SMALL',lead:'REMATCH_PROMISE'});
 const before=original();
 for(const bad of [valid.replace('UP_SMALL','999'),valid.replace('scene='+q.id,'scene=old'),valid.replace('|reward=', '|reward=NONE|reward='),valid.replace('>','>')+'\n'+valid,valid.replace('|lead=', '|unknown=X|lead='),packet(q,{at:q.startedAt-1}),valid.replace('|respect=NONE','')]){
  await output(bad);assert.equal(original(),before,'bad packet changed state');
 }
 await output(valid);assert.equal(state().screen,'hub');assert.equal(state().calendar.now,q.startedAt+30);assert.equal(state().player.trainingPoints,2);assert.equal(state().story.matchLeads.rookie_cycle.kind,'REMATCH_PROMISE');
 const after=original();await output(valid);assert.equal(original(),after);assert.ok(!(await render()).includes('<STORY_END'));
 await click('hub','open','matchmaking');await fixture('matchmaking','matchmaking');await click('matchmaking','draw');
 assert.equal(state().schedule[0].opponentId,'rookie_cycle');const fixed=original();await click('matchmaking','draw');assert.equal(original(),fixed);await fixture('scheduled','matchmaking');
 await click('matchmaking','back');await click('hub','open','story');await click('story','begin','rookie_cycle:TALK');
 const deadline=state().session.deadline;const current=original();await output(packet(state().session,{at:deadline+1}));assert.equal(original(),current);
 await output(packet(state().session,{at:deadline}));assert.equal(state().calendar.now,deadline);
 const due=original();await click('hub','open','training');assert.equal(original(),due);await click('hub','open','story');assert.equal(original(),due);await fixture('due','hub');
 await click('hub','start_battle');await fixture('prep','hub');
 assert.equal(state().session.input.opponent.strategy,'rookie_cycle');
 assert.equal(state().session.config.playerDeck.find(x=>x.id==='measured_strike').level,2);
 await click('hub','equip','measured_strike');await click('hub','equip','measured_strike');
 const pre=state();await click('hub','lock');assert.equal(state().screen,'entrance');assert.equal(state().session.entranceReady,true);await fixture('entrance','hub');
 await click('hub','enter');assert.equal(state().session.battle.player.skills.find(x=>x.id==='measured_strike').level,2);await fixture('battle','hub');
 assert.equal(saved.has('__battle_sim_state_v1'),false,'standalone BattleSim storage must remain untouched');
 const reload=original();for(const name of names)await open(name);assert.equal(original(),reload);onePanel(await render(),'hub');
 let turns=0;
 while(!state().session.battle.outcome || state().session.battle.presentation){
  const html=await render();
  const button=[...html.matchAll(/risu-btn="([^"]+)"/g)].map(x=>x[1]).find(x=>x.includes(';battle;bs;continue;')||x.includes(';battle;bs;execute;'));
  assert.ok(button,'no battle continuation');const turn=state().session.battle.matchTurn;
  await rawButton(button);const snap=original();await rawButton(button);assert.equal(original(),snap,'double battle click');
  if(state().session.battle.matchTurn>turn)turns++;
  assert.ok(turns<805,'battle bounded by original 100-round cap');
 }
 await fixture('battle-result','hub');
 const outcome=state().session.battle.outcome;await click('hub','settle');assert.equal(state().session,false);assert.equal(state().matchHistory.length,1);assert.equal(state().schedule[0].status,'completed');assert.equal(state().story.afterBattle.outcome,outcome);
 await click('hub','open','story');await fixture('after-battle','story');await click('story','begin','rookie_cycle:AFTER_BATTLE');
 llmMode='finish';await click('story','finish');assert.equal(state().session,false);assert.equal(state().story.afterBattle,false);assert.equal(state().matchHistory.length,1);
 report.firstCampaign={turns,outcome,battleSkillLevel:2,afterBattle:true};
 // Calendar input and a second match prove the loop can repeat.
 llmMode='opening';await click('hub','open','matchmaking');await click('matchmaking','draw');await click('matchmaking','back');await click('hub','open','calendar');await fixture('calendar','hub');
 inputs.push('1 00:00');const clock=original();await click('hub','time');assert.equal(original(),clock);
 inputs.push('9999 23:59');await click('hub','time');assert.equal(state().calendar.now,state().schedule[1].at);assert.equal(state().screen,'hub');
 await click('hub','start_battle');assert.notEqual(state().session.matchId,state().matchHistory[0].matchId);
 // Genuine NG+ processing through the same adapter (bounded 3-turn search).
 const ng=state();ng.session.config.aiMode='ng_plus';ng.session.input.opponent.aiMode='ng_plus';put(ng);
 llmMode='fail';await click('hub','lock');assert.equal(state().session.entranceReady,false);await click('hub','entry_skip');
 const html=await render();const execute=[...html.matchAll(/risu-btn="([^"]+)"/g)].map(x=>x[1]).find(x=>x.includes(';battle;bs;execute;'));await rawButton(execute);
 assert.equal(state().session.battle.matchTurn,1);assert.ok(state().session.battle.lastNg.transitions>0);report.ngPlus={...state().session.battle.lastNg,yields:yieldCount};
 // Independent save, fixed cup; no reroll or tournament overwrite.
 saved=new Map();llmMode='opening';await click('hub','open','matchmaking');await click('matchmaking','cup');assert.equal(state().schedule.length,3);assert.equal(state().scenario.mode,'tournament');const cup=original();await click('matchmaking','cup');assert.equal(original(),cup);await fixture('cup','matchmaking');
 // Explicit end command uses normal request pipeline; plain chat untouched.
 await click('matchmaking','back');await click('hub','open','story');await click('story','begin','veteran_guard:TALK');
 stopped=false;await start('안녕하세요');assert.equal(stopped,false);await start('/story end');assert.equal(state().session.closing,true);
 assert.ok((await edit('editRequest',[])).at(-1).content.includes('사용자가 서사 종료를 요청'));
 const cancellation=state().calendar.now;inputs.push('종료');await click('story','cancel');assert.equal(state().calendar.now,cancellation);assert.equal(state().session,false);
 stopped=false;await start('/apex');assert.ok(stopped);assert.equal(state().screen,'hub');
 const text='역사 메시지';assert.equal(await edit('editDisplay',text,0),text);
 const v=state();v.version=999;put(v);const broken=original();await rawButton('pa;hub;0;open;training');await render();assert.equal(original(),broken);
 report.contracts={sharedStorage:true,isolatedLuaEngines:true,independentHookOwners:true,readOnlyDisplay:true,staleButtons:true,packetValidation:true,duplicateSettlements:true,sceneTimeBounds:true,zeroTimeTraining:true,calendarClamp:true,fixedCup:true,modelFailureRecovery:true,saveReload:true,unknownVersionPreserved:true};
 report.llm={mocked:true,calls:llmCalls.length,liveModelTested:false};
 if(process.env.PA_BROWSER==='1'){
  console.log('Testing sanitized browser layouts and real DOM button transitions');
  const deps=path.join(process.env.USERPROFILE,'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
  const {chromium}=require(require.resolve('playwright',{paths:[deps]}));
  const md=require('../../last-bell/tests/vendor/markdown-it.cjs')({html:true,breaks:true}).disable(['code']);
  const browser=await chromium.launch({headless:true,channel:'msedge'});
  try{
   const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
   const css=await fs.readFile(path.join(root,'generated/Primal-Apex-Hub.css'),'utf8');
   const silhouette='data:image/svg+xml;base64,'+Buffer.from('<svg xmlns="http://www.w3.org/2000/svg" width="800" height="500"><rect width="800" height="500" fill="#190708"/><path d="M180 500V310Q180 240 300 225Q215 150 260 65Q330 0 390 80Q430 170 350 220Q490 240 490 330V500" fill="#5b3732"/></svg>').toString('base64');
   await page.setContent('<!doctype html><html lang="ko"><meta charset="UTF-8"><style>body{background:#101016;margin:0;padding:8px}</style>'+css+'<main id="host"></main></html>');
   await page.addScriptTag({path:path.join(root,'../last-bell/tests/vendor/purify.js')});
   await page.evaluate(()=>DOMPurify.addHook('uponSanitizeAttribute',(_node,data)=>{if(data.attrName==='class')data.attrValue=data.attrValue.split(' ').map(c=>c.startsWith('x-risu-')?c:'x-risu-'+c).join(' ')}));
   const mount=async html=>page.evaluate(({html})=>{document.querySelector('#host').innerHTML=DOMPurify.sanitize(html,{ADD_ATTR:['risu-btn']})},{html:md.render(html).replace(/\{\{raw::[^}]+\}\}/g,silhouette)});
   report.layouts=[];
   for(const width of [1100,390,320]){
    await page.setViewportSize({width,height:1000});
    for(const [name,html] of Object.entries(fixtures)){
     await mount(html);
     const audit=await page.evaluate(()=>({panels:document.querySelectorAll('[data-pa-module]').length,overflow:document.documentElement.scrollWidth>innerWidth,styled:getComputedStyle(document.querySelector('.x-risu-pa-panel')).backgroundColor==='rgb(25, 25, 31)',buttons:document.querySelectorAll('[risu-btn]').length}));
     assert.equal(audit.panels,1);assert.ok(!audit.overflow,`${name} overflow at ${width}`);assert.ok(audit.styled,`${name} CSS not applied`);assert.ok(audit.buttons>0);
     report.layouts.push({name,width,...audit});
     if(width!==320)await page.screenshot({path:path.join(root,`qa/${name}-${width}.png`),fullPage:true});
    }
   }
   saved=new Map();chats=[{role:'char',data:'Primal Apex'}];llmMode='opening';
   await page.setViewportSize({width:900,height:1000});await mount(await render());
   await page.exposeFunction('hostButton',async code=>{await rawButton(code);return md.render(await render())});
   await page.evaluate(()=>document.addEventListener('click',async e=>{const b=e.target.closest('[risu-btn]');if(!b||b.disabled)return;document.querySelector('#host').innerHTML=DOMPurify.sanitize(await window.hostButton(b.getAttribute('risu-btn')),{ADD_ATTR:['risu-btn']})}));
   for(const name of ['matchmaking','training','story']){
    await page.locator(`[risu-btn$="open;${name}"]`).click();await page.locator(`[data-pa-module="${name}"]`).waitFor();
    assert.equal(await page.locator('[data-pa-module="hub"]').count(),0);
    await page.locator('[risu-btn$="back;"]').click();await page.locator('[data-pa-module="hub"]').waitFor();
   }
   report.domClickFlow=true;assert.deepEqual(errors,[]);report.browserErrors=errors;
  }finally{await browser.close()}
 }
 for(const [name,html]of Object.entries(fixtures))await fs.writeFile(path.join(root,'qa',name+'.html'),html);
 await fs.writeFile(path.join(root,'qa/results.json'),JSON.stringify(report,null,2));
 console.log(JSON.stringify(report,null,2));
}finally{for(const lua of Object.values(engines))lua.global.close()}
