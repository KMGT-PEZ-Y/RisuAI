# Battle Simulator POC

## NG+ AI · M/U/H 30종 테스트베드 (2026-09-04)

`play_muh_skills.cmd`를 실행하면 M/U/H 각 10종을 양측 최대 5개씩 장착하고 시험할 수 있습니다.
`play_ng_plus.cmd`로도 같은 화면을 열 수 있습니다. Enemy AI에서 NG+를 선택하고 원하는 스킬 0~5개와 판단 충실도(0~1)를 지정한 뒤 새 경기를 시작합니다. NG+는 행동과 스킬을 함께 3턴 탐색하며 `NG+ 판단` 탭에 점수와 예상 연계를 표시합니다.
기존 AI의 수동 입력/무작위 스킬/무스킬 모드도 유지합니다. 계산량과 검증 결과는 [NG_PLUS_AI.md](NG_PLUS_AI.md)를 참조하세요.
30종 표, 연계·제어 제한, 판정 기준과 사용법은 [MUH_ACTIVE_SKILLS.md](MUH_ACTIVE_SKILLS.md)를 참조하세요.

`ROUND_TURN_BATTLE_POC_RULEBOOK.md`와 `BASIC_RESULT_TABLE_DRAFT_V0.1.md`를 실행 가능한 형태로 옮긴 표준 라이브러리 기반 Python 테스트베드다. 현재 무스킬 1 대 1 코어 전투, 독립 행동 정책, 전략 매트릭스, 난이도별 NPC 12종 실험과 액티브 스킬 상태·예약 효과 실행기까지 구현되어 있다. 외부 패키지는 필요하지 않는다.

현재 진행상황, 최신 실험 결과, 알려진 문제와 다음 작업 순서는 `BATTLE_SIM_POC_PROGRESS.md`를 기준으로 한다.

## 현재 상태

- M/U/H 액티브 스킬 30종, 양측 5슬롯 테스트 UI, 준비/할인/제어/후딜 및 NG+ 공용 탐색 AI 구현. 전체 테스트 149개 통과.

- 완료: 27+3 결과표, 1 대 1 무스킬 엔진, 라운드·그로기·다운·KO, 시드 재현, 전략 프레임워크
- 완료: 표준 Player 정책 8종 × NPC 정책 12종의 96개 케이스 실험
- 완료: Tkinter 기반 수동 플레이테스트 UI
- 검증: 기존 Phase A-D 등 86개 + 쉬움 적 스킬·선택기·랜덤 비교 20개, 자동 테스트 총 106개 통과
- 완료: 현재 무스킬 1 대 1 기준선의 RisuAI Lua 모듈 및 CHARX 이식
- 미구현: 패시브 적용 방식, 적별 난이도 보정·스킬 상위 레벨, 면역·다중 중첩 등 확장 상태이상, 다인 교대 및 확장 규칙의 Lua 동기화
- 완료: 강화와 다중 스킬을 지원하는 액티브 스킬 스키마 확정
- 완료: Python Phase A 데이터 모델·검증기, Phase B 캐릭터 스킬 상태·`TurnIntent`, Phase C timing·priority·여섯 즉시 효과 카테고리, Phase D 상태·예약 효과
- 완료: Player만 스킬을 장착·사용하고 무스킬 Enemy와 대전하는 Phase C-D 통합 UI 테스트베드
- 완료: 쉬움 적 3종의 예정형 스킬 선택, 공유 스킬 5종, 동일 장착 랜덤 Player와 적별 1,000경기 비교, 수동 플레이 UI
- 다음 작업: 쉬움 적 패턴 및 NG+ 컨셉 덱의 실제 플레이·난이도·스킬 효용 검증, 수치 조정

확정 스키마, 효과 카테고리, 적용 방식, 조건식과 단계별 구현 TODO는 `ACTIVE_SKILL_SCHEMA.md`를 기준으로 한다.

2026-09-03: 스킬 자동 선택 AI와 관련 설정·전용 테스트·설계 문서를 롤백했다.
이후 쉬움 적 3종과 랜덤 Player에 한정하여 새 선택기를 구현했다. 기본 설정은 여전히 자동 시전 없음이며, 새 테스트베드에서 명시적으로 선택기를 활성화한다.
Phase A-D 실행기와 Player 수동 스킬 테스트베드는 유지한다.
`phase_e_skill_sets.py`의 3레벨 예제 스킬 3종과 성장 비교용 장착 데이터는 선택 알고리즘과 독립적인 데이터로만 보존했다.

## 실행

### 쉬움 적 스킬 플레이테스트

`play_easy_enemies.cmd`를 더블클릭한다. Enemy 3종을 선택하고 Player도 새 스킬 5종 중 최대 3개를 장착할 수 있다. `적과 같은 장착으로 새 경기` 버튼으로 동일 장착 비교가 가능하다.

```powershell
.\projects\battle-sim-poc\play_easy_enemies.cmd
```

합의한 수치·조건·일정·난수·실패 처리는 `EASY_ENEMY_SKILLS.md`, 적별 1,000경기 결과는 `EASY_ENEMY_PLAYTEST_RESULTS.md`에 기록한다. 랜덤 Player는 적과 같은 세 스킬을 1레벨로 장착하며, 행동을 고른 뒤 사용 가능한 스킬과 미사용 중 균등 선택한다.

재실행:

```powershell
& "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -X utf8 .\projects\battle-sim-poc\run_easy_enemy_simulation.py --matches 1000 --seed 20260903 --json projects/battle-sim-poc/results/easy_enemies_1000.json --report projects/battle-sim-poc/EASY_ENEMY_PLAYTEST_RESULTS.md
```

### 플레이테스트 UI

탐색기에서 `projects\battle-sim-poc\play_ui.cmd`를 더블클릭하거나 저장소 루트에서 실행한다.

```powershell
.\projects\battle-sim-poc\play_ui.cmd
```

NPC 12종과 난수 시드를 선택한 뒤 공격·방어·회피 버튼으로 직접 플레이할 수 있다. UI는 양측 HP/스태미너/브레이크, 다운·그로기, 라운드와 결과표 로그를 표시한다. 다운 대기나 플레이어 그로기처럼 선택할 수 없는 턴은 다음 선택 시점까지 자동 진행한다.

### Phase C-D 스킬 테스트베드 UI

탐색기에서 `projects\battle-sim-poc\play_skill_testbed.cmd`를 더블클릭하거나 저장소 루트에서 실행한다.

```powershell
.\projects\battle-sim-poc\play_skill_testbed.cmd
```

Player는 Phase C 즉시 효과 8종과 Phase D 상태·예약 효과 6종, 총 14종 중 최대 4개를 경기 시작 전에 장착하고 매 턴 기본 행동과 사용할 스킬을 함께 선택한다. Enemy는 선택한 기존 행동 AI만 사용하며 스킬 로드아웃은 항상 비어 있다. UI는 스킬 사용 가능 여부, 현재 비용, 쿨다운, 남은 횟수, 양측 상태·예약 효과, 원본·최종 주사위와 timing·priority·조건 실패·효과 적용 전후 값을 표시한다.

`상태 제어 시험용 초기 상태 추가`는 정화와 지속시간 변경을 바로 확인할 수 있도록 Player에게 제거 가능한 negative 상태 두 개를 배치한다. Phase D 상태 스킬은 별도로 실제 payload를 저장하고 다음 자기 턴부터 발동한다.

경기 설정의 `기본 결과표 보기` 버튼은 공격/방어/회피 27개 기본 결과표와 그로기 전용 3개 결과를 팝업으로 표시한다. 각 행은 판정 ID, 행동 조합, 주사위 결과, 양측 HP/STA/BRK 변화와 한국어 개요를 보여 준다.

Phase D 예제는 `셰이킹 페인트`, `오픈 가드`, `포커스드 가드`, `네거티브 퍼지`, `스토어드 모멘텀`, `리커버리 에코`다. 목록에서 `[Phase C]`와 `[Phase D]`로 구분하며 기본 장착은 Phase D의 상태 2종과 예약 2종이다.

### 시뮬레이션 CLI

PowerShell에서 저장소 루트를 기준으로 실행한다.

```powershell
.\projects\battle-sim-poc\run.cmd --matches 100000 --seed 20260825
```

`run.cmd`는 PowerShell 스크립트 실행 정책의 영향을 받지 않는다. Codex 작업공간에 포함된 실제 Python을 우선 사용하며, 해당 환경이 없을 때만 시스템 Python을 찾는다. 이 순서는 Windows의 Microsoft Store용 `python` 앱 실행 별칭이 잘못 선택되는 문제를 방지한다.

집계 결과를 JSON으로 함께 저장하려면:

```powershell
.\projects\battle-sim-poc\run.cmd --matches 100000 --seed 20260825 --json projects/battle-sim-poc/results/baseline.json
```

특정 시드의 단일 경기를 턴별로 확인하려면:

```powershell
.\projects\battle-sim-poc\run.cmd --trace-seed 12345
```

상세 기록은 단순 상태 덤프가 아니라 각 턴의 행동과 주사위, 판정 컨셉, 자원 증감, 완전 그로기, 다운·기상 및 인터벌을 한국어 문장으로 해설한다.

서로 다른 행동 전략을 대전시키려면:

```powershell
.\projects\battle-sim-poc\run.cmd --matches 10000 --player-strategy pressure --enemy-strategy adaptive
```

여러 전략의 모든 순서쌍을 한 번에 비교하려면:

```powershell
.\projects\battle-sim-poc\run.cmd --matrix --matches 5000 --strategies random,attack,evade,cycle,defensive,pressure,adaptive,guard_evade_ratio,guard_attack_ratio,guard_mixed_ratio,guard_evade_adaptive,guard_attack_adaptive,guard_mixed_adaptive --json projects/battle-sim-poc/results/strategy_matrix.json
```

표준 플레이어 정책 8개와 난이도별 NPC 정책 12개의 96개 대전을 실행하려면:

```powershell
.\projects\battle-sim-poc\run.cmd --npc-roster --matches 2000 --seed 20260831 --json projects/battle-sim-poc/results/npc_roster_8x12.json
```

NPC 로스터는 쉬움·보통·어려움·매우 어려움마다 3개 정책을 포함한다. 각 케이스는 승패율, 평균·중앙값·P95 턴, 평균 라운드, 5라운드 이내 종료율과 10라운드 초과율을 기록한다.

- 쉬움: `rookie_cycle`, `rookie_guard`, `reckless_raider`
- 보통: `balanced_soldier`, `veteran_guard`, `cautious_hunter`
- 어려움: `pressure`, `adaptive`, `tactical_evaluator`
- 매우 어려움: `weighted_analyst`, `regret_duelist`, `executor`

지원 전략은 다음과 같다.

- `random`: 공격·방어·회피 균등 무작위
- `attack`, `evade`: 하나의 행동을 고정 반복
- `cycle`: 공격→방어→회피 순환
- `defensive`: 자신의 HP·브레이크 위험을 우선하는 상태 대응
- `pressure`: 상대의 낮은 HP·높은 브레이크를 공격적으로 마무리
- `adaptive`: 상대의 최근 6개 공개 행동 중 최빈 행동의 상성을 선택
- `guard_evade_ratio`: 방어 55%·회피 45% 비율형
- `guard_attack_ratio`: 방어 55%·공격 45% 비율형
- `guard_mixed_ratio`: 방어 45%·공격 30%·회피 25% 비율형
- `guard_evade_adaptive`: 방어·회피 풀 안에서 자기 위험과 상대 최근 행동에 적응
- `guard_attack_adaptive`: 방어·공격 풀 안에서 자기 위험과 상대 최근 행동에 적응
- `guard_mixed_adaptive`: 방어 우선 가중치를 유지하며 세 행동 모두로 적응

교착 검증용이었던 `defend` 고정 전략은 지원 전략에서 제외했다. 방어형 캐릭터도 반드시 공격 또는 회피 행동을 함께 보유한다.

전략은 상대가 같은 턴에 고른 행동을 볼 수 없고 과거 공개 정보만 사용한다. 정책용 난수와 전투 주사위 난수를 분리하여 전략 내부의 무작위 호출 횟수가 전투 주사위열을 바꾸지 않도록 했다.

자동 테스트:

```powershell
python -m unittest discover -s projects/battle-sim-poc -p "test_*.py" -v
```

## 포함된 규칙

- 기준 능력치 100/100/100, 최대 다운 3회, d6
- 공격·방어·회피와 양측 독립 행동 정책
- 27개 기본 결과표와 그로기 전용 3개 결과표
- 자원 변화 동시 적용
- 브레이크 최대 도달 시 완전 그로기
- 다운 횟수만큼 턴 스킵 후 HP 50% 기상
- 대기 캐릭터의 턴당 최대 HP 4% 회복
- 8턴 인터벌의 HP 33%, 스태미너 50%, 브레이크 절반
- 라운드 말 기상과 인터벌 회복 중첩
- 100라운드 자동 시뮬레이션 안전 한도
- 난수 시드 기반 완전 재현
- 양측 독립 전략 주입 및 전략 대전 매트릭스

## 주요 출력

- Player/Enemy 승률, 더블 KO 및 교착 비율
- 경기 턴 평균·중앙값·백분위
- 약 5라운드(40턴) 이내 및 10라운드(80턴) 초과 경기 비율
- 경기 라운드 평균·중앙값·95백분위
- 경기당 다운·그로기·대기 턴 평균
- 행동 선택 횟수
- 27개 기본 결과 및 그로기 전용 결과의 사용 횟수

무스킬 기준선, C-D 효과 시험, 쉬움 적 스킬 시험은 별도 진입점으로 유지한다. 구현 상태와 인수인계 정보는 `BATTLE_SIM_POC_PROGRESS.md`에 유지한다.

## RisuAI Lua 이식본

현재 무스킬 1 대 1 기준선은 `projects/battle-sim-lua`에 이식되어 있다. `BattleSim-RisuAI.charx`를 RisuAI에서 import할 수 있으며, Lua 구현 범위와 재빌드 방법은 해당 디렉터리의 `README.md`를 참조한다. 향후 스킬·상태이상·다인전 규칙은 Python 기준 구현에서 먼저 검증한 뒤 Lua 버전에 동기화한다.

`results/`의 JSON은 재생성 가능한 로컬 실험 산출물이므로 Git에서 제외된다. 공유 기준선은 실행 시드·반복 횟수와 요약 수치를 `BATTLE_SIM_POC_PROGRESS.md`에 기록한다.
