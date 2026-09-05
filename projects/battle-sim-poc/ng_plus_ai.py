"""Bounded, public-information, three-exchange NG+ intent planning.

The forward model calls the real BattleEngine. Only immutable definitions and
explicit public state enter a request: no submitted intent or live RNG state.
Search uses root-stratified open-loop beams and common random scenarios, then
replaces sampled first-exchange value with an exact dice expectation for finalists.
"""
from __future__ import annotations

from collections import Counter
from copy import copy
from dataclasses import dataclass
import math
import random
from threading import Event
from time import perf_counter

from battle_sim import Action, BattleEngine, CharacterState, MatchMetrics, TurnIntent
from skill_schema import EffectCategory, SkillControlOperation, Target


@dataclass(frozen=True)
class SearchConfig:
    scenarios: int = 4
    beam: int = 2
    depth: int = 3
    audit: int = 4
    max_transitions: int = 6552

    def __post_init__(self):
        if not (1 <= self.scenarios <= 8 and 1 <= self.beam <= 4
                and 1 <= self.depth <= 3 and 0 <= self.audit <= 4
                and 1 <= self.max_transitions <= 15696):
            raise ValueError("NG+ search configuration exceeds supported bounds")


DEFAULT_CONFIG = SearchConfig()
REFERENCE_CONFIG = SearchConfig(8, 4, 3, 4, 15696)


class SearchCancelled(Exception):
    pass


class _BudgetReached(Exception):
    pass


def _copy_character(source):
    actor = copy(source)
    actor.statuses = [copy(status) for status in source.statuses]
    actor.queued_effects = [copy(effect) for effect in source.queued_effects]
    actor.skill_cooldowns = source.skill_cooldowns.copy()
    actor.skill_uses_remaining = source.skill_uses_remaining.copy()
    actor.skill_round_uses_remaining = source.skill_round_uses_remaining.copy()
    actor.skill_cost_modifiers = {key: value.copy() for key, value in source.skill_cost_modifiers.items()}
    actor.next_skill_cost_modifiers = source.next_skill_cost_modifiers.copy()
    return actor


class _Dice:
    def __init__(self, values):
        self.values = iter(values)

    def randint(self, _low, _high):
        return next(self.values)


class ForwardModel(BattleEngine):
    """Isolated mutable branch; never constructed by copying a live engine dict."""
    _simulation = True

    def _choose_intent(self, actor_index):
        return self.forced_intents[actor_index]

    def fork(self):
        model = object.__new__(ForwardModel)
        model.__dict__ = self.__dict__.copy()
        model.player = _copy_character(self.player)
        model.enemy = _copy_character(self.enemy)
        model.action_history = tuple(list(history[-10:]) for history in self.action_history)
        model.intent_history = tuple(list(history[-10:]) for history in self.intent_history)
        model.exchange_history = ([], [])
        model.metrics = MatchMetrics()
        model._skills_committed_this_turn = set()
        model._current_effect_context = None
        model._intent_cache = {}
        return model


def public_model(engine, *, turn_started=False):
    model = object.__new__(ForwardModel)
    model.player = _copy_character(engine.player)
    model.enemy = _copy_character(engine.enemy)
    model.skill_registry = engine.skill_registry  # Frozen definitions, not runtime.
    model.action_history = tuple(list(history[-10:]) for history in engine.action_history)
    model.intent_history = tuple(list(history[-10:]) for history in engine.intent_history)
    model.exchange_history = ([], [])
    model.round_number = engine.round_number
    model.turn_in_round = engine.turn_in_round - int(turn_started)
    model.match_turn = engine.match_turn - int(turn_started)
    model.outcome, model.winner = engine.outcome, engine.winner
    model.max_rounds = engine.max_rounds
    model.trace_enabled, model.trace = False, []
    model.metrics = MatchMetrics()
    model._skills_committed_this_turn = set()
    model._current_effect_context = None
    model._intent_cache = {}
    return model


def can_choose(model, index):
    actor, other = model.characters[index], model.characters[1-index]
    return not (model.outcome or actor.is_down or actor.is_groggy or actor.is_ko or other.is_down)


def legal_intents(model, index):
    if index in model._intent_cache:
        return model._intent_cache[index]
    if not can_choose(model, index):
        result = (TurnIntent(model._actor_id(index), Action.ATTACK),)
    else:
        result = []
        actor = model.characters[index]
        for action in model.legal_actions(index):
            result.append(TurnIntent(model._actor_id(index), action))
            for owned in actor.skill_loadout:
                intent = model._intent_with_skill(index, action, owned.skill_id)
                if model.validate_intent(intent).valid:
                    result.append(intent)
        result = tuple(result)
    model._intent_cache[index] = result
    return result


def opponent_distribution(model, index):
    """Smoothed recent action/skill-use frequencies, restricted to legal moves.

    This deliberately does not see the simultaneous candidate being evaluated.
    Future branches do contain previous *revealed* simulated turns.
    """
    intents = legal_intents(model, index)
    counts = Counter({action: 1.0 for action in Action})
    for age, action in enumerate(reversed(model.action_history[index][-8:])):
        counts[action] += .85 ** age
    history = model.intent_history[index][-8:]
    use_rate = (2 + sum(i.active_skill_id is not None for i in history)) / (4 + len(history))
    skills_per_action = Counter(i.base_action for i in intents if i.active_skill_id)
    weighted = []
    for intent in intents:
        n = skills_per_action[intent.base_action]
        conditional = (use_rate / n if intent.active_skill_id else 1-use_rate) if n else 1.0
        weighted.append((intent, counts[intent.base_action] * conditional))
    total = sum(weight for _, weight in weighted)
    return tuple((intent, weight/total) for intent, weight in weighted)


def _pick(distribution, sample):
    for intent, weight in distribution:
        sample -= weight
        if sample <= 0:
            return intent
    return distribution[-1][0]


def _uses_die_values(condition):
    return condition is not None and (condition.predicate in {
        "raw_die_is", "final_die_at_least", "final_die_at_most"}
        or any(_uses_die_values(child) for child in condition.children))


def audit_dice(model, intents):
    """Exact aggregation only if outcomes depend on compare, not die values.

    Current conditions have no previous-die predicate and our opponent model
    reads actions/intents, never exchange_history. Otherwise enumerate all 36.
    """
    if not (can_choose(model, 0) and can_choose(model, 1)):
        return (((1,1), 1.0),)
    applications = []
    for index, intent in enumerate(intents):
        if intent.active_skill_id:
            applications.extend(model._owned_skill(model.characters[index], intent.active_skill_id)[2].applications)
    for actor in model.characters:
        applications.extend(s.application for s in actor.statuses if s.application)
        applications.extend(q.application for q in actor.queued_effects)
    sensitive = any(
        any(e.category == EffectCategory.DICE_MODIFIER for e in application.effects)
        or _uses_die_values(application.condition)
        or (application.delivery.status is not None and _uses_die_values(application.delivery.status.active_condition))
        or (application.delivery.trigger is not None and _uses_die_values(application.delivery.trigger.condition))
        for application in applications)
    if sensitive:
        return tuple(((a,b), 1/36) for a in range(1,7) for b in range(1,7))
    return (((6,1), 15/36), ((3,3), 6/36), ((1,6), 15/36))


def _effect_value(effect, actor, registry, *, to_self=True):
    """Small generic leaf estimate, NOT a second combat resolver.

    Actual damage, dice, restrictions and conditions inside the horizon always
    use the real resolver. Hints only value residual effects beyond the horizon.
    """
    p = effect.parameters
    category = effect.category
    value = 0.0
    resource_weight = {"hp": 1.0, "stamina": .22, "break_gauge": -.35}
    if category == EffectCategory.RESOURCE_CHANGE:
        if effect.operation.value == "add":
            value = p["value"] * resource_weight[p["resource"]]
    elif category == EffectCategory.RESULT_MODIFIER:
        sign = -1 if p["polarity"] in {"damage", "decrease"} else 1
        if effect.operation.value == "add":
            value = sign * p["value"] * resource_weight[p["resource"]] * .5
        elif effect.operation.value == "multiply":
            value = sign * 14 * (p["value"]-1) * resource_weight[p["resource"]]
    elif category == EffectCategory.DICE_MODIFIER:
        value = 2*(p["value"]-1) if effect.operation.value == "set_minimum" else -2*(6-p["value"])
    elif category == EffectCategory.ACTION_CONTROL:
        value = -3.0
    elif category == EffectCategory.SKILL_CONTROL:
        if effect.operation == SkillControlOperation.SEAL:
            value = -4.0
        elif effect.operation == SkillControlOperation.COST_DISCOUNT:
            eligible = [s for s in actor.skill_loadout if p["eligible_tag"] in registry[s.skill_id].tags
                        and actor.skill_cooldowns[s.skill_id] <= 1
                        and actor.skill_uses_remaining[s.skill_id] != 0]
            value = .22 * p["value"] if eligible else 0.0
    return value if to_self else -value


def _standing_value(actor, registry):
    if actor.is_ko:
        return 0.0
    wake_hp = math.floor(actor.max_hp * .5)
    hp = wake_hp if actor.is_down else actor.hp
    # No spurious 0-HP penalty while waiting to wake with guaranteed 50% HP.
    life = hp + max(0, actor.max_down_count - 1 - actor.down_count) * wake_hp
    value = life + .22*actor.stamina - .35*actor.break_gauge*(actor.break_gauge/actor.max_break_gauge)
    if actor.is_groggy:
        value -= 24
    if actor.is_down:
        value -= 4 * actor.skipped_turns_remaining
    for skill in actor.skill_loadout:
        uses = actor.skill_uses_remaining[skill.skill_id]
        if uses is not None:
            value += 2 * min(uses, 3) / (1 + actor.skill_cooldowns[skill.skill_id]/4)
    residual = 0.0
    for status in actor.statuses:
        if status.application is None:
            continue
        spec = status.application.delivery.status
        residual += sum(_effect_value(effect, actor, registry, to_self=spec.effect_target != Target.OPPONENT)
                        for effect in status.application.effects) * min(status.remaining_turns, 2)
    for queued in actor.queued_effects:
        residual += .5 * sum(_effect_value(effect, actor, registry, to_self=queued.application.target != Target.OPPONENT)
                             for effect in queued.application.effects)
    return value + max(-16, min(16, residual))


def evaluate(model, index):
    actor, other = model.characters[index], model.characters[1-index]
    if actor.is_ko and other.is_ko:
        return 0.0
    if actor.is_ko:
        return -1000.0
    if other.is_ko:
        return 1000.0
    return _standing_value(actor, model.skill_registry) - _standing_value(other, model.skill_registry)


@dataclass(frozen=True)
class CandidateScore:
    intent: TurnIntent
    score: float
    plan: tuple[TurnIntent, ...]
    first_turn_ko_risk: float | None = None


@dataclass(frozen=True)
class Decision:
    intent: TurnIntent
    candidates: tuple[CandidateScore, ...]
    transitions: int
    depth_completed: int
    elapsed_ms: float
    judgment: float
    random_choice: bool
    scenarios: int
    beam: int
    audit_completed: bool

    def summary(self):
        def label(intent):
            return {"action": intent.base_action.value, "skill": intent.active_skill_id}
        return {"selected": label(self.intent), "judgment": self.judgment,
                "random_choice": self.random_choice, "depth": self.depth_completed,
                "transitions": self.transitions, "elapsed_ms": round(self.elapsed_ms, 2),
                "scenarios": self.scenarios, "beam": self.beam, "audit_completed": self.audit_completed,
                "candidates": [{**label(c.intent), "score": round(c.score, 3),
                                "plan": [label(i) for i in c.plan], "ko_risk": c.first_turn_ko_risk}
                               for c in self.candidates[:5]]}


@dataclass
class _Node:
    states: tuple[ForwardModel, ...]
    plan: tuple[TurnIntent, ...]
    score: float


class PlanRequest:
    def __init__(self, root, index, seed, judgment=1.0, config=DEFAULT_CONFIG):
        if not math.isfinite(judgment) or not 0 <= judgment <= 1:
            raise ValueError("judgment must be between 0 and 1")
        if any(len(actor.skill_loadout) > 5 for actor in root.characters):
            raise ValueError("NG+ supports at most five skills per actor")
        self.root, self.index, self.seed = root, index, seed
        self.judgment, self.config = judgment, config

    def decide(self, cancel: Event | None = None):
        return _Search(self, cancel).run()


def create_request(engine, actor_index=1, *, turn_started=False, judgment=None, config=DEFAULT_CONFIG):
    if actor_index not in (0, 1):
        raise ValueError("invalid NG+ actor index")
    model = public_model(engine, turn_started=turn_started)
    # Only a separate deterministic policy seed; never getstate() on combat RNG.
    seed = engine.seed ^ 0x4E47504C5553 ^ ((model.match_turn+1)*0x9E3779B1) ^ actor_index
    return PlanRequest(model, actor_index, seed,
                       engine.ng_judgment if judgment is None else judgment, config)


class _Search:
    def __init__(self, request, cancel):
        self.root, self.index = request.root, request.index
        self.config, self.judgment, self.cancel = request.config, request.judgment, cancel
        self.transitions = 0
        self.rng = random.Random(request.seed)
        self.tape = [[(self.rng.random(), self.rng.randint(1,6), self.rng.randint(1,6))
                      for _ in range(self.config.scenarios)] for _ in range(self.config.depth)]

    def check(self):
        if self.cancel is not None and self.cancel.is_set():
            raise SearchCancelled()
        if self.transitions >= self.config.max_transitions:
            raise _BudgetReached()

    def step(self, source, own, other, dice):
        self.check()
        self.transitions += 1
        if source.outcome:
            return source
        model = source.fork()
        legal = legal_intents(source, self.index)
        if own not in legal:
            # A future plan can fail (resource/condition/CC); do not discard that
            # scenario or silently substitute another active skill.
            own = next((i for i in legal if i.base_action == own.base_action and i.active_skill_id is None), legal[0])
        model.forced_intents = (own, other) if self.index == 0 else (other, own)
        model.rng = _Dice(dice)
        model.play_turn()
        return model

    def extend(self, node, intent, depth):
        states = []
        for j, source in enumerate(node.states):
            sample, die0, die1 = self.tape[depth][j]
            other = _pick(opponent_distribution(source, 1-self.index), sample)
            states.append(self.step(source, intent, other, (die0, die1)))
        score = sum(evaluate(s, self.index) for s in states)/len(states)
        return _Node(tuple(states), (*node.plan, intent), score)

    def candidates(self, node):
        # Union of legally reachable intents; same plan across all scenarios.
        return tuple(dict.fromkeys(i for s in node.states for i in legal_intents(s, self.index)))

    def retain(self, nodes):
        nodes.sort(key=lambda node: node.score, reverse=True)
        kept = nodes[:self.config.beam]
        prepared = next((node for node in nodes if any(
            "preparation" in status.tags for state in node.states
            for status in state.characters[self.index].statuses)), None)
        if prepared is not None and not any(node is prepared for node in kept):
            kept[-1] = prepared
        return kept

    def audit(self, candidate):
        expected, ko_risk = 0.0, 0.0
        for other, probability in opponent_distribution(self.root, 1-self.index):
            intents = (candidate, other) if self.index == 0 else (other, candidate)
            for dice, dice_probability in audit_dice(self.root, intents):
                model = self.step(self.root, candidate, other, dice)
                weight = probability*dice_probability
                expected += weight*evaluate(model, self.index)
                ko_risk += weight*model.characters[self.index].is_ko
        return expected, ko_risk

    def run(self):
        started = perf_counter()
        self.check()
        roots = legal_intents(self.root, self.index)
        if not can_choose(self.root, self.index):
            raise ValueError("NG+ actor cannot choose this exchange")
        if self.judgment == 0:
            return Decision(self.rng.choice(roots), (), 0, 0, (perf_counter()-started)*1000,
                            0, True, self.config.scenarios, self.config.beam, False)
        empty = _Node((self.root,)*self.config.scenarios, (), evaluate(self.root, self.index))
        # Complete each depth for *all* roots before accepting that depth. A hard
        # budget never compares one deeply searched root with an unfinished one.
        best = {intent: _Node((), (intent,), empty.score) for intent in roots}
        beams, first_scores, completed = {}, {}, 0
        try:
            first = {intent: self.extend(empty, intent, 0) for intent in roots}
            best = first.copy()
            first_scores = {intent: node.score for intent, node in first.items()}
            beams = {intent: [node] for intent, node in first.items()}
            completed = 1
            for depth in range(1, self.config.depth):
                next_beams, next_best = {}, {}
                for root_intent, previous in beams.items():
                    extensions = [self.extend(node, intent, depth)
                                  for node in previous for intent in self.candidates(node)]
                    next_best[root_intent] = max(extensions, key=lambda node: node.score)
                    next_beams[root_intent] = self.retain(extensions)
                beams, best = next_beams, next_best
                completed = depth+1
        except _BudgetReached:
            pass
        ranked = sorted(best.items(), key=lambda pair: pair[1].score, reverse=True)
        audited = []
        audit_completed = False
        if completed and self.config.audit:
            try:
                for intent, node in ranked[:self.config.audit]:
                    immediate, risk = self.audit(intent)
                    audited.append(CandidateScore(intent, node.score-first_scores[intent]+immediate, node.plan, risk))
                audit_completed = True
            except _BudgetReached:
                audited = []  # Do not compare partially audited scores.
        candidates = audited or [CandidateScore(intent, node.score, node.plan) for intent, node in ranked]
        candidates.sort(key=lambda item: item.score, reverse=True)
        irrational = self.rng.random() >= self.judgment
        if irrational:
            chosen = self.rng.choice(roots)
        else:
            # Exact-value ties do not justify spending a skill, e.g. a basic
            # groggy hit already guarantees the final KO.
            efficient = []
            for candidate in candidates:
                if candidate.intent.active_skill_id and any(
                    other.intent.active_skill_id is None and abs(other.score-candidate.score) < 1e-9
                    for other in candidates):
                    continue
                efficient.append(candidate)
            top = efficient[0].score
            weights = [(c.intent, math.exp(max(-700, (c.score-top)/2))) for c in efficient]
            total = sum(weight for _, weight in weights)
            chosen = _pick(tuple((intent, weight/total) for intent, weight in weights), self.rng.random())
        return Decision(chosen, tuple(candidates), self.transitions, completed,
                        (perf_counter()-started)*1000, self.judgment, irrational,
                        self.config.scenarios, self.config.beam, audit_completed)
