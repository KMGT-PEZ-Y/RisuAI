local function cost(o) return o and o.level+1 or 2 end
function M.render(s)
  local parts={'<p>강화 자원 <strong>'..s.player.trainingPoints..'</strong> · 훈련은 시간을 소비하지 않습니다.</p>'}
  local ids={}; for _,o in ipairs(s.player.skills) do ids[#ids+1]=o.id end
  for _,id in ipairs(P.growthSkills) do if not P.contains(ids,id) then ids[#ids+1]=id end end
  for _,id in ipairs(ids) do
    local d=P.skills[id]; local o=P.owned(s,id); local c=cost(o)
    local reason=P.blocked(s)
    if not reason and o and o.level>=d.maxLevel then reason='최대 레벨입니다.' end
    if not reason and s.player.trainingPoints<c then reason='강화 자원이 부족합니다.' end
    local maximum=o and o.level>=d.maxLevel
    local label=maximum and ('Lv.'..o.level..' · 최대 레벨') or (o and ('Lv.'..o.level..' → '..(o.level+1)) or '신규 습득 · Lv.1')
    parts[#parts+1]=P.card(d.name,'<p>'..P.esc(d.description)..'</p><p>'..label..(maximum and '' or ' · 비용 '..c)..'</p>'..P.button(s,'upgrade',o and '강화' or '습득',id,reason))
  end
  parts[#parts+1]=P.returnButton(s)
  return P.panel(s,'트레이닝',table.concat(parts))
end
function M.handle(id,s,action,value)
  if action=='back' then s.screen='hub'; return true end
  local why=P.blocked(s); if why then return false,why end
  local d=P.skills[value]; local o=P.owned(s,value)
  if action~='upgrade' or not d or (not o and not P.contains(P.growthSkills,value)) then return false,'훈련할 수 없는 스킬입니다.' end
  if o and o.level>=d.maxLevel then return false,'최대 레벨입니다.' end
  local c=cost(o); if s.player.trainingPoints<c then return false,'강화 자원이 부족합니다.' end
  s.player.trainingPoints=s.player.trainingPoints-c
  if o then o.level=o.level+1 else s.player.skills[#s.player.skills+1]={id=value,level=1} end
  s.notice=d.name..' '..(o and ('Lv.'..o.level..' 강화 완료') or '습득 완료 · 경기 정비에서 장착하세요.')
  return true
end
