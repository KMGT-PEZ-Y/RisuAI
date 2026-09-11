// Compare every saved field with the repository's pre-change Lua distribution.
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {execFileSync} from 'node:child_process';
const require=createRequire(import.meta.url),root=path.dirname(fileURLToPath(import.meta.url));
const {LuaFactory}=require('./.qa-web/node_modules/wasmoon');
const lua=await new LuaFactory().createEngine();
try{
 await lua.doString('BATTLE_SIM_TEST=true; function listenEdit(...) end');
 const baseline=process.argv[2] ? await fs.readFile(process.argv[2],'utf8') : execFileSync('git',['show','HEAD:projects/battle-sim-lua/BattleSim.lua'],{cwd:root,encoding:'utf8',maxBuffer:2**22});
 lua.global.set('SOURCE',baseline);await lua.doString('OLD=assert(load(SOURCE))()');
 lua.global.set('SOURCE',await fs.readFile(path.join(root,'BattleSim.lua'),'utf8'));await lua.doString('NEW=assert(load(SOURCE))()');
 const result=await lua.doString(`
 local function same(a,b,where)
   assert(type(a)==type(b),where..' type')
   if type(a)~='table' then assert(a==b,where..' value'); return end
   for k,v in pairs(a) do same(v,b[k],where..'.'..tostring(k)) end
   for k in pairs(b) do assert(a[k]~=nil,where..' extra '..tostring(k)) end
 end
 local cases,turns=0,0
 for _,id in ipairs(NEW.skillOrder) do for level=1,#NEW.skills[id].levels do
   cases=cases+1;local c=NEW.defaultConfig();c.playerDeck={{id=id,level=level}};c.enemyDeck={{id=id,level=level}}
   local a=OLD.newState(c,713+cases);local b=NEW.newState(c,713+cases)
   a.player.hp=60;a.enemy.hp=60;b.player.hp=60;b.enemy.hp=60
   for turn=1,80 do
     if a.outcome then break end
     local intents={}
     for _,side in ipairs({'player','enemy'}) do
       local legal=OLD.legalIntents(a,side);same(legal,NEW.legalIntents(b,side),'legal')
       intents[side]=legal[(turn+cases)%#legal+1] or {action='attack'}
     end
     local dice={(turn*3+cases)%6+1,(turn+cases*2)%6+1}
     same(OLD.step(a,intents,dice,false),NEW.step(b,intents,dice,false),'step')
     same(a,b,id..':'..level..':'..turn);turns=turns+1
   end
 end end
 assert(cases==58)
 return cases..' skill levels / '..turns..' turns: every saved field matches baseline'
 `);
 console.log(result);
 await fs.writeFile(path.join(root,'qa-output/regression-results.txt'),result+'\n');
}finally{lua.global.close()}
