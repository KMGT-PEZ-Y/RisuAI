"""Generate the complete, named photo handoff from current skill definitions."""
from pathlib import Path
from export_data import registry
ROOT=Path(__file__).resolve().parent
portraits=[]
for down in range(3):
    for band,label in [('healthy','HP 60% 초과'),('wounded','HP 30% 초과~60%'),('critical','HP 30% 이하')]:
        portraits.append((f'main_d{down}_{band}',f'{down}회 다운 이후 기본 자세 · {label}'))
portraits += [('down_d1','첫 번째 다운'),('down_d2','두 번째 다운'),('ko','세 번째 다운 / KO')]
portraits += [(f'interval_d{n}',f'{n}회 다운 상태의 라운드 인터벌') for n in range(3)]
portraits += [('result_win','최종 승리'),('result_lose','최종 패배 / 더블 KO')]
overlays=[('action_attack','공격 행동'),('action_defend','방어 행동'),('action_evade','회피 행동'),
 ('resolve_attack_success','공격으로 상대 HP 피해 발생'),('resolve_attack_failed','공격했으나 상대 HP 피해 없음'),
 ('resolve_defend_success','방어 후 자신의 HP 피해 없음'),('resolve_guard_broken','방어 중 자신의 HP 피해 발생'),
 ('resolve_evade_success','회피 후 자신의 HP 피해 없음'),('resolve_evade_caught','회피 중 자신의 HP 피해 발생'),
 ('resolve_cross_clash','공격/공격 무승부 · 결과표 02'),('resolve_clinch','방어/방어 무승부 · 결과표 14'),
 ('resolve_standoff','회피/회피 무승부 · 결과표 26'),
 ('reaction_hit_light','결과 피해 1~12'),('reaction_hit_medium','결과 피해 13~27'),('reaction_hit_heavy','결과 피해 28 이상'),
 ('reaction_stamina_drained','HP 피해 없이 STA 감소'),('reaction_break_shaken','HP 피해 없이 BRK 증가'),
 ('reaction_recover','HP·STA 회복 또는 BRK 감소'),('reaction_groggy','새로 그로기 진입'),
 ('reaction_wake_d1','첫 다운 후 기상'),('reaction_wake_d2','둘째 다운 후 기상')]
assert len(portraits)==17 and len(overlays)==21
public,developer=registry()
text='''# 사진 에셋 전체 목록 · Lua POC v2

`{key}`는 대전 준비에서 지정한 **사진 에셋 접두사**입니다. 플레이어 기본값은 `player`, 상대 기본값은 `balanced_soldier`입니다. 예를 들어 상대 접두사를 `rival_a`로 지정하면 `rival_a_main_d0_healthy.png`, `rival_a_skill_m01.png`를 등록합니다. AI를 기존/NG+로 바꿔도 접두사는 바뀌지 않습니다.

사진 파일은 RisuAI 에셋에 아래 이름으로 추가합니다. 모듈은 `<img src="{{raw::파일명.png}}">` 방식으로 읽습니다. 로컬 파일 경로·웹 URL을 입력하는 방식이 아닙니다. 실제 사진은 이번 배포에 포함하지 않았습니다.

| 준비 범위 | 캐릭터 1명 | 양쪽 모두 서로 다른 캐릭터 |
|---|---:|---:|
| 기존 전투 연출 | 38장 | 76장 |
| 일반 스킬 전부 | 추가 35장 | 추가 70장 |
| 일반 스킬까지 전체 | 73장 | 146장 |
| 개발자 테스트 스킬도 전부 | 추가 17장, 총 90장 | 추가 34장, 총 180장 |

장착할 스킬만 먼저 제작해도 됩니다. 예를 들어 각자 5종 고정 덱이면 스킬 사진은 캐릭터당 5장으로 시작할 수 있습니다. 레벨이 달라도 같은 스킬 사진을 재사용합니다.

## 기본 초상화 17장

**5:3, 권장 1280×768, 일반 PNG.** 프레임을 채우도록 잘리므로 얼굴과 중요한 소품은 가장자리를 피합니다.

| 파일명 | 용도 |
|---|---|
'''
text+='\n'.join(f'| `{{key}}_{suffix}.png` | {purpose} |' for suffix,purpose in portraits)
text+='''

## 행동·결과·반응 21장

**1:1, 권장 1024×1024, 투명 배경 PNG.** 전체 이미지가 보이도록 표시됩니다. 좌우 자동 반전은 하지 않으므로 플레이어·상대의 시선 방향은 이미지에 반영합니다.

| 파일명 | 용도 |
|---|---|
'''
text+='\n'.join(f'| `{{key}}_{suffix}.png` | {purpose} |' for suffix,purpose in overlays)
text+='''

반응 우선순위는 HP 피해 → BRK 증가 → STA 감소 → 회복입니다. 기본 연출에서 행동 약 0.15초, 판정 결과 약 2.05초, 자원 반응 약 2.85초, 상태 반응 약 3.8초 순으로 나타나며, 다음 버튼은 약 5.2초 뒤 활성화됩니다. 빠른 진행은 이 애니메이션 대기를 생략합니다.

## 일반 스킬 사진 35장

모두 **1:1, 권장 1024×1024, 투명 배경 PNG**입니다. 선택한 스킬 설명 옆의 사진과 그 턴 행동 연출에 함께 사용합니다. 스킬 사진을 켰을 때 기본 `action_attack/defend/evade` 이미지 대신 해당 스킬 사진을 사용하며, 이후 결과·피격·상태 연출은 계속 표시됩니다. 사진 등록 전에는 설정의 **스킬 사진**을 꺼 두세요.

| 파일명 | 스킬 / 사진에 표현할 동작 |
|---|---|
'''
text+='\n'.join(f'| `{{key}}_skill_{id}.png` | {d.name} |' for id,d in public.items())
text+='''

## 개발자 테스트 스킬 사진 17장 · 선택 사항

모두 **1:1, 권장 1024×1024, 투명 배경 PNG**입니다. 테스트 덱의 사진 연출을 확인할 때만 필요합니다.

| 파일명 | 스킬 |
|---|---|
'''
text+='\n'.join(f'| `{{key}}_skill_{id}.png` | {d.name} |' for id,d in developer.items())
text+='\n'
(ROOT/'ASSETS.md').write_text(text,encoding='utf-8')
print('Asset manifest: 38 character + 35 public skill + 17 developer skill names')
