-- ============================================================
-- RogueLikePOC - Stage 4-A active skill combat POC
-- SP/MP resources + self/party attack scaling + single/all target
-- ============================================================

local STATE_KEY = 'rogue_state'
local STATE_VERSION = 2

local ITEM_NAMES = {
  potion = '포션',
}

local ROOM_LABELS = {
  battle = '전투',
  event = '이벤트',
  shop = '상점',
  boss = '보스',
}

local ROOM_SHORT = {
  battle = '전',
  event = '이',
  shop = '상',
  boss = '보',
}

-- Active skill schema:
-- costType: 'sp' | 'mp'
-- target:   'single' | 'all'
-- scaling:  'self_attack' | 'party_attack'
-- No engine-side limit is imposed on the number of skill IDs a unit owns.
local ACTIVE_SKILLS = {
  power_strike = {
    name = '강타',
    costType = 'sp',
    cost = 20,
    target = 'single',
    scaling = 'self_attack',
    multiplier = 1.8,
    description = '자신의 공격력 1.8배로 적 하나를 공격합니다.',
  },
  whirlwind = {
    name = '휩쓸기',
    costType = 'sp',
    cost = 35,
    target = 'all',
    scaling = 'self_attack',
    multiplier = 0.9,
    description = '자신의 공격력 0.9배로 모든 적을 공격합니다.',
  },
  united_strike = {
    name = '연합 강습',
    costType = 'sp',
    cost = 45,
    target = 'single',
    scaling = 'party_attack',
    multiplier = 1.1,
    description = '생존한 파티원의 공격력 합계 1.1배로 적 하나를 공격합니다.',
  },
  fireball = {
    name = '화염구',
    costType = 'mp',
    cost = 20,
    target = 'single',
    scaling = 'self_attack',
    multiplier = 1.7,
    description = '자신의 공격력 1.7배로 적 하나를 공격합니다.',
  },
  blizzard = {
    name = '눈보라',
    costType = 'mp',
    cost = 35,
    target = 'all',
    scaling = 'self_attack',
    multiplier = 0.85,
    description = '자신의 공격력 0.85배로 모든 적을 공격합니다.',
  },
  arcane_storm = {
    name = '비전 폭풍',
    costType = 'mp',
    cost = 55,
    target = 'all',
    scaling = 'party_attack',
    multiplier = 0.75,
    description = '생존한 파티원의 공격력 합계 0.75배로 모든 적을 공격합니다.',
  },
}

local DEFAULT_SKILLS = {
  [1] = { 'power_strike', 'whirlwind', 'united_strike' },
  [2] = { 'fireball', 'blizzard', 'arcane_storm' },
}

local ok, seed = pcall(function()
  return os.time() * 1000 + math.floor(os.clock() * 1000)
end)
if ok and seed then
  math.randomseed(seed)
end

-- ---------- Utilities ----------

local function escapeHtml(s)
  return tostring(s)
    :gsub('&', '&amp;')
    :gsub('<', '&lt;')
    :gsub('>', '&gt;')
    :gsub('"', '&quot;')
end

local function pushLog(state, msg)
  state.log = state.log or {}
  table.insert(state.log, msg)
  if #state.log > 30 then
    table.remove(state.log, 1)
  end
end

local function copyArray(source)
  local result = {}
  for _, value in ipairs(source or {}) do
    table.insert(result, value)
  end
  return result
end

local function resourceLabel(resourceType)
  if resourceType == 'mp' then
    return 'MP'
  end
  return 'SP'
end

local function normalizePartyMember(member, index, migrateSkills)
  local fallbackSkills = DEFAULT_SKILLS[index] or {}
  if migrateSkills or type(member.skills) ~= 'table' then
    member.skills = copyArray(fallbackSkills)
  else
    local knownSkills = {}
    for _, skillId in ipairs(member.skills) do
      if ACTIVE_SKILLS[skillId] then
        table.insert(knownSkills, skillId)
      end
    end
    member.skills = knownSkills
  end

  if member.maxSp == nil then
    member.maxSp = index == 1 and 100 or 40
  end
  if member.sp == nil then
    member.sp = member.maxSp
  end
  if member.maxMp == nil then
    member.maxMp = index == 2 and 120 or 30
  end
  if member.mp == nil then
    member.mp = member.maxMp
  end
  member.statuses = member.statuses or {}
  member.passives = member.passives or {}
  member.shield = member.shield or 0
  if member.alive == nil then
    member.alive = member.hp > 0
  end
end

local function normalizeState(state)
  if type(state) ~= 'table' or type(state.party) ~= 'table' then
    return nil
  end

  local previousVersion = state.version
  state.version = STATE_VERSION
  state.log = state.log or {}
  for index, member in ipairs(state.party) do
    normalizePartyMember(member, index, previousVersion ~= STATE_VERSION)
  end

  if type(state.battle) == 'table' and type(state.battle.units) == 'table' then
    state.battle.phase = state.battle.phase or 'player'
    state.battle.round = state.battle.round or 1
    for _, unit in ipairs(state.battle.units) do
      if unit.side == 'party' then
        local member = state.party[unit.idx]
        if member then
          unit.maxSp = unit.maxSp or member.maxSp
          unit.sp = unit.sp or member.sp
          unit.maxMp = unit.maxMp or member.maxMp
          unit.mp = unit.mp or member.mp
          if previousVersion ~= STATE_VERSION or type(unit.skills) ~= 'table' then
            unit.skills = copyArray(member.skills)
          end
        end
      else
        unit.maxSp = unit.maxSp or 0
        unit.sp = unit.sp or 0
        unit.maxMp = unit.maxMp or 0
        unit.mp = unit.mp or 0
        unit.skills = unit.skills or {}
      end
    end

    -- Migrate the previous POC's selection state safely.
    if state.battle.pendingAttacker and not state.battle.pendingActor then
      state.battle.pendingActor = state.battle.pendingAttacker
      state.battle.pendingAction = { kind = 'basic', target = 'single' }
      state.battle.pendingAttacker = nil
    end
  end

  return state
end

-- ---------- Map ----------

local function shuffle(t)
  for i = #t, 2, -1 do
    local j = math.random(i)
    t[i], t[j] = t[j], t[i]
  end
  return t
end

local function generateMap()
  local layerSizes = { 1, 2, 3, 2, 1 }
  local middlePool = shuffle({ 'battle', 'battle', 'battle', 'event', 'event', 'shop', 'shop' })
  local nodes = {}
  local layerNodes = {}
  local id = 0

  for layerIndex, count in ipairs(layerSizes) do
    layerNodes[layerIndex] = {}
    for _ = 1, count do
      id = id + 1
      local nodeType
      if layerIndex == 1 then
        nodeType = 'battle'
      elseif layerIndex == #layerSizes then
        nodeType = 'boss'
      else
        nodeType = table.remove(middlePool, 1)
      end
      local node = {
        id = id,
        type = nodeType,
        cleared = false,
        visited = false,
        layer = layerIndex,
      }
      nodes[id] = node
      table.insert(layerNodes[layerIndex], node)
    end
  end

  local outEdges = {}
  for layerIndex = 1, #layerSizes - 1 do
    local fromLayer = layerNodes[layerIndex]
    local toLayer = layerNodes[layerIndex + 1]

    -- Guarantee at least one incoming edge for every node in the next layer.
    for _, toNode in ipairs(toLayer) do
      local fromNode = fromLayer[math.random(#fromLayer)]
      outEdges[fromNode.id] = outEdges[fromNode.id] or {}
      table.insert(outEdges[fromNode.id], toNode.id)
    end

    -- Give each node one to three unique outgoing edges.
    for _, fromNode in ipairs(fromLayer) do
      outEdges[fromNode.id] = outEdges[fromNode.id] or {}
      local wanted = math.random(1, 3)
      local candidates = {}
      for _, toNode in ipairs(toLayer) do
        local exists = false
        for _, targetId in ipairs(outEdges[fromNode.id]) do
          if targetId == toNode.id then
            exists = true
            break
          end
        end
        if not exists then
          table.insert(candidates, toNode.id)
        end
      end
      shuffle(candidates)
      while #outEdges[fromNode.id] < wanted and #candidates > 0 do
        table.insert(outEdges[fromNode.id], table.remove(candidates, 1))
      end
    end
  end

  return { nodes = nodes, outEdges = outEdges }
end

-- ---------- Combat ----------

local ENEMY_POOL = {
  { name = '슬라임', hp = 40, atk = 12, def = 2, spd = 5 },
  { name = '늑대', hp = 50, atk = 15, def = 3, spd = 12 },
  { name = '고블린', hp = 45, atk = 13, def = 4, spd = 7 },
}

local BOSS = { name = '보스 몬스터', hp = 150, atk = 20, def = 6, spd = 9 }

local function findUnit(battle, side, index)
  for _, unit in ipairs(battle.units) do
    if unit.side == side and unit.idx == index then
      return unit
    end
  end
  return nil
end

local function aliveUnits(battle, side)
  local result = {}
  for _, unit in ipairs(battle.units) do
    if unit.side == side and unit.alive then
      table.insert(result, unit)
    end
  end
  return result
end

local function calcBasicDamage(attacker, defender)
  return math.max(0, attacker.atk - defender.def)
end

local function attackUnit(attacker, defender)
  local damage = calcBasicDamage(attacker, defender)
  defender.hp = math.max(0, defender.hp - damage)
  if defender.hp <= 0 then
    defender.alive = false
  end
  return damage
end

local function partyAttackTotal(battle)
  local total = 0
  for _, unit in ipairs(aliveUnits(battle, 'party')) do
    total = total + unit.atk
  end
  return total
end

local function calcSkillDamage(skill, battle, attacker, defender)
  local baseAttack = attacker.atk
  if skill.scaling == 'party_attack' then
    baseAttack = partyAttackTotal(battle)
  end
  local scaledAttack = math.floor(baseAttack * skill.multiplier + 0.5)
  return math.max(0, scaledAttack - defender.def)
end

local function canUseSkill(attacker, skill)
  if not attacker or not attacker.alive or not skill then
    return false
  end
  local resource = attacker[skill.costType] or 0
  return resource >= skill.cost
end

local function spendSkillResource(attacker, skill)
  attacker[skill.costType] = math.max(0, (attacker[skill.costType] or 0) - skill.cost)
end

local function damageWithSkill(skill, battle, attacker, defender)
  local damage = calcSkillDamage(skill, battle, attacker, defender)
  defender.hp = math.max(0, defender.hp - damage)
  if defender.hp <= 0 then
    defender.alive = false
  end
  return damage
end

local function startBattle(state, roomType)
  local units = {}
  for index, member in ipairs(state.party) do
    if member.alive then
      table.insert(units, {
        side = 'party',
        idx = index,
        name = member.name,
        hp = member.hp,
        maxHp = member.maxHp,
        sp = member.sp,
        maxSp = member.maxSp,
        mp = member.mp,
        maxMp = member.maxMp,
        atk = member.atk,
        def = member.def,
        spd = member.spd,
        skills = copyArray(member.skills),
        alive = true,
      })
    end
  end

  local enemies = {}
  if roomType == 'boss' then
    table.insert(enemies, BOSS)
  else
    local count = math.random(1, 2)
    for _ = 1, count do
      table.insert(enemies, ENEMY_POOL[math.random(#ENEMY_POOL)])
    end
  end

  for index, enemy in ipairs(enemies) do
    table.insert(units, {
      side = 'enemy',
      idx = index,
      name = enemy.name,
      hp = enemy.hp,
      maxHp = enemy.hp,
      sp = 0,
      maxSp = 0,
      mp = 0,
      maxMp = 0,
      atk = enemy.atk,
      def = enemy.def,
      spd = enemy.spd,
      skills = {},
      alive = true,
    })
  end

  state.battle = {
    units = units,
    phase = 'player',
    round = 1,
    pendingActor = nil,
    pendingAction = nil,
  }
  state.phase = 'battle'
  pushLog(state, '전투가 시작되었습니다!')
end

local function syncParty(state)
  if not state.battle then
    return
  end
  for _, unit in ipairs(state.battle.units) do
    if unit.side == 'party' then
      local member = state.party[unit.idx]
      if member then
        member.hp = unit.hp
        member.sp = unit.sp
        member.mp = unit.mp
        member.alive = unit.alive
      end
    end
  end
end

local function enemyTurn(state)
  for _, enemy in ipairs(state.battle.units) do
    if enemy.side == 'enemy' and enemy.alive then
      local targets = aliveUnits(state.battle, 'party')
      if #targets == 0 then
        return
      end
      local target = targets[math.random(#targets)]
      local damage = attackUnit(enemy, target)
      pushLog(state, string.format('%s이(가) %s을(를) 공격! %d 데미지!', enemy.name, target.name, damage))
      if not target.alive then
        pushLog(state, string.format('%s이(가) 쓰러졌습니다...', target.name))
      end
    end
  end
end

local function resolveAfterPlayerAction(triggerId, state)
  local battle = state.battle
  battle.pendingActor = nil
  battle.pendingAction = nil

  if #aliveUnits(battle, 'enemy') == 0 then
    syncParty(state)
    state.battle = nil
    local room = state.map.nodes[state.currentRoomId]
    room.cleared = true
    pushLog(state, '전투에서 승리했습니다!')
    if room.type == 'boss' then
      state.phase = 'victory'
      addChat(triggerId, 'char', '보스를 처치했습니다! 모험 성공!')
    else
      state.phase = 'map'
    end
    return
  end

  battle.phase = 'enemy'
  pushLog(state, string.format('라운드 %d: 적의 행동이 시작됩니다.', battle.round))
  enemyTurn(state)

  if #aliveUnits(battle, 'party') == 0 then
    syncParty(state)
    state.battle = nil
    state.phase = 'gameover'
    addChat(triggerId, 'char', '파티가 전멸했습니다...')
    return
  end

  syncParty(state)
  battle.phase = 'player'
  battle.round = battle.round + 1
end

local function executeBasicAction(triggerId, state, attacker, defender)
  local damage = attackUnit(attacker, defender)
  pushLog(state, string.format('%s이(가) %s을(를) 기본 공격! %d 데미지!', attacker.name, defender.name, damage))
  if not defender.alive then
    pushLog(state, string.format('%s을(를) 처치했습니다!', defender.name))
  end
  resolveAfterPlayerAction(triggerId, state)
end

local function executeSkillAction(triggerId, state, attacker, skillId, singleTarget)
  local skill = ACTIVE_SKILLS[skillId]
  if not canUseSkill(attacker, skill) then
    pushLog(state, '스킬을 사용할 수 없거나 자원이 부족합니다.')
    state.battle.pendingAction = nil
    return false
  end

  local targets = {}
  if skill.target == 'single' then
    if not singleTarget or not singleTarget.alive then
      return false
    end
    table.insert(targets, singleTarget)
  else
    targets = aliveUnits(state.battle, 'enemy')
  end

  if #targets == 0 then
    return false
  end

  spendSkillResource(attacker, skill)
  pushLog(state, string.format(
    '%s이(가) %s 사용! %s %d 소모.',
    attacker.name,
    skill.name,
    resourceLabel(skill.costType),
    skill.cost
  ))

  for _, defender in ipairs(targets) do
    local damage = damageWithSkill(skill, state.battle, attacker, defender)
    pushLog(state, string.format('%s에게 %d 데미지!', defender.name, damage))
    if not defender.alive then
      pushLog(state, string.format('%s을(를) 처치했습니다!', defender.name))
    end
  end

  resolveAfterPlayerAction(triggerId, state)
  return true
end

-- ---------- Game state ----------

local function newGameState()
  local state = {
    version = STATE_VERSION,
    phase = 'room',
    party = {
      {
        name = '검사',
        hp = 100,
        maxHp = 100,
        sp = 100,
        maxSp = 100,
        mp = 30,
        maxMp = 30,
        atk = 20,
        def = 5,
        spd = 10,
        skills = copyArray(DEFAULT_SKILLS[1]),
        passives = { 'last_stand' },
        statuses = {},
        shield = 0,
        alive = true,
      },
      {
        name = '마법사',
        hp = 80,
        maxHp = 80,
        sp = 40,
        maxSp = 40,
        mp = 120,
        maxMp = 120,
        atk = 25,
        def = 3,
        spd = 8,
        skills = copyArray(DEFAULT_SKILLS[2]),
        passives = { 'battle_shield' },
        statuses = {},
        shield = 0,
        alive = true,
      },
    },
    inventory = { { id = 'potion', count = 2 } },
    gold = 50,
    map = generateMap(),
    currentRoomId = 1,
    battle = nil,
    log = {},
  }
  state.map.nodes[1].visited = true
  pushLog(state, '1번 방(전투)에 입장했습니다.')
  startBattle(state, 'battle')
  return state
end

-- ---------- Rendering ----------

local function renderIdlePanel()
  return [[
<div class="rogue-panel">
  <div class="rogue-title">로그라이크 POC · Stage 4-A</div>
  <div class="rogue-desc">SP/MP와 공격형 액티브 스킬을 사용하는 턴제 전투 POC입니다.</div>
  <button risu-btn="rogue;start">시작</button>
</div>
]]
end

local function renderParty(state)
  local units = {}
  for _, member in ipairs(state.party) do
    local hpPercent = math.min(100, math.max(0, math.floor(member.hp / member.maxHp * 100)))
    local className = 'rogue-unit'
    if not member.alive then
      className = className .. ' rogue-unit-dead'
    end
    table.insert(units, string.format(
      '<div class="%s"><div class="rogue-unit-name">%s</div>'
      .. '<div class="rogue-hpbar"><div class="rogue-hpfill" style="width:%d%%"></div></div>'
      .. '<div class="rogue-unit-hp">HP %d/%d · SP %d/%d · MP %d/%d</div></div>',
      className,
      escapeHtml(member.name),
      hpPercent,
      member.hp,
      member.maxHp,
      member.sp,
      member.maxSp,
      member.mp,
      member.maxMp
    ))
  end
  return '<div class="rogue-party">' .. table.concat(units) .. '</div>'
end

local function renderResources(state)
  local inventory = {}
  for _, item in ipairs(state.inventory) do
    local label = ITEM_NAMES[item.id] or item.id
    table.insert(inventory, label .. ' x' .. item.count)
  end
  local inventoryText = table.concat(inventory, ', ')
  if inventoryText == '' then
    inventoryText = '없음'
  end
  return string.format('<div class="rogue-resources">골드: %d | %s</div>', state.gold, inventoryText)
end

local function renderLog(state)
  if #state.log == 0 then
    return ''
  end
  local lines = {}
  for _, line in ipairs(state.log) do
    table.insert(lines, '<div class="rogue-log-line">' .. escapeHtml(line) .. '</div>')
  end
  return '<div class="rogue-log">' .. table.concat(lines) .. '</div>'
end

local function renderMapRow(state)
  local layerColumns = {}
  for _, node in ipairs(state.map.nodes) do
    layerColumns[node.layer] = layerColumns[node.layer] or {}
    table.insert(layerColumns[node.layer], node)
  end

  local columns = {}
  for layerIndex = 1, #layerColumns do
    local cells = {}
    for _, node in ipairs(layerColumns[layerIndex]) do
      local className = 'rogue-map-room'
      if node.cleared then
        className = className .. ' rogue-map-cleared'
      end
      if node.id == state.currentRoomId then
        className = className .. ' rogue-map-current'
      end
      if node.visited then
        className = className .. ' rogue-map-visited'
      end
      if node.type == 'boss' then
        className = className .. ' rogue-map-boss'
      end
      table.insert(cells, string.format('<div class="%s">%s</div>', className, ROOM_SHORT[node.type] or '?'))
    end
    table.insert(columns, '<div class="rogue-map-col">' .. table.concat(cells) .. '</div>')
  end
  return '<div class="rogue-map">' .. table.concat(columns) .. '</div>'
end

local function renderChoices(state)
  local targets = state.map.outEdges[state.currentRoomId] or {}
  local parts = { '<div class="rogue-choices">' }
  table.insert(parts, '<div class="rogue-choices-title">다음 방 선택</div>')
  for _, targetId in ipairs(targets) do
    local target = state.map.nodes[targetId]
    local label = ROOM_LABELS[target.type] or target.type
    local visitedMark = target.visited and ' (방문함)' or ''
    table.insert(parts, string.format(
      '<button risu-btn="rogue;move;%d">%s 방%s</button>',
      targetId,
      label,
      visitedMark
    ))
  end
  table.insert(parts, '</div>')
  return table.concat(parts)
end

local function renderBattleUnit(state, unit)
  local battle = state.battle
  local hpPercent = math.min(100, math.max(0, math.floor(unit.hp / unit.maxHp * 100)))
  local className = 'rogue-bunit'
  if not unit.alive then
    className = className .. ' rogue-bunit-dead'
  end
  if battle.pendingActor and unit.side == 'party' and battle.pendingActor.idx == unit.idx then
    className = className .. ' rogue-bunit-selected'
  end

  local resourceLine = ''
  if unit.side == 'party' then
    resourceLine = string.format(
      '<div class="rogue-bunit-resource">SP %d/%d · MP %d/%d</div>',
      unit.sp,
      unit.maxSp,
      unit.mp,
      unit.maxMp
    )
  end

  local inner = string.format(
    '<div class="rogue-bunit-name">%s</div>'
    .. '<div class="rogue-hpbar"><div class="rogue-hpfill" style="width:%d%%"></div></div>'
    .. '<div class="rogue-bunit-hp">HP %d/%d</div>'
    .. '%s'
    .. '<div class="rogue-bunit-stats">공 %d / 방 %d</div>',
    escapeHtml(unit.name),
    hpPercent,
    unit.hp,
    unit.maxHp,
    resourceLine,
    unit.atk,
    unit.def
  )

  local clickable = false
  local code = ''
  if battle.phase == 'player' then
    if unit.side == 'party' and unit.alive and not battle.pendingActor then
      clickable = true
      code = string.format('rogue;battle;select;party;%d', unit.idx)
    elseif unit.side == 'enemy' and unit.alive and battle.pendingAction then
      clickable = true
      code = string.format('rogue;battle;target;%d', unit.idx)
    end
  end

  if clickable then
    return string.format('<button risu-btn="%s" class="%s rogue-bunit-clickable">%s</button>', code, className, inner)
  end
  return string.format('<div class="%s">%s</div>', className, inner)
end

local function renderActionMenu(state)
  local battle = state.battle
  local actorRef = battle.pendingActor
  if not actorRef then
    return ''
  end
  local actor = findUnit(battle, actorRef.side, actorRef.idx)
  if not actor then
    return ''
  end

  local parts = { '<div class="rogue-action-menu">' }
  table.insert(parts, '<div class="rogue-action-title">' .. escapeHtml(actor.name) .. '의 행동 선택</div>')
  table.insert(parts, '<button risu-btn="rogue;battle;action;basic">기본 공격</button>')

  for _, skillId in ipairs(actor.skills or {}) do
    local skill = ACTIVE_SKILLS[skillId]
    if skill then
      local label = string.format(
        '%s · %s %d',
        skill.name,
        resourceLabel(skill.costType),
        skill.cost
      )
      if canUseSkill(actor, skill) then
        table.insert(parts, string.format(
          '<button risu-btn="rogue;battle;action;skill;%s" title="%s">%s</button>',
          skillId,
          escapeHtml(skill.description),
          escapeHtml(label)
        ))
      else
        table.insert(parts, string.format(
          '<button disabled class="rogue-skill-disabled" title="%s">%s · 자원 부족</button>',
          escapeHtml(skill.description),
          escapeHtml(label)
        ))
      end
    end
  end

  table.insert(parts, '<button risu-btn="rogue;battle;cancel">캐릭터 선택 취소</button>')
  table.insert(parts, '</div>')
  return table.concat(parts)
end

local function renderBattle(state)
  local battle = state.battle
  local parts = { '<div class="rogue-battle">' }
  table.insert(parts, string.format('<div class="rogue-round">라운드 %d</div>', battle.round))

  table.insert(parts, '<div class="rogue-battle-side"><div class="rogue-battle-side-title">적</div>')
  for _, unit in ipairs(battle.units) do
    if unit.side == 'enemy' then
      table.insert(parts, renderBattleUnit(state, unit))
    end
  end
  table.insert(parts, '</div>')

  table.insert(parts, '<div class="rogue-battle-side"><div class="rogue-battle-side-title">아군</div>')
  for _, unit in ipairs(battle.units) do
    if unit.side == 'party' then
      table.insert(parts, renderBattleUnit(state, unit))
    end
  end
  table.insert(parts, '</div>')
  table.insert(parts, '</div>')

  if battle.phase == 'player' then
    if not battle.pendingActor then
      table.insert(parts, '<div class="rogue-battle-prompt">행동할 아군을 선택하세요.</div>')
    elseif battle.pendingAction then
      local actor = findUnit(battle, battle.pendingActor.side, battle.pendingActor.idx)
      local actionName = '기본 공격'
      if battle.pendingAction.kind == 'skill' then
        local skill = ACTIVE_SKILLS[battle.pendingAction.skillId]
        actionName = skill and skill.name or '스킬'
      end
      table.insert(parts, string.format(
        '<div class="rogue-battle-prompt">%s의 %s 대상을 선택하세요.</div>',
        escapeHtml(actor and actor.name or '?'),
        escapeHtml(actionName)
      ))
      table.insert(parts, '<button risu-btn="rogue;battle;cancel">행동 선택으로 돌아가기</button>')
    else
      table.insert(parts, renderActionMenu(state))
    end
  end

  return table.concat(parts)
end

local function renderGamePanel(state)
  local parts = { '<div class="rogue-panel">' }
  table.insert(parts, '<div class="rogue-title">로그라이크 POC · Stage 4-A</div>')

  if state.phase == 'victory' then
    table.insert(parts, '<div class="rogue-victory">보스를 처치했습니다! 모험 성공!</div>')
    table.insert(parts, '<button risu-btn="rogue;restart">새 모험</button>')
  elseif state.phase == 'gameover' then
    table.insert(parts, '<div class="rogue-gameover">파티가 전멸했습니다...</div>')
    table.insert(parts, '<button risu-btn="rogue;restart">새 모험</button>')
  else
    table.insert(parts, renderParty(state))
    table.insert(parts, renderResources(state))
    table.insert(parts, renderMapRow(state))

    local room = state.map.nodes[state.currentRoomId]
    local roomLabel = ROOM_LABELS[room.type] or room.type
    table.insert(parts, string.format(
      '<div class="rogue-room-info">방 %d (%d층): %s</div>',
      room.id,
      room.layer,
      roomLabel
    ))

    if state.phase == 'battle' and state.battle then
      table.insert(parts, renderBattle(state))
    elseif state.phase == 'map' then
      table.insert(parts, renderChoices(state))
    elseif state.phase == 'room' then
      table.insert(parts, '<div class="rogue-placeholder">이벤트/상점은 다음 단계에서 구현됩니다.</div>')
      table.insert(parts, '<button risu-btn="rogue;clear">방 클리어 (임시)</button>')
    end

    table.insert(parts, renderLog(state))
    table.insert(parts, '<button risu-btn="rogue;abandon">포기</button>')
  end

  table.insert(parts, '</div>')
  return table.concat(parts)
end

local function renderPanel(state)
  state = normalizeState(state)
  if not state or not state.map or not state.map.nodes then
    return renderIdlePanel()
  end
  return renderGamePanel(state)
end

-- ---------- RisuAI callbacks ----------

listenEdit('editDisplay', function(triggerId, data, meta)
  if meta and meta.index ~= nil then
    local position = meta.index - getChatLength(triggerId)
    if position ~= -1 then
      return data
    end
  end
  local state = getState(triggerId, STATE_KEY)
  return data .. renderPanel(state)
end)

onStart = function(triggerId)
  local fullChat = getFullChat(triggerId)
  local lastChat = fullChat[#fullChat]
  if not lastChat or lastChat.role ~= 'user' then
    return
  end
  local message = lastChat.data:gsub('^%s+', ''):gsub('%s+$', '')
  if message ~= '/rogue' then
    return
  end
  removeChat(triggerId, getChatLength(triggerId) - 1)
  addChat(triggerId, 'char', 'Stage 4-A 로그라이크 모험이 시작되었습니다!')
  setState(triggerId, STATE_KEY, newGameState())
  stopChat(triggerId)
end

onButtonClick = function(triggerId, code)
  local action, parameter = code:match('^rogue;([^;]+);?(.*)$')
  if not action then
    return
  end

  if action == 'start' then
    addChat(triggerId, 'char', 'Stage 4-A 로그라이크 모험이 시작되었습니다!')
    setState(triggerId, STATE_KEY, newGameState())
    return
  elseif action == 'abandon' then
    addChat(triggerId, 'char', '모험을 포기했습니다.')
    setState(triggerId, STATE_KEY, false)
    return
  elseif action == 'restart' then
    addChat(triggerId, 'char', '새로운 Stage 4-A 모험이 시작되었습니다!')
    setState(triggerId, STATE_KEY, newGameState())
    return
  end

  local state = normalizeState(getState(triggerId, STATE_KEY))
  if not state then
    return
  end

  if action == 'move' then
    if state.phase == 'map' and state.map and state.map.nodes then
      local targetId = tonumber(parameter)
      local valid = false
      for _, candidateId in ipairs(state.map.outEdges[state.currentRoomId] or {}) do
        if candidateId == targetId then
          valid = true
          break
        end
      end
      if valid and state.map.nodes[targetId] then
        state.currentRoomId = targetId
        local node = state.map.nodes[targetId]
        node.visited = true
        pushLog(state, string.format('%d번 방(%s)에 입장했습니다.', targetId, ROOM_LABELS[node.type] or '?'))
        if node.type == 'battle' or node.type == 'boss' then
          startBattle(state, node.type)
        else
          state.phase = 'room'
        end
        setState(triggerId, STATE_KEY, state)
      end
    end
    return
  elseif action == 'clear' then
    if state.phase == 'room' and state.map and state.map.nodes then
      local room = state.map.nodes[state.currentRoomId]
      room.cleared = true
      pushLog(state, string.format('%d번 방을 클리어했습니다.', room.id))
      state.phase = 'map'
      setState(triggerId, STATE_KEY, state)
    end
    return
  end

  if action ~= 'battle' or state.phase ~= 'battle' or not state.battle then
    return
  end

  local battle = state.battle
  if battle.phase ~= 'player' then
    return
  end

  local subAction, argument = parameter:match('^([^;]+);?(.*)$')
  if subAction == 'select' and not battle.pendingActor then
    local side, indexText = argument:match('^([^;]+);(%d+)$')
    if side == 'party' then
      local index = tonumber(indexText)
      local actor = findUnit(battle, 'party', index)
      if actor and actor.alive then
        battle.pendingActor = { side = 'party', idx = index }
        battle.pendingAction = nil
        setState(triggerId, STATE_KEY, state)
      end
    end
    return
  elseif subAction == 'cancel' and battle.pendingActor then
    if battle.pendingAction then
      battle.pendingAction = nil
    else
      battle.pendingActor = nil
    end
    setState(triggerId, STATE_KEY, state)
    return
  elseif subAction == 'action' and battle.pendingActor and not battle.pendingAction then
    local actionType, detail = argument:match('^([^;]+);?(.*)$')
    local actor = findUnit(battle, battle.pendingActor.side, battle.pendingActor.idx)
    if not actor or not actor.alive then
      battle.pendingActor = nil
      setState(triggerId, STATE_KEY, state)
      return
    end

    if actionType == 'basic' then
      battle.pendingAction = { kind = 'basic', target = 'single' }
      setState(triggerId, STATE_KEY, state)
      return
    elseif actionType == 'skill' then
      local skill = ACTIVE_SKILLS[detail]
      if not skill or not canUseSkill(actor, skill) then
        pushLog(state, '스킬을 사용할 수 없거나 자원이 부족합니다.')
        setState(triggerId, STATE_KEY, state)
        return
      end
      if skill.target == 'all' then
        executeSkillAction(triggerId, state, actor, detail, nil)
      else
        battle.pendingAction = {
          kind = 'skill',
          skillId = detail,
          target = 'single',
        }
      end
      setState(triggerId, STATE_KEY, state)
      return
    end
  elseif subAction == 'target' and battle.pendingActor and battle.pendingAction then
    local targetIndex = tonumber(argument)
    local attacker = findUnit(battle, battle.pendingActor.side, battle.pendingActor.idx)
    local defender = findUnit(battle, 'enemy', targetIndex)
    if not attacker or not attacker.alive or not defender or not defender.alive then
      return
    end

    if battle.pendingAction.kind == 'basic' then
      executeBasicAction(triggerId, state, attacker, defender)
    elseif battle.pendingAction.kind == 'skill' then
      executeSkillAction(triggerId, state, attacker, battle.pendingAction.skillId, defender)
    end
    setState(triggerId, STATE_KEY, state)
  end
end
