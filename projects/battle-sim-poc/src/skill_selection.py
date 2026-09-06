"""Skill-only policies: no engine access, action rerolls, effects or opponent intent."""

from dataclasses import dataclass
import random
from typing import Callable

from easy_enemy_profiles import EASY_ENEMY_PROFILES


SKILL_POLICY_NAMES = ("none", "random", *EASY_ENEMY_PROFILES)


@dataclass(frozen=True)
class SkillDecision:
    selected_skill_id: str | None
    planned_skill_id: str | None
    reason: str
    issues: tuple[str, ...] = ()


def skill_target_id(target: str, actor_id: str) -> str:
    opponent = "enemy" if actor_id == "player" else "player"
    return {"self": actor_id, "opponent": opponent, "both": "both"}[target]


def choose_skill(
    policy: str,
    *,
    action: str,
    action_number: int,
    equipped_skill_ids: tuple[str, ...],
    validate: Callable[[str], tuple[str, ...]],
    rng: random.Random,
) -> SkillDecision:
    """validate reports hard constraints only; the action has already been chosen."""
    if policy == "none":
        return SkillDecision(None, None, "disabled")
    if policy == "random":
        # Equal weight per legal skill AND no skill. No strategic effectiveness check.
        legal = tuple(skill for skill in equipped_skill_ids if not validate(skill))
        if not legal:
            return SkillDecision(None, None, "no_legal_skill")
        skill = rng.choice((None, *legal))
        return SkillDecision(skill, skill, "random_selected" if skill else "random_no_skill")
    profile = EASY_ENEMY_PROFILES[policy]
    planned = profile.planned_skill(action_number, action)
    if planned is None:
        return SkillDecision(None, None, "basic_slot")
    issues = validate(planned)
    if issues:
        return SkillDecision(None, planned, "unavailable", issues)
    return SkillDecision(planned, planned, "scheduled")
