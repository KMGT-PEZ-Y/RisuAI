"""Reproducible 3-enemy experiment; Player always has the opponent's exact loadout."""

import argparse
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
import random

from battle_sim import _summarize_results
from easy_enemy_profiles import EASY_ENEMY_PROFILES
from easy_enemy_skills import EASY_ENEMY_SKILLS, load_easy_skill_registry
from easy_enemy_testbed import create_random_player_match, enemy_loadout


def simulate_easy_enemies(matches=1000, seed=20260903, max_rounds=100):
    if matches < 1 or max_rounds < 1:
        raise ValueError("matches and max_rounds must be positive")
    seed_rng = random.Random(seed)
    match_seeds = tuple(seed_rng.getrandbits(64) for _ in range(matches))
    registry = load_easy_skill_registry()
    cases = {}
    for enemy in EASY_ENEMY_PROFILES:
        results = []
        uses = {"player": Counter(), "enemy": Counter()}
        reasons = {"player": Counter(), "enemy": Counter()}
        for match_seed in match_seeds:
            engine = create_random_player_match(
                match_seed, enemy_strategy=enemy, max_rounds=max_rounds, registry=registry,
            )
            results.append(engine.run())
            for index, actor in enumerate(("player", "enemy")):
                uses[actor].update(
                    intent.active_skill_id for intent in engine.intent_history[index]
                    if intent.active_skill_id is not None
                )
                reasons[actor].update(engine.skill_selection_counts[index])
        summary = _summarize_results(
            results, matches=matches, seed=seed, max_rounds=max_rounds,
            player_strategy="random", enemy_strategy=enemy,
        )
        loadout = [asdict(owned) for owned in enemy_loadout(enemy)]
        summary["config"].update(
            player_skill_policy="random", enemy_skill_policy=enemy,
            player_loadout=loadout, enemy_loadout=loadout,
            enemy_profile=asdict(EASY_ENEMY_PROFILES[enemy]),
        )
        summary["skill_uses"] = {actor: dict(counts) for actor, counts in uses.items()}
        summary["skill_selection_counts"] = {actor: dict(counts) for actor, counts in reasons.items()}
        summary["skill_uses_per_match"] = {
            actor: round(sum(counts.values()) / matches, 4) for actor, counts in uses.items()
        }
        cases[enemy] = summary
    return {
        "schema_version": 1,
        "seed": seed,
        "match_seed_generation": "random.Random(seed).getrandbits(64); same sequence for all enemies",
        "matches_per_enemy": matches,
        "total_matches": matches * len(cases),
        "random_player_rule": "uniform action; uniform choice among no skill and currently legal equipped skills",
        "skill_data": EASY_ENEMY_SKILLS,
        "cases": cases,
    }


def markdown_report(report):
    lines = [
        "# 쉬움 적 스킬 운용 실험",
        "",
        f"시드 `{report['seed']}`, 적별 {report['matches_per_enemy']:,}경기, 총 {report['total_matches']:,}경기.",
        "Player와 Enemy는 동일한 3개 스킬을 1레벨로 장착한다. 양측 HP/STA/BRK 기준 최대값은 100이다.",
        "Player는 공격·방어·회피를 각각 1/3로 선택한 뒤, 그 행동에서 사용 가능한 스킬과 미사용 중 균등 선택한다.",
        "사용 가능한 스킬이 1개면 시전 확률은 1/2, 2개면 2/3이다. 비용 부족·행동 제한은 지키며 효용 판단은 하지 않는다.",
        "적은 합의한 일정만 따른다. 행동·스킬·주사위 난수는 분리된다. 100라운드 안전 한도를 적용한다.",
        "",
        "| Enemy | Player 승 | Enemy 승 | 더블 KO | 교착 | 평균 턴 | P95 턴 | Player 스킬/경기 | Enemy 스킬/경기 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for enemy, case in report["cases"].items():
        rates = case["rates_percent"]
        lines.append(
            f"| {enemy} | {rates.get('PLAYER_WIN', 0):.1f}% | {rates.get('ENEMY_WIN', 0):.1f}% | "
            f"{rates.get('DOUBLE_KO', 0):.1f}% | {rates.get('STALEMATE', 0):.1f}% | "
            f"{case['turns']['mean']:.2f} | {case['turns']['p95']:g} | "
            f"{case['skill_uses_per_match']['player']:.2f} | {case['skill_uses_per_match']['enemy']:.2f} |"
        )
    lines.extend([
        "", "## 스킬별 사용 횟수", "",
        "| Enemy | 스킬 | Player | Enemy |", "|---|---|---:|---:|",
    ])
    registry = load_easy_skill_registry()
    for enemy, case in report["cases"].items():
        for owned in enemy_loadout(enemy):
            skill = owned.skill_id
            lines.append(f"| {enemy} | {registry[skill].name} | {case['skill_uses']['player'].get(skill, 0)} | {case['skill_uses']['enemy'].get(skill, 0)} |")
    lines.extend([
        "", "## 해석 범위", "",
        "이 결과는 같은 스킬 구성에서 랜덤 운용과 예정된 운용을 비교한 수치다. 패턴을 배우는 사람의 난이도나 재미를 증명하지 않는다.",
        "양측 기본 행동 정책도 다르므로 승률은 기본 행동과 스킬 운용을 합친 결과이며, 선택기만의 효과를 분리한 실험이 아니다.",
        "적마다 비교에 사용하는 스킬 구성이 다르므로 적 사이 승률 차이를 순수한 선택 AI 성능 차이로 해석하지 않는다.",
        "1,000경기에서 승률 50% 부근의 95% 표본 오차는 대략 ±3.1%p다.",
        "무스킬 과거 기준선과는 대전 조건이 다르다. 새 스킬의 성장·최적 수치는 아직 검증하지 않았다.", "",
    ])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matches", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20260903)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = simulate_easy_enemies(args.matches, args.seed)
    rendered = markdown_report(report)
    print(rendered)
    for path, content in (
        (args.json, json.dumps(report, ensure_ascii=False, indent=2)),
        (args.report, rendered),
    ):
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
