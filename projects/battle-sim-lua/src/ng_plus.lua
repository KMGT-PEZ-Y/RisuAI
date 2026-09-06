-- Native bounded NG+ planner: D=3, K=4, B=2, F=4, 6,552 transitions.
-- Independent policy RNG; no submitted player intent or combat RNG enters the model.
do
local copy,has,other=B.copy,B.has,B.other
local function key(i) return i.action..':'..(i.skill or '') end
local function fork(s)
  local r={player=copy(s.player),enemy=copy(s.enemy),histories=copy(s.histories),intentHistory=copy(s.intentHistory),
    exchanges={player={},enemy={}},roundNumber=s.roundNumber,turnInRound=s.turnInRound,matchTurn=s.matchTurn,
    maxRounds=s.maxRounds,outcome=s.outcome,winner=s.winner}
  for _,side in ipairs({'player','enemy'}) do
    for _,field in ipairs({'histories','intentHistory'}) do while #r[field][side]>10 do table.remove(r[field][side],1) end end
  end
  return r
end
local function effectValue(e,c,toSelf)
  local p=e.parameters; local v=0; local weights={hp=1,stamina=.22,break_gauge=-.35}
  if e.category=='resource_change' and e.operation=='add' then v=p.value*weights[p.resource]
  elseif e.category=='result_modifier' then local sign=(p.polarity=='damage' or p.polarity=='decrease') and -1 or 1
    if e.operation=='add' then v=sign*p.value*weights[p.resource]*.5 elseif e.operation=='multiply' then v=sign*14*(p.value-1)*weights[p.resource] end
  elseif e.category=='dice_modifier' then v=e.operation=='set_minimum' and 2*(p.value-1) or -2*(6-p.value)
  elseif e.category=='action_control' then v=-3
  elseif e.category=='skill_control' then
    if e.operation=='seal' then v=-4
    elseif e.operation=='cost_discount' then for _,o in ipairs(c.skills) do if has(B.skills[o.id].tags,p.eligible_tag) and (c.cooldowns[o.id] or 0)<=1 and c.uses[o.id]~=0 then v=.22*p.value; break end end end
  end
  return toSelf and v or -v
end
local function standing(c)
  if c.isKo then return 0 end
  local wakeHp=math.floor(c.maxHp*.5); local hp=c.isDown and wakeHp or c.hp
  local v=hp+math.max(0,c.maxDownCount-1-c.downCount)*wakeHp+.22*c.stamina-.35*c.breakGauge*(c.breakGauge/c.maxBreakGauge)
  if c.isGroggy then v=v-24 end
  if c.isDown then v=v-4*c.skippedTurnsRemaining end
  for _,o in ipairs(c.skills) do if c.uses[o.id]~=nil then v=v+2*math.min(c.uses[o.id],3)/(1+(c.cooldowns[o.id] or 0)/4) end end
  local residual=0
  for _,st in ipairs(c.statuses) do local a=B.apps[st.app] if a then for _,e in ipairs(a.effects) do residual=residual+effectValue(e,c,a.delivery.status.effect_target~='opponent')*math.min(st.remainingTurns,2) end end end
  for _,q in ipairs(c.queued) do local a=B.apps[q.app] for _,e in ipairs(a.effects) do residual=residual+.5*effectValue(e,c,a.target~='opponent') end end
  return v+clamp(residual,-16,16)
end
function B.evaluate(s,side)
  local c,o=s[side],s[other(side)]
  if c.isKo and o.isKo then return 0 elseif c.isKo then return -1000 elseif o.isKo then return 1000 end
  return standing(c)-standing(o)
end
local function legal(s,side)
  s._cache=s._cache or {}; s._cache[side]=s._cache[side] or B.legalIntents(s,side); return s._cache[side]
end
local function distribution(s,side)
  local intents=legal(s,side); local counts={attack=1,defend=1,evade=1}; local n={attack=0,defend=0,evade=0}
  local hist=s.histories[side]; for i=#hist,math.max(1,#hist-7),-1 do counts[hist[i]]=counts[hist[i]]+.85^(#hist-i) end
  local ih=s.intentHistory[side]; local used=0
  for i=math.max(1,#ih-7),#ih do if ih[i].skill then used=used+1 end end
  local rate=(2+used)/(4+math.min(#ih,8))
  for _,i in ipairs(intents) do if i.skill then n[i.action]=n[i.action]+1 end end
  local result,total={},0
  for _,i in ipairs(intents) do local conditional=1 if n[i.action]>0 then conditional=i.skill and rate/n[i.action] or 1-rate end
    local w=counts[i.action]*conditional; result[#result+1]={intent=i,weight=w}; total=total+w
  end
  for _,r in ipairs(result) do r.weight=r.weight/total end
  return result
end
B.opponentDistribution=distribution
local function pick(dist,sample) for _,r in ipairs(dist) do sample=sample-r.weight if sample<=0 then return r.intent end end return dist[#dist].intent end
local function sensitive(cond)
  if not cond then return false end
  if cond.predicate=='raw_die_is' or cond.predicate=='final_die_at_least' or cond.predicate=='final_die_at_most' then return true end
  for _,c in ipairs(cond.children) do if sensitive(c) then return true end end return false
end
local function auditDice(s,intents)
  if not (B.canChoose(s,'player') and B.canChoose(s,'enemy')) then return {{{1,1},1}} end
  local apps={}
  for _,side in ipairs({'player','enemy'}) do
    local i=intents[side]; if i.skill then for _,a in ipairs(B.level(s[side],i.skill).applications) do apps[#apps+1]=a end end
    for _,field in ipairs({'statuses','queued'}) do for _,st in ipairs(s[side][field]) do if B.apps[st.app] then apps[#apps+1]=B.apps[st.app] end end end
  end
  local exact=false
  for _,a in ipairs(apps) do
    if sensitive(a.condition) or (a.delivery.status and sensitive(a.delivery.status.active_condition)) or (a.delivery.trigger and sensitive(a.delivery.trigger.condition)) then exact=true end
    for _,e in ipairs(a.effects) do if e.category=='dice_modifier' then exact=true end end
  end
  if not exact then return {{{6,1},15/36},{{3,3},6/36},{{1,6},15/36}} end
  local result={} for a=1,6 do for b=1,6 do result[#result+1]={{a,b},1/36} end end return result
end
B.auditDice=auditDice
function B.ng(s,side,progress,options)
  options=options or {}; local limit=options.maxTransitions or 6552
  local root=fork(s); local q=clamp(s.judgment or 1,0,1)
  -- LCG is portable to RisuAI's Lua runtime. Fixed dice fixtures, not identical seeds,
  -- define Python/Lua parity (Python uses MT19937).
  local rng=newRng((s.seed or 1)+1315423911+(s.matchTurn+1)*2654435761+(side=='enemy' and 1 or 0))
  local tape={} for d=1,3 do tape[d]={} for j=1,4 do tape[d][j]={randomFloat(rng),randomInt(rng,1,6),randomInt(rng,1,6)} end end
  if options.tape then tape=options.tape end
  local roots=legal(root,side); local transitions,completed=0,0
  if not B.canChoose(root,side) then return {action='attack'},{transitions=0,depth=0,auditCompleted=false} end
  if q==0 then return copy(randomChoice(rng,roots)),{transitions=0,depth=0,auditCompleted=false} end
  local BUDGET={}
  local function step(source,own,opponent,dice)
    if transitions>=limit then error(BUDGET) end
    transitions=transitions+1
    if progress and transitions%128==0 then progress(transitions,limit) end
    if source.outcome then return source end
    local available=legal(source,side); local found=false
    for _,i in ipairs(available) do if key(i)==key(own) then found=true; break end end
    if not found then local action=own.action; own=available[1] for _,i in ipairs(available) do if i.action==action and not i.skill then own=i; break end end end
    local model=fork(source); local intents={[side]=own,[other(side)]=opponent}
    local ok,why=B.step(model,intents,dice,true); if not ok then error(why) end
    return model
  end
  local serial=0
  local function extend(node,intent,depth)
    local states,score={},0
    for j,source in ipairs(node.states) do local t=tape[depth][j]
      local opp=pick(distribution(source,other(side)),t[1]); states[j]=step(source,intent,opp,{t[2],t[3]}); score=score+B.evaluate(states[j],side)
    end
    local plan=copy(node.plan); plan[#plan+1]=intent; serial=serial+1
    return {states=states,score=score/#states,plan=plan,serial=serial}
  end
  local function rank(nodes) table.sort(nodes,function(a,b) if a.score~=b.score then return a.score>b.score end return a.serial<b.serial end) end
  local function union(node) local result,seen={},{} for _,state in ipairs(node.states) do for _,i in ipairs(legal(state,side)) do if not seen[key(i)] then seen[key(i)]=true; result[#result+1]=i end end end return result end
  local function retain(nodes)
    rank(nodes); local kept={nodes[1]}; if nodes[2] then kept[2]=nodes[2] end
    for _,node in ipairs(nodes) do local prepared=false
      for _,state in ipairs(node.states) do for _,st in ipairs(state[side].statuses) do if has(st.tags,'preparation') then prepared=true end end end
      if prepared then if not has(kept,node) then kept[#kept]=node end break end
    end
    return kept
  end
  local empty={states={root,root,root,root},plan={},score=B.evaluate(root,side)}
  local best,beams,first={},{},{}
  for i,intent in ipairs(roots) do best[i]={plan={intent},states={},score=empty.score,serial=i} end
  local ok,err=pcall(function()
    local initial={}
    for i,intent in ipairs(roots) do initial[i]=extend(empty,intent,1) end
    best=initial; completed=1
    for i,n in ipairs(initial) do first[i]=n.score; beams[i]={n} end
    for depth=2,3 do local nb,bb={},{}
      for i,previous in ipairs(beams) do local extensions={}
        for _,node in ipairs(previous) do for _,intent in ipairs(union(node)) do extensions[#extensions+1]=extend(node,intent,depth) end end
        rank(extensions); bb[i]=extensions[1]; nb[i]=retain(extensions)
      end
      beams,best=nb,bb; completed=depth
    end
  end)
  if not ok and err~=BUDGET then error(err) end
  local ranked={}
  for i,node in ipairs(best) do ranked[#ranked+1]={intent=roots[i],score=node.score,plan=node.plan,first=first[i],serial=i} end
  rank(ranked); local audited={}; local auditCompleted=false
  if completed>0 then
    ok,err=pcall(function()
      for i=1,math.min(4,#ranked) do local candidate=ranked[i]; local expected,risk=0,0
        for _,opp in ipairs(distribution(root,other(side))) do
          for _,d in ipairs(auditDice(root,{[side]=candidate.intent,[other(side)]=opp.intent})) do
            local model=step(root,candidate.intent,opp.intent,d[1]); local w=opp.weight*d[2]
            expected=expected+w*B.evaluate(model,side); if model[side].isKo then risk=risk+w end
          end
        end
        audited[#audited+1]={intent=candidate.intent,score=candidate.score-candidate.first+expected,plan=candidate.plan,koRisk=risk,serial=candidate.serial}
      end
    end)
    if ok then auditCompleted=true elseif err==BUDGET then audited={} else error(err) end
  end
  local candidates=#audited>0 and audited or ranked; rank(candidates)
  local chosen
  if randomFloat(rng)>=q then chosen=randomChoice(rng,roots)
  else
    local weights,total={},0
    for _,c in ipairs(candidates) do local waste=false
      if c.intent.skill then for _,v in ipairs(candidates) do if not v.intent.skill and math.abs(v.score-c.score)<1e-9 then waste=true end end end
      if not waste then local w=math.exp(math.max(-700,(c.score-candidates[1].score)/2)); weights[#weights+1]={intent=c.intent,weight=w}; total=total+w end
    end
    for _,w in ipairs(weights) do w.weight=w.weight/total end
    chosen=pick(weights,randomFloat(rng))
  end
  return copy(chosen),{transitions=transitions,depth=completed,auditCompleted=auditCompleted,candidates=candidates,judgment=q}
end
end
