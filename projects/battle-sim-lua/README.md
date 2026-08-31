# RisuAI Round/Turn Battle Simulator

`projects/battle-sim-poc/battle_sim.py`의 현재 1 대 1 무스킬 엔진을 RisuAI Lua 모듈로 이식한 버전이다.

## 포함 범위

- 27개 기본 결과표와 G01/G02/G03 그로기 결과표
- HP/STA/BRK 동시 적용, 완전 그로기, 최대 3다운과 KO
- 다운 대기·기상, 대기 HP 4% 회복, 8턴 인터벌
- 플레이어 수동 공격/방어/회피 및 POC의 NPC 12종
- 전투 난수와 정책 난수를 분리한 직렬화 가능 LCG
- 채팅별 `setState` 저장과 RisuAI 버튼 UI
- 턴별 주사위 판정, 피해 점멸·흔들림, 상태 heartbeat, 경기 종료 오버레이
- 결과 확인 후 다운·그로기·인터벌을 한 단계씩 진행하는 presentation 상태

Python POC에서 아직 미구현인 액티브/패시브 스킬, 실제 상태이상 효과, 다인 교대는 이 모듈에도 포함하지 않는다.

## 사용

1. RisuAI에서 `BattleSim-RisuAI.charx`를 모듈/캐릭터로 import한다.
2. 표시되는 패널에서 NPC를 선택하거나 채팅에 `/battle`을 입력한다.
3. 공격·방어·회피 버튼으로 진행한다.

## 초상화 에셋

모듈은 `{{raw::name.png}}` 방식으로 사용자 주입 에셋을 표시한다. `{name}`은 플레이어의 경우 `player`, NPC는 `rookie_cycle`, `balanced_soldier`, `executor` 같은 정책 ID다.

1280×768 이미지 17장:

```text
{name}_main_d0_healthy.png
{name}_main_d0_wounded.png
{name}_main_d0_critical.png
{name}_main_d1_healthy.png
{name}_main_d1_wounded.png
{name}_main_d1_critical.png
{name}_main_d2_healthy.png
{name}_main_d2_wounded.png
{name}_main_d2_critical.png
{name}_down_d1.png
{name}_down_d2.png
{name}_ko.png
{name}_interval_d0.png
{name}_interval_d1.png
{name}_interval_d2.png
{name}_result_win.png
{name}_result_lose.png
```

1024×1024 투명 이미지 21장:

```text
{name}_action_attack.png
{name}_action_defend.png
{name}_action_evade.png
{name}_resolve_attack_success.png
{name}_resolve_attack_failed.png
{name}_resolve_defend_success.png
{name}_resolve_guard_broken.png
{name}_resolve_evade_success.png
{name}_resolve_evade_caught.png
{name}_resolve_cross_clash.png
{name}_resolve_clinch.png
{name}_resolve_standoff.png
{name}_reaction_hit_light.png
{name}_reaction_hit_medium.png
{name}_reaction_hit_heavy.png
{name}_reaction_stamina_drained.png
{name}_reaction_break_shaken.png
{name}_reaction_recover.png
{name}_reaction_groggy.png
{name}_reaction_wake_d1.png
{name}_reaction_wake_d2.png
```

이미지가 없을 때는 초상화 프레임의 P/E 폴백이 남는다.

행동 이후에는 행동 이미지→주사위→행동 결과 이미지→피해·자원 반응 이미지→그로기·기상 이미지→새 메인 이미지 순서로 표시된다. `다음 턴`을 누르면 다운 대기, 그로기 강제 행동, 라운드 인터벌을 각각 한 단계씩 확인할 수 있다.

재빌드:

```powershell
.\projects\battle-sim-lua\build.ps1 -Force
```

빌드 스크립트는 독립 Lua 모듈의 예시인 `characters/useful-bots/roguelikePOC-stage4A.charx` 구조를 스캐폴드로 사용한다. BattleSim 전용 모듈 ID와 메타데이터로 교체하므로 원본 RogueLikePOC 또는 Labo En 모듈을 개량하거나 덮어쓰지 않는다.

CSS는 Lua가 출력하지 않는다. `BattleSim.css`의 `<style>` 블록을 `card.data.extensions.risuai.backgroundHTML`에 넣는 RisuAI background embedding 방식을 사용한다.
