-- Pure Lua skill engine. Stored states contain identifiers, never functions or definitions.
do
local sides={'player','enemy'}
local function other(side) return side=='player' and 'enemy' or 'player' end
local function has(xs,v) for _,x in ipairs(xs or {}) do if x==v then return true end end return false end
local function copy(v) if type(v)~='table' then return v end local r={} for k,x in pairs(v) do r[k]=copy(x) end return r end
B.copy=copy; B.other=other; B.has=has
local resourceKey={hp='hp',stamina='stamina',break_gauge='breakGauge'}
local maxKey={hp='maxHp',stamina='maxStamina',break_gauge='maxBreakGauge'}
local function filter(xs,fn) local r={} for _,x in ipairs(xs) do if fn(x) then r[#r+1]=x end end return r end
local function targets(side,target) if target=='both' then return {side,other(side)} end return {target=='opponent' and other(side) or side} end
B.apps={}
for id,d in pairs(B.skills) do for _,lv in ipairs(d.levels) do for i,a in ipairs(lv.applications) do
  a.ref=id..':'..lv.level..':'..i; B.apps[a.ref]=a
end end end
function B.equip(c,loadout)
  c.skills=copy(loadout or {}); c.cooldowns={}; c.uses={}; c.roundUses={}; c.costMods={}; c.nextCostMods={}; c.queued={}
  for _,o in ipairs(c.skills) do local lv=B.skills[o.id].levels[o.level or 1]
    c.cooldowns[o.id]=0; c.uses[o.id]=lv.usage_limit.per_match; c.roundUses[o.id]=lv.usage_limit.per_round
  end
end
function B.owned(c,id) for _,o in ipairs(c.skills or {}) do if o.id==id then return o end end end
function B.level(c,id) local o=B.owned(c,id); return o and B.skills[id].levels[o.level or 1] end
function B.migrate(s)
  if type(s)~='table' or not s.player then return s end
  if (s.version or 1)<2 then
    B.equip(s.player,{}); B.equip(s.enemy,{})
    for _,side in ipairs({'player','enemy'}) do for _,st in ipairs(s[side].statuses) do st.unit=st.unit or 'owner_turn' end end
    s.version=2; s.characterKeys={player='player',enemy=s.strategy or 'enemy'}
    s.aiMode='existing'; s.judgment=1; s.fast=false; s.skillPhotos=false
    s.intentHistory={player={},enemy={}}; s.matchId=tostring(s.seed)..'-migrated'
    -- Version 1 deferred interval calculation; retain this marker until Continue.
    s.legacyInterval=s.pendingInterval and true or false
  end
  s.intentHistory=s.intentHistory or {player={},enemy={}}
  return s
end
function B.newState(config,seed)
  local s=makeState(config.strategy,seed); s.version=2; s.matchId=tostring(seed)..'-'..tostring(config.serial or 1)
  s.characterKeys=copy(config.characterKeys); s.player.name=config.playerName; s.enemy.name=config.enemyName
  s.aiMode=config.aiMode; s.judgment=config.judgment or 1; s.fast=config.fast; s.skillPhotos=config.skillPhotos
  s.intentHistory={player={},enemy={}}; B.equip(s.player,config.playerDeck); B.equip(s.enemy,config.enemyDeck)
  return s
end
function B.canChoose(s,side)
  local c=s[side]; return not s.outcome and not c.isKo and not c.isDown and not c.isGroggy and not s[other(side)].isDown
end
local function statusRules(s,side,upcoming)
  local out={}
  for _,st in ipairs(s[side].statuses) do
    local a=B.apps[st.app]
    if a and st.remainingTurns>0 and st.appliedOnMatchTurn<s.matchTurn+(upcoming and 1 or 0) then
      for _,e in ipairs(a.effects) do out[#out+1]={st=st,a=a,e=e} end
    end
  end
  return out
end
function B.legalActions(s,side,upcoming)
  local allowed=copy(ACTIONS)
  local rules=statusRules(s,side,upcoming)
  for i,r in ipairs(rules) do r.order=i end
  table.sort(rules,function(a,b) if a.st.priority~=b.st.priority then return a.st.priority>b.st.priority end return a.order<b.order end)
  for _,r in ipairs(rules) do
    local e,sp=r.e,r.a.delivery.status
    if e.category=='action_control' and has(sp.tags,'selection_control') then
      if e.operation=='force' then return {e.parameters.action}
      elseif e.operation=='allow_only' then allowed=filter(allowed,function(a) return has(e.parameters.actions,a) end)
      else allowed=filter(allowed,function(a) return not has(e.parameters.actions,a) end) end
    end
  end
  return allowed
end
local function compare(a,b,op)
  if op=='equal' then return a==b elseif op=='not_equal' then return a~=b
  elseif op=='less_than' then return a<b elseif op=='less_than_or_equal' then return a<=b
  elseif op=='greater_than' then return a>b else return a>=b end
end
function B.condition(s,side,cond,intent,ctx,upcoming)
  if not cond then return true end
  if cond.kind=='all' then for _,ch in ipairs(cond.children) do if not B.condition(s,side,ch,intent,ctx,upcoming) then return false end end return true end
  if cond.kind=='any' then for _,ch in ipairs(cond.children) do if B.condition(s,side,ch,intent,ctx,upcoming) then return true end end return false end
  if cond.kind=='not' then return not B.condition(s,side,cond.children[1],intent,ctx,upcoming) end
  local p,a=cond.predicate,cond.arguments; local subject=a.subject=='opponent' and other(side) or side
  local c=s[subject]; local action=intent and intent.action
  if ctx then action=ctx.actions[subject] end
  local hist=s.histories[subject]; local val=a.value
  if p=='action_in' then return has(a.values,action)
  elseif p=='previous_action_is' then return hist[#hist]==val
  elseif p=='recent_action_count_at_least' then local n=0 for i=math.max(1,#hist-a.window+1),#hist do if hist[i]==a.action then n=n+1 end end return n>=val
  elseif p=='resource_at_least' then return c[resourceKey[a.resource]]>=val
  elseif p=='resource_at_most' then return c[resourceKey[a.resource]]<=val
  elseif p=='resource_ratio_at_least' then return c[resourceKey[a.resource]]/c[maxKey[a.resource]]>=val
  elseif p=='resource_ratio_at_most' then return c[resourceKey[a.resource]]/c[maxKey[a.resource]]<=val
  elseif p=='round_at_least' then return s.roundNumber>=val
  elseif p=='round_at_most' then return s.roundNumber<=val
  elseif p=='turn_in_round_is' then return s.turnInRound+(upcoming and 1 or 0)==val
  elseif p=='down_count_at_least' then return c.downCount>=val
  elseif p=='is_groggy' then return c.isGroggy==val
  elseif p=='is_down' then return c.isDown==val
  elseif p=='is_ko' then return c.isKo==val
  elseif p=='status_present' or p=='status_absent' then local found=false for _,st in ipairs(c.statuses) do if st.name==a.status_id then found=true end end if p=='status_absent' then return not found end return found
  elseif p=='status_tag_present' then for _,st in ipairs(c.statuses) do if st.remainingTurns>0 and has(st.tags,a.tag) then return true end end return false
  elseif p=='status_count_at_least' then return #c.statuses>=val
  elseif p=='skill_ready' then return B.owned(c,a.skill_id)~=nil and (c.cooldowns[a.skill_id] or 0)==0
  elseif p=='skill_uses_remaining_at_least' then return c.uses[a.skill_id]==nil or c.uses[a.skill_id]>=val
  elseif not ctx then return false
  elseif p=='raw_die_is' then return ctx.raw[subject]==val
  elseif p=='final_die_at_least' then return ctx.final[subject]~=nil and ctx.final[subject]>=val
  elseif p=='final_die_at_most' then return ctx.final[subject]~=nil and ctx.final[subject]<=val
  elseif p=='dice_result_is' then local d=ctx.diceResult if side=='enemy' and d~='draw' then d=({win='lose',lose='win'})[d] end return d==val
  elseif p=='result_entry_is' then return ctx.entryId==val
  elseif p=='result_delta_is' then return compare(ctx.deltas[subject][resourceKey[a.resource]],val,a.comparison) end
  error('Unsupported condition: '..tostring(p))
end
function B.cost(s,side,id,cost,upcoming)
  local c=s[side]; local amount=math.max(0,cost.amount+((c.costMods[id] or {})[cost.resource] or 0)+(c.nextCostMods[cost.resource] or 0))
  if cost.resource=='stamina' then for _,r in ipairs(statusRules(s,side,upcoming)) do
    if r.e.category=='skill_control' and r.e.operation=='cost_discount' and has(B.skills[id].tags,r.e.parameters.eligible_tag) then amount=math.max(r.e.parameters.minimum_cost or 8,amount-r.e.parameters.value) end
  end end
  return amount
end
function B.valid(s,side,intent,upcoming)
  if not intent or not B.canChoose(s,side) then return false,'행동할 수 없는 상태' end
  if not has(B.legalActions(s,side,upcoming),intent.action) then return false,'현재 금지된 행동' end
  if not intent.skill then return true end
  local c=s[side]; local lv=B.level(c,intent.skill)
  if not lv then return false,'장착되지 않은 스킬' end
  for _,r in ipairs(statusRules(s,side,upcoming)) do if r.e.category=='skill_control' and r.e.operation=='seal' then return false,'스킬 봉인 중' end end
  if not has(lv.requirements.allowed_actions,intent.action) then return false,'행동 조건 불일치' end
  if not B.condition(s,side,lv.requirements.condition,intent,nil,upcoming) then return false,'발동 조건 불충족' end
  if (c.cooldowns[intent.skill] or 0)>0 then return false,'재사용 대기 중' end
  if c.uses[intent.skill]==0 or c.roundUses[intent.skill]==0 then return false,'사용 횟수 소진' end
  for _,cost in ipairs(lv.costs) do if c[resourceKey[cost.resource]]-B.cost(s,side,intent.skill,cost,upcoming)<cost.minimum_remaining then return false,'자원 부족' end end
  return true
end
function B.legalIntents(s,side)
  if not B.canChoose(s,side) then return {{action='attack'}} end
  local r={}
  for _,act in ipairs(B.legalActions(s,side,true)) do
    r[#r+1]={action=act}
    for _,o in ipairs(s[side].skills) do local x={action=act,skill=o.id} if B.valid(s,side,x,true) then r[#r+1]=x end end
  end
  return r
end
local function commit(s,side,intent)
  local c=s[side]; local id=intent.skill; if not id then return end
  local lv=B.level(c,id)
  for _,cost in ipairs(lv.costs) do local k=resourceKey[cost.resource]; c[k]=c[k]-B.cost(s,side,id,cost,false) end
  c.nextCostMods={}
  if c.uses[id] then c.uses[id]=c.uses[id]-1 end
  if c.roundUses[id] then c.roundUses[id]=c.roundUses[id]-1 end
  if lv.cooldown.starts=='on_skill_commit' then c.cooldowns[id]=lv.cooldown.turns end
  for _,r in ipairs(statusRules(s,side,false)) do
    local e=r.e; local p=e.parameters
    if e.category=='skill_control' and e.operation=='cost_discount' then
      if has(B.skills[id].tags,p.eligible_tag) then
        r.st.remainingTurns=0
        if not has(B.skills[id].tags,'control') and not has(B.skills[id].tags,'finisher') then c.cooldowns[id]=math.max(2,(c.cooldowns[id] or 0)-(p.cooldown_reduction or 0)) end
      elseif p.extend_on_tag and has(B.skills[id].tags,p.extend_on_tag) and not r.st.discountExtended then r.st.remainingTurns=r.st.remainingTurns+1; r.st.discountExtended=true end
    end
  end
  c.statuses=filter(c.statuses,function(st) return st.remainingTurns>0 end)
end
local function effect(s,ctx,owner,target,app,e,index)
  local p=e.parameters; local op=e.operation; local c=s[target]; local key=resourceKey[p.resource]
  if e.category=='resource_change' then
    if p.requires_living and (c.hp<=0 or c.isDown or c.isKo) then return false end
    local value=p.value; if op=='add' then value=c[key]+value elseif op=='add_percent_of_max' then value=c[key]+c[maxKey[p.resource]]*value elseif op=='set_percent_of_max' then value=c[maxKey[p.resource]]*value end
    c[key]=clamp(math.floor(value),0,c[maxKey[p.resource]])
  elseif e.category=='result_modifier' then
    local before=ctx.deltas[target][key]; local pol=p.polarity
    local sign=(pol=='damage' or pol=='decrease' or (pol=='any' and before<0)) and -1 or 1
    if not (pol=='any' or before==0 or before*sign>0) then return false end
    if p.requires_base_change and ctx.base[target][key]*sign<=0 then return false end
    local v=p.value or 0; local after=0
    if op=='add' then after=before+sign*v elseif op=='multiply' then after=before*v elseif op=='minimum' then after=sign*math.max(math.abs(before),v) elseif op=='maximum' then after=sign*math.min(math.abs(before),v) end
    ctx.deltas[target][key]=after
  elseif e.category=='dice_modifier' then
    local mn,mx=1,6; if op=='set_minimum' then mn=p.value else mx=p.value end
    table.insert(ctx.ranges[target],{mn,mx,app.priority,index})
  elseif e.category=='action_control' then
    if ctx.controlled[target] then return false end
    local allowed
    if app.delivery.status and has(app.delivery.status.tags,'selection_control') then allowed=B.legalActions(s,target,false)
    elseif op=='force' then allowed={p.action}
    elseif op=='allow_only' then allowed=p.actions
    else allowed=filter(ACTIONS,function(a) return not has(p.actions,a) end) end
    if not has(allowed,ctx.actions[target]) then ctx.actions[target]=allowed[1] end
    ctx.controlled[target]=true
  elseif e.category=='status_control' then
    local sel=p.selector; local selected={}
    for i,st in ipairs(c.statuses) do
      if sel.type=='any' or (sel.type=='status_id' and st.name==sel.value) or (sel.type=='polarity' and st.polarity==sel.value) or (sel.type=='tag' and has(st.tags,sel.value)) then selected[#selected+1]={st=st,i=i} end
    end
    table.sort(selected,function(a,b)
      if sel.order=='highest_priority' and a.st.priority~=b.st.priority then return a.st.priority>b.st.priority end
      if a.st.appliedOnMatchTurn~=b.st.appliedOnMatchTurn then if sel.order=='newest' then return a.st.appliedOnMatchTurn>b.st.appliedOnMatchTurn end return a.st.appliedOnMatchTurn<b.st.appliedOnMatchTurn end
      if sel.order=='newest' then return a.i>b.i end return a.i<b.i
    end)
    local n=0
    for _,row in ipairs(selected) do if op=='change_duration' then row.st.remainingTurns=row.st.remainingTurns+p.value elseif row.st.removable and n<(p.count or 1) then row.st.remainingTurns=0; n=n+1 end end
    c.statuses=filter(c.statuses,function(st) return st.remainingTurns>0 end)
  elseif e.category=='skill_control' then
    if op=='seal' or op=='cost_discount' then return false end
    local sel=p.selector; local id=sel.value
    if sel.type=='skill_id' and not B.owned(c,id) then return false end
    if op=='modify_cost' then
      local mods=c.nextCostMods
      if sel.type~='next_used_skill' then c.costMods[id]=c.costMods[id] or {}; mods=c.costMods[id] end
      mods[p.resource]=(mods[p.resource] or 0)+p.value
    elseif op=='change_cooldown' then
      local before=c.cooldowns[id] or 0; local after=math.max(0,before+p.value); local d=B.skills[id]
      if d and has(d.tags,'muh') and p.value<0 then if has(d.tags,'control') or has(d.tags,'finisher') then after=before else after=math.max(math.min(before,2),after) end end
      c.cooldowns[id]=after
    elseif c.uses[id]~=nil then
      local before=c.uses[id]; local after=math.max(0,before+p.value)
      if B.skills[id] and has(B.skills[id].tags,'muh') then after=math.min(before,after) end
      c.uses[id]=after
    end
  else error('Unsupported effect: '..e.category) end
  return true
end
local function storeStatus(s,owner,target,id,a)
  local c=s[target]; local sp=a.delivery.status
  if sp.group then c.statuses=filter(c.statuses,function(st) return st.group~=sp.group or st.name==sp.status_id end) end
  local st={name=sp.status_id,displayName=sp.name,remainingTurns=sp.duration.value,unit=sp.duration.unit,appliedOnMatchTurn=s.matchTurn,
    removable=sp.removable,polarity=sp.polarity,priority=a.priority,tags=copy(sp.tags),group=sp.group,source=owner,skill=id,app=a.ref}
  for i,old in ipairs(c.statuses) do if old.name==st.name then
    if sp.stacking.mode=='refresh' then old.remainingTurns=st.remainingTurns; old.appliedOnMatchTurn=s.matchTurn else c.statuses[i]=st end
    return
  end end
  c.statuses[#c.statuses+1]=st
end
local dispatch
dispatch=function(s,ctx,timing,allowNew)
  local pending,deferred={},{}; local serial=0
  local function add(list,side,id,a,st,q,owner,index) serial=serial+1; list[#list+1]={side=side,id=id,a=a,st=st,q=q,owner=owner,serial=serial,index=index or tonumber(a.ref:match(':(%d+)$'))} end
  for _,side in ipairs(sides) do
    for i,st in ipairs(s[side].statuses) do local a=B.apps[st.app]
      if a and st.appliedOnMatchTurn<s.matchTurn and (a.delivery.status.active_timing or a.timing)==timing then add(pending,side,st.skill,a,st,nil,side,i) end
    end
    for i,q in ipairs(s[side].queued) do local a=B.apps[q.app]
      if a and q.appliedOnMatchTurn<=s.matchTurn and a.delivery.trigger.event==timing then add(pending,side,q.skill,a,nil,q,side,i) end
    end
  end
  for _,side in ipairs(sides) do local intent=ctx.intents[side]
    if intent and intent.skill then for _,a in ipairs(B.level(s[side],intent.skill).applications) do if a.timing==timing then
      if a.delivery.type=='immediate' or allowNew~=false then add(a.delivery.type=='immediate' and pending or deferred,side,intent.skill,a) end
    end end end
  end
  local function order(a,b) if a.a.priority~=b.a.priority then return a.a.priority>b.a.priority end if a.side~=b.side then return a.side=='player' end
    local ai=a.index; local bi=b.index
    if ai~=bi then return ai<bi end return a.serial<b.serial end
  table.sort(pending,order); table.sort(deferred,order)
  for _,r in ipairs(pending) do
    local a=r.a; local exists=true
    if r.st then exists=has(s[r.owner].statuses,r.st) and r.st.remainingTurns>0 elseif r.q then exists=has(s[r.owner].queued,r.q) and r.q.remainingTurns>0 end
    local condition=a.condition; local target=a.target; local owner=r.side
    if r.st then condition=a.delivery.status.active_condition; target=a.delivery.status.effect_target; owner=r.owner
    elseif r.q then condition=a.delivery.trigger.condition end
    if exists and B.condition(s,r.side,condition,{skill=r.id,action=ctx.actions[r.side]},ctx,false) then
      local applied=false
      for _,to in ipairs(targets(owner,target)) do for i,e in ipairs(a.effects) do if effect(s,ctx,r.side,to,a,e,i) then applied=true end end end
      if r.st then
        if r.st.unit=='trigger_count' then r.st.remainingTurns=r.st.remainingTurns-1 end
        if a.delivery.status.consume_on_trigger then r.st.remainingTurns=0 end
      elseif r.q then
        if a.delivery.consumes=='on_trigger' or (a.delivery.consumes=='on_successful_apply' and applied) then r.q.remainingTurns=0
        elseif r.q.unit=='trigger_count' then r.q.remainingTurns=r.q.remainingTurns-1 end
      end
    end
  end
  for _,side in ipairs(sides) do for _,field in ipairs({'statuses','queued'}) do s[side][field]=filter(s[side][field],function(st) return st.remainingTurns>0 end) end end
  local stored=false
  for _,r in ipairs(deferred) do local a=r.a
    if B.condition(s,r.side,a.condition,ctx.intents[r.side],ctx,false) then for _,to in ipairs(targets(r.side,a.target)) do
      if a.delivery.type=='status' then storeStatus(s,r.side,to,r.id,a); stored=true
      else local ex=a.delivery.expires; table.insert(s[r.side].queued,{name=a.application_id,remainingTurns=ex.value,unit=ex.unit,appliedOnMatchTurn=s.matchTurn,source=r.side,skill=r.id,app=a.ref}) end
    end end
  end
  if stored and timing~='on_status_apply' then dispatch(s,ctx,'on_status_apply',false) end
end
B.dispatch=dispatch
local function tick(s,ctx)
  for _,side in ipairs(sides) do local c=s[side]; local intent=ctx and ctx.intents[side]
    local actionable=not c.isDown and not c.isGroggy and not c.isKo and not s[other(side)].isDown
    for _,o in ipairs(c.skills) do local lv=B.level(c,o.id)
      if not (intent and intent.skill==o.id) and (lv.cooldown.decrements=='owner_turn' or (lv.cooldown.decrements=='owner_actionable_turn' and actionable)) then c.cooldowns[o.id]=math.max(0,(c.cooldowns[o.id] or 0)-1) end
    end
    for _,field in ipairs({'statuses','queued'}) do
      for _,st in ipairs(c[field]) do if st.appliedOnMatchTurn<s.matchTurn and (st.unit=='owner_turn' or st.unit=='exchange' or (st.unit=='owner_actionable_turn' and actionable)) then st.remainingTurns=st.remainingTurns-1 end end
      c[field]=filter(c[field],function(st) return st.remainingTurns>0 end)
    end
  end
end
function B.interval(s,ctx)
  for _,side in ipairs(sides) do local c=s[side]
    if c.isDown and not c.isKo then wake(c) end
    if not c.isKo then
      c.hp=math.min(c.maxHp,c.hp+math.floor(c.maxHp*.33)); c.stamina=math.min(c.maxStamina,c.stamina+math.floor(c.maxStamina*.5)); c.breakGauge=math.floor(c.breakGauge*.5); c.isGroggy=false
      for _,st in ipairs(c.statuses) do local a=B.apps[st.app]
        if not a or a.delivery.status.interval_decay~=false then st.remainingTurns=st.remainingTurns-(st.unit=='round' and 1 or 2) end
      end
      c.statuses=filter(c.statuses,function(st) return st.remainingTurns>0 end)
    end
    for _,q in ipairs(c.queued) do if q.unit=='round' then q.remainingTurns=q.remainingTurns-1 end end
    c.queued=filter(c.queued,function(st) return st.remainingTurns>0 end)
    for _,o in ipairs(c.skills) do local lv=B.level(c,o.id)
      if lv.cooldown.decrements=='round_end' then c.cooldowns[o.id]=math.max(0,(c.cooldowns[o.id] or 0)-1) end
      c.roundUses[o.id]=lv.usage_limit.per_round
    end
  end
  if ctx then dispatch(s,ctx,'on_interval'); afterResources(s) end
  s.roundNumber=s.roundNumber+1; s.turnInRound=0
end
local function finalizeDice(ctx)
  for _,side in ipairs(sides) do
    table.sort(ctx.ranges[side],function(a,b) if a[1]~=b[1] then return a[1]>b[1] elseif a[2]~=b[2] then return a[2]<b[2] elseif a[3]~=b[3] then return a[3]>b[3] else return a[4]<b[4] end end)
    local r=ctx.ranges[side][1]; ctx.final[side]=r and clamp(ctx.raw[side],r[1],r[2]) or ctx.raw[side]
  end
end
-- Intents and dice are supplied before either side is committed: the same transition is used by NG+ and live play.
function B.step(s,intents,dice,simulation)
  if s.outcome then return true end
  if s.roundNumber>s.maxRounds then s.outcome='STALEMATE'; return true end
  for _,side in ipairs(sides) do if B.canChoose(s,side) then local ok,why=B.valid(s,side,intents[side],true) if not ok then return false,why end end end
  local beforeP,beforeE=snapshot(s.player),snapshot(s.enemy)
  s.matchTurn=s.matchTurn+1; s.turnInRound=s.turnInRound+1
  local ctx,details; details={}
  if s.player.isDown or s.enemy.isDown then
    details.kind='down_wait'
    for _,side in ipairs(sides) do local c=s[side]; if not c.isDown then c.hp=math.min(c.maxHp,c.hp+math.floor(c.maxHp*.04)) else c.skippedTurnsRemaining=c.skippedTurnsRemaining-1; if c.skippedTurnsRemaining<=0 then wake(c) end end end
  elseif s.player.isGroggy and s.enemy.isGroggy then details.kind='both_groggy'
  else
    ctx={intents={},actions={player='attack',enemy='attack'},deltas={player=delta(),enemy=delta()},base={player=delta(),enemy=delta()},raw={},final={},ranges={player={},enemy={}},controlled={}}
    for _,side in ipairs(sides) do if B.canChoose(s,side) then ctx.intents[side]=intents[side]; ctx.actions[side]=intents[side].action; commit(s,side,intents[side]); s.intentHistory[side][#s.intentHistory[side]+1]=copy(intents[side]) end end
    dispatch(s,ctx,'on_skill_commit'); dispatch(s,ctx,'before_action_reveal')
    for _,side in ipairs(sides) do if ctx.intents[side] then table.insert(s.histories[side],ctx.actions[side]) end end
    local value
    if s.player.isGroggy or s.enemy.isGroggy then
      details.kind='groggy'; local side=s.enemy.isGroggy and 'player' or 'enemy'
      value=GROGGY_TABLE[ctx.actions[side]]; ctx.deltas[side]=copy(value.player); ctx.deltas[other(side)]=copy(value.enemy)
    else
      details.kind='normal'; dispatch(s,ctx,'before_roll')
      ctx.raw={player=dice and dice[1] or randomInt(s.battleRng,1,6),enemy=dice and dice[2] or randomInt(s.battleRng,1,6)}; ctx.final=copy(ctx.raw)
      dispatch(s,ctx,'after_raw_roll'); dispatch(s,ctx,'before_dice_compare'); finalizeDice(ctx)
      ctx.diceResult=ctx.final.player>ctx.final.enemy and 'win' or (ctx.final.player<ctx.final.enemy and 'lose' or 'draw')
      value=RESULT_TABLE[resultKey(ctx.actions.player,ctx.actions.enemy,ctx.diceResult)]
      ctx.deltas={player=copy(value.player),enemy=copy(value.enemy)}
      for _,side in ipairs(sides) do table.insert(s.exchanges[side],{ownAction=ctx.actions[side],opponentAction=ctx.actions[other(side)],ownDie=ctx.final[side],opponentDie=ctx.final[other(side)]}) end
    end
    ctx.entryId=value.id; ctx.base=copy(ctx.deltas)
    dispatch(s,ctx,'before_result_apply')
    for _,side in ipairs(sides) do for k,v in pairs(ctx.deltas[side]) do ctx.deltas[side][k]=math.floor(v) end applyDelta(s[side],ctx.deltas[side]) end
    dispatch(s,ctx,'after_result_apply'); afterResources(s)
    for _,side in ipairs(sides) do local intent=ctx.intents[side]
      if intent and intent.skill then local lv=B.level(s[side],intent.skill) if lv.cooldown.starts=='after_resolution' then s[side].cooldowns[intent.skill]=lv.cooldown.turns end end
      if intent then details[side..'Action']=ctx.actions[side]; details[side..'Skill']=intent.skill end
      details[side..'Effect']=ctx.deltas[side]; details[side..'Die']=ctx.final[side]
    end
    details.entryId=value.id; details.diceResult=ctx.diceResult
  end
  if ctx and s.turnInRound>=8 then dispatch(s,ctx,'on_round_end'); afterResources(s) end
  tick(s,ctx)
  if not simulation then
    setPresentation(s,details.kind,beforeP,beforeE,details)
    s.presentation.playerSkill=details.playerSkill; s.presentation.enemySkill=details.enemySkill
    pushLog(s,'T'..s.matchTurn..' · '..(details.entryId or details.kind)..(details.playerSkill and ' · '..B.skills[details.playerSkill].name or '')..(details.enemySkill and ' / '..B.skills[details.enemySkill].name or ''))
  end
  if not s.outcome and s.turnInRound>=8 then
    -- Calculate once now, display a saved interval frame after the exchange animation.
    local turnFrame=not simulation and copy(s.presentation)
    local displayActors=not simulation and {player=copy(s.player),enemy=copy(s.enemy),roundNumber=s.roundNumber,turnInRound=s.turnInRound,outcome=s.outcome}
    beforeP,beforeE=snapshot(s.player),snapshot(s.enemy); B.interval(s,ctx)
    if not simulation then setPresentation(s,'interval',beforeP,beforeE,{}); s.pendingInterval=copy(s.presentation); s.presentation=turnFrame; s.displayActors=displayActors end
  end
  if simulation then for _,side in ipairs(sides) do
    while #s.histories[side]>20 do table.remove(s.histories[side],1) end
    while #s.exchanges[side]>20 do table.remove(s.exchanges[side],1) end
    while #s.intentHistory[side]>20 do table.remove(s.intentHistory[side],1) end
  end end
  return true
end
function B.existingIntent(s,side)
  if not B.canChoose(s,side) then return {action='attack'} end
  local act=chooseAction(s.strategy,contextFor(s,side),s.enemyPolicyRng)
  local allowed=B.legalActions(s,side,true); if not has(allowed,act) then act=allowed[1] end
  local scheduled
  local n=#s.intentHistory[side]+1
  if s.strategy=='rookie_cycle' then scheduled=({'rookie_power_strike',false,'rookie_safe_footwork',false,'rookie_recovery_form',false})[(n-1)%6+1]
  elseif s.strategy=='reckless_raider' then scheduled=({false,'rookie_power_strike',false,'rookie_tuck_chin',false,'rookie_recovery_form'})[(n-1)%6+1]
  elseif s.strategy=='rookie_guard' and n%3==0 then scheduled=({attack='rookie_power_strike',defend='rookie_recovery_form',evade='rookie_create_distance'})[act]
  else
    local possible={{action=act}}
    for _,o in ipairs(s[side].skills) do local i={action=act,skill=o.id} if B.valid(s,side,i,true) then possible[#possible+1]=i end end
    if s.strategy~='rookie_cycle' and s.strategy~='reckless_raider' and s.strategy~='rookie_guard' then return randomChoice(s.enemyPolicyRng,possible) end
  end
  if scheduled and B.valid(s,side,{action=act,skill=scheduled},true) then return {action=act,skill=scheduled} end
  return {action=act}
end
end
