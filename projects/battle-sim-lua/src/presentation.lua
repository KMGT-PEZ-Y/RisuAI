-- Display-only adapters. Rules remain the tables used by the combat engine/AI.
function B.ruleRows()
  local rows={}
  for _,a in ipairs(ACTIONS) do for _,b in ipairs(ACTIONS) do
    for _,dice in ipairs({'win','draw','lose'}) do
      rows[#rows+1]={action=a,opponent=b,dice=dice,value=RESULT_TABLE[resultKey(a,b,dice)]}
    end
  end end
  for _,a in ipairs(ACTIONS) do rows[#rows+1]={action=a,opponent='groggy',dice='none',value=GROGGY_TABLE[a]} end
  return rows
end

local function stablePortrait(state,side,character)
  if state.outcome then
    local role=outcomeRole(state.outcome,side)
    if role=='winner' then return assetPath(state,side,'result_win') end
    if role=='loser' or role=='double-ko' then return assetPath(state,side,'result_lose') end
  end
  if character.isKo then return assetPath(state,side,'ko') end
  if character.isDown then return assetPath(state,side,'down_d'..math.max(1,downStage(character))) end
  return assetPath(state,side,string.format('main_d%d_%s',downStage(character),hpBand(character)))
end

-- Reconstruct the pre-resolution portrait from existing saved deltas/flags.
-- No extra save fields or timers: a presentation sequence owns the whole timeline.
local function beforePortrait(state,side,p)
  local c=B.copy(state[side]); local d=p[side..'Delta'] or {}
  c.hp=c.hp-(d.hp or 0)
  if p[side..'EnteredDown'] or p[side..'EnteredKo'] then c.downCount=math.max(0,c.downCount-1); c.isDown=false; c.isKo=false end
  if p[side..'Woke'] then c.isDown=true end
  return stablePortrait({characterKeys=state.characterKeys,strategy=state.strategy},side,c)
end

local function portraitImage(path,classes,title,attributes)
  return '<img class="'..classes..'" '..(attributes or '')..' src="{{raw::'..esc(path)..'}}" alt="'..esc(title or '')..'" loading="eager" decoding="sync">'
end

-- Merge adjacent equal assets, not all occurrences: A/B/A is still three shots.
-- Retaining the first/last stage preserves dice, reaction and Continue timing.
function B.mergePortraitStages(paths)
  local groups={}
  for i,path in ipairs(paths) do
    local previous=groups[#groups]
    if previous and previous.path==path then previous.last=i
    else groups[#groups+1]={path=path,first=i,last=i} end
  end
  return groups
end

local function pulseClass(c,outcome)
  if c.isKo or outcome then return 'bsim-pulse-still' end
  if c.isDown or c.isGroggy then return 'bsim-pulse-rest' end
  local ratio=c.maxHp>0 and c.hp/c.maxHp or 0
  if ratio<=.15 then return 'bsim-pulse-critical' end
  if ratio<=.35 then return 'bsim-pulse-danger' end
  if ratio<=.60 then return 'bsim-pulse-strained' end
  return 'bsim-pulse-calm'
end

function B.skillIconPath(id) return 'skill_'..id..'.png' end

local function renderDie(state,p,side)
  if not p or p.kind~='normal' or not p[side..'Die'] then return '' end
  local value=p[side..'Die']
  local id=p[side..'Skill']; local icon=''
  if state.skillPhotos and id and B.skills[id] then
    icon='<img class="bsim-dice-skill-icon" src="{{raw::'..esc(B.skillIconPath(id))..'}}" alt="사용 스킬: '..esc(B.skills[id].name)..'" loading="eager">'
  end
  return '<div class="bsim-dice-badge"><span class="bsim-die" role="img" aria-label="'..(side=='player' and '내 주사위' or '상대 주사위')..' '..value..'"><span class="bsim-die-rolling" aria-hidden="true"></span><span class="bsim-die-value" aria-hidden="true">'..value..'</span></span>'..icon..'</div>'
end

local function renderCharacter(state,side)
  local c=state[side]; local p=state.presentation; local standing=stablePortrait(state,side,c)
  local parts={'<section class="bsim-unit bsim-unit-'..side..' '..pulseClass(c,state.outcome)..'"><div class="bsim-portrait-frame'..(p and ' bsim-transition' or '')..'"'..(p and ' data-sequence="'..p.sequenceId..'"' or '')..'>'}
  parts[#parts+1]='<span class="bsim-portrait-fallback">'..(side=='player' and 'PLAYER' or 'OPPONENT')..'</span>'
  local retained=false
  if p then
    local before=beforePortrait(state,side,p)
    local action=actionPortraitPath(state,side,p)
    if p.kind=='interval' then action=assetPath(state,side,'interval_d'..downStage(c)) end
    if p.kind=='down_wait' then action=beforePortrait(state,side,p) end
    local resolve=resolvePortraitPath(state,side,p) or action
    local effect=effectReactionPath(state,side,p) or resolve
    local status=statusReactionPath(state,side,p) or effect
    local finish=finalResultPath(state,side,p)
    if c.isKo then finish=assetPath(state,side,'ko')
    elseif c.isDown then finish=assetPath(state,side,'down_d'..math.max(1,downStage(c))) end
    if p.kind=='both_groggy' then action=assetPath(state,side,'reaction_groggy'); resolve=action; effect=action; status=action end
    local groups=B.mergePortraitStages({action or standing,resolve or standing,effect or standing,status or standing,finish or status or standing})
    if groups[1].path~=before then parts[#parts+1]=portraitImage(before,'bsim-portrait bsim-standing-before') end
    retained=groups[#groups].path==standing
    for i,g in ipairs(groups) do
      local classes='bsim-cinematic-image bsim-phase-'..g.first..' bsim-through-'..g.last
      if i==1 and g.path==before then classes=classes..' bsim-held-start' end
      if i==#groups and retained then classes=classes..' bsim-held-end' end
      parts[#parts+1]=portraitImage(g.path,classes,nil,'data-phase-start="'..g.first..'" data-phase-end="'..g.last..'" data-asset="'..esc(g.path)..'"')
    end
  end
  parts[#parts+1]=portraitImage(standing,'bsim-portrait bsim-standing-after'..(retained and ' bsim-standing-retained' or ''),c.name)
  parts[#parts+1]=renderDie(state,p,side)
  local tags={}
  if c.isGroggy then tags[#tags+1]='GROGGY' end
  if c.isDown then tags[#tags+1]='DOWN '..c.skippedTurnsRemaining end
  if c.isKo then tags[#tags+1]='KO' end
  local _,result=outcomeRole(state.outcome,side)
  if result then tags[#tags+1]=result end
  parts[#parts+1]='<div class="bsim-conditions">'..table.concat(tags,' · ')..'</div>'..renderDeltas(p,side)..'</div>'
  parts[#parts+1]='<div class="bsim-unit-head"><b>'..esc(c.name)..'</b><small>다운 '..c.downCount..' / 3</small></div><div class="bsim-resources">'
  parts[#parts+1]=bar('HP',c.hp,c.maxHp,'hp')..bar('STA',c.stamina,c.maxStamina,'sta')..bar('BRK',c.breakGauge,c.maxBreakGauge,'brk')..'</div></section>'
  return table.concat(parts)
end

local function renderResolution(state)
  local p=state.presentation
  if not p then return '' end
  local label=({groggy='GROGGY OPENING',down_wait='DOWN COUNT',both_groggy='DOUBLE GROGGY',interval='ROUND INTERVAL'})[p.kind]
  if p.kind=='normal' then
    return '<div class="bsim-resolution" role="status">'..ACTION_LABEL[p.playerAction]..' · '..ACTION_LABEL[p.enemyAction]..'<span class="bsim-verdict"> · '..({win='PLAYER WIN',draw='DRAW',lose='PLAYER LOSE'})[p.diceResult]..(p.entryId and ' · TABLE '..p.entryId or '')..'</span></div>'
  end
  return '<div class="bsim-resolution" role="status">'..esc(label or 'RESOLUTION')..(p.entryId and ' · TABLE '..p.entryId or '')..'</div>'
end
