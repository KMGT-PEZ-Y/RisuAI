-- Build-time shared helpers; embedded in all four independent RisuAI modules.
-- No Lua globals are used for cross-module communication.
local P = {key='primal_apex_state_v1', module=PA_MODULE}
local M = {}
function P.copy(v)
  if type(v)~='table' then return v end
  local out={} for k,x in pairs(v) do out[k]=P.copy(x) end return out
end
function P.esc(v)
  return tostring(v or ''):gsub('&','&amp;'):gsub('<','&lt;'):gsub('>','&gt;'):gsub('"','&quot;'):gsub("'",'&#39;')
end
function P.contains(xs,v) for _,x in ipairs(xs or {}) do if x==v then return true end end return false end
function P.integer(v) return type(v)=='number' and v==math.floor(v) and v>=0 and v<1e10 end
function P.time(n)
  return string.format('%d일차 %02d:%02d',math.floor(n/1440)+1,math.floor(n%1440/60),n%60)
end
function P.parseTime(day,time)
  local h,m=tostring(time or ''):match('^(%d%d):(%d%d)$')
  local d=tonumber(day); h=tonumber(h); m=tonumber(m)
  if not P.integer(d) or d<1 or d>9999 or not h or h>23 or not m or m>59 then return nil end
  return (d-1)*1440+h*60+m
end
function P.nextMatch(s)
  local next
  for _,m in ipairs(s.schedule) do
    if m.status=='scheduled' and (not next or m.at<next.at) then next=m end
  end
  return next
end
function P.due(s) local m=P.nextMatch(s); return m and s.calendar.now>=m.at end
function P.blocked(s)
  if s.session then return '진행 중인 장면 또는 경기를 먼저 마쳐 주세요.' end
  if P.due(s) then return '경기 시각입니다. 경기 시작만 가능합니다.' end
end
function P.new()
  return {
    version=1, revision=0, screen='hub', nextId=1, rng=20260908,
    scenario={id='default',mode='free',stage='opening'},
    calendar={now=540},
    player={name='Player',stats={maxHp=100,maxStamina=100,maxBreakGauge=100,maxDownCount=3},
      skills={{id='rookie_power_strike',level=1},{id='rookie_recovery_form',level=1},{id='rookie_safe_footwork',level=1},
        {id=P.growthSkills[1],level=1}},
      loadout={'rookie_power_strike','rookie_recovery_form','rookie_safe_footwork',P.growthSkills[1]},trainingPoints=3},
    story={relationships={},flags={},matchLeads={},recentSummaries={},consumed={},afterBattle=false,contentMode='SFW'},
    schedule={},matchHistory={},session=false,
  }
end
function P.load(id)
  local raw=getChatVar(id,'__'..P.key)
  if raw==nil or raw=='' or raw=='null' then return P.new() end
  local ok,s=pcall(function() return getState(id,P.key) end)
  if not ok or type(s)~='table' then return nil,'저장 데이터를 읽지 못했습니다. 원본 저장은 유지됩니다.' end
  if s.version~=1 then return nil,'호환되지 않는 저장 버전입니다. 네 모듈을 함께 업데이트해 주세요.' end
  if not P.integer(s.revision) or not P.integer(s.nextId) or not P.integer(s.rng) or type(s.player)~='table'
    or type(s.calendar)~='table' or not P.integer(s.calendar.now) or type(s.story)~='table'
    or type(s.schedule)~='table' or type(s.matchHistory)~='table' or type(s.scenario)~='table'
    or not P.integer(s.player.trainingPoints) or type(s.player.skills)~='table' or type(s.player.loadout)~='table'
    or type(s.story.relationships)~='table' or type(s.story.flags)~='table' or type(s.story.matchLeads)~='table'
    or type(s.story.consumed)~='table' or type(s.story.recentSummaries)~='table' then
    return nil,'저장 구조가 올바르지 않습니다. 데이터를 덮어쓰지 않았습니다.'
  end
  return s
end
function P.commit(id,s,expected)
  local current,why=P.load(id)
  if not current then return false,why end
  if current.revision~=expected then return false,'화면이 변경되었습니다. 최신 버튼을 사용해 주세요.' end
  s.revision=expected+1
  setState(id,P.key,s)
  return true
end
function P.id(s,prefix) local id=prefix..s.nextId; s.nextId=s.nextId+1; return id end
function P.roll(s) s.rng=(s.rng*48271)%2147483647; return s.rng/2147483647 end
function P.owned(s,id) for _,x in ipairs(s.player.skills) do if x.id==id then return x end end end
function P.deck(s)
  local deck={}
  for _,id in ipairs(s.player.loadout) do local o=P.owned(s,id); if o then deck[#deck+1]=P.copy(o) end end
  return deck
end
function P.notice(id,msg) if alertNormal then alertNormal(id,msg) end end
function P.refresh(id) if reloadDisplay then reloadDisplay(id) end end
function P.await(v) if type(v)=='table' or type(v)=='userdata' then return v:await() end return v end
function P.button(s,action,label,value,reason)
  local attr=reason and 'disabled aria-disabled="true"' or ('risu-btn="pa;'..P.module..';'..s.revision..';'..action..';'..P.esc(value or '')..'"')
  return '<button type="button" class="pa-button" '..attr..'>'..P.esc(label)..'</button>'..(reason and '<small class="pa-muted">'..P.esc(reason)..'</small>' or '')
end
function P.card(title,body) return '<div class="pa-card"><strong>'..P.esc(title)..'</strong>'..body..'</div>' end
function P.panel(s,title,body)
  return '<section class="pa-panel" data-pa-module="'..P.module..'"><header><span class="pa-brand">PRIMAL APEX</span><h3>'..P.esc(title)..'</h3><p>'..P.time(s.calendar.now)..' · '..P.esc(s.scenario.stage)..'</p></header>'..(s.notice and '<p class="pa-notice" role="status">'..P.esc(s.notice)..'</p>' or '')..body..'</section>'
end
function P.scope(html)
  return html:gsub('class="([^"]*)"',function(classes)
    return 'class="'..classes:gsub('[^%s]+',function(c) return c:sub(1,7)=='x-risu-' and c or 'x-risu-'..c end)..'"'
  end)
end
function P.returnButton(s) return P.button(s,'back','허브로 돌아가기') end
function P.chatTail(id,n)
  local chats=getFullChat(id); local out={}
  for i=math.max(1,#chats-(n or 16)+1),#chats do
    local c=chats[i]; out[#out+1]={role=c.role=='user' and 'user' or 'assistant',content=P.strip(c.data or '')}
  end
  return out
end
function P.strip(text)
  return tostring(text or ''):gsub('<STORY_END[^>]*>',''):gsub('<PA_ENTER_END[^>]*>',''):gsub('<PA_SUMMARY>.-</PA_SUMMARY>','')
end
function P.generate(id,prompt,request)
  if not LLM then return nil,'LLM 호출을 사용할 수 없습니다. 일반 채팅으로 이어가거나 재시도해 주세요.' end
  local messages={{role='system',content=prompt}}
  for _,v in ipairs(P.chatTail(id,20)) do messages[#messages+1]=v end
  messages[#messages+1]={role='user',content=request}
  local ok,result=pcall(function() return LLM(id,messages,false,{streaming=false}) end)
  if not ok or type(result)~='table' or not result.success or type(result.result)~='string' or result.result=='' then
    return nil,'장면 생성에 실패했습니다. 모델 설정·모듈의 LLM 접근 권한을 확인한 뒤 재시도하거나 일반 채팅으로 이어가세요.'
  end
  return result.result
end
function P.inject(data,prompt)
  if type(data)~='table' then return data end
  for _,msg in ipairs(data) do
    if type(msg.content)=='string' then msg.content=P.strip(msg.content) end
  end
  table.insert(data,{role='system',content=prompt})
  return data
end
