"""Deterministic contracts for the 30-skill catalog and interactions."""
import itertools
import math
import copy
import unittest
from unittest.mock import Mock

from battle_sim import Action, InvalidTurnIntent, ManualBattleEngine, OwnedSkill, TurnIntent
from muh_skills import MUH_SKILLS, load_muh_skill_registry
from skill_schema import load_skill_definitions, validate_skill_data


class Duel(ManualBattleEngine):
    def _choose_intent(self, index):
        if index == 1 and getattr(self, "enemy_intent", None) is not None:
            return self.enemy_intent
        return super()._choose_intent(index)


def battle(player=(), enemy=()):
    return Duel(42, enemy_strategy="attack", skill_registry=load_muh_skill_registry(),
                player_skills=[OwnedSkill(code, 1) for code in player],
                enemy_skills=[OwnedSkill(code, 1) for code in enemy])


def turn(b, code=None, action="attack", enemy_code=None, enemy_action="attack", dice=(6, 1)):
    b.enemy_intent = TurnIntent("enemy", Action(enemy_action), enemy_code)
    b.rng = Mock()
    b.rng.randint.side_effect = dice
    b.submit_player_intent(TurnIntent("player", Action(action), code))
    return next(event["resolution"] for event in reversed(b.trace) if event["event"] == "turn")


def prepare(b, code, owner=0):
    # Use the actual declaration/storage path to initialize conditional fixtures.
    from battle_sim import EffectResolutionContext
    definition = b.skill_registry[code]
    intent = TurnIntent("player" if owner == 0 else "enemy", Action(definition.level(1).requirements.allowed_actions[0]), code)
    context = EffectResolutionContext((intent,), [Action.DEFEND, Action.DEFEND])
    for application in definition.level(1).applications:
        if application.delivery.status is not None:
            b._store_status(context, application.timing, owner, owner, intent, application)


class CatalogTests(unittest.TestCase):
    def test_new_schema_fields_reject_invalid_types(self):
        raw = copy.deepcopy(MUH_SKILLS[3])
        raw["levels"][0]["applications"][1]["delivery"]["status"]["active_timing"] = "unknown"
        self.assertTrue(validate_skill_data(raw))
        raw = copy.deepcopy(MUH_SKILLS[3])
        raw["levels"][0]["applications"][1]["effects"][0]["value"] = -5
        self.assertTrue(validate_skill_data(raw))

    def test_manual_enemy_invalid_input_does_not_mutate_player_or_rng(self):
        from muh_testbed import create_muh_testbed_engine
        b = create_muh_testbed_engine(12, equipped_skill_ids=["m01"], enemy_skill_ids=["h10"])
        before, rng = b.player.snapshot(), b.rng.getstate()
        with self.assertRaises(InvalidTurnIntent):
            b.submit_test_turn(TurnIntent("player", Action.ATTACK, "m01"), TurnIntent("enemy", Action.ATTACK, "h10"))
        self.assertEqual(b.player.snapshot(), before)
        self.assertEqual(b.match_turn, 0)
        self.assertEqual(b.rng.getstate(), rng)

    def test_random_enemy_and_player_complete_mixed_deck_games(self):
        from battle_sim import BattleEngine
        decks = (("m01","m02","m05","m06","u03"), ("h04","h05","h06","m02","u03"),
                 ("m09","u07","u06","m01","u03"), ("h08","u02","m08","m03","m01"),
                 ("u01","m10","u10","h10","m03"), ("h09","h03","h02","m01","u07"))
        registry = load_muh_skill_registry()
        for seed, (player, enemy) in enumerate(itertools.product(decks, repeat=2)):
            b = BattleEngine(seed, trace_enabled=False, max_rounds=20, skill_registry=registry,
                             player_skills=[OwnedSkill(code,1) for code in player],
                             enemy_skills=[OwnedSkill(code,1) for code in enemy],
                             player_skill_policy="random", enemy_skill_policy="random")
            result = b.run()
            self.assertIsNotNone(result.outcome)
            for actor in b.characters:
                self.assertGreaterEqual(actor.stamina, 0)
                self.assertTrue(all(value is None or value >= 0 for value in actor.skill_uses_remaining.values()))

    def test_exact_catalog_costs_cooldowns_limits(self):
        expected = {
            "m": [(12,2,5),(12,3,4),(16,4,3),(6,4,3),(10,4,3),(14,3,3),(12,4,3),(10,3,4),(14,5,3),(16,4,3)],
            "u": [(18,3,4),(18,4,3),(22,5,2),(8,5,3),(12,4,3),(20,4,3),(18,5,3),(18,5,2),(16,4,3),(26,6,2)],
            "h": [(22,4,3),(24,5,2),(28,8,1),(8,7,2),(14,6,2),(30,8,2),(26,6,2),(26,7,2),(30,8,1),(34,8,1)],
        }
        registry = load_muh_skill_registry()
        self.assertEqual(len(registry), 30)
        for prefix, rows in expected.items():
            for number, expected_values in enumerate(rows, 1):
                level = registry[f"{prefix}{number:02d}"].level(1)
                self.assertEqual((level.costs[0].amount, level.cooldown.turns, level.usage_limit.per_match), expected_values)

    def test_all_thirty_can_commit_for_either_actor(self):
        for code in load_muh_skill_registry():
            for owner in range(2):
                with self.subTest(code=code, owner=owner):
                    b = battle([code] if owner == 0 else [], [code] if owner == 1 else [])
                    actor, opponent = b.characters[owner], b.characters[1-owner]
                    if code in {"m03", "u03", "h03", "h09"}: actor.hp = 30
                    if code == "h03": actor.down_count = 1
                    if code in {"m10", "u10", "h10"}: opponent.break_gauge = 70
                    if code == "h10": opponent.hp = 30
                    if code in {"m07", "u07", "h07"}: prepare(b, "m05", 1-owner)
                    if code == "h06": prepare(b, "h05", owner)
                    a = b.skill_registry[code].level(1).requirements.allowed_actions[0]
                    other = "attack" if code in {"m02", "u02"} else "defend"
                    rolls = (1,6) if code == "m02" else (6,1)
                    r = turn(b, code if owner == 0 else None, a if owner == 0 else other,
                             code if owner == 1 else None, a if owner == 1 else other,
                             dice=rolls if owner == 0 else rolls[::-1])
                    self.assertEqual(actor.skill_uses_remaining[code], b.skill_registry[code].level(1).usage_limit.per_match - 1)
                    self.assertTrue(any(e.get("skill_id") == code and e.get("applied") for e in r["effects"]))

    def test_loadout_contracts(self):
        for ids in (("m01","m02","m03","m04","m05","m06"), ("m09","u08"), ("h06","h09"), ("h08","h09")):
            with self.subTest(ids=ids), self.assertRaises(ValueError): battle(ids)
        battle(("m01","m02","m03","m04","h09"))

    def test_cost_failure_is_atomic(self):
        b = battle(["h09"])
        b.player.hp = 30
        b.player.stamina = 29
        before = b.player.snapshot()
        with self.assertRaises(InvalidTurnIntent): turn(b, "h09")
        self.assertEqual(b.player.snapshot(), before)

    def test_start_conditions_do_not_use_post_cost_values(self):
        b = battle(["h10"])
        b.player.stamina = 40
        b.enemy.hp, b.enemy.break_gauge = 30, 70
        r = turn(b, "h10", enemy_action="defend", dice=(1,6))
        self.assertEqual(b.player.skill_uses_remaining["h10"], 0)
        # Enemy recovers 12 through defense and then loses a guaranteed 12.
        self.assertEqual(b.enemy.hp, 30)
        self.assertTrue(any(e.get("application_id") == "execute" and e.get("applied") for e in r["effects"]))


class ImmediateTests(unittest.TestCase):
    def test_additive_damage_and_break_over_all_basic_results(self):
        for code, hp_bonus, brk_bonus in (("m01",6,0),("m06",5,0),("m10",0,10),("u06",7,0),("u10",10,12),("h01",12,0)):
            for enemy_action, dice in itertools.product(("attack","defend","evade"), ((6,1),(3,3),(1,6))):
                with self.subTest(code=code, action=enemy_action, dice=dice):
                    b = battle([code]); b.enemy.break_gauge = 65
                    r = turn(b, code, enemy_action=enemy_action, dice=dice)
                    base, actual = r["base_enemy_delta"], r["applied_enemy_delta"]
                    self.assertEqual(actual["hp"], base["hp"] - (hp_bonus if base["hp"] < 0 else 0))
                    self.assertEqual(actual["break_gauge"], base["break_gauge"] + (brk_bonus if base["break_gauge"] > 0 else 0))

    def test_guard_pressure_only_rewards_actual_defense_hit(self):
        for enemy_action in ("attack", "defend", "evade"):
            b = battle(["u01"])
            r = turn(b, "u01", enemy_action=enemy_action)
            extra = 8 if enemy_action == "defend" else 0
            self.assertEqual(r["applied_enemy_delta"]["hp"], r["base_enemy_delta"]["hp"] - extra)

    def test_guard_and_risk_multipliers(self):
        for code, action, multiplier in (("m02","defend",.7),("u02","defend",.75),("h02","defend",.5),("h01","attack",1.2),("h05","attack",1.2)):
            b = battle([code])
            r = turn(b, code, action, dice=(1,6))
            self.assertEqual(r["applied_player_delta"]["hp"], math.floor(r["base_player_delta"]["hp"] * multiplier))

    def test_recoveries_and_no_resurrection(self):
        for code, hp, brk in (("m03",10,8),("u03",14,0),("h03",22,15)):
            b = battle([code]); b.player.hp = 30; b.player.break_gauge = 40; b.player.down_count = 1
            turn(b, code, "defend")
            self.assertEqual(b.player.hp, 30 + 12 + hp)
            self.assertEqual(b.player.break_gauge, 40 - 18 - brk)
            b = battle([code]); b.player.hp = 1; b.player.down_count = 1
            turn(b, code, "defend", dice=(1,6))
            self.assertTrue(b.player.is_down)
            self.assertEqual(b.player.hp, 0)

    def test_counter_dice_and_self_damage_tradeoff(self):
        b = battle(["u02"])
        turn(b, "u02", "defend")
        self.assertEqual(b.enemy.hp, 92)
        for code, action, minimum in (("m08","evade",3),("u09","attack",4),("h09","attack",6)):
            b = battle([code]); b.player.hp = 40
            r = turn(b, code, action, dice=(1,2))
            self.assertEqual(r["player_final_die"], minimum)
            if code == "u09":
                self.assertEqual(r["applied_enemy_delta"]["hp"], math.floor(r["base_enemy_delta"]["hp"]*.8))

    def test_finisher_does_not_add_break_after_hp_zero_or_double_count_down(self):
        b = battle(["h10"]); b.enemy.hp = 1; b.enemy.break_gauge = 70; b.enemy.down_count = 2
        r = turn(b, "h10")
        self.assertEqual(b.outcome, "PLAYER_WIN")
        self.assertEqual(b.enemy.down_count, 3)
        self.assertFalse(any(e.get("application_id") == "execute" and e.get("applied") for e in r["effects"]))


class ComboTests(unittest.TestCase):
    def test_disruption_accepts_new_preparation_tags_without_id_list(self):
        b = battle(["m07"])
        prepare(b, "m05", 1)
        b.enemy.statuses[0].name = "future_preparation"
        self.assertTrue(b.validate_intent(TurnIntent("player", Action.ATTACK, "m07")).valid)
        turn(b, "m07", enemy_action="defend")
        self.assertFalse(b.enemy.statuses)

    def test_unused_discount_expires_and_groups_do_not_stack(self):
        b = battle(["m04","u04","m01"])
        prepare(b, "m04"); prepare(b, "u04")
        self.assertEqual(len(b.player.statuses), 1)
        self.assertEqual(b._effective_skill_cost(b.player, "m01", "stamina", 12), 8)
        turn(b, action="defend", enemy_action="defend")
        self.assertFalse(b.player.statuses)
        self.assertEqual(b._effective_skill_cost(b.player, "m01", "stamina", 12), 12)

    def test_two_turn_combos_exact_damage_and_dice(self):
        for preparation, finish, damage, minimum in (("m05","m06",16,1),("u05","u06",17,4),("h05","h06",22,4)):
            b = battle([preparation, finish])
            turn(b, preparation, "defend", enemy_action="defend")
            r = turn(b, finish, dice=(1,1))
            self.assertGreaterEqual(r["player_final_die"], minimum)
            self.assertEqual(r["applied_enemy_delta"]["hp"], r["base_enemy_delta"]["hp"]-damage)
            self.assertFalse(any("preparation" in status.tags for status in b.player.statuses))

    def test_discount_no_preparation_discount_and_minimum_cost(self):
        b = battle(["m04","m05","m01"])
        turn(b, "m04", "evade", enemy_action="defend")
        self.assertEqual(b._effective_skill_cost(b.player, "m05", "stamina", 10), 10)
        self.assertEqual(b._effective_skill_cost(b.player, "m01", "stamina", 12), 8)
        before = b.player.stamina
        turn(b, "m01")
        self.assertEqual(b.player.stamina, before - 8 - 7)
        self.assertFalse(b.player.statuses)

    def test_u04_cooldown_reduction_and_finisher_protection(self):
        b = battle(["u04","u06"])
        turn(b, "u04", "evade", enemy_action="defend")
        turn(b, "u06")
        self.assertEqual(b.player.skill_cooldowns["u06"], 3)
        b = battle(["u04","h09"])
        turn(b, "u04", "evade", enemy_action="defend")
        b.player.hp = 40
        turn(b, "h09")
        self.assertEqual(b.player.skill_cooldowns["h09"], 8)

    def test_three_turn_combo_discount_extension(self):
        b = battle(["h04","h05","h06"])
        turn(b, "h04", "defend", enemy_action="defend")
        turn(b, "h05", "defend", enemy_action="defend")
        self.assertEqual(b._effective_skill_cost(b.player, "h06", "stamina", 30), 18)
        r = turn(b, "h06")
        self.assertEqual(r["applied_enemy_delta"]["hp"], -50)
        self.assertFalse(any("preparation" in s.tags for s in b.player.statuses))
        self.assertEqual([s.name for s in b.player.statuses], ["h06_recovery"])

    def test_preparations_replace_and_expire_on_wait_not_interval(self):
        b = battle(["m05","u05"])
        prepare(b, "m05"); prepare(b, "u05")
        self.assertEqual([s.name for s in b.player.statuses], ["u05_ready"])
        b = battle(["m05","m06"]); b.turn_in_round = 7
        turn(b, "m05", "defend", enemy_action="defend")
        self.assertEqual(b.player.statuses[0].remaining_turns, 1)
        b.enemy.is_down = True; b.enemy.skipped_turns_remaining = 2
        b.advance_forced_turn()
        self.assertFalse(b.player.statuses)

    def test_disruption_removes_only_latest_preparation_and_stamina(self):
        for code, drain in (("m07",0),("u07",6),("h07",12)):
            b = battle([code], ["h04","h05"])
            prepare(b, "h04", 1)
            # The new damage preparation is stored before result-end disruption.
            r = turn(b, code, enemy_code="h05", enemy_action="defend", dice=(1,6))
            self.assertEqual(b.enemy.stamina, min(100, 100-14+22)-drain)
            self.assertFalse(any(s.name == "h05_ready" for s in b.enemy.statuses))
            self.assertTrue(any(e.get("category") == "status_control" and e.get("applied") for e in r["effects"]))


class ControlTests(unittest.TestCase):
    def test_dice_debuff_next_turn_only_and_failure_spends_charge(self):
        b = battle(["m09"])
        r = turn(b, "m09", dice=(6,5))
        self.assertEqual(r["enemy_final_die"], 5)
        r = turn(b, dice=(6,6))
        self.assertEqual(r["enemy_final_die"], 4)
        self.assertFalse(b.enemy.statuses)
        b = battle(["m09"])
        turn(b, "m09", dice=(1,6))
        self.assertFalse(b.enemy.statuses)
        self.assertEqual(b.player.skill_uses_remaining["m09"], 2)

    def test_restriction_is_validated_before_any_cost(self):
        b = battle(["u08"])
        turn(b, "u08")
        self.assertNotIn(Action.EVADE, b.legal_actions(1))
        self.assertFalse(b.validate_intent(TurnIntent("enemy", Action.EVADE)).valid)
        b = battle(["h02"])
        turn(b, "h02", "defend")
        self.assertNotIn(Action.ATTACK, b.legal_actions(0))
        with self.assertRaises(InvalidTurnIntent): turn(b)
        turn(b, action="evade", enemy_action="defend")
        self.assertIn(Action.ATTACK, b.legal_actions(0))

    def test_taunt_applies_to_enemy_policy_and_player_validation(self):
        b = battle(["h08"])
        turn(b, "h08", "defend")
        b.enemy_intent = None
        self.assertEqual(b.legal_actions(1), (Action.ATTACK,))
        self.assertEqual(b._choose_intent(1).base_action, Action.ATTACK)
        b = battle([], ["h08"])
        turn(b, action="defend", enemy_code="h08", enemy_action="defend")
        self.assertEqual(b.legal_actions(0), (Action.ATTACK,))
        # Taunt wins a simultaneous conflict with the actor's guard recovery.
        b = battle(["h02"], ["h08"])
        turn(b, "h02", "defend", enemy_code="h08", enemy_action="defend")
        self.assertEqual(b.legal_actions(0), (Action.ATTACK,))
        r = turn(b, action="attack", enemy_action="defend")
        self.assertEqual(r["player_action"], "attack")

    def test_skill_seal_and_unremovable_penalties(self):
        b = battle(["h05","h06","u03"])
        prepare(b, "h05")
        turn(b, "h06")
        b.player.hp = 40
        result = b.validate_intent(TurnIntent("player", Action.DEFEND, "u03"))
        self.assertIn("skills_sealed", [e.code for e in result.issues])
        self.assertTrue(b.validate_intent(TurnIntent("player", Action.DEFEND)).valid)
        turn(b, action="defend")
        self.assertFalse(b.player.statuses)
        b = battle(["h09","u03"]); b.player.hp = 40
        turn(b, "h09")
        b.player.hp = 40
        r = turn(b, "u03", "defend", dice=(1,6))
        self.assertEqual(r["applied_player_delta"]["hp"], -35)
        self.assertEqual(b.player.hp, 19)

    def test_cooldown_counts_full_future_turns_and_usage_never_refills(self):
        b = battle(["m01"])
        turn(b, "m01", enemy_action="defend")
        self.assertEqual(b.player.skill_cooldowns["m01"], 2)
        for remaining in (1,0):
            self.assertFalse(b.validate_intent(TurnIntent("player", Action.ATTACK, "m01")).valid)
            turn(b, action="defend", enemy_action="defend")
            self.assertEqual(b.player.skill_cooldowns["m01"], remaining)
        self.assertTrue(b.validate_intent(TurnIntent("player", Action.ATTACK, "m01")).valid)
        b._end_round()
        self.assertEqual(b.player.skill_uses_remaining["m01"], 4)


if __name__ == "__main__":
    unittest.main()
