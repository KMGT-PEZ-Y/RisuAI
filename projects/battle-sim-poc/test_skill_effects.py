from __future__ import annotations

import copy
import math
import unittest

from battle_sim import (
    Action,
    ManualBattleEngine,
    OwnedSkill,
    StatusEffect,
    TurnIntent,
)
from skill_schema import load_skill_definitions
from test_skill_runtime import skill_data


def application(
    application_id: str,
    *,
    timing: str,
    target: str,
    effects: list[dict],
    priority: int = 100,
    condition: dict | None = None,
) -> dict:
    return {
        "id": application_id,
        "delivery": {"type": "immediate"},
        "timing": timing,
        "target": target,
        "condition": condition,
        "priority": priority,
        "effects": effects,
    }


def skill_with_applications(
    applications: list[dict],
    *,
    skill_id: str = "effect_skill",
    allowed_actions: tuple[str, ...] = ("attack",),
    target: str = "opponent",
) -> dict:
    raw = skill_data(
        skill_id=skill_id,
        allowed_actions=allowed_actions,
        cost=0,
        cooldown=0,
        per_match=None,
        per_round=None,
        target=target,
    )
    raw["levels"][0]["applications"] = applications
    return raw


def manual_engine(raw_skills: list[dict], loadout: tuple[OwnedSkill, ...], seed: int = 400):
    return ManualBattleEngine(
        seed,
        enemy_strategy="attack",
        skill_registry=load_skill_definitions(raw_skills),
        player_skills=loadout,
    )


def last_resolution(engine: ManualBattleEngine) -> dict:
    return next(
        event["resolution"]
        for event in reversed(engine.trace)
        if event["event"] == "turn"
    )


class ImmediateEffectCategoryTests(unittest.TestCase):
    def test_resource_change_applies_after_base_result(self) -> None:
        raw = skill_with_applications([
            application(
                "recover_hp",
                timing="after_result_apply",
                target="self",
                effects=[{
                    "category": "resource_change",
                    "operation": "add",
                    "resource": "hp",
                    "value": 5,
                }],
            )
        ], target="self")
        baseline = ManualBattleEngine(401, enemy_strategy="attack")
        skilled = manual_engine([raw], (OwnedSkill("effect_skill", 1),), seed=401)

        baseline.submit_player_action(Action.ATTACK)
        skilled.submit_player_intent(TurnIntent(
            "player", Action.ATTACK, "effect_skill"
        ))

        self.assertEqual(skilled.player.hp, min(100, baseline.player.hp + 5))
        effect = last_resolution(skilled)["effects"][0]
        self.assertEqual(effect["category"], "resource_change")
        self.assertEqual(effect["after"], skilled.player.hp)

    def test_result_modifier_changes_final_delta_not_base_table(self) -> None:
        raw = skill_with_applications([
            application(
                "amplify_damage",
                timing="before_result_apply",
                target="opponent",
                effects=[{
                    "category": "result_modifier",
                    "operation": "multiply",
                    "resource": "hp",
                    "direction": "dealt",
                    "polarity": "damage",
                    "value": 1.5,
                }],
            )
        ])
        engine = manual_engine([raw], (OwnedSkill("effect_skill", 1),), seed=402)

        engine.submit_player_intent(TurnIntent(
            "player", Action.ATTACK, "effect_skill", "enemy"
        ))

        resolution = last_resolution(engine)
        base_hp = resolution["base_enemy_delta"]["hp"]
        applied_hp = resolution["applied_enemy_delta"]["hp"]
        self.assertLess(base_hp, 0)
        self.assertEqual(applied_hp, math.floor(base_hp * 1.5))

    def test_result_modifier_any_polarity_preserves_delta_direction(self) -> None:
        raw = skill_with_applications([
            application(
                "increase_existing_delta",
                timing="before_result_apply",
                target="opponent",
                effects=[{
                    "category": "result_modifier",
                    "operation": "add",
                    "resource": "hp",
                    "direction": "dealt",
                    "polarity": "any",
                    "value": 3,
                }],
            )
        ])
        engine = manual_engine([raw], (OwnedSkill("effect_skill", 1),), seed=411)

        engine.submit_player_intent(TurnIntent(
            "player", Action.ATTACK, "effect_skill", "enemy"
        ))

        resolution = last_resolution(engine)
        base_hp = resolution["base_enemy_delta"]["hp"]
        self.assertLess(base_hp, 0)
        self.assertEqual(resolution["applied_enemy_delta"]["hp"], base_hp - 3)

    def test_dice_modifier_uses_range_dominance_rule(self) -> None:
        raw = skill_with_applications([
            application(
                "limit_maximum",
                timing="before_dice_compare",
                target="self",
                priority=200,
                effects=[{
                    "category": "dice_modifier",
                    "operation": "set_maximum",
                    "value": 3,
                }],
            ),
            application(
                "raise_minimum",
                timing="before_dice_compare",
                target="self",
                priority=100,
                effects=[{
                    "category": "dice_modifier",
                    "operation": "set_minimum",
                    "value": 7,
                }],
            ),
        ], target="self")
        engine = manual_engine([raw], (OwnedSkill("effect_skill", 1),), seed=403)

        engine.submit_player_intent(TurnIntent(
            "player", Action.ATTACK, "effect_skill"
        ))

        resolution = last_resolution(engine)
        self.assertEqual(resolution["player_final_die"], 7)
        dice_logs = [
            effect for effect in resolution["effects"]
            if effect["category"] == "dice_modifier"
        ]
        selected = [effect for effect in dice_logs if effect["selected"]]
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["range"], [7, 6])

    def test_action_control_uses_highest_priority_application(self) -> None:
        raw = skill_with_applications([
            application(
                "force_defend",
                timing="before_action_reveal",
                target="opponent",
                priority=200,
                effects=[{
                    "category": "action_control",
                    "operation": "force",
                    "action": "defend",
                }],
            ),
            application(
                "force_evade",
                timing="before_action_reveal",
                target="opponent",
                priority=100,
                effects=[{
                    "category": "action_control",
                    "operation": "force",
                    "action": "evade",
                }],
            ),
        ])
        engine = manual_engine([raw], (OwnedSkill("effect_skill", 1),), seed=404)

        engine.submit_player_intent(TurnIntent(
            "player", Action.ATTACK, "effect_skill", "enemy"
        ))

        resolution = last_resolution(engine)
        self.assertEqual(resolution["enemy_action"], "defend")
        action_logs = [
            effect for effect in resolution["effects"]
            if effect["category"] == "action_control"
        ]
        self.assertTrue(action_logs[0]["applied"])
        self.assertEqual(action_logs[1]["reason"], "lower_priority_action_control")

    def test_action_control_allow_only_and_forbid_choose_a_legal_fallback(self) -> None:
        cases = (
            ("allow_only", ["defend", "evade"]),
            ("forbid", ["attack"]),
        )
        for operation, actions in cases:
            with self.subTest(operation=operation):
                raw = skill_with_applications([
                    application(
                        "restrict_action",
                        timing="before_action_reveal",
                        target="opponent",
                        effects=[{
                            "category": "action_control",
                            "operation": operation,
                            "actions": actions,
                        }],
                    )
                ])
                engine = manual_engine(
                    [raw], (OwnedSkill("effect_skill", 1),), seed=408
                )

                engine.submit_player_intent(TurnIntent(
                    "player", Action.ATTACK, "effect_skill", "enemy"
                ))

                self.assertEqual(last_resolution(engine)["enemy_action"], "defend")

    def test_status_control_removes_legacy_status(self) -> None:
        raw = skill_with_applications([
            application(
                "clear_shaken",
                timing="after_result_apply",
                target="self",
                effects=[{
                    "category": "status_control",
                    "operation": "remove",
                    "selector": {"type": "status_id", "value": "shaken"},
                    "count": 1,
                }],
            )
        ], target="self")
        engine = manual_engine([raw], (OwnedSkill("effect_skill", 1),), seed=405)
        engine.player.statuses.extend([
            StatusEffect("shaken", 2, 0),
            StatusEffect("short_of_breath", 2, 0),
        ])

        engine.submit_player_intent(TurnIntent(
            "player", Action.ATTACK, "effect_skill"
        ))

        self.assertEqual(
            [status.name for status in engine.player.statuses],
            ["short_of_breath"],
        )

    def test_status_control_changes_duration_and_removes_expired_status(self) -> None:
        raw = skill_with_applications([
            application(
                "shorten_shaken",
                timing="after_result_apply",
                target="self",
                effects=[{
                    "category": "status_control",
                    "operation": "change_duration",
                    "selector": {"type": "status_id", "value": "shaken"},
                    "value": -2,
                }],
            )
        ], target="self")
        engine = manual_engine([raw], (OwnedSkill("effect_skill", 1),), seed=409)
        engine.player.statuses.append(StatusEffect("shaken", 2, 0))

        engine.submit_player_intent(TurnIntent(
            "player", Action.ATTACK, "effect_skill"
        ))

        self.assertEqual(engine.player.statuses, [])

    def test_skill_control_changes_cost_cooldown_and_charges(self) -> None:
        reserve = skill_data(
            skill_id="reserve_skill",
            cost=10,
            cooldown=5,
            per_match=2,
            per_round=None,
        )
        controller = skill_with_applications([
            application(
                "adjust_reserve",
                timing="after_result_apply",
                target="self",
                effects=[
                    {
                        "category": "skill_control",
                        "operation": "modify_cost",
                        "selector": {"type": "skill_id", "value": "reserve_skill"},
                        "resource": "stamina",
                        "value": -3,
                    },
                    {
                        "category": "skill_control",
                        "operation": "change_cooldown",
                        "selector": {"type": "skill_id", "value": "reserve_skill"},
                        "value": -1,
                    },
                    {
                        "category": "skill_control",
                        "operation": "change_charges",
                        "selector": {"type": "skill_id", "value": "reserve_skill"},
                        "value": 1,
                    },
                ],
            )
        ], skill_id="controller", target="self")
        engine = manual_engine(
            [controller, reserve],
            (OwnedSkill("controller", 1), OwnedSkill("reserve_skill", 1)),
            seed=406,
        )
        engine.player.skill_cooldowns["reserve_skill"] = 5

        engine.submit_player_intent(TurnIntent(
            "player", Action.ATTACK, "controller"
        ))

        self.assertEqual(
            engine.player.skill_cost_modifiers["reserve_skill"]["stamina"], -3
        )
        # Effect changes 5→4, then the ordinary owner-turn tick changes 4→3.
        self.assertEqual(engine.player.skill_cooldowns["reserve_skill"], 3)
        self.assertEqual(engine.player.skill_uses_remaining["reserve_skill"], 3)
        engine.player.skill_cooldowns["reserve_skill"] = 0
        engine.player.stamina = 7
        self.assertTrue(engine.validate_intent(TurnIntent(
            "player", Action.ATTACK, "reserve_skill", "enemy"
        )).valid)


class EffectPipelineTests(unittest.TestCase):
    def test_effect_condition_failure_is_logged_without_effect(self) -> None:
        raw = skill_with_applications([
            application(
                "win_only",
                timing="before_result_apply",
                target="opponent",
                condition={
                    "type": "dice_result_is",
                    "subject": "self",
                    "value": "win",
                },
                effects=[{
                    "category": "result_modifier",
                    "operation": "add",
                    "resource": "break_gauge",
                    "direction": "dealt",
                    "polarity": "increase",
                    "value": 99,
                }],
            )
        ])
        # Find a deterministic seed where Player does not win the dice exchange.
        engine = manual_engine([raw], (OwnedSkill("effect_skill", 1),), seed=1)
        engine.submit_player_intent(TurnIntent(
            "player", Action.ATTACK, "effect_skill", "enemy"
        ))

        resolution = last_resolution(engine)
        if resolution["dice_result"] == "win":
            self.skipTest("selected seed unexpectedly produced a win")
        self.assertEqual(resolution["effects"][0]["reason"], "condition_not_met")

    def test_effect_log_contains_before_and_after_values(self) -> None:
        raw = skill_with_applications([
            application(
                "recover_stamina",
                timing="after_result_apply",
                target="self",
                effects=[{
                    "category": "resource_change",
                    "operation": "add",
                    "resource": "stamina",
                    "value": 4,
                }],
            )
        ], target="self")
        engine = manual_engine([raw], (OwnedSkill("effect_skill", 1),), seed=407)

        engine.submit_player_intent(TurnIntent(
            "player", Action.ATTACK, "effect_skill"
        ))

        effect = last_resolution(engine)["effects"][0]
        self.assertEqual(effect["timing"], "after_result_apply")
        self.assertEqual(effect["actor"], "player")
        self.assertEqual(effect["target"], "player")
        self.assertIn("before", effect)
        self.assertIn("after", effect)

    def test_round_end_and_interval_timings_have_separate_trace_entries(self) -> None:
        raw = skill_with_applications([
            application(
                "round_end_boost",
                timing="on_round_end",
                target="self",
                effects=[{
                    "category": "resource_change",
                    "operation": "add",
                    "resource": "break_gauge",
                    "value": 10,
                }],
            ),
            application(
                "interval_boost",
                timing="on_interval",
                target="self",
                effects=[{
                    "category": "resource_change",
                    "operation": "add",
                    "resource": "break_gauge",
                    "value": 5,
                }],
            ),
        ], target="self")
        engine = manual_engine([raw], (OwnedSkill("effect_skill", 1),), seed=410)
        for character in engine.characters:
            character.max_hp = character.hp = 10_000
            character.max_break_gauge = 10_000
        for _ in range(7):
            engine.submit_player_action(Action.ATTACK)
        engine.submit_player_intent(TurnIntent(
            "player", Action.ATTACK, "effect_skill"
        ))

        turn_resolution = next(
            event["resolution"] for event in reversed(engine.trace)
            if event["event"] == "turn"
        )
        interval = next(
            event for event in reversed(engine.trace)
            if event["event"] == "interval"
        )
        self.assertEqual(
            [effect["timing"] for effect in turn_resolution["effects"]],
            ["on_round_end"],
        )
        self.assertEqual(
            [effect["timing"] for effect in interval["effects"]],
            ["on_interval"],
        )


if __name__ == "__main__":
    unittest.main()
