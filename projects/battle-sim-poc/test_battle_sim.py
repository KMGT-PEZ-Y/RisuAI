from __future__ import annotations

import random
import unittest

from battle_sim import (
    Action,
    BattleEngine,
    DiceResult,
    GROGGY_TABLE,
    ManualBattleEngine,
    NPC_STRATEGIES_BY_DIFFICULTY,
    PLAYER_TEST_STRATEGIES,
    RESULT_TABLE,
    StatusEffect,
    iter_trace_lines,
    simulate_batch,
    simulate_matchup,
    simulate_strategy_matrix,
    simulate_strategy_grid,
)


class ResultTableTests(unittest.TestCase):
    def test_table_has_all_27_entries(self) -> None:
        self.assertEqual(len(RESULT_TABLE), 27)
        for player_action in Action:
            for enemy_action in Action:
                for dice_result in DiceResult:
                    self.assertIn(
                        (player_action, enemy_action, dice_result), RESULT_TABLE
                    )

    def test_table_is_symmetric(self) -> None:
        inverse = {
            DiceResult.WIN: DiceResult.LOSE,
            DiceResult.DRAW: DiceResult.DRAW,
            DiceResult.LOSE: DiceResult.WIN,
        }
        for (player_action, enemy_action, result), entry in RESULT_TABLE.items():
            mirror = RESULT_TABLE[
                (enemy_action, player_action, inverse[result])
            ]
            self.assertEqual(entry.player, mirror.enemy)
            self.assertEqual(entry.enemy, mirror.player)

    def test_groggy_table_values(self) -> None:
        self.assertEqual(GROGGY_TABLE[Action.ATTACK].enemy.hp, -42)
        self.assertEqual(GROGGY_TABLE[Action.DEFEND].player.break_gauge, -24)
        self.assertEqual(GROGGY_TABLE[Action.EVADE].enemy.break_gauge, 27)

    def test_failed_evade_against_defend_has_symmetric_risk(self) -> None:
        defend_win = RESULT_TABLE[(Action.DEFEND, Action.EVADE, DiceResult.WIN)]
        evade_lose = RESULT_TABLE[(Action.EVADE, Action.DEFEND, DiceResult.LOSE)]

        self.assertEqual(defend_win.enemy.hp, -12)
        self.assertEqual(defend_win.enemy.break_gauge, 10)
        self.assertEqual(evade_lose.player, defend_win.enemy)
        self.assertEqual(evade_lose.enemy, defend_win.player)


class StateTransitionTests(unittest.TestCase):
    def test_waiting_character_heals_four_percent_and_down_character_wakes(self) -> None:
        engine = BattleEngine(1)
        engine.player.hp = 0
        engine.player.down_count = 1
        engine.player.is_down = True
        engine.player.skipped_turns_remaining = 1
        engine.enemy.hp = 50

        engine.play_turn()

        self.assertEqual(engine.enemy.hp, 54)
        self.assertFalse(engine.player.is_down)
        self.assertEqual(engine.player.hp, 50)

    def test_last_wait_turn_then_interval_stacks_recovery(self) -> None:
        engine = BattleEngine(2)
        engine.turn_in_round = 7
        engine.match_turn = 7
        engine.player.hp = 0
        engine.player.break_gauge = 100
        engine.player.down_count = 2
        engine.player.is_down = True
        engine.player.is_groggy = True
        engine.player.skipped_turns_remaining = 2
        engine.enemy.hp = 50

        engine.play_turn()

        self.assertEqual(engine.player.hp, 83)
        self.assertEqual(engine.player.break_gauge, 25)
        self.assertEqual(engine.enemy.hp, 87)  # wait +4, interval +33
        self.assertEqual(engine.round_number, 2)

    def test_status_starts_decreasing_next_turn(self) -> None:
        engine = BattleEngine(3)
        engine.match_turn = 3
        status = StatusEffect("confusion", 3, applied_on_match_turn=3)
        engine.player.statuses.append(status)

        engine._tick_active_statuses()
        self.assertEqual(status.remaining_turns, 3)
        engine.match_turn = 4
        engine._tick_active_statuses()
        self.assertEqual(status.remaining_turns, 2)

    def test_status_decreases_during_down_wait(self) -> None:
        engine = BattleEngine(4)
        engine.player.hp = 0
        engine.player.down_count = 1
        engine.player.is_down = True
        engine.player.skipped_turns_remaining = 1
        engine.player.statuses.append(StatusEffect("confusion", 3, 0))

        engine.play_turn()

        self.assertEqual(engine.player.statuses[0].remaining_turns, 2)

    def test_groggy_target_break_does_not_drop(self) -> None:
        engine = BattleEngine(5, player_strategy="cycle")
        # The cycle's second action is DEFEND, whose groggy target delta is zero.
        engine.action_history[0].append(Action.ATTACK)
        engine.enemy.break_gauge = 100
        engine.enemy.is_groggy = True
        engine.player.hp = 50
        engine.player.break_gauge = 50

        engine.play_turn()

        self.assertEqual(engine.enemy.break_gauge, 100)
        self.assertEqual(engine.player.hp, 65)
        self.assertEqual(engine.player.break_gauge, 26)

    def test_same_seed_is_reproducible(self) -> None:
        first = BattleEngine(12345).run()
        second = BattleEngine(12345).run()
        self.assertEqual(first.outcome, second.outcome)
        self.assertEqual(first.turns, second.turns)
        self.assertEqual(first.final_player.snapshot(), second.final_player.snapshot())
        self.assertEqual(first.final_enemy.snapshot(), second.final_enemy.snapshot())

    def test_trace_is_rendered_as_korean_turn_explanation(self) -> None:
        result = BattleEngine(12345, trace_enabled=True).run()
        rendered = "\n".join(iter_trace_lines(result))
        self.assertIn("단일 경기 상세 해설", rendered)
        self.assertIn("플레이어는", rendered)
        self.assertIn("판정", rendered)
        self.assertIn("경기 종료", rendered)


class BatchTests(unittest.TestCase):
    def test_small_batch_returns_expected_counts(self) -> None:
        summary = simulate_batch(20, seed=99)
        self.assertEqual(sum(summary["outcomes"].values()), 20)
        self.assertEqual(summary["config"]["matches"], 20)

    def test_fixed_strategies_are_injected_on_both_sides(self) -> None:
        engine = BattleEngine(
            100,
            player_strategy="attack",
            enemy_strategy="evade",
        )
        engine.play_turn()
        self.assertEqual(engine.action_history[0], [Action.ATTACK])
        self.assertEqual(engine.action_history[1], [Action.EVADE])

    def test_matchup_reports_five_round_pacing(self) -> None:
        summary = simulate_matchup(
            20,
            seed=101,
            player_strategy="pressure",
            enemy_strategy="defensive",
        )
        self.assertEqual(summary["config"]["player_strategy"], "pressure")
        self.assertIn("within_5_rounds_percent", summary["turns"])
        self.assertIn("mean", summary["rounds"])

    def test_strategy_matrix_contains_every_ordered_pair(self) -> None:
        matrix = simulate_strategy_matrix(
            ["random", "attack", "adaptive"],
            matches_per_matchup=5,
            seed=102,
        )
        self.assertEqual(len(matrix["matchups"]), 9)
        for matchup in matrix["matchups"]:
            self.assertEqual(sum(matchup["outcomes"].values()), 5)

    def test_guard_ratio_strategies_never_collapse_to_defend_only(self) -> None:
        engine = BattleEngine(
            103,
            player_strategy="guard_evade_ratio",
            enemy_strategy="guard_attack_ratio",
        )
        for _ in range(100):
            player_action = engine._choose_action(0)
            enemy_action = engine._choose_action(1)
            self.assertIn(player_action, (Action.DEFEND, Action.EVADE))
            self.assertIn(enemy_action, (Action.DEFEND, Action.ATTACK))
            engine.action_history[0].append(player_action)
            engine.action_history[1].append(enemy_action)
        self.assertIn(Action.EVADE, engine.action_history[0])
        self.assertIn(Action.ATTACK, engine.action_history[1])

    def test_guard_adaptive_strategies_keep_their_action_pools(self) -> None:
        engine = BattleEngine(
            104,
            player_strategy="guard_evade_adaptive",
            enemy_strategy="guard_attack_adaptive",
        )
        engine.action_history[0].extend([Action.ATTACK] * 6)
        engine.action_history[1].extend([Action.EVADE] * 6)
        for _ in range(30):
            self.assertIn(
                engine._choose_action(0),
                (Action.DEFEND, Action.EVADE),
            )
            self.assertIn(
                engine._choose_action(1),
                (Action.DEFEND, Action.ATTACK),
            )

    def test_npc_roster_has_three_policies_per_difficulty(self) -> None:
        self.assertEqual(len(PLAYER_TEST_STRATEGIES), 8)
        self.assertEqual(set(NPC_STRATEGIES_BY_DIFFICULTY), {
            "easy", "normal", "hard", "very_hard"
        })
        for strategies in NPC_STRATEGIES_BY_DIFFICULTY.values():
            self.assertEqual(len(strategies), 3)

    def test_rectangular_strategy_grid_contains_every_case(self) -> None:
        enemies = [
            strategy
            for strategies in NPC_STRATEGIES_BY_DIFFICULTY.values()
            for strategy in strategies
        ]
        grid = simulate_strategy_grid(
            PLAYER_TEST_STRATEGIES[:2],
            enemies[:3],
            matches_per_matchup=2,
            seed=105,
        )
        self.assertEqual(len(grid["matchups"]), 6)
        self.assertIn("p95_turns", grid["matchups"][0])


class ManualPlaytestTests(unittest.TestCase):
    def test_manual_player_action_is_recorded(self) -> None:
        engine = ManualBattleEngine(200, enemy_strategy="rookie_cycle")
        engine.submit_player_action(Action.EVADE)
        self.assertEqual(engine.action_history[0], [Action.EVADE])
        self.assertEqual(len(engine.action_history[1]), 1)
        self.assertEqual(engine.match_turn, 1)

    def test_manual_engine_advances_player_groggy_turn(self) -> None:
        engine = ManualBattleEngine(201, enemy_strategy="attack")
        engine.player.is_groggy = True
        engine.player.break_gauge = 100
        self.assertFalse(engine.player_can_choose)
        engine.advance_forced_turn()
        self.assertEqual(engine.match_turn, 1)
        self.assertEqual(engine.action_history[0], [])
        self.assertEqual(engine.action_history[1], [Action.ATTACK])

    def test_manual_engine_rejects_missing_player_choice(self) -> None:
        engine = ManualBattleEngine(202, enemy_strategy="random")
        with self.assertRaises(RuntimeError):
            engine.advance_forced_turn()


if __name__ == "__main__":
    unittest.main()
