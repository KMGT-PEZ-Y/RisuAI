// RisuAI-equivalent Lua 5.4/WASM, Promise adapter and official JSON round trips.
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import fs from 'node:fs/promises';
const require=createRequire(import.meta.url);
const {LuaFactory}=require('./.qa-web/node_modules/wasmoon');
const root=path.dirname(fileURLToPath(import.meta.url));
const factory=new LuaFactory();
await factory.mountFile('json.lua',await fs.readFile(path.join(root,'qa-output/risu-json.lua'),'utf8'));
const saved=new Map();
let sleeps=0;
const lua=await factory.createEngine({injectObjects:true});
try {
 lua.global.set('getChatVar',(_id,key)=>saved.get(key)??'null');
 lua.global.set('setChatVar',(_id,key,value)=>{JSON.parse(value);saved.set(key,value)});
 lua.global.set('sleep',(_id,ms)=>new Promise(resolve=>setTimeout(()=>{sleeps++;resolve(true)},ms)));
 lua.global.set('alertInput',async()=> 'custom_rival');
 lua.global.set('reloadDisplay',()=>{});
 lua.global.set('log',x=>{throw new Error(String(x))});
 await lua.doString(`
 json=require 'json'
 function getState(id,k) return json.decode(getChatVar(id,'__'..k)) end
 function setState(id,k,v) setChatVar(id,'__'..k,json.encode(v)) end
 function listenEdit(kind,fn) displayCallback=fn end
 function getChatLength(id) return 1 end
 -- Same coroutine/Promise contract as RisuAI's luaCodeWrapper.
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
 BATTLE_SIM_TEST=true
 `);
 const code=(await fs.readFile(path.join(root,'BattleSim.lua'),'utf8')).replace('if BATTLE_SIM_TEST then return B end','if BATTLE_SIM_TEST then BATTLE=B; return B end');
 await lua.doString(code);
 const call=async code=>{lua.global.set('BUTTON_CODE',code);await lua.doString(`onButtonClick('qa',BUTTON_CODE):await()`) };
 const state=()=>JSON.parse(saved.get('__battle_sim_state_v1'));
 const token=()=>{const s=state();return `${s.matchId}~${s.matchTurn}~${s.presentation?.sequenceId||0}`};
 await call('bs;preset;basic');
 await call('bs;side;enemy');
 await call('bs;preset;big_combo');
 await call('bs;ai;ng_plus');
 await call('bs;edit;enemyKey');
 if(JSON.parse(saved.get('__battle_sim_config_v2')).characterKeys.enemy!=='custom_rival') throw new Error('Async prompt failed');
 await call('bs;start');
 const timings=[];
 for(let turn=0;turn<12&&!state().outcome;turn++) {
   while(state().presentation) await call('bs;continue;'+token());
   const t=token(); await call('bs;act;'+t+';attack');
   const started=performance.now(); await call('bs;execute;'+t); timings.push(performance.now()-started);
   if(state().notice||state().thinking) throw new Error('Turn did not complete: '+JSON.stringify(state()));
   if(state().matchTurn!==turn+1) throw new Error('Unexpected turn count');
   await call('bs;execute;'+t);
   if(state().matchTurn!==turn+1) throw new Error('Double-submit advanced turn');
 }
 // Reloading code and decoding saved JSON preserves the battle and its render.
 const before=JSON.stringify(state()); await lua.doString(code);
 const html=await lua.doString(`return displayCallback('qa','',{index=0})`);
 if(!html.includes('custom_rival_')||JSON.stringify(state())!==before) throw new Error('Saved reload changed state/asset key');
 if(!sleeps) throw new Error('NG did not cooperatively yield');
 const result={runtime:'Wasmoon 1.16.0 / Lua 5.4',turns:timings.length,yields:sleeps,meanMs:timings.reduce((a,b)=>a+b,0)/timings.length,maxMs:Math.max(...timings),jsonBytes:Buffer.byteLength(saved.get('__battle_sim_state_v1'))};
 await fs.writeFile(path.join(root,'qa-output/wasmoon-results.json'),JSON.stringify(result,null,2));
 console.log('WASM async/JSON/reload/NG/live buttons passed:',result);
} finally {lua.global.close()}
