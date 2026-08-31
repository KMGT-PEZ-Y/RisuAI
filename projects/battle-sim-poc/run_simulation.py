"""Command line runner for the no-skill random battle test bed."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from battle_sim import (
    NPC_STRATEGIES_BY_DIFFICULTY,
    PLAYER_TEST_STRATEGIES,
    STRATEGY_NAMES,
    BattleEngine,
    iter_trace_lines,
    simulate_matchup,
    simulate_strategy_grid,
    simulate_strategy_matrix,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the round/turn battle POC simulation."
    )
    parser.add_argument("--matches", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=20260825)
    parser.add_argument("--max-rounds", type=int, default=100)
    parser.add_argument(
        "--player-strategy",
        choices=STRATEGY_NAMES,
        default="random",
    )
    parser.add_argument(
        "--enemy-strategy",
        choices=STRATEGY_NAMES,
        default="random",
    )
    parser.add_argument(
        "--matrix",
        action="store_true",
        help="Run every ordered pairing in --strategies.",
    )
    parser.add_argument(
        "--npc-roster",
        action="store_true",
        help="Run the standard 8 player policies against all 12 NPC policies.",
    )
    parser.add_argument(
        "--strategies",
        default=",".join(STRATEGY_NAMES),
        help="Comma-separated strategy names used by --matrix.",
    )
    parser.add_argument(
        "--json",
        type=Path,
        help="Optional path for the aggregate JSON report.",
    )
    parser.add_argument(
        "--trace-seed",
        type=int,
        help="Run one detailed match with this exact seed instead of a batch.",
    )
    return parser


def print_summary(summary: dict) -> None:
    config = summary["config"]
    turns = summary["turns"]
    means = summary["per_match_means"]
    print(
        f"matches={config['matches']:,} seed={config['seed']} "
        f"max_rounds={config['max_rounds']} "
        f"player={config['player_strategy']} enemy={config['enemy_strategy']}"
    )
    print(f"outcomes={summary['outcomes']}")
    print(f"rates(%)={summary['rates_percent']}")
    print(
        "turns: "
        f"mean={turns['mean']:.4f}, median={turns['median']:.4f}, "
        f"p25={turns['p25']:.4f}, p75={turns['p75']:.4f}, "
        f"p90={turns['p90']:.4f}, p95={turns['p95']:.4f}, "
        f"min={turns['min']}, max={turns['max']}"
    )
    print(
        f"within_5_rounds={turns['within_5_rounds_percent']:.4f}% "
        f"over_10_rounds={turns['over_10_rounds_percent']:.4f}%"
    )
    print(
        "rounds: "
        f"mean={summary['rounds']['mean']:.4f}, "
        f"median={summary['rounds']['median']:.4f}, "
        f"p95={summary['rounds']['p95']:.4f}"
    )
    print(f"per-match means={means}")


def print_matrix(matrix: dict) -> None:
    config = matrix["config"]
    strategies = config["strategies"]
    by_pair = {
        (row["player_strategy"], row["enemy_strategy"]): row
        for row in matrix["matchups"]
    }
    print(
        f"strategy matrix: matches_per_matchup={config['matches_per_matchup']:,} "
        f"seed={config['seed']}"
    )
    print("player win rate (%)")
    print("player\\enemy\t" + "\t".join(strategies))
    for player in strategies:
        values = [
            f"{by_pair[(player, enemy)]['rates_percent'].get('PLAYER_WIN', 0):.2f}"
            for enemy in strategies
        ]
        print(player + "\t" + "\t".join(values))
    print("mean turns")
    print("player\\enemy\t" + "\t".join(strategies))
    for player in strategies:
        values = [
            f"{by_pair[(player, enemy)]['mean_turns']:.2f}"
            for enemy in strategies
        ]
        print(player + "\t" + "\t".join(values))


def print_grid(grid: dict) -> None:
    config = grid["config"]
    players = config["player_strategies"]
    enemies = config["enemy_strategies"]
    by_pair = {
        (row["player_strategy"], row["enemy_strategy"]): row
        for row in grid["matchups"]
    }
    print(
        f"strategy grid: matches_per_matchup={config['matches_per_matchup']:,} "
        f"seed={config['seed']}"
    )
    print("player win rate (%)")
    print("player\\enemy\t" + "\t".join(enemies))
    for player in players:
        print(
            player
            + "\t"
            + "\t".join(
                f"{by_pair[(player, enemy)]['rates_percent'].get('PLAYER_WIN', 0):.2f}"
                for enemy in enemies
            )
        )
    print("mean turns")
    print("player\\enemy\t" + "\t".join(enemies))
    for player in players:
        print(
            player
            + "\t"
            + "\t".join(
                f"{by_pair[(player, enemy)]['mean_turns']:.2f}"
                for enemy in enemies
            )
        )


def main() -> None:
    args = build_parser().parse_args()
    if args.trace_seed is not None:
        result = BattleEngine(
            args.trace_seed,
            max_rounds=args.max_rounds,
            trace_enabled=True,
            player_strategy=args.player_strategy,
            enemy_strategy=args.enemy_strategy,
        ).run()
        print("\n".join(iter_trace_lines(result)))
        return

    if args.npc_roster:
        npc_strategies = [
            strategy
            for strategies in NPC_STRATEGIES_BY_DIFFICULTY.values()
            for strategy in strategies
        ]
        summary = simulate_strategy_grid(
            PLAYER_TEST_STRATEGIES,
            npc_strategies,
            matches_per_matchup=args.matches,
            seed=args.seed,
            max_rounds=args.max_rounds,
        )
        print_grid(summary)
    elif args.matrix:
        strategies = [
            value.strip() for value in args.strategies.split(",") if value.strip()
        ]
        summary = simulate_strategy_matrix(
            strategies,
            matches_per_matchup=args.matches,
            seed=args.seed,
            max_rounds=args.max_rounds,
        )
        print_matrix(summary)
    else:
        summary = simulate_matchup(
            args.matches,
            seed=args.seed,
            max_rounds=args.max_rounds,
            player_strategy=args.player_strategy,
            enemy_strategy=args.enemy_strategy,
        )
        print_summary(summary)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"json={args.json.resolve()}")


if __name__ == "__main__":
    main()
