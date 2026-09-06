# 폴더 정리 기록 · 2026-09-05

기존 루트의 파일 47개를 역할별 하위 폴더로 이동했습니다. 루트에는 `README.md`와 `.gitignore`를 두고, 기존 실험 결과는 `results/`에 유지했습니다. 경로는 이 문서의 위치가 아닌 **battle-sim-poc 프로젝트 루트 기준**입니다.

| 분류 | 위치 | 이동한 파일 수 |
|---|---|---:|
| 엔진·AI·스킬 데이터·테스트베드·UI | `src/` | 17 |
| 자동 테스트 | `tests/` | 9 |
| 통계 실험·NG+ 검증 | `experiments/` | 5 |
| 규칙·스킬·진행·결과 문서 | `docs/` | 9 |
| Windows 실행 파일 | `scripts/` | 7 |

이후 공통 덱 데이터 `src/concept_decks.py`, 테스트 경로 설정 `tests/__init__.py`, 자동 테스트 실행 파일 `scripts/test.cmd`, 4종 UI 검사 `experiments/qa_testbed_ui.py` 및 이 문서를 추가했습니다.

## 실행 방법

탐색기에서 `scripts/play_ng_plus.cmd`를 더블클릭하면 기존 NG+ / M/U/H 테스트베드가 열립니다. 쉬움 적·Phase C-D·무스킬 UI는 같은 폴더의 다른 `play_*.cmd`를 사용합니다.

아래 명령은 저장소 루트에서 실행합니다.

```powershell
# 자동 테스트
.\projects\battle-sim-poc\scripts\test.cmd

# 기본 통계 실험
.\projects\battle-sim-poc\scripts\run.cmd --matches 1000 --seed 20260825

# 쉬움 적 실험
python -X utf8 projects/battle-sim-poc/experiments/run_easy_enemy_simulation.py --matches 1000 --json projects/battle-sim-poc/results/easy_enemies_1000.json --report projects/battle-sim-poc/docs/EASY_ENEMY_PLAYTEST_RESULTS.md

# NG+ 컨셉 13종: 덱별 100경기
python -X utf8 projects/battle-sim-poc/experiments/run_ng_concept_simulation.py --matches 100 --workers 2 --output projects/battle-sim-poc/results/ng_concepts_after_reorganization

# 숨긴 Tk 창으로 4종 UI 검증
python -X utf8 projects/battle-sim-poc/experiments/qa_testbed_ui.py
```

Python이 설치되어 있지 않은 환경에서는 기존처럼 Codex 번들 Python을 우선 찾는 `.cmd` 파일을 사용합니다. 직접 Python을 호출할 경우 실행 환경에 맞는 Python 경로를 지정하면 됩니다.

unittest를 직접 실행할 때는 프로젝트를 최상위 경로로 지정합니다.

```powershell
python -m unittest discover -s projects/battle-sim-poc/tests -t projects/battle-sim-poc -p "test_*.py" -v
```

## 경로 보정

- 실험 스크립트는 자신의 위치에서 `../src`를 찾습니다. 현재 작업 폴더에 의존하지 않습니다. Windows 자식 프로세스에서도 같은 경로 설정이 실행됩니다.
- 테스트는 `tests` 패키지로 발견되며 테스트 사이의 보조 함수 참조도 패키지 상대 참조로 수정했습니다.
- `.cmd` / `.ps1`은 `../src` 또는 `../experiments`의 실제 진입점을 실행합니다. `.cmd`는 실행 오류 코드도 정확히 반환합니다.
- 공유 컨셉 덱은 `src/concept_decks.py`에서 가져옵니다. Lua 데이터 추출이 통계 실행 스크립트에 의존하지 않도록 분리했습니다.
- NG+ 기본 출력은 이동 전과 같은 프로젝트의 `results/ng_concepts_13000`입니다. 소스 검증은 `src`의 엔진·스킬·공유 덱과 `experiments`의 실행 스크립트를 모두 확인합니다.
- 실험에 명시적으로 지정하는 상대 출력 경로는 기존처럼 실행한 작업 폴더 기준입니다.
- Lua 쪽 `export_data.py`와 `qa.py`도 새 `src` 경로를 사용합니다. CHARX 재빌드 검사는 별도 결과 파일로 수행했습니다.
- NG+ 보고서의 최대 라운드 표기도 명령행 설정을 반영하도록 보정했습니다.

기존 결과·보고서는 이동 또는 보존했으며 결과 수치를 다시 계산해 덮어쓰지 않았습니다. 소스 지문 검증을 유지하므로 **정리 전 코드로 만든 중간 저장은 새 코드에서 이어 실행되지 않습니다**. 새 실험은 새로운 `--output` 폴더를 지정하세요. 정리 후 생성한 중간 저장은 다른 작업 폴더에서도 정상 재개되는 것을 확인했습니다.

## 검증 결과

| 검사 | 결과 |
|---|---|
| 이동 전·후 자동 테스트 | 각각 **149개 통과** |
| 외부 작업 폴더에서 `scripts/test.cmd` | **149개 통과** |
| 기본 `run.cmd` | 3경기 실행 및 JSON 생성. 프로젝트 밖 작업 폴더에서 확인 |
| `run.ps1` | 프로젝트 밖에서 1경기 실행 |
| 쉬움 적 실험 | 적 3종 × 2경기 = **6경기**, JSON·Markdown 생성 |
| NG+ 다중 프로세스 | 컨셉 13종 × 1경기, 2개 작업 프로세스, 공백이 들어간 출력 경로에서 **13/13 완료** |
| NG+ 재개 | 다른 작업 폴더에서 같은 설정으로 재실행. **13/13 기록 재사용**, 중복 경기 없음 |
| 기본·C-D·쉬움 적 UI | Tk 초기화·새 경기·턴 진행·화면 갱신 통과 |
| NG+ UI | 사용자 덱, 비동기 턴/판단 로그, 취소, 빈 장착, 판단 충실도 0, 기존 수동 AI 통과 |
| Lua 연동 빌드 | 35+17종 데이터 추출·단일 Lua 조립·CHARX 내장 소스 일치 검사 통과 |
| Lua 비교 검증 | **158경기 / 5,335턴** 일치, 별도 조건 검사 포함 58개 스킬 레벨 및 NG+ 공통 시나리오 비교 통과 |

작은 실험은 실행 경로·파일 생성·프로세스 시작·재개 동작 확인용입니다. NG+ 검사는 시간을 제한하기 위해 최대 1라운드로 실행했으므로 기존 1,300경기의 밸런스 결과를 대체하지 않습니다. 검사 결과 파일은 `results/reorganization_smoke/`에 있습니다.

Tk 검사는 제한된 실행 환경에서 초기화되지 않아 확장 권한으로 실행했으며, 창을 숨긴 상태로 동작을 확인했습니다. 사용자 RisuAI 앱이나 저장된 채팅을 변경하지 않았습니다.
