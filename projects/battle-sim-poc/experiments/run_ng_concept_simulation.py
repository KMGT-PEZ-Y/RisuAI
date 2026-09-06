"""Checkpointed comparison of 13 NG+ concept decks against a full-random player."""
from __future__ import annotations

from pathlib import Path as _Path
import sys as _sys

_sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "src"))

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import random
from statistics import mean, median
import time

from battle_sim import BattleEngine, OwnedSkill, percentile
from easy_enemy_skills import (
    EASY_ENEMY_SKILLS, POWER_STRIKE, RECOVERY_FORM, SAFE_FOOTWORK,
    load_easy_skill_registry,
)
from muh_skills import MUH_SKILLS, load_muh_skill_registry
from ng_plus_ai import DEFAULT_CONFIG


from concept_decks import DECKS

PLAYER_SKILLS = (POWER_STRIKE, RECOVERY_FORM, SAFE_FOOTWORK)
REGISTRY = {**load_easy_skill_registry(), **load_muh_skill_registry()}
OUTCOMES = ("PLAYER_WIN", "ENEMY_WIN", "DOUBLE_KO", "STALEMATE")


class ExperimentEngine(BattleEngine):
    """Keep player actions uniform even when NG+ forbids or forces an action."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.decision_ms = []
        self.search_transitions = 0
        self.search_depths = Counter()

    def _choose_action(self, actor_index):
        if actor_index == 0:
            return self.policy_rngs[0].choice(self.legal_actions(0, upcoming_turn=False))
        return super()._choose_action(actor_index)

    def record_ng_decision(self, actor_index, decision):
        super().record_ng_decision(actor_index, decision)
        self.decision_ms.append(decision.elapsed_ms)
        self.search_transitions += decision.transitions
        self.search_depths[decision.depth_completed] += 1


def play_one(task):
    deck, index, seed, max_rounds = task
    started = time.perf_counter()
    engine = ExperimentEngine(
        seed, max_rounds=max_rounds, skill_registry=REGISTRY,
        player_strategy="random", player_skill_policy="random",
        player_skills=[OwnedSkill(code, 1) for code in PLAYER_SKILLS],
        enemy_strategy="ng_plus", ng_judgment=1.0,
        enemy_skills=[OwnedSkill(code, 1) for code in DECKS[deck][1].split()],
    )
    result = engine.run()
    assert result.outcome in OUTCOMES
    return {
        "deck": deck, "index": index, "seed": seed,
        "outcome": result.outcome, "turns": result.turns, "rounds": result.rounds,
        "metrics": {key: dict(value) if isinstance(value, Counter) else value
                    for key, value in vars(result.metrics).items()},
        "skill_uses": {
            side: dict(Counter(intent.active_skill_id for intent in engine.intent_history[i]
                               if intent.active_skill_id is not None))
            for i, side in enumerate(("player", "enemy"))
        },
        "actions": {
            side: dict(Counter(intent.base_action.value for intent in engine.intent_history[i]))
            for i, side in enumerate(("player", "enemy"))
        },
        "player_skill_selection": dict(engine.skill_selection_counts[0]),
        "ng_decisions": len(engine.decision_ms),
        "ng_decision_ms_sum": sum(engine.decision_ms),
        "ng_decision_ms_max": max(engine.decision_ms, default=0),
        "ng_transitions": engine.search_transitions,
        "ng_depths": dict(engine.search_depths),
        "elapsed_seconds": time.perf_counter() - started,
    }


def wilson(wins, total):
    z = 1.959963984540054
    p = wins / total
    denominator = 1 + z*z/total
    center = (p + z*z/(2*total)) / denominator
    margin = z * math.sqrt(p*(1-p)/total + z*z/(4*total*total)) / denominator
    return [round(100*(center-margin), 3), round(100*(center+margin), 3)]


def summarize(rows):
    n = len(rows)
    outcomes = Counter(row["outcome"] for row in rows)
    turns = sorted(row["turns"] for row in rows)
    rounds = sorted(row["rounds"] for row in rows)
    uses, actions, used_matches = {}, {}, {}
    for side in ("player", "enemy"):
        uses[side], actions[side], used_matches[side] = Counter(), Counter(), Counter()
        for row in rows:
            uses[side].update(row["skill_uses"][side])
            actions[side].update(row["actions"][side])
            used_matches[side].update(row["skill_uses"][side].keys())
    return {
        "matches": n,
        "outcomes": {key: outcomes[key] for key in OUTCOMES},
        "rates_percent": {key: outcomes[key] * 100/n for key in OUTCOMES},
        "enemy_win_wilson_95_percent": wilson(outcomes["ENEMY_WIN"], n),
        "turns": {"mean": mean(turns), "median": median(turns),
                  "p95": percentile(turns, .95), "max": max(turns)},
        "rounds": {"mean": mean(rounds), "median": median(rounds),
                   "p95": percentile(rounds, .95)},
        "within_5_rounds_percent": sum(x <= 5 for x in rounds)*100/n,
        "over_10_rounds_percent": sum(x > 10 for x in rounds)*100/n,
        "skill_uses": uses,
        "skill_used_matches": used_matches,
        "skill_uses_per_match": {side: sum(uses[side].values())/n for side in uses},
        "actions": actions,
        "downs_per_match": {
            side: sum(row["metrics"]["down_events"][i] for row in rows)/n
            for i, side in enumerate(("player", "enemy"))},
        "ng_decisions": sum(row["ng_decisions"] for row in rows),
        "ng_transitions": sum(row["ng_transitions"] for row in rows),
    }


def render_report(report):
    config = report["config"]
    lines = ["# NG+ 컨셉 덱 13종 대전 실험", "",
             f"완료 시각(UTC): {report['completed_at']}", "",
             f"덱별 {config['matches']:,}경기, 총 {report['overall']['matches']:,}경기. 마스터 시드 {config['seed']}.",
             "Enemy: 제안한 5스킬 덱, 모두 Lv.1, NG+ 판단 충실도 1.0. 탐색 기본값 D3/K4/B2/F4, 예산 6,552 유지.",
             "Player: 힘주어 치기·자세 정비·안전한 발놀림 Lv.1. 가능한 기본 행동을 균등 선택한 뒤, 합법 스킬과 미사용을 균등 선택.",
             "행동 제한이 없으면 공격·방어·회피 각 1/3. 해당 행동의 기본 스킬이 사용 가능하면 사용/미사용 각 1/2. 강제·금지 행동은 준수.",
             f"모든 덱에 같은 경기 시드 목록을 적용. 행동·스킬·전투 난수 분리. 최대 {config['max_rounds']}라운드. 경기 길이 통계는 교착 포함 전체 경기 기준.", "",
             "| 순위 | NG+ 덱 | NG+ 승 | Player 승 | 더블 KO | 교착 | 평균 턴 | 중앙 턴 | P95 턴 | 평균 라운드 |",
             "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    ordered = sorted(report["cases"], key=lambda k: -report["cases"][k]["outcomes"]["ENEMY_WIN"])
    for deck in ordered:
        case = report["cases"][deck]
        rank = 1 + sum(report["cases"][other]["outcomes"]["ENEMY_WIN"] > case["outcomes"]["ENEMY_WIN"] for other in ordered)
        rates = case["rates_percent"]
        lines.append(f"| {rank} | {DECKS[deck][0]} | {rates['ENEMY_WIN']:.1f}% | {rates['PLAYER_WIN']:.1f}% | {case['outcomes']['DOUBLE_KO']} | {case['outcomes']['STALEMATE']} | {case['turns']['mean']:.2f} | {case['turns']['median']:g} | {case['turns']['p95']:g} | {case['rounds']['mean']:.2f} |")
    lines += ["", "## 장착과 운용 통계", "",
              "| 덱 | Enemy 장착 | Player 스킬/경기 | NG+ 스킬/경기 | 5라운드 이내 | 10라운드 초과 | NG+ 승률 95% 구간 |",
              "|---|---|---:|---:|---:|---:|---|"]
    for deck in ordered:
        c = report["cases"][deck]
        lo, hi = c["enemy_win_wilson_95_percent"]
        lines.append(f"| {DECKS[deck][0]} | {DECKS[deck][1].upper()} | {c['skill_uses_per_match']['player']:.2f} | {c['skill_uses_per_match']['enemy']:.2f} | {c['within_5_rounds_percent']:.1f}% | {c['over_10_rounds_percent']:.1f}% | {lo:.1f}–{hi:.1f}% |")
    lines += ["", "## NG+ 스킬별 사용", "", "| 덱 | 스킬 | 총 사용 | 경기당 사용 | 사용한 경기 |", "|---|---|---:|---:|---:|"]
    for deck in DECKS:
        c = report["cases"][deck]
        for code in DECKS[deck][1].split():
            uses = c["skill_uses"]["enemy"].get(code, 0)
            lines.append(f"| {DECKS[deck][0]} | {code.upper()} {REGISTRY[code].name} | {uses} | {uses/c['matches']:.3f} | {c['skill_used_matches']['enemy'].get(code, 0)} |")
    lines += ["", "## 해석 범위", "",
              "고정된 기본 3종 랜덤 상대에 대한 덱 운용 성능이다. 사람 상대 난이도, 덱 상호 대전 순위, AI만의 기여도를 분리한 검증이 아니다.",
              "판단 충실도 1.0에서도 기존 AI의 softmax 선택은 유지된다. 완전 최적 선택이나 모든 연계의 사용을 보장하지 않는다.",
              f"덱별 {config['matches']:,}경기에서 승률 50% 부근의 95% 표본 오차는 정규근사로 약 ±{98/math.sqrt(config['matches']):.1f}%p. 작은 순위 차이를 확정적 우열로 해석하지 않는다. 표의 개별 구간은 Wilson 방식이다.",
              "병렬 실행으로 측정된 판단 시간은 시스템 부하 영향을 받으므로 단일 UI 응답 시간과 비교하지 않는다.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matches", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20260905)
    parser.add_argument("--max-rounds", type=int, default=100)
    parser.add_argument("--workers", type=int, default=max(1, min(10, (os.cpu_count() or 2)-2)))
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "results/ng_concepts_13000")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if min(args.matches, args.max_rounds, args.workers) < 1:
        parser.error("matches, max-rounds and workers must be positive")
    args.output.mkdir(parents=True, exist_ok=True)
    seed_rng = random.Random(args.seed)
    seeds = [seed_rng.getrandbits(64) for _ in range(args.matches)]
    source = Path(__file__).resolve().parents[1] / "src"
    source_files = {name: source / name for name in (
        "battle_sim.py", "ng_plus_ai.py", "skill_schema.py", "skill_selection.py",
        "easy_enemy_skills.py", "muh_skills.py", "concept_decks.py")}
    source_files[Path(__file__).name] = Path(__file__).resolve()
    hashes = {name: hashlib.sha256(path.read_bytes()).hexdigest()
              for name, path in source_files.items()}
    config = dict(matches=args.matches, seed=args.seed, max_rounds=args.max_rounds,
                  match_seeds=seeds, decks=DECKS, player_skills=PLAYER_SKILLS,
                  skill_level=1, ng_judgment=1.0, search=asdict(DEFAULT_CONFIG), source_sha256=hashes,
                  random_rule="uniform legal actions, then uniform legal skills plus no skill")
    config = json.loads(json.dumps(config))
    metadata = args.output / "config.json"
    if metadata.exists():
        if json.loads(metadata.read_text(encoding="utf-8")) != config:
            raise ValueError("Checkpoint configuration/source mismatch; use a new output directory")
    else:
        metadata.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        (args.output / "skill_data.json").write_text(json.dumps(
            dict(player=EASY_ENEMY_SKILLS, enemy=MUH_SKILLS), ensure_ascii=False, indent=2), encoding="utf-8")
    journal = args.output / "matches.jsonl"
    rows = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()] if journal.exists() else []
    done = {(row["deck"], row["index"]) for row in rows}
    if len(done) != len(rows):
        raise ValueError("Duplicate checkpoint records")
    tasks = [(deck, i, seed, args.max_rounds) for i, seed in enumerate(seeds) for deck in DECKS if (deck, i) not in done]
    total, initial = len(DECKS)*args.matches, len(rows)
    started = last_log = time.monotonic()
    print(f"START {initial}/{total}, workers={args.workers}, unchanged NG+ depth=3 judgment=1.0", flush=True)
    with journal.open("a", encoding="utf-8") as output, ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(play_one, task) for task in tasks]
        for future in as_completed(futures):
            row = future.result()
            rows.append(row)
            output.write(json.dumps(row, ensure_ascii=False) + "\n")
            output.flush()
            now = time.monotonic()
            if now-last_log >= 25 or len(rows) == total:
                speed = (len(rows)-initial)/(now-started)
                progress = dict(completed=len(rows), total=total, elapsed_seconds=now-started,
                                matches_per_second=speed, remaining_seconds=(total-len(rows))/speed,
                                per_deck=dict(Counter(r["deck"] for r in rows)))
                (args.output / "progress.json").write_text(json.dumps(progress, indent=2), encoding="utf-8")
                print(f"PROGRESS {len(rows)}/{total} elapsed={(now-started)/60:.1f}m remaining~{progress['remaining_seconds']/60:.1f}m", flush=True)
                last_log = now
    assert len(rows) == total
    for deck in DECKS:
        subset = [r for r in rows if r["deck"] == deck]
        assert sorted(r["index"] for r in subset) == list(range(args.matches))
        assert all(r["seed"] == seeds[r["index"]] for r in subset)
    report = dict(config=config, completed_at=datetime.now(timezone.utc).isoformat(),
                  overall=summarize(rows), cases={deck: summarize([r for r in rows if r["deck"] == deck]) for deck in DECKS})
    (args.output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    rendered = render_report(report)
    (args.report or args.output / "REPORT.md").write_text(rendered, encoding="utf-8")
    print(rendered.split("## 장착과 운용 통계")[0], flush=True)


if __name__ == "__main__":
    main()
