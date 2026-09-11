import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url);
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
function dependency(name,override) {
  if(override) return require(override);
  try {return require(name)} catch(error) {
    const bundled=path.join(process.env.USERPROFILE??'', '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
    return require(require.resolve(name,{paths:[bundled]}));
  }
}
const {LuaFactory}=dependency('wasmoon',process.env.LAST_BELL_WASMOON);
const {chromium}=dependency('playwright');
const md=require('./vendor/markdown-it.cjs')({html:true,breaks:true}).disable(['code']);
const code=await fs.readFile(path.join(root,'release/Last-Bell.lua'),'utf8');
const css=await fs.readFile(path.join(root,'src/style.css'),'utf8');
const factory=new LuaFactory();
await factory.mountFile('json.lua',await fs.readFile(path.join(root,'tests/vendor/json.lua'),'utf8'));
await fs.mkdir(path.join(root,'qa'),{recursive:true});
const saved=new Map(); let lua; let refreshes=0; let stopped=false;
let chats=[{role:'char',data:'LAST BELL · 시작하세요.'}];
async function openEngine() {
  if(lua) lua.global.close();
  lua=await factory.createEngine({injectObjects:true});
  lua.global.set('getChatVar',(_id,k)=>saved.get(k)??'null');
  lua.global.set('setChatVar',(_id,k,v)=>{JSON.parse(v);saved.set(k,v)});
  lua.global.set('reloadDisplay',()=>{refreshes++});
  lua.global.set('getChatLength',()=>chats.length);
  lua.global.set('chatJSON',()=>JSON.stringify(chats));
  lua.global.set('removeChat',(_id,i)=>{chats.splice(i,1)});
  lua.global.set('addChat',(_id,role,data)=>{chats.push({role,data})});
  lua.global.set('stopChat',()=>{stopped=true});
  await lua.doString(`
    json=require 'json'; LAST_BELL_TEST=true
    function getState(id,k) return json.decode(getChatVar(id,'__'..k)) end
    function setState(id,k,v) setChatVar(id,'__'..k,json.encode(v)) end
    function getFullChat(id) return json.decode(chatJSON()) end
    function listenEdit(kind,fn) displayCallback=fn end
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
          checkresult=function()
            if safe and result==Promise.resolve(result) then result:finally(step) else step() end
          end
          checkresult()
        end)
      end
    end
  `);
  await lua.doString(code);
}
const state=()=>JSON.parse(saved.get('__last_bell_campaign_v1')??'null');
async function callRaw(token) {lua.global.set('BTN',token);await lua.doString(`onButtonClick('qa',BTN):await()`)}
async function call(action,value='') {const s=state()??{serial:1,revision:0};await callRaw(`lb;${s.serial};${s.revision};${action};${value}`)}
async function render() {return lua.doString(`return displayCallback('qa','LAST BELL · 시작하세요.',{index=getChatLength('qa')-1})`)}
const fixtures={}; const report={};
try {
  await openEngine();
  fixtures.home=await render();
  await call('style','reader');
  const stale=`lb;1;${state().revision};career;`;
  await callRaw(stale);const before=JSON.stringify(state());await callRaw(stale);assert.equal(JSON.stringify(state()),before);
  fixtures.gym=await render();
  await call('start'); fixtures.plan=await render();
  await call('add','slip');await call('add','cross');await call('add','breathe');
  fixtures.planned=await render();
  const execute=`lb;1;${state().revision};execute;`;await callRaw(execute);
  assert.equal(state().match.turn,1); await callRaw(execute);assert.equal(state().match.turn,1);
  fixtures.replay=await render();
  const stored=JSON.stringify(state()); await openEngine();assert.equal(JSON.stringify(state()),stored);
  assert.ok((await render()).includes('방금, 링 위에서.'));
  assert.equal(await lua.doString(`return displayCallback('qa','old',{index=-10})`),'old');
  // Exact slash commands stop model dispatch; ordinary chat is untouched.
  chats.push({role:'user',data:'/boxing'});await lua.doString(`onStart('qa')`);
  assert.ok(stopped);assert.equal(chats.at(-1).role,'char');assert.equal(state().match.turn,1);
  stopped=false;chats.push({role:'user',data:'안녕하세요'});await lua.doString(`onStart('qa')`);assert.equal(stopped,false);
  chats.pop();
  await call('resetAsk'); fixtures.reset=await render();await call('resetCancel');assert.equal(state().match.turn,1);
  await call('help');fixtures.help=await render();await call('help');
  report.integration={asyncButtons:true,staleButtons:true,doubleSubmit:true,jsonReload:true,lastMessageOnly:true,slashCommand:true,ordinaryChatUntouched:true,resetCancel:true};
  console.log('Host integration passed. Running rules and randomized matches…');
  await lua.doString(await fs.readFile(path.join(root,'tests/rules.lua'),'utf8'));
  report.rules=JSON.parse(await lua.doString('return json.encode(RULE_RESULTS)'));
  console.log('Rules passed:',JSON.stringify(report.rules));
  // Start a fresh real campaign, then drive every screen exclusively via host button hooks.
  await call('resetAsk');await call('resetYes');assert.equal(state().screen,'home');assert.equal(state().serial,2);
  await call('career');await call('start');
  const campaign=[];const started=performance.now();
  while(state().screen!=='champion') {
    const s=state(),m=s.match;
    if(s.screen==='gym') {
      while(state().points>0) {
        const u=state().upgrades;const upgrade=u.power<3?'power':u.lungs<3?'lungs':'heart';
        await call('train',upgrade);
      }
      await call('start');
    } else if(s.screen==='result') {
      fixtures.result??=await render();
      campaign.push({level:s.level,opponent:s.level,result:m.result,turns:m.turn,health:m.p.hp,score:[m.totalP,m.totalE]});
      console.log('Campaign bout:',JSON.stringify(campaign.at(-1)));
      assert.equal(m.result.winner,'player',`Planner could not beat rival ${s.level}`);
      await call('resultNext');
    } else if(m.mode==='plan') {
      const plan=JSON.parse(await lua.doString(`return json.encode(LAST_BELL.testChoose(getState('qa',LAST_BELL.key)))`));
      for(const a of plan) await call('add',a);
      await call('execute');
    } else if(m.mode==='replay') await call('continue');
    else {
      fixtures.corner??=await render();
      await call('corner',m.p.hp<m.p.maxhp-14?'ice':m.p.sta<15||m.p.shock>10?'air':'read');
    }
    assert.ok(campaign.length<=5,'Campaign loop');
  }
  fixtures.champion=await render();
  report.campaign={style:'reader',bouts:campaign,seconds:Math.round((performance.now()-started)/1000)};
  report.refreshes=refreshes;
  await fs.writeFile(path.join(root,'qa/fixtures.json'),JSON.stringify(fixtures,null,2));
  console.log('Campaign passed. Rendering desktop and mobile layouts…');
  const browser=await chromium.launch({headless:true,channel:process.env.LAST_BELL_BROWSER??'msedge'});
  try {
    const page=await browser.newPage(); const browserErrors=[];
    page.on('pageerror',e=>browserErrors.push(e.message));
    report.layouts=[];
    for(const width of [1100,390,320]) {
      await page.setViewportSize({width,height:1000});
      for(const [name,html] of Object.entries(fixtures)) {
        await page.setContent('<html lang="ko"><meta charset="UTF-8"><style>body{background:#0b1118;margin:0;padding:16px} @media(max-width:600px){body{padding:4px}}</style><style>'+css+'</style><div id="host"></div></html>');
        await page.addScriptTag({path:path.join(root,'tests/vendor/purify.js')});
        // RisuAI's Markdown + DOMPurify + class-prefix contract, using project-independent fixtures.
        const parsed=md.render(html);
        const audit=await page.evaluate(({parsed})=>{
          DOMPurify.addHook('uponSanitizeAttribute',(_node,data)=>{if(data.attrName==='class') data.attrValue=data.attrValue.split(' ').map(v=>v.startsWith('x-risu-')?v:'x-risu-'+v).join(' ')});
          document.querySelector('#host').innerHTML=DOMPurify.sanitize(parsed,{ADD_ATTR:['risu-btn']});
          const panel=document.querySelector('.x-risu-lb');
          return {panel:!!panel,buttons:panel.querySelectorAll('[risu-btn]').length,disabled:panel.querySelectorAll('button:disabled').length,overflow:document.documentElement.scrollWidth>innerWidth,broken:[...panel.querySelectorAll('button')].some(b=>!b.disabled&&!b.hasAttribute('risu-btn'))};
        },{parsed});
        assert.ok(audit.panel);assert.ok(audit.buttons>0);assert.ok(!audit.overflow,`${name} overflow at ${width}`);assert.ok(!audit.broken,'Missing host button');
        report.layouts.push({name,width,...audit});
        if(width!==320) await page.screenshot({path:path.join(root,`qa/${name}-${width}.png`),fullPage:true});
        if(width===1100) await fs.writeFile(path.join(root,`qa/${name}.html`),'<!doctype html><html lang="ko"><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Last Bell — '+name+'</title><style>body{background:#0b1118;padding:16px;margin:0}</style><style>'+css+'</style>'+parsed+'</html>');
      }
    }
    assert.deepEqual(browserErrors,[]);report.browserErrors=browserErrors;
    // Actual DOM clicks → Lua host callbacks → saved state → DOM refresh.
    await page.setViewportSize({width:900,height:1000});
    await page.exposeFunction('hostButton',async value=>{await callRaw(value);return md.render(await render())});
    await page.evaluate(()=>{document.addEventListener('click',async e=>{const b=e.target.closest('[risu-btn]');if(!b)return;document.querySelector('#host').innerHTML=DOMPurify.sanitize(await window.hostButton(b.getAttribute('risu-btn')),{ADD_ATTR:['risu-btn']})})});
    await page.locator('[risu-btn$="resetAsk;"]').first().click();
    await page.locator('[risu-btn$="resetYes;"]').waitFor();
    await page.locator('[risu-btn$="resetYes;"]').click();
    await page.locator('[risu-btn$="career;"]').waitFor();
    await page.locator('[risu-btn$="career;"]').click();
    await page.locator('[risu-btn$="start;"]').waitFor();
    await page.locator('[risu-btn$="start;"]').click();
    await page.locator('[risu-btn$="add;jab"]').waitFor();
    for(const action of ['jab','cross','breathe']) await page.locator(`[risu-btn$="add;${action}"]`).click();
    await page.locator('[risu-btn$="execute;"]').waitFor();await page.locator('[risu-btn$="execute;"]').click();
    await page.locator('[risu-btn$="continue;"]').waitFor();assert.equal(state().match.turn,1);
    report.domClickFlow=true;
  } finally {await browser.close()}
  await fs.writeFile(path.join(root,'qa/results.json'),JSON.stringify(report,null,2));
  console.log('ALL PASSED:',JSON.stringify({checks:report.rules.checks,layouts:report.layouts.length,domClickFlow:true,campaign:report.campaign}));
} finally {lua?.global.close()}
