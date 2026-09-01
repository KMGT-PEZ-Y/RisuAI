"""Data-driven status and queued-effect skills for the Phase D UI testbed."""

from __future__ import annotations

from typing import Any


def _status_delivery(
    status_id: str,
    name: str,
    *,
    duration: int,
    mode: str = "refresh",
    removable: bool = True,
    polarity: str,
) -> dict[str, Any]:
    return {
        "type": "status",
        "status": {
            "id": status_id,
            "name": name,
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


def _application(
    application_id: str,
    *,
    delivery: dict[str, Any],
    timing: str,
    target: str,
    effects: list[dict[str, Any]],
    condition: dict[str, Any] | None = None,
    priority: int = 100,
) -> dict[str, Any]:
    return {
        "id": application_id,
        "delivery": delivery,
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


PHASE_D_TEST_SKILLS: tuple[dict[str, Any], ...] = (
    _skill(
        "shaking_feint",
        "셰이킹 페인트",
        "상대에게 2턴 흔들림을 부여한다. 다음 턴부터 최종 주사위가 최대 3이다.",
        tags=["phase_d", "status", "dice_modifier", "negative"],
        target="opponent",
        allowed_actions=["evade"],
        cost=11,
        cooldown=3,
        applications=[_application(
            "apply_shaken",
            delivery=_status_delivery(
                "shaken", "흔들림", duration=2, polarity="negative"
            ),
            timing="before_dice_compare",
            target="opponent",
            effects=[{
                "category": "dice_modifier",
                "operation": "set_maximum",
                "value": 3,
            }],
        )],
    ),
    _skill(
        "open_guard",
        "오픈 가드",
        "상대에게 2턴 노출을 부여한다. 다음 턴부터 받는 HP 피해가 1.2배다.",
        tags=["phase_d", "status", "result_modifier", "negative"],
        target="opponent",
        allowed_actions=["attack"],
        cost=15,
        cooldown=3,
        per_match=3,
        applications=[_application(
            "apply_exposed",
            delivery=_status_delivery(
                "exposed", "노출", duration=2, mode="replace", polarity="negative"
            ),
            timing="before_result_apply",
            target="opponent",
            effects=[{
                "category": "result_modifier",
                "operation": "multiply",
                "resource": "hp",
                "direction": "received",
                "polarity": "damage",
                "value": 1.2,
            }],
        )],
    ),
    _skill(
        "focused_guard",
        "포커스드 가드",
        "자신에게 2턴 집중을 부여한다. 다음 턴부터 최종 주사위가 최소 3이다.",
        tags=["phase_d", "status", "dice_modifier", "positive"],
        target="self",
        allowed_actions=["defend"],
        cost=10,
        cooldown=3,
        applications=[_application(
            "apply_focus",
            delivery=_status_delivery(
                "focus", "집중", duration=2, polarity="positive"
            ),
            timing="before_dice_compare",
            target="self",
            effects=[{
                "category": "dice_modifier",
                "operation": "set_minimum",
                "value": 3,
            }],
        )],
    ),
    _skill(
        "purge_negative",
        "네거티브 퍼지",
        "결과 적용 후 가장 오래된 제거 가능 디버프 하나를 정화한다.",
        tags=["phase_d", "status_control", "cleanse"],
        target="self",
        allowed_actions=["defend", "evade"],
        cost=7,
        cooldown=2,
        applications=[_application(
            "cleanse_oldest_negative",
            delivery={"type": "immediate"},
            timing="after_result_apply",
            target="self",
            effects=[{
                "category": "status_control",
                "operation": "remove",
                "selector": {
                    "type": "polarity",
                    "value": "negative",
                    "order": "oldest",
                },
                "count": 1,
            }],
        )],
    ),
    _skill(
        "stored_momentum",
        "스토어드 모멘텀",
        "3턴 안의 다음 주사위 승리 1회에 상대 BRK를 8 추가 축적한다.",
        tags=["phase_d", "queued", "result_modifier", "on_trigger"],
        target="opponent",
        allowed_actions=["attack"],
        cost=12,
        cooldown=3,
        per_match=3,
        applications=[_application(
            "next_win_break",
            delivery={
                "type": "queued",
                "trigger": {
                    "event": "before_result_apply",
                    "condition": {
                        "type": "dice_result_is",
                        "subject": "self",
                        "value": "win",
                    },
                },
                "expires": {"value": 3, "unit": "owner_turn"},
                "consumes": "on_trigger",
            },
            timing="on_skill_commit",
            target="opponent",
            effects=[{
                "category": "result_modifier",
                "operation": "add",
                "resource": "break_gauge",
                "direction": "dealt",
                "polarity": "increase",
                "value": 8,
            }],
        )],
    ),
    _skill(
        "recovery_echo",
        "리커버리 에코",
        "이번 결과와 다음 2턴의 결과 적용 후 HP를 3씩 회복하는 예약 효과를 둔다.",
        tags=["phase_d", "queued", "resource_change", "never"],
        target="self",
        allowed_actions=["defend"],
        cost=9,
        cooldown=4,
        applications=[_application(
            "repeat_recovery",
            delivery={
                "type": "queued",
                "trigger": {"event": "after_result_apply", "condition": None},
                "expires": {"value": 2, "unit": "owner_turn"},
                "consumes": "never",
            },
            timing="on_skill_commit",
            target="self",
            effects=[{
                "category": "resource_change",
                "operation": "add",
                "resource": "hp",
                "value": 3,
            }],
        )],
    ),
)
