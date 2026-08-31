# Battle Simulator POC 진행상황 및 인수인계

- 최종 갱신일: 2026-08-29
- 현재 단계: 무스킬 1 대 1 코어 엔진·전략 프레임워크·NPC 정책 실험 완료
- 다음 우선순위: NPC 난이도 재보정 후 액티브 스킬 데이터 모델 설계
- 실행 환경: Python 표준 라이브러리, 외부 패키지 없음

이 문서는 새 채팅이나 새 작업자가 현재 상태에서 바로 작업을 이어가기 위한 기준 문서다. 세부 전투 규칙은 `ROUND_TURN_BATTLE_POC_RULEBOOK.md`, 확정된 27+3 결과 수치는 `BASIC_RESULT_TABLE_DRAFT_V0.1.md`를 참조한다.

## 1. 현재 완료된 범위

### 1.1 전투 코어

- 기준 능력치 HP/STA/BRK 100, 최대 다운 3회, d6
- 공격·방어·회피와 27개 기본 결과표
- 그로기 대상 전용 G01/G02/G03 결과표
- 양측 자원 변화 동시 반영
- 브레이크 100 도달 시 완전 그로기
- 1·2번째 다운 후 다운 횟수만큼 턴 스킵
- 3번째 다운 시 KO
- 다운 대기 중 서 있는 캐릭터의 최대 HP 4% 회복
- 8턴 라운드와 라운드 인터벌
- 인터벌 HP 33%, STA 50%, 현재 BRK 절반 회복
- 라운드 말 기상과 인터벌 회복 중첩
- 더블 다운·더블 KO·승패 처리
- 100라운드 안전 한도와 `STALEMATE`
- 동일 시드 재현
- 구조화된 트레이스와 한국어 턴 해설

### 1.2 전략 프레임워크

- Player/Enemy에 서로 다른 전략을 독립 주입
- 같은 턴 상대 선택을 볼 수 없는 블라인드 선택
- 정책 난수와 전투 주사위 난수 분리
- 과거 공개 행동 기록과 공개 주사위 교환 기록 저장
- 단일 전략 대전, 정사각 전략 매트릭스, 직사각 전략 그리드 지원
- 평균·중앙값·P25/P75/P90/P95 턴
- 평균·중앙값·P95 라운드
- 5라운드 이내 종료율과 10라운드 초과율
- 승패·더블 KO·교착, 다운·그로기·대기 턴 집계

### 1.3 결과표 밸런스 변경

초기 결과표에서 회피 고정 전략은 랜덤 CPU에게 약 80% 승률을 냈다. 회피가 방어에 상성과 주사위 모두 패배해도 아무 손실이 없던 것이 주원인이었다.

현재 표에서는 16번과 24번을 다음과 같이 변경했다.

```text
방어 vs 회피 / 방어 Win
방어자: (+10,+18,-16)
회피자: (-12,0,+10)
```

대칭 행도 동일하게 적용한다. 이 변경 후 회피 고정의 랜덤 상대 승률은 약 80%에서 약 66% 수준으로 낮아졌다. 27+3 전체 수치는 결과표 문서와 `battle_sim.py`의 `RESULT_TABLE`, `GROGGY_TABLE`이 기준이다.

### 1.4 수동 플레이테스트 UI

- Tkinter 표준 라이브러리 UI
- NPC 12종과 난수 시드 선택
- 플레이어 공격·방어·회피 직접 입력
- 양측 HP/STA/BRK 진행 바
- 다운 횟수, 다운 대기, 완전 그로기, KO 표시
- 라운드·전체 턴·결과표 ID·주사위·자원 변화 로그
- 플레이어 다운/그로기와 상대 다운 대기 턴 자동 진행
- CPU는 시뮬레이션과 동일한 블라인드 정책 사용

## 2. 주요 파일

| 파일 | 역할 |
|---|---|
| `battle_sim.py` | 결과표, 상태 모델, 전투 엔진, 전략 정책, 집계 함수 |
| `run_simulation.py` | CLI, 단일 배치·매트릭스·NPC 로스터 실행 |
| `playtest_ui.py` | Tkinter 수동 플레이테스트 UI |
| `play_ui.cmd` | Windows UI 실행 스크립트 |
| `test_battle_sim.py` | 자동 테스트 22개 |
| `README.md` | 빠른 실행법과 지원 기능 |
| `ROUND_TURN_BATTLE_POC_RULEBOOK.md` | 전체 목표 규칙과 미구현 확장 명세 |
| `BASIC_RESULT_TABLE_DRAFT_V0.1.md` | 현재 27+3 수치와 설계 의도 |
| `results/baseline.json` | 최신 랜덤 대 랜덤 100,000경기 기준선 |
| `results/guard_strategy_matrix.json` | 방어 혼합 전략 실험 결과 |
| `results/npc_roster_8x12.json` | 플레이어 8종 × NPC 12종 실험 결과 |

`results/`는 `.gitignore` 대상이므로 결과를 보존·공유해야 한다면 별도 확인이 필요하다.

## 3. 실행 명령

저장소 루트 `C:\Users\xor09\Desktop\RisuAI` 기준:

```powershell
# 수동 플레이테스트 UI
.\projects\battle-sim-poc\play_ui.cmd

# 랜덤 대 랜덤 기준선
.\projects\battle-sim-poc\run.cmd --matches 100000 --seed 20260825 --json projects/battle-sim-poc/results/baseline.json

# 특정 전략 대전
.\projects\battle-sim-poc\run.cmd --matches 10000 --player-strategy pressure --enemy-strategy adaptive

# 선택한 전략의 모든 순서쌍
.\projects\battle-sim-poc\run.cmd --matrix --matches 3000 --strategies random,attack,evade,cycle,pressure,adaptive

# 표준 플레이어 8종 × NPC 12종
.\projects\battle-sim-poc\run.cmd --npc-roster --matches 2000 --seed 20260831 --json projects/battle-sim-poc/results/npc_roster_8x12.json

# 단일 경기 해설
.\projects\battle-sim-poc\run.cmd --trace-seed 12345 --player-strategy pressure --enemy-strategy adaptive

# 자동 테스트
& "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest discover -s .\projects\battle-sim-poc -p "test_*.py" -v
```

## 4. 최신 랜덤 기준선

`seed=20260825`, 100,000경기, 현재 결과표와 정책/주사위 난수 분리 구조 기준:

| 지표 | 결과 |
|---|---:|
| Player 승률 | 49.419% |
| Enemy 승률 | 50.032% |
| 더블 KO | 0.549% |
| 평균 턴 | 34.4389 |
| 중앙값 턴 | 32 |
| P95 턴 | 54 |
| 평균 라운드 | 4.6249 |
| 중앙 라운드 | 4 |
| P95 라운드 | 7 |
| 5라운드 이내 종료 | 75.791% |
| 10라운드 초과 | 0.067% |

밸런스 목표는 평균을 정확히 40턴에 맞추는 것이 아니라 경기가 대체로 5라운드 전후에 종료되는 것이다. 랜덤 기준선은 이 느슨한 목표에 들어온다.

## 5. 현재 지원 전략

### 5.1 공용·검증 전략

| ID | 개요 |
|---|---|
| `random` | 세 행동 균등 무작위 |
| `attack` | 공격 고정 |
| `evade` | 회피 고정 |
| `cycle` | 공격→방어→회피 순환 |
| `defensive` | 자기 HP·브레이크 위험 대응 |
| `pressure` | 상대 저HP·고BRK 마무리 |
| `adaptive` | 최근 6개 상대 행동의 최빈 행동 카운터 |
| `guard_mixed_adaptive` | 방어 우선 세 행동 적응형 |

`defend` 고정은 100% 교착을 만들 수 있어 지원 목록에서 제거했다. 방어형 NPC도 반드시 공격 또는 회피 수단을 가진다.

### 5.2 방어형 실험 전략

- 비율형: `guard_evade_ratio`, `guard_attack_ratio`, `guard_mixed_ratio`
- 적응형: `guard_evade_adaptive`, `guard_attack_adaptive`, `guard_mixed_adaptive`

현재 가장 안정적인 일반 방어형은 `guard_mixed_adaptive`다. 실제 자가대전 행동 비율은 대략 공격 29%, 방어 40.5%, 회피 30.5%였고 자가대전 평균은 약 5.4라운드였다.

## 6. NPC 12종 로스터

표준 플레이어 정책은 `random`, `attack`, `evade`, `cycle`, `defensive`, `pressure`, `adaptive`, `guard_mixed_adaptive` 8종이다.

| 예정 난이도 | NPC 정책 ID | 개요 |
|---|---|---|
| 쉬움 | `rookie_cycle` | 고정 순환 훈련생 |
| 쉬움 | `rookie_guard` | 방어 45/공격 30/회피 25 비율형 |
| 쉬움 | `reckless_raider` | 공격→공격→회피, 고BRK 시 방어 |
| 보통 | `balanced_soldier` | 연속 행동 제한 균형형 |
| 보통 | `veteran_guard` | 방어 우선 세 행동 적응형 |
| 보통 | `cautious_hunter` | 완만한 상태 임계값 압박형 |
| 어려움 | `pressure` | 공격적 상태 임계값형 |
| 어려움 | `adaptive` | 최근 최빈 행동 카운터형 |
| 어려움 | `tactical_evaluator` | 상대 행동 분포 기반 한 턴 기대값형 |
| 매우 어려움 | `weighted_analyst` | 최근 행동 가중 기대값형 |
| 매우 어려움 | `regret_duelist` | 과거 공개 교환의 후회 최소화형 |
| 매우 어려움 | `executor` | 낮은 온도의 상태·후속 기회 평가형 |

### 6.1 8×12 실험 종합

각 케이스 2,000회, 총 192,000경기, `seed=20260831`:

| 예정 난이도 | NPC | 평균 Player 승률 | 평균 NPC 승률 | 평균 턴 | 판단 |
|---|---|---:|---:|---:|---|
| 쉬움 | `rookie_cycle` | 55.94% | 43.45% | 32.33 | 쉬움보다 약간 강함 |
| 쉬움 | `rookie_guard` | 66.50% | 33.17% | 33.64 | 의도에 적합 |
| 쉬움 | `reckless_raider` | 31.74% | 67.44% | 28.45 | 매우 강함, 재설계 필요 |
| 보통 | `balanced_soldier` | 56.92% | 42.48% | 30.82 | 적합 |
| 보통 | `veteran_guard` | 58.00% | 41.66% | 32.86 | 적합 |
| 보통 | `cautious_hunter` | 53.46% | 45.91% | 30.47 | 적합 |
| 어려움 | `pressure` | 43.67% | 54.62% | 25.49 | 적합 |
| 어려움 | `adaptive` | 43.07% | 56.31% | 30.70 | 적합 |
| 어려움 | `tactical_evaluator` | 39.51% | 59.45% | 26.46 | 적합, 상단 난이도 |
| 매우 어려움 | `weighted_analyst` | 34.50% | 64.51% | 25.66 | 적합 |
| 매우 어려움 | `regret_duelist` | 44.75% | 54.12% | 26.80 | 너무 약함, 재설계 필요 |
| 매우 어려움 | `executor` | 32.01% | 67.03% | 25.22 | 적합 |

승률 표준오차는 50% 부근에서 약 1.1%p, 95% 오차 범위는 약 ±2.2%p다.

### 6.2 확인된 NPC 문제

1. `reckless_raider`는 쉬움이 아니다. `공격→공격→회피`가 최근 최빈 행동을 추적하는 Player를 역으로 공략한다. `adaptive` Player 승률은 4.75%였다. 공격 50/방어 30/회피 20의 단순 비율형 또는 공격→공격→방어로 바꾸는 안을 우선 검토한다.
2. `regret_duelist`는 매우 어려움이 아니다. 공격 고정 Player에게 75% 승률을 허용한다. 현재 상태·다운·그로기 가치를 후회 계산에 포함하고 방어 확률 상한 및 진행 행동 최소 확률을 추가해야 한다.
3. `rookie_cycle`은 평균 Player 승률 55.94%로 쉬움보다는 보통에 가깝다. 시작 순서나 그로기 행동을 더 비효율적으로 만들 수 있다.
4. 난이도가 높을수록 경기가 짧아진다. 보통 약 31턴, 어려움 약 28턴, 매우 어려움 약 26턴이다. 난이도와 경기 페이스를 별도로 제어할 필요가 있다.

## 7. 자동 테스트 상태

현재 `test_battle_sim.py`의 테스트는 22개이며 모두 통과한다.

주요 검증:

- 27개 결과 존재 및 완전 대칭
- 회피 실패 위험 행 16/24 대칭
- G01/G02/G03 핵심 수치
- 다운 대기·기상·인터벌 중첩
- 상태이상 지속시간 감소의 기본 골격
- 그로기 대상 BRK 최대치 처리
- 동일 시드 재현
- 한국어 상세 해설
- 전략 양측 주입
- 전략 매트릭스와 직사각 그리드 케이스 수
- 방어 혼합 전략의 허용 행동 풀
- 난이도별 NPC 3개 및 플레이어 정책 8개 구성
- 수동 Player 행동 입력 기록
- 플레이어 그로기 강제 턴 진행
- Player 선택이 필요한 턴의 무입력 진행 차단

룰북의 21개 검증 기준 전체를 자동화한 것은 아니다. 특히 다인 교대, 실제 액티브·패시브, 주사위 조작 충돌, 상태이상 실효 효과는 아직 테스트 대상이 아니다.

## 8. 아직 구현되지 않은 범위

- 액티브 스킬 데이터 모델과 실행 파이프라인
- 패시브 스킬
- 스킬 비용·쿨다운·경기당 사용 제한
- 주사위 minimum/maximum 조작 효과
- 행동 강제 효과
- HP/STA/BRK 결과 증폭 스킬
- 상태이상 해제 및 실제 상태이상 효과
- 상태이상 중첩·재적용·면역
- 예약 효과
- 1 대 N/N 대 N 팀, 벤치, 라운드별 교대
- RisuAI Lua 프론트엔드 포팅

`StatusEffect` 자료구조와 지속시간 감소 골격은 존재하지만 실제 혼란·행동 불능·주사위 제한 효과는 없다.

## 9. 액티브 스킬 설계 시 유지할 원칙

이전 검토에서 보수적인 초기 범위는 다음과 같았다. 아직 코드에는 반영하지 않았다.

- 일반 스킬 비용 STA 12~18
- 강한 제어 비용 STA 20~30
- 결과 증폭 1.10~1.20배
- HP 추가 피해 4~8
- BRK 추가 축적 4~7
- 약한 주사위 조작: 자기 최소 2 또는 상대 최대 5
- 일반 쿨다운 2턴, 강한 제어 3~4턴
- 상태이상 실제 발동 1~2턴

스킬 밸런스는 랜덤 대전 하나가 아니라 플레이어 정책 8종과 NPC 정책군 전체에서 비교해야 한다.

## 10. 다음 작업 권장 순서

1. `reckless_raider`, `regret_duelist`, 필요 시 `rookie_cycle`을 재설계한다.
2. 8×12 그리드를 같은 시드와 반복 횟수로 다시 실행하여 난이도 구간을 확정한다.
3. NPC 정책 ID와 실제 캐릭터 이름·성격·행동 설명을 데이터로 분리한다.
4. 액티브 스킬 공통 스키마를 정의한다.
5. 스킬 없는 `Action` 선택과 `Action + Skill` 의도를 분리한다.
6. 사용 가능성 검증→비용 지불→행동 강제→주사위 조작→결과 증폭 순서를 구현한다.
7. 무스킬 기준선과 스킬 전략 매트릭스를 비교한다.
8. Python 규칙이 안정된 뒤 `projects/roguelike-stage4a/RogueLikePOC.lua` 패턴을 참조해 RisuAI Lua 모듈로 이식한다.

## 11. 새 작업 시작 체크리스트

새 채팅에서 다음 순서로 확인하면 된다.

1. 이 문서를 읽는다.
2. `README.md`의 실행 명령을 확인한다.
3. `battle_sim.py`의 `STRATEGY_NAMES`, `PLAYER_TEST_STRATEGIES`, `NPC_STRATEGIES_BY_DIFFICULTY`를 확인한다.
4. 자동 테스트 22개를 실행한다.
5. 변경 전 `results/npc_roster_8x12.json`을 기준선으로 보존한다.
6. 결과표를 바꾸면 `baseline.json`, 방어 전략 매트릭스, 8×12 NPC 그리드를 모두 재생성한다.
7. 전략만 바꾸면 최소 8×12 NPC 그리드를 재생성한다.
