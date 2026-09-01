# Battle Simulator 액티브 스킬 스키마

- 문서 버전: 1.0
- 확정일: 2026-09-01
- 구현 상태: 설계 확정, Python Phase A·B·C 완료, 다음 작업 Phase D 상태·예약 효과
- 기준 문서: `ROUND_TURN_BATTLE_POC_RULEBOOK.md`

## 1. 설계 원칙

- 효과 내용과 적용 방식을 분리한다.
- 액티브 스킬은 기본 행동과 함께 선택하고 양측이 동시에 공개한다.
- `requirements`는 스킬을 선택할 수 있는지를, `application.condition`은 사용한 스킬의 개별 효과가 발동하는지를 판정한다.
- 모든 스킬은 레벨별 완성 데이터를 가지며 강화 과정에서 비용, 쿨다운, 효과량, 효과 종류가 달라질 수 있다.
- 스킬 레벨과 보유 스킬 수의 증가는 고정된 상대에 대한 전체 기대 승률을 높이는 수직 성장 요소다.
- 큰 스킬 전력 차이에서 일방적인 결과를 허용하되, 비슷한 전력대에서 단일 스킬이 대부분의 승패를 독점하는 설계는 지양한다.

## 2. 전체 구조

```text
SkillDefinition
  schema_version
  id / name / description / tags
  max_level
  targeting
  levels[]
    level
    costs[]
    cooldown
    usage_limit
    requirements
    applications[]
      id
      delivery
      timing
      target
      condition
      priority
      effects[]
  ui
```

```json
{
  "schema_version": 1,
  "id": "power_strike",
  "name": "파워 스트라이크",
  "description": "공격 행동의 HP 피해를 강화한다.",
  "tags": ["attack", "damage"],
  "max_level": 3,
  "targeting": {
    "type": "opponent",
    "selection_required": false
  },
  "levels": [],
  "ui": {
    "icon": null,
    "short_description": "공격 HP 피해 강화",
    "show_exact_values": true
  }
}
```

각 `levels[]` 항목은 이전 레벨에 대한 패치가 아니라 해당 레벨의 완성된 실행 데이터다. 런타임은 캐릭터가 보유한 레벨 하나만 조회한다.

## 3. 대상

지원 대상 ID:

```text
self
opponent
both
selected_ally
selected_opponent
```

현재 1 대 1 POC는 `self`, `opponent`, `both`만 구현한다. 다인전용 선택 대상은 스키마에 예약하되 검증기가 명시적으로 거부한다.

## 4. 레벨별 비용과 제한

```json
{
  "level": 1,
  "costs": [
    {
      "resource": "stamina",
      "amount": 16,
      "minimum_remaining": 0
    }
  ],
  "cooldown": {
    "turns": 2,
    "starts": "on_skill_commit",
    "decrements": "owner_turn"
  },
  "usage_limit": {
    "per_match": 3,
    "per_round": null
  },
  "requirements": {},
  "applications": []
}
```

비용 자원은 `hp`, `stamina`, `break_gauge`를 지원한다. HP 비용은 `minimum_remaining`으로 자기 KO를 금지할 수 있다.

쿨다운 시작 시점:

```text
on_skill_commit
after_resolution
```

쿨다운 감소 단위:

```text
owner_turn
owner_actionable_turn
round_end
```

기본값은 `starts=on_skill_commit`, `decrements=owner_turn`이다. 제한이 없는 사용 횟수는 `null`로 기록한다.

## 5. 사용 가능 조건

`requirements` 실패 시 스킬을 선택할 수 없으며 비용, 쿨다운, 사용 횟수를 소비하지 않는다.

특정 기본 행동과 결합하는 단축 필드:

```json
{
  "requirements": {
    "allowed_actions": ["attack"],
    "condition": null
  }
}
```

내부에서는 다음 조건으로 정규화한다.

```json
{
  "type": "action_in",
  "subject": "self",
  "values": ["attack"]
}
```

복합 조건은 `all`, `any`, `not`으로 조합한다.

```json
{
  "all": [
    {
      "type": "action_in",
      "subject": "self",
      "values": ["attack"]
    },
    {
      "any": [
        {
          "type": "resource_ratio_at_most",
          "subject": "opponent",
          "resource": "hp",
          "value": 0.3
        },
        {
          "type": "resource_at_least",
          "subject": "opponent",
          "resource": "break_gauge",
          "value": 75
        }
      ]
    }
  ]
}
```

### 5.1 조건 ID

행동·기록:

```text
action_in
previous_action_is
recent_action_count_at_least
```

자원:

```text
resource_at_least
resource_at_most
resource_ratio_at_least
resource_ratio_at_most
```

경기 상태:

```text
round_at_least
round_at_most
turn_in_round_is
down_count_at_least
is_groggy
is_down
is_ko
```

상태·스킬:

```text
status_present
status_absent
status_count_at_least
skill_ready
skill_uses_remaining_at_least
```

주사위·결과 조건은 해당 정보가 공개된 이후의 `application.condition`에서만 사용할 수 있다.

```text
dice_result_is
raw_die_is
final_die_at_least
final_die_at_most
result_entry_is
result_delta_is
```

조건 평가기는 각 `timing`에서 아직 존재하지 않거나 공개되지 않은 정보를 참조하는 조건을 스키마 오류로 거부한다.

## 6. 적용 단위

```json
{
  "id": "increase_hp_damage",
  "delivery": { "type": "immediate" },
  "timing": "before_result_apply",
  "target": "opponent",
  "condition": null,
  "priority": 100,
  "effects": []
}
```

`application.condition` 실패 시 스킬 비용과 사용 횟수는 이미 소비되고 쿨다운도 시작한다. 해당 application만 적용하지 않으며 다른 application은 독립적으로 판정한다.

## 7. 적용 방식

### 7.1 즉시 — `immediate`

```json
{ "type": "immediate" }
```

지정된 `timing`에 한 번 적용한다.

### 7.2 상태 — `status`

```json
{
  "type": "status",
  "status": {
    "id": "shaken",
    "name": "흔들림",
    "duration": {
      "value": 1,
      "unit": "owner_turn",
      "starts": "next_owner_turn"
    },
    "stacking": {
      "mode": "refresh",
      "max_stacks": 1
    },
    "removable": true,
    "polarity": "negative"
  }
}
```

지속시간 단위:

```text
owner_turn
owner_actionable_turn
exchange
round
trigger_count
```

중첩 방식은 `ignore`, `refresh`, `replace`, `stack`을 예약한다. 첫 Python POC는 `refresh`, `replace`, `max_stacks=1`만 지원한다.

### 7.3 예약 — `queued`

```json
{
  "type": "queued",
  "trigger": {
    "event": "before_result_apply",
    "condition": {
      "type": "dice_result_is",
      "subject": "self",
      "value": "win"
    }
  },
  "expires": {
    "value": 2,
    "unit": "owner_turn"
  },
  "consumes": "on_trigger"
}
```

소비 방식:

```text
on_trigger
on_successful_apply
never
```

### 7.4 패시브 — `passive`

```json
{ "type": "passive" }
```

공통 효과 엔진 재사용을 위해 예약한다. 액티브 스킬 첫 POC 범위에는 포함하지 않는다.

## 8. 적용 시점

전체 예약 시점:

```text
on_skill_commit
before_action_reveal
after_action_reveal
before_roll
after_raw_roll
before_dice_compare
after_dice_compare
before_result_lookup
after_result_lookup
before_result_apply
after_result_apply
on_status_apply
on_status_remove
on_groggy
on_down
on_wake
on_round_end
on_interval
```

첫 Python POC 필수 시점:

```text
on_skill_commit
before_action_reveal
before_roll
after_raw_roll
before_dice_compare
before_result_apply
after_result_apply
on_status_apply
on_round_end
on_interval
```

## 9. 효과 내용 카테고리

확정 카테고리:

```text
resource_change
result_modifier
dice_modifier
action_control
status_control
skill_control
```

### 9.1 `resource_change`

현재 자원을 결과표와 무관하게 직접 변경한다.

```json
{
  "category": "resource_change",
  "operation": "add",
  "resource": "stamina",
  "value": 15
}
```

연산:

```text
add
set
add_percent_of_max
set_percent_of_max
```

### 9.2 `result_modifier`

결과표가 산출한 HP·STA·BRK 변화량을 수정한다.

```json
{
  "category": "result_modifier",
  "resource": "hp",
  "direction": "dealt",
  "polarity": "damage",
  "operation": "multiply",
  "value": 1.2
}
```

방향은 `dealt`, `received`, `self`, `opponent`, 변화 극성은 `damage`, `recovery`, `increase`, `decrease`, `any`를 지원한다. 연산은 `add`, `multiply`, `minimum`, `maximum`, `nullify`를 지원한다. 곱셈과 고정값 적용 후 최종 소수점은 내림한다.

### 9.3 `dice_modifier`

```json
{
  "category": "dice_modifier",
  "operation": "set_minimum",
  "value": 2
}
```

예약 연산:

```text
set_minimum
set_maximum
add
set
reroll
roll_keep
change_tie_result
```

첫 POC는 `set_minimum`, `set_maximum`만 구현한다. minimum을 우선 적용하고 maximum을 보조 적용한다. 충돌로 범위가 역전되면 minimum 값을 최종 주사위로 사용한다.

### 9.4 `action_control`

```json
{
  "category": "action_control",
  "operation": "forbid",
  "actions": ["evade"]
}
```

연산:

```text
allow_only
forbid
force
replace
cancel
```

첫 POC는 `allow_only`, `forbid`, `force`를 구현한다. 여러 행동 제어가 충돌하면 높은 priority를 먼저 적용하며 동일 priority 충돌은 스키마 오류로 기록한다.

### 9.5 `status_control`

```json
{
  "category": "status_control",
  "operation": "remove",
  "selector": {
    "type": "polarity",
    "value": "negative",
    "order": "oldest"
  },
  "count": 1
}
```

연산:

```text
remove
change_duration
block_next
grant_immunity
replace
```

첫 POC는 `remove`, `change_duration`을 구현한다. 선택기는 `status_id`, `polarity` 및 `oldest`, `newest`, `highest_priority` 순서를 지원한다.

### 9.6 `skill_control`

```json
{
  "category": "skill_control",
  "operation": "change_cooldown",
  "selector": {
    "type": "skill_id",
    "value": "second_wind"
  },
  "value": -1
}
```

연산:

```text
modify_cost
change_cooldown
reset_cooldown
change_charges
disable
enable
```

첫 POC는 `modify_cost`, `change_cooldown`, `change_charges`를 구현한다. 자기 자신을 대상으로 삼을 수 있는지는 효과 데이터에서 명시적으로 허용해야 하며, 비용과 쿨다운은 0 미만이 될 수 없다.

## 10. 실행 순서

```text
1. 기본 행동 선택
2. 액티브 스킬과 대상 선택
3. 스킬 레벨 데이터 조회
4. allowed_actions 및 requirements.condition 검사
5. 대상 유효성 검사
6. 비용·쿨다운·사용 횟수 검사
7. TurnIntent 확정
8. 비용 지불, 사용 횟수 차감, 쿨다운 시작
9. 양측 행동·스킬 동시 공개
10. timing 순서에 따라 application 조회
11. application.condition 검사
12. delivery에 따라 즉시 적용·상태 저장·예약 저장
13. effects를 priority 순으로 계산
14. 기본 결과와 모든 수정치를 동시 반영
15. 턴 종료 시 상태·쿨다운·예약 만료 갱신
```

정상적으로 commit된 스킬은 개별 효과 조건이 실패해도 비용, 사용 횟수, 쿨다운을 반환하지 않는다. 상태 면역이나 후속 상황 변화 때문에 모든 효과가 막힌 경우의 반환 여부도 기본적으로 `반환 없음`으로 한다.

## 11. 대표 예시

```json
{
  "schema_version": 1,
  "id": "driving_strike",
  "name": "드라이빙 스트라이크",
  "description": "공격 승리 시 상대의 브레이크를 추가로 압박한다.",
  "tags": ["attack", "break"],
  "max_level": 1,
  "targeting": {
    "type": "opponent",
    "selection_required": false
  },
  "levels": [
    {
      "level": 1,
      "costs": [
        { "resource": "stamina", "amount": 16, "minimum_remaining": 0 }
      ],
      "cooldown": {
        "turns": 2,
        "starts": "on_skill_commit",
        "decrements": "owner_turn"
      },
      "usage_limit": {
        "per_match": null,
        "per_round": null
      },
      "requirements": {
        "allowed_actions": ["attack"],
        "condition": null
      },
      "applications": [
        {
          "id": "add_break_on_win",
          "delivery": { "type": "immediate" },
          "timing": "before_result_apply",
          "target": "opponent",
          "condition": {
            "type": "dice_result_is",
            "subject": "self",
            "value": "win"
          },
          "priority": 100,
          "effects": [
            {
              "category": "result_modifier",
              "resource": "break_gauge",
              "direction": "dealt",
              "polarity": "increase",
              "operation": "add",
              "value": 7
            }
          ]
        }
      ]
    }
  ],
  "ui": {
    "icon": null,
    "short_description": "공격 승리 시 BRK +7",
    "show_exact_values": true
  }
}
```

## 12. Python POC 구현 TODO

### Phase A — 데이터 모델과 검증

- [x] `SkillDefinition`, `SkillLevel`, `SkillCost`, `CooldownRule`, `UsageLimit` 자료구조 정의
- [x] `SkillApplication`, `DeliverySpec`, `ContentEffect` 자료구조 정의
- [x] `Condition` 재귀 자료구조와 `all`·`any`·`not` 파서 정의
- [x] 여섯 효과 카테고리와 각 operation enum 정의
- [x] 스킬 ID, 레벨 연속성, 필수 필드, 지원 enum을 검사하는 스키마 검증기 작성
- [x] 현재 1 대 1 POC에서 지원하지 않는 대상·timing·operation을 명확한 오류로 거부
- [x] 레벨별 완성 데이터를 읽어 불변 런타임 정의로 정규화

완료 기준: 예제 스킬 JSON을 로드하고 잘못된 행동 ID, 레벨 누락, timing과 조건 정보 단계 불일치를 자동 테스트로 검출한다.

완료 기록: 2026-09-01 `skill_schema.py`와 `test_skill_schema.py`에 구현했다. 스키마 전용 테스트 13개가 통과한다.

### Phase B — 캐릭터와 턴 입력 확장

- [x] `CharacterState`에 보유 스킬 ID·레벨, 쿨다운, 남은 사용 횟수 추가
- [x] 기존 행동 입력을 `TurnIntent(base_action, active_skill_id, target_id)`로 확장
- [x] 무스킬 입력은 `active_skill_id=null`로 완전 호환
- [x] `allowed_actions` 및 일반 `requirements` 평가기 구현
- [x] 대상, 비용, 쿨다운, 사용 횟수 검증 구현
- [x] commit 시 비용 지불·횟수 차감·쿨다운 시작을 원자적으로 처리
- [x] 수동 엔진이 사용할 수 없는 스킬과 사유를 UI에 제공할 수 있도록 구조화된 검증 결과 반환

완료 기준: 무스킬 기존 시드 결과가 바뀌지 않고, 유효·무효 스킬 입력과 비용 처리가 자동 테스트를 통과한다.

완료 기록: 2026-09-01 `battle_sim.py`와 `test_skill_runtime.py`에 구현했다. Phase B 테스트 14개가 통과하며, 100,000경기 무스킬 기준선은 Player 49.419%, Enemy 50.032%, 평균 34.4389턴으로 변경 전과 정확히 일치한다.

### Phase C — 이벤트와 효과 실행기

- [x] 필수 `timing` 이벤트 디스패처 추가
- [x] application condition을 해당 timing의 공개 정보만으로 평가
- [x] priority 기반 효과 정렬과 구조화된 적용 로그 구현
- [x] `resource_change` 구현
- [x] `result_modifier` 구현 및 배율·고정값·내림 순서 확정
- [x] `dice_modifier`의 minimum·maximum 구현
- [x] `action_control`의 allow_only·forbid·force 구현
- [x] `status_control`의 remove·change_duration 구현
- [x] `skill_control`의 비용·쿨다운·사용 횟수 변경 구현
- [x] 양측 효과와 기본 결과를 기존 동시 적용 원칙에 맞게 병합

완료 기준: 여섯 카테고리마다 최소 한 개의 즉시 스킬이 단위 테스트와 단일 경기 트레이스를 통과한다.

완료 기록: 2026-09-01 `battle_sim.py`와 `test_skill_effects.py`에 구현했다. 즉시 적용 방식의 필수 timing, condition, priority와 여섯 효과 카테고리를 12개 Phase C 테스트로 검증했다. 이후 Player만 최대 4개 스킬을 장착·사용하고 무스킬 Enemy와 대전하는 UI 테스트베드와 테스트 8개를 추가해 전체 71개 테스트가 통과한다. 100,000경기 무스킬 기준선도 Player 49.419%, Enemy 50.032%, 더블 KO 0.549%, 평균 34.4389턴으로 정확히 유지된다. `on_status_apply` 실제 호출은 상태 부여가 구현되는 Phase D에서 연결한다.

### Phase D — 상태와 예약 효과

- [ ] `StatusEffect`를 `delivery=status` payload 보관 구조로 마이그레이션
- [ ] 다음 자기 턴부터 발동하는 시작 규칙 구현
- [ ] refresh·replace 및 `max_stacks=1` 구현
- [ ] 다운 대기·행동 불능 중 지속시간 감소 규칙 유지
- [ ] 정화 선택기와 제거 불가능 상태 처리 구현
- [ ] `QueuedEffect` 저장, trigger, expires, consumes 구현
- [ ] 같은 턴에 새로 부여된 상태가 선행 정화에 제거되지 않는 순서 보장

완료 기준: 흔들림형 주사위 제한, 결과 증폭 상태, 상태 제거, 다음 성공 시 1회 발동 예약 효과가 자동 테스트를 통과한다.

### Phase E — 스킬 세트와 AI

- [ ] 여섯 효과 카테고리를 각각 검증하는 최소 예제 스킬 세트 작성
- [ ] 무스킬·저레벨·고레벨·다중 스킬 성장 사다리 캐릭터 구성 작성
- [ ] CPU 후보를 `(base_action, active_skill_id, target_id)` 단위로 생성
- [ ] CPU가 requirements를 만족하지 않는 후보를 제거하도록 구현
- [ ] 초기에는 규칙 기반 사용 정책을 추가하고 이후 기대값형 평가기로 확장
- [ ] 정책 난수와 전투 주사위 난수 분리 원칙 유지
- [ ] 동일 시드·동일 스킬 입력 재현 테스트 추가

완료 기준: Player와 NPC가 모두 스킬을 선택할 수 있고 블라인드 동시 선택 및 시드 재현이 유지된다.

### Phase F — 통계와 밸런스 검증

- [ ] 스킬별 선택·성공·조건 실패·효과 차단·미사용 횟수 집계
- [ ] 경기당 비용, 추가 HP·STA·BRK 기여량, 상태 부여·제거 횟수 집계
- [ ] 무스킬 기준선과 성장 사다리 전략 그리드 비교
- [ ] 레벨 및 스킬 수 증가에 따른 전체 기대 승률 추세 검증
- [ ] 단일 스킬 제거 실험 지원
- [ ] 특정 스킬 하나가 비슷한 전력대의 결과를 독점하는지 보고서에 표시
- [ ] 결과 JSON에 스키마 버전과 스킬 구성 기록

완료 기준: 같은 상대군에서 무스킬→저레벨→고레벨→다중 스킬의 승률·경기 길이·스킬 기여도를 재현 가능한 JSON으로 비교한다.

### Phase G — UI, 문서, Lua 동기화

- [ ] Tkinter UI에 사용 가능 스킬, 비용, 쿨다운, 남은 횟수 표시
- [ ] 기본 행동 선택 후 결합 가능한 스킬만 활성화
- [ ] 전투 로그에 요구조건, 비용, 발동·실패, 상태·예약, 수정 전후 수치 표시
- [ ] CLI에 스킬 구성과 성장 사다리 실행 옵션 추가
- [ ] 구현된 operation과 후순위 operation을 문서에서 구분
- [ ] Python 규칙 안정화 후 `projects/battle-sim-lua`에 동일 데이터와 실행 순서 이식
- [ ] CHARX 재빌드 및 RisuAI 수동 회귀 테스트

완료 기준: Python UI·CLI에서 동일 스킬 데이터가 동작하고, 확정된 Python 기준선이 Lua/CHARX에 동기화된다.

## 13. 첫 구현에서 제외하는 범위

- 다인 대상 선택
- 상태 중첩 2단계 이상
- 재굴림, 여러 주사위 중 선택, 동률 규칙 변경
- 행동 교체와 행동 취소
- 상태 면역·반사·변환
- 전체 스킬 봉인과 임의 스킬 복제
- 과거 턴 되돌리기 또는 승리 조건 변경
- 패시브 스킬

스키마에는 일부 확장 enum을 예약하지만 첫 POC 검증기는 미지원 기능을 묵시적으로 무시하지 않고 오류로 거부한다.
