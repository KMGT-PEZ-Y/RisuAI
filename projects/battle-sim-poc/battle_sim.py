"""Round/turn battle POC simulation engine.

The implementation follows:
- ROUND_TURN_BATTLE_POC_RULEBOOK.md v0.6
- BASIC_RESULT_TABLE_DRAFT_V0.1.md (document version 0.4)

The symmetric 1v1 core also hosts the Phase A-D active-skill, status, and
queued-effect runtime while preserving the original no-skill path.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from enum import Enum
import math
import random
from typing import Any, Iterable, Mapping

from skill_schema import (
    ActionControlOperation,
    Condition,
    ConditionKind,
    CooldownDecrement,
    CooldownStart,
    DeliveryType,
    DiceModifierOperation,
    DurationStart,
    DurationUnit,
    EffectCategory,
    QueuedConsume,
    ResourceChangeOperation,
    ResultModifierOperation,
    SkillDefinition,
    SkillControlOperation,
    SkillLevel,
    StatusControlOperation,
    Target,
    Timing,
)


class Action(str, Enum):
    ATTACK = "attack"
    DEFEND = "defend"
    EVADE = "evade"


class DiceResult(str, Enum):
    WIN = "win"
    DRAW = "draw"
    LOSE = "lose"


@dataclass(frozen=True)
class Delta:
    hp: int = 0
    stamina: int = 0
    break_gauge: int = 0


@dataclass(frozen=True)
class ResultEntry:
    entry_id: str
    player: Delta
    enemy: Delta


def _d(hp: int = 0, stamina: int = 0, break_gauge: int = 0) -> Delta:
    return Delta(hp, stamina, break_gauge)


# Player action, Enemy action, dice comparison -> simultaneous deltas.
RESULT_TABLE: dict[tuple[Action, Action, DiceResult], ResultEntry] = {
    (Action.ATTACK, Action.ATTACK, DiceResult.WIN): ResultEntry("01", _d(-10, -7, 12), _d(-28, -16, 22)),
    (Action.ATTACK, Action.ATTACK, DiceResult.DRAW): ResultEntry("02", _d(-36, -20, 24), _d(-36, -20, 24)),
    (Action.ATTACK, Action.ATTACK, DiceResult.LOSE): ResultEntry("03", _d(-28, -16, 22), _d(-10, -7, 12)),
    (Action.ATTACK, Action.DEFEND, DiceResult.WIN): ResultEntry("04", _d(), _d(-28, -16, 20)),
    (Action.ATTACK, Action.DEFEND, DiceResult.DRAW): ResultEntry("05", _d(0, -10, 14), _d(8, 14, -12)),
    (Action.ATTACK, Action.DEFEND, DiceResult.LOSE): ResultEntry("06", _d(0, -16, 20), _d(12, 22, -18)),
    (Action.ATTACK, Action.EVADE, DiceResult.WIN): ResultEntry("07", _d(), _d(-36, -18, 22)),
    (Action.ATTACK, Action.EVADE, DiceResult.DRAW): ResultEntry("08", _d(), _d(-24, -12, 16)),
    (Action.ATTACK, Action.EVADE, DiceResult.LOSE): ResultEntry("09", _d(-32, 0, 24), _d()),
    (Action.DEFEND, Action.ATTACK, DiceResult.WIN): ResultEntry("10", _d(12, 22, -18), _d(0, -16, 20)),
    (Action.DEFEND, Action.ATTACK, DiceResult.DRAW): ResultEntry("11", _d(8, 14, -12), _d(0, -10, 14)),
    (Action.DEFEND, Action.ATTACK, DiceResult.LOSE): ResultEntry("12", _d(-28, -16, 20), _d()),
    (Action.DEFEND, Action.DEFEND, DiceResult.WIN): ResultEntry("13", _d(10, 18, -16), _d(4, 8, -8)),
    (Action.DEFEND, Action.DEFEND, DiceResult.DRAW): ResultEntry("14", _d(0, 0, 35), _d(0, 0, 35)),
    (Action.DEFEND, Action.DEFEND, DiceResult.LOSE): ResultEntry("15", _d(4, 8, -8), _d(10, 18, -16)),
    (Action.DEFEND, Action.EVADE, DiceResult.WIN): ResultEntry("16", _d(10, 18, -16), _d(-12, 0, 10)),
    (Action.DEFEND, Action.EVADE, DiceResult.DRAW): ResultEntry("17", _d(-24, 0, 18), _d()),
    (Action.DEFEND, Action.EVADE, DiceResult.LOSE): ResultEntry("18", _d(-40, 0, 28), _d()),
    (Action.EVADE, Action.ATTACK, DiceResult.WIN): ResultEntry("19", _d(), _d(-32, 0, 24)),
    (Action.EVADE, Action.ATTACK, DiceResult.DRAW): ResultEntry("20", _d(-24, -12, 16), _d()),
    (Action.EVADE, Action.ATTACK, DiceResult.LOSE): ResultEntry("21", _d(-36, -18, 22), _d()),
    (Action.EVADE, Action.DEFEND, DiceResult.WIN): ResultEntry("22", _d(), _d(-40, 0, 28)),
    (Action.EVADE, Action.DEFEND, DiceResult.DRAW): ResultEntry("23", _d(), _d(-24, 0, 18)),
    (Action.EVADE, Action.DEFEND, DiceResult.LOSE): ResultEntry("24", _d(-12, 0, 10), _d(10, 18, -16)),
    (Action.EVADE, Action.EVADE, DiceResult.WIN): ResultEntry("25", _d(), _d(-20, 0, 18)),
    (Action.EVADE, Action.EVADE, DiceResult.DRAW): ResultEntry("26", _d(0, -30, 0), _d(0, -30, 0)),
    (Action.EVADE, Action.EVADE, DiceResult.LOSE): ResultEntry("27", _d(-20, 0, 18), _d()),
}


# Values are already floor(same-action Dice Win core effect * 1.5).
GROGGY_TABLE: dict[Action, ResultEntry] = {
    Action.ATTACK: ResultEntry("G01", _d(), _d(-42, -24, 33)),
    Action.DEFEND: ResultEntry("G02", _d(15, 27, -24), _d()),
    Action.EVADE: ResultEntry("G03", _d(), _d(-30, 0, 27)),
}


ACTION_LABELS = {
    Action.ATTACK: "공격",
    Action.DEFEND: "방어",
    Action.EVADE: "회피",
}

ACTION_OBJECT_LABELS = {
    Action.ATTACK: "공격을",
    Action.DEFEND: "방어를",
    Action.EVADE: "회피를",
}

DICE_RESULT_LABELS = {
    DiceResult.WIN: "플레이어 주사위 승리",
    DiceResult.DRAW: "주사위 동률",
    DiceResult.LOSE: "적 주사위 승리",
}

RESULT_CONCEPTS = {
    "01": "플레이어가 타격전에서 우세했지만 적도 약한 유효타를 적중시켰습니다.",
    "02": "동시에 주먹이 꽂히는 크로스 펀치가 발생했습니다.",
    "03": "적이 타격전에서 우세했지만 플레이어도 약한 유효타를 적중시켰습니다.",
    "04": "플레이어의 공격이 적의 가드를 관통했습니다.",
    "05": "적이 공격을 부분적으로 차단하고 자세를 정비했습니다.",
    "06": "적이 공격을 완전히 막아 플레이어의 자원만 소모시켰습니다.",
    "07": "플레이어가 적의 회피 경로를 읽고 강한 공격을 적중시켰습니다.",
    "08": "플레이어가 움직이는 적을 포착해 공격을 적중시켰습니다.",
    "09": "적이 공격을 피한 뒤 대형 카운터를 적중시켰습니다.",
    "10": "플레이어가 공격을 완전히 막고 자세를 정비했습니다.",
    "11": "플레이어가 공격을 부분적으로 차단하고 자세를 정비했습니다.",
    "12": "적의 공격이 플레이어의 가드를 관통했습니다.",
    "13": "양측이 방어하는 동안 플레이어가 더 안정적으로 정비했습니다.",
    "14": "클린치·그래플링 싸움이 이어져 양측의 브레이크가 크게 축적됐습니다.",
    "15": "양측이 방어하는 동안 적이 더 안정적으로 정비했습니다.",
    "16": "플레이어가 카운터 시도를 흘리고 안전하게 정비했습니다.",
    "17": "적이 방어 자세의 빈틈에 중형 카운터를 적중시켰습니다.",
    "18": "적이 방어 자세의 빈틈에 대형 카운터를 적중시켰습니다.",
    "19": "플레이어가 공격을 피한 뒤 대형 카운터를 적중시켰습니다.",
    "20": "적이 플레이어의 회피 움직임을 포착해 공격했습니다.",
    "21": "적이 회피 경로를 읽고 강한 공격을 적중시켰습니다.",
    "22": "플레이어가 방어 자세의 빈틈에 대형 카운터를 적중시켰습니다.",
    "23": "플레이어가 방어 자세의 빈틈에 중형 카운터를 적중시켰습니다.",
    "24": "적이 카운터 시도를 흘리고 안전하게 정비했습니다.",
    "25": "플레이어가 대치 중 타이밍을 잡아 적을 포착했습니다.",
    "26": "지지부진한 대치가 이어져 양측의 스태미너가 크게 감소했습니다.",
    "27": "적이 대치 중 타이밍을 잡아 플레이어를 포착했습니다.",
    "G01": "완전 그로기 상태의 대상에게 강화된 확정 타격을 가했습니다.",
    "G02": "상대가 완전 그로기인 틈에 안전하게 체력과 자세를 정비했습니다.",
    "G03": "완전 그로기 상태의 대상에게 강화된 확정 카운터를 가했습니다.",
}


@dataclass
class StatusEffect:
    name: str
    remaining_turns: int
    applied_on_match_turn: int
    display_name: str | None = None
    removable: bool = True
    polarity: str = "neutral"
    priority: int = 100
    duration_unit: str = "owner_turn"
    starts: str = "next_owner_turn"
    source_actor_index: int | None = None
    source_skill_id: str | None = None
    application: Any | None = field(default=None, repr=False, compare=False)

    @property
    def status_id(self) -> str:
        return self.name

    def snapshot(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "remaining_turns": self.remaining_turns,
            "applied_on_match_turn": self.applied_on_match_turn,
            "display_name": self.display_name,
            "removable": self.removable,
            "polarity": self.polarity,
            "priority": self.priority,
            "duration_unit": self.duration_unit,
            "starts": self.starts,
            "source_actor_index": self.source_actor_index,
            "source_skill_id": self.source_skill_id,
        }


@dataclass
class QueuedEffect:
    queue_id: str
    remaining_turns: int
    applied_on_match_turn: int
    owner_index: int
    source_skill_id: str
    application: Any = field(repr=False, compare=False)
    duration_unit: str = "owner_turn"
    consumes: str = "on_trigger"

    def snapshot(self) -> dict[str, Any]:
        return {
            "queue_id": self.queue_id,
            "remaining_turns": self.remaining_turns,
            "applied_on_match_turn": self.applied_on_match_turn,
            "owner_index": self.owner_index,
            "source_skill_id": self.source_skill_id,
            "duration_unit": self.duration_unit,
            "consumes": self.consumes,
        }


@dataclass(frozen=True)
class OwnedSkill:
    skill_id: str
    level: int


@dataclass(frozen=True)
class TurnIntent:
    actor_id: str
    base_action: Action
    active_skill_id: str | None = None
    target_id: str | None = None


@dataclass(frozen=True)
class IntentValidationIssue:
    code: str
    message: str


@dataclass(frozen=True)
class IntentValidationResult:
    issues: tuple[IntentValidationIssue, ...] = ()

    @property
    def valid(self) -> bool:
        return not self.issues

    def messages(self) -> tuple[str, ...]:
        return tuple(issue.message for issue in self.issues)


class InvalidTurnIntent(ValueError):
    def __init__(self, result: IntentValidationResult):
        self.result = result
        super().__init__("; ".join(result.messages()))


@dataclass
class EffectResolutionContext:
    intents: tuple[TurnIntent, ...]
    actions: list[Action]
    raw_dice: list[int | None] = field(default_factory=lambda: [None, None])
    final_dice: list[int | None] = field(default_factory=lambda: [None, None])
    dice_result: DiceResult | None = None
    entry_id: str | None = None
    deltas: list[dict[str, float]] = field(
        default_factory=lambda: [
            {"hp": 0, "stamina": 0, "break_gauge": 0},
            {"hp": 0, "stamina": 0, "break_gauge": 0},
        ]
    )
    dice_ranges: list[list[tuple[float, float, int, int, dict[str, Any]]]] = field(
        default_factory=lambda: [[], []]
    )
    action_controlled: set[int] = field(default_factory=set)
    effect_log: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class CharacterState:
    name: str
    max_hp: int = 100
    max_stamina: int = 100
    max_break_gauge: int = 100
    max_down_count: int = 3
    hp: int = 100
    stamina: int = 100
    break_gauge: int = 0
    down_count: int = 0
    skipped_turns_remaining: int = 0
    is_down: bool = False
    is_groggy: bool = False
    is_ko: bool = False
    statuses: list[StatusEffect] = field(default_factory=list)
    queued_effects: list[QueuedEffect] = field(default_factory=list)
    skill_loadout: tuple[OwnedSkill, ...] = ()
    skill_cooldowns: dict[str, int] = field(default_factory=dict)
    skill_uses_remaining: dict[str, int | None] = field(default_factory=dict)
    skill_round_uses_remaining: dict[str, int | None] = field(default_factory=dict)
    skill_cost_modifiers: dict[str, dict[str, float]] = field(default_factory=dict)
    next_skill_cost_modifiers: dict[str, float] = field(default_factory=dict)

    def snapshot(self) -> dict[str, Any]:
        return {
            "hp": self.hp,
            "stamina": self.stamina,
            "break_gauge": self.break_gauge,
            "down_count": self.down_count,
            "skipped_turns_remaining": self.skipped_turns_remaining,
            "is_down": self.is_down,
            "is_groggy": self.is_groggy,
            "is_ko": self.is_ko,
            "statuses": [status.snapshot() for status in self.statuses],
            "queued_effects": [queued.snapshot() for queued in self.queued_effects],
            "skill_loadout": [asdict(skill) for skill in self.skill_loadout],
            "skill_cooldowns": dict(self.skill_cooldowns),
            "skill_uses_remaining": dict(self.skill_uses_remaining),
            "skill_round_uses_remaining": dict(
                self.skill_round_uses_remaining
            ),
            "skill_cost_modifiers": {
                skill_id: dict(modifiers)
                for skill_id, modifiers in self.skill_cost_modifiers.items()
            },
            "next_skill_cost_modifiers": dict(self.next_skill_cost_modifiers),
        }


STRATEGY_NAMES = (
    "random",
    "attack",
    "evade",
    "cycle",
    "defensive",
    "pressure",
    "adaptive",
    "guard_evade_ratio",
    "guard_attack_ratio",
    "guard_mixed_ratio",
    "guard_evade_adaptive",
    "guard_attack_adaptive",
    "guard_mixed_adaptive",
    "rookie_cycle",
    "rookie_guard",
    "reckless_raider",
    "balanced_soldier",
    "veteran_guard",
    "cautious_hunter",
    "tactical_evaluator",
    "weighted_analyst",
    "regret_duelist",
    "executor",
)

PLAYER_TEST_STRATEGIES = (
    "random",
    "attack",
    "evade",
    "cycle",
    "defensive",
    "pressure",
    "adaptive",
    "guard_mixed_adaptive",
)

NPC_STRATEGIES_BY_DIFFICULTY = {
    "easy": ("rookie_cycle", "rookie_guard", "reckless_raider"),
    "normal": ("balanced_soldier", "veteran_guard", "cautious_hunter"),
    "hard": ("pressure", "adaptive", "tactical_evaluator"),
    "very_hard": ("weighted_analyst", "regret_duelist", "executor"),
}


@dataclass(frozen=True)
class StrategyExchange:
    """One previously revealed normal exchange, stored from the actor's view."""

    own_action: Action
    opponent_action: Action
    own_die: int
    opponent_die: int


@dataclass(frozen=True)
class StrategyContext:
    """Read-only decision context built from information available before reveal."""

    own_hp: int
    own_max_hp: int
    own_stamina: int
    own_max_stamina: int
    own_break_gauge: int
    own_down_count: int
    opponent_hp: int
    opponent_max_hp: int
    opponent_stamina: int
    opponent_max_stamina: int
    opponent_break_gauge: int
    opponent_down_count: int
    opponent_is_groggy: bool
    round_number: int
    turn_in_round: int
    match_turn: int
    own_history: tuple[Action, ...]
    opponent_history: tuple[Action, ...]
    exchange_history: tuple[StrategyExchange, ...]


def choose_strategy_action(
    strategy: str,
    context: StrategyContext,
    rng: random.Random,
) -> Action:
    """Choose from public pre-reveal state; never sees the opponent's current intent."""
    if strategy == "random":
        return rng.choice(tuple(Action))
    if strategy == "attack":
        return Action.ATTACK
    if strategy == "evade":
        return Action.EVADE
    if strategy in ("cycle", "rookie_cycle"):
        return tuple(Action)[len(context.own_history) % len(Action)]
    if strategy == "reckless_raider":
        if context.own_break_gauge >= 80:
            return Action.DEFEND
        return (Action.ATTACK, Action.ATTACK, Action.DEFEND)[
            len(context.own_history) % 3
        ]
    if strategy == "balanced_soldier":
        if context.opponent_is_groggy:
            return _weighted_action(
                {Action.ATTACK: 0.60, Action.DEFEND: 0.10, Action.EVADE: 0.30},
                rng,
            )
        weights = {action: 1.0 for action in Action}
        if context.own_break_gauge >= 80:
            weights = {Action.ATTACK: 0.25, Action.DEFEND: 0.50, Action.EVADE: 0.25}
        if (
            len(context.own_history) >= 2
            and context.own_history[-1] == context.own_history[-2]
        ):
            weights[context.own_history[-1]] = 0.0
        return _weighted_action(weights, rng)
    if strategy == "defensive":
        if context.opponent_is_groggy:
            return Action.ATTACK
        if (
            context.own_hp <= context.own_max_hp * 0.35
            or context.own_break_gauge >= 75
        ):
            return Action.DEFEND
        if (
            context.opponent_hp <= context.opponent_max_hp * 0.35
            or context.opponent_break_gauge >= 75
        ):
            return Action.ATTACK
        return Action.EVADE
    if strategy == "pressure":
        if context.opponent_is_groggy:
            return Action.ATTACK
        if (
            context.opponent_hp <= context.opponent_max_hp * 0.45
            or context.opponent_break_gauge >= 60
        ):
            return Action.ATTACK
        if context.own_hp < context.own_max_hp * 0.55 and context.own_break_gauge >= 80:
            return Action.DEFEND
        return Action.EVADE
    if strategy == "cautious_hunter":
        if context.opponent_is_groggy:
            return _weighted_action(
                {Action.ATTACK: 0.70, Action.EVADE: 0.30}, rng
            )
        weights = {Action.ATTACK: 0.35, Action.DEFEND: 0.30, Action.EVADE: 0.35}
        if context.opponent_hp <= context.opponent_max_hp * 0.30:
            weights[Action.ATTACK] += 0.60
        if context.opponent_break_gauge >= 75:
            weights[Action.ATTACK] += 0.70
        if context.own_hp <= context.own_max_hp * 0.30:
            weights[Action.DEFEND] += 0.60
        if context.own_break_gauge >= 80:
            weights[Action.DEFEND] += 0.70
        return _weighted_action(weights, rng)
    if strategy == "adaptive":
        if context.opponent_is_groggy:
            return Action.ATTACK
        recent = context.opponent_history[-6:]
        if not recent:
            return rng.choice(tuple(Action))
        counts = Counter(recent)
        highest = max(counts.values())
        predicted = rng.choice(
            [action for action in Action if counts[action] == highest]
        )
        counter = {
            Action.ATTACK: Action.DEFEND,
            Action.DEFEND: Action.EVADE,
            Action.EVADE: Action.ATTACK,
        }
        return counter[predicted]
    if strategy == "tactical_evaluator":
        distribution = _opponent_distribution(context, recent_limit=6, blend=0.60)
        return _softmax_scored_action(
            context,
            distribution,
            rng,
            temperature=10.0,
            state_awareness=0.65,
        )
    if strategy == "weighted_analyst":
        distribution = _opponent_distribution(
            context,
            recent_limit=10,
            blend=0.80,
            recency_decay=0.85,
        )
        return _softmax_scored_action(
            context,
            distribution,
            rng,
            temperature=6.0,
            state_awareness=1.0,
        )
    if strategy == "regret_duelist":
        return _regret_matching_action(context, rng)
    if strategy == "executor":
        distribution = _opponent_distribution(
            context,
            recent_limit=10,
            blend=0.85,
            recency_decay=0.82,
        )
        return _softmax_scored_action(
            context,
            distribution,
            rng,
            temperature=3.5,
            state_awareness=1.35,
            successor_awareness=True,
        )

    ratio_weights = {
        "guard_evade_ratio": {
            Action.DEFEND: 0.55,
            Action.EVADE: 0.45,
        },
        "guard_attack_ratio": {
            Action.DEFEND: 0.55,
            Action.ATTACK: 0.45,
        },
        "guard_mixed_ratio": {
            Action.DEFEND: 0.45,
            Action.ATTACK: 0.30,
            Action.EVADE: 0.25,
        },
        "rookie_guard": {
            Action.DEFEND: 0.45,
            Action.ATTACK: 0.30,
            Action.EVADE: 0.25,
        },
    }
    if strategy in ratio_weights:
        return _weighted_action(ratio_weights[strategy], rng)

    adaptive_weights = {
        "guard_evade_adaptive": {
            Action.DEFEND: 0.55,
            Action.EVADE: 0.45,
        },
        "guard_attack_adaptive": {
            Action.DEFEND: 0.55,
            Action.ATTACK: 0.45,
        },
        "guard_mixed_adaptive": {
            Action.DEFEND: 0.45,
            Action.ATTACK: 0.30,
            Action.EVADE: 0.25,
        },
        "veteran_guard": {
            Action.DEFEND: 0.45,
            Action.ATTACK: 0.30,
            Action.EVADE: 0.25,
        },
    }
    if strategy in adaptive_weights:
        weights = dict(adaptive_weights[strategy])
        if context.opponent_is_groggy:
            if Action.ATTACK in weights:
                return Action.ATTACK
            return Action.EVADE

        # High personal danger makes the defensive bias stronger without ever
        # collapsing into an all-defend policy.
        if (
            context.own_hp <= context.own_max_hp * 0.35
            or context.own_break_gauge >= 75
        ):
            weights[Action.DEFEND] = weights.get(Action.DEFEND, 0.0) + 0.35

        recent = context.opponent_history[-6:]
        if recent:
            counts = Counter(recent)
            highest = max(counts.values())
            predicted = rng.choice(
                [action for action in Action if counts[action] == highest]
            )
            counter = {
                Action.ATTACK: Action.DEFEND,
                Action.DEFEND: Action.EVADE,
                Action.EVADE: Action.ATTACK,
            }[predicted]
            if counter in weights:
                weights[counter] += 0.50
            else:
                # If the ideal counter is outside this character's action pool,
                # prefer the available action that avoids the weakest matchup.
                fallback = {
                    "guard_evade_adaptive": Action.EVADE,
                    # Attack is the only progress-making response available to
                    # this action pool when the opponent keeps defending.
                    "guard_attack_adaptive": Action.ATTACK,
                }.get(strategy, Action.DEFEND)
                weights[fallback] += 0.50
        return _weighted_action(weights, rng)
    raise ValueError(
        f"unknown strategy: {strategy!r}; choose from {', '.join(STRATEGY_NAMES)}"
    )


def _weighted_action(
    weights: dict[Action, float],
    rng: random.Random,
) -> Action:
    total = sum(max(0.0, weight) for weight in weights.values())
    if total <= 0:
        raise ValueError("action weights must contain a positive value")
    pick = rng.random() * total
    cumulative = 0.0
    for action in Action:
        cumulative += max(0.0, weights.get(action, 0.0))
        if pick <= cumulative:
            return action
    return next(reversed(weights))


def _opponent_distribution(
    context: StrategyContext,
    *,
    recent_limit: int,
    blend: float,
    recency_decay: float = 1.0,
) -> dict[Action, float]:
    recent = context.opponent_history[-recent_limit:]
    if not recent:
        return {action: 1 / len(Action) for action in Action}
    observed = {action: 0.0 for action in Action}
    for age, action in enumerate(reversed(recent)):
        observed[action] += recency_decay**age
    observed_total = sum(observed.values())
    uniform_share = (1.0 - blend) / len(Action)
    return {
        action: uniform_share + blend * observed[action] / observed_total
        for action in Action
    }


def _delta_score(entry: ResultEntry) -> float:
    own = entry.player
    opponent = entry.enemy
    return (
        max(0, -opponent.hp) * 1.00
        - max(0, opponent.hp) * 0.80
        + max(0, own.hp) * 0.80
        - max(0, -own.hp) * 1.10
        + max(0, -opponent.stamina) * 0.20
        - max(0, opponent.stamina) * 0.10
        + max(0, own.stamina) * 0.10
        - max(0, -own.stamina) * 0.15
        + max(0, opponent.break_gauge) * 0.40
        - max(0, -opponent.break_gauge) * 0.25
        + max(0, -own.break_gauge) * 0.35
        - max(0, own.break_gauge) * 0.45
    )


def _state_adjusted_score(
    context: StrategyContext,
    entry: ResultEntry,
    *,
    state_awareness: float,
    successor_awareness: bool,
) -> float:
    score = _delta_score(entry)
    own_hp_after = context.own_hp + entry.player.hp
    opponent_hp_after = context.opponent_hp + entry.enemy.hp
    own_break_after = context.own_break_gauge + entry.player.break_gauge
    opponent_break_after = context.opponent_break_gauge + entry.enemy.break_gauge

    if opponent_hp_after <= 0:
        score += state_awareness * (
            120 if context.opponent_down_count >= 2 else 28
        )
    if own_hp_after <= 0:
        score -= state_awareness * (150 if context.own_down_count >= 2 else 35)
    if opponent_break_after >= 100:
        score += state_awareness * 16
    if own_break_after >= 100:
        score -= state_awareness * 20

    if context.own_hp <= context.own_max_hp * 0.35:
        score += max(0, entry.player.hp) * state_awareness * 0.60
        score -= max(0, -entry.player.hp) * state_awareness * 0.35
    if context.opponent_hp <= context.opponent_max_hp * 0.35:
        score += max(0, -entry.enemy.hp) * state_awareness * 0.45

    if successor_awareness:
        # Approximate the value of the next exchange without inspecting a future
        # action: groggy creates a follow-up opening, while an imminent interval
        # discounts break that fails to reach the threshold this turn.
        if opponent_break_after >= 100 and opponent_hp_after > 0:
            score += 12
        if own_break_after >= 100 and own_hp_after > 0:
            score -= 15
        if context.turn_in_round >= 7:
            if 0 < entry.enemy.break_gauge and opponent_break_after < 100:
                score -= entry.enemy.break_gauge * 0.18
            if 0 < entry.player.break_gauge and own_break_after < 100:
                score += entry.player.break_gauge * 0.16
    return score


def _score_action(
    action: Action,
    context: StrategyContext,
    opponent_distribution: dict[Action, float],
    *,
    state_awareness: float,
    successor_awareness: bool,
) -> float:
    dice_probabilities = {
        DiceResult.WIN: 15 / 36,
        DiceResult.DRAW: 6 / 36,
        DiceResult.LOSE: 15 / 36,
    }
    total = 0.0
    for opponent_action, action_probability in opponent_distribution.items():
        for dice_result, dice_probability in dice_probabilities.items():
            entry = RESULT_TABLE[(action, opponent_action, dice_result)]
            total += (
                action_probability
                * dice_probability
                * _state_adjusted_score(
                    context,
                    entry,
                    state_awareness=state_awareness,
                    successor_awareness=successor_awareness,
                )
            )
    return total


def _softmax_scored_action(
    context: StrategyContext,
    opponent_distribution: dict[Action, float],
    rng: random.Random,
    *,
    temperature: float,
    state_awareness: float,
    successor_awareness: bool = False,
) -> Action:
    scores = {
        action: _score_action(
            action,
            context,
            opponent_distribution,
            state_awareness=state_awareness,
            successor_awareness=successor_awareness,
        )
        for action in Action
    }
    highest = max(scores.values())
    weights = {
        action: math.exp((score - highest) / temperature)
        for action, score in scores.items()
    }
    return _weighted_action(weights, rng)


def _regret_matching_action(
    context: StrategyContext,
    rng: random.Random,
) -> Action:
    if not context.exchange_history:
        return rng.choice(tuple(Action))
    regrets = {action: 0.0 for action in Action}
    for exchange in context.exchange_history[-20:]:
        actual = RESULT_TABLE[
            (
                exchange.own_action,
                exchange.opponent_action,
                compare_dice(exchange.own_die, exchange.opponent_die),
            )
        ]
        actual_score = _delta_score(actual)
        for action in Action:
            alternative = RESULT_TABLE[
                (
                    action,
                    exchange.opponent_action,
                    compare_dice(exchange.own_die, exchange.opponent_die),
                )
            ]
            regrets[action] += _delta_score(alternative) - actual_score
    # Exploration weight 1 keeps every action available; positive regret then
    # raises the probability of choices that would have performed better.
    return _weighted_action(
        {action: 1.0 + max(0.0, regret) for action, regret in regrets.items()},
        rng,
    )


@dataclass
class MatchMetrics:
    action_counts: Counter[str] = field(default_factory=Counter)
    table_entry_counts: Counter[str] = field(default_factory=Counter)
    groggy_entries: list[int] = field(default_factory=lambda: [0, 0])
    groggy_character_turns: int = 0
    down_events: list[int] = field(default_factory=lambda: [0, 0])
    wait_turns: int = 0
    double_downs: int = 0


@dataclass
class MatchResult:
    seed: int
    outcome: str
    winner: str | None
    turns: int
    rounds: int
    metrics: MatchMetrics
    final_player: CharacterState
    final_enemy: CharacterState
    trace: list[dict[str, Any]]


def compare_dice(player_die: int, enemy_die: int) -> DiceResult:
    if player_die > enemy_die:
        return DiceResult.WIN
    if player_die < enemy_die:
        return DiceResult.LOSE
    return DiceResult.DRAW


def floor_percent(value: int, ratio: float) -> int:
    return math.floor(value * ratio)


def apply_delta(character: CharacterState, delta: Delta) -> None:
    character.hp = min(character.max_hp, max(0, character.hp + delta.hp))
    character.stamina = min(
        character.max_stamina, max(0, character.stamina + delta.stamina)
    )
    character.break_gauge = min(
        character.max_break_gauge,
        max(0, character.break_gauge + delta.break_gauge),
    )


class BattleEngine:
    """Symmetric 1v1 battle engine with injectable action policies and skills."""

    def __init__(
        self,
        seed: int,
        *,
        max_rounds: int = 100,
        trace_enabled: bool = False,
        player_strategy: str = "random",
        enemy_strategy: str = "random",
        skill_registry: Mapping[str, SkillDefinition] | None = None,
        player_skills: Iterable[OwnedSkill] = (),
        enemy_skills: Iterable[OwnedSkill] = (),
    ) -> None:
        if player_strategy not in STRATEGY_NAMES:
            raise ValueError(f"unknown player strategy: {player_strategy!r}")
        if enemy_strategy not in STRATEGY_NAMES:
            raise ValueError(f"unknown enemy strategy: {enemy_strategy!r}")
        self.seed = seed
        self.rng = random.Random(seed)
        # Policy RNGs are separated from dice RNG so a strategy's internal random
        # calls cannot shift the combat roll sequence.
        self.policy_rngs = (
            random.Random(seed ^ 0x9E3779B97F4A7C15),
            random.Random(seed ^ 0xD1B54A32D192ED03),
        )
        self.strategies = (player_strategy, enemy_strategy)
        self.action_history: tuple[list[Action], list[Action]] = ([], [])
        self.exchange_history: tuple[
            list[StrategyExchange], list[StrategyExchange]
        ] = ([], [])
        self.max_rounds = max_rounds
        self.trace_enabled = trace_enabled
        self.skill_registry: Mapping[str, SkillDefinition] = (
            skill_registry if skill_registry is not None else {}
        )
        self.player = CharacterState("Player")
        self.enemy = CharacterState("Enemy")
        self._equip_skills(self.player, tuple(player_skills))
        self._equip_skills(self.enemy, tuple(enemy_skills))
        self.intent_history: tuple[list[TurnIntent], list[TurnIntent]] = ([], [])
        self._skills_committed_this_turn: set[tuple[int, str]] = set()
        self._current_effect_context: EffectResolutionContext | None = None
        self.round_number = 1
        self.turn_in_round = 0
        self.match_turn = 0
        self.outcome: str | None = None
        self.winner: str | None = None
        self.metrics = MatchMetrics()
        self.trace: list[dict[str, Any]] = []

    @property
    def characters(self) -> tuple[CharacterState, CharacterState]:
        return self.player, self.enemy

    @staticmethod
    def _actor_id(actor_index: int) -> str:
        return "player" if actor_index == 0 else "enemy"

    @staticmethod
    def _actor_index(actor_id: str) -> int | None:
        if actor_id == "player":
            return 0
        if actor_id == "enemy":
            return 1
        return None

    def _equip_skills(
        self,
        character: CharacterState,
        loadout: tuple[OwnedSkill, ...],
    ) -> None:
        seen: set[str] = set()
        for owned in loadout:
            if owned.skill_id in seen:
                raise ValueError(f"duplicate equipped skill: {owned.skill_id!r}")
            seen.add(owned.skill_id)
            definition = self.skill_registry.get(owned.skill_id)
            if definition is None:
                raise ValueError(f"unknown equipped skill: {owned.skill_id!r}")
            try:
                level = definition.level(owned.level)
            except KeyError as exc:
                raise ValueError(str(exc)) from exc
            character.skill_cooldowns[owned.skill_id] = 0
            character.skill_uses_remaining[owned.skill_id] = (
                level.usage_limit.per_match
            )
            character.skill_round_uses_remaining[owned.skill_id] = (
                level.usage_limit.per_round
            )
        character.skill_loadout = loadout

    def _owned_skill(
        self, character: CharacterState, skill_id: str
    ) -> tuple[OwnedSkill, SkillDefinition, SkillLevel] | None:
        owned = next(
            (skill for skill in character.skill_loadout if skill.skill_id == skill_id),
            None,
        )
        if owned is None:
            return None
        definition = self.skill_registry.get(skill_id)
        if definition is None:
            return None
        return owned, definition, definition.level(owned.level)

    @staticmethod
    def _effective_skill_cost(
        character: CharacterState,
        skill_id: str,
        resource: str,
        base_amount: float,
    ) -> float:
        persistent = character.skill_cost_modifiers.get(skill_id, {}).get(
            resource, 0
        )
        next_use = character.next_skill_cost_modifiers.get(resource, 0)
        return max(0, base_amount + persistent + next_use)

    def _log(self, event: str, **details: Any) -> None:
        if not self.trace_enabled:
            return
        self.trace.append(
            {
                "event": event,
                "round": self.round_number,
                "turn_in_round": self.turn_in_round,
                "match_turn": self.match_turn,
                **details,
            }
        )

    def _strategy_context(self, actor_index: int) -> StrategyContext:
        actor = self.characters[actor_index]
        opponent = self.characters[1 - actor_index]
        return StrategyContext(
            own_hp=actor.hp,
            own_max_hp=actor.max_hp,
            own_stamina=actor.stamina,
            own_max_stamina=actor.max_stamina,
            own_break_gauge=actor.break_gauge,
            own_down_count=actor.down_count,
            opponent_hp=opponent.hp,
            opponent_max_hp=opponent.max_hp,
            opponent_stamina=opponent.stamina,
            opponent_max_stamina=opponent.max_stamina,
            opponent_break_gauge=opponent.break_gauge,
            opponent_down_count=opponent.down_count,
            opponent_is_groggy=opponent.is_groggy,
            round_number=self.round_number,
            turn_in_round=self.turn_in_round,
            match_turn=self.match_turn,
            own_history=tuple(self.action_history[actor_index]),
            opponent_history=tuple(self.action_history[1 - actor_index]),
            exchange_history=tuple(self.exchange_history[actor_index]),
        )

    def _choose_action(self, actor_index: int) -> Action:
        return choose_strategy_action(
            self.strategies[actor_index],
            self._strategy_context(actor_index),
            self.policy_rngs[actor_index],
        )

    def _choose_intent(self, actor_index: int) -> TurnIntent:
        """Backward-compatible policy intent; Phase E will add skill choices."""
        return TurnIntent(
            actor_id=self._actor_id(actor_index),
            base_action=self._choose_action(actor_index),
        )

    def validate_intent(
        self,
        intent: TurnIntent,
        *,
        upcoming_turn: bool = True,
    ) -> IntentValidationResult:
        issues: list[IntentValidationIssue] = []
        actor_index = self._actor_index(intent.actor_id)
        if actor_index is None:
            return IntentValidationResult((IntentValidationIssue(
                "unknown_actor",
                f"unknown actor id: {intent.actor_id!r}",
            ),))
        actor = self.characters[actor_index]
        opponent = self.characters[1 - actor_index]
        if actor.is_down or actor.is_groggy or actor.is_ko:
            issues.append(IntentValidationIssue(
                "actor_cannot_act",
                f"{intent.actor_id} cannot act in the current state",
            ))
        if intent.active_skill_id is None:
            if intent.target_id is not None:
                issues.append(IntentValidationIssue(
                    "target_without_skill",
                    "target_id must be null when no active skill is selected",
                ))
            return IntentValidationResult(tuple(issues))

        resolved = self._owned_skill(actor, intent.active_skill_id)
        if resolved is None:
            issues.append(IntentValidationIssue(
                "skill_not_owned",
                f"{intent.actor_id} does not own skill {intent.active_skill_id!r}",
            ))
            return IntentValidationResult(tuple(issues))
        _, definition, level = resolved

        if intent.base_action.value not in level.requirements.allowed_actions:
            issues.append(IntentValidationIssue(
                "action_not_allowed",
                f"skill {definition.skill_id!r} cannot be used with "
                f"action {intent.base_action.value!r}",
            ))
        issues.extend(self._validate_intent_target(
            intent, actor_index, definition.targeting.type,
            definition.targeting.selection_required,
        ))
        if level.requirements.condition is not None and not self._evaluate_condition(
            level.requirements.condition,
            actor_index,
            intent,
            upcoming_turn=upcoming_turn,
        ):
            issues.append(IntentValidationIssue(
                "requirements_not_met",
                f"requirements are not met for skill {definition.skill_id!r}",
            ))
        for cost in level.costs:
            current = getattr(actor, cost.resource.value)
            effective_cost = self._effective_skill_cost(
                actor,
                definition.skill_id,
                cost.resource.value,
                cost.amount,
            )
            if (
                current < effective_cost
                or current - effective_cost < cost.minimum_remaining
            ):
                issues.append(IntentValidationIssue(
                    "insufficient_resource",
                    f"insufficient {cost.resource.value} for skill "
                    f"{definition.skill_id!r}",
                ))
        if actor.skill_cooldowns.get(definition.skill_id, 0) > 0:
            issues.append(IntentValidationIssue(
                "skill_on_cooldown",
                f"skill {definition.skill_id!r} has "
                f"{actor.skill_cooldowns[definition.skill_id]} cooldown turns remaining",
            ))
        match_uses = actor.skill_uses_remaining.get(definition.skill_id)
        if match_uses is not None and match_uses <= 0:
            issues.append(IntentValidationIssue(
                "match_uses_exhausted",
                f"skill {definition.skill_id!r} has no match uses remaining",
            ))
        round_uses = actor.skill_round_uses_remaining.get(definition.skill_id)
        if round_uses is not None and round_uses <= 0:
            issues.append(IntentValidationIssue(
                "round_uses_exhausted",
                f"skill {definition.skill_id!r} has no round uses remaining",
            ))
        return IntentValidationResult(tuple(issues))

    def _validate_intent_target(
        self,
        intent: TurnIntent,
        actor_index: int,
        target_type: Target,
        selection_required: bool,
    ) -> list[IntentValidationIssue]:
        actor_id = self._actor_id(actor_index)
        opponent_id = self._actor_id(1 - actor_index)
        expected = {
            Target.SELF: actor_id,
            Target.OPPONENT: opponent_id,
            Target.BOTH: "both",
        }[target_type]
        if intent.target_id is None:
            if selection_required:
                return [IntentValidationIssue(
                    "target_required",
                    f"skill {intent.active_skill_id!r} requires a target",
                )]
            return []
        if intent.target_id != expected:
            return [IntentValidationIssue(
                "invalid_target",
                f"skill {intent.active_skill_id!r} expects target {expected!r}, "
                f"got {intent.target_id!r}",
            )]
        return []

    def _condition_subject(
        self, actor_index: int, subject: str
    ) -> tuple[int, CharacterState]:
        index = actor_index if subject == "self" else 1 - actor_index
        return index, self.characters[index]

    def _evaluate_condition(
        self,
        condition: Condition,
        actor_index: int,
        intent: TurnIntent,
        *,
        upcoming_turn: bool,
    ) -> bool:
        if condition.kind == ConditionKind.ALL:
            return all(
                self._evaluate_condition(
                    child, actor_index, intent, upcoming_turn=upcoming_turn
                )
                for child in condition.children
            )
        if condition.kind == ConditionKind.ANY:
            return any(
                self._evaluate_condition(
                    child, actor_index, intent, upcoming_turn=upcoming_turn
                )
                for child in condition.children
            )
        if condition.kind == ConditionKind.NOT:
            return not self._evaluate_condition(
                condition.children[0],
                actor_index,
                intent,
                upcoming_turn=upcoming_turn,
            )

        predicate = condition.predicate
        arguments = condition.arguments
        subject_index, subject = self._condition_subject(
            actor_index, arguments.get("subject", "self")
        )
        if predicate == "action_in":
            return intent.base_action.value in arguments["values"]
        if predicate == "previous_action_is":
            history = self.action_history[subject_index]
            return bool(history) and history[-1].value == arguments["value"]
        if predicate == "recent_action_count_at_least":
            recent = self.action_history[subject_index][-arguments["window"]:]
            return sum(
                action.value == arguments["action"] for action in recent
            ) >= arguments["value"]
        if predicate and predicate.startswith("resource_"):
            current = getattr(subject, arguments["resource"])
            if "_ratio_" in predicate:
                maximum = getattr(subject, f"max_{arguments['resource']}")
                current = current / maximum if maximum else 0
            if predicate.endswith("_at_least"):
                return current >= arguments["value"]
            return current <= arguments["value"]
        if predicate == "round_at_least":
            return self.round_number >= arguments["value"]
        if predicate == "round_at_most":
            return self.round_number <= arguments["value"]
        if predicate == "turn_in_round_is":
            evaluated_turn = self.turn_in_round + (1 if upcoming_turn else 0)
            return evaluated_turn == arguments["value"]
        if predicate == "down_count_at_least":
            return subject.down_count >= arguments["value"]
        if predicate in {"is_groggy", "is_down", "is_ko"}:
            return getattr(subject, predicate) == arguments["value"]
        if predicate in {"status_present", "status_absent"}:
            present = any(
                status.name == arguments["status_id"] for status in subject.statuses
            )
            return present if predicate == "status_present" else not present
        if predicate == "status_count_at_least":
            return len(subject.statuses) >= arguments["value"]
        if predicate == "skill_ready":
            skill_id = arguments["skill_id"]
            return (
                self._owned_skill(subject, skill_id) is not None
                and subject.skill_cooldowns.get(skill_id, 0) == 0
            )
        if predicate == "skill_uses_remaining_at_least":
            remaining = subject.skill_uses_remaining.get(arguments["skill_id"])
            return remaining is None or remaining >= arguments["value"]
        raise RuntimeError(f"unsupported requirement predicate: {predicate!r}")

    def commit_intents(
        self,
        intents: Iterable[TurnIntent],
        *,
        upcoming_turn: bool = True,
    ) -> None:
        """Validate every intent before atomically consuming any skill state."""
        intents = tuple(intents)
        actor_ids = [intent.actor_id for intent in intents]
        if len(actor_ids) != len(set(actor_ids)):
            raise InvalidTurnIntent(IntentValidationResult((IntentValidationIssue(
                "duplicate_actor_intent",
                "only one intent per actor may be committed in a turn",
            ),)))
        validations = tuple(
            self.validate_intent(intent, upcoming_turn=upcoming_turn)
            for intent in intents
        )
        issues = tuple(
            issue for validation in validations for issue in validation.issues
        )
        if issues:
            raise InvalidTurnIntent(IntentValidationResult(issues))
        for intent in intents:
            if intent.active_skill_id is None:
                continue
            actor_index = self._actor_index(intent.actor_id)
            assert actor_index is not None
            actor = self.characters[actor_index]
            resolved = self._owned_skill(actor, intent.active_skill_id)
            assert resolved is not None
            _, definition, level = resolved
            for cost in level.costs:
                current = getattr(actor, cost.resource.value)
                effective_cost = self._effective_skill_cost(
                    actor,
                    definition.skill_id,
                    cost.resource.value,
                    cost.amount,
                )
                setattr(actor, cost.resource.value, current - effective_cost)
            actor.next_skill_cost_modifiers.clear()
            if actor.skill_uses_remaining[definition.skill_id] is not None:
                actor.skill_uses_remaining[definition.skill_id] -= 1
            if actor.skill_round_uses_remaining[definition.skill_id] is not None:
                actor.skill_round_uses_remaining[definition.skill_id] -= 1
            if level.cooldown.starts == CooldownStart.ON_SKILL_COMMIT:
                actor.skill_cooldowns[definition.skill_id] = level.cooldown.turns
            self._skills_committed_this_turn.add(
                (actor_index, definition.skill_id)
            )

    def _finalize_intent_cooldowns(self, intents: Iterable[TurnIntent]) -> None:
        for intent in intents:
            if intent.active_skill_id is None:
                continue
            actor_index = self._actor_index(intent.actor_id)
            assert actor_index is not None
            actor = self.characters[actor_index]
            resolved = self._owned_skill(actor, intent.active_skill_id)
            assert resolved is not None
            _, definition, level = resolved
            if level.cooldown.starts == CooldownStart.AFTER_RESOLUTION:
                actor.skill_cooldowns[definition.skill_id] = level.cooldown.turns

    def _tick_skill_cooldowns(self) -> None:
        for actor_index, actor in enumerate(self.characters):
            opponent = self.characters[1 - actor_index]
            actionable = (
                not actor.is_down
                and not actor.is_groggy
                and not actor.is_ko
                and not opponent.is_down
            )
            for owned in actor.skill_loadout:
                remaining = actor.skill_cooldowns.get(owned.skill_id, 0)
                if remaining <= 0:
                    continue
                if (actor_index, owned.skill_id) in self._skills_committed_this_turn:
                    continue
                resolved = self._owned_skill(actor, owned.skill_id)
                assert resolved is not None
                _, _, level = resolved
                if level.cooldown.decrements == CooldownDecrement.OWNER_TURN:
                    actor.skill_cooldowns[owned.skill_id] = remaining - 1
                elif (
                    level.cooldown.decrements
                    == CooldownDecrement.OWNER_ACTIONABLE_TURN
                    and actionable
                ):
                    actor.skill_cooldowns[owned.skill_id] = remaining - 1

    @staticmethod
    def _comparison_matches(left: float, operation: str, right: float) -> bool:
        return {
            "equal": left == right,
            "not_equal": left != right,
            "less_than": left < right,
            "less_than_or_equal": left <= right,
            "greater_than": left > right,
            "greater_than_or_equal": left >= right,
        }[operation]

    def _evaluate_effect_condition(
        self,
        condition: Condition,
        actor_index: int,
        intent: TurnIntent,
        context: EffectResolutionContext,
    ) -> bool:
        if condition.kind == ConditionKind.ALL:
            return all(
                self._evaluate_effect_condition(child, actor_index, intent, context)
                for child in condition.children
            )
        if condition.kind == ConditionKind.ANY:
            return any(
                self._evaluate_effect_condition(child, actor_index, intent, context)
                for child in condition.children
            )
        if condition.kind == ConditionKind.NOT:
            return not self._evaluate_effect_condition(
                condition.children[0], actor_index, intent, context
            )

        predicate = condition.predicate
        arguments = condition.arguments
        subject_index = (
            actor_index if arguments.get("subject", "self") == "self"
            else 1 - actor_index
        )
        if predicate == "action_in":
            return context.actions[subject_index].value in arguments["values"]
        if predicate == "raw_die_is":
            return context.raw_dice[subject_index] == arguments["value"]
        if predicate in {"final_die_at_least", "final_die_at_most"}:
            value = context.final_dice[subject_index]
            if value is None:
                return False
            if predicate.endswith("at_least"):
                return value >= arguments["value"]
            return value <= arguments["value"]
        if predicate == "dice_result_is":
            if context.dice_result is None:
                return False
            actor_result = context.dice_result
            if actor_index == 1:
                actor_result = {
                    DiceResult.WIN: DiceResult.LOSE,
                    DiceResult.DRAW: DiceResult.DRAW,
                    DiceResult.LOSE: DiceResult.WIN,
                }[actor_result]
            return actor_result.value == arguments["value"]
        if predicate == "result_entry_is":
            return context.entry_id == arguments["value"]
        if predicate == "result_delta_is":
            value = context.deltas[subject_index][arguments["resource"]]
            return self._comparison_matches(
                value, arguments["comparison"], arguments["value"]
            )
        projected_intent = TurnIntent(
            intent.actor_id,
            context.actions[actor_index],
            intent.active_skill_id,
            intent.target_id,
        )
        return self._evaluate_condition(
            condition,
            actor_index,
            projected_intent,
            upcoming_turn=False,
        )

    def _application_targets(
        self, target: Target, actor_index: int
    ) -> tuple[int, ...]:
        if target == Target.SELF:
            return (actor_index,)
        if target == Target.OPPONENT:
            return (1 - actor_index,)
        return (0, 1)

    def _dispatch_timing(
        self,
        timing: Timing,
        context: EffectResolutionContext,
        *,
        allow_new_deliveries: bool = True,
    ) -> None:
        pending: list[tuple[int, int, int, TurnIntent, Any, str, Any | None]] = []

        # Effects already attached to a character take part in the same priority
        # ordering as immediate effects.  A status never re-checks its original
        # application condition; a queued effect checks its trigger condition.
        for owner_index, owner in enumerate(self.characters):
            current_intent = next(
                (
                    intent for intent in context.intents
                    if self._actor_index(intent.actor_id) == owner_index
                ),
                TurnIntent(self._actor_id(owner_index), context.actions[owner_index]),
            )
            for status_index, status in enumerate(owner.statuses):
                if (
                    status.application is not None
                    and status.applied_on_match_turn < self.match_turn
                    and status.application.timing == timing
                ):
                    status_intent = TurnIntent(
                        self._actor_id(owner_index),
                        current_intent.base_action,
                        status.source_skill_id,
                        self._actor_id(owner_index),
                    )
                    pending.append((
                        -status.priority,
                        owner_index,
                        status_index,
                        status_intent,
                        status.application,
                        "status",
                        status,
                    ))
            for queue_index, queued in enumerate(owner.queued_effects):
                trigger = queued.application.delivery.trigger
                if (
                    queued.applied_on_match_turn <= self.match_turn
                    and trigger is not None
                    and trigger.event == timing
                ):
                    queued_intent = TurnIntent(
                        self._actor_id(owner_index),
                        current_intent.base_action,
                        queued.source_skill_id,
                        self._actor_id(owner_index),
                    )
                    pending.append((
                        -queued.application.priority,
                        owner_index,
                        queue_index,
                        queued_intent,
                        queued.application,
                        "queued",
                        queued,
                    ))

        deferred: list[tuple[int, int, int, TurnIntent, Any]] = []
        for intent in context.intents:
            if intent.active_skill_id is None:
                continue
            actor_index = self._actor_index(intent.actor_id)
            assert actor_index is not None
            resolved = self._owned_skill(
                self.characters[actor_index], intent.active_skill_id
            )
            assert resolved is not None
            _, _, level = resolved
            for application_index, application in enumerate(level.applications):
                if application.timing != timing:
                    continue
                if application.delivery.type == DeliveryType.IMMEDIATE:
                    pending.append((
                        -application.priority,
                        actor_index,
                        application_index,
                        intent,
                        application,
                        "immediate",
                        None,
                    ))
                elif allow_new_deliveries:
                    deferred.append((
                        -application.priority,
                        actor_index,
                        application_index,
                        intent,
                        application,
                    ))

        consumed_queues: set[int] = set()
        expired_statuses: set[int] = set()
        for _, actor_index, _, intent, application, source_kind, source in sorted(
            pending, key=lambda item: item[:3]
        ):
            condition = application.condition if source_kind == "immediate" else None
            if source_kind == "queued":
                condition = application.delivery.trigger.condition
            if condition is not None and not self._evaluate_effect_condition(
                condition, actor_index, intent, context
            ):
                context.effect_log.append({
                    "timing": timing.value,
                    "actor": intent.actor_id,
                    "skill_id": intent.active_skill_id,
                    "application_id": application.application_id,
                    "applied": False,
                    "reason": (
                        "trigger_condition_not_met"
                        if source_kind == "queued" else "condition_not_met"
                    ),
                    "source": source_kind,
                })
                continue
            target_indexes = (
                (actor_index,)
                if source_kind == "status"
                else self._application_targets(application.target, actor_index)
            )
            log_start = len(context.effect_log)
            for target_index in target_indexes:
                for effect_index, effect in enumerate(application.effects):
                    self._execute_content_effect(
                        context,
                        timing,
                        actor_index,
                        target_index,
                        intent,
                        application,
                        effect,
                        effect_index,
                    )
                    context.effect_log[-1]["source"] = source_kind
            if source_kind == "queued":
                successful = any(
                    entry.get("applied", False)
                    for entry in context.effect_log[log_start:]
                )
                consumes = source.consumes
                if (
                    consumes == QueuedConsume.ON_TRIGGER.value
                    or (
                        consumes == QueuedConsume.ON_SUCCESSFUL_APPLY.value
                        and successful
                    )
                ):
                    consumed_queues.add(id(source))
                elif source.duration_unit == DurationUnit.TRIGGER_COUNT.value:
                    source.remaining_turns -= 1
                    if source.remaining_turns <= 0:
                        consumed_queues.add(id(source))
            elif (
                source_kind == "status"
                and source.duration_unit == DurationUnit.TRIGGER_COUNT.value
            ):
                source.remaining_turns -= 1
                if source.remaining_turns <= 0:
                    expired_statuses.add(id(source))

        if consumed_queues:
            for character in self.characters:
                character.queued_effects = [
                    queued for queued in character.queued_effects
                    if id(queued) not in consumed_queues
                ]
        if expired_statuses:
            for character in self.characters:
                character.statuses = [
                    status for status in character.statuses
                    if id(status) not in expired_statuses
                ]

        status_applied = False
        for _, actor_index, _, intent, application in sorted(deferred):
            if application.condition is not None and not self._evaluate_effect_condition(
                application.condition, actor_index, intent, context
            ):
                context.effect_log.append({
                    "timing": timing.value,
                    "actor": intent.actor_id,
                    "skill_id": intent.active_skill_id,
                    "application_id": application.application_id,
                    "applied": False,
                    "reason": "condition_not_met",
                    "source": application.delivery.type.value,
                })
                continue
            for target_index in self._application_targets(
                application.target, actor_index
            ):
                if application.delivery.type == DeliveryType.STATUS:
                    status_applied |= self._store_status(
                        context, timing, actor_index, target_index, intent, application
                    )
                else:
                    self._store_queued_effect(
                        context, timing, actor_index, target_index, intent, application
                    )

        if status_applied and timing != Timing.ON_STATUS_APPLY:
            self._dispatch_timing(
                Timing.ON_STATUS_APPLY,
                context,
                allow_new_deliveries=False,
            )

    def _store_status(
        self,
        context: EffectResolutionContext,
        timing: Timing,
        actor_index: int,
        target_index: int,
        intent: TurnIntent,
        application: Any,
    ) -> bool:
        spec = application.delivery.status
        assert spec is not None
        target = self.characters[target_index]
        existing = next(
            (status for status in target.statuses if status.name == spec.status_id),
            None,
        )
        status = StatusEffect(
            spec.status_id,
            spec.duration.value,
            self.match_turn,
            display_name=spec.name,
            removable=spec.removable,
            polarity=spec.polarity.value,
            priority=application.priority,
            duration_unit=spec.duration.unit.value,
            starts=(
                spec.duration.starts.value
                if spec.duration.starts is not None
                else DurationStart.NEXT_OWNER_TURN.value
            ),
            source_actor_index=actor_index,
            source_skill_id=intent.active_skill_id,
            application=application,
        )
        mode = spec.stacking.mode.value
        if existing is None:
            target.statuses.append(status)
            result = "added"
        elif mode == "refresh":
            existing.remaining_turns = spec.duration.value
            existing.applied_on_match_turn = self.match_turn
            result = "refreshed"
        else:
            target.statuses[target.statuses.index(existing)] = status
            result = "replaced"
        context.effect_log.append({
            "timing": timing.value,
            "actor": intent.actor_id,
            "target": self._actor_id(target_index),
            "skill_id": intent.active_skill_id,
            "application_id": application.application_id,
            "delivery": "status",
            "status_id": spec.status_id,
            "remaining_turns": spec.duration.value,
            "result": result,
            "applied": True,
        })
        return True

    def _store_queued_effect(
        self,
        context: EffectResolutionContext,
        timing: Timing,
        actor_index: int,
        target_index: int,
        intent: TurnIntent,
        application: Any,
    ) -> None:
        delivery = application.delivery
        assert delivery.expires is not None and delivery.consumes is not None
        queued = QueuedEffect(
            application.application_id,
            delivery.expires.value,
            self.match_turn,
            actor_index,
            intent.active_skill_id or "",
            application,
            duration_unit=delivery.expires.unit.value,
            consumes=delivery.consumes.value,
        )
        # A queued application belongs to the skill user; its target is resolved
        # only when the trigger fires.  This lets "next successful hit" effects
        # remain attached to the attacker while still modifying the opponent.
        self.characters[actor_index].queued_effects.append(queued)
        context.effect_log.append({
            "timing": timing.value,
            "actor": intent.actor_id,
            "target": self._actor_id(target_index),
            "owner": self._actor_id(actor_index),
            "skill_id": intent.active_skill_id,
            "application_id": application.application_id,
            "delivery": "queued",
            "remaining_turns": queued.remaining_turns,
            "applied": True,
        })

    def _effect_log_entry(
        self,
        timing: Timing,
        actor_index: int,
        target_index: int,
        intent: TurnIntent,
        application: Any,
        effect: Any,
    ) -> dict[str, Any]:
        return {
            "timing": timing.value,
            "actor": self._actor_id(actor_index),
            "target": self._actor_id(target_index),
            "skill_id": intent.active_skill_id,
            "application_id": application.application_id,
            "category": effect.category.value,
            "operation": effect.operation.value,
            "priority": application.priority,
            "applied": True,
        }

    def _execute_content_effect(
        self,
        context: EffectResolutionContext,
        timing: Timing,
        actor_index: int,
        target_index: int,
        intent: TurnIntent,
        application: Any,
        effect: Any,
        effect_index: int,
    ) -> None:
        log = self._effect_log_entry(
            timing, actor_index, target_index, intent, application, effect
        )
        parameters = effect.parameters
        target = self.characters[target_index]

        if effect.category == EffectCategory.RESOURCE_CHANGE:
            resource = parameters["resource"]
            before = getattr(target, resource)
            maximum = getattr(target, f"max_{resource}")
            value = parameters["value"]
            if effect.operation == ResourceChangeOperation.ADD:
                after = before + value
            elif effect.operation == ResourceChangeOperation.SET:
                after = value
            elif effect.operation == ResourceChangeOperation.ADD_PERCENT_OF_MAX:
                after = before + maximum * value
            else:
                after = maximum * value
            after = min(maximum, max(0, math.floor(after)))
            setattr(target, resource, after)
            log.update(resource=resource, before=before, after=after)

        elif effect.category == EffectCategory.RESULT_MODIFIER:
            resource = parameters["resource"]
            before = context.deltas[target_index][resource]
            polarity = parameters["polarity"]
            if polarity in {"damage", "decrease"}:
                sign = -1
            elif polarity in {"recovery", "increase"}:
                sign = 1
            else:
                sign = -1 if before < 0 else 1
            matches = (
                polarity == "any"
                or before == 0
                or (sign < 0 and before < 0)
                or (sign > 0 and before > 0)
            )
            if not matches:
                log.update(applied=False, reason="polarity_not_matched", before=before)
            else:
                value = parameters.get("value", 0)
                if effect.operation == ResultModifierOperation.ADD:
                    after = before + sign * value
                elif effect.operation == ResultModifierOperation.MULTIPLY:
                    after = before * value
                elif effect.operation == ResultModifierOperation.MINIMUM:
                    after = sign * max(abs(before), value)
                elif effect.operation == ResultModifierOperation.MAXIMUM:
                    after = sign * min(abs(before), value)
                else:
                    after = 0
                context.deltas[target_index][resource] = after
                log.update(resource=resource, before=before, after=after)

        elif effect.category == EffectCategory.DICE_MODIFIER:
            if effect.operation == DiceModifierOperation.SET_MINIMUM:
                minimum, maximum = parameters["value"], 6
            else:
                minimum, maximum = 1, parameters["value"]
            context.dice_ranges[target_index].append((
                minimum,
                maximum,
                application.priority,
                effect_index,
                log,
            ))
            log.update(range=[minimum, maximum], pending=True)

        elif effect.category == EffectCategory.ACTION_CONTROL:
            before = context.actions[target_index]
            if target_index in context.action_controlled:
                log.update(applied=False, reason="lower_priority_action_control")
            else:
                if effect.operation == ActionControlOperation.FORCE:
                    after = Action(parameters["action"])
                elif effect.operation == ActionControlOperation.ALLOW_ONLY:
                    allowed = tuple(Action(value) for value in parameters["actions"])
                    after = before if before in allowed else allowed[0]
                else:
                    forbidden = {Action(value) for value in parameters["actions"]}
                    after = before
                    if before in forbidden:
                        after = next(action for action in Action if action not in forbidden)
                context.actions[target_index] = after
                context.action_controlled.add(target_index)
                log.update(before=before.value, after=after.value)

        elif effect.category == EffectCategory.STATUS_CONTROL:
            selector = parameters["selector"]
            selected = list(range(len(target.statuses)))
            if selector["type"] == "status_id":
                selected = [
                    index for index in selected
                    if target.statuses[index].name == selector["value"]
                ]
            elif selector["type"] == "polarity":
                selected = [
                    index for index in selected
                    if target.statuses[index].polarity == selector["value"]
                ]
            order = selector.get("order", "oldest")
            if order == "newest":
                selected.reverse()
            elif order == "highest_priority":
                selected.sort(
                    key=lambda index: target.statuses[index].priority,
                    reverse=True,
                )
            if effect.operation == StatusControlOperation.REMOVE:
                selected = [
                    index for index in selected
                    if target.statuses[index].removable
                ][:parameters.get("count", 1)]
                before = len(target.statuses)
                removed = set(selected)
                target.statuses = [
                    status for index, status in enumerate(target.statuses)
                    if index not in removed
                ]
                log.update(before=before, after=len(target.statuses))
            else:
                before = [target.statuses[index].remaining_turns for index in selected]
                for index in selected:
                    target.statuses[index].remaining_turns += parameters["value"]
                target.statuses = [
                    status for status in target.statuses if status.remaining_turns > 0
                ]
                log.update(before=before, after=[
                    status.remaining_turns for status in target.statuses
                ])

        elif effect.category == EffectCategory.SKILL_CONTROL:
            selector = parameters["selector"]
            selected_skill_id = selector.get("value")
            if (
                selector["type"] == "skill_id"
                and self._owned_skill(target, selected_skill_id) is None
            ):
                log.update(applied=False, reason="skill_not_owned")
                context.effect_log.append(log)
                return
            if effect.operation == SkillControlOperation.MODIFY_COST:
                resource = parameters["resource"]
                if selector["type"] == "next_used_skill":
                    before = target.next_skill_cost_modifiers.get(resource, 0)
                    target.next_skill_cost_modifiers[resource] = (
                        before + parameters["value"]
                    )
                    after = target.next_skill_cost_modifiers[resource]
                else:
                    modifiers = target.skill_cost_modifiers.setdefault(
                        selected_skill_id, {}
                    )
                    before = modifiers.get(resource, 0)
                    modifiers[resource] = before + parameters["value"]
                    after = modifiers[resource]
                log.update(resource=resource, before=before, after=after)
            elif effect.operation == SkillControlOperation.CHANGE_COOLDOWN:
                before = target.skill_cooldowns.get(selected_skill_id, 0)
                after = max(0, before + int(parameters["value"]))
                target.skill_cooldowns[selected_skill_id] = after
                log.update(before=before, after=after)
            else:
                before = target.skill_uses_remaining.get(selected_skill_id)
                if before is None:
                    after = None
                else:
                    after = max(0, before + int(parameters["value"]))
                    target.skill_uses_remaining[selected_skill_id] = after
                log.update(before=before, after=after)

        context.effect_log.append(log)

    def _finalize_dice(self, context: EffectResolutionContext) -> None:
        for target_index in range(2):
            raw = context.raw_dice[target_index]
            if raw is None:
                continue
            candidates = context.dice_ranges[target_index]
            if not candidates:
                context.final_dice[target_index] = raw
                continue
            chosen = max(
                candidates,
                key=lambda item: (item[0], -item[1], item[2], -item[3]),
            )
            minimum, maximum, _, _, chosen_log = chosen
            if minimum > maximum:
                final = minimum
            else:
                final = min(maximum, max(minimum, raw))
            context.final_dice[target_index] = int(final)
            for candidate in candidates:
                candidate_log = candidate[4]
                candidate_log["pending"] = False
                candidate_log["raw_die"] = raw
                candidate_log["final_die"] = int(final)
                candidate_log["selected"] = candidate is chosen

    @staticmethod
    def _delta_from_context(context: EffectResolutionContext, index: int) -> Delta:
        values = context.deltas[index]
        return Delta(
            math.floor(values["hp"]),
            math.floor(values["stamina"]),
            math.floor(values["break_gauge"]),
        )

    def run(self) -> MatchResult:
        while self.outcome is None:
            if self.round_number > self.max_rounds:
                self.outcome = "STALEMATE"
                break
            self.play_turn()

        return MatchResult(
            seed=self.seed,
            outcome=self.outcome,
            winner=self.winner,
            turns=self.match_turn,
            rounds=min(self.round_number, self.max_rounds),
            metrics=self.metrics,
            final_player=self.player,
            final_enemy=self.enemy,
            trace=self.trace,
        )

    def play_turn(self) -> None:
        if self.outcome is not None:
            return

        self.match_turn += 1
        self.turn_in_round += 1
        self._skills_committed_this_turn.clear()
        self._current_effect_context = None
        before = [character.snapshot() for character in self.characters]

        groggy_count = sum(character.is_groggy for character in self.characters)
        self.metrics.groggy_character_turns += groggy_count

        if self.player.is_down or self.enemy.is_down:
            resolution = self._resolve_down_wait_turn()
        elif self.player.is_groggy or self.enemy.is_groggy:
            resolution = self._resolve_groggy_turn()
        else:
            resolution = self._resolve_normal_turn()

        if self._current_effect_context is not None and self.turn_in_round >= 8:
            self._dispatch_timing(
                Timing.ON_ROUND_END, self._current_effect_context
            )
            self._after_resource_change()
            resolution["effects"] = list(
                self._current_effect_context.effect_log
            )
        self._tick_skill_cooldowns()
        self._tick_active_statuses()
        after = [character.snapshot() for character in self.characters]
        self._log("turn", resolution=resolution, before=before, after=after)

        if self.outcome is None and self.turn_in_round >= 8:
            self._end_round(self._current_effect_context)

    def _resolve_normal_turn(self) -> dict[str, Any]:
        # Both contexts are built before either current action is recorded, so
        # neither strategy can inspect the opponent's simultaneous choice.
        player_intent = self._choose_intent(0)
        enemy_intent = self._choose_intent(1)
        intents = (player_intent, enemy_intent)
        self.commit_intents(intents, upcoming_turn=False)
        self.intent_history[0].append(player_intent)
        self.intent_history[1].append(enemy_intent)
        context = EffectResolutionContext(
            intents=intents,
            actions=[player_intent.base_action, enemy_intent.base_action],
        )
        self._current_effect_context = context
        self._dispatch_timing(Timing.ON_SKILL_COMMIT, context)
        self._dispatch_timing(Timing.BEFORE_ACTION_REVEAL, context)
        player_action, enemy_action = context.actions
        self.action_history[0].append(player_action)
        self.action_history[1].append(enemy_action)
        self._dispatch_timing(Timing.BEFORE_ROLL, context)
        player_die = self.rng.randint(1, 6)
        enemy_die = self.rng.randint(1, 6)
        context.raw_dice = [player_die, enemy_die]
        context.final_dice = [player_die, enemy_die]
        self._dispatch_timing(Timing.AFTER_RAW_ROLL, context)
        self._dispatch_timing(Timing.BEFORE_DICE_COMPARE, context)
        self._finalize_dice(context)
        final_player_die = context.final_dice[0]
        final_enemy_die = context.final_dice[1]
        assert final_player_die is not None and final_enemy_die is not None
        dice_result = compare_dice(final_player_die, final_enemy_die)
        context.dice_result = dice_result
        entry = RESULT_TABLE[(player_action, enemy_action, dice_result)]
        context.entry_id = entry.entry_id
        context.deltas = [
            {
                "hp": entry.player.hp,
                "stamina": entry.player.stamina,
                "break_gauge": entry.player.break_gauge,
            },
            {
                "hp": entry.enemy.hp,
                "stamina": entry.enemy.stamina,
                "break_gauge": entry.enemy.break_gauge,
            },
        ]
        self._dispatch_timing(Timing.BEFORE_RESULT_APPLY, context)
        self.exchange_history[0].append(
            StrategyExchange(
                player_action, enemy_action, final_player_die, final_enemy_die
            )
        )
        self.exchange_history[1].append(
            StrategyExchange(
                enemy_action, player_action, final_enemy_die, final_player_die
            )
        )

        self.metrics.action_counts[f"player:{player_action.value}"] += 1
        self.metrics.action_counts[f"enemy:{enemy_action.value}"] += 1
        self.metrics.table_entry_counts[entry.entry_id] += 1

        applied_player_delta = self._delta_from_context(context, 0)
        applied_enemy_delta = self._delta_from_context(context, 1)
        apply_delta(self.player, applied_player_delta)
        apply_delta(self.enemy, applied_enemy_delta)
        self._dispatch_timing(Timing.AFTER_RESULT_APPLY, context)
        self._after_resource_change()
        self._finalize_intent_cooldowns(intents)
        return {
            "kind": "normal",
            "player_action": player_action.value,
            "enemy_action": enemy_action.value,
            "player_skill": player_intent.active_skill_id,
            "enemy_skill": enemy_intent.active_skill_id,
            "player_die": player_die,
            "enemy_die": enemy_die,
            "player_final_die": final_player_die,
            "enemy_final_die": final_enemy_die,
            "dice_result": dice_result.value,
            "entry_id": entry.entry_id,
            "base_player_delta": asdict(entry.player),
            "base_enemy_delta": asdict(entry.enemy),
            "applied_player_delta": asdict(applied_player_delta),
            "applied_enemy_delta": asdict(applied_enemy_delta),
            "effects": list(context.effect_log),
        }

    def _resolve_groggy_turn(self) -> dict[str, Any]:
        if self.player.is_groggy and self.enemy.is_groggy:
            return {"kind": "both_groggy_idle"}

        if self.enemy.is_groggy:
            actor = self.player
            target = self.enemy
            actor_index = 0
        else:
            actor = self.enemy
            target = self.player
            actor_index = 1

        intent = self._choose_intent(actor_index)
        self.commit_intents((intent,), upcoming_turn=False)
        self.intent_history[actor_index].append(intent)
        context = EffectResolutionContext(
            intents=(intent,),
            actions=[Action.ATTACK, Action.ATTACK],
        )
        self._current_effect_context = context
        context.actions[actor_index] = intent.base_action
        self._dispatch_timing(Timing.ON_SKILL_COMMIT, context)
        self._dispatch_timing(Timing.BEFORE_ACTION_REVEAL, context)
        action = context.actions[actor_index]
        self.action_history[actor_index].append(action)
        entry = GROGGY_TABLE[action]
        context.entry_id = entry.entry_id
        actor_delta = {
            "hp": entry.player.hp,
            "stamina": entry.player.stamina,
            "break_gauge": entry.player.break_gauge,
        }
        target_delta = {
            "hp": entry.enemy.hp,
            "stamina": entry.enemy.stamina,
            "break_gauge": entry.enemy.break_gauge,
        }
        context.deltas[actor_index] = actor_delta
        context.deltas[1 - actor_index] = target_delta
        self._dispatch_timing(Timing.BEFORE_RESULT_APPLY, context)
        self.metrics.action_counts[
            f"{'player' if actor_index == 0 else 'enemy'}:{action.value}"
        ] += 1
        self.metrics.table_entry_counts[entry.entry_id] += 1

        applied_actor_delta = self._delta_from_context(context, actor_index)
        applied_target_delta = self._delta_from_context(context, 1 - actor_index)
        apply_delta(actor, applied_actor_delta)
        apply_delta(target, applied_target_delta)
        self._dispatch_timing(Timing.AFTER_RESULT_APPLY, context)
        self._after_resource_change()
        self._finalize_intent_cooldowns((intent,))
        return {
            "kind": "groggy",
            "actor": actor.name,
            "target": target.name,
            "action": action.value,
            "skill": intent.active_skill_id,
            "entry_id": entry.entry_id,
            "applied_actor_delta": asdict(applied_actor_delta),
            "applied_target_delta": asdict(applied_target_delta),
            "effects": list(context.effect_log),
        }

    def _resolve_down_wait_turn(self) -> dict[str, Any]:
        self.metrics.wait_turns += 1
        down_at_start = [character.is_down for character in self.characters]
        recovered: list[str] = []
        woke: list[str] = []

        # A standing character waits and heals while the opponent remains down.
        if down_at_start == [True, False]:
            self._waiting_heal(self.enemy)
            recovered.append(self.enemy.name)
        elif down_at_start == [False, True]:
            self._waiting_heal(self.player)
            recovered.append(self.player.name)

        for character in self.characters:
            if not character.is_down:
                continue
            character.skipped_turns_remaining -= 1
            if character.skipped_turns_remaining <= 0:
                self._wake(character)
                woke.append(character.name)

        return {"kind": "down_wait", "healed": recovered, "woke": woke}

    @staticmethod
    def _waiting_heal(character: CharacterState) -> None:
        heal = floor_percent(character.max_hp, 0.04)
        character.hp = min(character.max_hp, character.hp + heal)

    def _after_resource_change(self) -> None:
        # Groggy is checked before down, matching the rulebook pipeline.
        for index, character in enumerate(self.characters):
            if (
                not character.is_groggy
                and not character.is_down
                and not character.is_ko
                and character.break_gauge >= character.max_break_gauge
            ):
                character.is_groggy = True
                self.metrics.groggy_entries[index] += 1

        newly_down: list[CharacterState] = []
        for index, character in enumerate(self.characters):
            if character.hp > 0 or character.is_down or character.is_ko:
                continue
            character.down_count += 1
            self.metrics.down_events[index] += 1
            newly_down.append(character)
            if character.down_count >= character.max_down_count:
                character.is_ko = True
            else:
                character.is_down = True
                character.skipped_turns_remaining = character.down_count

        if len(newly_down) == 2:
            self.metrics.double_downs += 1

        player_ko = self.player.is_ko
        enemy_ko = self.enemy.is_ko
        if player_ko and enemy_ko:
            self.outcome = "DOUBLE_KO"
            self.winner = None
        elif player_ko:
            self.outcome = "ENEMY_WIN"
            self.winner = self.enemy.name
        elif enemy_ko:
            self.outcome = "PLAYER_WIN"
            self.winner = self.player.name

    @staticmethod
    def _wake(character: CharacterState) -> None:
        character.is_down = False
        character.skipped_turns_remaining = 0
        character.hp = floor_percent(character.max_hp, 0.50)
        character.break_gauge = floor_percent(character.max_break_gauge, 0.50)
        character.is_groggy = False

    def _tick_active_statuses(self) -> None:
        for character_index, character in enumerate(self.characters):
            opponent = self.characters[1 - character_index]
            actionable = (
                not character.is_down
                and not character.is_groggy
                and not character.is_ko
                and not opponent.is_down
            )
            kept: list[StatusEffect] = []
            for status in character.statuses:
                active = status.applied_on_match_turn < self.match_turn
                unit = status.duration_unit
                if active and (
                    unit in {
                        DurationUnit.OWNER_TURN.value,
                        DurationUnit.EXCHANGE.value,
                    }
                    or (
                        unit == DurationUnit.OWNER_ACTIONABLE_TURN.value
                        and actionable
                    )
                ):
                    status.remaining_turns -= 1
                if status.remaining_turns > 0:
                    kept.append(status)
            character.statuses = kept

            kept_queued: list[QueuedEffect] = []
            for queued in character.queued_effects:
                active = queued.applied_on_match_turn < self.match_turn
                unit = queued.duration_unit
                if active and (
                    unit in {
                        DurationUnit.OWNER_TURN.value,
                        DurationUnit.EXCHANGE.value,
                    }
                    or (
                        unit == DurationUnit.OWNER_ACTIONABLE_TURN.value
                        and actionable
                    )
                ):
                    queued.remaining_turns -= 1
                if queued.remaining_turns > 0:
                    kept_queued.append(queued)
            character.queued_effects = kept_queued

    def _end_round(
        self, context: EffectResolutionContext | None = None
    ) -> None:
        interval_before = [character.snapshot() for character in self.characters]
        # Any non-KO downed character rises immediately before interval recovery.
        for character in self.characters:
            if character.is_down and not character.is_ko:
                self._wake(character)

        for character in self.characters:
            if character.is_ko:
                continue
            character.hp = min(
                character.max_hp,
                character.hp + floor_percent(character.max_hp, 0.33),
            )
            character.stamina = min(
                character.max_stamina,
                character.stamina
                + floor_percent(character.max_stamina, 0.50),
            )
            character.break_gauge = floor_percent(character.break_gauge, 0.50)
            character.is_groggy = False
            for status in character.statuses:
                if status.duration_unit == DurationUnit.ROUND.value:
                    status.remaining_turns -= 1
                else:
                    status.remaining_turns -= 2
            character.statuses = [
                status for status in character.statuses if status.remaining_turns > 0
            ]
            for queued in character.queued_effects:
                if queued.duration_unit == DurationUnit.ROUND.value:
                    queued.remaining_turns -= 1
            character.queued_effects = [
                queued for queued in character.queued_effects
                if queued.remaining_turns > 0
            ]
            for owned in character.skill_loadout:
                resolved = self._owned_skill(character, owned.skill_id)
                assert resolved is not None
                _, _, level = resolved
                if (
                    level.cooldown.decrements == CooldownDecrement.ROUND_END
                    and character.skill_cooldowns[owned.skill_id] > 0
                ):
                    character.skill_cooldowns[owned.skill_id] -= 1
                character.skill_round_uses_remaining[owned.skill_id] = (
                    level.usage_limit.per_round
                )

        if context is not None:
            effect_start = len(context.effect_log)
            self._dispatch_timing(Timing.ON_INTERVAL, context)
            self._after_resource_change()
            interval_effects = list(context.effect_log[effect_start:])
        else:
            interval_effects = []

        self._log(
            "interval",
            before=interval_before,
            after=[character.snapshot() for character in self.characters],
            effects=interval_effects,
        )
        self.round_number += 1
        self.turn_in_round = 0


class ManualBattleEngine(BattleEngine):
    """Interactive adapter that accepts the Player action from an external UI."""

    def __init__(
        self,
        seed: int,
        *,
        enemy_strategy: str,
        max_rounds: int = 100,
        trace_enabled: bool = True,
        skill_registry: Mapping[str, SkillDefinition] | None = None,
        player_skills: Iterable[OwnedSkill] = (),
        enemy_skills: Iterable[OwnedSkill] = (),
    ) -> None:
        super().__init__(
            seed,
            max_rounds=max_rounds,
            trace_enabled=trace_enabled,
            # The adapter intercepts Player decisions before this fallback is used.
            player_strategy="random",
            enemy_strategy=enemy_strategy,
            skill_registry=skill_registry,
            player_skills=player_skills,
            enemy_skills=enemy_skills,
        )
        self._submitted_player_action: Action | None = None
        self._submitted_player_intent: TurnIntent | None = None

    @property
    def player_can_choose(self) -> bool:
        if self.outcome is not None:
            return False
        return (
            not self.player.is_down
            and not self.player.is_groggy
            and not self.enemy.is_down
        )

    def _choose_action(self, actor_index: int) -> Action:
        if actor_index == 0:
            if self._submitted_player_action is None:
                raise RuntimeError("a Player action must be submitted for this turn")
            return self._submitted_player_action
        return super()._choose_action(actor_index)

    def _choose_intent(self, actor_index: int) -> TurnIntent:
        if actor_index == 0:
            if self._submitted_player_intent is not None:
                return self._submitted_player_intent
            if self._submitted_player_action is None:
                raise RuntimeError("a Player intent must be submitted for this turn")
        return super()._choose_intent(actor_index)

    def submit_player_action(self, action: Action | str) -> None:
        self.submit_player_intent(TurnIntent("player", Action(action)))

    def submit_player_intent(self, intent: TurnIntent) -> None:
        if not self.player_can_choose:
            raise RuntimeError("the Player cannot choose an action in the current state")
        if intent.actor_id != "player":
            raise InvalidTurnIntent(IntentValidationResult((IntentValidationIssue(
                "actor_mismatch",
                "manual Player intent must use actor_id 'player'",
            ),)))
        validation = self.validate_intent(intent)
        if not validation.valid:
            raise InvalidTurnIntent(validation)
        self._submitted_player_intent = intent
        self._submitted_player_action = intent.base_action
        try:
            self.play_turn()
        finally:
            self._submitted_player_intent = None
            self._submitted_player_action = None

    def advance_forced_turn(self) -> None:
        if self.outcome is not None:
            return
        if self.player_can_choose:
            raise RuntimeError("the Player must choose an action for this turn")
        self.play_turn()

    def advance_until_player_choice(self, *, max_turns: int = 16) -> int:
        """Resolve down/groggy forced turns and stop at the next Player decision."""
        advanced = 0
        while self.outcome is None and not self.player_can_choose:
            if advanced >= max_turns:
                raise RuntimeError("forced-turn safety limit reached")
            self.advance_forced_turn()
            advanced += 1
        return advanced


def percentile(sorted_values: list[int], percentile_value: float) -> float:
    """Linear interpolation percentile, matching common statistical tools."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    position = (len(sorted_values) - 1) * percentile_value
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(sorted_values[lower])
    fraction = position - lower
    return sorted_values[lower] + (
        sorted_values[upper] - sorted_values[lower]
    ) * fraction


def _summarize_results(
    results: list[MatchResult],
    *,
    matches: int,
    seed: int,
    max_rounds: int,
    player_strategy: str,
    enemy_strategy: str,
) -> dict[str, Any]:
    completed_turns = sorted(
        result.turns for result in results if result.outcome != "STALEMATE"
    )
    all_turns = sorted(result.turns for result in results)
    all_rounds = sorted(result.rounds for result in results)
    outcomes = Counter(result.outcome for result in results)
    action_counts: Counter[str] = Counter()
    table_counts: Counter[str] = Counter()
    total_groggy_entries = [0, 0]
    total_downs = [0, 0]
    groggy_character_turns = 0
    wait_turns = 0
    double_downs = 0

    for result in results:
        action_counts.update(result.metrics.action_counts)
        table_counts.update(result.metrics.table_entry_counts)
        total_groggy_entries[0] += result.metrics.groggy_entries[0]
        total_groggy_entries[1] += result.metrics.groggy_entries[1]
        total_downs[0] += result.metrics.down_events[0]
        total_downs[1] += result.metrics.down_events[1]
        groggy_character_turns += result.metrics.groggy_character_turns
        wait_turns += result.metrics.wait_turns
        double_downs += result.metrics.double_downs

    mean_turns = sum(all_turns) / matches
    return {
        "config": {
            "matches": matches,
            "seed": seed,
            "max_rounds": max_rounds,
            "player_strategy": player_strategy,
            "enemy_strategy": enemy_strategy,
            "target_pacing": "around_5_rounds",
        },
        "outcomes": dict(sorted(outcomes.items())),
        "rates_percent": {
            key: round(value * 100 / matches, 4)
            for key, value in sorted(outcomes.items())
        },
        "turns": {
            "mean": round(mean_turns, 4),
            "median": round(percentile(all_turns, 0.50), 4),
            "p25": round(percentile(all_turns, 0.25), 4),
            "p75": round(percentile(all_turns, 0.75), 4),
            "p90": round(percentile(all_turns, 0.90), 4),
            "p95": round(percentile(all_turns, 0.95), 4),
            "min": all_turns[0],
            "max": all_turns[-1],
            "within_5_rounds_percent": round(
                sum(value <= 40 for value in all_turns) * 100 / matches, 4
            ),
            # Backward-compatible alias for existing reports.
            "within_40_percent": round(
                sum(value <= 40 for value in all_turns) * 100 / matches, 4
            ),
            "over_10_rounds_percent": round(
                sum(value > 80 for value in all_turns) * 100 / matches, 4
            ),
            "over_80_percent": round(
                sum(value > 80 for value in all_turns) * 100 / matches, 4
            ),
            "completed_mean": round(
                sum(completed_turns) / len(completed_turns), 4
            )
            if completed_turns
            else None,
        },
        "rounds": {
            "mean": round(sum(all_rounds) / matches, 4),
            "median": round(percentile(all_rounds, 0.50), 4),
            "p95": round(percentile(all_rounds, 0.95), 4),
        },
        "per_match_means": {
            "player_downs": round(total_downs[0] / matches, 4),
            "enemy_downs": round(total_downs[1] / matches, 4),
            "player_groggy_entries": round(total_groggy_entries[0] / matches, 4),
            "enemy_groggy_entries": round(total_groggy_entries[1] / matches, 4),
            "groggy_character_turns": round(groggy_character_turns / matches, 4),
            "down_wait_turns": round(wait_turns / matches, 4),
            "double_downs": round(double_downs / matches, 4),
        },
        "action_counts": dict(sorted(action_counts.items())),
        "table_entry_counts": dict(
            sorted(table_counts.items(), key=lambda item: item[0])
        ),
    }


def simulate_matchup(
    matches: int,
    *,
    seed: int,
    max_rounds: int = 100,
    player_strategy: str = "random",
    enemy_strategy: str = "random",
) -> dict[str, Any]:
    if matches <= 0:
        raise ValueError("matches must be positive")

    seed_rng = random.Random(seed)
    results: list[MatchResult] = []
    for _ in range(matches):
        match_seed = seed_rng.getrandbits(64)
        results.append(
            BattleEngine(
                match_seed,
                max_rounds=max_rounds,
                player_strategy=player_strategy,
                enemy_strategy=enemy_strategy,
            ).run()
        )
    return _summarize_results(
        results,
        matches=matches,
        seed=seed,
        max_rounds=max_rounds,
        player_strategy=player_strategy,
        enemy_strategy=enemy_strategy,
    )


def simulate_batch(
    matches: int,
    *,
    seed: int,
    max_rounds: int = 100,
) -> dict[str, Any]:
    """Backward-compatible random-versus-random batch simulation."""
    return simulate_matchup(matches, seed=seed, max_rounds=max_rounds)


def simulate_strategy_matrix(
    strategies: Iterable[str],
    *,
    matches_per_matchup: int,
    seed: int,
    max_rounds: int = 100,
) -> dict[str, Any]:
    names = list(dict.fromkeys(strategies))
    return simulate_strategy_grid(
        names,
        names,
        matches_per_matchup=matches_per_matchup,
        seed=seed,
        max_rounds=max_rounds,
    )


def simulate_strategy_grid(
    player_strategies: Iterable[str],
    enemy_strategies: Iterable[str],
    *,
    matches_per_matchup: int,
    seed: int,
    max_rounds: int = 100,
) -> dict[str, Any]:
    player_names = list(dict.fromkeys(player_strategies))
    enemy_names = list(dict.fromkeys(enemy_strategies))
    names = player_names + enemy_names
    if not player_names or not enemy_names:
        raise ValueError("at least one player and enemy strategy is required")
    invalid = [name for name in names if name not in STRATEGY_NAMES]
    if invalid:
        raise ValueError(f"unknown strategies: {', '.join(invalid)}")
    if matches_per_matchup <= 0:
        raise ValueError("matches_per_matchup must be positive")

    matchup_seed_rng = random.Random(seed)
    matchups: list[dict[str, Any]] = []
    for player_strategy in player_names:
        for enemy_strategy in enemy_names:
            matchup_seed = matchup_seed_rng.getrandbits(64)
            summary = simulate_matchup(
                matches_per_matchup,
                seed=matchup_seed,
                max_rounds=max_rounds,
                player_strategy=player_strategy,
                enemy_strategy=enemy_strategy,
            )
            matchups.append(
                {
                    "player_strategy": player_strategy,
                    "enemy_strategy": enemy_strategy,
                    "outcomes": summary["outcomes"],
                    "rates_percent": summary["rates_percent"],
                    "mean_turns": summary["turns"]["mean"],
                    "median_turns": summary["turns"]["median"],
                    "p95_turns": summary["turns"]["p95"],
                    "mean_rounds": summary["rounds"]["mean"],
                    "within_5_rounds_percent": summary["turns"][
                        "within_5_rounds_percent"
                    ],
                    "over_10_rounds_percent": summary["turns"][
                        "over_10_rounds_percent"
                    ],
                }
            )
    return {
        "config": {
            "player_strategies": player_names,
            "enemy_strategies": enemy_names,
            "strategies": player_names if player_names == enemy_names else None,
            "matches_per_matchup": matches_per_matchup,
            "seed": seed,
            "max_rounds": max_rounds,
            "target_pacing": "around_5_rounds",
        },
        "matchups": matchups,
    }


def _signed(value: int) -> str:
    return f"+{value}" if value > 0 else str(value)


def _character_label(name: str) -> str:
    return {"Player": "플레이어", "Enemy": "적"}.get(name, name)


def _resource_change_lines(
    label: str, before: dict[str, Any], after: dict[str, Any]
) -> list[str]:
    names = (("hp", "HP"), ("stamina", "스태미너"), ("break_gauge", "브레이크"))
    changes: list[str] = []
    for key, display_name in names:
        difference = after[key] - before[key]
        if difference:
            changes.append(
                f"{display_name} {before[key]}→{after[key]}({_signed(difference)})"
            )
    if not changes:
        changes.append("자원 변화 없음")
    return [f"  - {label}: " + ", ".join(changes)]


def _state_event_lines(
    label: str, before: dict[str, Any], after: dict[str, Any]
) -> list[str]:
    lines: list[str] = []
    if not before["is_groggy"] and after["is_groggy"]:
        lines.append(f"  - {label}: 브레이크 게이지가 최대가 되어 완전 그로기에 빠졌습니다.")
    if after["down_count"] > before["down_count"]:
        lines.append(
            f"  - {label}: 다운! 다운 카운트가 "
            f"{after['down_count']}회가 됐습니다."
        )
    if not before["is_ko"] and after["is_ko"]:
        lines.append(f"  - {label}: 최대 다운 카운트에 도달하여 KO됐습니다.")
    elif not before["is_down"] and after["is_down"]:
        lines.append(
            f"  - {label}: 앞으로 {after['skipped_turns_remaining']}턴 동안 다운 상태입니다."
        )
    if before["is_down"] and not after["is_down"] and not after["is_ko"]:
        lines.append(f"  - {label}: 최대 HP의 50%로 기상했습니다.")
    if before["is_groggy"] and not after["is_groggy"] and not before["is_down"]:
        lines.append(f"  - {label}: 완전 그로기가 해제됐습니다.")
    return lines


def _turn_explanation(event: dict[str, Any]) -> str:
    resolution = event["resolution"]
    before = event["before"]
    after = event["after"]
    heading = (
        f"[라운드 {event['round']} · 턴 {event['turn_in_round']} "
        f"· 전체 {event['match_turn']}턴]"
    )
    lines = [heading]

    if resolution["kind"] == "normal":
        player_action = ACTION_LABELS[Action(resolution["player_action"])]
        enemy_action = ACTION_LABELS[Action(resolution["enemy_action"])]
        dice_label = DICE_RESULT_LABELS[DiceResult(resolution["dice_result"])]
        lines.append(
            f"  플레이어는 {player_action}(d6={resolution['player_die']}), "
            f"적은 {enemy_action}(d6={resolution['enemy_die']})을 선택했습니다. "
            f"{dice_label}입니다."
        )
        lines.append(
            f"  판정 {resolution['entry_id']}: "
            f"{RESULT_CONCEPTS[resolution['entry_id']]}"
        )
    elif resolution["kind"] == "groggy":
        action = ACTION_OBJECT_LABELS[Action(resolution["action"])]
        actor = _character_label(resolution["actor"])
        target = _character_label(resolution["target"])
        lines.append(
            f"  {target}: 완전 그로기로 행동할 수 없습니다. "
            f"{actor}: {action} 선택하여 Dice Win 1.5배 판정을 자동 적용합니다."
        )
        lines.append(
            f"  판정 {resolution['entry_id']}: "
            f"{RESULT_CONCEPTS[resolution['entry_id']]}"
        )
    elif resolution["kind"] == "both_groggy_idle":
        lines.append("  양측 모두 완전 그로기 상태라 행동하지 못하고 턴이 경과합니다.")
    elif resolution["kind"] == "down_wait":
        healed = resolution["healed"]
        woke = resolution["woke"]
        if healed:
            healed_labels = ", ".join(_character_label(name) for name in healed)
            lines.append(
                f"  대기 회복: {healed_labels}, 최대 HP의 4%를 회복했습니다."
            )
        else:
            lines.append("  양측이 다운되어 다운 카운트만 진행됩니다.")
        if woke:
            woke_labels = ", ".join(_character_label(name) for name in woke)
            lines.append(f"  기상: {woke_labels}, 이번 턴 종료와 함께 일어났습니다.")

    lines.extend(_resource_change_lines("플레이어", before[0], after[0]))
    lines.extend(_resource_change_lines("적", before[1], after[1]))
    lines.extend(_state_event_lines("플레이어", before[0], after[0]))
    lines.extend(_state_event_lines("적", before[1], after[1]))
    return "\n".join(lines)


def _interval_explanation(event: dict[str, Any]) -> str:
    before = event["before"]
    after = event["after"]
    lines = [f"[라운드 {event['round']} 종료 · 인터벌]"]
    lines.append(
        "  출전 캐릭터에게 HP 33%, 스태미너 50% 회복과 브레이크 절반 감소를 적용합니다."
    )
    lines.extend(_resource_change_lines("플레이어", before[0], after[0]))
    lines.extend(_resource_change_lines("적", before[1], after[1]))
    lines.extend(_state_event_lines("플레이어", before[0], after[0]))
    lines.extend(_state_event_lines("적", before[1], after[1]))
    return "\n".join(lines)


def iter_trace_lines(result: MatchResult) -> Iterable[str]:
    yield (
        "=== 단일 경기 상세 해설 ===\n"
        f"시드: {result.seed} · 총 {result.turns}턴 · {result.rounds}라운드"
    )
    for event in result.trace:
        if event["event"] == "interval":
            yield _interval_explanation(event)
        else:
            yield _turn_explanation(event)

    if result.outcome == "PLAYER_WIN":
        conclusion = "플레이어 승리"
    elif result.outcome == "ENEMY_WIN":
        conclusion = "적 승리"
    elif result.outcome == "DOUBLE_KO":
        conclusion = "더블 KO 무승부"
    else:
        conclusion = "안전 한도 도달로 교착 처리"
    yield f"=== 경기 종료: {conclusion} ({result.turns}턴) ==="
