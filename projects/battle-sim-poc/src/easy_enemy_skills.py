"""Approved level-1 easy-enemy skills, independent of automatic selection."""

from skill_schema import load_skill_definitions


POWER_STRIKE = "rookie_power_strike"
RECOVERY_FORM = "rookie_recovery_form"
SAFE_FOOTWORK = "rookie_safe_footwork"
CREATE_DISTANCE = "rookie_create_distance"
TUCK_CHIN = "rookie_tuck_chin"


def _skill(skill_id, name, description, action, target, resource, polarity, value):
    return {
        "schema_version": 1,
        "id": skill_id,
        "name": name,
        "description": description,
        "tags": ["easy_enemy", action],
        "max_level": 1,
        "targeting": {"type": target, "selection_required": False},
        "levels": [{
            "level": 1,
            "costs": [{"resource": "stamina", "amount": 8, "minimum_remaining": 0}],
            "cooldown": {"turns": 0, "starts": "on_skill_commit", "decrements": "owner_turn"},
            "usage_limit": {"per_match": None, "per_round": None},
            "requirements": {"allowed_actions": [action], "condition": None},
            "applications": [{
                "id": "modify_current_result",
                "delivery": {"type": "immediate"},
                "timing": "before_result_apply",
                "target": target,
                "priority": 100,
                "condition": {
                    "type": "result_delta_is",
                    "subject": target,
                    "resource": resource,
                    "comparison": "less_than" if polarity == "damage" else "greater_than",
                    "value": 0,
                },
                "effects": [{
                    "category": "result_modifier",
                    "operation": "multiply",
                    "resource": resource,
                    "direction": "dealt" if target == "opponent" else "self",
                    "polarity": polarity,
                    "value": value,
                }],
            }],
        }],
        "ui": {"icon": None, "short_description": description, "show_exact_values": True},
    }


EASY_ENEMY_SKILLS = (
    _skill(POWER_STRIKE, "힘주어 치기", "이번 공격이 주는 HP 피해 20% 증가. 피해가 없으면 효과 없음.",
           "attack", "opponent", "hp", "damage", 1.2),
    _skill(RECOVERY_FORM, "자세 정비", "이번 방어로 얻는 HP 회복량 50% 증가. 회복이 없으면 효과 없음.",
           "defend", "self", "hp", "recovery", 1.5),
    _skill(SAFE_FOOTWORK, "안전한 발놀림", "이번 회피 중 받는 HP 피해 20% 감소. 다음 턴에는 유지되지 않음.",
           "evade", "self", "hp", "damage", 0.8),
    _skill(CREATE_DISTANCE, "거리 확보", "이번 회피 중 자신에게 쌓이는 BRK 20% 감소. HP 피해는 줄이지 않음.",
           "evade", "self", "break_gauge", "increase", 0.8),
    _skill(TUCK_CHIN, "턱 당기기", "이번 공격 중 받는 HP 피해 20% 감소. 다음 공격까지 보호하지 않음.",
           "attack", "self", "hp", "damage", 0.8),
)


def load_easy_skill_registry():
    return load_skill_definitions(EASY_ENEMY_SKILLS)
