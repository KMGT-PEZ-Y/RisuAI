# 사진 에셋 전체 목록 · Lua POC v2

`{key}`는 대전 준비에서 지정한 **사진 에셋 접두사**입니다. 플레이어 기본값은 `player`, 상대 기본값은 `balanced_soldier`입니다. 예를 들어 상대 접두사를 `rival_a`로 지정하면 `rival_a_main_d0_healthy.png`, `rival_a_action_attack.png`를 등록합니다. AI를 기존/NG+로 바꿔도 접두사는 바뀌지 않습니다.

사진 파일은 RisuAI 에셋에 아래 이름으로 추가합니다. 모듈은 `<img src="{{raw::파일명.png}}">` 방식으로 읽습니다. 로컬 파일 경로·웹 URL을 입력하는 방식이 아닙니다. 실제 사진은 이번 배포에 포함하지 않았습니다.

| 준비 범위 | 캐릭터 1명 | 양쪽 모두 서로 다른 캐릭터 |
|---|---:|---:|
| 기존 전투 연출 | 38장 | 76장 |
| 일반 스킬 전부 | 추가 35장 | 추가 35장 (공용) |
| 일반 스킬까지 전체 | 73장 | 111장 |
| 개발자 테스트 스킬도 전부 | 추가 17장, 총 90장 | 추가 17장 (공용), 총 128장 |

장착할 스킬만 먼저 제작해도 됩니다. 아이콘은 캐릭터 접두사 없이 `skill_{스킬ID}.png`로 등록하며, 양측 캐릭터와 모든 레벨이 공유합니다. 장착할 고유 스킬 수만큼만 준비하면 됩니다.

## 기본 초상화 17장

**5:3, 권장 1280×768, 일반 PNG.** 프레임을 채우도록 잘리므로 얼굴과 중요한 소품은 가장자리를 피합니다.

| 파일명 | 용도 |
|---|---|
| `{key}_main_d0_healthy.png` | 0회 다운 이후 기본 자세 · HP 60% 초과 |
| `{key}_main_d0_wounded.png` | 0회 다운 이후 기본 자세 · HP 30% 초과~60% |
| `{key}_main_d0_critical.png` | 0회 다운 이후 기본 자세 · HP 30% 이하 |
| `{key}_main_d1_healthy.png` | 1회 다운 이후 기본 자세 · HP 60% 초과 |
| `{key}_main_d1_wounded.png` | 1회 다운 이후 기본 자세 · HP 30% 초과~60% |
| `{key}_main_d1_critical.png` | 1회 다운 이후 기본 자세 · HP 30% 이하 |
| `{key}_main_d2_healthy.png` | 2회 다운 이후 기본 자세 · HP 60% 초과 |
| `{key}_main_d2_wounded.png` | 2회 다운 이후 기본 자세 · HP 30% 초과~60% |
| `{key}_main_d2_critical.png` | 2회 다운 이후 기본 자세 · HP 30% 이하 |
| `{key}_down_d1.png` | 첫 번째 다운 |
| `{key}_down_d2.png` | 두 번째 다운 |
| `{key}_ko.png` | 세 번째 다운 / KO |
| `{key}_interval_d0.png` | 0회 다운 상태의 라운드 인터벌 |
| `{key}_interval_d1.png` | 1회 다운 상태의 라운드 인터벌 |
| `{key}_interval_d2.png` | 2회 다운 상태의 라운드 인터벌 |
| `{key}_result_win.png` | 최종 승리 |
| `{key}_result_lose.png` | 최종 패배 / 더블 KO |

## 행동·결과·반응 21장

**1:1, 권장 1024×1024, 투명 배경 PNG.** 전체 이미지가 보이도록 표시됩니다. 좌우 자동 반전은 하지 않으므로 플레이어·상대의 시선 방향은 이미지에 반영합니다.

| 파일명 | 용도 |
|---|---|
| `{key}_action_attack.png` | 공격 행동 |
| `{key}_action_defend.png` | 방어 행동 |
| `{key}_action_evade.png` | 회피 행동 |
| `{key}_resolve_attack_success.png` | 공격으로 상대 HP 피해 발생 |
| `{key}_resolve_attack_failed.png` | 공격했으나 상대 HP 피해 없음 |
| `{key}_resolve_defend_success.png` | 방어 후 자신의 HP 피해 없음 |
| `{key}_resolve_guard_broken.png` | 방어 중 자신의 HP 피해 발생 |
| `{key}_resolve_evade_success.png` | 회피 후 자신의 HP 피해 없음 |
| `{key}_resolve_evade_caught.png` | 회피 중 자신의 HP 피해 발생 |
| `{key}_resolve_cross_clash.png` | 공격/공격 무승부 · 결과표 02 |
| `{key}_resolve_clinch.png` | 방어/방어 무승부 · 결과표 14 |
| `{key}_resolve_standoff.png` | 회피/회피 무승부 · 결과표 26 |
| `{key}_reaction_hit_light.png` | 결과 피해 1~12 |
| `{key}_reaction_hit_medium.png` | 결과 피해 13~27 |
| `{key}_reaction_hit_heavy.png` | 결과 피해 28 이상 |
| `{key}_reaction_stamina_drained.png` | HP 피해 없이 STA 감소 |
| `{key}_reaction_break_shaken.png` | HP 피해 없이 BRK 증가 |
| `{key}_reaction_recover.png` | HP·STA 회복 또는 BRK 감소 |
| `{key}_reaction_groggy.png` | 새로 그로기 진입 |
| `{key}_reaction_wake_d1.png` | 첫 다운 후 기상 |
| `{key}_reaction_wake_d2.png` | 둘째 다운 후 기상 |

반응 우선순위는 HP 피해 → BRK 증가 → STA 감소 → 회복입니다. 기본 연출에서 행동 약 0.15초, 판정 결과 약 2.05초, 자원 반응 약 2.85초, 상태 반응 약 3.8초 순으로 나타나며, 다음 버튼은 약 5.2초 뒤 활성화됩니다. 빠른 진행은 이 애니메이션 대기를 생략합니다.

## 일반 스킬 아이콘 35장

모두 **1:1, 권장 1024×1024, 투명 배경 PNG**입니다. 장착 스킬 버튼, 스킬 설명, 주사위 아래의 사용 스킬 표시에 표시하는 공용 아이콘입니다. 설정의 **스킬 아이콘**을 켜면 표시됩니다. 스킬 사용 여부와 관계없이 초상화는 캐릭터별 행동·결과·반응 21장으로 action → resolve → reaction 연출을 진행합니다. 아이콘 등록 전에는 옵션을 꺼 두세요.

| 파일명 | 스킬 |
|---|---|
| `skill_rookie_power_strike.png` | 힘주어 치기 |
| `skill_rookie_recovery_form.png` | 자세 정비 |
| `skill_rookie_safe_footwork.png` | 안전한 발놀림 |
| `skill_rookie_create_distance.png` | 거리 확보 |
| `skill_rookie_tuck_chin.png` | 턱 당기기 |
| `skill_m01.png` | 묵직한 한 방 |
| `skill_m02.png` | 단단한 가드 |
| `skill_m03.png` | 호흡 정리 |
| `skill_m04.png` | 발판 잡기 |
| `skill_m05.png` | 힘 모으기 |
| `skill_m06.png` | 연결 타격 |
| `skill_m07.png` | 준비 끊기 |
| `skill_m08.png` | 중심 잡기 |
| `skill_m09.png` | 발놀림 흐트리기 |
| `skill_m10.png` | 숨통 조이기 |
| `skill_u01.png` | 가드 압박 |
| `skill_u02.png` | 받아치기 |
| `skill_u03.png` | 재정비 |
| `skill_u04.png` | 속행 준비 |
| `skill_u05.png` | 약점 포착 |
| `skill_u06.png` | 꿰뚫기 |
| `skill_u07.png` | 흐름 절단 |
| `skill_u08.png` | 측면 몰기 |
| `skill_u09.png` | 침착한 판정 |
| `skill_u10.png` | 브레이크 러시 |
| `skill_h01.png` | 분쇄 타격 |
| `skill_h02.png` | 철벽 자세 |
| `skill_h03.png` | 마지막 호흡 |
| `skill_h04.png` | 결전 호흡 |
| `skill_h05.png` | 전력 장전 |
| `skill_h06.png` | 결전의 일격 |
| `skill_h07.png` | 연결고리 파괴 |
| `skill_h08.png` | 도발 압박 |
| `skill_h09.png` | 승부수 |
| `skill_h10.png` | 한계 돌파 |

## 개발자 테스트 스킬 아이콘 17장 · 선택 사항

모두 **1:1, 권장 1024×1024, 투명 배경 PNG**입니다. 테스트 덱의 공용 아이콘을 표시할 때만 필요합니다.

| 파일명 | 스킬 |
|---|---|
| `skill_second_wind.png` | 세컨드 윈드 |
| `skill_power_drive.png` | 파워 드라이브 |
| `skill_steady_form.png` | 스테디 폼 |
| `skill_read_the_play.png` | 리드 더 플레이 |
| `skill_reset_rhythm.png` | 리듬 리셋 |
| `skill_breathing_control.png` | 호흡 조절 |
| `skill_reserve_plan.png` | 리저브 플랜 |
| `skill_sideline_coaching.png` | 사이드라인 코칭 |
| `skill_shaking_feint.png` | 셰이킹 페인트 |
| `skill_open_guard.png` | 오픈 가드 |
| `skill_focused_guard.png` | 포커스드 가드 |
| `skill_purge_negative.png` | 네거티브 퍼지 |
| `skill_stored_momentum.png` | 스토어드 모멘텀 |
| `skill_recovery_echo.png` | 리커버리 에코 |
| `skill_measured_strike.png` | 메저드 스트라이크 |
| `skill_growth_focus.png` | 그로스 포커스 |
| `skill_banked_pressure.png` | 뱅크드 프레셔 |
