-- BattleSim for RisuAI
-- Port of battle_sim_poc/battle_sim.py (1v1, no-skill POC).

local STATE_KEY = 'battle_sim_state_v1'
local ACTIONS = { 'attack', 'defend', 'evade' }
local ACTION_LABEL = { attack = '공격', defend = '방어', evade = '회피' }

local function delta(hp, stamina, breakGauge)
  return { hp = hp or 0, stamina = stamina or 0, breakGauge = breakGauge or 0 }
end

local function entry(id, ph, ps, pb, eh, es, eb)
  return { id = id, player = delta(ph, ps, pb), enemy = delta(eh, es, eb) }
end

local RESULT_TABLE = {}
local function resultKey(a, b, dice) return a .. ':' .. b .. ':' .. dice end
local function addResult(a, b, dice, value) RESULT_TABLE[resultKey(a, b, dice)] = value end

addResult('attack','attack','win',  entry('01',-10,-7,12,-28,-16,22))
addResult('attack','attack','draw', entry('02',-36,-20,24,-36,-20,24))
addResult('attack','attack','lose', entry('03',-28,-16,22,-10,-7,12))
addResult('attack','defend','win',  entry('04',0,0,0,-28,-16,20))
addResult('attack','defend','draw', entry('05',0,-10,14,8,14,-12))
addResult('attack','defend','lose', entry('06',0,-16,20,12,22,-18))
addResult('attack','evade','win',   entry('07',0,0,0,-36,-18,22))
addResult('attack','evade','draw',  entry('08',0,0,0,-24,-12,16))
addResult('attack','evade','lose',  entry('09',-32,0,24,0,0,0))
addResult('defend','attack','win',  entry('10',12,22,-18,0,-16,20))
addResult('defend','attack','draw', entry('11',8,14,-12,0,-10,14))
addResult('defend','attack','lose', entry('12',-28,-16,20,0,0,0))
addResult('defend','defend','win',  entry('13',10,18,-16,4,8,-8))
addResult('defend','defend','draw', entry('14',0,0,35,0,0,35))
addResult('defend','defend','lose', entry('15',4,8,-8,10,18,-16))
addResult('defend','evade','win',   entry('16',10,18,-16,-12,0,10))
addResult('defend','evade','draw',  entry('17',-24,0,18,0,0,0))
addResult('defend','evade','lose',  entry('18',-40,0,28,0,0,0))
addResult('evade','attack','win',   entry('19',0,0,0,-32,0,24))
addResult('evade','attack','draw',  entry('20',-24,-12,16,0,0,0))
addResult('evade','attack','lose',  entry('21',-36,-18,22,0,0,0))
addResult('evade','defend','win',   entry('22',0,0,0,-40,0,28))
addResult('evade','defend','draw',  entry('23',0,0,0,-24,0,18))
addResult('evade','defend','lose',  entry('24',-12,0,10,10,18,-16))
addResult('evade','evade','win',    entry('25',0,0,0,-20,0,18))
addResult('evade','evade','draw',   entry('26',0,-30,0,0,-30,0))
addResult('evade','evade','lose',   entry('27',-20,0,18,0,0,0))

local GROGGY_TABLE = {
  attack = entry('G01',0,0,0,-42,-24,33),
  defend = entry('G02',15,27,-24,0,0,0),
  evade = entry('G03',0,0,0,-30,0,27),
}

local NPCS = {
  { id='rookie_cycle', name='훈련생', difficulty='쉬움' },
  { id='rookie_guard', name='초보 가드', difficulty='쉬움' },
  { id='reckless_raider', name='무모한 습격자', difficulty='쉬움' },
  { id='balanced_soldier', name='균형 잡힌 병사', difficulty='보통' },
  { id='veteran_guard', name='베테랑 가드', difficulty='보통' },
  { id='cautious_hunter', name='신중한 사냥꾼', difficulty='보통' },
  { id='pressure', name='압박가', difficulty='어려움' },
  { id='adaptive', name='적응형 전사', difficulty='어려움' },
  { id='tactical_evaluator', name='전술 평가자', difficulty='어려움' },
  { id='weighted_analyst', name='가중 분석가', difficulty='매우 어려움' },
  { id='regret_duelist', name='후회 결투가', difficulty='매우 어려움*' },
  { id='executor', name='처형자', difficulty='매우 어려움' },
}

local function clamp(value, minimum, maximum)
  return math.max(minimum, math.min(maximum, value))
end

local function newRng(seed)
  seed = math.floor(tonumber(seed) or 1) % 2147483647
  if seed <= 0 then seed = seed + 2147483646 end
  return { state = seed }
end

local function randomFloat(rng)
  rng.state = (rng.state * 48271) % 2147483647
  return rng.state / 2147483647
end

local function randomInt(rng, low, high)
  return low + math.floor(randomFloat(rng) * (high - low + 1))
end

local function randomChoice(rng, values)
  return values[randomInt(rng, 1, #values)]
end

local function weightedAction(weights, rng)
  local total = 0
  for _, action in ipairs(ACTIONS) do total = total + math.max(0, weights[action] or 0) end
  if total <= 0 then return 'attack' end
  local pick, sum = randomFloat(rng) * total, 0
  for _, action in ipairs(ACTIONS) do
    sum = sum + math.max(0, weights[action] or 0)
    if pick <= sum then return action end
  end
  return 'evade'
end

local function newCharacter(name)
  return {
    name=name, maxHp=100, maxStamina=100, maxBreakGauge=100, maxDownCount=3,
    hp=100, stamina=100, breakGauge=0, downCount=0, skippedTurnsRemaining=0,
    isDown=false, isGroggy=false, isKo=false, statuses={},
  }
end

local function pushLog(state, text)
  state.log = state.log or {}
  table.insert(state.log, text)
  while #state.log > 18 do table.remove(state.log, 1) end
end

local function countRecent(history, limit)
  local counts = { attack=0, defend=0, evade=0 }
  local first = math.max(1, #history - limit + 1)
  for i=first,#history do counts[history[i]] = counts[history[i]] + 1 end
  return counts
end

local COUNTER = { attack='defend', defend='evade', evade='attack' }

local function opponentDistribution(context, limit, blend, decay)
  decay = decay or 1
  local observed, total = {attack=0,defend=0,evade=0}, 0
  local first = math.max(1, #context.opponentHistory - limit + 1)
  for i=#context.opponentHistory,first,-1 do
    local weight = decay ^ (#context.opponentHistory - i)
    observed[context.opponentHistory[i]] = observed[context.opponentHistory[i]] + weight
    total = total + weight
  end
  if total == 0 then return {attack=1/3,defend=1/3,evade=1/3} end
  local base = (1-blend)/3
  return {
    attack=base + blend*observed.attack/total,
    defend=base + blend*observed.defend/total,
    evade=base + blend*observed.evade/total,
  }
end

local function deltaScore(value)
  local own, opponent = value.player, value.enemy
  return math.max(0,-opponent.hp) - math.max(0,opponent.hp)*0.8
    + math.max(0,own.hp)*0.8 - math.max(0,-own.hp)*1.1
    + math.max(0,-opponent.stamina)*0.2 - math.max(0,opponent.stamina)*0.1
    + math.max(0,own.stamina)*0.1 - math.max(0,-own.stamina)*0.15
    + math.max(0,opponent.breakGauge)*0.4 - math.max(0,-opponent.breakGauge)*0.25
    + math.max(0,-own.breakGauge)*0.35 - math.max(0,own.breakGauge)*0.45
end

local function adjustedScore(context, value, awareness, successor)
  local score = deltaScore(value)
  local ohp = context.own.hp + value.player.hp
  local ehp = context.opponent.hp + value.enemy.hp
  local obr = context.own.breakGauge + value.player.breakGauge
  local ebr = context.opponent.breakGauge + value.enemy.breakGauge
  if ehp <= 0 then score = score + awareness * (context.opponent.downCount >= 2 and 120 or 28) end
  if ohp <= 0 then score = score - awareness * (context.own.downCount >= 2 and 150 or 35) end
  if ebr >= 100 then score = score + awareness*16 end
  if obr >= 100 then score = score - awareness*20 end
  if context.own.hp <= context.own.maxHp*0.35 then
    score = score + math.max(0,value.player.hp)*awareness*0.6
      - math.max(0,-value.player.hp)*awareness*0.35
  end
  if context.opponent.hp <= context.opponent.maxHp*0.35 then
    score = score + math.max(0,-value.enemy.hp)*awareness*0.45
  end
  if successor then
    if ebr >= 100 and ehp > 0 then score = score + 12 end
    if obr >= 100 and ohp > 0 then score = score - 15 end
    if context.turnInRound >= 7 then
      if value.enemy.breakGauge > 0 and ebr < 100 then score = score-value.enemy.breakGauge*0.18 end
      if value.player.breakGauge > 0 and obr < 100 then score = score+value.player.breakGauge*0.16 end
    end
  end
  return score
end

local DICE_PROB = { win=15/36, draw=6/36, lose=15/36 }
local function scoredAction(context, distribution, temperature, awareness, successor, rng)
  local scores, highest = {}, -math.huge
  for _, action in ipairs(ACTIONS) do
    local score = 0
    for _, opponentAction in ipairs(ACTIONS) do
      for _, dice in ipairs({'win','draw','lose'}) do
        score = score + distribution[opponentAction]*DICE_PROB[dice]
          * adjustedScore(context, RESULT_TABLE[resultKey(action,opponentAction,dice)], awareness, successor)
      end
    end
    scores[action] = score
    highest = math.max(highest, score)
  end
  local weights = {}
  for _, action in ipairs(ACTIONS) do weights[action] = math.exp((scores[action]-highest)/temperature) end
  return weightedAction(weights, rng)
end

local function chooseAction(strategy, context, rng)
  if strategy == 'random' then return randomChoice(rng, ACTIONS) end
  if strategy == 'attack' then return 'attack' end
  if strategy == 'evade' then return 'evade' end
  if strategy == 'cycle' or strategy == 'rookie_cycle' then return ACTIONS[(#context.ownHistory % 3)+1] end
  if strategy == 'reckless_raider' then
    if context.own.breakGauge >= 80 then return 'defend' end
    return ({'attack','attack','defend'})[(#context.ownHistory%3)+1]
  end
  if strategy == 'balanced_soldier' then
    if context.opponent.isGroggy then return weightedAction({attack=.6,defend=.1,evade=.3},rng) end
    local weights={attack=1,defend=1,evade=1}
    if context.own.breakGauge >= 80 then weights={attack=.25,defend=.5,evade=.25} end
    if #context.ownHistory >= 2 and context.ownHistory[#context.ownHistory] == context.ownHistory[#context.ownHistory-1] then
      weights[context.ownHistory[#context.ownHistory]]=0
    end
    return weightedAction(weights,rng)
  end
  if strategy == 'defensive' then
    if context.opponent.isGroggy then return 'attack' end
    if context.own.hp <= 35 or context.own.breakGauge >= 75 then return 'defend' end
    if context.opponent.hp <= 35 or context.opponent.breakGauge >= 75 then return 'attack' end
    return 'evade'
  end
  if strategy == 'pressure' then
    if context.opponent.isGroggy or context.opponent.hp <= 45 or context.opponent.breakGauge >= 60 then return 'attack' end
    if context.own.hp < 55 and context.own.breakGauge >= 80 then return 'defend' end
    return 'evade'
  end
  if strategy == 'cautious_hunter' then
    if context.opponent.isGroggy then return weightedAction({attack=.7,evade=.3},rng) end
    local w={attack=.35,defend=.3,evade=.35}
    if context.opponent.hp <= 30 then w.attack=w.attack+.6 end
    if context.opponent.breakGauge >= 75 then w.attack=w.attack+.7 end
    if context.own.hp <= 30 then w.defend=w.defend+.6 end
    if context.own.breakGauge >= 80 then w.defend=w.defend+.7 end
    return weightedAction(w,rng)
  end
  if strategy == 'adaptive' then
    if context.opponent.isGroggy then return 'attack' end
    if #context.opponentHistory == 0 then return randomChoice(rng,ACTIONS) end
    local counts=countRecent(context.opponentHistory,6)
    local best={}; local high=math.max(counts.attack,counts.defend,counts.evade)
    for _,a in ipairs(ACTIONS) do if counts[a]==high then table.insert(best,a) end end
    return COUNTER[randomChoice(rng,best)]
  end
  if strategy == 'tactical_evaluator' then return scoredAction(context,opponentDistribution(context,6,.6),10,.65,false,rng) end
  if strategy == 'weighted_analyst' then return scoredAction(context,opponentDistribution(context,10,.8,.85),6,1,false,rng) end
  if strategy == 'executor' then return scoredAction(context,opponentDistribution(context,10,.85,.82),3.5,1.35,true,rng) end
  if strategy == 'regret_duelist' then
    if #context.exchanges == 0 then return randomChoice(rng,ACTIONS) end
    local regrets={attack=0,defend=0,evade=0}; local first=math.max(1,#context.exchanges-19)
    for i=first,#context.exchanges do
      local x=context.exchanges[i]; local dice=x.ownDie>x.opponentDie and 'win' or (x.ownDie<x.opponentDie and 'lose' or 'draw')
      local actual=deltaScore(RESULT_TABLE[resultKey(x.ownAction,x.opponentAction,dice)])
      for _,a in ipairs(ACTIONS) do regrets[a]=regrets[a]+deltaScore(RESULT_TABLE[resultKey(a,x.opponentAction,dice)])-actual end
    end
    return weightedAction({attack=1+math.max(0,regrets.attack),defend=1+math.max(0,regrets.defend),evade=1+math.max(0,regrets.evade)},rng)
  end
  local ratios={
    guard_evade_ratio={defend=.55,evade=.45}, guard_attack_ratio={defend=.55,attack=.45},
    guard_mixed_ratio={defend=.45,attack=.3,evade=.25}, rookie_guard={defend=.45,attack=.3,evade=.25},
  }
  if ratios[strategy] then return weightedAction(ratios[strategy],rng) end
  local adaptive={
    guard_evade_adaptive={defend=.55,evade=.45}, guard_attack_adaptive={defend=.55,attack=.45},
    guard_mixed_adaptive={defend=.45,attack=.3,evade=.25}, veteran_guard={defend=.45,attack=.3,evade=.25},
  }
  local w=adaptive[strategy]
  if w then
    local weights={attack=w.attack,defend=w.defend,evade=w.evade}
    if context.opponent.isGroggy then return weights.attack and 'attack' or 'evade' end
    if context.own.hp<=35 or context.own.breakGauge>=75 then weights.defend=(weights.defend or 0)+.35 end
    if #context.opponentHistory>0 then
      local counts=countRecent(context.opponentHistory,6); local high=math.max(counts.attack,counts.defend,counts.evade); local best={}
      for _,a in ipairs(ACTIONS) do if counts[a]==high then table.insert(best,a) end end
      local counter=COUNTER[randomChoice(rng,best)]
      if weights[counter] then weights[counter]=weights[counter]+.5
      else weights[strategy=='guard_evade_adaptive' and 'evade' or (strategy=='guard_attack_adaptive' and 'attack' or 'defend')]=(weights[strategy=='guard_evade_adaptive' and 'evade' or (strategy=='guard_attack_adaptive' and 'attack' or 'defend')] or 0)+.5 end
    end
    return weightedAction(weights,rng)
  end
  return 'attack'
end

local function makeState(strategy, seed)
  seed = math.floor(tonumber(seed) or 20260830)
  return {
    version=1, phase='battle', outcome=false, winner=false, strategy=strategy or 'balanced_soldier', seed=seed,
    roundNumber=1, turnInRound=0, matchTurn=0, maxRounds=100,
    player=newCharacter('Player'), enemy=newCharacter('Enemy'),
    playerPortrait='player.png', enemyPortrait=(strategy or 'balanced_soldier')..'.png',
    battleRng=newRng(seed), playerPolicyRng=newRng(seed+1000003), enemyPolicyRng=newRng(seed+2000003),
    histories={player={},enemy={}}, exchanges={player={},enemy={}}, log={},
    presentation=false, presentationSequence=0, pendingInterval=false,
  }
end

local function contextFor(state, side)
  local own = side=='player' and state.player or state.enemy
  local opponent = side=='player' and state.enemy or state.player
  return { own=own, opponent=opponent, ownHistory=state.histories[side], opponentHistory=state.histories[side=='player' and 'enemy' or 'player'],
    exchanges=state.exchanges[side], roundNumber=state.roundNumber, turnInRound=state.turnInRound, matchTurn=state.matchTurn }
end

local function applyDelta(character, value)
  character.hp=clamp(character.hp+value.hp,0,character.maxHp)
  character.stamina=clamp(character.stamina+value.stamina,0,character.maxStamina)
  character.breakGauge=clamp(character.breakGauge+value.breakGauge,0,character.maxBreakGauge)
end

local function snapshot(character)
  return {
    hp=character.hp, stamina=character.stamina, breakGauge=character.breakGauge,
    downCount=character.downCount, isDown=character.isDown, isGroggy=character.isGroggy, isKo=character.isKo,
  }
end

local function actualDelta(before, after)
  return {
    hp=after.hp-before.hp,
    stamina=after.stamina-before.stamina,
    breakGauge=after.breakGauge-before.breakGauge,
  }
end

local function hitSeverity(amount)
  local damage=math.max(0,-amount)
  if damage>=28 then return 'heavy' end
  if damage>=13 then return 'medium' end
  if damage>0 then return 'light' end
  return false
end

local function setPresentation(state, kind, beforePlayer, beforeEnemy, details)
  details=details or {}
  state.presentationSequence=(state.presentationSequence or 0)+1
  local afterPlayer=snapshot(state.player); local afterEnemy=snapshot(state.enemy)
  local playerDelta=actualDelta(beforePlayer,afterPlayer); local enemyDelta=actualDelta(beforeEnemy,afterEnemy)
  state.presentation={
    sequenceId=state.presentationSequence, kind=kind, entryId=details.entryId,
    playerAction=details.playerAction, enemyAction=details.enemyAction,
    playerDie=details.playerDie, enemyDie=details.enemyDie, diceResult=details.diceResult,
    playerDelta=playerDelta, enemyDelta=enemyDelta,
    playerEffect=details.playerEffect or playerDelta, enemyEffect=details.enemyEffect or enemyDelta,
    playerHit=hitSeverity((details.playerEffect or playerDelta).hp), enemyHit=hitSeverity((details.enemyEffect or enemyDelta).hp),
    playerEnteredGroggy=not beforePlayer.isGroggy and afterPlayer.isGroggy,
    enemyEnteredGroggy=not beforeEnemy.isGroggy and afterEnemy.isGroggy,
    playerEnteredDown=not beforePlayer.isDown and afterPlayer.isDown,
    enemyEnteredDown=not beforeEnemy.isDown and afterEnemy.isDown,
    playerEnteredKo=not beforePlayer.isKo and afterPlayer.isKo,
    enemyEnteredKo=not beforeEnemy.isKo and afterEnemy.isKo,
    playerWoke=beforePlayer.isDown and not afterPlayer.isDown,
    enemyWoke=beforeEnemy.isDown and not afterEnemy.isDown,
    outcome=state.outcome,
  }
end

local function wake(character)
  character.isDown=false; character.skippedTurnsRemaining=0
  character.hp=math.floor(character.maxHp*.5); character.breakGauge=math.floor(character.maxBreakGauge*.5); character.isGroggy=false
end

local function afterResources(state)
  for _,character in ipairs({state.player,state.enemy}) do
    if not character.isGroggy and not character.isDown and not character.isKo and character.breakGauge>=character.maxBreakGauge then character.isGroggy=true end
  end
  local newly=0
  for _,character in ipairs({state.player,state.enemy}) do
    if character.hp<=0 and not character.isDown and not character.isKo then
      newly=newly+1; character.downCount=character.downCount+1
      if character.downCount>=character.maxDownCount then character.isKo=true
      else character.isDown=true; character.skippedTurnsRemaining=character.downCount end
    end
  end
  if state.player.isKo and state.enemy.isKo then state.outcome='DOUBLE_KO'
  elseif state.player.isKo then state.outcome='ENEMY_WIN'; state.winner=state.enemy.name
  elseif state.enemy.isKo then state.outcome='PLAYER_WIN'; state.winner=state.player.name end
end

local function finishRound(state)
  for _,c in ipairs({state.player,state.enemy}) do
    if c.isDown and not c.isKo then wake(c) end
    if not c.isKo then
      c.hp=math.min(c.maxHp,c.hp+math.floor(c.maxHp*.33)); c.stamina=math.min(c.maxStamina,c.stamina+math.floor(c.maxStamina*.5))
      c.breakGauge=math.floor(c.breakGauge*.5); c.isGroggy=false
      local kept={}; for _,status in ipairs(c.statuses or {}) do status.remainingTurns=status.remainingTurns-2; if status.remainingTurns>0 then table.insert(kept,status) end end; c.statuses=kept
    end
  end
  pushLog(state,string.format('라운드 %d 인터벌: HP 33%% / STA 50%% 회복, BRK 절반.',state.roundNumber))
  state.roundNumber=state.roundNumber+1; state.turnInRound=0
end

local function tickStatuses(state)
  for _,c in ipairs({state.player,state.enemy}) do
    local kept={}; for _,status in ipairs(c.statuses or {}) do
      if (status.appliedOnMatchTurn or 0)<state.matchTurn then status.remainingTurns=status.remainingTurns-1 end
      if status.remainingTurns>0 then table.insert(kept,status) end
    end; c.statuses=kept
  end
end

local function playTurn(state, submittedAction)
  if state.outcome then return end
  if state.roundNumber>state.maxRounds then state.outcome='STALEMATE'; return end
  local beforePlayer=snapshot(state.player); local beforeEnemy=snapshot(state.enemy)
  local details={}
  state.matchTurn=state.matchTurn+1; state.turnInRound=state.turnInRound+1
  if state.player.isDown or state.enemy.isDown then
    if state.player.isDown and not state.enemy.isDown then state.enemy.hp=math.min(state.enemy.maxHp,state.enemy.hp+math.floor(state.enemy.maxHp*.04)) end
    if state.enemy.isDown and not state.player.isDown then state.player.hp=math.min(state.player.maxHp,state.player.hp+math.floor(state.player.maxHp*.04)) end
    for _,c in ipairs({state.player,state.enemy}) do if c.isDown then c.skippedTurnsRemaining=c.skippedTurnsRemaining-1; if c.skippedTurnsRemaining<=0 then wake(c) end end end
    pushLog(state,string.format('T%d 다운 대기 턴.',state.matchTurn))
    details.kind='down_wait'
  elseif state.player.isGroggy or state.enemy.isGroggy then
    if state.player.isGroggy and state.enemy.isGroggy then
      pushLog(state,string.format('T%d 양측 그로기.',state.matchTurn)); details.kind='both_groggy'
    else
      local actorSide=state.enemy.isGroggy and 'player' or 'enemy'; local actor=actorSide=='player' and state.player or state.enemy; local target=actorSide=='player' and state.enemy or state.player
      local action=actorSide=='player' and submittedAction or chooseAction(state.strategy,contextFor(state,'enemy'),state.enemyPolicyRng)
      if not action then state.matchTurn=state.matchTurn-1; state.turnInRound=state.turnInRound-1; return false end
      table.insert(state.histories[actorSide],action); local value=GROGGY_TABLE[action]
      applyDelta(actor,value.player); applyDelta(target,value.enemy); afterResources(state)
      pushLog(state,string.format('T%d %s → 그로기 %s [%s].',state.matchTurn,ACTION_LABEL[action],target.name,value.id))
      details.kind='groggy'; details.entryId=value.id
      if actorSide=='player' then
        details.playerAction=action; details.playerEffect=value.player; details.enemyEffect=value.enemy
      else
        details.enemyAction=action; details.enemyEffect=value.player; details.playerEffect=value.enemy
      end
    end
  else
    if not submittedAction then state.matchTurn=state.matchTurn-1; state.turnInRound=state.turnInRound-1; return false end
    local enemyAction=chooseAction(state.strategy,contextFor(state,'enemy'),state.enemyPolicyRng)
    table.insert(state.histories.player,submittedAction); table.insert(state.histories.enemy,enemyAction)
    local pd=randomInt(state.battleRng,1,6); local ed=randomInt(state.battleRng,1,6); local dice=pd>ed and 'win' or (pd<ed and 'lose' or 'draw')
    local value=RESULT_TABLE[resultKey(submittedAction,enemyAction,dice)]
    table.insert(state.exchanges.player,{ownAction=submittedAction,opponentAction=enemyAction,ownDie=pd,opponentDie=ed})
    table.insert(state.exchanges.enemy,{ownAction=enemyAction,opponentAction=submittedAction,ownDie=ed,opponentDie=pd})
    applyDelta(state.player,value.player); applyDelta(state.enemy,value.enemy); afterResources(state)
    pushLog(state,string.format('T%d %s vs %s · %d:%d [%s].',state.matchTurn,ACTION_LABEL[submittedAction],ACTION_LABEL[enemyAction],pd,ed,value.id))
    details.kind='normal'; details.entryId=value.id; details.playerAction=submittedAction; details.enemyAction=enemyAction
    details.playerDie=pd; details.enemyDie=ed; details.diceResult=dice
    details.playerEffect=value.player; details.enemyEffect=value.enemy
  end
  tickStatuses(state)
  setPresentation(state,details.kind or 'turn',beforePlayer,beforeEnemy,details)
  if not state.outcome and state.turnInRound>=8 then state.pendingInterval=true end
  return true
end

local function playerCanChoose(state)
  return not state.outcome and not state.player.isDown and not state.player.isGroggy and not state.enemy.isDown
end

local function presentInterval(state)
  local beforePlayer=snapshot(state.player); local beforeEnemy=snapshot(state.enemy)
  finishRound(state)
  setPresentation(state,'interval',beforePlayer,beforeEnemy,{})
end

local function advancePresentation(state)
  state.presentation=false
  if state.outcome then return end
  if state.pendingInterval then
    state.pendingInterval=false; presentInterval(state); return
  end
  if not playerCanChoose(state) then playTurn(state,nil) end
end

local function esc(value)
  return tostring(value):gsub('&','&amp;'):gsub('<','&lt;'):gsub('>','&gt;'):gsub('"','&quot;')
end

local function bar(label,value,maximum,color)
  local percent=math.floor(100*value/maximum)
  return string.format('<div class="bsim-meter"><div class="bsim-meter-label"><span>%s</span><span>%d / %d</span></div><div class="bsim-meter-track"><i class="bsim-meter-fill bsim-meter-%s" style="width:%d%%"></i></div></div>',label,value,maximum,color,percent)
end

local function signed(value)
  if value>0 then return '+'..value end
  return tostring(value)
end

local function renderDeltas(presentation,side)
  if not presentation then return '' end
  local values=side=='player' and presentation.playerDelta or presentation.enemyDelta
  if not values then return '' end
  local parts={'<div class="bsim-float-deltas">'}
  for _,item in ipairs({{'HP','hp'},{'STA','stamina'},{'BRK','breakGauge'}}) do
    local value=values[item[2]] or 0
    if value~=0 then
      local direction=value>0 and 'positive' or 'negative'
      table.insert(parts,string.format('<span class="bsim-delta bsim-delta-%s bsim-delta-%s">%s %s</span>',item[2],direction,item[1],signed(value)))
    end
  end
  table.insert(parts,'</div>'); return table.concat(parts)
end

local function outcomeRole(outcome,side)
  if not outcome then return false,false end
  if outcome=='PLAYER_WIN' then return side=='player' and 'winner' or 'loser',side=='player' and 'WIN' or 'LOSE' end
  if outcome=='ENEMY_WIN' then return side=='enemy' and 'winner' or 'loser',side=='enemy' and 'WIN' or 'LOSE' end
  if outcome=='DOUBLE_KO' then return 'double-ko','DOUBLE KO' end
  return 'draw','STALEMATE'
end

local function assetBase(state,side)
  if side=='player' then return 'player' end
  return state.strategy or 'enemy'
end

local function assetPath(state,side,suffix)
  return assetBase(state,side)..'_'..suffix..'.png'
end

local function downStage(character)
  return math.max(0,math.min(2,character.downCount or 0))
end

local function hpBand(character)
  local ratio=character.maxHp>0 and character.hp/character.maxHp or 0
  if ratio>.60 then return 'healthy' end
  if ratio>.30 then return 'wounded' end
  return 'critical'
end

local function mainPortraitPath(state,side)
  local character=side=='player' and state.player or state.enemy
  local role=outcomeRole(state.outcome,side)
  if state.outcome and not state.presentation and (role=='winner' or role=='loser' or role=='double-ko') then
    return assetPath(state,side,role=='winner' and 'result_win' or 'result_lose')
  end
  if state.presentation and state.presentation.kind=='interval' then
    return assetPath(state,side,'interval_d'..downStage(character))
  end
  if character.isKo then return assetPath(state,side,'ko') end
  if character.isDown then return assetPath(state,side,'down_d'..math.max(1,downStage(character))) end
  return assetPath(state,side,string.format('main_d%d_%s',downStage(character),hpBand(character)))
end

local SPECIAL_RESOLVE_SUFFIX={['02']='resolve_cross_clash',['14']='resolve_clinch',['26']='resolve_standoff'}

local function actionPortraitPath(state,side,presentation)
  local action=side=='player' and presentation.playerAction or presentation.enemyAction
  if not action then return false end
  return assetPath(state,side,'action_'..action)
end

local function resolvePortraitPath(state,side,presentation)
  if SPECIAL_RESOLVE_SUFFIX[presentation.entryId] then return assetPath(state,side,SPECIAL_RESOLVE_SUFFIX[presentation.entryId]) end
  local action=side=='player' and presentation.playerAction or presentation.enemyAction
  if not action then return false end
  local own=side=='player' and presentation.playerEffect or presentation.enemyEffect
  local opponent=side=='player' and presentation.enemyEffect or presentation.playerEffect
  own=own or {}; opponent=opponent or {}
  local suffix
  if action=='attack' then suffix=(opponent.hp or 0)<0 and 'resolve_attack_success' or 'resolve_attack_failed'
  elseif action=='defend' then suffix=(own.hp or 0)<0 and 'resolve_guard_broken' or 'resolve_defend_success'
  elseif action=='evade' then suffix=(own.hp or 0)<0 and 'resolve_evade_caught' or 'resolve_evade_success' end
  return suffix and assetPath(state,side,suffix) or false
end

local function effectReactionPath(state,side,presentation)
  local hit=side=='player' and presentation.playerHit or presentation.enemyHit
  if hit then return assetPath(state,side,'reaction_hit_'..hit) end
  local effect=side=='player' and presentation.playerEffect or presentation.enemyEffect
  effect=effect or {}
  if (effect.breakGauge or 0)>0 then return assetPath(state,side,'reaction_break_shaken') end
  if (effect.stamina or 0)<0 then return assetPath(state,side,'reaction_stamina_drained') end
  if (effect.hp or 0)>0 or (effect.stamina or 0)>0 or (effect.breakGauge or 0)<0 then
    return assetPath(state,side,'reaction_recover')
  end
  return false
end

local function statusReactionPath(state,side,presentation)
  local character=side=='player' and state.player or state.enemy
  local groggy=side=='player' and presentation.playerEnteredGroggy or presentation.enemyEnteredGroggy
  local woke=side=='player' and presentation.playerWoke or presentation.enemyWoke
  if groggy then return assetPath(state,side,'reaction_groggy') end
  if woke then return assetPath(state,side,'reaction_wake_d'..math.max(1,downStage(character))) end
  return false
end

local function finalResultPath(state,side,presentation)
  if not presentation.outcome then return false end
  local role=outcomeRole(presentation.outcome,side)
  if role=='winner' then return assetPath(state,side,'result_win') end
  if role=='loser' or role=='double-ko' then return assetPath(state,side,'result_lose') end
  return false
end

local function cinematicImage(path,className)
  if not path then return '' end
  return '<img class="bsim-cinematic-image '..className..'" src="{{raw::'..esc(path)..'}}" alt="" loading="eager" decoding="sync">'
end

local function renderCinematicActor(state,side,presentation)
  local parts={'<div class="bsim-cinematic-actor bsim-cinematic-'..side..'">'}
  table.insert(parts,cinematicImage(actionPortraitPath(state,side,presentation),'bsim-cinematic-action'))
  table.insert(parts,cinematicImage(resolvePortraitPath(state,side,presentation),'bsim-cinematic-resolve'))
  table.insert(parts,cinematicImage(effectReactionPath(state,side,presentation),'bsim-cinematic-effect'))
  table.insert(parts,cinematicImage(statusReactionPath(state,side,presentation),'bsim-cinematic-state'))
  table.insert(parts,'</div>'); return table.concat(parts)
end

local function renderActionPreload(state)
  local parts={'<div class="bsim-asset-preload" aria-hidden="true">'}
  for _,side in ipairs({'player','enemy'}) do
    for _,action in ipairs(ACTIONS) do
      local path=assetPath(state,side,'action_'..action)
      table.insert(parts,'<img src="{{raw::'..esc(path)..'}}" alt="" loading="eager">')
    end
  end
  table.insert(parts,'</div>'); return table.concat(parts)
end

local function renderCharacter(state,side)
  local character=side=='player' and state.player or state.enemy
  local presentation=state.presentation
  local title=side=='player' and '플레이어' or ('적 · '..state.strategy)
  local portrait=mainPortraitPath(state,side)
  local initial=side=='player' and 'P' or 'E'
  local classes={'bsim-unit','bsim-unit-'..side}
  if character.hp<=character.maxHp*.15 and not character.isKo then table.insert(classes,'is-critical')
  elseif character.hp<=character.maxHp*.35 and not character.isKo then table.insert(classes,'is-danger') end
  if character.breakGauge>=character.maxBreakGauge*.75 and not character.isKo then table.insert(classes,'is-break-danger') end
  if character.isGroggy then table.insert(classes,'is-groggy') end
  if character.isDown then table.insert(classes,'is-down') end
  if character.isKo then table.insert(classes,'is-ko') end
  local hit=presentation and (side=='player' and presentation.playerHit or presentation.enemyHit)
  if hit then table.insert(classes,'is-hit-'..hit) end
  local role,resultLabel=outcomeRole(state.outcome,side)
  if role then table.insert(classes,'is-'..role) end
  local enteredGroggy=presentation and (side=='player' and presentation.playerEnteredGroggy or presentation.enemyEnteredGroggy)
  local enteredDown=presentation and (side=='player' and presentation.playerEnteredDown or presentation.enemyEnteredDown)
  local finalPortrait=presentation and finalResultPath(state,side,presentation) or false
  local tags={}
  if character.isGroggy then table.insert(tags,'<span class="bsim-condition bsim-condition-groggy'..(enteredGroggy and ' is-new' or '')..'">GROGGY</span>') end
  if character.isDown then table.insert(tags,'<span class="bsim-condition bsim-condition-down'..(enteredDown and ' is-new' or '')..'">DOWN '..character.skippedTurnsRemaining..'</span>') end
  if character.isKo then table.insert(tags,'<span class="bsim-condition bsim-condition-ko">KO</span>') end
  local parts={string.format('<section class="%s">',table.concat(classes,' '))}
  table.insert(parts,'<div class="bsim-unit-head"><b>'..esc(title)..'</b><small>다운 '..character.downCount..' / 3</small></div>')
  table.insert(parts,'<div class="bsim-portrait-frame"><span class="bsim-portrait-fallback">'..initial..'</span><div class="bsim-heartbeat-layer"><div class="bsim-hit-layer"><img class="bsim-portrait" src="{{raw::'..esc(portrait)..'}}" alt="'..esc(title)..'" loading="eager" decoding="sync"></div></div>')
  if finalPortrait then table.insert(parts,'<img class="bsim-portrait-result" src="{{raw::'..esc(finalPortrait)..'}}" alt="" loading="eager" decoding="sync">') end
  table.insert(parts,'<div class="bsim-damage-flash"></div>')
  table.insert(parts,'<div class="bsim-conditions">'..table.concat(tags)..'</div>')
  table.insert(parts,renderDeltas(presentation,side))
  if resultLabel then table.insert(parts,'<div class="bsim-end-overlay"><strong>'..resultLabel..'</strong></div>') end
  table.insert(parts,'</div><div class="bsim-resources">')
  table.insert(parts,bar('HP',character.hp,character.maxHp,'hp')..bar('STA',character.stamina,character.maxStamina,'sta')..bar('BRK',character.breakGauge,character.maxBreakGauge,'brk'))
  table.insert(parts,'</div></section>'); return table.concat(parts)
end

local function renderResolution(state)
  local presentation=state.presentation
  if not presentation then return '' end
  local parts={string.format('<div class="bsim-resolution bsim-resolution-%s" data-sequence="%d">',presentation.diceResult or presentation.kind,presentation.sequenceId or 0)}
  if presentation.kind~='interval' and presentation.kind~='both_groggy' then
    table.insert(parts,'<div class="bsim-cinematic-stage">'..renderCinematicActor(state,'player',presentation)..renderCinematicActor(state,'enemy',presentation)..'</div>')
  end
  if presentation.kind=='normal' then
    local verdict=presentation.diceResult=='win' and 'PLAYER WIN' or (presentation.diceResult=='lose' and 'PLAYER LOSE' or 'DRAW')
    table.insert(parts,'<div class="bsim-action-readout"><span>'..ACTION_LABEL[presentation.playerAction]..'</span><span>'..ACTION_LABEL[presentation.enemyAction]..'</span></div>')
    table.insert(parts,string.format('<div class="bsim-dice-stage"><span class="bsim-die bsim-die-player">%d</span><b>VS</b><span class="bsim-die bsim-die-enemy">%d</span></div>',presentation.playerDie,presentation.enemyDie))
    table.insert(parts,'<div class="bsim-verdict">'..verdict..'</div>')
  elseif presentation.kind=='groggy' then
    table.insert(parts,'<div class="bsim-special-verdict">GROGGY OPENING</div>')
  elseif presentation.kind=='down_wait' then
    table.insert(parts,'<div class="bsim-special-verdict">DOWN COUNT</div>')
  elseif presentation.kind=='both_groggy' then
    table.insert(parts,'<div class="bsim-special-verdict">DOUBLE GROGGY</div>')
  elseif presentation.kind=='interval' then
    table.insert(parts,'<div class="bsim-special-verdict">ROUND INTERVAL</div>')
  else table.insert(parts,'<div class="bsim-special-verdict">RESOLUTION</div>') end
  if presentation.entryId then table.insert(parts,'<small>TABLE '..presentation.entryId..'</small>') end
  table.insert(parts,'</div>'); return table.concat(parts)
end

local function render(state)
  if type(state)~='table' or not state.player then
    local parts={'<div class="bsim-panel bsim-panel-idle"><header class="bsim-header"><div><span class="bsim-kicker">RISUAI COMBAT LAB</span><h3>Round / Turn Battle</h3></div><span class="bsim-status">READY</span></header><p class="bsim-intro">Python POC를 이식한 1 대 1 전투 엔진입니다. 상대 정책을 선택하세요.</p><div class="bsim-roster">'}
    for _,npc in ipairs(NPCS) do table.insert(parts,string.format('<button class="bsim-roster-button" risu-btn="bs;start;%s" title="초상화: %s.png"><span>%s</span><b>%s</b></button>',npc.id,npc.id,npc.difficulty,npc.name)) end
    table.insert(parts,'</div><div class="bsim-hint">38종 초상화 에셋의 접두사로 <code>player</code> 및 <code>NPC정책ID</code>를 사용합니다. · 채팅 명령 <code>/battle</code></div></div>'); return table.concat(parts)
  end
  local resolving=state.presentation and ' is-resolving' or ''
  local parts={'<div class="bsim-panel'..resolving..'"><header class="bsim-header"><div><span class="bsim-kicker">LIVE MATCH</span><h3>Round '..state.roundNumber..' · Turn '..state.turnInRound..'</h3></div><span class="bsim-status">TOTAL '..state.matchTurn..'</span></header>'}
  table.insert(parts,renderResolution(state))
  table.insert(parts,'<div class="bsim-grid">'..renderCharacter(state,'player')..renderCharacter(state,'enemy')..'</div>')
  if state.presentation then
    local nextLabel=state.outcome and '결과 확인' or (state.pendingInterval and '인터벌 진행' or '다음 턴')
    table.insert(parts,'<button class="bsim-continue" risu-btn="bs;continue"><span>CONTINUE</span>'..nextLabel..'</button>')
  elseif state.outcome then
    local label={PLAYER_WIN='플레이어 승리',ENEMY_WIN='적 승리',DOUBLE_KO='더블 KO',STALEMATE='교착'}
    table.insert(parts,'<div class="bsim-result"><strong>'..(label[state.outcome] or state.outcome)..'</strong><button class="bsim-button bsim-button-secondary" risu-btn="bs;reset">상대 선택으로</button></div>')
  elseif playerCanChoose(state) then
    table.insert(parts,'<div class="bsim-actions"><button class="bsim-button bsim-attack" risu-btn="bs;act;attack"><span>ATTACK</span><b>공격</b></button><button class="bsim-button bsim-defend" risu-btn="bs;act;defend"><span>DEFEND</span><b>방어</b></button><button class="bsim-button bsim-evade" risu-btn="bs;act;evade"><span>EVADE</span><b>회피</b></button></div>')
  else table.insert(parts,'<div class="bsim-forced">강제 턴을 진행하려면 다음 턴을 누르세요.</div>') end
  table.insert(parts,'<div class="bsim-log"><div class="bsim-log-title">COMBAT LOG</div>'); for i=#state.log,1,-1 do table.insert(parts,'<div class="bsim-log-line">'..esc(state.log[i])..'</div>') end
  table.insert(parts,'</div><button class="bsim-exit" risu-btn="bs;reset">종료 / 새 전투</button>'..renderActionPreload(state)..'</div>'); return table.concat(parts)
end

listenEdit('editDisplay', function(triggerId, data, meta)
  if meta and meta.index~=nil and meta.index-getChatLength(triggerId)~=-1 then return data end
  return data..render(getState(triggerId,STATE_KEY))
end)

onStart=function(triggerId)
  local chat=getFullChat(triggerId); local last=chat[#chat]
  if not last or last.role~='user' or last.data:gsub('^%s+',''):gsub('%s+$','')~='/battle' then return end
  removeChat(triggerId,getChatLength(triggerId)-1); addChat(triggerId,'char','전투 시뮬레이터를 시작합니다.')
  setState(triggerId,STATE_KEY,makeState('balanced_soldier',os.time and os.time() or 20260830)); stopChat(triggerId)
end

onButtonClick=function(triggerId,code)
  local action,param=code:match('^bs;([^;]+);?(.*)$'); if not action then return end
  if action=='reset' then setState(triggerId,STATE_KEY,false); return end
  if action=='start' then setState(triggerId,STATE_KEY,makeState(param,os.time and os.time() or 20260830)); return end
  local state=getState(triggerId,STATE_KEY); if type(state)~='table' then return end
  if action=='continue' and state.presentation then
    advancePresentation(state); setState(triggerId,STATE_KEY,state); return
  end
  if action=='act' and not state.presentation and (param=='attack' or param=='defend' or param=='evade') and playerCanChoose(state) then
    playTurn(state,param); setState(triggerId,STATE_KEY,state)
  end
end
