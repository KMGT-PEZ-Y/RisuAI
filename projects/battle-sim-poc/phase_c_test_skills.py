"""Small, data-driven active-skill catalog for the Phase C UI testbed."""

from __future__ import annotations

from typing import Any


def _application(
    application_id: str,
    *,
    timing: str,
    target: str,
    effects: list[dict[str, Any]],
    condition: dict[str, Any] | None = None,
    priority: int = 100,
) -> dict[str, Any]:
    return {
        "id": application_id,
        "delivery": {"type": "immediate"},
        "timing": timing,
        "target": target,
        "condition": condition,
        "priority": priority,
        "effects": effects,
    }


def _skill(
    skill_id: str,
    name: str,
    description: str,
    *,
    tags: list[str],
    target: str,
    allowed_actions: list[str],
    cost: int,
    cooldown: int,
    applications: list[dict[str, Any]],
    per_match: int | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "id": skill_id,
        "name": name,
        "description": description,
        "tags": tags,
        "max_level": 1,
        "targeting": {"type": target, "selection_required": False},
        "levels": [{
            "level": 1,
            "costs": [{
                "resource": "stamina",
                "amount": cost,
                "minimum_remaining": 0,
            }],
            "cooldown": {
                "turns": cooldown,
                "starts": "on_skill_commit",
                "decrements": "owner_turn",
            },
            "usage_limit": {"per_match": per_match, "per_round": None},
            "requirements": {
                "allowed_actions": allowed_actions,
                "condition": None,
            },
            "applications": applications,
        }],
        "ui": {
            "icon": None,
            "short_description": description,
            "show_exact_values": True,
        },
    }


PHASE_C_TEST_SKILLS: tuple[dict[str, Any], ...] = (
    _skill(
        "second_wind",
        "세컨드 윈드",
        "결과 적용 후 자신의 HP를 8 회복한다.",
        tags=["resource_change", "recovery"],
        target="self",
        allowed_actions=["attack", "defend", "evade"],
        cost=8,
        cooldown=2,
        applications=[_application(
            "recover_hp",
            timing="after_result_apply",
            target="self",
            effects=[{
                "category": "resource_change",
                "operation": "add",
                "resource": "hp",
                "value": 8,
            }],
        )],
    ),
    _skill(
        "power_drive",
        "파워 드라이브",
        "공격 주사위 승리 시 상대 HP 피해를 1.25배로 만든다.",
        tags=["result_modifier", "attack"],
        target="opponent",
        allowed_actions=["attack"],
        cost=14,
        cooldown=2,
        per_match=3,
        applications=[_application(
            "amplify_hp_damage",
            timing="before_result_apply",
            target="opponent",
            condition={
                "type": "dice_result_is",
                "subject": "self",
                "value": "win",
            },
            effects=[{
                "category": "result_modifier",
                "operation": "multiply",
                "resource": "hp",
                "direction": "dealt",
                "polarity": "damage",
                "value": 1.25,
            }],
        )],
    ),
    _skill(
        "steady_form",
        "스테디 폼",
        "자신의 최종 주사위 최솟값을 4로 제한한다.",
        tags=["dice_modifier", "control"],
        target="self",
        allowed_actions=["attack", "defend", "evade"],
        cost=12,
        cooldown=3,
        applications=[_application(
            "set_die_minimum",
            timing="before_dice_compare",
            target="self",
            effects=[{
                "category": "dice_modifier",
                "operation": "set_minimum",
                "value": 4,
            }],
        )],
    ),
    _skill(
        "read_the_play",
        "리드 더 플레이",
        "상대의 이번 행동을 방어로 강제한다.",
        tags=["action_control", "tactics"],
        target="opponent",
        allowed_actions=["evade"],
        cost=20,
        cooldown=4,
        per_match=2,
        applications=[_application(
            "force_defend",
            timing="before_action_reveal",
            target="opponent",
            priority=200,
            effects=[{
                "category": "action_control",
                "operation": "force",
                "action": "defend",
            }],
        )],
    ),
    _skill(
        "reset_rhythm",
        "리듬 리셋",
        "자신에게 미리 부여된 흔들림 상태를 하나 제거한다.",
        tags=["status_control", "cleanse"],
        target="self",
        allowed_actions=["defend"],
        cost=6,
        cooldown=2,
        applications=[_application(
            "remove_shaken",
            timing="after_result_apply",
            target="self",
            effects=[{
                "category": "status_control",
                "operation": "remove",
                "selector": {"type": "status_id", "value": "shaken"},
                "count": 1,
            }],
        )],
    ),
    _skill(
        "breathing_control",
        "호흡 조절",
        "숨고르기의 남은 지속시간을 2턴 줄인다.",
        tags=["status_control", "duration"],
        target="self",
        allowed_actions=["defend", "evade"],
        cost=5,
        cooldown=1,
        applications=[_application(
            "shorten_breath_status",
            timing="after_result_apply",
            target="self",
            effects=[{
                "category": "status_control",
                "operation": "change_duration",
                "selector": {
                    "type": "status_id",
                    "value": "short_of_breath",
                },
                "value": -2,
            }],
        )],
    ),
    _skill(
        "reserve_plan",
        "리저브 플랜",
        "다음에 사용할 액티브 스킬의 STA 비용을 5 줄인다.",
        tags=["skill_control", "cost"],
        target="self",
        allowed_actions=["attack", "defend", "evade"],
        cost=4,
        cooldown=3,
        applications=[_application(
            "discount_next_skill",
            timing="after_result_apply",
            target="self",
            effects=[{
                "category": "skill_control",
                "operation": "modify_cost",
                "selector": {"type": "next_used_skill"},
                "resource": "stamina",
                "value": -5,
            }],
        )],
    ),
    _skill(
        "sideline_coaching",
        "사이드라인 코칭",
        "파워 드라이브의 쿨다운을 2 줄이고 사용 횟수를 1 늘린다.",
        tags=["skill_control", "cooldown", "charges"],
        target="self",
        allowed_actions=["defend"],
        cost=9,
        cooldown=3,
        applications=[_application(
            "refresh_power_drive",
            timing="after_result_apply",
            target="self",
            effects=[
                {
                    "category": "skill_control",
                    "operation": "change_cooldown",
                    "selector": {"type": "skill_id", "value": "power_drive"},
                    "value": -2,
                },
                {
                    "category": "skill_control",
                    "operation": "change_charges",
                    "selector": {"type": "skill_id", "value": "power_drive"},
                    "value": 1,
                },
            ],
        )],
    ),
)

