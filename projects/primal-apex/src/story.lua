local changes={NONE=0,UP_SMALL=1,DOWN_SMALL=-1}
local rewards={NONE=0,TRAINING_SMALL=1}
local leads={NONE=true,CHALLENGE=true,REMATCH_OFFER=true,REMATCH_PROMISE=true}
local function scene(s) return s.session and s.session.kind=='story' and s.session end
local function allowed(s,target,interaction)
  local after=s.story.afterBattle
  if interaction=='AFTER_BATTLE' then return after and after.opponentId==target end
  if interaction=='INTIMATE' then return after and after.opponentId==target and s.story.contentMode=='MATURE' and P.npc(target).adult end
  for _,i in ipairs(P.interactions) do if i.id==interaction then return true end end
  return false
end
local function prompt(s)
  local q=scene(s); if not q then return '' end
  local n=P.npc(q.npcId); local rel=s.story.relationships[n.id] or {affinity=0,respect=0}
  local next=P.nextMatch(s)
  local lines={
    '[PRIMAL_APEX_STORY_REQUEST]',
    '당신은 복싱 리그 Primal Apex의 서술자다. 한국어로 자연스럽게 이야기한다. 사용자의 행동, 대사, 감정은 대신 결정하지 않는다.',
    '게임 상태는 Lua가 관리한다. 아래 값은 확정 사실이다. 숫자 보상이나 임의 스킬을 창작하지 않는다. 본문에서 시스템 패킷을 설명하지 않는다.',
    'scene='..q.id..'; stage='..s.scenario.stage..'; player='..s.player.name,
    'npc='..n.id..' / '..n.name..'; profile='..n.bio,
    'place='..q.placeId..'; interaction='..q.interaction..'; relationship='..json.encode(rel),
    'start='..P.time(q.startedAt)..'; latest confirmed time='..P.time(s.calendar.now),
    next and ('종료 상한='..P.time(next.at)..'. 이 시각을 넘겨 서술하지 말고 경기 준비로 연결하라.') or '다음 경기 시각은 아직 없다. 사건에 맞는 종료 시각을 선택하라.',
    '대화 중 시간 흐름은 텍스트로만 표현한다. 장면당 고정 시간은 없다. 시작 시각 이전으로 돌아가지 않는다.',
    q.interaction=='INTIMATE' and '사용자가 선택한 성인 간 선택적 친밀 장면이다. 사용자 경계와 중단 의사를 따르고 거절·장면 전환을 허용한다.' or '이번 장면은 SFW다. 성적인 내용을 생성하지 않는다.',
    'flags='..json.encode(s.story.flags)..'; recent summaries='..json.encode(s.story.recentSummaries),
    '요청에 맞는 상황이나 작은 퀘스트를 제시하고 사용자의 자유 반응을 기다린다. 매 응답마다 정산하지 않는다.',
    '서사가 자연스럽게 끝나거나 종료를 요청받으면 짧은 결말과 <PA_SUMMARY>사건 요약 1~3문장</PA_SUMMARY>를 쓰고 마지막 줄에 종료 패킷 하나만 쓴다.',
    '형식: <STORY_END|scene='..q.id..'|end_day=D|end_time=HH:MM|affinity=KEY|respect=KEY|reward=KEY|lead=KEY>',
    'affinity/respect: NONE,UP_SMALL,DOWN_SMALL. reward: NONE,TRAINING_SMALL. lead: '..table.concat(q.allowedLeads,','),
    'KEY는 위에서 하나 선택한다. end_day는 1부터 시작하는 게임 일차, end_time은 24시간제 두 자리 시:분이다. 추가 필드나 숫자 관계 변화는 금지한다.',
    'REMATCH_PROMISE는 사용자가 실제로 대전을 약속했을 때만, TRAINING_SMALL은 퀘스트 성취 등 근거가 있을 때만 선택한다.',
    '이번 요청: '..(q.closing and '사용자가 서사 종료를 요청했다. 사건을 정리하고 종료 패킷을 반환하라.' or '현재 상호작용을 진행하라. 초대만으로 퀘스트 완료나 보상을 확정하지 마라.'),
  }
  if q.afterMatch then lines[#lines+1]='직전 경기 확정 결과='..json.encode(q.afterMatch) end
  return table.concat(lines,'\n')
end
local function parse(text,q)
  local count=0; for _ in text:gmatch('<STORY_END') do count=count+1 end
  if count==0 then return nil end
  if count~=1 then return false,'종료 패킷은 하나만 허용됩니다.' end
  local raw=text:match('<STORY_END|([^<>\r\n]+)>')
  if not raw or #raw>600 or raw:sub(-1)=='|' or raw:find('||',1,true) then return false,'종료 패킷 형식이 올바르지 않습니다.' end
  local fields={}; local keys={scene=true,end_day=true,end_time=true,affinity=true,respect=true,reward=true,lead=true}
  for part in raw:gmatch('[^|]+') do
    local k,v=part:match('^([a-z_]+)=([%w_:%-]+)$')
    if not k or not keys[k] or fields[k] then return false,'허용되지 않거나 중복된 필드입니다.' end
    fields[k]=v
  end
  for k in pairs(keys) do if not fields[k] then return false,'종료 패킷 필드가 누락되었습니다: '..k end end
  if fields.scene~=q.id then return false,'현재 장면과 다른 종료 패킷입니다.' end
  if changes[fields.affinity]==nil or changes[fields.respect]==nil or rewards[fields.reward]==nil or not leads[fields.lead]
    or not P.contains(q.allowedLeads,fields.lead) then return false,'허용되지 않은 결과 키워드입니다.' end
  if not fields.end_day:match('^%d+$') then return false,'종료 일차가 올바르지 않습니다.' end
  local at=P.parseTime(fields.end_day,fields.end_time)
  if not at or at<q.startedAt or (q.deadline and at>q.deadline) then return false,'종료 시각이 장면 시작 이전이거나 경기 시각 이후입니다.' end
  fields.at=at
  return fields
end
local function settle(s,text)
  local q=scene(s); if not q then return nil end
  local f,err=parse(text,q); if not f then return f,err end
  if s.story.consumed[q.id] then return false,'이미 정산한 장면입니다.' end
  local rel=s.story.relationships[q.npcId] or {affinity=0,respect=0}
  rel.affinity=math.max(-100,math.min(100,rel.affinity+changes[f.affinity]))
  rel.respect=math.max(-100,math.min(100,rel.respect+changes[f.respect]))
  s.story.relationships[q.npcId]=rel
  s.player.trainingPoints=s.player.trainingPoints+rewards[f.reward]
  if f.lead~='NONE' then
    local old=s.story.matchLeads[q.npcId]
    if not old or old.kind~='REMATCH_PROMISE' then s.story.matchLeads[q.npcId]={kind=f.lead,at=f.at} end
  end
  s.calendar.now=f.at; s.story.consumed[q.id]=true
  local summary=text:match('<PA_SUMMARY>(.-)</PA_SUMMARY>')
  if not summary or #summary>3000 then summary=P.npc(q.npcId).name..'와 '..q.interaction..' 장면 완료. 관계 '..f.affinity..'/'..f.respect..', 보상 '..f.reward..', 대전 계기 '..f.lead end
  s.story.recentSummaries[#s.story.recentSummaries+1]={sceneId=q.id,npcId=q.npcId,at=f.at,text=summary}
  while #s.story.recentSummaries>8 do table.remove(s.story.recentSummaries,1) end
  if q.afterMatch then s.story.afterBattle=false end
  s.session=false; s.screen='hub'; s.notice='장면 종료 · '..P.time(f.at)..' · 강화 자원 +'..rewards[f.reward]
  return true
end
local function generate(id)
  local s=P.load(id); local q=s and scene(s); if not q then return end
  local expected=s.revision; local text,err=P.generate(id,prompt(s),q.closing and '현재 장면을 마무리하고 요약과 종료 패킷을 반환해 주세요.' or '선택한 인물과의 장면을 시작하거나 이어 주세요.')
  local current=P.load(id); if not current or current.revision~=expected then return end
  if not text then s.notice=err; P.commit(id,s,expected); return end
  local ok,why=settle(s,text)
  if ok==false then s=P.copy(current); s.notice=why..' 정산 재요청 또는 일반 채팅으로 수정할 수 있습니다.' end
  if ok==nil then s.notice=q.closing and '종료 패킷이 없습니다. 정산을 재요청하거나 보상 없이 종료하세요.' or '아래 입력창에서 자유롭게 반응하세요.' end
  if P.commit(id,s,expected) then addChat(id,'char',text) end
end
function M.render(s)
  local q=scene(s); local parts={}
  if q then
    parts[#parts+1]=P.card(P.npc(q.npcId).name..'와의 장면','<p>'..P.esc(q.interaction)..' · 시작 '..P.time(q.startedAt)..'</p><p>대화 중 시간은 서술로만 흐릅니다. 종료 시 정산합니다.</p>')
    parts[#parts+1]=P.button(s,'finish',q.closing and '정산 재요청 · LLM' or '서사 마무리 · LLM')
    parts[#parts+1]=P.button(s,'retry','장면 생성 재시도 · LLM',nil,q.closing and '종료 정산을 요청 중입니다.' or nil)
    parts[#parts+1]=P.button(s,'cancel','보상 없이 종료 확인')
    parts[#parts+1]='<p class="pa-muted">일반 채팅으로 반응하거나 /story end로 마무리하세요. 모델 호출에는 현재 RisuAI 모델 설정을 사용합니다.</p>'
  else
    local blocked=P.blocked(s)
    parts[#parts+1]='<p>장소와 인물을 고른 뒤 상호작용을 선택하세요.</p>'
    if s.story.afterBattle then
      local n=P.npc(s.story.afterBattle.opponentId)
      local body='<p>방금 경기를 마친 두 선수의 이야기입니다.</p>'..P.button(s,'begin','경기 후 대화',n.id..':AFTER_BATTLE',blocked)
      if s.story.contentMode=='MATURE' then body=body..P.button(s,'begin','선택적 성인 친밀 장면',n.id..':INTIMATE',blocked) end
      body=body..P.button(s,'skip_after','경기 후 장면 건너뛰기',nil,blocked)
      parts[#parts+1]=P.card(n.name..' · 대기실',body)
    end
    parts[#parts+1]='<div class="pa-grid">'
    for _,place in ipairs(P.places) do
      local body='<p>'..P.esc(place.description)..'</p>'
      for _,n in ipairs(P.npcs) do if n.place==place.id then
        body=body..'<p><b>'..P.esc(n.name)..'</b></p>'
        for _,i in ipairs(P.interactions) do body=body..P.button(s,'begin',i.name,n.id..':'..i.id,blocked) end
      end end
      parts[#parts+1]=P.card(place.name,body)
    end
    parts[#parts+1]='</div>'..P.returnButton(s)
    parts[#parts+1]=P.button(s,'content',s.story.contentMode=='SFW' and '선택적 성인 장면 사용 확인' or 'SFW로 전환',nil,blocked)
  end
  return P.panel(s,'스토리',table.concat(parts))
end
function M.handle(id,s,action,value)
  local q=scene(s)
  if q then
    if action=='finish' then q.closing=true; return true,nil,generate end
    if action=='retry' and not q.closing then return true,nil,generate end
    if action=='cancel' then
      local yes=P.await(alertInput(id,'보상 없이 장면을 종료하려면 종료를 입력하세요. 시간은 시작 시각에 유지됩니다.'))
      if yes~='종료' then return false end
      s.story.consumed[q.id]=true; if q.afterMatch then s.story.afterBattle=false end
      s.session=false; s.screen='hub'; s.notice='장면을 정산 없이 종료했습니다.'; return true
    end
    return false,'진행 중인 장면을 먼저 마쳐 주세요.'
  end
  if action=='back' then s.screen='hub'; return true end
  local why=P.blocked(s); if why then return false,why end
  if action=='skip_after' and s.story.afterBattle then s.story.afterBattle=false; s.notice='경기 후 장면을 건너뛰었습니다.'; return true end
  if action=='content' then
    if s.story.contentMode=='SFW' then
      local yes=P.await(alertInput(id,'성인 사용자이며 성인 NPC와의 선택적 친밀 장면 사용을 원하면 동의를 입력하세요. 언제든 SFW로 돌아올 수 있습니다.'))
      if yes~='동의' then return false end
      s.story.contentMode='MATURE'
    else s.story.contentMode='SFW' end
    return true
  end
  if action=='begin' then
    local npcId,interaction=value:match('^([%w_]+):([A-Z_]+)$'); local n=P.npc(npcId)
    if not n or not allowed(s,npcId,interaction) then return false,'지금 선택할 수 없는 상호작용입니다.' end
    local next=P.nextMatch(s)
    local choices={'NONE','CHALLENGE','REMATCH_OFFER'}
    if interaction=='CHALLENGE' or interaction=='AFTER_BATTLE' then choices[#choices+1]='REMATCH_PROMISE' end
    s.session={kind='story',id=P.id(s,'scene_'),npcId=npcId,interaction=interaction,placeId=(interaction=='AFTER_BATTLE' or interaction=='INTIMATE') and 'locker_room' or n.place,
      startedAt=s.calendar.now,deadline=next and next.at or false,allowedLeads=choices,closing=false,
      afterMatch=(interaction=='AFTER_BATTLE' or interaction=='INTIMATE') and P.copy(s.story.afterBattle) or false}
    s.notice='장면을 생성합니다. 생성 실패 시 일반 채팅으로도 진행할 수 있습니다.'
    return true,nil,generate
  end
  return false,'사용할 수 없는 선택입니다.'
end
function M.request(id,data)
  local s=P.load(id); if not s or not scene(s) then return data end
  return P.inject(data,prompt(s))
end
function M.output(id)
  local s=P.load(id); if not s or not scene(s) then return end
  local chats=getFullChat(id); local last=chats[#chats]; if not last or last.role~='char' then return end
  local expected=s.revision; local ok,why=settle(s,last.data or '')
  if ok then P.commit(id,s,expected); P.refresh(id)
  elseif ok==false then P.notice(id,why) end
end
function M.start(id)
  local chats=getFullChat(id); local last=chats[#chats]; if not last or last.role~='user' then return end
  local cmd=last.data:match('^%s*(.-)%s*$'); if cmd~='/story end' then return end
  local s=P.load(id)
  if not s or not scene(s) then stopChat(id); P.notice(id,'진행 중인 스토리 장면이 없습니다.'); return end
  local rev=s.revision; s.session.closing=true; P.commit(id,s,rev)
end
M.settle=settle; M.prompt=prompt
