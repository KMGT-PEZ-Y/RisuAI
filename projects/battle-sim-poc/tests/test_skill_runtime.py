from __future__ import annotations

import unittest

from battle_sim import (
    Action,
    BattleEngine,
    InvalidTurnIntent,
    ManualBattleEngine,
    OwnedSkill,
    TurnIntent,
)
from skill_schema import load_skill_definitions


def skill_data(
    *,
    skill_id: str = "driving_strike",
    allowed_actions: tuple[str, ...] = ("attack",),
    cost: int = 16,
    cooldown: int = 2,
    cooldown_starts: str = "on_skill_commit",
    cooldown_decrements: str = "owner_turn",
    per_match: int | None = 2,
    per_round: int | None = 1,
    requirement: dict | None = None,
    target: str = "opponent",
    selection_required: bool = False,
) -> dict:
    return {
        "schema_version": 1,
        "id": skill_id,
        "name": "테스트 스킬",
        "description": "Phase B 입력과 런타임 상태 검증용 스킬",
        "tags": ["test"],
        "max_level": 1,
        "targeting": {
            "type": target,
            "selection_required": selection_required,
        },
        "levels": [
            {
                "level": 1,
                "costs": [
                    {
                        "resource": "stamina",
                        "amount": cost,
                        "minimum_remaining": 0,
                    }
                ],
                "cooldown": {
                    "turns": cooldown,
                    "starts": cooldown_starts,
                    "decrements": cooldown_decrements,
                },
                "usage_limit": {
                    "per_match": per_match,
                    "per_round": per_round,
                },
                "requirements": {
                    "allowed_actions": list(allowed_actions),
                    "condition": requirement,
                },
                "applications": [
                    {
                        "id": "phase_b_placeholder",
                        "delivery": {"type": "immediate"},
                        "timing": "before_result_apply",
                        "target": target,
                        "condition": None,
                        "priority": 100,
                        "effects": [
                            {
                                "category": "result_modifier",
                                "resource": "break_gauge",
                                "direction": "dealt",
                                "polarity": "increase",
                                "operation": "add",
                                "value": 1,
                            }
                        ],
                    }
                ],
            }
        ],
        "ui": {},
    }


def engine_with_skill(**skill_options) -> BattleEngine:
    raw = skill_data(**skill_options)
    registry = load_skill_definitions([raw])
    return BattleEngine(
        300,
        skill_registry=registry,
        player_skills=(OwnedSkill(raw["id"], 1),),
    )


class SkillRuntimeStateTests(unittest.TestCase):
    def test_loadout_initializes_character_runtime_state(self) -> None:
        engine = engine_with_skill(per_match=3, per_round=1)

        self.assertEqual(
            engine.player.skill_loadout,
            (OwnedSkill("driving_strike", 1),),
        )
        self.assertEqual(engine.player.skill_cooldowns["driving_strike"], 0)
        self.assertEqual(engine.player.skill_uses_remaining["driving_strike"], 3)
        self.assertEqual(
            engine.player.skill_round_uses_remaining["driving_strike"], 1
        )
        self.assertEqual(
            engine.player.snapshot()["skill_loadout"],
            [{"skill_id": "driving_strike", "level": 1}],
        )

    def test_unknown_or_duplicate_equipped_skill_is_rejected(self) -> None:
        registry = load_skill_definitions([skill_data()])
        with self.assertRaisesRegex(ValueError, "unknown equipped skill"):
            BattleEngine(
                301,
                skill_registry=registry,
                player_skills=(OwnedSkill("missing", 1),),
            )
        with self.assertRaisesRegex(ValueError, "duplicate equipped skill"):
            BattleEngine(
                302,
                skill_registry=registry,
                player_skills=(
                    OwnedSkill("driving_strike", 1),
                    OwnedSkill("driving_strike", 1),
                ),
            )

    def test_commit_consumes_cost_uses_and_starts_cooldown(self) -> None:
        engine = engine_with_skill(cost=16, cooldown=2, per_match=2, per_round=1)
        intent = TurnIntent(
            "player", Action.ATTACK, "driving_strike", "enemy"
        )

        self.assertTrue(engine.validate_intent(intent).valid)
        engine.commit_intents((intent,))

        self.assertEqual(engine.player.stamina, 84)
        self.assertEqual(engine.player.skill_cooldowns["driving_strike"], 2)
        self.assertEqual(engine.player.skill_uses_remaining["driving_strike"], 1)
        self.assertEqual(
            engine.player.skill_round_uses_remaining["driving_strike"], 0
        )

    def test_invalid_intent_does_not_mutate_skill_state(self) -> None:
        engine = engine_with_skill()
        intent = TurnIntent(
            "player", Action.DEFEND, "driving_strike", "enemy"
        )

        validation = engine.validate_intent(intent)
        self.assertFalse(validation.valid)
        self.assertIn("action_not_allowed", {issue.code for issue in validation.issues})
        with self.assertRaises(InvalidTurnIntent):
            engine.commit_intents((intent,))

        self.assertEqual(engine.player.stamina, 100)
        self.assertEqual(engine.player.skill_cooldowns["driving_strike"], 0)
        self.assertEqual(engine.player.skill_uses_remaining["driving_strike"], 2)

    def test_multiple_intents_are_committed_atomically(self) -> None:
        engine = engine_with_skill()
        valid = TurnIntent(
            "player", Action.ATTACK, "driving_strike", "enemy"
        )
        invalid = TurnIntent(
            "enemy", Action.ATTACK, "driving_strike", "player"
        )

        with self.assertRaises(InvalidTurnIntent):
            engine.commit_intents((valid, invalid))
        self.assertEqual(engine.player.stamina, 100)
        self.assertEqual(engine.player.skill_uses_remaining["driving_strike"], 2)

    def test_duplicate_actor_intents_are_rejected_atomically(self) -> None:
        engine = engine_with_skill()
        intent = TurnIntent(
            "player", Action.ATTACK, "driving_strike", "enemy"
        )

        with self.assertRaisesRegex(InvalidTurnIntent, "one intent per actor"):
            engine.commit_intents((intent, intent))
        self.assertEqual(engine.player.stamina, 100)

    def test_resource_requirement_and_target_are_validated(self) -> None:
        engine = engine_with_skill(
            requirement={
                "type": "resource_at_most",
                "subject": "self",
                "resource": "hp",
                "value": 40,
            },
            selection_required=True,
        )
        no_target = TurnIntent("player", Action.ATTACK, "driving_strike")
        codes = {issue.code for issue in engine.validate_intent(no_target).issues}
        self.assertEqual(codes, {"target_required", "requirements_not_met"})

        engine.player.hp = 40
        wrong_target = TurnIntent(
            "player", Action.ATTACK, "driving_strike", "player"
        )
        codes = {issue.code for issue in engine.validate_intent(wrong_target).issues}
        self.assertEqual(codes, {"invalid_target"})
        valid = TurnIntent(
            "player", Action.ATTACK, "driving_strike", "enemy"
        )
        self.assertTrue(engine.validate_intent(valid).valid)

    def test_cooldown_ticks_on_future_owner_turns(self) -> None:
        engine = engine_with_skill(cost=0, cooldown=2, per_round=None)
        engine.commit_intents((TurnIntent(
            "player", Action.ATTACK, "driving_strike", "enemy"
        ),))

        engine.play_turn()
        self.assertEqual(engine.player.skill_cooldowns["driving_strike"], 1)
        engine.play_turn()
        self.assertEqual(engine.player.skill_cooldowns["driving_strike"], 0)

    def test_after_resolution_cooldown_starts_after_skill_turn(self) -> None:
        raw = skill_data(
            cost=0,
            cooldown=3,
            cooldown_starts="after_resolution",
            per_round=None,
        )
        registry = load_skill_definitions([raw])
        engine = ManualBattleEngine(
            303,
            enemy_strategy="rookie_cycle",
            skill_registry=registry,
            player_skills=(OwnedSkill("driving_strike", 1),),
        )

        engine.submit_player_intent(TurnIntent(
            "player", Action.ATTACK, "driving_strike", "enemy"
        ))
        self.assertEqual(engine.player.skill_cooldowns["driving_strike"], 3)

    def test_turn_requirement_matches_preselection_and_resolution_context(self) -> None:
        raw = skill_data(
            cost=0,
            requirement={"type": "turn_in_round_is", "value": 1},
            per_round=None,
        )
        registry = load_skill_definitions([raw])
        engine = ManualBattleEngine(
            304,
            enemy_strategy="rookie_cycle",
            skill_registry=registry,
            player_skills=(OwnedSkill("driving_strike", 1),),
        )
        intent = TurnIntent(
            "player", Action.ATTACK, "driving_strike", "enemy"
        )

        self.assertTrue(engine.validate_intent(intent).valid)
        engine.submit_player_intent(intent)
        self.assertEqual(engine.match_turn, 1)

    def test_round_usage_resets_at_interval(self) -> None:
        engine = engine_with_skill(cost=0, cooldown=0, per_match=2, per_round=1)
        engine.commit_intents((TurnIntent(
            "player", Action.ATTACK, "driving_strike", "enemy"
        ),))
        self.assertEqual(
            engine.player.skill_round_uses_remaining["driving_strike"], 0
        )

        engine.turn_in_round = 7
        engine.match_turn = 7
        engine.play_turn()
        self.assertEqual(engine.round_number, 2)
        self.assertEqual(
            engine.player.skill_round_uses_remaining["driving_strike"], 1
        )


class SkillTurnIntentTests(unittest.TestCase):
    def test_manual_engine_accepts_skill_intent_and_records_it(self) -> None:
        raw = skill_data(cost=0, cooldown=2, per_match=2, per_round=None)
        registry = load_skill_definitions([raw])
        engine = ManualBattleEngine(
            310,
            enemy_strategy="rookie_cycle",
            skill_registry=registry,
            player_skills=(OwnedSkill("driving_strike", 1),),
        )
        intent = TurnIntent(
            "player", Action.ATTACK, "driving_strike", "enemy"
        )

        engine.submit_player_intent(intent)

        self.assertEqual(engine.intent_history[0], [intent])
        self.assertEqual(engine.action_history[0], [Action.ATTACK])
        self.assertEqual(engine.player.skill_cooldowns["driving_strike"], 2)
        turn_event = next(event for event in engine.trace if event["event"] == "turn")
        self.assertEqual(
            turn_event["resolution"]["player_skill"], "driving_strike"
        )

    def test_old_action_submission_creates_no_skill_intent(self) -> None:
        engine = ManualBattleEngine(311, enemy_strategy="rookie_cycle")
        engine.submit_player_action(Action.EVADE)

        self.assertEqual(
            engine.intent_history[0],
            [TurnIntent("player", Action.EVADE)],
        )

    def test_manual_invalid_skill_returns_structured_validation(self) -> None:
        engine = engine_with_skill()
        result = engine.validate_intent(TurnIntent(
            "player", Action.DEFEND, "driving_strike", "enemy"
        ))

        self.assertFalse(result.valid)
        self.assertEqual(result.issues[0].code, "action_not_allowed")
        self.assertIn("cannot be used", result.issues[0].message)


if __name__ == "__main__":
    unittest.main()
