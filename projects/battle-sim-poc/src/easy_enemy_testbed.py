"""Factories for manual play and equal-loadout random-player comparisons."""

from battle_sim import BattleEngine, ManualBattleEngine, OwnedSkill
from easy_enemy_profiles import EASY_ENEMY_PROFILES
from easy_enemy_skills import load_easy_skill_registry


MAX_PLAYER_SKILLS = 3


def enemy_loadout(enemy_strategy: str) -> tuple[OwnedSkill, ...]:
    if enemy_strategy not in EASY_ENEMY_PROFILES:
        raise ValueError(f"unknown easy enemy: {enemy_strategy!r}")
    return tuple(OwnedSkill(skill_id, 1) for skill_id in EASY_ENEMY_PROFILES[enemy_strategy].skill_ids)


def create_easy_testbed_engine(
    seed: int, *, enemy_strategy: str, equipped_skill_ids,
    add_test_statuses: bool = False,
) -> ManualBattleEngine:
    if add_test_statuses:
        raise ValueError("the easy-enemy testbed starts without artificial statuses")
    enemy_skills = enemy_loadout(enemy_strategy)
    skill_ids = tuple(equipped_skill_ids)
    if len(skill_ids) > MAX_PLAYER_SKILLS:
        raise ValueError("at most 3 skills may be equipped")
    return ManualBattleEngine(
        seed, enemy_strategy=enemy_strategy, skill_registry=load_easy_skill_registry(),
        player_skills=tuple(OwnedSkill(skill_id, 1) for skill_id in skill_ids),
        enemy_skills=enemy_skills, enemy_skill_policy=enemy_strategy,
    )


def create_random_player_match(
    seed: int, *, enemy_strategy: str, trace_enabled: bool = False,
    max_rounds: int = 100, registry=None,
) -> BattleEngine:
    loadout = enemy_loadout(enemy_strategy)
    return BattleEngine(
        seed, max_rounds=max_rounds, trace_enabled=trace_enabled,
        player_strategy="random", enemy_strategy=enemy_strategy,
        skill_registry=registry if registry is not None else load_easy_skill_registry(),
        player_skills=loadout, enemy_skills=loadout,
        player_skill_policy="random", enemy_skill_policy=enemy_strategy,
    )
