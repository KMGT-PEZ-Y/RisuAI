local function candidates(s)
  local out,total={},0; local promise
  for _,n in ipairs(P.npcs) do
    local lead=s.story.matchLeads[n.id]
    if lead and lead.kind=='REMATCH_PROMISE' and (not promise or lead.at<promise.at) then promise={npc=n.id,at=lead.at} end
  end
  for _,n in ipairs(P.npcs) do
    local rel=s.story.relationships[n.id] or {}; local lead=s.story.matchLeads[n.id]
    local weight=math.max(1,10+math.floor((rel.respect or 0)/5))
    if lead then weight=weight+(lead.kind=='REMATCH_OFFER' and 30 or 20) end
    local last=s.matchHistory[#s.matchHistory]
    if last and last.opponentId==n.id then weight=math.max(1,math.floor(weight/4)) end
    if promise then weight=n.id==promise.npc and 1 or 0 end
    out[#out+1]={npc=n,weight=weight,reason=promise and '약속된 대전' or (lead and lead.kind or '기본 후보')}; total=total+weight
  end
  return out,total
end
function M.render(s)
  local parts={}; local next=P.nextMatch(s); local blocked=P.blocked(s)
  if next then
    parts[#parts+1]=P.card('확정된 다음 경기','<p>'..P.esc(P.npc(next.opponentId).name)..' · '..P.time(next.at)..'</p><p class="pa-muted">상대 재추첨은 할 수 없습니다.</p>')
  elseif s.scenario.mode=='tournament' then
    parts[#parts+1]='<p>등록된 컵 일정을 모두 마쳤습니다. 허브에서 자유 대전으로 전환할 수 있습니다.</p>'
  else
    local list,total=candidates(s)
    for _,c in ipairs(list) do
      parts[#parts+1]=P.card(c.npc.name,'<p>선정 확률 '..string.format('%.1f',100*c.weight/total)..'% · '..P.esc(c.reason)..'</p><small class="pa-muted">AI: '..c.npc.aiMode..' / '..c.npc.strategy..'</small>')
    end
    parts[#parts+1]=P.button(s,'draw','상대 선정 · 내일 같은 시각에 경기 확정',nil,blocked or (s.story.afterBattle and '경기 후 장면을 마치거나 건너뛰어 주세요.' or nil))
    if #s.schedule==0 and #s.matchHistory==0 then parts[#parts+1]=P.button(s,'cup','3경기 고정 컵 일정 등록',nil,blocked) end
  end
  for _,m in ipairs(s.schedule) do
    parts[#parts+1]='<p class="pa-muted">'..P.time(m.at)..' · '..P.esc(P.npc(m.opponentId).name)..' · '..(m.status=='completed' and '완료' or '예정')..'</p>'
  end
  parts[#parts+1]=P.returnButton(s)
  return P.panel(s,'매치메이킹',table.concat(parts))
end
function M.handle(id,s,action,value)
  if action=='back' then s.screen='hub'; return true end
  local why=P.blocked(s); if why then return false,why end
  if s.story.afterBattle then return false,'경기 후 장면을 마치거나 건너뛰어 주세요.' end
  if P.nextMatch(s) then return false,'이미 확정된 경기가 있습니다.' end
  if action=='draw' and s.scenario.mode=='free' then
    local list,total=candidates(s); local pick=P.roll(s)*total; local chosen
    for _,c in ipairs(list) do if c.weight>0 then pick=pick-c.weight; if pick<0 then chosen=c; break end end end
    if not chosen then return false,'가능한 상대가 없습니다.' end
    local lead=s.story.matchLeads[chosen.npc.id]
    s.schedule[#s.schedule+1]={id=P.id(s,'match_'),opponentId=chosen.npc.id,at=s.calendar.now+1440,venueId='arena',
      reason=lead and lead.kind or 'LEAGUE_DRAW',status='scheduled'}
    s.story.matchLeads[chosen.npc.id]=nil
    s.notice=chosen.npc.name..'와의 경기가 확정되었습니다.'
    return true
  elseif action=='cup' and #s.schedule==0 and #s.matchHistory==0 then
    s.scenario.mode='tournament'; s.scenario.id='starter_cup'; s.scenario.stage='cup_1'
    for i,n in ipairs(P.npcs) do s.schedule[#s.schedule+1]={id=P.id(s,'match_'),opponentId=n.id,at=s.calendar.now+i*2880,venueId='arena',reason='FIXED_CUP',status='scheduled'} end
    s.notice='승패와 관계없이 세 선수를 순서대로 만나는 고정 시나리오 컵을 등록했습니다.'
    return true
  end
  return false,'사용할 수 없는 선택입니다.'
end
