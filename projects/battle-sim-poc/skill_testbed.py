"""Non-visual helpers shared by the Phase C-D skill testbed and its tests."""

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
from phase_d_test_skills import PHASE_D_TEST_SKILLS
from skill_schema import SkillDefinition, Target, load_skill_definitions


MAX_EQUIPPED_SKILLS = 4
TEST_STATUS_NAMES = {
    "shaken": "흔들림",
    "short_of_breath": "숨고르기",
    "exposed": "노출",
    "focus": "집중",
}


def load_test_skill_registry() -> Mapping[str, SkillDefinition]:
    return load_skill_definitions((*PHASE_C_TEST_SKILLS, *PHASE_D_TEST_SKILLS))


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
            StatusEffect(
                "shaken", 4, 0,
                display_name="흔들림", polarity="negative",
            ),
            StatusEffect(
                "short_of_breath", 5, 0,
                display_name="숨고르기", polarity="negative",
            ),
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
    actor_index: int = 0,
) -> float:
    actor = engine.characters[actor_index]
    resolved = engine._owned_skill(actor, skill_id)
    if resolved is None:
        raise ValueError(f"actor does not own skill {skill_id!r}")
    _, definition, level = resolved
    base_cost = next(
        (cost.amount for cost in level.costs if cost.resource.value == "stamina"),
        0,
    )
    return engine._effective_skill_cost(
        actor, definition.skill_id, "stamina", base_cost
    )


def status_runtime_text(character) -> str:
    parts = []
    for status in character.statuses:
        name = status.display_name or TEST_STATUS_NAMES.get(status.name, status.name)
        removable = "정화 가능" if status.removable else "정화 불가"
        parts.append(
            f"{name} [{status.polarity}, {removable}] {status.remaining_turns}턴"
        )
    return ", ".join(parts) if parts else "없음"


def queued_runtime_text(character) -> str:
    parts = []
    for queued in character.queued_effects:
        trigger = queued.application.delivery.trigger
        event = trigger.event.value if trigger is not None else "?"
        parts.append(
            f"{queued.queue_id} [{event}, {queued.consumes}] "
            f"만료 {queued.remaining_turns}턴"
        )
    return ", ".join(parts) if parts else "없음"

