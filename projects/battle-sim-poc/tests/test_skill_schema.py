from __future__ import annotations

from dataclasses import FrozenInstanceError
import copy
import json
import unittest

from skill_schema import (
    ConditionKind,
    DeliveryType,
    DiceModifierOperation,
    EffectCategory,
    ResultModifierOperation,
    SkillSchemaError,
    StackingMode,
    load_skill_definitions,
    load_skill_definitions_json,
    parse_skill_definition,
    validate_skill_data,
)


def valid_skill() -> dict:
    return {
        "schema_version": 1,
        "id": "driving_strike",
        "name": "드라이빙 스트라이크",
        "description": "공격 승리 시 상대의 브레이크를 추가로 압박한다.",
        "tags": ["attack", "break"],
        "max_level": 1,
        "targeting": {
            "type": "opponent",
            "selection_required": False,
        },
        "levels": [
            {
                "level": 1,
                "costs": [
                    {
                        "resource": "stamina",
                        "amount": 16,
                        "minimum_remaining": 0,
                    }
                ],
                "cooldown": {
                    "turns": 2,
                    "starts": "on_skill_commit",
                    "decrements": "owner_turn",
                },
                "usage_limit": {
                    "per_match": None,
                    "per_round": None,
                },
                "requirements": {
                    "allowed_actions": ["attack"],
                    "condition": None,
                },
                "applications": [
                    {
                        "id": "add_break_on_win",
                        "delivery": {"type": "immediate"},
                        "timing": "before_result_apply",
                        "target": "opponent",
                        "condition": {
                            "type": "dice_result_is",
                            "subject": "self",
                            "value": "win",
                        },
                        "priority": 100,
                        "effects": [
                            {
                                "category": "result_modifier",
                                "resource": "break_gauge",
                                "direction": "dealt",
                                "polarity": "increase",
                                "operation": "add",
                                "value": 7,
                            }
                        ],
                    }
                ],
            }
        ],
        "ui": {
            "icon": None,
            "short_description": "공격 승리 시 BRK +7",
            "show_exact_values": True,
        },
    }


class SkillSchemaModelTests(unittest.TestCase):
    def test_valid_skill_is_normalized_to_immutable_models(self) -> None:
        skill = parse_skill_definition(valid_skill())

        self.assertEqual(skill.skill_id, "driving_strike")
        self.assertEqual(skill.level(1).requirements.allowed_actions, ("attack",))
        application = skill.level(1).applications[0]
        self.assertEqual(application.delivery.type, DeliveryType.IMMEDIATE)
        self.assertEqual(application.condition.kind, ConditionKind.PREDICATE)
        self.assertEqual(application.condition.predicate, "dice_result_is")
        effect = application.effects[0]
        self.assertEqual(effect.category, EffectCategory.RESULT_MODIFIER)
        self.assertEqual(effect.operation, ResultModifierOperation.ADD)
        self.assertEqual(effect.parameters["value"], 7)

        with self.assertRaises(FrozenInstanceError):
            skill.name = "변경 불가"
        with self.assertRaises(TypeError):
            effect.parameters["value"] = 999

    def test_defaults_are_filled_during_normalization(self) -> None:
        raw = valid_skill()
        level = raw["levels"][0]
        level["costs"] = []
        level["cooldown"] = {}
        level["usage_limit"] = {}
        level["requirements"] = {}
        raw["ui"] = {}

        skill = parse_skill_definition(raw)
        normalized = skill.level(1)
        self.assertEqual(normalized.cooldown.turns, 0)
        self.assertEqual(
            normalized.requirements.allowed_actions,
            ("attack", "defend", "evade"),
        )
        self.assertIsNone(normalized.usage_limit.per_match)
        self.assertTrue(skill.ui.show_exact_values)

    def test_status_delivery_keeps_payload_metadata(self) -> None:
        raw = valid_skill()
        application = raw["levels"][0]["applications"][0]
        application["delivery"] = {
            "type": "status",
            "status": {
                "id": "shaken",
                "name": "흔들림",
                "duration": {
                    "value": 1,
                    "unit": "owner_turn",
                    "starts": "next_owner_turn",
                },
                "stacking": {"mode": "refresh", "max_stacks": 1},
                "removable": True,
                "polarity": "negative",
            },
        }
        application["condition"] = None
        application["timing"] = "on_status_apply"
        application["effects"] = [
            {
                "category": "dice_modifier",
                "operation": "set_maximum",
                "value": 5,
            }
        ]

        skill = parse_skill_definition(raw)
        delivery = skill.level(1).applications[0].delivery
        self.assertEqual(delivery.type, DeliveryType.STATUS)
        self.assertEqual(delivery.status.status_id, "shaken")
        self.assertEqual(delivery.status.stacking.mode, StackingMode.REFRESH)
        self.assertEqual(
            skill.level(1).applications[0].effects[0].operation,
            DiceModifierOperation.SET_MAXIMUM,
        )

    def test_json_loader_builds_immutable_unique_registry(self) -> None:
        registry = load_skill_definitions_json(json.dumps([valid_skill()]))
        self.assertEqual(tuple(registry), ("driving_strike",))
        with self.assertRaises(TypeError):
            registry["other"] = registry["driving_strike"]


class SkillSchemaValidationTests(unittest.TestCase):
    def test_unknown_allowed_action_is_rejected_with_path(self) -> None:
        raw = valid_skill()
        raw["levels"][0]["requirements"]["allowed_actions"] = ["counter_attack"]

        errors = validate_skill_data(raw)
        self.assertTrue(
            any(
                "skill.levels[0].requirements.allowed_actions[0]" in error
                and "unknown action" in error
                for error in errors
            )
        )

    def test_levels_must_be_complete_and_consecutive(self) -> None:
        raw = valid_skill()
        raw["max_level"] = 3
        second = copy.deepcopy(raw["levels"][0])
        second["level"] = 3
        raw["levels"].append(second)

        with self.assertRaisesRegex(
            SkillSchemaError,
            r"expected consecutive levels \[1, 2, 3\], got \[1, 3\]",
        ):
            parse_skill_definition(raw)

    def test_result_condition_cannot_run_before_dice_exists(self) -> None:
        raw = valid_skill()
        raw["levels"][0]["applications"][0]["timing"] = "before_roll"

        with self.assertRaisesRegex(
            SkillSchemaError,
            "dice_result_is cannot be evaluated at timing 'before_roll'",
        ):
            parse_skill_definition(raw)

    def test_result_condition_is_forbidden_in_requirements(self) -> None:
        raw = valid_skill()
        raw["levels"][0]["requirements"]["condition"] = {
            "type": "dice_result_is",
            "subject": "self",
            "value": "win",
        }

        with self.assertRaisesRegex(
            SkillSchemaError,
            "dice_result_is cannot be used in requirements",
        ):
            parse_skill_definition(raw)

    def test_requirement_cannot_read_opponent_current_action(self) -> None:
        raw = valid_skill()
        raw["levels"][0]["requirements"]["condition"] = {
            "type": "action_in",
            "subject": "opponent",
            "values": ["attack"],
        }

        with self.assertRaisesRegex(
            SkillSchemaError,
            "requirements action_in supports subject 'self' only",
        ):
            parse_skill_definition(raw)

    def test_reserved_multiplayer_target_is_rejected(self) -> None:
        raw = valid_skill()
        raw["targeting"]["type"] = "selected_ally"

        with self.assertRaisesRegex(SkillSchemaError, "unsupported value 'selected_ally'"):
            parse_skill_definition(raw)

    def test_reserved_dice_operation_is_rejected(self) -> None:
        raw = valid_skill()
        effect = raw["levels"][0]["applications"][0]["effects"][0]
        effect.clear()
        effect.update({
            "category": "dice_modifier",
            "operation": "reroll",
            "count": 1,
        })

        with self.assertRaisesRegex(SkillSchemaError, "unsupported value 'reroll'"):
            parse_skill_definition(raw)

    def test_action_forbid_must_leave_a_legal_action(self) -> None:
        raw = valid_skill()
        effect = raw["levels"][0]["applications"][0]["effects"][0]
        effect.clear()
        effect.update({
            "category": "action_control",
            "operation": "forbid",
            "actions": ["attack", "defend", "evade"],
        })

        with self.assertRaisesRegex(
            SkillSchemaError, "forbid must leave at least one action"
        ):
            parse_skill_definition(raw)

    def test_duplicate_skill_ids_are_rejected(self) -> None:
        with self.assertRaisesRegex(SkillSchemaError, "duplicate skill id"):
            load_skill_definitions([valid_skill(), valid_skill()])

    def test_status_stacks_above_one_are_rejected_for_first_poc(self) -> None:
        raw = valid_skill()
        application = raw["levels"][0]["applications"][0]
        application["delivery"] = {
            "type": "status",
            "status": {
                "id": "shaken",
                "name": "흔들림",
                "duration": {
                    "value": 1,
                    "unit": "owner_turn",
                    "starts": "next_owner_turn",
                },
                "stacking": {"mode": "refresh", "max_stacks": 2},
                "removable": True,
                "polarity": "negative",
            },
        }

        with self.assertRaisesRegex(SkillSchemaError, "supports max_stacks=1 only"):
            parse_skill_definition(raw)


if __name__ == "__main__":
    unittest.main()
