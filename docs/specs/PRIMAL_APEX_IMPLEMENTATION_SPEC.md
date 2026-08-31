# Primal Apex 캐릭터 봇 구현 명세

> 문서 상태: 설계 초안 1.0  
> 대상 플랫폼: RisuAI 캐릭터 카드 + Lua 모듈  
> 기준 전투 코어: `projects/battle-sim-lua/BattleSim.lua` 및 `projects/battle-sim-poc`  
> 작성 기준일: 2026-08-31

## 초록

**Primal Apex**는 무제한 라운드, KO Only 혼성 복싱 리그를 무대로 하는 RisuAI 캐릭터 봇이다. 플레이 경험은 두 축으로 구성된다. 첫째는 공격·방어·회피의 상성, 액티브·패시브 스킬, 제한된 난수를 사용하는 턴제 복싱 전투다. 둘째는 다양한 선수와의 경기·훈련·일상·라이벌리·친밀 관계를 통해 스토리와 성장 경로가 달라지는 캐릭터 중심 어드벤처다.

구현의 핵심 원칙은 **Lua가 게임의 사실을 결정하고 LLM이 그 사실을 표현한다**는 권위 분리다. HP, STA, BRK, 주사위, 행동 결과, 스킬, 다운, KO, 보상, 시간, 관계 수치, 이벤트 플래그 등 재현성과 일관성이 필요한 상태는 Lua가 관리한다. LLM은 Lua가 제공한 구조화 패킷을 바탕으로 경기 요약, 대화, 훈련, 일상, SFW·성인 장면을 서술하며, 사용자의 자연어가 기계적 판정을 요구할 경우 제한된 의미의 아웃바운드 패킷을 출력한다.

정확한 명령과 UI 버튼은 Lua가 직접 처리하고, 자연어 해석이 필요한 경우에만 LLM을 의미 변환기로 사용한다. 이 하이브리드 구조는 전투의 정확성·속도와 캐릭터 어드벤처의 자유도를 동시에 확보하는 것을 목표로 한다.

---

## 1. 제품 목표와 사용자 경험

### 1.1 전투 축

- 공격·방어·회피의 읽기 쉬운 기본 상성
- d6 기반의 직관적인 운 요소
- HP, 스태미너(STA), 브레이크(BRK)의 서로 다른 압박
- 액티브 3개와 패시브 1개를 중심으로 하는 간결한 로드아웃
- 상대의 공개 행동 기록과 버릇을 활용하는 제한적 분석
- 훈련과 관계 이벤트를 통해 획득하는 새 전술
- 동일 입력과 동일 시드가 동일 결과를 만드는 재현성

### 1.2 캐릭터 어드벤처 축

- 경기 결과뿐 아니라 **어떻게 싸웠는가**에 반응하는 캐릭터
- 선수별 말투, 생활, 욕망, 약점, 라이벌리와 상호 관계
- 훈련·회복·일상·비밀·갈등·친밀 장면
- affection, trust, respect, tension의 다축 관계 상태
- 관계와 스토리를 통해 얻는 정보, 훈련, 스킬과 경기 기회
- 업적, 평판, 재대결, 시즌 이벤트에 의한 장기 변화

### 1.3 범위 원칙

- 초기 버전은 1 대 1 전투에 집중한다.
- 기본 턴은 Lua UI만으로 빠르게 진행할 수 있다.
- LLM 경기 묘사는 선택적이다. 전체 턴, 라운드 요약, 하이라이트 전용 모드를 지원한다.
- 성인 콘텐츠는 세계관 설정과 실제 출력 모드를 분리하고 사용자 설정·장면 접근 조건을 적용한다.
- 다인 교대전, 복잡한 경제, 스폰서 시뮬레이션은 후순위다.

---

## 2. 설계 원칙

### 2.1 권위 분리

| 주체 | 소유하는 것 | 소유하지 않는 것 |
|---|---|---|
| 사용자 | 의도, 선택, 자유 행동, 대사 | 판정 결과와 NPC 내면 |
| Lua | 수치, 상태, RNG, 유효성, 보상, 관계 변화, 이벤트 접근성 | 산문과 캐릭터 대사 |
| LLM | 내러티브, 대사, 분위기, 자연어 의미 분류 | 임의 수치 변화, 승패, 보상, 스킬 해금 |
| Lorebook | 세계관, 인물 연기, 패킷 해석, 장면 규칙 | 지속 상태와 수치 계산 |
| RisuAI UI | 입력 버튼, 패널, 에셋 표시 | 게임 규칙의 최종 판정 |

핵심 문장은 다음과 같다.

> Lua owns truth. LLM owns expression. Player owns intent.

### 2.2 입력 경로의 분리

1. **정확한 명령:** `/Match Start`, `/Status`, `/Rest` 등은 `onStart`에서 Lua가 직접 처리한다.
2. **버튼:** `risu-btn` 코드는 `onButtonClick`에서 Lua가 직접 처리한다.
3. **자연어:** “한세연에게 준비됐다고 말하고 링으로 향한다” 같은 문장은 LLM이 의미 패킷으로 변환하고 `onOutput`에서 Lua가 처리한다.
4. **순수 대화:** 기계적 변화가 없으면 패킷 없이 LLM과 사용자가 대화를 계속한다.

### 2.3 상태 변경 원칙

- 외부 입력은 즉시 상태를 수정하지 않고 명령으로 정규화한다.
- 각 엔진은 `events`, `mutations`, `ui`, `narrative`, `nextPhase`를 반환한다.
- GameController가 모든 변경을 검증하고 한 번에 커밋한다.
- 모든 커밋은 revision을 증가시킨다.
- 같은 패킷·버튼·보상은 한 번만 소비한다.
- LLM 출력은 항상 불신 입력으로 검증한다.

---

## 3. 상위 아키텍처

```text
사용자
 ├─ 슬래시 명령 ────────────────┐
 ├─ Lua UI 버튼 ────────────────┤
 └─ 자연어 ─→ LLM ─→ N2L 패킷 ┤
                                  ▼
                           GameController
                                  │
                ┌─────────────────┼─────────────────┐
                ▼                 ▼                 ▼
          Protocol/Flow       Game Engines      State/RNG
                │                 │                 │
                └─────────────────┼─────────────────┘
                                  ▼
                             State Commit
                             ┌────┴────┐
                             ▼         ▼
                           Lua UI   L2N 패킷
                                       │
                                       ▼
                                      LLM
```

### 3.1 소스 구조 권장안

RisuAI 배포본은 하나의 Lua 모듈일 수 있지만 개발 소스는 논리적으로 분리한다.

```text
primal_apex/
├─ src/
│  ├─ controller/
│  │  ├─ GameController.lua
│  │  ├─ ProtocolEngine.lua
│  │  └─ FlowEngine.lua
│  ├─ core/
│  │  ├─ StateEngine.lua
│  │  ├─ RNGEngine.lua
│  │  └─ EventLogEngine.lua
│  ├─ battle/
│  │  ├─ MatchEngine.lua
│  │  ├─ BattleEngine.lua
│  │  ├─ SkillEngine.lua
│  │  ├─ StatusEffectEngine.lua
│  │  ├─ FighterAIEngine.lua
│  │  ├─ ScoutEngine.lua
│  │  └─ MatchSummaryEngine.lua
│  ├─ campaign/
│  │  ├─ CalendarEngine.lua
│  │  ├─ RecoveryEngine.lua
│  │  ├─ TrainingEngine.lua
│  │  ├─ ProgressionEngine.lua
│  │  ├─ RelationshipEngine.lua
│  │  ├─ StoryEventEngine.lua
│  │  └─ MemoryEngine.lua
│  ├─ league/
│  │  ├─ MatchmakingEngine.lua
│  │  ├─ RankingEngine.lua
│  │  ├─ EconomyEngine.lua
│  │  ├─ ReputationEngine.lua
│  │  └─ AchievementEngine.lua
│  ├─ presentation/
│  │  ├─ NarrativeBridge.lua
│  │  ├─ UIEngine.lua
│  │  └─ AssetEngine.lua
│  └─ data/
│     ├─ fighters.lua
│     ├─ skills.lua
│     ├─ statuses.lua
│     ├─ events.lua
│     └─ achievements.lua
├─ tests/
└─ build.ps1
```

빌드 단계에서 위 소스를 RisuAI용 단일 Lua 파일과 캐릭터 카드로 패키징한다.

---

## 4. 핵심 상태 모델

```lua
CampaignState = {
    schemaVersion = 1,
    revision = 42,
    runId = "run_0001",

    flow = {
        phase = "STORY_FREE",
        owner = "LLM",
        activeSceneId = nil
    },

    protocol = {
        nextRequestId = 18,
        pending = nil,
        consumed = {}
    },

    rng = {
        battle = {...},
        policy = {...},
        training = {...},
        story = {...},
        matchmaking = {...}
    },

    calendar = {...},
    player = {...},
    roster = {...},
    relationships = {...},
    story = { flags = {}, completedEvents = {} },
    league = { rank = 0, scheduledMatch = nil },
    achievements = {},
    memory = {...},

    match = nil,
    presentation = nil
}
```

상태는 다음처럼 분리한다.

- `CampaignState`: 영구 진행
- `MatchState`: 현재 경기의 일시 상태
- `PresentationState`: 애니메이션과 결과 확인 단계
- `PendingRequest`: LLM에 보낸 요청과 허용 응답
- `EventLog`: 재현·디버깅·요약용 구조화 로그

---

## 5. 패킷 프로토콜

### 5.1 기본 형식

초기 구현은 한 줄 key-value 패킷을 사용한다.

```text
<PA_CMD|v=1|req=r17|rev=42|op=MATCH_START>
```

복잡한 사실 전달에는 Lua가 생성하는 이벤트 패킷을 사용한다.

```text
<PA_EVT|v=1|id=e204|rev=43|type=MATCH_END|winner=player|finish=KO|tags=COMEBACK_WIN,SIGNATURE_FINISH|reply=NO_PACKET>
```

### 5.2 패킷 종류

| 방향 | 종류 | 목적 |
|---|---|---|
| Lua → LLM | `PA_EVT` | 확정된 사건을 내러티브화 |
| Lua → LLM | `PA_REQ` | 허용된 선택 또는 의미 분류 요청 |
| LLM → Lua | `PA_CMD` | 선택·의도·장면 종료 제안 |
| Lua → UI | 내부 ViewModel | 패널과 버튼 렌더링 |

### 5.3 패킷 안전 규칙

- `op`, `type`, `target`은 허용 enum과 내부 ID만 사용한다.
- 수치 변화량은 LLM이 출력하지 않는다.
- `req`, `rev`가 현재 pending request와 일치해야 한다.
- 이미 소비한 `req`는 다시 실행하지 않는다.
- 잘못된 패킷은 추측 복구하지 않고 상태를 유지한다.
- 패킷은 `editDisplay`에서 숨기고, 필요하면 다음 요청 문맥에서도 제거한다.

### 5.4 `/Match Start` 예시

#### 직접 명령 경로(권장)

```text
사용자 /Match Start
→ onStart
→ FlowEngine 검증
→ MatchEngine 초기화
→ stopChat
→ Lua 전투 UI
```

#### 자연어 경로

```text
사용자: 한세연에게 준비됐다고 말하고 링으로 향한다.
→ LLM 내러티브
→ <PA_CMD|v=1|req=r17|rev=42|op=MATCH_START>
→ onOutput
→ ProtocolEngine
→ GameController
→ MatchEngine
→ Lua 전투 UI
```

---

## 6. 기술 요소

### 6.1 RisuAI Lua 통합

- `onStart`: 사용자 메시지와 정확한 명령 감지
- `onOutput`: LLM의 N2L 패킷 감지
- `onButtonClick`: 전투·훈련·메뉴 버튼 처리
- `listenEdit('editDisplay')`: 현재 상태 패널 추가 및 패킷 숨김
- `listenEdit('editRequest')`: 필요한 상태·이벤트 패킷의 프롬프트 주입 또는 과거 패킷 제거
- `getState`/`setState`: 직렬화 가능한 캠페인 상태 저장
- `getChatVar`/`setChatVar`: Lorebook에서 참조할 짧은 pending context 제공
- `getFullChat`: 최신 입력·출력 확인
- `stopChat`: Lua 단독 명령의 LLM 호출 차단
- `addChat`/`removeChat`: 필요한 최소 시스템성 전환 메시지 처리

### 6.2 데이터 주도 설계

다음 항목은 함수 내부 하드코딩보다 데이터 테이블로 정의한다.

- 선수 프로필과 전투 정책
- 27+3 전투 결과표
- 스킬과 패시브
- 상태이상
- 훈련
- 스토리 이벤트와 조건
- 관계 선호·금기
- 업적
- 에셋 경로 규칙

### 6.3 결정론과 테스트

- 전투 RNG와 정책 RNG를 분리한다.
- 훈련·스토리·매치메이킹 RNG도 별도 스트림으로 둔다.
- 모든 RNG draw index를 로그에 남긴다.
- 같은 시드와 명령열로 같은 결과를 재생할 수 있어야 한다.
- 엔진별 순수 함수 테스트와 전체 캠페인 통합 테스트를 병행한다.

### 6.4 버전과 마이그레이션

- `schemaVersion`: 저장 데이터 구조 버전
- `protocolVersion`: LLM 패킷 문법 버전
- `rulesetVersion`: 전투 수치와 결과표 버전
- 오래된 저장은 StateEngine의 순차 마이그레이션을 거친다.
- 구버전 카드의 LLM 계산형 상태를 새 상태로 자동 변환하려 하지 않고 새 캠페인으로 시작하는 것을 기본으로 한다.

---

## 7. 전체 플레이 흐름

```text
HUB
→ MATCHMAKING
→ PRE_MATCH
→ MATCH
→ POST_MATCH
→ RECOVERY
→ TRAINING
→ STORY_FREE / STORY_EVENT
→ 다음 MATCHMAKING
```

### 7.1 매치메이킹

1. 사용자가 상대를 요청하거나 자동 배정을 선택한다.
2. MatchmakingEngine이 상대의 일정·부상·랭킹·최근 대전을 검증한다.
3. CalendarEngine이 경기 날짜를 예약한다.
4. LLM은 한세연 등의 인물을 통해 대전 성사 장면을 묘사한다.

### 7.2 경기 준비

1. 플레이어가 스킬 로드아웃과 세컨드를 선택한다.
2. ScoutEngine이 공개 가능한 상대 정보만 표시한다.
3. `/Match Start` 또는 버튼으로 경기를 시작한다.
4. MatchEngine이 로드아웃·상태를 잠그고 RNG를 초기화한다.

### 7.3 경기

1. UI에서 공격·방어·회피와 스킬을 선택한다.
2. FighterAIEngine이 같은 턴의 플레이어 선택을 보지 않고 상대 행동을 정한다.
3. SkillEngine과 StatusEffectEngine이 사전 효과를 준비한다.
4. BattleEngine이 주사위, 결과표, 자원, 그로기, 다운, KO를 처리한다.
5. Lua UI가 결과를 표시한다.
6. 설정에 따라 LLM은 매 턴, 라운드, 중요 하이라이트만 묘사한다.

### 7.4 경기 후

1. MatchSummaryEngine이 결정타, 다운, 역전, 스타일을 요약한다.
2. Recovery, Ranking, Economy, Reputation, Achievement 엔진이 결과를 계산한다.
3. StoryEventEngine이 경기 후 이벤트를 선정한다.
4. NarrativeBridge가 L2N 패킷을 만들고 LLM이 결과 장면을 작성한다.

### 7.5 훈련과 스토리

1. 훈련 선택은 TrainingEngine이 비용·시간·피로·성과를 판정한다.
2. ProgressionEngine이 숙련도와 스킬 학습 진도를 반영한다.
3. 자연어 대화 중 기계적 의미가 생기면 LLM이 N2L intent를 출력한다.
4. RelationshipEngine이 실제 관계 변화를 확정한다.
5. StoryEventEngine과 MemoryEngine이 후속 사건과 기억을 갱신한다.

---

## 8. LLM과 Lua 상호작용 시나리오

### 8.1 Lua 단독 구간

적용 대상:

- 정확한 명령
- 메뉴와 전투 버튼
- 일반 exchange
- 다운 대기와 기상
- 기본 인터벌
- 상태 패널

```text
UI2L → Lua 판정 → State Commit → L2UI
```

### 8.2 LLM 단독에 가까운 구간

적용 대상:

- 수치 변화 없는 잡담
- 이미 확정된 사건에 대한 감상
- 환경 관찰
- 기계적 의미가 없는 캐릭터 롤플레이

```text
U2N → LLM → N2U
```

### 8.3 교차 구간

적용 대상:

- 자연어 경기 신청
- 관계 변화 가능 장면
- 특수 훈련
- 스킬 전수
- 경기 후 분기
- 친밀 장면 진입·종료

```text
Lua L2N 사실/요청
→ LLM 내러티브
→ 사용자 자유 응답
→ LLM N2L intent
→ Lua 검증·판정·커밋
→ 후속 L2N 결과
```

### 8.4 경기 종료 패킷 예시

```text
<PA_EVT|v=1|id=e204|rev=43|type=MATCH_END
|winner=player|finish=KO|rounds=5
|tags=COMEBACK_WIN,BODY_DAMAGE_FOCUS,SIGNATURE_FINISH
|reply=PACKET_IF_MECHANICAL>
```

LLM은 이 패킷을 보고 결정타와 경기 후 반응을 묘사하지만, 추가 보상이나 부상을 창작하지 않는다.

### 8.5 관계 intent 예시

```text
<PA_CMD|v=1|req=r31|rev=57|op=STORY_INTENT
|target=sol_jiyoon|intent=PRAISE_SKILL|tone=SINCERE>
```

RelationshipEngine은 솔지윤의 성격, 현재 respect·trust, 최근 경기 결과, 공개·사적 장소 여부를 종합해 변화량과 `visibleReaction`을 확정한다.

---

## 9. Lorebook 구현 TODO

### 9.1 시스템 커널

| ID | Lorebook | 예상 내용 | 활성 조건 | 우선순위 |
|---|---|---|---|---|
| LB-001 | Narrative Authority Kernel | Lua 권위, 플레이어 행동 강제 금지, 시스템/극중 분리 | 항상 | MVP |
| LB-002 | Packet Protocol | PA_EVT/PA_REQ/PA_CMD 문법, 필드, 출력 위치, 오류 규칙 | 항상·짧게 | MVP |
| LB-003 | Phase Router | phase별 허용 장면과 패킷, 임의 전환 금지 | 항상 또는 phase packet | MVP |
| LB-004 | Narrative Base | 시점, 문체, 응답 호흡, 반복 억제, suspension point | 항상 | MVP |

### 9.2 세계와 리그

| ID | Lorebook | 예상 내용 | 활성 조건 | 우선순위 |
|---|---|---|---|---|
| LB-010 | Primal Apex World Core | 근미래 도시, 인간·수인, 혼성 리그, 사회적 위상 | 기본 설정 | MVP |
| LB-011 | Official Match Rules | 복싱, 8 exchange, 다운·KO의 극중 의미, 금지 행위 | PRE_MATCH/MATCH | MVP |
| LB-012 | League Institutions | 스타디움, 로컬 아레나, 매니저, 심판, 세컨드, 방송 | 관련 장면 | 2차 |
| LB-013 | Reputation Semantics | HONORABLE, RUTHLESS, TECHNICIAN 등 평판 태그의 의미 | 경기 후·대중 장면 | 2차 |
| LB-014 | City Overview | 8개 구역, 강과 교통, 시간대 | STORY | 2차 |
| LB-015~022 | District Books | 장소, 분위기, 사건, 출현 인물, 시설 | 해당 district | 2차 |

### 9.3 캐릭터

| ID | Lorebook | 예상 내용 | 활성 조건 | 우선순위 |
|---|---|---|---|---|
| LB-030 | Roster Index | ID, 이름, 성인 나이, 종족, 직업, 말투, AI 정책 | 선택·목록 | MVP |
| LB-031~039 | Fighter Public Profiles | 외형, 말투, 성격, 욕망, 복싱 스타일, 일상, 공개 관계 | 해당 인물 등장 | MVP/확장 |
| LB-040~048 | Fighter Secret Profiles | 과거, 트라우마, 감춘 동기, 공개 조건 | 관련 flag | 2차 |
| LB-049 | Han Seyeon Manager | 매니저 역할, 전 챔피언, 시력 손상, 화법, 조언 범위 | 한세연 등장 | MVP |
| LB-050 | NPC-to-NPC Relations | 루시-알리사, 도해인-차수현 등 상호 관계와 호칭 | 다인 장면 | 2차 |

### 9.4 관계와 스토리

| ID | Lorebook | 예상 내용 | 활성 조건 | 우선순위 |
|---|---|---|---|---|
| LB-060 | Relationship Model | affection/trust/respect/tension 의미, 수치 계산 금지 | STORY | MVP |
| LB-061 | Intent Taxonomy | PRAISE_SKILL, COMFORT, PROVOKE 등 의미 ID | PA_REQ intent | MVP |
| LB-062~070 | Character Relationship Overlays | 관계 조합별 말투·거리·행동 변화 | 인물+관계 태그 | 2차 |
| LB-071 | Story Mode Director | 자유 행동, 이벤트, 일정, 판정 요청 기준 | STORY | MVP |
| LB-072 | Encounter Type | Casual/Secret/Confrontation/Rescue/Mismatch | 선택된 타입 | 2차 |
| LB-073 | Scene Beat & Suspension | 한 응답 범위, 사용자 반응 지점, 장면 종결 규칙 | 이벤트 장면 | MVP |
| LB-074 | Event Knowledge Rules | 정보 범위, 비밀 누출 방지, required/forbidden facts | 이벤트 장면 | 2차 |
| LB-075 | Calendar & Matchmaking Narrative | 경기 제안, 일정, 극중 행정 표현 | 매치메이킹 | 2차 |

### 9.5 전투와 성장 내러티브

| ID | Lorebook | 예상 내용 | 활성 조건 | 우선순위 |
|---|---|---|---|---|
| LB-080 | Match Narrative Adapter | battle packet을 산문으로 변환, 결과 불변 | LLM 전투 묘사 | MVP |
| LB-081 | Combat Tag Dictionary | 타격·카운터·그로기·다운·KO 태그의 강도 | LLM 전투 묘사 | MVP |
| LB-082 | Match Compression | FULL_BEAT/ROUND_SUMMARY/HIGHLIGHT_ONLY | 묘사 모드 | 2차 |
| LB-083 | Interval Narrative | 세컨드 조언, 공개 정보, 전술 선택 | 특수 인터벌 | 2차 |
| LB-084 | Match End & Aftermath | 결정타, 관중, 대기실, 확정 부상만 묘사 | POST_MATCH | MVP |
| LB-085 | Progression Semantics | 숙련도·피로·스킬 단계의 극중 의미 | RECOVERY/TRAINING | MVP |
| LB-086 | Training Scene Director | 훈련 종류, 접근법, 결과 묘사 | TRAINING | MVP |
| LB-087 | Skill Learning Narrative | OFFERED/PRACTICING/MASTERED 단계 | 특수 훈련 | 2차 |

### 9.6 콘텐츠와 출력

| ID | Lorebook | 예상 내용 | 활성 조건 | 우선순위 |
|---|---|---|---|---|
| LB-090 | Content Mode & Boundaries | SFW/MATURE/EXPLICIT/FADE, 중단·하향, 성인 확인 | 관련 설정/장면 | MVP |
| LB-091 | Post-Match Ritual | 경기 후 의식의 세계관·비성적/성적 분기·시간 | 선택 시만 | 2차 |
| LB-092~100 | Intimacy Overlays | 캐릭터별 친밀 표현·경계·후속 태도 | 허용된 친밀 장면 | 3차 |
| LB-101 | N2L Output Grammar | 마지막 줄, 한 패킷, enum, 금지 필드 | PA_REQ 응답 | MVP |
| LB-102 | Error Recovery | 형식 오류, stale revision, 재질문, 중복 방지 | 오류 발생 | MVP |

---

## 10. Lua 엔진 구현 TODO

아래 Input/Output은 논리적 계약이다. 실제 함수는 `context` 하나를 받고 `EngineResult`를 반환하도록 통일할 수 있다.

### 10.1 제어·코어 엔진

#### ENG-001 GameController — MVP

- **역할:** 모든 사용자·버튼·LLM 입력의 진입점, 라우팅, 트랜잭션 커밋.
- **Input:** `triggerId`, source, rawInput, chatIndex, currentState.
- **Output:** handled, committed revision, renderRequired, narrativePacket, error.
- **완료 조건:** 잘못된 phase·중복 command·엔진 오류에서 상태가 부분 변경되지 않는다.

#### ENG-002 StateEngine — MVP

- **역할:** 상태 생성, 정규화, 스냅샷, mutation 적용, schema migration.
- **Input:** operation, expectedRevision, mutations 또는 storedState.
- **Output:** normalizedState, newRevision, validation errors.
- **완료 조건:** 범위 초과 수치·없는 ID·깨진 match 상태를 거부하거나 복구한다.

#### ENG-003 ProtocolEngine — MVP

- **역할:** 패킷 생성·추출·파싱·검증·중복 방지.
- **Input:** raw LLM text 또는 packet data, pending request.
- **Output:** validated packet, narrative text, packet key, protocol error.
- **완료 조건:** 리롤·재생성으로 동일 `req`가 다시 실행되지 않는다.

#### ENG-004 FlowEngine — MVP

- **역할:** phase 상태 머신과 Lua/LLM/UI 진행권 관리.
- **Input:** currentPhase, event/command, campaign state.
- **Output:** nextPhase, owner, entry actions, rejection reason.
- **완료 조건:** 경기 중 스토리 이벤트, 경기 확정 후 로드아웃 변경 등 불법 전환을 차단한다.

#### ENG-005 RNGEngine — MVP

- **역할:** battle/policy/training/story/matchmaking 난수 스트림.
- **Input:** stream, range 또는 weighted candidates, count.
- **Output:** values, new stream state, draw index.
- **완료 조건:** 동일 시드·명령열 재현 및 스트림 독립성.

#### ENG-006 EventLogEngine — MVP

- **역할:** command, RNG, mutation, phase, 전투·관계 사건의 구조화 로그.
- **Input:** event, revision before/after, source command.
- **Output:** append-only log entry와 요약 조회.
- **완료 조건:** 버그 재현에 필요한 입력과 결과를 추적할 수 있다.

### 10.2 전투 엔진

#### ENG-010 MatchEngine — MVP

- **역할:** 경기 생성, 참가자·로드아웃 잠금, 라운드 운영, 종료 확정.
- **Input:** scheduled match, fighter definitions, loadouts, ruleset, seed.
- **Output:** MatchState, phase events, final MatchResult.
- **완료 조건:** 현재 1 대 1 코어와 캠페인 상태가 안정적으로 연결된다.

#### ENG-011 BattleEngine — 구현 기반 존재/MVP 확장

- **역할:** 27+3 결과표, d6, HP/STA/BRK, 그로기, 다운, 기상, KO, 인터벌.
- **Input:** MatchState, 양측 action, resolved skill modifiers, battle RNG.
- **Output:** exchange event, dice, deltas, transitions, tags, updated MatchState.
- **완료 조건:** 기존 자동 테스트와 신규 스킬·상태 테스트 통과.

#### ENG-012 SkillEngine — MVP

- **역할:** 액티브·패시브, 비용, 쿨다운, 주사위 조작, 결과 증폭.
- **Input:** actor/target, selected action/skill, timing, match context.
- **Output:** usable, costs, ordered effects, skill tags, errors.
- **완료 조건:** 최소 액티브 8~12종, 패시브 6~8종 데이터화.

#### ENG-013 StatusEffectEngine — MVP

- **역할:** 상태 부여, 면역, 중첩, tick, 해제, 예약 효과.
- **Input:** effect ID, source/target, duration, timing, character state.
- **Output:** applied/expired statuses, modifiers, forced actions.
- **완료 조건:** 지속시간과 발동 시점이 룰북 처리 순서와 일치한다.

#### ENG-014 FighterAIEngine — MVP

- **역할:** NPC 기본 행동과 스킬의 블라인드 선택.
- **Input:** policy ID, self state, opponent public state/history, usable skills, policy RNG.
- **Output:** action, skill ID, internal decision tags.
- **완료 조건:** 난이도 재보정, `reckless_raider`·`regret_duelist` 문제 수정.

#### ENG-015 ScoutEngine — 2차

- **역할:** 상대 행동 기록 분석과 관찰 정보 해금.
- **Input:** target, known exchanges, prior matches, scout skill.
- **Output:** analysis level, unlocked facts, 확률 범위.
- **완료 조건:** 내부 정확한 AI 가중치를 그대로 노출하지 않는다.

#### ENG-016 MatchSummaryEngine — 2차

- **역할:** 긴 전투 로그를 캠페인·LLM용 의미 태그로 압축.
- **Input:** MatchResult, event log.
- **Output:** facts, highlights, style assessment, opening/turning point/finish.
- **완료 조건:** 경기 후 반응·업적·평판이 동일 요약을 공유한다.

### 10.3 캠페인 엔진

#### ENG-020 CalendarEngine — MVP

- **역할:** 시간 경과, 일정, 경기일, 이벤트 만기.
- **Input:** current datetime, duration, reason 또는 schedule request.
- **Output:** new datetime, due events, warnings, conflicts.
- **완료 조건:** 스토리 중 경기일 도달과 일정 충돌을 처리한다.

#### ENG-021 RecoveryEngine — 2차

- **역할:** 피로, 경기 후 부상, 치료, 휴식, 출전 제한.
- **Input:** match summary, fighter state, rest/treatment choice, recovery RNG.
- **Output:** fatigue change, injuries, recovery days, restrictions, narrative tags.
- **완료 조건:** 전투 HP와 영구 부상을 직접 동일시하지 않는다.

#### ENG-022 TrainingEngine — MVP

- **역할:** 훈련 비용·시간·피로·성과·위험·파트너 이벤트.
- **Input:** training ID, approach, partner, player state, location, RNG.
- **Output:** result tier, costs, mastery gains, skill progress, context event.
- **완료 조건:** 일반 훈련과 서사형 특수 훈련을 모두 지원한다.

#### ENG-023 ProgressionEngine — MVP

- **역할:** 경험, 숙련도, 영구 성장, 스킬 해금·장착.
- **Input:** match/training result, requirements, player progression.
- **Output:** gains, available/unlocked skills, derived stats, loadout errors.
- **완료 조건:** 수치 인플레이션보다 선택지 확장 중심의 성장.

#### ENG-024 RelationshipEngine — MVP

- **역할:** LLM intent를 캐릭터별 관계 변화와 상태 전이로 판정.
- **Input:** scene context, intent/tone/target, preferences, current relationship.
- **Output:** relationship mutations, status, flags, unlocked events, visibleReaction.
- **완료 조건:** 장면당 변화 상한, 반복 행동 수확 체감, 다축 관계 반영.

#### ENG-025 StoryEventEngine — MVP

- **역할:** 조건에 맞는 이벤트 선정, sceneSpec과 beat 진행.
- **Input:** phase, 시간, 장소, 관계, flags, recent events, story RNG.
- **Output:** selected event, required/optional beats, forbidden facts, choices.
- **완료 조건:** 비밀 누출·이벤트 반복·동시 장면 충돌을 방지한다.

#### ENG-026 MemoryEngine — 2차

- **역할:** 중요 사건, 인물별 기억, 미해결 갈등의 구조화 저장과 압축.
- **Input:** canonical event 또는 scene context query.
- **Output:** recent facts, relationship facts, unresolved threads, forbidden assumptions.
- **완료 조건:** 장문의 고정 lorebook 요약을 대체한다.

### 10.4 리그와 메타 엔진

#### ENG-030 MatchmakingEngine — 2차

- **역할:** 상대·경기 종류·날짜·장소 선정.
- **Input:** 요청 상대, 랭킹, 일정, 부상, 관계, 최근 경기, story flags.
- **Output:** opponent, match type, venue, date, selection reasons.

#### ENG-031 RankingEngine — 3차

- **역할:** 랭킹과 챔피언전 자격.
- **Input:** match result, 양측 rank, match type.
- **Output:** rank changes, titles, qualification flags.

#### ENG-032 EconomyEngine — 3차

- **역할:** 경기 수당, 훈련·치료 비용, 보상.
- **Input:** match/training/treatment event, sponsor/reputation flags.
- **Output:** gross, bonus, expense, net mutations.

#### ENG-033 ReputationEngine — 2차

- **역할:** 경기 방식과 공개 선택에 따른 대중 이미지.
- **Input:** match summary, public post-match choice, current reputation.
- **Output:** reputation changes, tags, crowd/sponsor reactions.

#### ENG-034 AchievementEngine — 2차

- **역할:** 전투·관계·발견 업적 판정.
- **Input:** trigger event, campaign state, unlocked achievements.
- **Output:** newly unlocked achievements와 확정 보상.

#### ENG-035 ContentGateEngine — MVP 기본/2차 확장

- **역할:** SFW/성인 모드, 성인 확인, 사용자 경계, 장면 접근성.
- **Input:** requested transition, participants, settings, relationship, scene state.
- **Output:** allowed, resolved mode, allowed/blocked tags, exit options.

### 10.5 프레젠테이션 엔진

#### ENG-040 NarrativeBridge — MVP

- **역할:** 엔진 결과를 LLM에 필요한 사실·태그·금지 주장으로 축약.
- **Input:** event type, engine results, scene, narrative preferences.
- **Output:** PA_EVT/PA_REQ, visible facts, required beats, forbidden claims, reply policy.
- **완료 조건:** 내부 수치·비밀·AI 정책이 불필요하게 노출되지 않는다.

#### ENG-041 UIEngine — MVP

- **역할:** phase별 패널과 허용 버튼 렌더링.
- **Input:** campaign/match/presentation state, available commands.
- **Output:** HTML, button codes, disabled reasons.
- **완료 조건:** 버튼 조작 입력도 GameController가 재검증한다.

#### ENG-042 AssetEngine — 2차

- **역할:** 인물·상태·행동·결과에 맞는 에셋 경로 결정.
- **Input:** character ID, phase, condition, presentation event.
- **Output:** main/action/reaction/fallback asset IDs.
- **완료 조건:** LLM이 이미지 파일명을 조합하지 않는다.

---

## 11. 개발 단계별 TODO 체크리스트

### Stage 0 — 계약 고정

- [ ] `CampaignState` 스키마 확정
- [ ] phase와 허용 command 표 확정
- [ ] PA 패킷 v1 문법 확정
- [ ] 엔진 공통 `EngineResult` 계약 확정
- [ ] fighter/skill/status/event 내부 ID 규칙 확정
- [ ] 구버전 카드에서 재사용할 캐릭터·세계관 데이터 정제

### Stage 1 — 전투 MVP

- [ ] 기존 BattleSim을 MatchEngine 아래로 분리
- [ ] GameController, State, Flow, Protocol, RNG 구현
- [ ] `/Match Start` 직접 처리
- [ ] 전투 버튼과 UI 연결
- [ ] NPC 난이도 재보정
- [ ] 전투 결과 구조화 로그
- [ ] Match End 패킷 생성
- [ ] 기존 22개 테스트 이관 및 확장

### Stage 2 — 스킬과 상태

- [ ] 액티브·패시브 데이터 스키마
- [ ] SkillEngine 처리 순서
- [ ] StatusEffectEngine
- [ ] 주사위 범위 충돌 우선순위
- [ ] 쿨다운·사용 제한·비용 UI
- [ ] 스킬 밸런스 자동 시뮬레이션

### Stage 3 — 최소 캠페인

- [ ] Calendar, Training, Progression, Relationship 구현
- [ ] StoryEvent의 정적 이벤트 10~15개
- [ ] 테스트 선수 3명 + 한세연 Lorebook
- [ ] 경기→회복→훈련→스토리→다음 경기 루프
- [ ] 자연어 intent 패킷 처리
- [ ] revision·req 중복 방지 테스트

### Stage 4 — 캐릭터 콘텐츠

- [ ] 선수 9명 Public Profile 정리
- [ ] 선수별 관계 overlay
- [ ] Secret Profile과 공개 조건
- [ ] 캐릭터 유래 훈련·스킬
- [ ] NPC-to-NPC 관계
- [ ] 경기 방식별 후속 반응
- [ ] MemoryEngine 도입

### Stage 5 — 리그와 장기 진행

- [ ] Matchmaking, Ranking, Reputation, Achievement
- [ ] 장소·일정·재대결
- [ ] 시즌 이벤트와 챔피언전
- [ ] 경제는 필요 범위만 도입
- [ ] 장기 세이브 마이그레이션 테스트

### Stage 6 — 콘텐츠 모드와 폴리싱

- [ ] ContentGate 기본 설정
- [ ] SFW/MATURE/EXPLICIT/FADE 분기
- [ ] Post-Match Ritual 조건부 Lorebook
- [ ] 에셋 레지스트리와 fallback
- [ ] 모델별 패킷 준수율 테스트
- [ ] 모바일·데스크톱 UI 검수
- [ ] charx 빌드와 배포 문서

---

## 12. 테스트와 승인 기준

### 12.1 엔진 테스트

- 동일 시드 재현
- 자원 동시 반영
- 스킬·상태 처리 순서
- 다운·기상·인터벌·더블 다운
- 불법 phase 명령 거부
- stale revision 거부
- 동일 request 중복 실행 방지
- 관계 변화 범위와 상태 전이
- 일정 충돌과 경기일 강제 전환

### 12.2 LLM 계약 테스트

- `reply=NO_PACKET`에서 패킷을 출력하지 않음
- `reply=REQUIRED`에서 지정 타입 한 개 출력
- 허용되지 않은 필드·선택 ID를 만들지 않음
- Lua 결과를 뒤집지 않음
- 플레이어 행동·감정을 강제하지 않음
- 비밀 flag 전 정보 누출 없음
- 패킷이 내러티브 본문에 노출되지 않음

### 12.3 통합 플레이테스트

- 경기 한 사이클을 새 채팅에서 완료
- LLM 없이 전투 전체 진행 가능
- 자연어로 경기 시작·훈련·관계 intent 처리 가능
- 리롤 후 보상·관계가 중복 적용되지 않음
- 장기 대화에서도 현재 상대·날짜·관계가 유지됨
- SFW 설정에서 성인 장면용 Lorebook과 출력이 활성화되지 않음

---

## 13. 주요 위험과 대응

| 위험 | 영향 | 대응 |
|---|---|---|
| LLM 패킷 누락·오타 | 진행 정지 | strict parser, 복구 UI, 버튼 fallback |
| 리롤·재생성 | 중복 보상·관계 | req/rev/consumed ledger |
| 항상 활성 Lorebook 과다 | 비용·지시 충돌 | phase·character·flag 조건 활성화 |
| LLM의 수치 창작 | 상태 불일치 | Narrative Authority + Lua UI 권위 |
| 장기 요약 비대화 | 맥락 손실·토큰 증가 | MemoryEngine의 canonical fact 압축 |
| NPC 난이도와 서사 위상 불일치 | 몰입 저하 | 정책 매트릭스와 캐릭터 배정 분리 검증 |
| 자유 입력의 과도한 기계화 | 롤플레이 경직 | 기계적 변화가 있을 때만 N2L 패킷 |
| 성인 장면의 강제 활성화 | 사용자 통제 상실 | ContentGate, opt-in, fade/stop 경로 |

---

## 14. MVP 완료 정의

MVP는 다음 조건을 모두 만족할 때 완료로 본다.

1. 구버전에서 정제한 선수 3명과 한세연이 일관된 말투와 성격을 유지한다.
2. `/Match Start` 또는 버튼으로 LLM 없이 1 대 1 경기를 완주할 수 있다.
3. 공격·방어·회피, HP/STA/BRK, 그로기, 다운, KO, 인터벌이 재현 가능하다.
4. 액티브 8종 이상과 패시브 6종 이상이 데이터 기반으로 동작한다.
5. 경기 결과가 MatchSummary를 거쳐 LLM의 경기 후 장면에 정확히 반영된다.
6. 훈련 하나와 캐릭터 이벤트 하나를 거쳐 숙련도 또는 스킬 진도가 증가한다.
7. 자유 대화에서 관계 intent 하나를 추출하고 Lua가 관계 변화를 확정한다.
8. 경기→회복→훈련→스토리→다음 경기 루프가 한 채팅에서 반복된다.
9. 리롤·오류 패킷·중복 버튼이 상태를 두 번 변경하지 않는다.
10. Lorebook은 현재 phase와 등장인물에 필요한 항목만 활성화된다.

---

## 15. 결론

Primal Apex의 핵심 구현 과제는 전투 코드를 만드는 것만이 아니라, **Lua의 결정론적 게임 상태와 LLM의 자유로운 캐릭터 서사를 안정적으로 왕복시키는 계약**을 만드는 것이다. 정확한 명령과 버튼은 Lua가 직접 처리하고, 자연어에서 기계적 의미가 필요한 순간만 LLM 패킷을 사용한다. Lua 판정 결과는 NarrativeBridge를 통해 필요한 사실만 LLM에 전달한다.

이 구조가 정착되면 전투·성장·관계·스토리가 서로 분리된 미니게임이 아니라 하나의 순환으로 연결된다. 관계에서 얻은 정보와 기술이 경기에 영향을 주고, 경기의 승패와 방식이 다시 캐릭터의 태도·평판·후속 이벤트를 바꾸는 것이 최종 제품의 중심 경험이다.
