from __future__ import annotations

import math
import unittest

from battle_sim import Action, ManualBattleEngine, OwnedSkill, StatusEffect, TurnIntent
from skill_schema import load_skill_definitions
from test_skill_runtime import skill_data


def application(
    application_id: str,
    *,
    delivery: dict,
    timing: str,
    target: str,
    effects: list[dict],
    priority: int = 100,
    condition: dict | None = None,
) -> dict:
    return {
        "id": application_id,
        "delivery": delivery,
        "timing": timing,
        "target": target,
        "condition": condition,
        "priority": priority,
        "effects": effects,
    }


def status_delivery(
    status_id: str,
    *,
    duration: int = 2,
    mode: str = "refresh",
    removable: bool = True,
    polarity: str = "negative",
) -> dict:
    return {
        "type": "status",
        "status": {
            "id": status_id,
            "name": status_id.replace("_", " ").title(),
            "duration": {
                "value": duration,
                "unit": "owner_turn",
                "starts": "next_owner_turn",
            },
            "stacking": {"mode": mode, "max_stacks": 1},
            "removable": removable,
            "polarity": polarity,
        },
    }


def skill(skill_id: str, applications: list[dict], *, target: str) -> dict:
    raw = skill_data(
        skill_id=skill_id,
        cost=0,
        cooldown=0,
        per_match=None,
        per_round=None,
        target=target,
    )
    raw["levels"][0]["applications"] = applications
    return raw


def engine(raw_skills: list[dict], *, seed: int = 500) -> ManualBattleEngine:
    return ManualBattleEngine(
        seed,
        enemy_strategy="attack",
        skill_registry=load_skill_definitions(raw_skills),
        player_skills=tuple(OwnedSkill(raw["id"], 1) for raw in raw_skills),
    )


def last_turn(engine: ManualBattleEngine) -> dict:
    return next(
        event["resolution"] for event in reversed(engine.trace)
        if event["event"] == "turn"
    )


class StatusDeliveryTests(unittest.TestCase):
    def test_shaken_dice_limit_starts_on_next_owner_turn(self) -> None:
        raw = skill("apply_shaken", [application(
            "shaken",
            delivery=status_delivery("shaken", duration=2),
            timing="before_dice_compare",
            target="opponent",
            effects=[{
                "category": "dice_modifier",
                "operation": "set_maximum",
                "value": 2,
            }],
        )], target="opponent")
        battle = engine([raw], seed=503)

        battle.submit_player_intent(TurnIntent(
            "player", Action.ATTACK, "apply_shaken", "enemy"
        ))
        first = last_turn(battle)
        self.assertEqual(first["enemy_die"], first["enemy_final_die"])
        self.assertEqual(battle.enemy.statuses[0].remaining_turns, 2)

        battle.submit_player_action(Action.ATTACK)
        second = last_turn(battle)
        self.assertLessEqual(second["enemy_final_die"], 2)
        self.assertEqual(battle.enemy.statuses[0].remaining_turns, 1)

    def test_result_amplifier_status_modifies_future_result(self) -> None:
        raw = skill("mark_target", [application(
            "vulnerable",
            delivery=status_delivery("vulnerable", duration=2),
            timing="before_result_apply",
            target="opponent",
            effects=[{
                "category": "result_modifier",
                "operation": "multiply",
                "resource": "hp",
                "direction": "received",
                "polarity": "damage",
                "value": 1.5,
            }],
        )], target="opponent")
        battle = engine([raw], seed=504)
        battle.submit_player_intent(TurnIntent(
            "player", Action.ATTACK, "mark_target", "enemy"
        ))

        battle.submit_player_action(Action.ATTACK)
        resolution = last_turn(battle)
        base = resolution["base_enemy_delta"]["hp"]
        self.assertLess(base, 0)
        self.assertEqual(
            resolution["applied_enemy_delta"]["hp"], math.floor(base * 1.5)
        )

    def test_refresh_keeps_one_stack_and_restarts_duration(self) -> None:
        raw = skill("steady_shake", [application(
            "shaken",
            delivery=status_delivery("shaken", duration=3, mode="refresh"),
            timing="before_dice_compare",
            target="opponent",
            effects=[{
                "category": "dice_modifier",
                "operation": "set_maximum",
                "value": 2,
            }],
        )], target="opponent")
        battle = engine([raw], seed=505)
        intent = TurnIntent("player", Action.ATTACK, "steady_shake", "enemy")
        battle.submit_player_intent(intent)
        battle.submit_player_intent(intent)

        self.assertEqual(len(battle.enemy.statuses), 1)
        self.assertEqual(battle.enemy.statuses[0].remaining_turns, 3)
        self.assertEqual(battle.enemy.statuses[0].applied_on_match_turn, 2)

    def test_replace_swaps_the_stored_payload(self) -> None:
        first = skill("weak_mark", [application(
            "weak_mark",
            delivery=status_delivery("shared_mark", duration=3, mode="replace"),
            timing="before_dice_compare",
            target="opponent",
            effects=[{
                "category": "dice_modifier",
                "operation": "set_maximum",
                "value": 4,
            }],
        )], target="opponent")
        second = skill("strong_mark", [application(
            "strong_mark",
            delivery=status_delivery("shared_mark", duration=2, mode="replace"),
            timing="before_dice_compare",
            target="opponent",
            priority=200,
            effects=[{
                "category": "dice_modifier",
                "operation": "set_maximum",
                "value": 1,
            }],
        )], target="opponent")
        battle = engine([first, second], seed=508)
        battle.submit_player_intent(TurnIntent(
            "player", Action.ATTACK, "weak_mark", "enemy"
        ))
        battle.submit_player_intent(TurnIntent(
            "player", Action.ATTACK, "strong_mark", "enemy"
        ))

        self.assertEqual(len(battle.enemy.statuses), 1)
        self.assertEqual(battle.enemy.statuses[0].source_skill_id, "strong_mark")
        self.assertEqual(battle.enemy.statuses[0].remaining_turns, 2)
        battle.submit_player_action(Action.ATTACK)
        self.assertEqual(last_turn(battle)["enemy_final_die"], 1)

    def test_cleanse_skips_unremovable_and_cannot_remove_new_same_turn_status(self) -> None:
        raw = skill("cleanse_then_mark", [
            application(
                "cleanse",
                delivery={"type": "immediate"},
                timing="after_result_apply",
                target="self",
                priority=200,
                effects=[{
                    "category": "status_control",
                    "operation": "remove",
                    "selector": {
                        "type": "polarity",
                        "value": "negative",
                        "order": "oldest",
                    },
                    "count": 5,
                }],
            ),
            application(
                "new_mark",
                delivery=status_delivery("new_mark", duration=2),
                timing="after_result_apply",
                target="self",
                priority=100,
                effects=[{
                    "category": "dice_modifier",
                    "operation": "set_maximum",
                    "value": 4,
                }],
            ),
        ], target="self")
        battle = engine([raw], seed=506)
        battle.player.statuses.extend([
            StatusEffect("locked", 3, 0, removable=False, polarity="negative"),
            StatusEffect("old_mark", 3, 0, removable=True, polarity="negative"),
        ])

        battle.submit_player_intent(TurnIntent(
            "player", Action.ATTACK, "cleanse_then_mark"
        ))

        self.assertEqual(
            [status.name for status in battle.player.statuses],
            ["locked", "new_mark"],
        )

    def test_on_status_apply_timing_runs_after_status_is_stored(self) -> None:
        raw = skill("mark_and_recover", [
            application(
                "mark",
                delivery=status_delivery("focus", duration=2, polarity="positive"),
                timing="after_result_apply",
                target="self",
                effects=[{
                    "category": "dice_modifier",
                    "operation": "set_minimum",
                    "value": 2,
                }],
            ),
            application(
                "status_recovery",
                delivery={"type": "immediate"},
                timing="on_status_apply",
                target="self",
                effects=[{
                    "category": "resource_change",
                    "operation": "add",
                    "resource": "stamina",
                    "value": 7,
                }],
            ),
        ], target="self")
        battle = engine([raw], seed=509)
        battle.player.stamina = 50
        battle.submit_player_intent(TurnIntent(
            "player", Action.ATTACK, "mark_and_recover"
        ))

        effects = last_turn(battle)["effects"]
        recovery = next(
            effect for effect in effects
            if effect.get("application_id") == "status_recovery"
        )
        self.assertEqual(recovery["timing"], "on_status_apply")
        self.assertEqual(recovery["after"], recovery["before"] + 7)


class QueuedDeliveryTests(unittest.TestCase):
    def test_next_win_queue_survives_failure_then_consumes_on_trigger(self) -> None:
        queued = {
            "type": "queued",
            "trigger": {
                "event": "before_result_apply",
                "condition": {
                    "type": "dice_result_is",
                    "subject": "self",
                    "value": "win",
                },
            },
            "expires": {"value": 2, "unit": "owner_turn"},
            "consumes": "on_trigger",
        }
        raw = skill("prepared_strike", [application(
            "next_win_break",
            delivery=queued,
            timing="on_skill_commit",
            target="opponent",
            effects=[{
                "category": "result_modifier",
                "operation": "add",
                "resource": "break_gauge",
                "direction": "dealt",
                "polarity": "increase",
                "value": 9,
            }],
        )], target="opponent")
        battle = engine([raw], seed=3)  # rolls: 2<5, then 5>2

        battle.submit_player_intent(TurnIntent(
            "player", Action.ATTACK, "prepared_strike", "enemy"
        ))
        self.assertEqual(len(battle.player.queued_effects), 1)
        self.assertEqual(battle.player.queued_effects[0].remaining_turns, 2)

        battle.submit_player_action(Action.ATTACK)
        resolution = last_turn(battle)
        self.assertEqual(resolution["dice_result"], "win")
        self.assertEqual(
            resolution["applied_enemy_delta"]["break_gauge"],
            resolution["base_enemy_delta"]["break_gauge"] + 9,
        )
        self.assertEqual(battle.player.queued_effects, [])

    def test_on_successful_apply_waits_when_every_effect_is_blocked(self) -> None:
        queued = {
            "type": "queued",
            "trigger": {"event": "after_result_apply", "condition": None},
            "expires": {"value": 2, "unit": "owner_turn"},
            "consumes": "on_successful_apply",
        }
        raw = skill("blocked_queue", [application(
            "blocked_skill_control",
            delivery=queued,
            timing="on_skill_commit",
            target="opponent",
            effects=[{
                "category": "skill_control",
                "operation": "change_cooldown",
                "selector": {"type": "skill_id", "value": "missing_skill"},
                "value": -1,
            }],
        )], target="opponent")
        battle = engine([raw], seed=510)
        battle.submit_player_intent(TurnIntent(
            "player", Action.ATTACK, "blocked_queue", "enemy"
        ))

        self.assertEqual(len(battle.player.queued_effects), 1)
        blocked = next(
            effect for effect in last_turn(battle)["effects"]
            if effect.get("application_id") == "blocked_skill_control"
            and effect.get("source") == "queued"
        )
        self.assertFalse(blocked["applied"])
        self.assertEqual(blocked["reason"], "skill_not_owned")

    def test_never_consume_queue_can_trigger_more_than_once(self) -> None:
        queued = {
            "type": "queued",
            "trigger": {"event": "after_result_apply", "condition": None},
            "expires": {"value": 2, "unit": "owner_turn"},
            "consumes": "never",
        }
        raw = skill("repeat_queue", [application(
            "repeat_recovery",
            delivery=queued,
            timing="on_skill_commit",
            target="self",
            effects=[{
                "category": "resource_change",
                "operation": "add",
                "resource": "stamina",
                "value": 1,
            }],
        )], target="self")
        battle = engine([raw], seed=511)
        battle.submit_player_intent(TurnIntent(
            "player", Action.ATTACK, "repeat_queue"
        ))
        self.assertEqual(len(battle.player.queued_effects), 1)
        battle.submit_player_action(Action.ATTACK)
        self.assertEqual(len(battle.player.queued_effects), 1)
        queue_logs = [
            event for trace in battle.trace for event in trace["resolution"].get("effects", [])
            if event.get("application_id") == "repeat_recovery"
            and event.get("source") == "queued"
        ]
        self.assertEqual(len(queue_logs), 2)

    def test_queue_expires_during_down_wait_owner_turns(self) -> None:
        queued = {
            "type": "queued",
            "trigger": {"event": "before_result_apply", "condition": None},
            "expires": {"value": 1, "unit": "owner_turn"},
            "consumes": "never",
        }
        raw = skill("waiting_queue", [application(
            "wait_one_turn",
            delivery=queued,
            timing="on_skill_commit",
            target="self",
            effects=[{
                "category": "resource_change",
                "operation": "add",
                "resource": "stamina",
                "value": 1,
            }],
        )], target="self")
        battle = engine([raw], seed=507)
        battle.submit_player_intent(TurnIntent(
            "player", Action.ATTACK, "waiting_queue"
        ))
        self.assertEqual(len(battle.player.queued_effects), 1)

        battle.enemy.is_down = True
        battle.enemy.skipped_turns_remaining = 2
        battle.play_turn()
        self.assertEqual(battle.player.queued_effects, [])


if __name__ == "__main__":
    unittest.main()
