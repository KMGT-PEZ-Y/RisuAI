-- RisuAI adapter and desktop setup/live UI. No JavaScript or LLM calls required.
do
local CONFIG_KEY='battle_sim_config_v2'
local copy,has=B.copy,B.has
B.busy={}
function B.defaultConfig()
  return {screen='setup',tab='skills',deckSide='player',strategy='balanced_soldier',aiMode='existing',judgment=1,
    playerName='Player',enemyName='균형 잡힌 병사',characterKeys={player='player',enemy='balanced_soldier'},
    playerDeck={},enemyDeck={},fast=false,skillPhotos=false,serial=0}
end
function B.deckValid(deck)
  if #deck>5 then return false,'스킬은 최대 5개까지 장착할 수 있습니다.' end
  local seen,tags={},{}; local control,finisher=0,0
  for _,o in ipairs(deck) do local d=B.skills[o.id]
    if not d or not d.levels[o.level or 1] then return false,'존재하지 않는 스킬 또는 레벨입니다.' end
    if seen[o.id] then return false,'같은 스킬을 중복 장착할 수 없습니다.' end
    seen[o.id]=true
    for _,t in ipairs(d.tags) do tags[t]=true end
    if has(d.tags,'control') then control=control+1 end
    if has(d.tags,'finisher') then finisher=finisher+1 end
  end
  if tags.muh and (control>1 or finisher>1) then return false,'제어·결정기는 각각 최대 1개입니다.' end
  if tags.forces_attack and tags.fixed_six then return false,'도발 압박과 승부수는 함께 장착할 수 없습니다.' end
  return true
end
local function button(code,label,selected,disabled)
  return '<button class="bsim-chip'..(selected and ' is-selected' or '')..'" '..(disabled and 'disabled aria-disabled="true"' or 'risu-btn="bs;'..esc(code)..'"')..'>'..esc(label)..'</button>'
end
local function skillText(id,level)
  local d=B.skills[id]; local lv=d.levels[level or 1]; local parts={d.name..' · Lv.'..lv.level,d.description}
  local costs={} for _,cost in ipairs(lv.costs) do costs[#costs+1]=({hp='HP',stamina='STA',break_gauge='BRK'})[cost.resource]..' '..cost.amount end
  local actions={} for _,a in ipairs(lv.requirements.allowed_actions) do actions[#actions+1]=ACTION_LABEL[a] end
  parts[#parts+1]=table.concat(actions,' / ')..' · '..table.concat(costs,' / ')..' · CD '..lv.cooldown.turns..' · 경기 '..(lv.usage_limit.per_match or '무제한')..'회'..(lv.usage_limit.per_round and ' · 라운드 '..lv.usage_limit.per_round..'회' or '')
  return table.concat(parts,'\n')
end
B.skillText=skillText
local function detail(id,level,s,side)
  if not id or not B.skills[id] then return '<div class="bsim-skill-detail">스킬을 선택하면 이곳에 설명이 표시됩니다. 기본 행동만 실행할 수도 있습니다.</div>' end
  local photo=''
  if s and s.skillPhotos then photo='<img class="bsim-skill-photo" src="{{raw::'..esc(assetPath(s,side,'skill_'..id))..'}}" alt="'..esc(B.skills[id].name)..'">' end
  return '<div class="bsim-skill-detail" role="status">'..photo..'<div>'..esc(skillText(id,level)):gsub('\n','<br>')..'</div></div>'
end
local function setup(s,c)
  local parts={'<div class="bsim-panel bsim-setup"><header class="bsim-header"><div><span class="bsim-kicker">BATTLE SIM · SKILLS</span><h3>대전 준비</h3></div><span class="bsim-status">35 SKILLS + NG+</span></header>'}
  if c.notice then parts[#parts+1]='<p class="bsim-notice" role="alert">'..esc(c.notice)..'</p>' end
  parts[#parts+1]='<div class="bsim-setup-columns"><section class="bsim-settings"><h4>대전 캐릭터</h4><p>이름과 사진 에셋 접두사를 직접 지정할 수 있습니다.</p>'
  for _,side in ipairs({'player','enemy'}) do
    parts[#parts+1]='<div class="bsim-config-row"><b>'..(side=='player' and '플레이어' or '상대')..'</b>'..button('edit;'..side..'Name',c[side..'Name'])..button('edit;'..side..'Key','에셋: '..c.characterKeys[side])..'</div>'
  end
  parts[#parts+1]='<details><summary>기존 캐릭터 선택</summary><div class="bsim-chip-list">'
  for _,npc in ipairs(NPCS) do parts[#parts+1]=button('character;'..npc.id,npc.name,c.characterKeys.enemy==npc.id) end
  parts[#parts+1]='</div></details><h4>상대 AI</h4><div class="bsim-chip-list">'..button('ai;existing','기존 AI',c.aiMode=='existing')..button('ai;ng_plus','NG+ AI',c.aiMode=='ng_plus')..'</div>'
  if c.aiMode=='existing' then
    parts[#parts+1]='<div class="bsim-chip-list">'
    for _,npc in ipairs(NPCS) do parts[#parts+1]=button('policy;'..npc.id,npc.name..' · '..npc.difficulty,c.strategy==npc.id) end
    parts[#parts+1]='</div><p class="bsim-hint">초급 3종 AI는 기존 스킬 사용 순서를 따릅니다. 나머지 AI는 결정한 행동에서 사용 가능한 장착 스킬을 선택합니다.</p>'
  else parts[#parts+1]='<p>판단 충실도 1.0 · 행동과 스킬을 함께 판단합니다.</p>' end
  parts[#parts+1]='<h4>연출</h4><div class="bsim-chip-list">'..button('fast',c.fast and '빠른 진행: 켜짐' or '빠른 진행: 꺼짐',c.fast)..button('photos',c.skillPhotos and '스킬 사진: 켜짐' or '스킬 사진: 꺼짐',c.skillPhotos)..'</div><p class="bsim-hint">기본 연출 속도는 기존과 같습니다. 스킬 사진을 추가한 뒤 스킬 사진을 켜세요.</p></section>'
  parts[#parts+1]='<section class="bsim-deck-editor"><h4>덱 구성</h4><div class="bsim-chip-list">'..button('side;player','플레이어 덱',c.deckSide=='player')..button('side;enemy','상대 덱',c.deckSide=='enemy')..'</div>'
  local side=c.deckSide; local deck=c[side..'Deck']
  parts[#parts+1]='<p>장착 '..#deck..' / 5 · 제어·결정기 각 1개까지</p><div class="bsim-equipped">'
  for _,o in ipairs(deck) do parts[#parts+1]=button('equip;'..o.id,B.skills[o.id].name..' Lv.'..o.level..' ×',true) end
  if #deck==0 then parts[#parts+1]='<span>빈 스킬 장착 상태</span>' end
  parts[#parts+1]='</div><details><summary>프리셋 선택 · 현재 덱 교체</summary><div class="bsim-preset-list">'
  for _,p in ipairs(B.presets) do parts[#parts+1]=button('preset;'..p.id,p.name) end
  parts[#parts+1]='</div></details><div class="bsim-chip-list bsim-tabs">'..button('tab;skills','스킬 35종',c.tab=='skills')..button('tab;developer','개발자 · 테스트 17종',c.tab=='developer')..'</div><div class="bsim-catalog">'
  for _,id in ipairs(B.skillOrder) do local d=B.skills[id]
    if (c.tab=='developer')==d.developer then
      local owned=B.owned({skills=deck},id)
      parts[#parts+1]='<article class="bsim-skill-card'..(owned and ' is-equipped' or '')..'"><b>'..esc(d.name)..'</b><p>'..esc(d.description)..'</p><div class="bsim-card-controls">'..button('inspect;'..id,'설명',c.inspect==id)..button('equip;'..id,owned and '해제' or '장착',owned~=nil)
      if d.max_level>1 and owned then parts[#parts+1]=button('level;'..id,'Lv.'..owned.level..' 변경') end
      parts[#parts+1]='</div></article>'
    end
  end
  parts[#parts+1]='</div>'
  if c.inspect and ((c.tab=='developer')==B.skills[c.inspect].developer) then local owned=B.owned({skills=deck},c.inspect)
    parts[#parts+1]=detail(c.inspect,owned and owned.level or 1,c,side)
  end
  parts[#parts+1]='</section></div><div class="bsim-setup-footer">'..button('start','이 설정으로 새 대전 시작')
  if s and s.player then parts[#parts+1]=button('back','진행 중인 경기로 돌아가기') end
  parts[#parts+1]='</div></div>'
  return table.concat(parts)
end
function B.token(s)
  return s.matchId..'~'..s.matchTurn..'~'..(s.presentation and s.presentation.sequenceId or 0)
end
local function loadoutInfo(s,side)
  local c=s[side]; local parts={'<div class="bsim-live-deck"><b>'..(side=='player' and '내 장착 스킬' or '상대 장착 스킬')..'</b><div class="bsim-chip-list">'}
  for _,o in ipairs(c.skills) do
    -- Enemy runtime data deliberately never enters the rendered HTML, including titles.
    local tooltip=side=='player' and (' title="'..esc(skillText(o.id,o.level))..'"') or ''
    parts[#parts+1]='<span class="bsim-skill-name"'..tooltip..'>'..esc(B.skills[o.id].name)..'</span>'
  end
  if #c.skills==0 then parts[#parts+1]='<span>없음</span>' end
  parts[#parts+1]='</div></div>'; return table.concat(parts)
end
local function battle(s,c)
  local display=s
  if s.displayActors then display=copy(s); for k,v in pairs(s.displayActors) do display[k]=v end end
  local token=B.token(s)
  local parts={'<div class="bsim-panel'..(s.presentation and ' is-resolving' or '')..(s.fast and ' bsim-fast' or '')..'"><header class="bsim-header"><div><span class="bsim-kicker">'..(s.aiMode=='ng_plus' and 'NG+ · 판단 충실도 1.0' or 'LIVE MATCH')..'</span><h3>Round '..display.roundNumber..' · Turn '..display.turnInRound..'</h3></div><span class="bsim-status">TOTAL '..s.matchTurn..'</span></header>'}
  parts[#parts+1]=renderResolution(display)..'<div class="bsim-grid">'..renderCharacter(display,'player')..renderCharacter(display,'enemy')..'</div>'
  parts[#parts+1]='<div class="bsim-grid">'..loadoutInfo(s,'player')..loadoutInfo(s,'enemy')..'</div>'
  if s.notice then parts[#parts+1]='<p class="bsim-notice" role="alert">'..esc(s.notice)..'</p>' end
  if s.thinking then parts[#parts+1]='<div class="bsim-thinking" role="status">NG+가 행동을 판단하고 있습니다…</div>'
  elseif s.presentation then parts[#parts+1]='<button class="bsim-continue" risu-btn="bs;continue;'..token..'"><span>CONTINUE</span>'..(s.pendingInterval and '인터벌 확인' or (s.outcome and '결과 확인' or '다음 턴'))..'</button>'
  elseif s.outcome then
    parts[#parts+1]='<div class="bsim-result"><strong>'..(({PLAYER_WIN='플레이어 승리',ENEMY_WIN='상대 승리',DOUBLE_KO='더블 KO',STALEMATE='교착'})[s.outcome] or s.outcome)..'</strong></div>'
  elseif B.canChoose(s,'player') then
    local act=s.selectedAction or B.legalActions(s,'player',true)[1]
    parts[#parts+1]='<div class="bsim-actions">'
    for _,a in ipairs(ACTIONS) do parts[#parts+1]=button('act;'..token..';'..a,ACTION_LABEL[a],act==a,not has(B.legalActions(s,'player',true),a)) end
    parts[#parts+1]='</div><div class="bsim-skill-selection"><h4>이번 턴 스킬</h4><div class="bsim-chip-list">'..button('skill;'..token..';none','기본 행동만',not s.selectedSkill)
    for _,o in ipairs(s.player.skills) do
      local ok,why=B.valid(s,'player',{action=act,skill=o.id},true)
      local status='CD '..(s.player.cooldowns[o.id] or 0)..' · 남은 '..(s.player.uses[o.id] or '∞')..'회'
      parts[#parts+1]='<span class="bsim-skill-choice" title="'..esc(skillText(o.id,o.level))..'">'..button('skill;'..token..';'..o.id,B.skills[o.id].name,s.selectedSkill==o.id)..'<small>'..esc(status)..(ok and '' or ' · '..esc(why))..'</small></span>'
    end
    parts[#parts+1]='</div>'
    local owned=B.owned(s.player,s.selectedSkill)
    parts[#parts+1]=detail(s.selectedSkill,owned and owned.level or 1,s,'player')
    local intent={action=act,skill=s.selectedSkill or nil}; local ok,why=B.valid(s,'player',intent,true)
    parts[#parts+1]=button('execute;'..token,'선택한 행동 실행',true,not ok)
    if not ok then parts[#parts+1]='<p class="bsim-hint">'..esc(why)..'</p>' end
    parts[#parts+1]='</div>'
  else parts[#parts+1]=button('execute;'..token,'강제 턴 진행') end
  local statuses={}
  for _,st in ipairs(s.player.statuses) do statuses[#statuses+1]=esc(st.displayName or st.name)..' ('..st.remainingTurns..')' end
  for _,q in ipairs(s.player.queued) do statuses[#statuses+1]='예약: '..esc(B.skills[q.skill].name)..' ('..q.remainingTurns..')' end
  if #statuses>0 then parts[#parts+1]='<div class="bsim-own-status">내 상태 · '..table.concat(statuses,' / ')..'</div>' end
  parts[#parts+1]='<div class="bsim-log"><div class="bsim-log-title">COMBAT LOG</div>'
  for i=#s.log,1,-1 do parts[#parts+1]='<div class="bsim-log-line">'..esc(s.log[i])..'</div>' end
  parts[#parts+1]='</div><div class="bsim-chip-list">'..button('livefast',s.fast and '빠른 진행: 켜짐' or '빠른 진행: 꺼짐',s.fast)..button('setup','대전 설정')..'</div>'..renderActionPreload(s)..'</div>'
  return table.concat(parts)
end
function B.render(s,c)
  c=c or B.defaultConfig(); s=B.migrate(s)
  if c.screen=='setup' or type(s)~='table' or not s.player then return setup(s,c) end
  return battle(s,c)
end
local function awaitValue(v) if type(v)=='table' or type(v)=='userdata' then return v:await() end return v end
local function save(id,s,c) setState(id,STATE_KEY,s); setState(id,CONFIG_KEY,c) end
local function runTurn(id,s)
  local selected={action=s.selectedAction or B.legalActions(s,'player',true)[1] or 'attack',skill=s.selectedSkill or nil}
  if B.canChoose(s,'player') then local ok,why=B.valid(s,'player',selected,true) if not ok then s.notice=why; return end end
  s.thinking=true; B.busy[id]=true; setState(id,STATE_KEY,s)
  if reloadDisplay then reloadDisplay(id) end
  local ok,intent,stats=pcall(function()
    if s.aiMode=='ng_plus' and B.canChoose(s,'enemy') then
      return B.ng(s,'enemy',function() if sleep and async then awaitValue(sleep(id,0)) end end)
    end
    return B.existingIntent(s,'enemy')
  end)
  s.thinking=false; B.busy[id]=nil
  if not ok then s.notice='AI 판정에 실패했습니다. 현재 턴은 보존됩니다. 다시 실행해 주세요.'; if log then log(tostring(intent)) end return end
  local worked,why=B.step(s,{player=selected,enemy=intent},nil,false)
  if not worked then s.notice=why; return end
  s.selectedAction=nil; s.selectedSkill=nil; s.notice=nil
  if stats then s.lastNg={transitions=stats.transitions,depth=stats.depth,auditCompleted=stats.auditCompleted} end
end
function B.handle(id,code)
  if type(code)~='string' then return end
  local action,param=code:match('^bs;([^;]+);?(.*)$'); if not action then return end
  local s=B.migrate(getState(id,STATE_KEY)); local c=getState(id,CONFIG_KEY)
  if not c then c=B.defaultConfig(); if type(s)=='table' and s.player then c.screen='battle' end end
  if type(s)=='table' and s.thinking and not B.busy[id] then s.thinking=false end
  c.notice=nil
  if action=='setup' then c.screen='setup'
  elseif action=='back' then c.screen='battle'
  elseif action=='start' then
    local ok,why=B.deckValid(c.playerDeck); if ok then ok,why=B.deckValid(c.enemyDeck) end
    if not ok then c.notice=why else
      c.serial=c.serial+1; s=B.newState(c,(os.time and os.time() or 20260905)+c.serial); c.screen='battle'
    end
  elseif action=='livefast' and type(s)=='table' then s.fast=not s.fast; c.fast=s.fast
  elseif c.screen=='setup' or type(s)~='table' then
    if action=='ai' and (param=='existing' or param=='ng_plus') then c.aiMode=param
    elseif action=='character' or action=='policy' then for _,npc in ipairs(NPCS) do if npc.id==param then
      if action=='character' then c.enemyName=npc.name; c.characterKeys.enemy=npc.id else c.strategy=npc.id end
    end end
    elseif action=='side' and (param=='player' or param=='enemy') then c.deckSide=param; c.inspect=nil
    elseif action=='tab' and (param=='skills' or param=='developer') then c.tab=param; c.inspect=nil
    elseif action=='fast' then c.fast=not c.fast
    elseif action=='photos' then c.skillPhotos=not c.skillPhotos
    elseif action=='edit' then
      local side,field=param:match('^(player)(Name)$'); if not side then side,field=param:match('^(enemy)(Name)$') end
      if not side then side,field=param:match('^(player)(Key)$') end; if not side then side,field=param:match('^(enemy)(Key)$') end
      if side then
        local message=field=='Key' and '사진 에셋 접두사를 입력하세요. 예: rival_a (영문·숫자·밑줄·하이픈)' or '대전 캐릭터 이름을 입력하세요.'
        local value=awaitValue(alertInput(id,message))
        if type(value)=='string' then value=value:match('^%s*(.-)%s*$')
          if #value>0 and #value<=100 then
            if field=='Key' then if value:match('^[%w_-]+$') then c.characterKeys[side]=value else c.notice='에셋 접두사는 영문·숫자·밑줄·하이픈만 사용할 수 있습니다.' end
            else c[side..'Name']=value end
          end
        end
      end
    elseif action=='preset' then for _,p in ipairs(B.presets) do if p.id==param then c[c.deckSide..'Deck']={} for _,skill in ipairs(p.skills) do table.insert(c[c.deckSide..'Deck'],{id=skill,level=1}) end end end
    elseif (action=='equip' or action=='inspect' or action=='level') and B.skills[param] and ((c.tab=='developer')==B.skills[param].developer or B.owned({skills=c[c.deckSide..'Deck']},param)) then
      local deck=copy(c[c.deckSide..'Deck']); local owned=B.owned({skills=deck},param)
      if action=='inspect' then c.inspect=param
      elseif action=='level' and owned then owned.level=owned.level%B.skills[param].max_level+1; c[c.deckSide..'Deck']=deck
      elseif action=='equip' then
        if owned then for i,o in ipairs(deck) do if o.id==param then table.remove(deck,i); break end end
        else deck[#deck+1]={id=param,level=1} end
        local ok,why=B.deckValid(deck); if ok then c[c.deckSide..'Deck']=deck; c.inspect=param else c.notice=why end
      end
    end
  elseif not s.thinking then
    local token,value=param:match('^([^;]+);?(.*)$')
    if token==B.token(s) then
      if action=='continue' and s.presentation then
        s.presentation=false; s.displayActors=nil
        if s.legacyInterval then s.legacyInterval=nil; s.pendingInterval=false; local p,e=snapshot(s.player),snapshot(s.enemy); B.interval(s,nil); setPresentation(s,'interval',p,e,{})
        elseif s.pendingInterval then s.presentation=s.pendingInterval; s.pendingInterval=false end
      elseif not s.presentation and not s.outcome then
        if action=='act' and has(B.legalActions(s,'player',true),value) then s.selectedAction=value
        elseif action=='skill' and (value=='none' or B.owned(s.player,value)) then s.selectedSkill=value~='none' and value or nil
        elseif action=='execute' then runTurn(id,s) end
      end
    end
  end
  save(id,s,c)
end
listenEdit('editDisplay',function(id,data,meta)
  if meta and meta.index~=nil and meta.index-getChatLength(id)~=-1 then return data end
  local s=getState(id,STATE_KEY); if type(s)=='table' and (s.version or 1)<2 then s=B.migrate(s); setState(id,STATE_KEY,s) end
  local c=getState(id,CONFIG_KEY)
  if not c then c=B.defaultConfig(); if type(s)=='table' and s.player then c.screen='battle' end end
  return data..B.render(s,c)
end)
onStart=function(id)
  local chat=getFullChat(id); local last=chat[#chat]
  if not last or last.role~='user' or last.data:match('^%s*(.-)%s*$')~='/battle' then return end
  removeChat(id,getChatLength(id)-1); addChat(id,'char','대전 설정을 선택하세요.'); stopChat(id)
  local c=getState(id,CONFIG_KEY) or B.defaultConfig(); c.screen='setup'; setState(id,CONFIG_KEY,c)
end
onButtonClick=async and async(B.handle) or B.handle
end
