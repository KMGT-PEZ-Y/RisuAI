// Visual smoke test of Lua-rendered HTML; does not touch the user's RisuAI data.
import {createRequire} from 'node:module';
import {fileURLToPath,pathToFileURL} from 'node:url';
import path from 'node:path';
const require=createRequire(import.meta.url);
const {chromium}=require(require.resolve('playwright',{paths:[process.env.USERPROFILE+'/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules']}));
const root=path.dirname(fileURLToPath(import.meta.url));
const browser=await chromium.launch({headless:true,channel:'msedge'});
try {
 const page=await browser.newPage({viewport:{width:1280,height:1100},deviceScaleFactor:1});
 for(const name of ['setup','live','developer','fast']) {
   await page.goto(pathToFileURL(path.join(root,'qa-output',name+'.html')).href);
   await page.screenshot({path:path.join(root,'qa-output',name+'.png'),fullPage:true});
   const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
   if(overflow) throw new Error(name+': horizontal overflow');
   if(name==='setup'||name==='developer') {
     const count=await page.locator('.bsim-skill-card').count();
     if(count!==(name==='setup'?35:17)) throw new Error('Wrong catalog count');
   } else if(!(await page.locator('.bsim-skill-detail').innerText()).includes('묵직한 한 방')) throw new Error('Missing selected skill tooltip');
 }
 await page.setViewportSize({width:900,height:900});
 await page.goto(pathToFileURL(path.join(root,'qa-output','setup.html')).href);
 if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)) throw new Error('900px overflow');
 for(const name of ['resolution','resolution-fast']) {
   await page.goto(pathToFileURL(path.join(root,'qa-output',name+'.html')).href);
   const timing=await page.locator('.bsim-continue').evaluate(el=>({delay:getComputedStyle(el).animationDelay,pointer:getComputedStyle(el).pointerEvents}));
   if(name==='resolution-fast'&&(timing.delay!=='0s'||timing.pointer!=='auto')) throw new Error('Fast progression not immediate');
   if(name==='resolution'&&!timing.delay.includes('5.2s')) throw new Error('Legacy progression timing changed');
 }
 console.log('Desktop HTML: 4 screenshots; 35/17 catalog, persistent tooltip and 1280/900px layout passed.');
} finally {await browser.close();}
