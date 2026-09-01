from __future__ import annotations

import unittest

from battle_sim import Action
from skill_testbed import (
    MAX_EQUIPPED_SKILLS,
    create_testbed_engine,
    effective_stamina_cost,
    load_test_skill_registry,
    make_player_intent,
)


class SkillTestbedCatalogTests(unittest.TestCase):
    def test_catalog_covers_all_phase_c_effect_categories(self) -> None:
        registry = load_test_skill_registry()
        categories = {
            effect.category.value
            for definition in registry.values()
            for application in definition.level(1).applications
            for effect in application.effects
        }

        self.assertEqual(len(registry), 8)
        self.assertEqual(categories, {
            "resource_change",
            "result_modifier",
            "dice_modifier",
            "action_control",
            "status_control",
            "skill_control",
        })

    def test_loadout_limit_and_unknown_skill_are_rejected(self) -> None:
        registry = load_test_skill_registry()
        with self.assertRaisesRegex(ValueError, "at most 4 skills"):
            create_testbed_engine(
                1,
                enemy_strategy="attack",
                equipped_skill_ids=tuple(registry)[:MAX_EQUIPPED_SKILLS + 1],
            )
        with self.assertRaisesRegex(ValueError, "unknown test skill"):
            create_testbed_engine(
                1,
                enemy_strategy="attack",
                equipped_skill_ids=("missing_skill",),
            )


class PlayerOnlySkillTestbedTests(unittest.TestCase):
    def test_every_catalog_skill_can_be_selected_and_resolved(self) -> None:
        actions = {
            "second_wind": Action.ATTACK,
            "power_drive": Action.ATTACK,
            "steady_form": Action.ATTACK,
            "read_the_play": Action.EVADE,
            "reset_rhythm": Action.DEFEND,
            "breathing_control": Action.DEFEND,
            "reserve_plan": Action.ATTACK,
            "sideline_coaching": Action.DEFEND,
        }
        for skill_id, action in actions.items():
            with self.subTest(skill_id=skill_id):
                loadout = (skill_id,)
                if skill_id == "sideline_coaching":
                    loadout = (skill_id, "power_drive")
                engine = create_testbed_engine(
                    10,
                    enemy_strategy="attack",
                    equipped_skill_ids=loadout,
                    add_test_statuses=True,
                )
                intent = make_player_intent(action, skill_id, engine.skill_registry)

                self.assertTrue(engine.validate_intent(intent).valid)
                engine.submit_player_intent(intent)
                self.assertEqual(engine.intent_history[0][-1].active_skill_id, skill_id)

    def test_enemy_has_no_skill_loadout_or_skill_intent(self) -> None:
        engine = create_testbed_engine(
            2,
            enemy_strategy="attack",
            equipped_skill_ids=("second_wind",),
            add_test_statuses=False,
        )
        intent = make_player_intent(
            Action.ATTACK, "second_wind", engine.skill_registry
        )

        engine.submit_player_intent(intent)

        self.assertEqual(engine.enemy.skill_loadout, ())
        self.assertIsNone(engine.intent_history[1][-1].active_skill_id)

    def test_skill_target_is_derived_and_intent_is_validated(self) -> None:
        engine = create_testbed_engine(
            3,
            enemy_strategy="attack",
            equipped_skill_ids=("power_drive", "second_wind"),
        )
        opponent_intent = make_player_intent(
            Action.ATTACK, "power_drive", engine.skill_registry
        )
        self_intent = make_player_intent(
            Action.DEFEND, "second_wind", engine.skill_registry
        )

        self.assertEqual(opponent_intent.target_id, "enemy")
        self.assertEqual(self_intent.target_id, "player")
        self.assertTrue(engine.validate_intent(opponent_intent).valid)
        self.assertTrue(engine.validate_intent(self_intent).valid)

    def test_test_statuses_can_be_removed_by_player_skill(self) -> None:
        engine = create_testbed_engine(
            4,
            enemy_strategy="attack",
            equipped_skill_ids=("reset_rhythm",),
            add_test_statuses=True,
        )
        self.assertEqual(
            [status.name for status in engine.player.statuses],
            ["shaken", "short_of_breath"],
        )

        engine.submit_player_intent(make_player_intent(
            Action.DEFEND, "reset_rhythm", engine.skill_registry
        ))

        self.assertEqual(
            [status.name for status in engine.player.statuses],
            ["short_of_breath"],
        )

    def test_next_skill_discount_is_visible_in_runtime_cost(self) -> None:
        engine = create_testbed_engine(
            5,
            enemy_strategy="attack",
            equipped_skill_ids=("reserve_plan", "power_drive"),
            add_test_statuses=False,
        )
        self.assertEqual(effective_stamina_cost(engine, "power_drive"), 14)

        engine.submit_player_intent(make_player_intent(
            Action.ATTACK, "reserve_plan", engine.skill_registry
        ))

        self.assertEqual(effective_stamina_cost(engine, "power_drive"), 9)

    def test_action_requirement_produces_structured_validation(self) -> None:
        engine = create_testbed_engine(
            6,
            enemy_strategy="attack",
            equipped_skill_ids=("read_the_play",),
            add_test_statuses=False,
        )
        invalid = make_player_intent(
            Action.ATTACK, "read_the_play", engine.skill_registry
        )
        valid = make_player_intent(
            Action.EVADE, "read_the_play", engine.skill_registry
        )

        self.assertEqual(
            [issue.code for issue in engine.validate_intent(invalid).issues],
            ["action_not_allowed"],
        )
        self.assertTrue(engine.validate_intent(valid).valid)


if __name__ == "__main__":
    unittest.main()
