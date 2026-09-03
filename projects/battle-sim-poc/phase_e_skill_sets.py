"""Preserved levelled skill data and comparison loadouts; no skill-selection AI."""

from __future__ import annotations

from typing import Any, Mapping

from battle_sim import OwnedSkill
from skill_schema import SkillDefinition, load_skill_definitions


def _level(
    level: int,
    *,
    cost: int,
    cooldown: int,
    allowed_actions: list[str],
    application: dict[str, Any],
) -> dict[str, Any]:
    return {
        "level": level,
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
        "usage_limit": {"per_match": None, "per_round": None},
        "requirements": {
            "allowed_actions": allowed_actions,
            "condition": None,
        },
        "applications": [application],
    }


def _skill(
    skill_id: str,
    name: str,
    description: str,
    *,
    tags: list[str],
    target: str,
    levels: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "id": skill_id,
        "name": name,
        "description": description,
        "tags": ["phase_e", *tags],
        "max_level": len(levels),
        "targeting": {"type": target, "selection_required": False},
        "levels": levels,
        "ui": {
            "icon": None,
            "short_description": description,
            "show_exact_values": True,
        },
    }


def _strike_level(level: int, cost: int, multiplier: float) -> dict[str, Any]:
    return _level(
        level,
        cost=cost,
        cooldown=2,
        allowed_actions=["attack"],
        application={
            "id": "measured_damage",
            "delivery": {"type": "immediate"},
            "timing": "before_result_apply",
            "target": "opponent",
            "condition": None,
            "priority": 100,
            "effects": [{
                "category": "result_modifier",
                "operation": "multiply",
                "resource": "hp",
                "direction": "dealt",
                "polarity": "damage",
                "value": multiplier,
            }],
        },
    )


def _focus_level(
    level: int, cost: int, duration: int, minimum: int
) -> dict[str, Any]:
    return _level(
        level,
        cost=cost,
        cooldown=2,
        allowed_actions=["defend"],
        application={
            "id": "growth_focus",
            "delivery": {
                "type": "status",
                "status": {
                    "id": "growth_focus",
                    "name": "성장 집중",
                    "duration": {
                        "value": duration,
                        "unit": "owner_turn",
                        "starts": "next_owner_turn",
                    },
                    "stacking": {"mode": "refresh", "max_stacks": 1},
                    "removable": True,
                    "polarity": "positive",
                },
            },
            "timing": "before_dice_compare",
            "target": "self",
            "condition": None,
            "priority": 100,
            "effects": [{
                "category": "dice_modifier",
                "operation": "set_minimum",
                "value": minimum,
            }],
        },
    )


def _momentum_level(
    level: int, cost: int, expires: int, break_value: int
) -> dict[str, Any]:
    return _level(
        level,
        cost=cost,
        cooldown=3,
        allowed_actions=["attack"],
        application={
            "id": "growth_next_win_break",
            "delivery": {
                "type": "queued",
                "trigger": {
                    "event": "before_result_apply",
                    "condition": {
                        "type": "dice_result_is",
                        "subject": "self",
                        "value": "win",
                    },
                },
                "expires": {"value": expires, "unit": "owner_turn"},
                "consumes": "on_trigger",
            },
            "timing": "on_skill_commit",
            "target": "opponent",
            "condition": None,
            "priority": 100,
            "effects": [{
                "category": "result_modifier",
                "operation": "add",
                "resource": "break_gauge",
                "direction": "dealt",
                "polarity": "increase",
                "value": break_value,
            }],
        },
    )


PHASE_E_SKILLS: tuple[dict[str, Any], ...] = (
    _skill(
        "measured_strike",
        "메저드 스트라이크",
        "레벨에 따라 공격 HP 피해 배율이 성장한다.",
        tags=["attack", "result_modifier"],
        target="opponent",
        levels=[
            _strike_level(1, 8, 1.12),
            _strike_level(2, 10, 1.16),
            _strike_level(3, 12, 1.20),
        ],
    ),
    _skill(
        "growth_focus",
        "그로스 포커스",
        "레벨에 따라 지속시간과 다음 턴 주사위 최솟값이 성장한다.",
        tags=["control", "status", "positive"],
        target="self",
        levels=[
            _focus_level(1, 7, 1, 2),
            _focus_level(2, 8, 2, 3),
            _focus_level(3, 9, 2, 4),
        ],
    ),
    _skill(
        "banked_pressure",
        "뱅크드 프레셔",
        "레벨에 따라 다음 승리 예약의 만료와 추가 BRK가 성장한다.",
        tags=["attack", "break", "queued"],
        target="opponent",
        levels=[
            _momentum_level(1, 8, 2, 4),
            _momentum_level(2, 9, 3, 6),
            _momentum_level(3, 10, 3, 8),
        ],
    ),
)


PHASE_E_GROWTH_LADDER: Mapping[str, tuple[OwnedSkill, ...]] = {
    "no_skill": (),
    "low_single": (OwnedSkill("measured_strike", 1),),
    "high_single": (OwnedSkill("measured_strike", 3),),
    "multi_skill": (
        OwnedSkill("measured_strike", 3),
        OwnedSkill("growth_focus", 3),
        OwnedSkill("banked_pressure", 3),
    ),
}


def load_phase_e_skill_registry() -> Mapping[str, SkillDefinition]:
    return load_skill_definitions(PHASE_E_SKILLS)
