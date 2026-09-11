# Primal Apex 모듈 공유 계약 v1

## 저장과 화면

네 모듈은 동일 채팅에서 `getState(id, 'primal_apex_state_v1')` / `setState`를 사용한다. 실제 채팅 변수 이름은 `__primal_apex_state_v1`이다. `id`는 RisuAI가 매 호출에 주는 접근 토큰이며 저장 식별자로 사용하지 않는다. 모듈 namespace는 각각 달라도 공유 키는 같다.

| 패러미터 | 형식과 용도 |
|---|---|
| `version` | 저장 스키마. 현재 1. 다른 버전은 덮어쓰지 않고 거부 |
| `revision` | 변경 저장마다 1 증가. 오래된 버튼 검증 |
| `screen` | `hub`, `matchmaking`, `training`, `story`, `calendar`, `prep`, `entrance`, `battle` |
| `nextId` | 장면·경기 ID 생성용 단조 증가 번호 |
| `rng` | 매치메이킹·경기 시드 발급용 LCG 상태 |
| `scenario` | `id`, `mode=free/tournament`, `stage` |
| `calendar.now` | 1일차 00:00을 0으로 한 누적 분 |
| `player` | 이름, 최대 자원 스펙, 보유 스킬, 장착 ID 목록, 강화 자원 |
| `story.relationships` | NPC ID → `{affinity, respect}` |
| `story.matchLeads` | NPC ID → `{kind, at}` |
| `story.flags` | 이후 시나리오 확장용 값 |
| `story.recentSummaries` | `{sceneId,npcId,at,text}`의 최근 8개 기록 |
| `story.consumed` | 완료/취소한 장면 ID → true |
| `story.afterBattle` | 미정리 경기 후 상호작용의 경기 결과 또는 false |
| `story.contentMode` | `SFW` 또는 명시적으로 활성화한 `MATURE` |
| `schedule` | `{id,opponentId,at,venueId,reason,status}` 배열 |
| `matchHistory` | 완료 경기 결과 배열 |
| `session` | 현재 story/battle 세션 또는 false |
| `notice` | 현재 화면의 안내 문구. 선택 사항 |

Lua JSON의 빈 테이블은 객체로 왕복할 수 있으므로 빈 목록도 Lua table로 취급한다. JavaScript 연동 시 빈 `{}`와 `[]` 양쪽을 허용한다.

## 버튼과 화면 소유

```text
pa;<module>;<revision>;<action>;<value>
```

예: `pa;hub;12;open;matchmaking`.

RisuAI는 버튼을 활성화된 모든 Lua 모듈에 전달한다. 각 모듈은 자신의 접두사만 처리하고 현재 화면과 revision을 재검증한다. 허브는 `hub/calendar/prep/entrance/battle` 화면을 소유한다. 나머지 세 모듈은 자신의 이름과 같은 화면 하나를 소유한다.

모듈 이동은 `screen`을 저장하는 것으로 끝난다. 다음 렌더에서 이전 모듈은 HTML을 추가하지 않고 새 모듈만 표시한다. 렌더는 최신 메시지에만 패널을 붙이며, 조회 자체로 저장을 바꾸지 않는다.

`/apex`는 활성 세션을 유지한다. 단순 메뉴 탐색 중이라면 허브로 복귀한다.

## 저장 처리

각 모듈의 `M.handle`은 전달받은 상태 복사본을 수정한다. 공통 런타임이 성공 결과를 저장한다. 비동기 입력이나 모델 응답 후에는 현재 revision을 다시 확인한다. 실패한 선택은 복사본을 버린다.

```lua
M.render(state)                        -- 현재 모듈의 최소 HTML
M.handle(triggerId, state, action, value)
-- 반환: ok, errorMessage, optionalAfterCommitFunction
```

LLM 호출처럼 기다림이 긴 작업은 장면 상태를 먼저 저장한 뒤 실행한다. 호출 실패 시 같은 장면에서 재시도하거나 일반 채팅으로 진행한다. 응답 중 상태가 바뀌었다면 오래된 응답은 적용하지 않는다.

초기 설계의 `options/enter/handle`을 추가 관리 계층으로 구현하지 않고, 최소 UI의 `render/handle`로 통합했다. 모듈별 규칙은 모듈 내부에 유지한다.

## 스토리 세션

```lua
session = {
    kind = 'story',
    id = 'scene_1',
    npcId = 'rookie_cycle',
    interaction = 'TALK',
    placeId = 'gym',
    startedAt = 540,
    deadline = false, -- 다음 경기 시각 또는 false
    allowedLeads = {'NONE', 'CHALLENGE', 'REMATCH_OFFER'},
    closing = false,
    afterMatch = false, -- 경기 후 장면이면 직전 경기 결과
}
```

`editRequest`는 이 세션의 사실과 허용 결과를 일반 모델 요청에 주입한다. `onOutput`은 현재 캐릭터 응답의 종료 패킷을 검증한다. 버튼에서 직접 호출한 LLM 응답도 동일한 정산 함수를 사용한다.

현재 장면 ID, 정확한 필드 목록, 키워드, 시간 범위를 모두 검증한다. 결과를 한 번 적용하면 세션을 닫고 허브로 이동한다. 자유 서술에 포함된 숫자는 패러미터 변경으로 해석하지 않는다.

## BattleSim 세션

```lua
session = {
    kind = 'battle',
    matchId = 'match_2',
    seed = 12345,
    input = {
        contractVersion = 1,
        match = {},          -- 확정 일정 스냅샷
        player = {},         -- 정비 확정 시 플레이어 스냅샷
        opponent = {
            id = 'rookie_cycle', name = '훈련생',
            stats = {maxHp=100,maxStamina=100,maxBreakGauge=100,maxDownCount=3},
            skills = {{id='rookie_power_strike',level=1}},
            aiMode = 'existing', strategy = 'rookie_cycle', judgment = 1,
        },
    },
    config = {},             -- 기존 B.newState가 받는 config
    entranceReady = false,
    battle = nil,            -- 경기 개시 이후 기존 BattleSim 상태
}
```

정비 확정 시 `player.loadout`의 ID를 보유 스킬의 실제 레벨과 결합해 `config.playerDeck`으로 만든다. `config.enemyDeck`은 확정 NPC의 덱이다. `B.newState(config, seed)` 이후 입력 스냅샷의 최대 자원 스펙을 적용한다.

원본 BattleSim의 `bs;...` 버튼은 허브가 `pa;hub;<revision>;battle;bs;...` 형태로 감싼다. `act/skill/execute/continue/livefast`만 전달한다. 기존 내부 턴 토큰 검증도 유지한다.

경기 완료 출력:

```lua
{
    matchId='match_2', opponentId='rookie_cycle',
    outcome='PLAYER_WIN', winner='player',
    rounds=3, turns=24, playerDowns=1, enemyDowns=3,
    at=2040, playerDeck={}, enemyDeck={},
}
```

완료 시 허브가 일정 상태를 `completed`로 바꾸고 기록·보상·시간을 함께 저장한다. 같은 결과를 다시 정산하지 않는다. 결과 요약은 `story.afterBattle`로 스토리모드에 전달한다.

## 유지보수 경계

- 네 모듈의 공통 계약은 `src/shared.lua`, `src/data.lua`, `src/runtime.lua`에서 함께 빌드한다.
- BattleSim은 허브에만 들어간다. 다른 모듈에는 UI에 필요한 스킬 이름·설명·레벨 한도 메타데이터만 넣는다.
- 새 NPC는 기본 데이터와 장소 연결을 추가한다. 새 성장 스킬은 실제 BattleSim 정의와 강화 카탈로그를 함께 갱신한다.
- 저장 구조 변경 시 `version`을 올리고 필요한 마이그레이션을 추가한다. 이번 버전은 미래 버전이나 손상된 저장을 초기화하지 않는다.
