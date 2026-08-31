"""Round/turn battle POC simulation engine.

The implementation follows:
- ROUND_TURN_BATTLE_POC_RULEBOOK.md v0.6
- BASIC_RESULT_TABLE_DRAFT_V0.1.md (document version 0.4)

Only the no-skill, symmetric 1v1 random-policy test bed is implemented here.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from enum import Enum
import math
import random
from typing import Any, Iterable


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
            "statuses": [asdict(status) for status in self.statuses],
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
        return (Action.ATTACK, Action.ATTACK, Action.EVADE)[
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
    """Symmetric, no-skill 1v1 battle engine with injectable action policies."""

    def __init__(
        self,
        seed: int,
        *,
        max_rounds: int = 100,
        trace_enabled: bool = False,
        player_strategy: str = "random",
        enemy_strategy: str = "random",
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
        self.player = CharacterState("Player")
        self.enemy = CharacterState("Enemy")
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
        before = [character.snapshot() for character in self.characters]

        groggy_count = sum(character.is_groggy for character in self.characters)
        self.metrics.groggy_character_turns += groggy_count

        if self.player.is_down or self.enemy.is_down:
            resolution = self._resolve_down_wait_turn()
        elif self.player.is_groggy or self.enemy.is_groggy:
            resolution = self._resolve_groggy_turn()
        else:
            resolution = self._resolve_normal_turn()

        self._tick_active_statuses()
        after = [character.snapshot() for character in self.characters]
        self._log("turn", resolution=resolution, before=before, after=after)

        if self.outcome is None and self.turn_in_round >= 8:
            self._end_round()

    def _resolve_normal_turn(self) -> dict[str, Any]:
        # Both contexts are built before either current action is recorded, so
        # neither strategy can inspect the opponent's simultaneous choice.
        player_action = self._choose_action(0)
        enemy_action = self._choose_action(1)
        self.action_history[0].append(player_action)
        self.action_history[1].append(enemy_action)
        player_die = self.rng.randint(1, 6)
        enemy_die = self.rng.randint(1, 6)
        dice_result = compare_dice(player_die, enemy_die)
        entry = RESULT_TABLE[(player_action, enemy_action, dice_result)]
        self.exchange_history[0].append(
            StrategyExchange(player_action, enemy_action, player_die, enemy_die)
        )
        self.exchange_history[1].append(
            StrategyExchange(enemy_action, player_action, enemy_die, player_die)
        )

        self.metrics.action_counts[f"player:{player_action.value}"] += 1
        self.metrics.action_counts[f"enemy:{enemy_action.value}"] += 1
        self.metrics.table_entry_counts[entry.entry_id] += 1

        apply_delta(self.player, entry.player)
        apply_delta(self.enemy, entry.enemy)
        self._after_resource_change()
        return {
            "kind": "normal",
            "player_action": player_action.value,
            "enemy_action": enemy_action.value,
            "player_die": player_die,
            "enemy_die": enemy_die,
            "dice_result": dice_result.value,
            "entry_id": entry.entry_id,
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

        action = self._choose_action(actor_index)
        self.action_history[actor_index].append(action)
        entry = GROGGY_TABLE[action]
        self.metrics.action_counts[
            f"{'player' if actor_index == 0 else 'enemy'}:{action.value}"
        ] += 1
        self.metrics.table_entry_counts[entry.entry_id] += 1

        # GROGGY_TABLE is stored from actor/target perspective.
        apply_delta(actor, entry.player)
        apply_delta(target, entry.enemy)
        self._after_resource_change()
        return {
            "kind": "groggy",
            "actor": actor.name,
            "target": target.name,
            "action": action.value,
            "entry_id": entry.entry_id,
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
        for character in self.characters:
            kept: list[StatusEffect] = []
            for status in character.statuses:
                if status.applied_on_match_turn < self.match_turn:
                    status.remaining_turns -= 1
                if status.remaining_turns > 0:
                    kept.append(status)
            character.statuses = kept

    def _end_round(self) -> None:
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
                status.remaining_turns -= 2
            character.statuses = [
                status for status in character.statuses if status.remaining_turns > 0
            ]

        self._log(
            "interval",
            before=interval_before,
            after=[character.snapshot() for character in self.characters],
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
    ) -> None:
        super().__init__(
            seed,
            max_rounds=max_rounds,
            trace_enabled=trace_enabled,
            # The adapter intercepts Player decisions before this fallback is used.
            player_strategy="random",
            enemy_strategy=enemy_strategy,
        )
        self._submitted_player_action: Action | None = None

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

    def submit_player_action(self, action: Action | str) -> None:
        if not self.player_can_choose:
            raise RuntimeError("the Player cannot choose an action in the current state")
        self._submitted_player_action = Action(action)
        try:
            self.play_turn()
        finally:
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
