// Real Lua renderer + RisuAI sanitizer/class scoping + Chromium/WebView2 engine.
// Run: node qa_ui.mjs. No writes to the user's app or saves.
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url), root=path.dirname(fileURLToPath(import.meta.url));
const deps=process.env.USERPROFILE+'/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
const {chromium}=require(require.resolve('playwright',{paths:[deps]}));
const {LuaFactory}=require('./.qa-web/node_modules/wasmoon');
const lua=await new LuaFactory().createEngine();
// Wasmoon 1.16 leaves returned values on its global stack. Balance every call
// so repeated HTML snapshots cannot exhaust the C API stack in this harness.
async function runLua(source){const top=lua.global.getTop();try{return await lua.doString(source)}finally{lua.global.setTop(top)}}
const browser=await chromium.launch({headless:true,channel:'msedge'});
const output=path.join(root,'qa-output'); await fs.mkdir(output,{recursive:true});
const report={viewports:[],rules:0,timelineSamples:0,errors:[]};
try {
 await runLua(`BATTLE_SIM_TEST=true; SAVED={}; function listenEdit(...) end; function getState(id,k) return SAVED[k] end; function setState(id,k,v) SAVED[k]=v end`);
 await runLua((await fs.readFile(path.join(root,'BattleSim.lua'),'utf8')).replace('if BATTLE_SIM_TEST then return B end','if BATTLE_SIM_TEST then BATTLE=B; return B end'));
 await runLua(`
 B=BATTLE
 -- Icons are shared UI assets and must never replace a cinematic portrait.
 for _,case in ipairs({{'attack','m01'},{'defend','m02'},{'evade','m04'}}) do
   local c=B.defaultConfig(); c.screen='battle'; c.skillPhotos=true
   c.characterKeys={player='hero',enemy='rival'}
   c.playerDeck={{id=case[2],level=1}}; c.enemyDeck=B.copy(c.playerDeck)
   local s=B.newState(c,713)
   assert(B.step(s,{player={action=case[1],skill=case[2]},enemy={action=case[1],skill=case[2]}},{6,1},false))
   local html=B.render(s,c)
   local _,icons=html:gsub('class="bsim%-dice%-skill%-icon"',''); assert(icons==2)
   s.skillPhotos=false; assert(not B.render(s,c):find('bsim-dice-skill-icon',1,true)); s.skillPhotos=true
   assert(html:find('{{raw::skill_'..case[2]..'.png}}',1,true))
   for _,key in ipairs({'hero','rival'}) do
     assert(html:find('data-asset="'..key..'_action_'..case[1]..'.png"',1,true))
     assert(not html:find(key..'_skill_',1,true))
   end
   for asset in html:gmatch('data-asset="([^"]+)"') do assert(not asset:find('skill_',1,true)) end
 end
 function fixture(kind)
   C=B.defaultConfig(); C.screen='battle'; C.aiMode='ng_plus'; C.playerDeck={{id='m01',level=1},{id='m02',level=1},{id='m03',level=1},{id='m08',level=1},{id='m10',level=1}}; C.enemyDeck=B.copy(C.playerDeck)
   S=B.newState(C,713); S.selectedAction='attack'; S.selectedSkill='m01'
   if kind=='setup' or kind=='developer' then C.screen='setup'; C.tab=kind=='developer' and 'developer' or 'skills'
   elseif kind=='loaded' then
     for i=1,40 do S.log[i]='T'..i..' · 묵직한 한 방 / HP −28 · STA −16 · BRK +22' end
     S.player.statuses={{name='preparation',displayName='힘 모으기',remainingTurns=2},{name='guard',displayName='단단한 가드',remainingTurns=1}}
     S.notice='선택한 행동의 조건을 확인하세요.'
   elseif kind~='live' then
     S.skillPhotos=true
     if kind=='down' or kind=='ko' then S.enemy.hp=10; S.enemy.downCount=kind=='ko' and 2 or 0 end
     if kind=='interval' then S.turnInRound=7 end
     if kind=='wake' or kind=='down_wait' then S.player.isDown=true; S.player.hp=0; S.player.downCount=1; S.player.skippedTurnsRemaining=kind=='wake' and 1 or 2 end
     if kind=='groggy' then S.enemy.isGroggy=true end
     if kind=='both_groggy' then S.player.isGroggy=true; S.enemy.isGroggy=true end
     assert(B.step(S,{player={action='attack',skill='m01'},enemy={action='attack'}},{6,1},false))
     if kind=='interval' then S.presentation=S.pendingInterval; S.pendingInterval=false; S.displayActors=nil end
     S.fast=kind=='fast'
   end
   SAVED.battle_sim_state_v1=S; SAVED.battle_sim_config_v2=C
   return B.render(S,C)
 end
 local count=0
 for _,r in ipairs(B.ruleRows()) do
   local c=B.defaultConfig(); local s=B.newState(c,10)
   for _,side in ipairs({'player','enemy'}) do s[side].hp=60; s[side].stamina=60; s[side].breakGauge=40 end
   if r.opponent=='groggy' then s.enemy.isGroggy=true end
   local dice=r.dice=='win' and {6,1} or (r.dice=='lose' and {1,6} or {3,3})
   assert(B.step(s,{player={action=r.action},enemy={action=r.opponent=='groggy' and 'attack' or r.opponent}},dice,false))
   assert(s.presentation.entryId==r.value.id)
   for _,side in ipairs({'player','enemy'}) do for _,k in ipairs({'hp','stamina','breakGauge'}) do
     assert(s.presentation[side..'Effect'][k]==r.value[side][k],r.value.id..side..k)
   end end
   count=count+1
 end
 assert(count==30)
 local function grouped(paths,expected)
   local out={};for _,g in ipairs(B.mergePortraitStages(paths)) do out[#out+1]=g.path..':'..g.first..'-'..g.last end
   assert(table.concat(out,',')==expected)
 end
 grouped({'A','B','C','C','C'},'A:1-1,B:2-2,C:3-5')
 grouped({'A','A','B','B','C'},'A:1-2,B:3-4,C:5-5')
 grouped({'A','A','A','A','A'},'A:1-5')
 grouped({'A','B','A','B','A'},'A:1-1,B:2-2,A:3-3,B:4-4,A:5-5')
 `);
 report.rules=30;
 const css=(await fs.readFile(path.join(root,'BattleSim.css'),'utf8')).replace(/<\/?style>/g,'').replace(/\.(bsim-[\w-]+|is-[\w-]+)/g,'.x-risu-$1');
 const page=await browser.newPage({viewport:{width:1366,height:768}});
 page.on('pageerror',e=>report.errors.push(e.message));
 page.on('console',m=>{if(m.type()==='error')report.errors.push(m.text())});
 await page.setContent('<!doctype html><meta charset="utf-8"><style>body{margin:0;padding:16px;background:#080709}.chattext{max-width:1180px;margin:auto}</style><style>'+css+'</style><main class="chattext" id="host"></main>');
 await page.addScriptTag({path:path.join(output,'purify.js')});
 await page.evaluate(()=>DOMPurify.addHook('uponSanitizeAttribute',(_node,data)=>{if(data.attrName==='class')data.attrValue=data.attrValue.split(' ').map(c=>c.startsWith('x-risu-')?c:'x-risu-'+c).join(' ')}));
 // Only the harness resolves {{raw::...}}. Production still uses RisuAI assets.
 const placeholder='data:image/svg+xml;base64,'+Buffer.from('<svg xmlns="http://www.w3.org/2000/svg" width="800" height="500"><rect width="800" height="500" fill="#190708"/><path d="M180 500V310Q180 240 300 225Q215 150 260 65Q330 0 390 80Q430 170 350 220Q490 240 490 330V500" fill="#5b3732"/></svg>').toString('base64');
 async function mount(html){await page.evaluate(({html,placeholder})=>{document.querySelector('#host').innerHTML=DOMPurify.sanitize(html.replace(/\{\{raw::[^}]+\}\}/g,placeholder),{ADD_ATTR:['risu-btn']})},{html,placeholder})}
 async function fixture(kind){lua.global.set('KIND',kind);await mount(await runLua('return fixture(KIND)'))}
 await page.exposeFunction('hostButton',async code=>{lua.global.set('CODE',code);await runLua(`B.handle('qa',CODE)`);return await runLua('return B.render(S,C)')});
 await page.evaluate(placeholder=>document.addEventListener('click',async e=>{const b=e.target.closest('[risu-btn]');if(b){const html=await window.hostButton(b.getAttribute('risu-btn'));document.querySelector('#host').innerHTML=DOMPurify.sanitize(html.replace(/\{\{raw::[^}]+\}\}/g,placeholder),{ADD_ATTR:['risu-btn']})}}),placeholder);
 const q=s=>page.locator(s.replace(/\.(bsim-|is-)/g,'.x-risu-$1'));
 await fixture('resolution');
 // Host chat styles can give images a prose margin; framed images reset it.
 await page.addStyleTag({content:'img{margin-top:20px}'});
 const framedImages='.bsim-portrait,.bsim-cinematic-image,.bsim-skill-thumbnail,.bsim-skill-photo,.bsim-dice-skill-icon';
 assert((await q(framedImages).evaluateAll(es=>es.map(e=>getComputedStyle(e).marginTop))).every(v=>v==='0px'));
 await q('.bsim-dice-badge').evaluateAll(es=>es.forEach(e=>e.getAnimations({subtree:true}).forEach(a=>{a.pause();a.currentTime=800})));
 assert.equal(await q('.bsim-dice-skill-icon').count(),1);
 assert.equal(await q('.bsim-dice-skill-icon').evaluate(e=>getComputedStyle(e).opacity),'1');
 const iconBox=await q('.bsim-dice-skill-icon').boundingBox();
 const dieBox=await q('.bsim-unit-player .bsim-die').boundingBox();
 assert.equal(iconBox.width,44);assert.equal(iconBox.height,44);
 assert(iconBox.y>=dieBox.y+dieBox.height,'skill icon below die');
 await page.screenshot({path:path.join(output,'dice-skill-icon.png')});
 for(const viewport of [{width:1920,height:1080},{width:1440,height:900},{width:1366,height:768},{width:1280,height:720},{width:1024,height:768}]){
   await page.setViewportSize(viewport); await fixture('live');
   const layout=await page.evaluate(()=>{
     const units=[...document.querySelectorAll('.x-risu-bsim-unit')].map(el=>el.getBoundingClientRect().toJSON());
     const frames=[...document.querySelectorAll('.x-risu-bsim-portrait-frame')].map(el=>el.getBoundingClientRect().toJSON());
     const heads=[...document.querySelectorAll('.x-risu-bsim-unit-head')].map(el=>el.getBoundingClientRect().toJSON());
     return {height:document.documentElement.scrollHeight,width:document.documentElement.scrollWidth,units,frames,heads};
   });
   if(layout.height>viewport.height){await page.screenshot({path:path.join(output,'ui-overflow.png'),fullPage:true});console.log(await q('.bsim-controls').evaluate(e=>[...e.querySelectorAll('*')].map(x=>[x.className,x.getBoundingClientRect().height,getComputedStyle(x).margin,getComputedStyle(x).padding])))}
   assert(layout.height<=viewport.height,JSON.stringify({viewport,layout}));assert(layout.width<=viewport.width);
   assert.equal(layout.units[0].y,layout.units[1].y);assert.equal(layout.frames[0].width,layout.frames[1].width);assert(layout.heads[0].y>=layout.frames[0].bottom);
   report.viewports.push({...viewport,documentHeight:layout.height});
   await fixture('loaded');assert(await page.evaluate(()=>document.documentElement.scrollHeight<=innerHeight),'loaded state overflow '+JSON.stringify(viewport));
   await mount(await runLua('S.skillPhotos=true;return B.render(S,C)'));
   assert.equal(await q('.bsim-skill-name img').count(),10);
   assert(await page.evaluate(()=>document.documentElement.scrollHeight<=innerHeight),'image loadout overflow '+JSON.stringify(viewport));
 }
 assert.equal(await q('.bsim-skill-detail').count(),0);assert.equal(await q('.bsim-skill-choice').count(),5);assert.equal(await q('.bsim-meter').count(),6);
 await page.setViewportSize({width:1366,height:768});await fixture('live');
 await page.screenshot({path:path.join(output,'ui-battle.png'),fullPage:true});
 // All skill metadata belongs to the same button, including its click target.
 assert.equal(await q('button.bsim-skill-choice small').count(),5);
 const cardBounds=await q('button.bsim-skill-choice').evaluateAll(cards=>cards.every(b=>[...b.children].every(c=>{const r=b.getBoundingClientRect(),s=c.getBoundingClientRect();return s.left>=r.left&&s.right<=r.right&&s.top>=r.top&&s.bottom<=r.bottom})));
 assert(cardBounds,'metadata escaped the skill card');
 await q('.bsim-skill-choice').filter({hasText:'단단한 가드'}).locator('small').click();
 await q('.bsim-execute button:disabled').waitFor();assert.equal(await q('.bsim-execute button').innerText(),'행동 조건 불일치');assert.equal(await q('.bsim-execute').locator('p').count(),0);
 await page.screenshot({path:path.join(output,'ui-invalid-skill.png'),fullPage:true});
 await fixture('live');
 const invokers=q('.bsim-skill-name'); const before=await q('.bsim-controls').boundingBox();
 const ax=await page.context().newCDPSession(page);
 async function expanded(index){const id=await invokers.nth(index).getAttribute('popovertarget');const {root:doc}=await ax.send('DOM.getDocument');const {nodeId}=await ax.send('DOM.querySelector',{nodeId:doc.nodeId,selector:`button[popovertarget="${id}"]`});const {nodes}=await ax.send('Accessibility.getPartialAXTree',{nodeId,fetchRelatives:false});return nodes[0].properties.find(p=>p.name==='expanded')?.value.value}
 assert.equal(await expanded(0),false);
 await invokers.nth(0).click(); assert.equal(await expanded(0),true);assert.equal(await q('.bsim-skill-popover:popover-open').count(),1);
 assert.deepEqual(await q('.bsim-controls').boundingBox(),before);
 await invokers.nth(0).click();assert.equal(await expanded(0),false);
 await invokers.nth(0).click();await invokers.nth(5).click();assert.equal(await q('.bsim-skill-popover:popover-open').count(),1);assert.match(await q('.bsim-skill-popover:popover-open').innerText(),/상대 장착/);
 await page.screenshot({path:path.join(output,'ui-skill-overlay.png'),fullPage:true});
 await page.keyboard.press('Escape');assert.equal(await q('.bsim-skill-popover:popover-open').count(),0);
 await invokers.nth(0).focus();await page.keyboard.press('Enter');assert.equal(await expanded(0),true);await page.mouse.click(10,10);assert.equal(await expanded(0),false);
 await invokers.nth(5).focus();await page.keyboard.press('Space');assert.equal(await expanded(5),true);await page.keyboard.press('Escape');
 // Changing the existing photo setting also updates the active match on return.
 await runLua(`B.handle('qa','bs;setup');B.handle('qa','bs;photos');B.handle('qa','bs;back');assert(S.skillPhotos and C.skillPhotos)`);
 await mount(await runLua('return B.render(S,C)'));
 assert.equal(await q('.bsim-skill-name img').count(),10);assert.equal(await invokers.nth(0).innerText(),'');
 await invokers.nth(0).focus();await page.keyboard.press('Enter');assert.equal(await expanded(0),true);
 await page.screenshot({path:path.join(output,'ui-image-skills.png'),fullPage:true});
 await invokers.nth(0).click();assert.equal(await expanded(0),false);
 await invokers.nth(5).click();await page.keyboard.press('Escape');await fixture('live');
 const staticText=await q('.bsim-skill-popover').allTextContents();
 await mount(await runLua(`S.player.hp=13; S.enemy.hp=17; S.player.stamina=41; S.enemy.breakGauge=37; for _,o in ipairs(S.enemy.skills) do S.enemy.cooldowns[o.id]=987;S.enemy.uses[o.id]=654 end;return B.render(S,C)`));
 assert.deepEqual(await q('.bsim-skill-popover').allTextContents(),staticText);
 assert(!(await q('.bsim-battle').innerText()).includes('987'));await fixture('live');
 const fingerprint=await runLua(`return S.matchTurn..':'..S.battleRng.state..':'..S.selectedAction..':'..S.selectedSkill`);
 await q('.bsim-rules-button').click();assert.equal(await q('.bsim-rules:popover-open tbody tr').count(),30);
 const expectedRows=await runLua(`local rows={};for _,r in ipairs(B.ruleRows()) do local cells={r.value.id};for _,k in ipairs({'hp','stamina','breakGauge'}) do cells[#cells+1]=r.value.player[k]..','..r.value.enemy[k] end;rows[#rows+1]=table.concat(cells,';') end;return table.concat(rows,'|')`);
 const actualRows=await q('.bsim-rules tbody tr').evaluateAll(rows=>rows.map(r=>[r.dataset.rule,...[...r.cells].slice(4).map(c=>c.textContent.replaceAll('−','-').replaceAll('+','').replace(/\s/g,'').replace('/',','))].join(';')).join('|'));
 assert.equal(actualRows,expectedRows);
 const headerBefore=await q('.bsim-rules .bsim-header').boundingBox();await q('.bsim-table-scroll').evaluate(e=>e.scrollTop=e.scrollHeight);assert.deepEqual(await q('.bsim-rules .bsim-header').boundingBox(),headerBefore);
 await page.screenshot({path:path.join(output,'ui-rules.png'),fullPage:true});
 await q('.bsim-rules button').click();assert.equal(await q('.bsim-rules:popover-open').count(),0);
 assert.equal(await runLua(`return S.matchTurn..':'..S.battleRng.state..':'..S.selectedAction..':'..S.selectedSkill`),fingerprint);
 // Each animation is paused and sampled at 1ms resolution, including every
 // fade boundary. This detects translucent standing/animation overlap too.
 for(const kind of ['resolution','down','ko','interval','wake','down_wait','groggy','both_groggy','fast']){
   await fixture(kind);
   const result=await page.evaluate(()=>{
     const frames=[...document.querySelectorAll('.x-risu-bsim-transition')];
     const animations=frames.flatMap(f=>f.getAnimations({subtree:true}));animations.forEach(a=>a.pause());
     const visible=e=>{const c=getComputedStyle(e);return c.visibility==='visible'&&+c.opacity>0};
     let holds=0;const starts=[240,1900,2900,3800,4600],ends=[1900,2900,3800,4600,5200];
     for(const f of frames){const movies=[...f.querySelectorAll('.x-risu-bsim-cinematic-image')];for(let i=1;i<movies.length;i++){if(movies[i].dataset.asset===movies[i-1].dataset.asset)return {error:'adjacent duplicate DOM'}}}
     for(let t=0;t<=5501;t++){
       animations.forEach(a=>a.currentTime=t);
       for(const f of frames){const standing=[...f.querySelectorAll('.x-risu-bsim-portrait')].some(visible);const movies=[...f.querySelectorAll('.x-risu-bsim-cinematic-image')].some(visible);if(standing&&movies)return {error:'overlap',t};}
       if(!document.querySelector('.x-risu-bsim-fast'))for(const img of document.querySelectorAll('.x-risu-bsim-cinematic-image')){
         const first=+img.dataset.phaseStart,last=+img.dataset.phaseEnd;
         const enter=img.classList.contains('x-risu-bsim-held-start')?0:starts[first-1]+200;
         const exit=img.classList.contains('x-risu-bsim-held-end')?5500:ends[last-1]-200;
         if(t>=enter&&t<exit){const c=getComputedStyle(img);if(+c.opacity!==1||c.visibility!=='visible'||c.scale!=='1'||c.translate!=='0px')return {error:'repeated transition inside held image',t,first,last,opacity:c.opacity,scale:c.scale};holds++}
       }
     }
     return {count:5502*frames.length,holds,final:frames.every(f=>visible(f.querySelector('.x-risu-bsim-standing-after'))&&![...f.querySelectorAll('.x-risu-bsim-cinematic-image')].some(visible))};
   });
   assert(!result.error,kind+JSON.stringify(result));assert(result.final,kind+' final');report.timelineSamples+=result.count;
   report.heldImageSamples=(report.heldImageSamples||0)+result.holds;
   if(kind==='down_wait'){
     assert.equal(await q('.bsim-unit-player .bsim-cinematic-image').count(),1);
     assert.equal(await q('.bsim-unit-player .bsim-held-start.bsim-held-end').count(),1);
     assert.equal(await q('.bsim-unit-player .bsim-standing-before').count(),0);
     assert.equal(await q('.bsim-unit-player .bsim-standing-retained').count(),1);
   }
   if(kind==='down'){await q('.bsim-transition').evaluateAll(fs=>fs.forEach(f=>f.getAnimations({subtree:true}).forEach(a=>a.currentTime=4900)));await page.screenshot({path:path.join(output,'ui-down.png'),fullPage:true})}
 }
 // A native view change does not recreate the sequence DOM or restart its clock.
 await fixture('resolution');
 const diceAndPop=await page.evaluate(()=>{
   const frame=document.querySelector('.x-risu-bsim-portrait-frame'),all=document.querySelector('.x-risu-bsim-battle').getAnimations({subtree:true});
   all.forEach(a=>a.pause());
   const seek=t=>all.forEach(a=>a.currentTime=t);
   const die=frame.querySelector('.x-risu-bsim-die'),value=die.querySelector('.x-risu-bsim-die-value');
   seek(900);const rolling={transform:getComputedStyle(die).transform,opacity:getComputedStyle(value).opacity,face:getComputedStyle(die.querySelector('.x-risu-bsim-die-rolling'),'::before').content};
   seek(1000);const nextFace=getComputedStyle(die.querySelector('.x-risu-bsim-die-rolling'),'::before').content;
   seek(1700);const settled={transform:getComputedStyle(die).transform,opacity:getComputedStyle(value).opacity,rolling:getComputedStyle(die.querySelector('.x-risu-bsim-die-rolling')).visibility,values:[...document.querySelectorAll('.x-risu-bsim-die-value')].map(e=>e.textContent)};
   const starts=[240,1900,2900,3800,4600],ends=[1900,2900,3800,4600,5200];
   const phases=[],exits=[];for(const img of frame.querySelectorAll('.x-risu-bsim-cinematic-image')){
     if(!img.classList.contains('x-risu-bsim-held-start')){seek(starts[+img.dataset.phaseStart-1]+80);const c=getComputedStyle(img);phases.push({opacity:+c.opacity,scale:c.scale,translate:c.translate})}
     if(!img.classList.contains('x-risu-bsim-held-end')){seek(ends[+img.dataset.phaseEnd-1]-70);exits.push(+getComputedStyle(img).opacity)}
   }
   seek(3600);const c=getComputedStyle(frame.querySelector('.x-risu-bsim-float-deltas'));const delta={radius:c.borderRadius,border:c.borderTopWidth,background:c.backgroundColor};
   return {rolling,nextFace,settled,phases,exits,delta};
 });
 assert.equal(diceAndPop.rolling.opacity,'0');assert.notEqual(diceAndPop.rolling.transform,diceAndPop.settled.transform);assert.notEqual(diceAndPop.rolling.face,diceAndPop.nextFace);
 assert.equal(diceAndPop.settled.opacity,'1');assert.equal(diceAndPop.settled.rolling,'hidden');assert.deepEqual(diceAndPop.settled.values,['6','1']);
 assert(diceAndPop.phases.every(p=>p.opacity>0&&p.opacity<1&&p.scale!=='1'&&p.translate!=='0px'),'missing gradual pop-in');
 assert.equal(await q('.bsim-unit-player .bsim-cinematic-image').count(),3,'normal reaction should occupy one shot through stages 3–5');
 assert.equal(await q('.bsim-unit-player .bsim-phase-3').getAttribute('data-phase-end'),'5');
 assert(diceAndPop.exits.every(opacity=>opacity>0&&opacity<1),'missing gradual pop-out');
 assert.equal(diceAndPop.delta.radius,'8px');assert.equal(diceAndPop.delta.border,'1px');assert.match(diceAndPop.delta.background,/0\.45/);
 await q('.bsim-battle').evaluate(e=>e.getAnimations({subtree:true}).forEach(a=>a.currentTime=3600));await page.screenshot({path:path.join(output,'ui-dice-deltas.png'),fullPage:true});
 const pulses=[];
 for(const [hp,status] of [[100,'normal'],[50,'normal'],[25,'normal'],[10,'normal'],[0,'down'],[20,'groggy']]){
   await fixture('live');lua.global.set('HP',hp);lua.global.set('CONDITION',status);
   await mount(await runLua(`for _,side in ipairs({'player','enemy'}) do S[side].hp=HP;S[side].isDown=CONDITION=='down';S[side].isGroggy=CONDITION=='groggy';S[side].skippedTurnsRemaining=2 end;return B.render(S,C)`));
   const samples=await q('.bsim-standing-after').evaluateAll(images=>images.map(img=>{const a=img.getAnimations()[0];a.pause();const duration=a.effect.getTiming().duration;a.currentTime=duration*.12;const peak=+getComputedStyle(img).scale;a.currentTime=duration*.42;return {duration,peak,rest:+getComputedStyle(img).scale}}));
   assert.deepEqual(samples[0],samples[1]);assert(samples[0].peak>samples[0].rest);pulses.push(samples[0]);
 }
 assert(pulses.slice(0,4).every((p,i)=>!i||(p.duration<pulses[i-1].duration&&p.peak>pulses[i-1].peak)));
 assert.equal(pulses[4].duration,4000);assert.equal(pulses[5].duration,4000);
 report.effects={dice:'roll / changing faces / final 6:1 verified',popIn:diceAndPop.phases,popOut:diceAndPop.exits,pulses,delta:diceAndPop.delta};
 await fixture('resolution');await q('.bsim-transition').evaluateAll(fs=>fs.forEach(f=>f.getAnimations({subtree:true}).forEach(a=>{a.pause();a.currentTime=2000})));
 await q('.bsim-rules-button').click();await q('.bsim-rules button').click();assert.equal(await q('.bsim-standing-before').first().evaluate(e=>e.getAnimations()[0].currentTime),2000);
 await page.emulateMedia({reducedMotion:'reduce'});await fixture('down');assert.equal(await q('.bsim-cinematic-image').first().evaluate(e=>getComputedStyle(e).visibility),'hidden');assert.equal(await q('.bsim-standing-after').first().evaluate(e=>getComputedStyle(e).opacity),'1');await page.emulateMedia({reducedMotion:'no-preference'});
 for(const mode of ['fast','reduced']){await page.emulateMedia({reducedMotion:mode==='reduced'?'reduce':'no-preference'});await fixture(mode==='fast'?'fast':'resolution');assert.equal(await q('.bsim-die-value').first().evaluate(e=>getComputedStyle(e).opacity),'1');assert.equal(await q('.bsim-die-rolling').first().evaluate(e=>getComputedStyle(e).display),'none')}
 await fixture('live');assert.equal(await q('.bsim-standing-after').first().evaluate(e=>e.getAnimations().length),0);await page.emulateMedia({reducedMotion:'no-preference'});
 // Real button route and replayed stale event.
 await fixture('live');const code=await q('.bsim-execute button').getAttribute('risu-btn');await q('.bsim-execute button').click();await q('.bsim-continue').waitFor({state:'attached'});assert.equal(await runLua('return S.matchTurn'),1);lua.global.set('CODE',code);await runLua(`B.handle('qa',CODE)`);assert.equal(await runLua('return S.matchTurn'),1);
 await runLua(`B.busy.qa=true;B.handle('qa','bs;start');B.handle('qa','bs;livefast');assert(S.matchTurn==1 and not S.fast);B.busy.qa=nil`);
 for(const kind of ['setup','developer']){await fixture(kind);assert.equal(await q('.bsim-skill-card').count(),kind==='setup'?35:17)}
 await page.setViewportSize({width:390,height:844});await fixture('live');assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 assert.deepEqual(report.errors,[]);report.popover='toggle / replace / outside / Escape / Enter / Space / computed expanded passed';report.views='30 rows / internal scrolling / preserved state and animation clock passed';
 await fs.writeFile(path.join(output,'ui-results.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
} catch(error){console.error('UI check failed:',error);throw error} finally {await browser.close();lua.global.close()}
