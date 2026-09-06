"""Contracts for easy-enemy content, blind skill selection and reproducible comparison."""

import math
import random
import unittest
from unittest.mock import Mock

from battle_sim import Action, BattleEngine, OwnedSkill, TurnIntent, choose_strategy_action
from easy_enemy_profiles import EASY_ENEMY_PROFILES
from easy_enemy_skills import (
    POWER_STRIKE, RECOVERY_FORM, SAFE_FOOTWORK, CREATE_DISTANCE, TUCK_CHIN,
    load_easy_skill_registry,
)
from easy_enemy_testbed import create_easy_testbed_engine, create_random_player_match
from run_easy_enemy_simulation import simulate_easy_enemies
from skill_selection import choose_skill, skill_target_id


def last_resolution(engine):
    return next(event["resolution"] for event in reversed(engine.trace) if event["event"] == "turn")


def keep_normal(engine):
    for actor in engine.characters:
        actor.hp = actor.max_hp = 10000
        actor.stamina = actor.max_stamina = 10000
        actor.break_gauge = 0
        actor.is_groggy = actor.is_down = actor.is_ko = False


def decision_state(engine):
    return (
        [actor.snapshot() for actor in engine.characters],
        [rng.getstate() for rng in (*engine.policy_rngs, *engine.skill_rngs, engine.rng)],
        [list(history) for history in engine.action_history],
        [list(history) for history in engine.intent_history],
        list(engine.trace), list(engine.last_skill_decisions),
        [dict(counts) for counts in engine.skill_selection_counts],
        engine.match_turn, engine.turn_in_round,
    )


class EasySkillEffectTests(unittest.TestCase):
    def test_five_skills_have_approved_costs_and_no_persistent_delivery(self):
        registry = load_easy_skill_registry()
        self.assertEqual(len(registry), 5)
        for definition in registry.values():
            level = definition.level(1)
            self.assertEqual(level.costs[0].amount, 8)
            self.assertEqual(level.cooldown.turns, 0)
            self.assertIsNone(level.usage_limit.per_match)
            self.assertIsNone(level.usage_limit.per_round)
            self.assertEqual(level.applications[0].delivery.type.value, "immediate")

    def test_effects_on_both_sides_for_every_opponent_action_and_die_result(self):
        # Expected design values, independent of the generated content dictionaries.
        specs = (
            (POWER_STRIKE, Action.ATTACK, "opponent", "hp", -1, 1.2),
            (RECOVERY_FORM, Action.DEFEND, "self", "hp", 1, 1.5),
            (SAFE_FOOTWORK, Action.EVADE, "self", "hp", -1, 0.8),
            (CREATE_DISTANCE, Action.EVADE, "self", "break_gauge", 1, 0.8),
            (TUCK_CHIN, Action.ATTACK, "self", "hp", -1, 0.8),
        )
        for skill, action, target, resource, sign, multiplier in specs:
            for owner in (0, 1):
                for opponent_action in Action:
                    for dice in ((6, 1), (3, 3), (1, 6)):
                        with self.subTest(skill=skill, owner=owner, action=opponent_action, dice=dice):
                            engine = BattleEngine(
                                1, trace_enabled=True, skill_registry=load_easy_skill_registry(),
                                player_skills=(OwnedSkill(skill, 1),) if owner == 0 else (),
                                enemy_skills=(OwnedSkill(skill, 1),) if owner == 1 else (),
                            )
                            for actor in engine.characters:
                                actor.hp = 50
                                actor.break_gauge = 20
                            actors = ("player", "enemy")
                            intents = [TurnIntent(actor, opponent_action) for actor in actors]
                            intents[owner] = TurnIntent(
                                actors[owner], action, skill, skill_target_id(target, actors[owner]),
                            )
                            engine._choose_intent = lambda index: intents[index]
                            engine.rng = Mock(randint=Mock(side_effect=dice))
                            engine.play_turn()
                            resolution = last_resolution(engine)
                            target_index = owner if target == "self" else 1 - owner
                            expected = [dict(resolution[f"base_{actor}_delta"]) for actor in actors]
                            before = expected[target_index][resource]
                            applies = before * sign > 0
                            if applies:
                                expected[target_index][resource] = math.floor(before * multiplier)
                            for index, actor in enumerate(actors):
                                self.assertEqual(resolution[f"applied_{actor}_delta"], expected[index])
                            self.assertEqual(engine.characters[owner].stamina, max(0, min(100, 92 + expected[owner]["stamina"])))
                            self.assertEqual(resolution["effects"][0]["applied"], applies)
                            self.assertFalse(engine.characters[owner].statuses)
                            self.assertFalse(engine.characters[owner].queued_effects)

    def test_new_skills_are_manually_selectable_and_do_not_persist(self):
        registry = load_easy_skill_registry()
        for skill, definition in registry.items():
            with self.subTest(skill=skill):
                engine = create_easy_testbed_engine(18, enemy_strategy="rookie_guard", equipped_skill_ids=(skill,))
                action = Action(definition.level(1).requirements.allowed_actions[0])
                intent = TurnIntent("player", action, skill, skill_target_id(definition.targeting.type.value, "player"))
                self.assertTrue(engine.validate_intent(intent).valid)
                engine.submit_player_intent(intent)
                self.assertEqual(engine.intent_history[0][-1], intent)
                keep_normal(engine)
                engine.submit_player_action(action)
                resolution = last_resolution(engine)
                self.assertEqual(resolution["effects"], [])  # Enemy's second action is a rest slot too.

    def test_effect_conditions_also_work_against_groggy_targets(self):
        for skill, action in ((POWER_STRIKE, Action.ATTACK), (RECOVERY_FORM, Action.DEFEND), (SAFE_FOOTWORK, Action.EVADE)):
            with self.subTest(skill=skill):
                engine = create_easy_testbed_engine(7, enemy_strategy="rookie_cycle", equipped_skill_ids=(skill,))
                engine.player.hp = 50
                engine.enemy.is_groggy = True
                engine.enemy.break_gauge = 100
                definition = engine.skill_registry[skill]
                engine.submit_player_intent(TurnIntent("player", action, skill, skill_target_id(definition.targeting.type.value, "player")))
                resolution = last_resolution(engine)
                self.assertEqual(resolution["kind"], "groggy")
                if skill == POWER_STRIKE:
                    self.assertEqual(resolution["applied_target_delta"]["hp"], -51)
                elif skill == RECOVERY_FORM:
                    self.assertEqual(resolution["applied_actor_delta"]["hp"], 22)
                else:
                    self.assertFalse(resolution["effects"][0]["applied"])
                    self.assertEqual(engine.player.stamina, 92)


class EasySkillSelectionTests(unittest.TestCase):
    def test_fixed_schedules_repeat_across_round_boundary(self):
        schedules = {
            "rookie_cycle": [POWER_STRIKE, None, SAFE_FOOTWORK, None, RECOVERY_FORM, None],
            "reckless_raider": [None, POWER_STRIKE, None, TUCK_CHIN, None, RECOVERY_FORM],
        }
        for enemy, schedule in schedules.items():
            engine = create_random_player_match(12, enemy_strategy=enemy)
            for _ in range(12):
                keep_normal(engine)
                engine.play_turn()
            self.assertEqual([intent.active_skill_id for intent in engine.intent_history[1]], schedule * 2)
            self.assertGreater(engine.round_number, 1)

    def test_guard_maps_only_every_third_action(self):
        engine = create_random_player_match(3, enemy_strategy="rookie_guard")
        enemy_actions = [Action.ATTACK] * 3 + [Action.DEFEND] * 3 + [Action.EVADE] * 3
        original = engine._choose_action
        engine._choose_action = lambda index: enemy_actions[len(engine.action_history[1])] if index == 1 else original(index)
        for _ in enemy_actions:
            keep_normal(engine)
            engine.play_turn()
        self.assertEqual([intent.active_skill_id for intent in engine.intent_history[1]], [None, None, POWER_STRIKE, None, None, RECOVERY_FORM, None, None, CREATE_DISTANCE])
        self.assertEqual(engine.action_history[1], enemy_actions)

    def test_raider_high_break_defends_and_does_not_substitute_or_carry(self):
        engine = create_random_player_match(4, enemy_strategy="reckless_raider")
        engine.action_history[1].append(Action.ATTACK)
        engine.enemy.break_gauge = 80
        engine.play_turn()
        self.assertEqual(engine.intent_history[1][-1], TurnIntent("enemy", Action.DEFEND))
        self.assertEqual(engine.last_skill_decisions[1].planned_skill_id, POWER_STRIKE)
        self.assertIn("action_not_allowed", engine.last_skill_decisions[1].issues)
        keep_normal(engine)
        engine.play_turn()
        self.assertIsNone(engine.intent_history[1][-1].active_skill_id)
        self.assertEqual(len(engine.action_history[1]), 3)

    def test_unavailable_skill_skips_without_delaying_schedule(self):
        for issue, field, value in (("insufficient_resource", "stamina", 0), ("skill_on_cooldown", "skill_cooldowns", 20), ("match_uses_exhausted", "skill_uses_remaining", 0)):
            with self.subTest(issue=issue):
                engine = create_random_player_match(9, enemy_strategy="rookie_cycle")
                if field == "stamina":
                    engine.enemy.stamina = value
                else:
                    getattr(engine.enemy, field)[POWER_STRIKE] = value
                engine.play_turn()
                self.assertIn(issue, engine.last_skill_decisions[1].issues)
                self.assertIsNone(engine.intent_history[1][-1].active_skill_id)
                keep_normal(engine)
                engine.play_turn()
                self.assertIsNone(engine.intent_history[1][-1].active_skill_id)
                keep_normal(engine)
                engine.play_turn()
                self.assertEqual(engine.intent_history[1][-1].active_skill_id, SAFE_FOOTWORK)

    def test_no_missing_skill_substitution(self):
        engine = BattleEngine(1, enemy_strategy="rookie_cycle", enemy_skill_policy="rookie_cycle", skill_registry=load_easy_skill_registry(), enemy_skills=(OwnedSkill(RECOVERY_FORM, 1),))
        engine.play_turn()
        self.assertIn("skill_not_owned", engine.last_skill_decisions[1].issues)
        self.assertIsNone(engine.intent_history[1][-1].active_skill_id)

    def test_skills_do_not_reroll_or_reweight_basic_actions(self):
        for enemy in EASY_ENEMY_PROFILES:
            engine = create_random_player_match(921, enemy_strategy=enemy)
            for index in range(24):
                keep_normal(engine)
                engine.enemy.break_gauge = 80 if index % 5 == 0 else 0
                expected_rng = random.Random()
                expected_rng.setstate(engine.policy_rngs[1].getstate())
                expected = choose_strategy_action(enemy, engine._strategy_context(1), expected_rng)
                engine.play_turn()
                self.assertEqual(engine.intent_history[1][-1].base_action, expected)
                self.assertEqual(engine.policy_rngs[1].getstate(), expected_rng.getstate())

    def test_action_count_pauses_for_down_and_own_groggy_but_not_opponent_groggy(self):
        for state in ("down", "groggy"):
            engine = create_random_player_match(51, enemy_strategy="rookie_cycle")
            if state == "down":
                engine.enemy.is_down = True
                engine.enemy.hp = 0
                engine.enemy.skipped_turns_remaining = 2
            else:
                engine.enemy.is_groggy = True
                engine.enemy.break_gauge = 100
            engine.play_turn()
            self.assertEqual(engine.action_history[1], [])
            self.assertIsNone(engine.last_skill_decisions[1])
        engine = create_random_player_match(52, enemy_strategy="rookie_cycle")
        engine.player.is_groggy = True
        engine.player.break_gauge = 100
        engine.play_turn()
        self.assertEqual(engine.action_history[0], [])
        self.assertEqual(engine.intent_history[1][-1].active_skill_id, POWER_STRIKE)
        self.assertEqual(len(engine.action_history[1]), 1)

    def test_enemy_cannot_read_current_manual_player_choice(self):
        for enemy in EASY_ENEMY_PROFILES:
            observed = []
            for action in Action:
                engine = create_easy_testbed_engine(901, enemy_strategy=enemy, equipped_skill_ids=(POWER_STRIKE,))
                engine.action_history[1].extend([Action.ATTACK, Action.DEFEND])
                skill = POWER_STRIKE if action == Action.ATTACK else None
                engine.submit_player_intent(TurnIntent("player", action, skill, "enemy" if skill else None))
                observed.append((engine.intent_history[1][-1], engine.last_skill_decisions[1]))
            self.assertEqual(observed[0], observed[1])
            self.assertEqual(observed[1], observed[2])

    def test_preview_does_not_change_any_decision_state(self):
        engine = create_random_player_match(187, enemy_strategy="rookie_cycle", trace_enabled=True)
        before = decision_state(engine)
        for index in (0, 1):
            for action in Action:
                first = engine.preview_skill_decision(index, action)
                self.assertEqual(first, engine.preview_skill_decision(index, action))
        self.assertEqual(before, decision_state(engine))
        control = create_random_player_match(187, enemy_strategy="rookie_cycle", trace_enabled=True)
        self.assertEqual(engine.run(), control.run())

    def test_skill_randomness_does_not_shift_action_or_dice_streams(self):
        first = create_random_player_match(741, enemy_strategy="rookie_guard", trace_enabled=True)
        second = create_random_player_match(741, enemy_strategy="rookie_guard", trace_enabled=True)
        for _ in range(20):
            second.skill_rngs[0].random()
        first.play_turn()
        second.play_turn()
        self.assertEqual(first.action_history, second.action_history)
        for key in ("player_die", "enemy_die"):
            self.assertEqual(last_resolution(first)[key], last_resolution(second)[key])
        self.assertEqual(first.rng.getstate(), second.rng.getstate())
        self.assertEqual(first.policy_rngs[0].getstate(), second.policy_rngs[0].getstate())

    def test_scheduled_policies_do_not_consume_skill_randomness(self):
        for enemy in EASY_ENEMY_PROFILES:
            engine = create_random_player_match(401, enemy_strategy=enemy)
            before = engine.skill_rngs[1].getstate()
            engine.run()
            self.assertEqual(before, engine.skill_rngs[1].getstate())

    def test_empty_loadouts_preserve_no_skill_baseline(self):
        for enemy in EASY_ENEMY_PROFILES:
            for seed in (0, 1, 20260903):
                baseline = BattleEngine(seed, enemy_strategy=enemy)
                selected = BattleEngine(seed, enemy_strategy=enemy, player_skill_policy="random", enemy_skill_policy=enemy)
                self.assertEqual(baseline.run(), selected.run())
                self.assertEqual(baseline.rng.getstate(), selected.rng.getstate())
                self.assertEqual(baseline.policy_rngs[1].getstate(), selected.policy_rngs[1].getstate())


class RandomPlayerComparisonTests(unittest.TestCase):
    def test_random_pool_contains_only_legal_skills_plus_no_skill(self):
        rng = Mock()
        rng.choice.return_value = None
        choose_skill("random", action="attack", action_number=1, equipped_skill_ids=(POWER_STRIKE, TUCK_CHIN, RECOVERY_FORM), validate=lambda skill: ("action_not_allowed",) if skill == RECOVERY_FORM else (), rng=rng)
        rng.choice.assert_called_once_with((None, POWER_STRIKE, TUCK_CHIN))

    def test_equal_loadouts_and_valid_intents_for_each_enemy(self):
        for enemy in EASY_ENEMY_PROFILES:
            engine = create_random_player_match(8, enemy_strategy=enemy, trace_enabled=True)
            self.assertEqual(engine.player.skill_loadout, engine.enemy.skill_loadout)
            self.assertEqual(len(engine.player.skill_loadout), 3)
            engine.run()  # commit validates every actual intent.
            self.assertTrue(any(i.active_skill_id for i in engine.intent_history[0]))
            self.assertTrue(any(i.active_skill_id for i in engine.intent_history[1]))

    def test_small_comparison_is_reproducible_and_records_loadouts(self):
        report = simulate_easy_enemies(matches=3, seed=199)
        self.assertEqual(report, simulate_easy_enemies(matches=3, seed=199))
        self.assertEqual(report["total_matches"], 9)
        for case in report["cases"].values():
            self.assertEqual(sum(case["outcomes"].values()), 3)
            self.assertEqual(case["config"]["player_loadout"], case["config"]["enemy_loadout"])

    def test_testbed_rejects_excess_loadout_and_non_easy_enemy(self):
        with self.assertRaises(ValueError):
            create_easy_testbed_engine(1, enemy_strategy="rookie_cycle", equipped_skill_ids=tuple(load_easy_skill_registry()))
        with self.assertRaises(ValueError):
            create_random_player_match(1, enemy_strategy="executor")


if __name__ == "__main__":
    unittest.main()
