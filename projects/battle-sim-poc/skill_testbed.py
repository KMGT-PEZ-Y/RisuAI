"""Non-visual helpers shared by the Phase C skill testbed and its tests."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from battle_sim import (
    Action,
    ManualBattleEngine,
    OwnedSkill,
    StatusEffect,
    TurnIntent,
)
from phase_c_test_skills import PHASE_C_TEST_SKILLS
from skill_schema import SkillDefinition, Target, load_skill_definitions


MAX_EQUIPPED_SKILLS = 4
TEST_STATUS_NAMES = {
    "shaken": "흔들림",
    "short_of_breath": "숨고르기",
}


def load_test_skill_registry() -> Mapping[str, SkillDefinition]:
    return load_skill_definitions(PHASE_C_TEST_SKILLS)


def create_testbed_engine(
    seed: int,
    *,
    enemy_strategy: str,
    equipped_skill_ids: Iterable[str],
    add_test_statuses: bool = True,
) -> ManualBattleEngine:
    registry = load_test_skill_registry()
    skill_ids = tuple(equipped_skill_ids)
    if len(skill_ids) > MAX_EQUIPPED_SKILLS:
        raise ValueError(f"at most {MAX_EQUIPPED_SKILLS} skills may be equipped")
    if len(skill_ids) != len(set(skill_ids)):
        raise ValueError("equipped skills must be unique")
    unknown = [skill_id for skill_id in skill_ids if skill_id not in registry]
    if unknown:
        raise ValueError(f"unknown test skill: {unknown[0]!r}")

    engine = ManualBattleEngine(
        seed,
        enemy_strategy=enemy_strategy,
        skill_registry=registry,
        player_skills=tuple(OwnedSkill(skill_id, 1) for skill_id in skill_ids),
        enemy_skills=(),
    )
    if add_test_statuses:
        engine.player.statuses.extend((
            StatusEffect("shaken", 4, 0),
            StatusEffect("short_of_breath", 5, 0),
        ))
    return engine


def target_id_for_skill(definition: SkillDefinition) -> str:
    return {
        Target.SELF: "player",
        Target.OPPONENT: "enemy",
        Target.BOTH: "both",
    }[definition.targeting.type]


def make_player_intent(
    action: Action,
    skill_id: str | None,
    registry: Mapping[str, SkillDefinition],
) -> TurnIntent:
    if skill_id is None:
        return TurnIntent("player", action)
    definition = registry.get(skill_id)
    if definition is None:
        raise ValueError(f"unknown test skill: {skill_id!r}")
    return TurnIntent(
        "player",
        action,
        skill_id,
        target_id_for_skill(definition),
    )


def effective_stamina_cost(
    engine: ManualBattleEngine,
    skill_id: str,
) -> float:
    resolved = engine._owned_skill(engine.player, skill_id)
    if resolved is None:
        raise ValueError(f"player does not own skill {skill_id!r}")
    _, definition, level = resolved
    base_cost = next(
        (cost.amount for cost in level.costs if cost.resource.value == "stamina"),
        0,
    )
    return engine._effective_skill_cost(
        engine.player, definition.skill_id, "stamina", base_cost
    )

