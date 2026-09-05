"""NG+ information boundary, real-rule parity, search limits and integration."""
from threading import Event
import unittest
from unittest.mock import Mock

from battle_sim import Action, TurnIntent
from muh_skills import load_muh_skill_registry
from muh_testbed import create_muh_testbed_engine
from ng_plus_ai import (DEFAULT_CONFIG, ForwardModel, SearchConfig, SearchCancelled,
                        _Dice, _Search, audit_dice, create_request, evaluate,
                        legal_intents, opponent_distribution, public_model)
from test_muh_skills import prepare


def engine(player=(), enemy=(), *, seed=17, judgment=1):
    return create_muh_testbed_engine(seed, enemy_strategy="ng_plus", equipped_skill_ids=player,
                                     enemy_skill_ids=enemy, ng_judgment=judgment)


def stable(decision):
    data = decision.summary()
    data.pop("elapsed_ms")
    return data


class PublicInformationTests(unittest.TestCase):
    def test_hidden_current_input_and_combat_rng_are_never_read(self):
        b = engine(["m01","m02"], ["m01","m02","m05","m06"])
        before = [c.snapshot() for c in b.characters]
        rng = b.rng.getstate()
        first = create_request(b).decide()
        b._submitted_player_intent = TurnIntent("player", Action.ATTACK, "m01")
        b.enemy_override = TurnIntent("enemy", Action.EVADE)
        class ForbiddenRng:
            def __getattr__(self, name):
                raise AssertionError("planner accessed live RNG: " + name)
        b.rng = ForbiddenRng()
        second = create_request(b).decide()
        self.assertEqual(stable(first), stable(second))
        self.assertEqual([c.snapshot() for c in b.characters], before)
        self.assertEqual(b.intent_history, ([], []))

    def test_request_snapshot_survives_live_loadout_and_status_changes(self):
        b = engine(enemy=["m01","m02"])
        request = create_request(b)
        first = request.decide()
        b.enemy.hp = 1
        b.enemy.skill_loadout = ()
        b.enemy.skill_uses_remaining.clear()
        self.assertEqual(stable(first), stable(request.decide()))
        self.assertNotIn("_submitted_player_intent", request.root.__dict__)
        self.assertNotIn("policy_rngs", request.root.__dict__)
        self.assertNotIn("rng", request.root.__dict__)

    def test_repeated_preview_preserves_all_live_rngs_and_state(self):
        b = engine(enemy=["h04","h05","h06"])
        states = [r.getstate() for r in (b.rng, *b.policy_rngs, *b.skill_rngs)]
        before = [c.snapshot() for c in b.characters]
        create_request(b).decide()
        self.assertEqual(states, [r.getstate() for r in (b.rng, *b.policy_rngs, *b.skill_rngs)])
        self.assertEqual(before, [c.snapshot() for c in b.characters])
        self.assertFalse(b.trace)

    def test_opponent_model_learns_past_actions_but_keeps_support(self):
        b = engine(player=["m01"])
        b.action_history[0].extend([Action.ATTACK]*8)
        distribution = opponent_distribution(public_model(b), 0)
        mass = {a:sum(p for i,p in distribution if i.base_action == a) for a in Action}
        self.assertGreater(mass[Action.ATTACK], mass[Action.DEFEND])
        self.assertTrue(all(p > 0 for _,p in distribution))
        self.assertAlmostEqual(sum(p for _,p in distribution), 1)


class ForwardModelTests(unittest.TestCase):
    def test_all_thirty_effects_match_real_engine_transitions(self):
        for code in load_muh_skill_registry():
            with self.subTest(code=code):
                b = engine(player=[code])
                b.player.hp, b.player.down_count = 30, 1
                b.enemy.hp, b.enemy.break_gauge = 30, 70
                if code in {"m07","u07","h07"}: prepare(b, "m05", 1)
                if code == "h06": prepare(b, "h05")
                action = Action(b.skill_registry[code].level(1).requirements.allowed_actions[0])
                intents = (b._intent_with_skill(0, action, code), TurnIntent("enemy", Action.DEFEND))
                model = public_model(b)
                model.forced_intents = intents
                model.rng = _Dice((6,1))
                model.play_turn()
                b.rng = Mock(); b.rng.randint.side_effect = (6,1)
                b.submit_test_turn(*intents)
                self.assertEqual([a.snapshot() for a in model.characters], [a.snapshot() for a in b.characters])
                self.assertEqual(model.outcome, b.outcome)

    def test_forward_model_keeps_round_boundary_and_wait_expiry(self):
        b = engine(player=["m05"])
        b.turn_in_round = 7
        model = public_model(b)
        pair = (b._intent_with_skill(0, Action.DEFEND, "m05"), TurnIntent("enemy",Action.DEFEND))
        model.forced_intents = pair; model.rng = _Dice((6,1)); model.play_turn()
        b.rng = Mock(); b.rng.randint.side_effect = (6,1); b.submit_test_turn(*pair)
        self.assertEqual(model.round_number, 2)
        self.assertEqual([a.snapshot() for a in model.characters], [a.snapshot() for a in b.characters])
        for state in (model, b):
            state.enemy.is_down = True; state.enemy.skipped_turns_remaining = 2
        model.play_turn(); b.submit_test_turn()
        self.assertFalse(model.player.statuses)
        self.assertEqual([a.snapshot() for a in model.characters], [a.snapshot() for a in b.characters])

    def test_exact_audit_aggregation_matches_full_36_rolls(self):
        for skill in (None, "m01", "h09"):
            b = engine(enemy=[skill] if skill else [])
            b.enemy.hp = 30
            request = create_request(b)
            search = _Search(request, None)
            own = request.root._intent_with_skill(1, Action.ATTACK, skill) if skill else TurnIntent("enemy",Action.ATTACK)
            exact, _ = search.audit(own)
            full = 0
            for other, p in opponent_distribution(request.root, 0):
                for a in range(1,7):
                    for c in range(1,7):
                        full += p*evaluate(search.step(request.root, own, other, (a,c)), 1)/36
            self.assertAlmostEqual(exact, full)
            pairs = audit_dice(request.root, (TurnIntent("player",Action.ATTACK),own))
            self.assertEqual(len(pairs), 36 if skill == "h09" else 3)


class PlannerTests(unittest.TestCase):
    def test_depth_three_budget_and_prepared_combo(self):
        b = engine(["m01","m02","m05","m06","u03"], ["h04","h05","h06","m02","u03"])
        result = create_request(b).decide()
        self.assertEqual(result.depth_completed, 3)
        self.assertLessEqual(result.transitions, DEFAULT_CONFIG.max_transitions)
        self.assertTrue(result.audit_completed)
        self.assertTrue(b.validate_intent(result.intent).valid)
        self.assertTrue(any([i.active_skill_id for i in c.plan][:2] == ["h05","h06"] for c in result.candidates))

    def test_ng_uses_equipped_skills_without_fixed_deck(self):
        for loadout in ((), ("m01",), ("m03","u03","h03"), ("m09","u07","u06","m01","u03")):
            with self.subTest(loadout=loadout):
                b = engine(enemy=loadout)
                d = create_request(b).decide()
                self.assertTrue(b.validate_intent(d.intent).valid)
                self.assertTrue(d.intent.active_skill_id is None or d.intent.active_skill_id in loadout)

    def test_zero_judgment_is_fast_legal_and_variable(self):
        selections = set()
        for seed in range(30):
            b = engine(enemy=["m01","m02"], seed=seed, judgment=0)
            d = create_request(b).decide()
            self.assertEqual(d.transitions, 0)
            self.assertTrue(d.random_choice)
            self.assertTrue(b.validate_intent(d.intent).valid)
            selections.add(d.intent)
        self.assertGreater(len(selections), 3)

    def test_invalid_judgment_and_excessive_budget_rejected(self):
        for judgment in (-1, 1.1, float("nan"), float("inf")):
            with self.assertRaises(ValueError): engine(judgment=judgment)
        with self.assertRaises(ValueError): SearchConfig(depth=4)
        with self.assertRaises(ValueError): SearchConfig(scenarios=9)

    def test_hard_budget_and_cancel(self):
        b = engine(enemy=["m01","m02"])
        d = create_request(b, config=SearchConfig(max_transitions=25)).decide()
        self.assertLessEqual(d.transitions, 25)
        self.assertEqual(d.depth_completed, 1)
        self.assertTrue(b.validate_intent(d.intent).valid)
        cancel = Event(); cancel.set()
        with self.assertRaises(SearchCancelled): create_request(b).decide(cancel)

    def test_seal_and_action_control_obeyed(self):
        b = engine(enemy=["m01","m02","h06"])
        prepare(b, "h06", 1)
        prepare(b, "h08", 1)
        d = create_request(b).decide()
        self.assertEqual(d.intent.base_action, Action.ATTACK)
        self.assertIsNone(d.intent.active_skill_id)

    def test_basic_finishing_hit_does_not_waste_skill(self):
        b = engine(enemy=["m01"])
        b.player.hp = 10; b.player.down_count = 2; b.player.is_groggy = True
        d = create_request(b).decide()
        self.assertIsNone(d.intent.active_skill_id)
        self.assertIn(d.intent.base_action, (Action.ATTACK, Action.EVADE))

    def test_synchronous_engine_and_preview_choose_same_intent(self):
        b = engine(enemy=["h05","h06"])
        expected = create_request(b).decide()
        b.submit_test_turn(TurnIntent("player", Action.DEFEND))
        self.assertEqual(b.intent_history[1][-1], expected.intent)
        self.assertEqual(b.last_ng_decisions[1].intent, expected.intent)
        self.assertEqual(b.match_turn, 1)
        self.assertTrue(any(event["event"] == "ng_plus_decision" for event in b.trace))

    def test_snapshot_turn_number_adjustment_does_not_leak_current_turn(self):
        b = engine(enemy=["m01"])
        previous = create_request(b).decide()
        b.match_turn += 1; b.turn_in_round += 1
        inside = create_request(b, turn_started=True).decide()
        self.assertEqual(stable(previous), stable(inside))


if __name__ == "__main__":
    unittest.main()
