local function clamp(x,a,b) return math.max(a,math.min(b,x)) end
local function copy(t) if type(t)~='table' then return t end local n={} for k,v in pairs(t) do n[k]=copy(v) end return n end
G.copy=copy
G.clamp=clamp
function G.new(seed,serial)
  return {version=1,revision=0,serial=serial or 1,seed=seed or 1701,screen='home',style='reader',level=1,points=0,
    upgrades={lungs=0,power=0,heart=0},records={},wins=0,losses=0,help=false}
end
local function random(s,n) s.seed=(s.seed*48271)%2147483647 return s.seed%n+1 end
function G.fighter(hp,sta,power,style)
  return {hp=hp,maxhp=hp,sta=sta,maxsta=sta,power=power or 0,style=style or 'rival',shock=0,downs=0,
    ropes=0,combo='',opening=false,rdDamage=0,rdDowns=0,hits=0,damage=0}
end
function G.cost(f,id)
  local c=G.actions[id].cost
  if f.style=='reader' and (id=='slip' or id=='pivot') then c=c-1 end
  return c
end
function G.forecast(s)
  local m=s.match; local r=G.rivals[s.level]
  local i=random(s,#r.patterns)
  if m.pattern==i then i=i%#r.patterns+1 end
  m.pattern=i; m.intent=copy(r.patterns[i]); m.adapt=''
  -- Adapt only between exchanges, before the player edits their next plan.
  if s.level==5 and m.lastFirst then
    if m.lastFirst=='jab' or m.lastFirst=='cross' then m.intent[1]='slip'; m.adapt='지난 첫 펀치를 읽고 슬립 준비.'
    elseif m.lastFirst=='guard' then m.intent[1]='body'; m.adapt='지난 하이 가드를 읽고 바디 준비.'
    elseif m.lastFirst=='out' then m.intent[1]='in'; m.adapt='지난 후퇴를 읽고 전진 준비.' end
  end
  if m.e.sta<10 then m.intent[1]='guard'; m.intent[2]='breathe'; m.adapt='호흡을 회복하려고 템포를 낮춥니다.' end
end
function G.start(s)
  local r=G.rivals[s.level]; local u=s.upgrades
  s.match={p=G.fighter(100+u.heart*8,30+u.lungs*4+(s.style=='engine' and 6 or 0),u.power,s.style),
    e=G.fighter(r.hp,r.sta,r.power),round=1,exchange=1,distance=2,plan={},cards={},log={},turn=0,
    last={},rounds=r.rounds,totalP=0,totalE=0,mode='plan',result=false,recorded=false}
  s.screen='fight'; s.notice=nil; G.forecast(s)
end
local function addlog(m,t) m.log[#m.log+1]=t if #m.log>24 then table.remove(m.log,1) end end
local function inrange(d,r) for _,v in ipairs(r) do if v==d then return true end end return false end
local function damage(m,a,b,id,def)
  local d=G.actions[id]
  if not d.damage then return 0,0,'',false end
  if not inrange(m.distance,d.range) then return 0,0,'거리 밖',false end
  if def=='slip' and (id=='jab' or id=='cross') then return 0,0,'슬립 회피',true end
  local n=d.damage+a.power
  if a.style=='pressure' and (id=='hook' or id=='body') then n=n+2 end
  if a.combo=='slip' or (a.combo=='jab' and id=='cross') then n=n+4 end
  if a.combo=='feint' then n=n+2 end
  local drain=d.kind=='body' and 7 or 0
  local note='적중'
  if not a.opening then
    if def=='guard' and d.kind=='head' then n=n*0.3; note='가드'
    elseif def=='low' and d.kind=='body' then n=n*0.2; drain=1; note='바디 방어'
    elseif def=='low' and d.kind=='head' then n=n*1.2; note='열린 머리'
    elseif def=='pivot' and d.kind=='head' then n=n*0.7; note='피벗 감쇄' end
  else note='페인트 관통' end
  if b.ropes==2 and d.kind=='head' then n=n+1 end
  return math.max(1,math.floor(n+0.5)),drain,note,false
end
local function recover(f,id)
  f.sta=clamp(f.sta+2+(id=='breathe' and 7 or 0),0,f.maxsta)
  f.shock=clamp(f.shock-(id=='breathe' and 3 or 0),0,18)
end
local function available(f,id)
  local c=G.cost(f,id)
  if f.sta<c then return 'breathe',true end
  f.sta=f.sta-c
  return id,false
end
function G.beat(m,pi,ei,beat)
  local p,e=m.p,m.e
  local pa,pfail=available(p,pi); local ea,efail=available(e,ei)
  local pd,ed=G.actions[pa],G.actions[ea]
  local trace={beat=beat,p=pa,e=ea,pOriginal=pi,eOriginal=ei,pDamage=0,eDamage=0}
  local notes={}
  if pfail then notes[#notes+1]='내 호흡 부족 → 호흡으로 전환' end
  if efail then notes[#notes+1]='상대 호흡 부족 → 호흡으로 전환' end
  local delta=0
  local oldP,oldE=p.ropes,e.ropes
  for _,pair in ipairs({{p,e,pa},{e,p,ea}}) do
    local a,b,id=pair[1],pair[2],pair[3]
    if id=='in' then delta=delta-1
    elseif id=='out' then
      if a.ropes<2 then delta=delta+1 else notes[#notes+1]=(a==p and '내' or '상대')..' 로프에 후퇴 막힘' end
    end
  end
  p.ropes=clamp((pa=='pivot' and 0 or oldP)+(pa=='out' and oldP<2 and 1 or 0)+(ea=='in' and 1 or 0),0,2)
  e.ropes=clamp((ea=='pivot' and 0 or oldE)+(ea=='out' and oldE<2 and 1 or 0)+(pa=='in' and 1 or 0),0,2)
  m.distance=clamp(m.distance+delta,0,3)
  local tied=(pa=='clinch' or ea=='clinch') and m.distance<=1
  if tied then
    m.distance=2; p.ropes=0; e.ropes=0
    p.shock=clamp(p.shock-4,0,18); e.shock=clamp(e.shock-4,0,18)
    p.combo=''; e.combo=''; p.opening=false; e.opening=false
    notes[#notes+1]='클린치 · 공격 중단, 중앙에서 분리'
  else
    -- Both impacts are calculated from the same pre-impact state: no first-player advantage.
    local pn,pe,pt,eslip=damage(m,p,e,pa,ea)
    local en,ep,et,pslip=damage(m,e,p,ea,pa)
    trace.pDamage=pn; trace.eDamage=en
    p.hp=clamp(p.hp-en,0,p.maxhp); e.hp=clamp(e.hp-pn,0,e.maxhp)
    p.sta=clamp(p.sta-ep,0,p.maxsta); e.sta=clamp(e.sta-pe,0,e.maxsta)
    if pd.kind=='head' then e.shock=clamp(e.shock+math.floor(pn*0.55),0,18) end
    if ed.kind=='head' then p.shock=clamp(p.shock+math.floor(en*0.55),0,18) end
    p.rdDamage=p.rdDamage+pn; e.rdDamage=e.rdDamage+en
    p.damage=p.damage+pn; e.damage=e.damage+en
    if pn>0 then p.hits=p.hits+1 end if en>0 then e.hits=e.hits+1 end
    p.combo=pslip and 'slip' or (pa=='jab' and pn>0 and 'jab') or (pa=='feint' and 'feint') or ''
    e.combo=eslip and 'slip' or (ea=='jab' and en>0 and 'jab') or (ea=='feint' and 'feint') or ''
    p.opening=pa=='feint' and (ea=='guard' or ea=='low')
    e.opening=ea=='feint' and (pa=='guard' or pa=='low')
    if pt~='' then notes[#notes+1]='내 '..G.actions[pa].name..' '..pt..' '..pn end
    if et~='' then notes[#notes+1]='상대 '..G.actions[ea].name..' '..et..' '..en end
    if pa=='clinch' or ea=='clinch' then notes[#notes+1]='멀어서 클린치 실패' end
  end
  -- A knockout takes priority over recovery; shock knockdowns interrupt the remaining beats.
  if p.hp<=0 or e.hp<=0 then
    m.result={winner=p.hp<=0 and (e.hp<=0 and 'draw' or 'enemy') or 'player',method='KO'}
  else
    for _,f in ipairs({p,e}) do
      if f.shock>=18 then
        f.downs=f.downs+1; f.rdDowns=f.rdDowns+1; f.shock=0; f.combo=''; f.opening=false
        trace.down=true; notes[#notes+1]=(f==p and '내' or '상대')..' 다운 · 카운트 8에 기립'
      end
    end
    if p.downs>=3 or e.downs>=3 then
      m.result={winner=p.downs>=3 and (e.downs>=3 and 'draw' or 'enemy') or 'player',method='TKO'}
    end
    if trace.down then
      m.distance=2; p.ropes=0; e.ropes=0; p.combo=''; e.combo=''; p.opening=false; e.opening=false
    end
  end
  recover(p,pa); recover(e,ea)
  trace.distance=m.distance; trace.notes=table.concat(notes,' · ')
  if trace.notes=='' then trace.notes='서로 간격과 호흡을 조정합니다.' end
  addlog(m,'R'..m.round..' / '..m.exchange..'-'..beat..' · '..trace.notes)
  return trace
end
function G.scoreRound(m)
  local p,e=m.p,m.e
  local winner=p.rdDamage==e.rdDamage and 'draw' or (p.rdDamage>e.rdDamage and 'player' or 'enemy')
  local ps,es=10,10
  if winner=='player' then es=9 elseif winner=='enemy' then ps=9 end
  ps=math.max(7,ps-p.rdDowns); es=math.max(7,es-e.rdDowns)
  -- Normalize to the game's ten-point must card after knockdown deductions.
  if ps>es then ps=10 elseif es>ps then es=10 else ps=10; es=10 end
  m.cards[#m.cards+1]={round=m.round,p=ps,e=es,pDamage=p.rdDamage,eDamage=e.rdDamage,pDowns=p.rdDowns,eDowns=e.rdDowns}
  m.totalP=m.totalP+ps; m.totalE=m.totalE+es
end
local function record(s)
  local m=s.match
  if m.recorded then return end
  m.recorded=true
  local won=m.result.winner=='player'
  if won then s.wins=s.wins+1 else s.losses=s.losses+(m.result.winner=='enemy' and 1 or 0) end
  s.records[#s.records+1]={level=s.level,winner=m.result.winner,method=m.result.method,p=m.totalP,e=m.totalE}
  if #s.records>30 then table.remove(s.records,1) end
  if won then s.points=s.points+2 end
end
function G.execute(s)
  local m=s.match
  if not m or m.mode~='plan' or #m.plan~=3 or m.result then return false end
  for _,id in ipairs(m.plan) do if not G.actions[id] then return false end end
  m.last={}; m.lastFirst=m.plan[1]
  for i=1,3 do
    local row=G.beat(m,m.plan[i],m.intent[i],i); m.last[#m.last+1]=row
    if row.down or m.result then break end
  end
  m.turn=m.turn+1; m.plan={}; m.mode='replay'
  if m.exchange==4 or m.result then
    G.scoreRound(m)
    if not m.result and m.round==m.rounds then
      m.result={winner=m.totalP==m.totalE and 'draw' or (m.totalP>m.totalE and 'player' or 'enemy'),method='판정'}
    end
  end
  if m.result then record(s) end
  return true
end
function G.continue(s)
  local m=s.match
  if not m or m.mode~='replay' then return false end
  if m.result then s.screen='result'
  elseif m.exchange==4 then m.mode='corner'
  else m.exchange=m.exchange+1; m.mode='plan'; G.forecast(s) end
  return true
end
function G.corner(s,id)
  local m=s.match
  if not m or m.mode~='corner' or not ({ice=true,air=true,read=true})[id] then return false end
  for _,f in ipairs({m.p,m.e}) do
    f.sta=clamp(f.sta+10,0,f.maxsta); f.shock=clamp(f.shock-6,0,18)
    f.ropes=0; f.combo=''; f.opening=false; f.rdDamage=0; f.rdDowns=0
  end
  if id=='ice' then m.p.hp=clamp(m.p.hp+14,0,m.p.maxhp)
  elseif id=='air' then m.p.sta=m.p.maxsta; m.p.shock=0
  elseif id=='read' then m.p.combo='feint'; m.p.opening=true end
  m.e.hp=clamp(m.e.hp+6,0,m.e.maxhp)
  m.round=m.round+1; m.exchange=1; m.distance=2; m.mode='plan'; G.forecast(s)
  return true
end
function G.project(s)
  local m=copy(s.match); local start=m.p.sta
  local rows={}
  for i,id in ipairs(m.plan) do
    local cost=G.cost(m.p,id); local low=m.p.sta<cost
    local row=G.beat(m,id,m.intent[i],i)
    rows[#rows+1]={sta=m.p.sta,low=low}
    if m.result or row.down then break end
  end
  return rows,start
end
-- Every mutating button includes a revision. Old UI and double-clicks are harmless.
function G.reduce(s,action,value)
  local m=s.match
  s.notice=nil
  if action=='help' then s.help=not s.help; return true end
  if action=='resetAsk' then s.resetPending=true; return true end
  if action=='resetCancel' then s.resetPending=false; return true end
  if action=='resetYes' and s.resetPending then
    local n=G.new(s.seed,s.serial+1); n.revision=s.revision
    for k in pairs(s) do s[k]=nil end for k,v in pairs(n) do s[k]=v end return true
  end
  if s.resetPending then return false end
  if action=='style' and s.screen=='home' then
    for _,v in ipairs(G.styles) do if v.id==value then s.style=value; return true end end
  elseif action=='career' and s.screen=='home' then s.screen='gym'; return true
  elseif action=='train' and s.screen=='gym' and s.points>0 then
    for _,u in ipairs(G.upgrades) do if u.id==value and s.upgrades[value]<u.max then s.upgrades[value]=s.upgrades[value]+1; s.points=s.points-1; return true end end
  elseif action=='start' and s.screen=='gym' then G.start(s); return true
  elseif action=='add' and s.screen=='fight' and m.mode=='plan' and #m.plan<3 and G.actions[value] then m.plan[#m.plan+1]=value; return true
  elseif action=='undo' and s.screen=='fight' and m.mode=='plan' and #m.plan>0 then table.remove(m.plan); return true
  elseif action=='clear' and s.screen=='fight' and m.mode=='plan' then m.plan={}; return true
  elseif action=='execute' and s.screen=='fight' then return G.execute(s)
  elseif action=='continue' and s.screen=='fight' then return G.continue(s)
  elseif action=='corner' and s.screen=='fight' then return G.corner(s,value)
  elseif action=='resultNext' and s.screen=='result' and m.result then
    if m.result.winner=='player' then
      if s.level==#G.rivals then s.screen='champion' else s.level=s.level+1; s.screen='gym' end
    else s.screen='gym' end
    return true
  end
  return false
end
