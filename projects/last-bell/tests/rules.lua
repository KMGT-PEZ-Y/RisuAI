local G=LAST_BELL
local checks=0
local function eq(a,b,msg) checks=checks+1; assert(a==b,(msg or '')..': '..tostring(a)..' != '..tostring(b)) end
local function yes(v,msg) checks=checks+1; assert(v,msg) end
local function fresh()
  local s=G.new(123); G.start(s); s.match.p.style='rival'; return s,s.match
end
do local s,m=fresh(); m.distance=3; local r=G.beat(m,'hook','breathe',1); eq(r.pDamage,0,'out of range') end
do local s,m=fresh(); local r=G.beat(m,'jab','slip',1); eq(r.pDamage,0,'slip'); eq(m.e.combo,'slip')
  local rr=G.beat(m,'breathe','cross',2); eq(rr.eDamage,12,'slip counter') end
do local s,m=fresh(); m.distance=1; local r=G.beat(m,'hook','slip',1); eq(r.pDamage,11,'hook catches slip') end
do local s,m=fresh(); local r=G.beat(m,'cross','guard',1); eq(r.pDamage,2,'head block') end
do local s,m=fresh(); local r=G.beat(m,'body','guard',1); eq(r.pDamage,4); eq(m.e.sta,21,'body drain + recovery') end
do local s,m=fresh(); local r=G.beat(m,'body','low',1); eq(r.pDamage,1,'body block'); eq(m.e.sta,26,'drain block cap') end
do local s,m=fresh(); G.beat(m,'jab','breathe',1); local r=G.beat(m,'cross','breathe',2); eq(r.pDamage,12,'jab cross') end
do local s,m=fresh(); G.beat(m,'feint','guard',1); local r=G.beat(m,'cross','guard',2); eq(r.pDamage,10,'feint piercing') end
do local s,m=fresh(); G.beat(m,'feint','guard',1); G.beat(m,'breathe','guard',2); local r=G.beat(m,'cross','guard',3); eq(r.pDamage,2,'combo expires') end
do local s,m=fresh(); m.distance=1; local r=G.beat(m,'clinch','hook',1); eq(r.eDamage,0); eq(m.distance,2,'clinch') end
do local s,m=fresh(); local r=G.beat(m,'clinch','cross',1); eq(r.eDamage,8,'failed far clinch') end
do local s,m=fresh(); m.p.sta=0; local r=G.beat(m,'hook','breathe',1); eq(r.p,'breathe'); eq(m.p.sta,9,'fizzle recovers') end
do local s,m=fresh(); m.p.ropes=2; G.beat(m,'out','breathe',1); eq(m.distance,2,'rope blocks'); G.beat(m,'pivot','breathe',2); eq(m.p.ropes,0) end
do local s,m=fresh(); G.beat(m,'in','out',1); eq(m.distance,2,'simultaneous movement') end
do local s,m=fresh(); m.p.hp=4; m.e.hp=4; local r=G.beat(m,'jab','jab',1); eq(m.result.winner,'draw','double KO') end
do local s,m=fresh(); m.e.shock=17; m.plan={'cross','cross','cross'}; m.intent={'breathe','breathe','breathe'}
  G.execute(s); eq(#m.last,1,'down interrupts'); eq(m.e.downs,1); eq(m.mode,'replay') end
do local s,m=fresh(); m.e.hp=100; m.e.maxhp=100; m.e.downs=2; m.e.shock=17; m.plan={'cross','cross','cross'}; m.intent={'breathe','breathe','breathe'}
  G.execute(s); eq(m.result.method,'TKO'); eq(m.result.winner,'player'); eq(s.points,2,'reward once'); yes(not G.execute(s)); eq(s.points,2) end
do local s,m=fresh(); m.exchange=4; m.plan={'guard','guard','guard'}; m.intent={'guard','guard','guard'}
  G.execute(s); eq(#m.cards,1); G.continue(s); eq(m.mode,'corner'); yes(G.corner(s,'ice')); eq(m.round,2); eq(m.p.rdDamage,0); yes(not G.corner(s,'ice'),'no repeated corner') end
do local s,m=fresh(); m.round=m.rounds; m.exchange=4; m.totalP=10; m.totalE=9; m.plan={'guard','guard','guard'}; m.intent={'guard','guard','guard'}
  G.execute(s); eq(m.result.winner,'player','decision'); eq(m.totalP,20); eq(m.totalE,19) end
do local s,m=fresh(); m.p.rdDamage=12; m.e.rdDamage=4; m.e.rdDowns=1; G.scoreRound(m); eq(m.totalP,10); eq(m.totalE,8,'10-8 card') end
do local s=G.new(); eq(G.cost(G.fighter(100,30,0,'reader'),'slip'),2,'style cost');
  yes(not G.reduce(s,'train','power')); s.screen='gym'; s.points=4
  for i=1,3 do yes(G.reduce(s,'train','power')) end yes(not G.reduce(s,'train','power')); eq(s.points,1,'upgrade cap') end
-- Symmetry: every pair of legal actions at every distance, including rope edges.
for d=0,3 do for rope=0,2 do for _,a in ipairs(G.order) do for _,b in ipairs(G.order) do
  local s,m=fresh(); m.distance=d; m.p.ropes=rope; m.e.ropes=1
  m.e=G.copy(m.p); m.e.ropes=1
  local n=G.copy(m); n.p,n.e=G.copy(m.e),G.copy(m.p)
  G.beat(m,a,b,1); G.beat(n,b,a,1)
  eq(m.p.hp,n.e.hp,'symmetric HP'); eq(m.p.sta,n.e.sta,'symmetric breath'); eq(m.distance,n.distance,'symmetric distance'); eq(m.p.ropes,n.e.ropes,'symmetric ropes')
end end end end
-- Fuzz full matches. All state stays finite and every match terminates.
local fuzz={player=0,enemy=0,draw=0}
math.randomseed(88021)
for i=1,300 do
  local s=G.new(i*31); s.level=(i-1)%5+1; s.style=G.styles[(i-1)%3+1].id; G.start(s)
  local m=s.match; local count=0
  while not m.result do
    if m.mode=='plan' then
      m.plan={G.order[math.random(#G.order)],G.order[math.random(#G.order)],G.order[math.random(#G.order)]}
      yes(G.execute(s)); count=count+1
    elseif m.mode=='replay' then G.continue(s)
    else G.corner(s,({'ice','air','read'})[math.random(3)]) end
    for _,f in ipairs({m.p,m.e}) do
      yes(f.hp>=0 and f.hp<=f.maxhp); yes(f.sta>=0 and f.sta<=f.maxsta); yes(f.shock>=0 and f.shock<=18)
      yes(f.ropes>=0 and f.ropes<=2); yes(f.downs<=3)
    end
    yes(m.distance>=0 and m.distance<=3); yes(count<=m.rounds*4,'bounded match')
  end
  fuzz[m.result.winner]=fuzz[m.result.winner]+1
end
RULE_RESULTS={checks=checks,fuzzMatches=300,fuzz=fuzz}

-- Independent candidate planner for solvability and a full campaign smoke test.
local function choose(s)
  local base=s.match; local best=-1e9; local plan
  for _,a in ipairs(G.order) do for _,b in ipairs(G.order) do for _,c in ipairs(G.order) do
    local m=G.copy(base)
    for i,id in ipairs({a,b,c}) do local r=G.beat(m,id,m.intent[i],i); if r.down or m.result then break end end
    local val=(base.e.hp-m.e.hp)*1.35-(base.p.hp-m.p.hp)*1.6+(m.p.sta-base.p.sta)*.23-(m.e.sta-base.e.sta)*.15
      +(m.e.shock-base.e.shock)*.25-(m.p.shock-base.p.shock)*.4+(m.e.downs-base.e.downs)*10-(m.p.downs-base.p.downs)*16
      -m.p.ropes*.3-math.abs(m.distance-2)*.1
    if m.result then val=val+(m.result.winner=='player' and 1000 or m.result.winner=='enemy' and -1000 or -200) end
    if val>best then best=val; plan={a,b,c} end
  end end end
  return plan
end
G.testChoose=choose
