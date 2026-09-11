-- BattleSim is bundled into this module only. B is provided by build.py's adapter.
local function battleSession(s) return s.session and s.session.kind=='battle' and s.session end
local function entrancePrompt(s)
  local q=battleSession(s)
  return '[PRIMAL_APEX_MATCH_ENTRY]\n한국어 복싱 리그 서술자. SFW 경기 입장 장면만 짧게 묘사한다. 사용자 행동·감정을 대신 결정하지 않는다. 경기 결과와 능력치를 창작하지 않는다. 입장 후 경기 개시를 기다린다. 시스템 패킷을 출력하지 않는다.\n참가자와 확정 대전='..json.encode(q.input)..'\n최근 사건='..json.encode(s.story.recentSummaries)
end
local function entrance(id)
  local s=P.load(id); local q=s and battleSession(s)
  if not q or s.screen~='entrance' then return end
  local expected=s.revision
  local text,why=P.generate(id,entrancePrompt(s),'확정된 두 선수의 입장 장면을 묘사해 주세요.')
  local now=P.load(id); if not now or now.revision~=expected then return end
  if text then q.entranceReady=true; s.notice='입장 장면을 확인하고 경기 개시를 누르세요.' else s.notice=why end
  if P.commit(id,s,expected) and text then addChat(id,'char',P.strip(text)) end
end
local function configFor(s,n)
  return {screen='battle',tab='skills',deckSide='player',strategy=n.strategy,aiMode=n.aiMode,judgment=1,
    playerName=s.player.name,enemyName=n.name,characterKeys={player='player',enemy=n.id},playerDeck=P.deck(s),enemyDeck=P.copy(n.deck),
    fast=false,skillPhotos=false,serial=s.nextId}
end
function M.owns(s) return s.screen=='hub' or s.screen=='calendar' or s.screen=='prep' or s.screen=='entrance' or s.screen=='battle' end
function M.render(s)
  local parts={}; local next=P.nextMatch(s); local q=battleSession(s)
  if s.screen=='calendar' then
    parts[#parts+1]='<p>미래의 날짜와 시각을 직접 입력할 수 있습니다. 예정 경기를 지나치면 경기 시각에서 멈춥니다.</p>'
    parts[#parts+1]=P.button(s,'time','날짜와 시각 입력')..P.button(s,'wait','다음 경기 시각까지 이동',nil,not next and '예정 경기가 없습니다.' or nil)..P.returnButton(s)
    return P.panel(s,'캘린더',table.concat(parts))
  elseif s.screen=='prep' and q then
    parts[#parts+1]='<p>상대: '..P.esc(q.input.opponent.name)..' · AI '..P.esc(q.input.opponent.aiMode)..'</p><p>보유 스킬에서 최대 5개를 장착하세요. 능력치와 스킬 레벨은 성장 상태를 사용합니다.</p>'
    for _,o in ipairs(s.player.skills) do
      local d=P.skills[o.id]; local selected=P.contains(s.player.loadout,o.id)
      parts[#parts+1]=P.card(d.name..' · Lv.'..o.level,'<p>'..P.esc(d.description)..'</p>'..P.button(s,'equip',selected and '장착 해제' or '장착',o.id))
    end
    parts[#parts+1]=P.button(s,'name','플레이어 이름 변경')..P.button(s,'lock','정비 확정 · 입장 장면 생성')..P.button(s,'prep_back','허브로 돌아가기')
    return P.panel(s,'경기 전 최종 정비',table.concat(parts))
  elseif s.screen=='entrance' and q then
    parts[#parts+1]='<p>'..P.esc(q.input.player.name)..' vs '..P.esc(q.input.opponent.name)..'</p>'
    parts[#parts+1]=P.button(s,'enter','경기 개시',nil,not q.entranceReady and '입장 장면을 생성하거나 생략하세요.' or nil)
    parts[#parts+1]=P.button(s,'entry_retry','입장 장면 재시도 · LLM')..P.button(s,'entry_skip','입장 묘사 생략 · 경기 개시')
    return P.panel(s,'선수 입장',table.concat(parts))
  elseif s.screen=='battle' and q and q.battle then
    local html=B.render(P.copy(q.battle),P.copy(q.config))
    -- Campaign owns setup and matchmaking; remove the sandbox's unrestricted setup button.
    html=html:gsub('<button[^>]-risu%-btn="bs;setup"[^>]*>.-</button>','')
    html=html:gsub('risu%-btn="(bs;[^"]+)"',function(code) return 'risu-btn="pa;hub;'..s.revision..';battle;'..code..'"' end)
    parts[#parts+1]=html
    if q.battle.outcome and not q.battle.presentation then parts[#parts+1]=P.button(s,'settle','경기 결과 저장 · 허브로 돌아가기') end
    return P.panel(s,'복싱 경기',table.concat(parts))
  end
  parts[#parts+1]='<p>'..P.esc(s.player.name)..' · 강화 자원 '..s.player.trainingPoints..' · 완료 경기 '..#s.matchHistory..'</p>'
  if next then parts[#parts+1]=P.card('다음 경기','<p>'..P.esc(P.npc(next.opponentId).name)..' · '..P.time(next.at)..'</p>') else parts[#parts+1]='<p>다음 경기가 아직 정해지지 않았습니다.</p>' end
  local due=P.due(s); local reason=due and '경기 시각입니다.' or nil
  parts[#parts+1]='<div class="pa-grid">'
  parts[#parts+1]=P.card('매치메이킹',P.button(s,'open','매치메이킹', 'matchmaking',reason or (s.story.afterBattle and '경기 후 장면을 마치거나 건너뛰어 주세요.' or nil)))
  parts[#parts+1]=P.card('트레이닝',P.button(s,'open','트레이닝','training',reason))
  parts[#parts+1]=P.card('스토리',P.button(s,'open',s.story.afterBattle and '경기 후 이야기 · 지도' or '지도와 인물 보기','story',reason))
  parts[#parts+1]=P.card('경기',P.button(s,'start_battle','경기 시작',nil,not next and '먼저 대진을 확정하세요.' or (not due and '경기 시각에 시작할 수 있습니다.' or nil)))
  parts[#parts+1]=P.card('캘린더',P.button(s,'open','시간 이동','calendar',reason or (s.story.afterBattle and '경기 후 장면을 먼저 정리해 주세요.' or nil)))
  parts[#parts+1]='</div>'
  if s.scenario.mode=='tournament' and not next then parts[#parts+1]=P.button(s,'free','컵 종료 · 자유 대전으로 전환') end
  parts[#parts+1]='<p class="pa-muted">화면이 보이지 않으면 /apex를 입력하세요. 네 Primal Apex 모듈을 모두 활성화해야 합니다.</p>'
  return P.panel(s,'허브',table.concat(parts))
end
function M.handle(id,s,action,value)
  local q=battleSession(s)
  if s.screen=='battle' and q then
    if action=='battle' then
      local kind=value:match('^bs;([a-z]+)')
      if not P.contains({'act','skill','execute','continue','livefast'},kind) then return false,'허용되지 않은 전투 명령입니다.' end
      P.battleContext=q
      local ok,why=pcall(B.handle,id,value)
      P.battleContext=nil
      if not ok then return false,'전투 처리 실패. 이번 턴과 RNG는 보존됩니다.' end
      if q.battle.notice then return false,q.battle.notice end
      return true
    elseif action=='settle' then
      local b=q.battle; if not b.outcome or b.presentation then return false,'결과 화면을 먼저 확인해 주세요.' end
      local match=P.nextMatch(s)
      if not match or match.id~=q.matchId then return false,'현재 경기 일정과 결과가 일치하지 않습니다.' end
      local result={matchId=match.id,opponentId=match.opponentId,outcome=b.outcome,winner=b.winner,
        rounds=b.roundNumber,turns=b.matchTurn,playerDowns=b.player.downCount,enemyDowns=b.enemy.downCount,at=s.calendar.now+60,
        playerDeck=P.copy(q.config.playerDeck),enemyDeck=P.copy(q.config.enemyDeck)}
      match.status='completed'; s.matchHistory[#s.matchHistory+1]=result
      s.calendar.now=result.at; s.player.trainingPoints=s.player.trainingPoints+2
      s.story.afterBattle=P.copy(result); s.session=false; s.screen='hub'
      if s.scenario.mode=='tournament' then s.scenario.stage=P.nextMatch(s) and ('cup_'..(#s.matchHistory+1)) or 'cup_complete'
      else s.scenario.stage='cycle_'..(#s.matchHistory+1) end
      s.notice='경기 기록 저장 · 강화 자원 +2 · 스토리에서 경기 후 장면을 이어가세요.'
      return true
    end
    return false,'진행 중인 경기를 먼저 마쳐 주세요.'
  elseif s.screen=='prep' and q then
    if action=='equip' then
      local o=P.owned(s,value); if not o then return false,'보유하지 않은 스킬입니다.' end
      if P.contains(s.player.loadout,value) then for i,v in ipairs(s.player.loadout) do if v==value then table.remove(s.player.loadout,i); break end end
      else s.player.loadout[#s.player.loadout+1]=value end
      local ok,why=B.deckValid(P.deck(s)); if not ok then return false,why end
      return true
    elseif action=='name' then
      local name=P.await(alertInput(id,'플레이어 이름을 입력하세요 (1~40자).'))
      if type(name)~='string' then return false end
      name=name:match('^%s*(.-)%s*$')
      if name=='' or #name>120 or name:find('[<>\r\n]') then return false,'올바른 이름을 입력하세요.' end
      s.player.name=name; return true
    elseif action=='prep_back' then s.session=false; s.screen='hub'; return true
    elseif action=='lock' then
      local ok,why=B.deckValid(P.deck(s)); if not ok then return false,why end
      q.config.playerDeck=P.deck(s); q.config.playerName=s.player.name; q.input.player=P.copy(s.player)
      s.screen='entrance'; q.entranceReady=false
      return true,nil,entrance
    end
    return false,'정비 화면의 선택을 사용해 주세요.'
  elseif s.screen=='entrance' and q then
    if action=='entry_retry' then return true,nil,entrance end
    if action=='entry_skip' or (action=='enter' and q.entranceReady) then
      q.battle=B.newState(q.config,q.seed)
      for _,side in ipairs({'player','enemy'}) do
        local stats=side=='player' and q.input.player.stats or q.input.opponent.stats
        for _,k in ipairs({'maxHp','maxStamina','maxBreakGauge','maxDownCount'}) do q.battle[side][k]=stats[k] end
        q.battle[side].hp=stats.maxHp; q.battle[side].stamina=stats.maxStamina
      end
      s.screen='battle'; return true
    end
    return false,'입장 장면을 확인하거나 생략해 주세요.'
  end
  if s.session then return false,'진행 중인 세션으로 돌아가 주세요.' end
  if action=='back' and s.screen=='calendar' then s.screen='hub'; return true end
  if action=='start_battle' and s.screen=='hub' then
    local next=P.nextMatch(s); if not next or not P.due(s) then return false,'아직 경기 시작 시각이 아닙니다.' end
    local n=P.npc(next.opponentId)
    s.session={kind='battle',matchId=next.id,config=configFor(s,n),seed=math.floor(P.roll(s)*2147483646)+1,
      input={contractVersion=1,match=P.copy(next),player=P.copy(s.player),opponent={id=n.id,name=n.name,skills=P.copy(n.deck),aiMode=n.aiMode,strategy=n.strategy,judgment=1,
        stats={maxHp=100,maxStamina=100,maxBreakGauge=100,maxDownCount=3}}}}
    s.screen='prep'; return true
  end
  if P.due(s) then return false,'경기 시각입니다. 경기 시작만 가능합니다.' end
  if action=='open' and s.screen=='hub' and P.contains({'matchmaking','training','story','calendar'},value) then
    if s.story.afterBattle and (value=='matchmaking' or value=='calendar') then return false,'경기 후 장면을 먼저 정리해 주세요.' end
    s.screen=value; return true
  elseif (action=='time' or action=='wait') and s.screen=='calendar' then
    local next=P.nextMatch(s); local at
    if action=='wait' then if not next then return false,'예정 경기가 없습니다.' end; at=next.at
    else
      local text=P.await(alertInput(id,'이동할 시각을 입력하세요. 형식: 3 16:30 (3일차 16:30)'))
      if type(text)~='string' then return false end
      local d,t=text:match('^%s*(%d+)%s+(%d%d:%d%d)%s*$'); at=P.parseTime(d,t)
      if not at then return false,'예: 3 16:30 형식으로 입력하세요.' end
    end
    if at<=s.calendar.now then return false,'현재보다 미래 시각을 선택하세요.' end
    if next and at>next.at then at=next.at; s.notice='예정된 경기를 지나칠 수 없어 경기 시각에서 멈췄습니다.' end
    s.calendar.now=at; s.screen='hub'; return true
  elseif action=='free' and s.scenario.mode=='tournament' and not P.nextMatch(s) then
    s.scenario.mode='free'; s.scenario.id='default'; s.scenario.stage='free_league'; return true
  end
  return false,'사용할 수 없는 선택입니다.'
end
function M.start(id)
  local chats=getFullChat(id); local last=chats[#chats]
  if not last or last.role~='user' then return end
  local cmd=last.data:match('^%s*(.-)%s*$'); if cmd~='/apex' and cmd~='/hub' then return end
  stopChat(id)
  local s,why=P.load(id); if not s then P.notice(id,why); return end
  local rev=s.revision
  if not s.session then s.screen='hub' end
  if P.commit(id,s,rev) then removeChat(id,getChatLength(id)-1); addChat(id,'char','Primal Apex · 현재 진행을 이어갑니다.'); P.refresh(id) end
end
function M.request(id,data)
  local s=P.load(id)
  if s and s.screen=='entrance' and battleSession(s) then return P.inject(data,entrancePrompt(s)) end
  return data
end
function M.output(id)
  local s=P.load(id); local q=s and battleSession(s)
  if not q or s.screen~='entrance' or q.entranceReady then return end
  local chats=getFullChat(id); local last=chats[#chats]
  if last and last.role=='char' then local rev=s.revision; q.entranceReady=true; P.commit(id,s,rev); P.refresh(id) end
end
