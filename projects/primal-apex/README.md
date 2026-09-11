# Primal Apex 모듈 0.1.0

네 개의 독립 Lua 기반 RisuAI 모듈입니다. 같은 채팅의 상태를 공유하고, 현재 화면에 해당하는 모듈 하나만 UI를 표시합니다. **허브 배포본에는 기존 BattleSim이 포함되어 있어 실제 경기와 결과 회수까지 가능합니다.**

## 설치와 시작

`release`의 다음 네 파일을 RisuAI 모듈로 가져와 같은 캐릭터 또는 채팅에서 모두 활성화하세요.

| 파일 | 기능 |
|---|---|
| [Primal-Apex-Hub.risum](release/Primal-Apex-Hub.risum) | 허브, 시간 이동, 최종 정비, 입장 묘사, BattleSim 경기, 결과 저장 |
| [Primal-Apex-Matchmaking.risum](release/Primal-Apex-Matchmaking.risum) | 관계·대전 계기 기반 상대 선정, 일정 고정, 3경기 고정 컵 |
| [Primal-Apex-Story.risum](release/Primal-Apex-Story.risum) | 장소·NPC 선택, LLM 상호작용, 종료 패킷 정산 |
| [Primal-Apex-Training.risum](release/Primal-Apex-Training.risum) | 스킬 습득·강화, 자원 차감 |

1. 네 모듈을 활성화하고 캐릭터의 채팅을 엽니다. 첫 화면에는 허브만 표시됩니다.
2. 패널이 없으면 `/apex` 또는 `/hub`를 입력합니다.
3. 매치메이킹·트레이닝·스토리를 누르면 해당 화면만 나타납니다. 돌아가기 버튼으로 허브에 복귀합니다.
4. 매치메이킹에서 대진을 확정하고 스토리나 트레이닝을 진행합니다.
5. 시간 이동에서 `3 16:30` 같은 일차·시각을 입력하거나 다음 경기까지 이동합니다.
6. 경기 시각에는 경기 시작만 가능합니다. 정비 확정 → 입장 묘사 → 경기 개시 → 결과 확인 → 허브 복귀 순서로 진행합니다.
7. 경기 후 스토리에서 상대와 상호작용하거나 장면을 건너뛴 뒤 다음 경기를 준비합니다.

허브와 스토리 모듈은 버튼에서 RisuAI의 현재 모델을 호출하므로 LLM 접근 설정(`lowLevelAccess`)을 사용합니다. 모듈에서 호출 권한을 끄면 장면 생성이 실패할 수 있습니다. 모델이 없거나 요청이 실패해도 기존 상태는 유지됩니다. 입장 묘사는 생략해 전투할 수 있고, 스토리는 일반 채팅으로 이어가거나 보상 없이 종료할 수 있습니다.

BattleSim은 허브 안에 포함되어 있으므로 기존 독립 BattleSim 트리거와 중복 활성화하지 마세요. 기존 BattleSim 카드의 내장 트리거가 있는 경우 해당 트리거를 비활성화하거나 일반 캐릭터/새 테스트 캐릭터에서 이 네 모듈을 사용하세요. 네 모듈은 활성화 순서와 무관하게 동작합니다.

업데이트할 때는 기존 네 모듈을 교체하세요. 같은 모듈을 중복 가져와 동시에 활성화하지 마세요. 모듈 ID가 가져오기 과정에서 변경되어도 공유 저장 키는 유지됩니다. 이전 BattleSim 단독 저장을 캠페인으로 자동 가져오지는 않습니다.

## 이번 구현의 기본 콘텐츠

- 1일차 09:00, 강화 자원 3으로 시작합니다.
- 기본 스킬 3개와 `measured_strike` Lv.1을 보유·장착합니다.
- 지도는 체육관, 카페, 아레나이며 테스트 인물은 기존 BattleSim의 훈련생, 베테랑 가드, 적응형 전사입니다. 실제 Primal Apex 인물 설정을 자동 추출한 것이 아닙니다.
- 훈련은 `measured_strike`, `growth_focus`, `banked_pressure`의 실제 BattleSim Lv.1~3 정의를 사용합니다. 기존 BattleSim에서 개발용으로 분류했던 성장 스킬을 캠페인 성장 검증용으로 공개했습니다.
- 신규 습득은 자원 2, 강화는 현재 레벨 +1만큼 소비합니다. 기존 1레벨 스킬에는 가짜 강화 레벨을 만들지 않습니다.
- 경기 완료 시 자원 2, 스토리의 `TRAINING_SMALL`은 자원 1을 지급합니다.
- 자유 대전은 확정 시점에서 1일 뒤로 잡습니다. 경기 완료에 게임 시간 60분을 반영합니다.
- 고정 컵은 첫 대진 전에 선택할 수 있습니다. 세 상대를 2일 간격으로 모두 만나는 시나리오형 컵입니다. 승패에 따른 탈락식 토너먼트 브래킷은 이번 범위에 포함하지 않습니다.
- 관계는 affinity/respect 두 축이며 변화는 -1, 0, +1, 값의 범위는 -100~100입니다.
- 기본 스토리는 SFW입니다. 사용자가 선택적 성인 장면을 명시적으로 켜면 경기 후 친밀 상호작용을 선택할 수 있습니다. 일반 지도 상호작용은 계속 SFW입니다.

이 값들은 밸런스 확정값이 아니라 연결 프로토타입의 초기 설정입니다.

## 스토리 사용

장소의 NPC 아래에서 대화, 작은 퀘스트, 대전 이야기를 선택하면 장면 요청을 만들어 현재 모델로 첫 장면을 생성합니다. 이후 일반 채팅 입력으로 자유롭게 반응합니다.

자연스러운 장면 종료, `서사 마무리 · LLM` 버튼, `/story end` 명령으로 정산합니다. 대화 중에는 실제 캘린더가 변하지 않으며, 종료 패킷에 적힌 시각만 반영합니다. 종료 시각은 시작 이전이거나 다음 경기 이후일 수 없습니다.

```text
<PA_SUMMARY>상호작용의 짧은 요약</PA_SUMMARY>
<STORY_END|scene=scene_1|end_day=1|end_time=10:30|affinity=UP_SMALL|respect=NONE|reward=TRAINING_SMALL|lead=CHALLENGE>
```

- 관계: `NONE`, `UP_SMALL`, `DOWN_SMALL`
- 보상: `NONE`, `TRAINING_SMALL`
- 대전 계기: `NONE`, `CHALLENGE`, `REMATCH_OFFER`; 대전 이야기 또는 경기 후 대화에서는 `REMATCH_PROMISE`도 허용
- `scene`은 현재 장면과 일치해야 합니다. 한 응답에 종료 패킷은 하나만 허용합니다.
- 필드 누락·중복·알 수 없는 키워드·시간 범위 오류가 있으면 정산하지 않습니다.
- 요약과 기계 패킷은 화면에서 숨깁니다. 요약은 최근 8개까지만 저장합니다.
- 동일 장면의 결과는 한 번만 적용합니다. 모델 재생성으로 보상을 중복 적용하지 않습니다.

종료 패킷이 없거나 잘못되면 재요청하거나 일반 대화로 정정을 요청하세요. 보상 없이 종료하면 시간과 보상을 변경하지 않고 허브로 돌아갑니다.

## 공유 상태와 확장

정확한 계약은 [MODULE_CONTRACT.md](MODULE_CONTRACT.md)에 있습니다. 초기 설계는 [구현 명세](PRIMAL_APEX_IMPLEMENTATION_SPEC.md)를 참고하세요.

실행 중 모듈들은 Lua 전역 변수를 공유하지 않습니다. 모두 `getState/setState`의 동일 키 `primal_apex_state_v1`을 사용합니다. `screen` 값이 표시할 UI를 결정하며, 버튼에는 처리 모듈과 revision이 들어 있습니다.

독립 스크립트는 서로의 함수를 호출할 수 없으므로 허브의 저장 함수 호출 대신 **동일한 작은 공유 헬퍼를 각 배포본에 포함**합니다. 헬퍼의 원본은 `src/shared.lua` 하나입니다. 별도의 다섯 번째 모듈을 설치할 필요가 없습니다.

| 수정 대상 | 소스 |
|---|---|
| 상태 기본값, 공통 버튼·저장·시간 함수 | `src/shared.lua` |
| NPC 프로필·AI·장소·기본 상대 덱 | `src/data.lua` |
| 허브, 캘린더, 경기 진입과 결과 처리 | `src/hub.lua` |
| 후보 가중치, 일정, 컵 | `src/matchmaking.lua` |
| 훈련 비용·습득 대상 | `src/training.lua` |
| 서사 프롬프트·패킷·결과 키워드 | `src/story.lua` |
| 모듈별 훅 연결과 공통 입력 검증 | `src/runtime.lua` |
| 최소 UI 스타일 | `src/style.css` |

`generated`는 빌드 결과입니다. 직접 수정하지 마세요. 공유 계약이나 데이터 정의를 바꾸면 네 모듈을 함께 빌드·교체합니다.

## BattleSim 참조 범위

빌드는 `../battle-sim-lua/BattleSim-RisuAI.charx`의 `module.risum`에서 Lua를 읽어 허브에 포함합니다. 원본 BattleSim 폴더나 카드를 변경하지 않습니다. 참조한 Lua의 SHA-256은 `release/manifest.json`에 기록합니다.

- 기존 판정표, 자원, 스킬, 다운·그로기·인터벌, 기존 AI와 NG+, 전투 UI와 연출을 사용합니다.
- 원본 저장 API는 캠페인의 `session.battle`과 `session.config`로 연결합니다. `battle_sim_state_v1` 등 단독 저장 키에는 쓰지 않습니다.
- 원본 훅은 로컬 범위로 격리합니다. 호스트에는 허브 훅만 등록됩니다.
- 자유로운 상대·덱·레벨 편집 화면은 캠페인 정비로 대체합니다. 상대 설정은 일정의 NPC에서 가져오며, 플레이어는 보유 스킬만 장착합니다.
- 기존 100라운드 교착 판정 등 원본 룰은 보존합니다.
- 초상화·스킬 이미지 경로는 원본의 `{{raw::...}}` 규칙입니다. 참조 카드에 선수 사진이 포함되어 있지 않아 사진은 이 산출물에도 포함하지 않았습니다. 에셋 없는 환경에서도 수치와 버튼으로 경기할 수 있습니다. 실제 이미지 등록은 기존 BattleSim의 `ASSETS.md`를 참고하세요.

## 빌드와 검증

Python 표준 라이브러리만으로 패키징합니다.

```powershell
python build.py
```

Lua/WASM 검증에는 기존 BattleSim 프로젝트의 Wasmoon 1.16.0과 공식 JSON 파일을 사용합니다.

```powershell
node tests/qa.mjs
```

브라우저 검증에는 Playwright, Edge와 같은 저장소의 Markdown/DOMPurify 테스트 파일을 사용합니다.

```powershell
$env:PA_BROWSER='1'
node tests/qa.mjs
```

검증 결과와 한계는 [VALIDATION.md](VALIDATION.md)에 기록합니다. 실제 설치본이나 사용자 채팅은 변경하지 않습니다.

호스트 계약은 [RisuAI 공식 Lua 실행기](https://github.com/kwaroran/RisuAI/blob/main/src/ts/process/scriptings.ts), [트리거 실행기](https://github.com/kwaroran/RisuAI/blob/main/src/ts/process/triggers.ts), [모듈 포맷](https://github.com/kwaroran/RisuAI/blob/main/src/ts/process/modules.ts)을 확인했습니다.
