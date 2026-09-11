local function esc(v) return (tostring(v or ''):gsub('&','&amp;'):gsub('<','&lt;'):gsub('>','&gt;'):gsub('"','&quot;'):gsub("'",'&#39;')) end
local function div(cls,content) return '<div class="x-risu-lb-'..cls:gsub(' ',' x-risu-lb-')..'">'..content..'</div>' end
local function tag(v) return '<span class="x-risu-lb-eyebrow">'..v..'</span>' end
local function title(k,t,p) return tag(k)..'<h2>'..t..'</h2>'..(p and '<p>'..p..'</p>' or '') end
local function btn(s,action,value,label,cls,disabled)
  return '<button type="button" class="x-risu-lb-btn '..(cls and 'x-risu-lb-'..cls:gsub(' ',' x-risu-lb-') or '')..'"'..
    (disabled and ' disabled aria-disabled="true"' or ' risu-btn="lb;'..s.serial..';'..s.revision..';'..action..';'..(value or '')..'"')..'>'..label..'</button>'
end
local function stat(label,value) return div('stat','<small>'..label..'</small><strong>'..value..'</strong>') end
local function meter(name,value,max,cls)
  return '<div class="x-risu-lb-meter"><div><span>'..name..'</span><b>'..value..'<small> / '..max..'</small></b></div><div class="x-risu-lb-track"><i class="x-risu-lb-'..cls..'" style="width:'..G.clamp(math.floor(value/max*100),0,100)..'%"></i></div></div>'
end
local function figure(side)
  return '<div class="x-risu-lb-boxer x-risu-lb-'..side..'" aria-hidden="true"><i class="x-risu-lb-head"></i><i class="x-risu-lb-torso"></i><i class="x-risu-lb-glove x-risu-lb-glove-a"></i><i class="x-risu-lb-glove x-risu-lb-glove-b"></i><i class="x-risu-lb-leg x-risu-lb-leg-a"></i><i class="x-risu-lb-leg x-risu-lb-leg-b"></i></div>'
end
local function arena(s,hero)
  local r=G.rivals[s.level]; local d=s.match and s.match.distance or 2
  return '<div class="x-risu-lb-arena '..(hero and 'x-risu-lb-hero' or '')..' x-risu-lb-distance-'..d..'">'..
    div('arena-top',tag('SEOUL / AFTER HOURS')..'<span>'..r.venue..'</span>')..
    div('ring-word',hero and 'LAST<br>BELL' or 'ROUND<br>'..string.format('%02d',s.match.round))..
    '<div class="x-risu-lb-rope x-risu-lb-rope-one"></div><div class="x-risu-lb-rope x-risu-lb-rope-two"></div><div class="x-risu-lb-rope x-risu-lb-rope-three"></div>'..
    figure('you')..figure('opponent')..div('canvas-mark','L B / 01')..
    div('arena-bottom','<span>BLUE CORNER · YOU</span><span>'..r.alias..' · RED</span>')..'</div>'
end
local function map(s)
  local h={}
  for i,r in ipairs(G.rivals) do
    h[#h+1]='<div class="x-risu-lb-stop '..(i==s.level and 'x-risu-lb-current' or '')..'">'..
      '<b>'..(i<s.level and '✓' or string.format('%02d',i))..'</b><span>'..r.name..'<small>'..r.venue..'</small></span></div>'
  end
  return div('route',table.concat(h))
end
local function guide()
  return '<details class="x-risu-lb-guide" open><summary>코너 노트 · 플레이 방법</summary>'..
    '<p><b>① 읽기</b> 상대의 3박자 행동은 확정 예고입니다. <b>② 배치</b> 행동 버튼으로 내 3박자를 채웁니다. <b>③ 실행</b> 각 박자는 이동 → 동시 타격 → 회복 순서로 해결됩니다.</p>'..
    '<p><b>거리</b> 0 밀착 / 1 포켓 / 2 잽 거리 / 3 아웃사이드. 전진은 거리 -1, 후퇴는 +1. 양쪽 이동은 합산됩니다. 로프 압박 2에서는 후퇴가 막히므로 피벗하세요.</p>'..
    '<p><b>연결</b> 잽 적중 → 스트레이트 +4. 슬립 성공 → 다음 펀치 +4. 페인트 → 다음 펀치 +2; 페인트 때 상대가 가드했다면 다음 펀치는 가드를 관통합니다. 연결은 바로 다음 박자에만 적용됩니다.</p>'..
    '<p><b>호흡</b> 매 박자 +2, 호흡 행동은 추가 +7. 행동 비용을 낼 수 없으면 호흡으로 전환됩니다. 바디는 체력과 호흡을 함께 깎습니다.</p>'..
    '<p><b>승리</b> 체력 0은 KO, 충격 18은 다운이며 남은 박자를 중단합니다. 한 경기 누적 3다운은 TKO입니다. 1라운드 = 4교환 × 최대 3박자. 제한 라운드 뒤에는 표시된 점수표로 판정합니다.</p>'..
    '<p><b>채점</b> 라운드 총 피해 우세가 10–9, 같으면 10–10. 다운 1회마다 다운된 선수 -1점(최저 7), 높은 쪽은 10점으로 정규화합니다. KO 라운드도 기록용 점수를 남기지만 승패는 KO가 우선합니다. 실제 대회 규정과 다른 게임 전용 채점입니다.</p>'..
    '<p><b>코너</b> 양쪽 호흡 +10·충격 -6, 상대 체력 +6. 나는 치료(+14 체력), 회복(호흡 최대·충격 0), 읽기(첫 박자 +2·가드 관통) 중 하나를 고릅니다. 다음 경기에는 체력과 호흡이 완전히 회복됩니다.</p>'..
    '<p>자동 저장은 현재 채팅에 연결됩니다. 오래된 화면의 버튼은 무효입니다. <b>/boxing</b> 또는 <b>/lastbell</b>로 패널을 다시 열 수 있습니다. 일반 메시지는 원래 채팅대로 처리됩니다.</p></details>'
end
local function home(s)
  local h={arena(s,true),div('intro',title('A THREE-BEAT BOXING GAME','마지막 종이 울리기 전.','세 박자를 읽고, 빈틈 하나를 만든다.<br>동네 체육관에서 미드나이트 타이틀까지.'))}
  h[#h+1]=div('features',stat('시스템','3박자 계획')..stat('커리어','5명의 라이벌')..stat('플레이','버튼 · 자동 저장'))
  h[#h+1]='<h3>당신의 복싱</h3><div class="x-risu-lb-styles">'
  for _,style in ipairs(G.styles) do
    h[#h+1]=btn(s,'style',style.id,tag(style.tag)..'<b>'..style.name..'</b><small>'..style.desc..'</small>',s.style==style.id and 'style selected' or 'style')
  end
  h[#h+1]='</div>'..btn(s,'career','','커리어 시작 <span>→</span>','primary')
  h[#h+1]=div('footnote','결과는 거리와 행동으로 결정됩니다. 명중 주사위·AI 호출·외부 서버가 없습니다.')
  return table.concat(h)
end
local function gym(s)
  local r=G.rivals[s.level]; local h={title('THE ROAD / '..string.format('%02d',s.level),'다음 링으로.','훈련을 고르고 상대의 습관을 읽으세요.'),map(s)}
  h[#h+1]=div('scout',tag('SCOUTING REPORT / '..r.rounds..' ROUNDS')..'<h3>'..r.name..' <small>'..r.alias..'</small></h3><blockquote>“'..r.quote..'”</blockquote><p>'..r.lesson..'</p>')
  h[#h+1]=div('section-head','<h3>오늘의 훈련</h3><span>훈련 포인트 <b>'..s.points..'</b></span>')..'<div class="x-risu-lb-training">'
  for _,u in ipairs(G.upgrades) do h[#h+1]=btn(s,'train',u.id,'<b>'..u.name..'</b><small>'..u.desc..'</small><span>'..s.upgrades[u.id]..' / '..u.max..' · 1P</span>','training-card',s.points<1 or s.upgrades[u.id]>=u.max) end
  h[#h+1]='</div><p class="x-risu-lb-subtle">승리마다 2P. 패배·무승부는 훈련을 유지하고 같은 상대에게 재도전합니다.</p>'
  h[#h+1]=btn(s,'start','','링에 오르기 <span>→</span>','primary')
  return table.concat(h)
end
local function fighter(f,name,side)
  local status=f.combo=='slip' and '회피 연결 +4' or f.combo=='jab' and '스트레이트 연결 +4' or f.combo=='feint' and '페인트 연결 +2' or '연결 없음'
  return div('fighter',div('fighter-name',tag(side)..'<b>'..name..'</b>')..meter('체력',f.hp,f.maxhp,'health')..meter('호흡',f.sta,f.maxsta,'energy')..meter('충격',f.shock,18,'shock')..
    div('fighter-meta','<span>다운 <b>'..f.downs..'/3</b></span><span>로프 <b>'..f.ropes..'/2</b></span>')..
    div('status',status..(f.opening and ' · 가드 관통' or '')))
end
local function ranges(m)
  local h={}
  for i,v in ipairs({'밀착','포켓','잽 거리','아웃사이드'}) do h[#h+1]='<span class="'..(m.distance==i-1 and 'x-risu-lb-range-active' or '')..'"><b>'..i-1 ..'</b>'..v..'</span>' end
  return div('range',table.concat(h))
end
local function score(m)
  if #m.cards==0 then return '<p class="x-risu-lb-subtle">첫 라운드 종료 후 점수가 기록됩니다.</p>' end
  local h={'<table class="x-risu-lb-score"><caption>공개 점수표</caption><thead><tr><th>라운드</th><th>나</th><th>상대</th><th>가한 피해</th></tr></thead><tbody>'}
  for _,c in ipairs(m.cards) do h[#h+1]='<tr><td>R'..c.round..'</td><td>'..c.p..'</td><td>'..c.e..'</td><td>'..c.pDamage..' : '..c.eDamage..'</td></tr>' end
  h[#h+1]='</tbody><tfoot><tr><th>합계</th><th>'..m.totalP..'</th><th>'..m.totalE..'</th><td></td></tr></tfoot></table>'
  return table.concat(h)
end
local function plan(s)
  local m=s.match; local h={div('section-head','<h3>상대의 다음 3박자</h3>'..tag('INTENT / LOCKED')),'<div class="x-risu-lb-beats">'}
  for i,id in ipairs(m.intent) do local a=G.actions[id]
    h[#h+1]=div('intent','<small>0'..i..' · '..a.short..'</small><b>'..a.name..'</b><span>'..a.tip..'</span>')
  end
  h[#h+1]='</div>'
  if m.adapt~='' then h[#h+1]=div('callout',m.adapt) end
  h[#h+1]=div('section-head','<h3>나의 3박자</h3><span>'..#m.plan..' / 3 배치</span>')..'<div class="x-risu-lb-beats">'
  for i=1,3 do local id=m.plan[i]
    h[#h+1]=div('slot'..(id and ' filled' or ''),'<small>0'..i..'</small><b>'..(id and G.actions[id].name or '행동 선택')..'</b><span>'..(id and '호흡 -'..G.cost(m.p,id) or '아래 버튼으로 채우세요')..'</span>')
  end
  h[#h+1]='</div>'..div('plan-tools',btn(s,'undo','','마지막 취소',nil,#m.plan==0)..btn(s,'clear','','모두 비우기',nil,#m.plan==0))
  h[#h+1]='<div class="x-risu-lb-actions">'
  for _,id in ipairs(G.order) do local a=G.actions[id]
    h[#h+1]=btn(s,'add',id,'<span><b>'..a.name..'</b><em>−'..G.cost(m.p,id)..'</em></span><small>'..a.tip..'</small>','action',#m.plan==3)
  end
  h[#h+1]='</div>'
  local rows=G.project(s); local low=false
  for _,v in ipairs(rows) do if v.low then low=true end end
  if low then h[#h+1]=div('callout','이 계획은 도중에 호흡이 부족해질 수 있습니다. 부족한 행동은 자동으로 호흡으로 바뀝니다.') end
  h[#h+1]=btn(s,'execute','','3박자 실행 <span>→</span>','primary',#m.plan~=3)
  return table.concat(h)
end
local function replay(s)
  local m=s.match; local h={title('EXCHANGE / REPLAY','방금, 링 위에서.','각 박자의 이동과 타격을 동시에 계산한 결과입니다.')}
  for _,row in ipairs(m.last) do
    h[#h+1]=div('replay-row','<b class="x-risu-lb-beat-num">0'..row.beat..'</b><div><strong>'..G.actions[row.p].name..' <span>vs</span> '..G.actions[row.e].name..'</strong><p>'..row.notes..'</p></div><span class="x-risu-lb-impact">'..row.pDamage..' <small>/ '..row.eDamage..'</small></span>')
  end
  if #m.last<3 then h[#h+1]=div('callout','다운 또는 경기 종료로 남은 박자를 중단했습니다.') end
  h[#h+1]=btn(s,'continue','',m.result and '경기 결과 보기 →' or (m.exchange==4 and '코너로 돌아가기 →' or '다음 교환 계획 →'),'primary')
  return table.concat(h)
end
local function corner(s)
  local m=s.match
  return div('corner',title('BETWEEN ROUNDS','숨을 고르는 시간.','R'..m.round..' 종료. 기본 회복 후 아래 선택 하나가 다음 라운드에 적용됩니다.')..score(m)..
    div('corner-options',btn(s,'corner','ice','<b>차가운 수건</b><small>체력 +14. 맞교환으로 지친 몸을 치료합니다.</small>','choice')..
    btn(s,'corner','air','<b>깊게, 한 번 더</b><small>호흡 최대·충격 0. 다운 위기를 끊습니다.</small>','choice')..
    btn(s,'corner','read','<b>약점을 짚어 줘</b><small>첫 박자 펀치 +2·가드 관통. 시작부터 빈틈을 찌릅니다.</small>','choice')))
end
local function fight(s)
  local m=s.match; local r=G.rivals[s.level]
  local h={div('bout-heading',tag('BOUT '..string.format('%02d',s.level)..' / '..r.venue)..'<b>R'..m.round..' / '..m.rounds..' <small>교환 '..m.exchange..' / 4</small></b>'),arena(s),
    div('fighters',fighter(m.p,'당신','BLUE CORNER')..fighter(m.e,r.name,r.alias)),ranges(m)}
  if m.mode=='plan' then h[#h+1]=plan(s) elseif m.mode=='replay' then h[#h+1]=replay(s) else h[#h+1]=corner(s) end
  h[#h+1]='<details class="x-risu-lb-details"><summary>스카우팅 · 점수표 · 경기 기록</summary><p>'..r.lesson..'</p>'..score(m)
  for i=#m.log,1,-1 do h[#h+1]='<p class="x-risu-lb-log">'..esc(m.log[i])..'</p>' end
  h[#h+1]='</details>'
  return table.concat(h)
end
local function result(s)
  local m=s.match; local r=m.result; local won=r.winner=='player'
  return div('result',tag(r.method..' / OFFICIAL RESULT')..'<h2>'..(won and '당신의 라운드.' or r.winner=='draw' and '아직, 끝나지 않았다.' or '다시 일어설 시간.')..'</h2><p>'..(won and G.rivals[s.level].name..'에게 승리했습니다. 훈련 포인트 +2.' or '훈련 기록은 유지됩니다. 상대의 예고를 다시 읽고 재도전하세요.')..'</p>'..
    div('features',stat('가한 피해',m.p.damage)..stat('적중',m.p.hits)..stat('내 다운',m.p.downs))..score(m)..
    btn(s,'resultNext','',won and (s.level==5 and '챔피언 벨트 받기 →' or '다음 라이벌 →') or '체육관으로 →','primary'))
end
function G.render(s)
  local h={'<div class="x-risu-lb" lang="ko"><header class="x-risu-lb-header"><b>LB<span> / LAST BELL</span></b><span>TURN-BASED BOXING</span></header><main class="x-risu-lb-main">'}
  if s.resetPending then
    h[#h+1]=div('callout','<h3>커리어를 새로 시작할까요?</h3><p>현재 채팅의 경기·훈련·전적이 초기화됩니다.</p>'..btn(s,'resetYes','','초기화하고 시작','danger')..btn(s,'resetCancel','','돌아가기'))
  elseif s.screen=='home' then h[#h+1]=home(s)
  elseif s.screen=='gym' then h[#h+1]=gym(s)
  elseif s.screen=='fight' then h[#h+1]=fight(s)
  elseif s.screen=='result' then h[#h+1]=result(s)
  elseif s.screen=='champion' then
    h[#h+1]=arena(s,true)..div('result',title('MIDNIGHT CHAMPION','마지막까지, 서 있었다.','다섯 개의 링을 지나 챔피언이 되었습니다. 당신의 리듬이 이 도시의 밤에 남습니다.')..div('belt','★  LAST BELL CHAMPION  ★')..div('features',stat('승리',s.wins)..stat('패배',s.losses)..stat('클리어','5 / 5'))..btn(s,'resetAsk','','다른 스타일로 새 커리어','primary'))
  end
  if s.help then h[#h+1]=guide() end
  h[#h+1]='</main><footer class="x-risu-lb-footer"><span>A LOCAL BOXING STORY · v1.0</span><div>'..btn(s,'help','',s.help and '설명 닫기' or '플레이 방법')..btn(s,'resetAsk','','새 커리어')..'</div></footer></div>'
  return table.concat(h)
end
