-- LAST BELL: a deterministic, three-beat boxing puzzle. No BattleSim engine code.
local G = {}
G.version = 1
G.key = 'last_bell_campaign_v1'
G.order = {'jab','cross','hook','body','guard','low','slip','feint','in','out','pivot','breathe','clinch'}
G.actions = {
  jab={name='잽',short='JAB',cost=4,damage=4,kind='head',range={1,2},tip='포켓·잽 거리 / 4 피해. 적중 직후 스트레이트 +4.'},
  cross={name='스트레이트',short='CROSS',cost=7,damage=8,kind='head',range={1,2},tip='포켓·잽 거리 / 8 피해. 잽 적중 또는 슬립 성공 직후 +4.'},
  hook={name='훅',short='HOOK',cost=8,damage=11,kind='head',range={1},tip='포켓 전용 / 11 피해. 슬립을 잡지만 거리가 벌어지면 빗나감.'},
  body={name='바디',short='BODY',cost=6,damage=4,kind='body',range={0,1,2},tip='밀착~잽 거리 / 4 피해·호흡 7 감소. 하이 가드 공략.'},
  guard={name='하이 가드',short='HIGH',cost=0,tip='머리 피해 70% 감소. 바디는 막지 못함.'},
  low={name='로우 가드',short='LOW',cost=0,tip='바디 피해·호흡 손실 80% 감소. 머리 피해는 20% 증가.'},
  slip={name='슬립',short='SLIP',cost=3,tip='잽·스트레이트 회피. 성공 직후 펀치 +4. 훅·바디에는 무방비.'},
  feint={name='페인트',short='FEINT',cost=2,tip='다음 박자 펀치 +2. 상대가 이 박자 가드라면 다음 펀치가 가드 관통.'},
  ['in']={name='전진',short='STEP IN',cost=2,move=-1,tip='한 칸 접근하고 상대를 로프로 압박. 이번 박자는 공격하지 않음.'},
  out={name='후퇴',short='STEP OUT',cost=2,move=1,tip='한 칸 벌리며 내 로프 압박 +1. 압박 2에서는 후퇴 불가.'},
  pivot={name='피벗',short='PIVOT',cost=3,tip='내 로프 압박을 0으로. 거리 유지·머리 피해 30% 감소.'},
  breathe={name='호흡',short='BREATHE',cost=0,tip='기본 회복에 추가 호흡 +7·충격 -3. 방어 효과는 없음.'},
  clinch={name='클린치',short='CLINCH',cost=4,tip='밀착·포켓에서 양쪽 공격을 중단. 중앙 잽 거리로 복귀·충격 -4.'}
}
G.styles = {
  {id='reader',name='아웃복서',tag='READ & RETURN',desc='슬립·피벗 비용 -1. 회피로 기회를 만드는 선수.'},
  {id='pressure',name='인파이터',tag='CLOSE THE GAP',desc='훅·바디 피해 +2. 가까이 붙어 호흡을 무너뜨리는 선수.'},
  {id='engine',name='페이스메이커',tag='STAY THE DISTANCE',desc='최대 호흡 +6. 긴 경기와 공격 연속 배치에 유리.'}
}
G.rivals = {
  {name='한도윤',alias='THE METRONOME',venue='동네 체육관',color='#78cfc3',rounds=2,hp=65,sta=26,power=0,
   quote='박자를 알면, 주먹이 보인다.',lesson='잽·스트레이트에는 슬립. 하이 가드가 보이면 바디. 먼저 기본 패턴을 익히세요.',
   patterns={{'jab','cross','breathe'},{'guard','jab','cross'},{'in','body','guard'}}},
  {name='백태오',alias='IRON TIDE',venue='항구 창고 링',color='#efa170',rounds=3,hp=82,sta=30,power=1,
   quote='물러날 곳이 언제까지 있을까?',lesson='전진 뒤 훅이 이어집니다. 후퇴로 훅을 비우되 로프 압박 2가 되기 전에 피벗하세요.',
   patterns={{'in','hook','body'},{'in','body','hook'},{'guard','breathe','cross'},{'jab','in','hook'}}},
  {name='서이서',alias='GLASS NEEDLE',venue='옥상 야간 리그',color='#b3a0f3',rounds=3,hp=78,sta=32,power=1,
   quote='네가 던지기 전에, 나는 비어 있어.',lesson='슬립을 잽으로 쫓지 마세요. 포켓에서 훅을 노리거나 바디로 호흡을 빼앗으세요.',
   patterns={{'slip','cross','out'},{'jab','slip','cross'},{'in','slip','hook'},{'low','jab','breathe'}}},
  {name='권무진',alias='THE LOCK',venue='시민 챔피언십',color='#e5c477',rounds=4,hp=104,sta=32,power=1,
   quote='문은 없다. 네가 만들어야 한다.',lesson='가드를 향한 페인트 다음 펀치는 방어를 관통합니다. 높은 가드와 낮은 가드를 구분하세요.',
   patterns={{'guard','guard','cross'},{'low','body','guard'},{'in','guard','hook'},{'guard','breathe','body'}}},
  {name='윤세라',alias='LAST LIGHT',venue='미드나이트 타이틀전',color='#f17788',rounds=4,hp=110,sta=36,power=2,
   quote='마지막 종이 울릴 때, 누가 서 있을까?',lesson='반복한 첫 행동에 다음 교환부터 대응합니다. 예고는 확정되어 있으니 변화를 읽고 계획하세요.',
   patterns={{'feint','cross','hook'},{'in','body','cross'},{'slip','cross','guard'},{'jab','out','breathe'},{'guard','body','hook'}}}
}
G.upgrades = {
  {id='lungs',name='로드워크',desc='최대 호흡 +4',max=3},
  {id='power',name='샌드백',desc='모든 펀치 피해 +1',max=3},
  {id='heart',name='기초 체력',desc='최대 체력 +8',max=3}
}
