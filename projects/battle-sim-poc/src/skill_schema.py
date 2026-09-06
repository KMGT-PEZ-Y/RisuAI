"""Active-skill schema models and Phase A validation.

This module deliberately has no dependency on the battle engine.  It turns
JSON-compatible dictionaries into immutable runtime definitions and rejects
schema features that the first 1v1 Python POC does not support yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import re
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence


class Resource(str, Enum):
    HP = "hp"
    STAMINA = "stamina"
    BREAK_GAUGE = "break_gauge"


class Target(str, Enum):
    SELF = "self"
    OPPONENT = "opponent"
    BOTH = "both"


class EffectCategory(str, Enum):
    RESOURCE_CHANGE = "resource_change"
    RESULT_MODIFIER = "result_modifier"
    DICE_MODIFIER = "dice_modifier"
    ACTION_CONTROL = "action_control"
    STATUS_CONTROL = "status_control"
    SKILL_CONTROL = "skill_control"


class ResourceChangeOperation(str, Enum):
    ADD = "add"
    SET = "set"
    ADD_PERCENT_OF_MAX = "add_percent_of_max"
    SET_PERCENT_OF_MAX = "set_percent_of_max"


class ResultModifierOperation(str, Enum):
    ADD = "add"
    MULTIPLY = "multiply"
    MINIMUM = "minimum"
    MAXIMUM = "maximum"
    NULLIFY = "nullify"


class DiceModifierOperation(str, Enum):
    SET_MINIMUM = "set_minimum"
    SET_MAXIMUM = "set_maximum"


class ActionControlOperation(str, Enum):
    ALLOW_ONLY = "allow_only"
    FORBID = "forbid"
    FORCE = "force"


class StatusControlOperation(str, Enum):
    REMOVE = "remove"
    CHANGE_DURATION = "change_duration"


class SkillControlOperation(str, Enum):
    MODIFY_COST = "modify_cost"
    CHANGE_COOLDOWN = "change_cooldown"
    CHANGE_CHARGES = "change_charges"
    COST_DISCOUNT = "cost_discount"
    SEAL = "seal"


EffectOperation = (
    ResourceChangeOperation
    | ResultModifierOperation
    | DiceModifierOperation
    | ActionControlOperation
    | StatusControlOperation
    | SkillControlOperation
)


class DeliveryType(str, Enum):
    IMMEDIATE = "immediate"
    STATUS = "status"
    QUEUED = "queued"


class Timing(str, Enum):
    ON_SKILL_COMMIT = "on_skill_commit"
    BEFORE_ACTION_REVEAL = "before_action_reveal"
    BEFORE_ROLL = "before_roll"
    AFTER_RAW_ROLL = "after_raw_roll"
    BEFORE_DICE_COMPARE = "before_dice_compare"
    BEFORE_RESULT_APPLY = "before_result_apply"
    AFTER_RESULT_APPLY = "after_result_apply"
    ON_STATUS_APPLY = "on_status_apply"
    ON_ROUND_END = "on_round_end"
    ON_INTERVAL = "on_interval"


class CooldownStart(str, Enum):
    ON_SKILL_COMMIT = "on_skill_commit"
    AFTER_RESOLUTION = "after_resolution"


class CooldownDecrement(str, Enum):
    OWNER_TURN = "owner_turn"
    OWNER_ACTIONABLE_TURN = "owner_actionable_turn"
    ROUND_END = "round_end"


class DurationUnit(str, Enum):
    OWNER_TURN = "owner_turn"
    OWNER_ACTIONABLE_TURN = "owner_actionable_turn"
    EXCHANGE = "exchange"
    ROUND = "round"
    TRIGGER_COUNT = "trigger_count"


class DurationStart(str, Enum):
    IMMEDIATE = "immediate"
    NEXT_OWNER_TURN = "next_owner_turn"


class StackingMode(str, Enum):
    REFRESH = "refresh"
    REPLACE = "replace"


class StatusPolarity(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class QueuedConsume(str, Enum):
    ON_TRIGGER = "on_trigger"
    ON_SUCCESSFUL_APPLY = "on_successful_apply"
    NEVER = "never"


class ConditionKind(str, Enum):
    PREDICATE = "predicate"
    ALL = "all"
    ANY = "any"
    NOT = "not"


@dataclass(frozen=True)
class Condition:
    kind: ConditionKind
    predicate: str | None = None
    arguments: Mapping[str, Any] = MappingProxyType({})
    children: tuple["Condition", ...] = ()

    def argument(self, name: str, default: Any = None) -> Any:
        return self.arguments.get(name, default)


@dataclass(frozen=True)
class SkillCost:
    resource: Resource
    amount: float
    minimum_remaining: float = 0


@dataclass(frozen=True)
class CooldownRule:
    turns: int = 0
    starts: CooldownStart = CooldownStart.ON_SKILL_COMMIT
    decrements: CooldownDecrement = CooldownDecrement.OWNER_TURN


@dataclass(frozen=True)
class UsageLimit:
    per_match: int | None = None
    per_round: int | None = None


@dataclass(frozen=True)
class Requirements:
    allowed_actions: tuple[str, ...]
    condition: Condition | None = None


@dataclass(frozen=True)
class DurationSpec:
    value: int
    unit: DurationUnit
    starts: DurationStart | None = None


@dataclass(frozen=True)
class StackingSpec:
    mode: StackingMode
    max_stacks: int = 1


@dataclass(frozen=True)
class StatusSpec:
    status_id: str
    name: str
    duration: DurationSpec
    stacking: StackingSpec
    removable: bool
    polarity: StatusPolarity
    tags: tuple[str, ...] = ()
    group: str | None = None
    effect_target: Target = Target.SELF
    active_condition: Condition | None = None
    consume_on_trigger: bool = False
    interval_decay: bool = True
    active_timing: Timing | None = None


@dataclass(frozen=True)
class TriggerSpec:
    event: Timing
    condition: Condition | None = None


@dataclass(frozen=True)
class DeliverySpec:
    type: DeliveryType
    status: StatusSpec | None = None
    trigger: TriggerSpec | None = None
    expires: DurationSpec | None = None
    consumes: QueuedConsume | None = None


@dataclass(frozen=True)
class ContentEffect:
    category: EffectCategory
    operation: EffectOperation
    parameters: Mapping[str, Any]


@dataclass(frozen=True)
class SkillApplication:
    application_id: str
    delivery: DeliverySpec
    timing: Timing
    target: Target
    condition: Condition | None
    priority: int
    effects: tuple[ContentEffect, ...]


@dataclass(frozen=True)
class SkillLevel:
    level: int
    costs: tuple[SkillCost, ...]
    cooldown: CooldownRule
    usage_limit: UsageLimit
    requirements: Requirements
    applications: tuple[SkillApplication, ...]


@dataclass(frozen=True)
class TargetingSpec:
    type: Target
    selection_required: bool


@dataclass(frozen=True)
class SkillUI:
    icon: str | None = None
    short_description: str = ""
    show_exact_values: bool = True


@dataclass(frozen=True)
class SkillDefinition:
    schema_version: int
    skill_id: str
    name: str
    description: str
    tags: tuple[str, ...]
    max_level: int
    targeting: TargetingSpec
    levels: tuple[SkillLevel, ...]
    ui: SkillUI

    def level(self, value: int) -> SkillLevel:
        if value < 1 or value > self.max_level:
            raise KeyError(f"{self.skill_id}: level {value} does not exist")
        return self.levels[value - 1]


class SkillSchemaError(ValueError):
    """One or more path-aware schema validation failures."""

    def __init__(self, errors: Iterable[str]):
        self.errors = tuple(errors)
        super().__init__("\n".join(self.errors))


_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_ACTIONS = {"attack", "defend", "evade"}
_SUBJECTS = {"self", "opponent"}
_DICE_RESULTS = {"win", "draw", "lose"}
_COMPARISONS = {
    "equal",
    "not_equal",
    "less_than",
    "less_than_or_equal",
    "greater_than",
    "greater_than_or_equal",
}

_OPERATION_ENUMS: dict[EffectCategory, type[Enum]] = {
    EffectCategory.RESOURCE_CHANGE: ResourceChangeOperation,
    EffectCategory.RESULT_MODIFIER: ResultModifierOperation,
    EffectCategory.DICE_MODIFIER: DiceModifierOperation,
    EffectCategory.ACTION_CONTROL: ActionControlOperation,
    EffectCategory.STATUS_CONTROL: StatusControlOperation,
    EffectCategory.SKILL_CONTROL: SkillControlOperation,
}

_TIMING_ORDER = {timing: index for index, timing in enumerate((
    Timing.ON_SKILL_COMMIT,
    Timing.BEFORE_ACTION_REVEAL,
    Timing.BEFORE_ROLL,
    Timing.AFTER_RAW_ROLL,
    Timing.BEFORE_DICE_COMPARE,
    Timing.BEFORE_RESULT_APPLY,
    Timing.AFTER_RESULT_APPLY,
    Timing.ON_STATUS_APPLY,
    Timing.ON_ROUND_END,
    Timing.ON_INTERVAL,
))}

_PREDICATE_MIN_TIMING: dict[str, Timing] = {
    "action_in": Timing.ON_SKILL_COMMIT,
    "previous_action_is": Timing.ON_SKILL_COMMIT,
    "recent_action_count_at_least": Timing.ON_SKILL_COMMIT,
    "resource_at_least": Timing.ON_SKILL_COMMIT,
    "resource_at_most": Timing.ON_SKILL_COMMIT,
    "resource_ratio_at_least": Timing.ON_SKILL_COMMIT,
    "resource_ratio_at_most": Timing.ON_SKILL_COMMIT,
    "round_at_least": Timing.ON_SKILL_COMMIT,
    "round_at_most": Timing.ON_SKILL_COMMIT,
    "turn_in_round_is": Timing.ON_SKILL_COMMIT,
    "down_count_at_least": Timing.ON_SKILL_COMMIT,
    "is_groggy": Timing.ON_SKILL_COMMIT,
    "is_down": Timing.ON_SKILL_COMMIT,
    "is_ko": Timing.ON_SKILL_COMMIT,
    "status_present": Timing.ON_SKILL_COMMIT,
    "status_absent": Timing.ON_SKILL_COMMIT,
    "status_tag_present": Timing.ON_SKILL_COMMIT,
    "status_count_at_least": Timing.ON_SKILL_COMMIT,
    "skill_ready": Timing.ON_SKILL_COMMIT,
    "skill_uses_remaining_at_least": Timing.ON_SKILL_COMMIT,
    "raw_die_is": Timing.AFTER_RAW_ROLL,
    "final_die_at_least": Timing.BEFORE_DICE_COMPARE,
    "final_die_at_most": Timing.BEFORE_DICE_COMPARE,
    "dice_result_is": Timing.BEFORE_RESULT_APPLY,
    "result_entry_is": Timing.BEFORE_RESULT_APPLY,
    "result_delta_is": Timing.BEFORE_RESULT_APPLY,
}

_REQUIREMENT_PREDICATES = {
    name
    for name, timing in _PREDICATE_MIN_TIMING.items()
    if timing == Timing.ON_SKILL_COMMIT
}


def _frozen(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _frozen(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_frozen(item) for item in value)
    return value


class _Parser:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def error(self, path: str, message: str) -> None:
        self.errors.append(f"{path}: {message}")

    def mapping(self, value: Any, path: str) -> Mapping[str, Any]:
        if not isinstance(value, Mapping):
            self.error(path, "object required")
            return {}
        return value

    def sequence(self, value: Any, path: str) -> Sequence[Any]:
        if not isinstance(value, list):
            self.error(path, "array required")
            return []
        return value

    def string(self, value: Any, path: str, *, identifier: bool = False) -> str:
        if not isinstance(value, str) or not value:
            self.error(path, "non-empty string required")
            return ""
        if identifier and not _ID_PATTERN.fullmatch(value):
            self.error(path, "lowercase snake_case identifier required")
        return value

    def integer(self, value: Any, path: str, *, minimum: int = 0) -> int:
        if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
            self.error(path, f"integer >= {minimum} required")
            return minimum
        return value

    def number(self, value: Any, path: str, *, minimum: float | None = None) -> float:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            self.error(path, "number required")
            return 0
        if minimum is not None and value < minimum:
            self.error(path, f"number >= {minimum} required")
        return value

    def boolean(self, value: Any, path: str) -> bool:
        if not isinstance(value, bool):
            self.error(path, "boolean required")
            return False
        return value

    def enum(self, enum_type: type[Enum], value: Any, path: str) -> Any:
        try:
            return enum_type(value)
        except (TypeError, ValueError):
            allowed = ", ".join(repr(item.value) for item in enum_type)
            self.error(path, f"unsupported value {value!r}; expected one of {allowed}")
            return next(iter(enum_type))

    def condition(
        self,
        raw: Any,
        path: str,
        *,
        timing: Timing,
        requirement: bool = False,
    ) -> Condition | None:
        if raw is None:
            return None
        data = self.mapping(raw, path)
        group_keys = [key for key in ("all", "any", "not") if key in data]
        if group_keys:
            if len(group_keys) != 1 or "type" in data:
                self.error(path, "condition must contain exactly one of all, any, not, or type")
            key = group_keys[0]
            if key == "not":
                child = self.condition(
                    data[key], f"{path}.not", timing=timing, requirement=requirement
                )
                return Condition(
                    ConditionKind.NOT,
                    children=() if child is None else (child,),
                )
            items = self.sequence(data[key], f"{path}.{key}")
            if not items:
                self.error(f"{path}.{key}", "at least one condition required")
            children = tuple(
                child
                for index, item in enumerate(items)
                if (child := self.condition(
                    item,
                    f"{path}.{key}[{index}]",
                    timing=timing,
                    requirement=requirement,
                )) is not None
            )
            return Condition(ConditionKind(key), children=children)

        predicate = self.string(data.get("type"), f"{path}.type")
        if predicate not in _PREDICATE_MIN_TIMING:
            self.error(f"{path}.type", f"unsupported condition {predicate!r}")
        else:
            minimum_timing = _PREDICATE_MIN_TIMING[predicate]
            if requirement and predicate not in _REQUIREMENT_PREDICATES:
                self.error(path, f"{predicate} cannot be used in requirements")
            elif (
                requirement
                and predicate == "action_in"
                and data.get("subject") != "self"
            ):
                self.error(path, "requirements action_in supports subject 'self' only")
            elif _TIMING_ORDER[timing] < _TIMING_ORDER[minimum_timing]:
                self.error(
                    path,
                    f"{predicate} cannot be evaluated at timing {timing.value!r}; "
                    f"earliest timing is {minimum_timing.value!r}",
                )
        arguments = {key: value for key, value in data.items() if key != "type"}
        self.validate_predicate_arguments(predicate, arguments, path)
        return Condition(
            ConditionKind.PREDICATE,
            predicate=predicate,
            arguments=_frozen(arguments),
        )

    def validate_predicate_arguments(
        self, predicate: str, arguments: Mapping[str, Any], path: str
    ) -> None:
        subject_predicates = {
            "action_in", "previous_action_is", "recent_action_count_at_least",
            "resource_at_least", "resource_at_most", "resource_ratio_at_least",
            "resource_ratio_at_most", "down_count_at_least", "is_groggy",
            "is_down", "is_ko", "status_present", "status_absent",
            "status_count_at_least", "skill_ready",
            "skill_uses_remaining_at_least", "raw_die_is",
            "final_die_at_least", "final_die_at_most", "dice_result_is",
            "result_delta_is",
            "status_tag_present",
        }
        if predicate in subject_predicates and arguments.get("subject") not in _SUBJECTS:
            self.error(f"{path}.subject", "expected 'self' or 'opponent'")
        resource_predicates = {
            "resource_at_least", "resource_at_most", "resource_ratio_at_least",
            "resource_ratio_at_most", "result_delta_is",
        }
        if predicate in resource_predicates:
            self.enum(Resource, arguments.get("resource"), f"{path}.resource")
        value_number = {
            "resource_at_least", "resource_at_most", "resource_ratio_at_least",
            "resource_ratio_at_most", "round_at_least", "round_at_most",
            "turn_in_round_is", "down_count_at_least", "status_count_at_least",
            "skill_uses_remaining_at_least", "raw_die_is", "final_die_at_least",
            "final_die_at_most", "result_delta_is",
        }
        if predicate in value_number:
            self.number(arguments.get("value"), f"{path}.value")
        if predicate == "action_in":
            values = self.sequence(arguments.get("values"), f"{path}.values")
            if not values:
                self.error(f"{path}.values", "at least one action required")
            for index, action in enumerate(values):
                if action not in _ACTIONS:
                    self.error(f"{path}.values[{index}]", f"unknown action {action!r}")
        if predicate == "previous_action_is" and arguments.get("value") not in _ACTIONS:
            self.error(f"{path}.value", f"unknown action {arguments.get('value')!r}")
        if predicate == "recent_action_count_at_least":
            if arguments.get("action") not in _ACTIONS:
                self.error(f"{path}.action", f"unknown action {arguments.get('action')!r}")
            self.integer(arguments.get("window"), f"{path}.window", minimum=1)
            self.integer(arguments.get("value"), f"{path}.value", minimum=1)
        if predicate in {"is_groggy", "is_down", "is_ko"}:
            self.boolean(arguments.get("value"), f"{path}.value")
        if predicate in {"status_present", "status_absent"}:
            self.string(arguments.get("status_id"), f"{path}.status_id", identifier=True)
        if predicate == "status_tag_present":
            self.string(arguments.get("tag"), f"{path}.tag", identifier=True)
        if predicate in {"skill_ready", "skill_uses_remaining_at_least"}:
            self.string(arguments.get("skill_id"), f"{path}.skill_id", identifier=True)
        if predicate == "dice_result_is" and arguments.get("value") not in _DICE_RESULTS:
            self.error(f"{path}.value", "expected 'win', 'draw', or 'lose'")
        if predicate == "result_entry_is":
            self.string(arguments.get("value"), f"{path}.value")
        if predicate == "result_delta_is" and arguments.get("comparison") not in _COMPARISONS:
            self.error(f"{path}.comparison", "unsupported comparison")

    def delivery(self, raw: Any, path: str, timing: Timing = Timing.ON_SKILL_COMMIT) -> DeliverySpec:
        data = self.mapping(raw, path)
        delivery_type = self.enum(DeliveryType, data.get("type"), f"{path}.type")
        if delivery_type == DeliveryType.IMMEDIATE:
            return DeliverySpec(delivery_type)
        if delivery_type == DeliveryType.STATUS:
            status_data = self.mapping(data.get("status"), f"{path}.status")
            duration = self.duration(
                status_data.get("duration"), f"{path}.status.duration", starts_required=True
            )
            stacking_data = self.mapping(
                status_data.get("stacking"), f"{path}.status.stacking"
            )
            stacking = StackingSpec(
                self.enum(
                    StackingMode,
                    stacking_data.get("mode"),
                    f"{path}.status.stacking.mode",
                ),
                self.integer(
                    stacking_data.get("max_stacks", 1),
                    f"{path}.status.stacking.max_stacks",
                    minimum=1,
                ),
            )
            if stacking.max_stacks != 1:
                self.error(
                    f"{path}.status.stacking.max_stacks",
                    "first POC supports max_stacks=1 only",
                )
            status = StatusSpec(
                self.string(
                    status_data.get("id"), f"{path}.status.id", identifier=True
                ),
                self.string(status_data.get("name"), f"{path}.status.name"),
                duration,
                stacking,
                self.boolean(
                    status_data.get("removable"), f"{path}.status.removable"
                ),
                self.enum(
                    StatusPolarity,
                    status_data.get("polarity"),
                    f"{path}.status.polarity",
                ),
                tuple(self.string(tag, f"{path}.status.tags", identifier=True)
                      for tag in self.sequence(status_data.get("tags", []), f"{path}.status.tags")),
                (self.string(status_data["group"], f"{path}.status.group", identifier=True)
                 if status_data.get("group") is not None else None),
                self.enum(Target, status_data.get("effect_target", "self"), f"{path}.status.effect_target"),
                self.condition(status_data.get("active_condition"), f"{path}.status.active_condition",
                               timing=self.enum(Timing, status_data.get("active_timing", timing.value), f"{path}.status.active_timing")),
                self.boolean(status_data.get("consume_on_trigger", False), f"{path}.status.consume_on_trigger"),
                self.boolean(status_data.get("interval_decay", True), f"{path}.status.interval_decay"),
                self.enum(Timing, status_data.get("active_timing", timing.value), f"{path}.status.active_timing"),
            )
            return DeliverySpec(delivery_type, status=status)

        trigger_data = self.mapping(data.get("trigger"), f"{path}.trigger")
        event = self.enum(Timing, trigger_data.get("event"), f"{path}.trigger.event")
        trigger = TriggerSpec(
            event,
            self.condition(
                trigger_data.get("condition"),
                f"{path}.trigger.condition",
                timing=event,
            ),
        )
        expires = self.duration(data.get("expires"), f"{path}.expires")
        consumes = self.enum(
            QueuedConsume, data.get("consumes"), f"{path}.consumes"
        )
        return DeliverySpec(
            delivery_type, trigger=trigger, expires=expires, consumes=consumes
        )

    def duration(
        self, raw: Any, path: str, *, starts_required: bool = False
    ) -> DurationSpec:
        data = self.mapping(raw, path)
        starts_raw = data.get("starts")
        if starts_required and starts_raw is None:
            self.error(f"{path}.starts", "required for status duration")
        starts = (
            None
            if starts_raw is None
            else self.enum(DurationStart, starts_raw, f"{path}.starts")
        )
        return DurationSpec(
            self.integer(data.get("value"), f"{path}.value", minimum=1),
            self.enum(DurationUnit, data.get("unit"), f"{path}.unit"),
            starts,
        )

    def effect(self, raw: Any, path: str) -> ContentEffect:
        data = self.mapping(raw, path)
        category = self.enum(EffectCategory, data.get("category"), f"{path}.category")
        operation_type = _OPERATION_ENUMS[category]
        operation = self.enum(operation_type, data.get("operation"), f"{path}.operation")
        parameters = {
            key: value for key, value in data.items() if key not in {"category", "operation"}
        }
        self.validate_effect_parameters(category, operation.value, parameters, path)
        return ContentEffect(category, operation, _frozen(parameters))

    def validate_effect_parameters(
        self,
        category: EffectCategory,
        operation: str,
        parameters: Mapping[str, Any],
        path: str,
    ) -> None:
        if category == EffectCategory.RESOURCE_CHANGE:
            self.enum(Resource, parameters.get("resource"), f"{path}.resource")
            self.number(parameters.get("value"), f"{path}.value")
            self.boolean(parameters.get("requires_living", False), f"{path}.requires_living")
        elif category == EffectCategory.RESULT_MODIFIER:
            self.boolean(parameters.get("requires_base_change", False), f"{path}.requires_base_change")
            self.enum(Resource, parameters.get("resource"), f"{path}.resource")
            if parameters.get("direction") not in {"dealt", "received", "self", "opponent"}:
                self.error(f"{path}.direction", "unsupported result direction")
            if parameters.get("polarity") not in {
                "damage", "recovery", "increase", "decrease", "any"
            }:
                self.error(f"{path}.polarity", "unsupported result polarity")
            if operation != "nullify":
                self.number(parameters.get("value"), f"{path}.value")
        elif category == EffectCategory.DICE_MODIFIER:
            self.number(parameters.get("value"), f"{path}.value")
        elif category == EffectCategory.ACTION_CONTROL:
            if operation in {"allow_only", "forbid"}:
                actions = self.sequence(parameters.get("actions"), f"{path}.actions")
                if not actions:
                    self.error(f"{path}.actions", "at least one action required")
                if len(actions) != len(set(actions)):
                    self.error(f"{path}.actions", "duplicate actions are not allowed")
                for index, action in enumerate(actions):
                    if action not in _ACTIONS:
                        self.error(f"{path}.actions[{index}]", f"unknown action {action!r}")
                if operation == "forbid" and set(actions) == _ACTIONS:
                    self.error(f"{path}.actions", "forbid must leave at least one action")
            elif parameters.get("action") not in _ACTIONS:
                self.error(f"{path}.action", f"unknown action {parameters.get('action')!r}")
        elif category == EffectCategory.STATUS_CONTROL:
            selector = self.mapping(parameters.get("selector"), f"{path}.selector")
            if selector.get("type") not in {"status_id", "polarity", "tag"}:
                self.error(f"{path}.selector.type", "expected 'status_id', 'polarity' or 'tag'")
            elif selector.get("type") in {"status_id", "tag"}:
                self.string(
                    selector.get("value"),
                    f"{path}.selector.value",
                    identifier=True,
                )
            elif selector.get("value") not in {"positive", "negative", "neutral"}:
                self.error(
                    f"{path}.selector.value",
                    "expected 'positive', 'negative', or 'neutral'",
                )
            if selector.get("order", "oldest") not in {
                "oldest", "newest", "highest_priority"
            }:
                self.error(
                    f"{path}.selector.order",
                    "expected 'oldest', 'newest', or 'highest_priority'",
                )
            if operation == "remove":
                self.integer(parameters.get("count", 1), f"{path}.count", minimum=1)
            else:
                self.number(parameters.get("value"), f"{path}.value")
        elif category == EffectCategory.SKILL_CONTROL:
            if operation == "seal":
                return
            if operation == "cost_discount":
                self.integer(parameters.get("value"), f"{path}.value", minimum=1)
                self.integer(parameters.get("minimum_cost", 8), f"{path}.minimum_cost", minimum=0)
                self.integer(parameters.get("cooldown_reduction", 0), f"{path}.cooldown_reduction", minimum=0)
                self.string(parameters.get("eligible_tag"), f"{path}.eligible_tag", identifier=True)
                if parameters.get("extend_on_tag") is not None:
                    self.string(parameters["extend_on_tag"], f"{path}.extend_on_tag", identifier=True)
                return
            self.mapping(parameters.get("selector"), f"{path}.selector")
            self.number(parameters.get("value"), f"{path}.value")
            if operation == "modify_cost":
                self.enum(Resource, parameters.get("resource"), f"{path}.resource")

    def application(self, raw: Any, path: str) -> SkillApplication:
        data = self.mapping(raw, path)
        timing = self.enum(Timing, data.get("timing"), f"{path}.timing")
        effects_raw = self.sequence(data.get("effects"), f"{path}.effects")
        if not effects_raw:
            self.error(f"{path}.effects", "at least one effect required")
        return SkillApplication(
            self.string(data.get("id"), f"{path}.id", identifier=True),
            self.delivery(data.get("delivery"), f"{path}.delivery", timing),
            timing,
            self.enum(Target, data.get("target"), f"{path}.target"),
            self.condition(data.get("condition"), f"{path}.condition", timing=timing),
            self.integer(data.get("priority", 100), f"{path}.priority"),
            tuple(
                self.effect(effect, f"{path}.effects[{index}]")
                for index, effect in enumerate(effects_raw)
            ),
        )

    def requirements(self, raw: Any, path: str) -> Requirements:
        data = self.mapping(raw or {}, path)
        actions_raw = data.get("allowed_actions", ["attack", "defend", "evade"])
        actions = self.sequence(actions_raw, f"{path}.allowed_actions")
        if not actions:
            self.error(f"{path}.allowed_actions", "at least one action required")
        for index, action in enumerate(actions):
            if action not in _ACTIONS:
                self.error(f"{path}.allowed_actions[{index}]", f"unknown action {action!r}")
        return Requirements(
            tuple(action for action in actions if action in _ACTIONS),
            self.condition(
                data.get("condition"),
                f"{path}.condition",
                timing=Timing.ON_SKILL_COMMIT,
                requirement=True,
            ),
        )

    def level(self, raw: Any, path: str) -> SkillLevel:
        data = self.mapping(raw, path)
        costs_raw = self.sequence(data.get("costs", []), f"{path}.costs")
        costs: list[SkillCost] = []
        seen_resources: set[Resource] = set()
        for index, raw_cost in enumerate(costs_raw):
            cost_path = f"{path}.costs[{index}]"
            cost_data = self.mapping(raw_cost, cost_path)
            resource = self.enum(Resource, cost_data.get("resource"), f"{cost_path}.resource")
            if resource in seen_resources:
                self.error(cost_path, f"duplicate cost resource {resource.value!r}")
            seen_resources.add(resource)
            costs.append(SkillCost(
                resource,
                self.number(cost_data.get("amount"), f"{cost_path}.amount", minimum=0),
                self.number(
                    cost_data.get("minimum_remaining", 0),
                    f"{cost_path}.minimum_remaining",
                    minimum=0,
                ),
            ))
        cooldown_data = self.mapping(data.get("cooldown", {}), f"{path}.cooldown")
        cooldown = CooldownRule(
            self.integer(cooldown_data.get("turns", 0), f"{path}.cooldown.turns"),
            self.enum(
                CooldownStart,
                cooldown_data.get("starts", "on_skill_commit"),
                f"{path}.cooldown.starts",
            ),
            self.enum(
                CooldownDecrement,
                cooldown_data.get("decrements", "owner_turn"),
                f"{path}.cooldown.decrements",
            ),
        )
        limit_data = self.mapping(data.get("usage_limit", {}), f"{path}.usage_limit")
        per_match = limit_data.get("per_match")
        per_round = limit_data.get("per_round")
        if per_match is not None:
            per_match = self.integer(per_match, f"{path}.usage_limit.per_match", minimum=1)
        if per_round is not None:
            per_round = self.integer(per_round, f"{path}.usage_limit.per_round", minimum=1)
        if per_match is not None and per_round is not None and per_round > per_match:
            self.error(f"{path}.usage_limit.per_round", "cannot exceed per_match")
        applications_raw = self.sequence(data.get("applications"), f"{path}.applications")
        if not applications_raw:
            self.error(f"{path}.applications", "at least one application required")
        applications = tuple(
            self.application(item, f"{path}.applications[{index}]")
            for index, item in enumerate(applications_raw)
        )
        application_ids = [item.application_id for item in applications]
        if len(application_ids) != len(set(application_ids)):
            self.error(f"{path}.applications", "application ids must be unique per level")
        return SkillLevel(
            self.integer(data.get("level"), f"{path}.level", minimum=1),
            tuple(costs),
            cooldown,
            UsageLimit(per_match, per_round),
            self.requirements(data.get("requirements", {}), f"{path}.requirements"),
            applications,
        )

    def skill(self, raw: Any, path: str = "skill") -> SkillDefinition:
        data = self.mapping(raw, path)
        schema_version = self.integer(
            data.get("schema_version"), f"{path}.schema_version", minimum=1
        )
        if schema_version != 1:
            self.error(f"{path}.schema_version", "only schema version 1 is supported")
        max_level = self.integer(data.get("max_level"), f"{path}.max_level", minimum=1)
        targeting_data = self.mapping(data.get("targeting"), f"{path}.targeting")
        levels_raw = self.sequence(data.get("levels"), f"{path}.levels")
        levels = tuple(
            self.level(level, f"{path}.levels[{index}]")
            for index, level in enumerate(levels_raw)
        )
        actual_levels = [level.level for level in levels]
        expected_levels = list(range(1, max_level + 1))
        if actual_levels != expected_levels:
            self.error(
                f"{path}.levels",
                f"expected consecutive levels {expected_levels}, got {actual_levels}",
            )
        tags_raw = self.sequence(data.get("tags", []), f"{path}.tags")
        tags = tuple(
            self.string(tag, f"{path}.tags[{index}]", identifier=True)
            for index, tag in enumerate(tags_raw)
        )
        ui_data = self.mapping(data.get("ui", {}), f"{path}.ui")
        icon = ui_data.get("icon")
        if icon is not None and not isinstance(icon, str):
            self.error(f"{path}.ui.icon", "string or null required")
            icon = None
        return SkillDefinition(
            schema_version,
            self.string(data.get("id"), f"{path}.id", identifier=True),
            self.string(data.get("name"), f"{path}.name"),
            self.string(data.get("description"), f"{path}.description"),
            tags,
            max_level,
            TargetingSpec(
                self.enum(Target, targeting_data.get("type"), f"{path}.targeting.type"),
                self.boolean(
                    targeting_data.get("selection_required", False),
                    f"{path}.targeting.selection_required",
                ),
            ),
            levels,
            SkillUI(
                icon,
                self.string(
                    ui_data.get("short_description", ""),
                    f"{path}.ui.short_description",
                ) if "short_description" in ui_data else "",
                self.boolean(
                    ui_data.get("show_exact_values", True),
                    f"{path}.ui.show_exact_values",
                ),
            ),
        )


def parse_skill_definition(raw: Mapping[str, Any], path: str = "skill") -> SkillDefinition:
    """Validate and normalize one JSON-compatible skill dictionary."""
    parser = _Parser()
    skill = parser.skill(raw, path)
    if parser.errors:
        raise SkillSchemaError(parser.errors)
    return skill


def validate_skill_data(raw: Mapping[str, Any], path: str = "skill") -> tuple[str, ...]:
    """Return path-aware errors without raising."""
    try:
        parse_skill_definition(raw, path)
    except SkillSchemaError as exc:
        return exc.errors
    return ()


def load_skill_definitions(raw_skills: Sequence[Mapping[str, Any]]) -> Mapping[str, SkillDefinition]:
    """Validate a collection and return an immutable id-indexed registry."""
    registry: dict[str, SkillDefinition] = {}
    errors: list[str] = []
    for index, raw in enumerate(raw_skills):
        try:
            skill = parse_skill_definition(raw, f"skills[{index}]")
        except SkillSchemaError as exc:
            errors.extend(exc.errors)
            continue
        if skill.skill_id in registry:
            errors.append(f"skills[{index}].id: duplicate skill id {skill.skill_id!r}")
        else:
            registry[skill.skill_id] = skill
    if errors:
        raise SkillSchemaError(errors)
    return MappingProxyType(registry)


def load_skill_definitions_json(text: str) -> Mapping[str, SkillDefinition]:
    """Parse a JSON array and return an immutable validated registry."""
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SkillSchemaError((f"json: {exc.msg} at line {exc.lineno} column {exc.colno}",)) from exc
    if not isinstance(raw, list):
        raise SkillSchemaError(("json: top-level array of skills required",))
    return load_skill_definitions(raw)
