"""Thirty level-one M/U/H skills. Content only; no enemy decision policy.

Identifiers are the proposal's m01..h10. Declarative status payloads implement
preparations, one-turn controls and discounts through the shared effect engine.
"""
from skill_schema import load_skill_definitions


def predicate(kind, subject="self", **args):
    return {"type": kind, "subject": subject, **args}


def all_of(*conditions):
    return {"all": list(conditions)}


def action(value, subject="self"):
    return predicate("action_in", subject, values=[value])


def resource(name, value, *, subject="self", minimum=False):
    return predicate("resource_at_least" if minimum else "resource_at_most",
                     subject, resource=name, value=value)


def present(name):
    return predicate("status_present", status_id=name)


def result_change(name, value, operation="add", *, received=False):
    return {"category": "result_modifier", "operation": operation,
            "resource": name, "direction": "received" if received else "dealt",
            "polarity": "increase" if name == "break_gauge" else "damage",
            "value": value, "requires_base_change": True}


def direct(name, value):
    return {"category": "resource_change", "operation": "add", "resource": name,
            "value": value, "requires_living": True}


def die(value, *, maximum=False):
    return {"category": "dice_modifier", "operation": "set_maximum" if maximum else "set_minimum", "value": value}


def remove(selector_type, value, order="oldest"):
    return {"category": "status_control", "operation": "remove", "count": 1,
            "selector": {"type": selector_type, "value": value, "order": order}}


def app(name, effects, *, target="self", timing="before_result_apply", condition=None, status=None):
    return {"id": name, "effects": effects, "target": target, "timing": timing,
            "condition": condition, "priority": 100,
            "delivery": {"type": "status", "status": status} if status else {"type": "immediate"}}


def status(name, label, *, tags=(), group=None, target="self", condition=None,
           timing="before_result_apply", consume=False, negative=False, removable=True):
    return {"id": name, "name": label, "duration": {"value": 1, "unit": "owner_turn", "starts": "next_owner_turn"},
            "stacking": {"mode": "replace", "max_stacks": 1},
            "polarity": "negative" if negative else "positive", "removable": removable,
            "tags": list(tags), "group": group, "effect_target": target,
            "active_condition": condition, "active_timing": timing,
            "consume_on_trigger": consume, "interval_decay": False}


def preparation(name, label, damage):
    return app(name, [result_change("hp", damage)], status=status(
        name, label, tags=("preparation",), group="damage_preparation", target="opponent",
        condition=action("attack"), consume=True))


def discount(name, label, amount, *, cooldown=0, extend=None):
    rule = {"category": "skill_control", "operation": "cost_discount", "value": amount,
            "eligible_tag": "attack_boost", "minimum_cost": 8, "cooldown_reduction": cooldown}
    if extend:
        rule["extend_on_tag"] = extend
    return app(name, [rule], timing="on_skill_commit", status=status(
        name, label, tags=("preparation",), group="cost_preparation", timing="on_skill_commit"))


HAS_PREPARATION = predicate("status_tag_present", "opponent", tag="preparation")
WIN = predicate("dice_result_is", value="win")


def skill(code, name, description, cost, cooldown, uses, actions, applications, *, condition=None, tags=()):
    return {"schema_version": 1, "id": code, "name": name, "description": description,
            "tags": ["muh", code[0], *tags], "max_level": 1,
            "targeting": {"type": "self", "selection_required": False},
            "levels": [{"level": 1, "costs": [{"resource": "stamina", "amount": cost}],
                        "cooldown": {"turns": cooldown, "starts": "on_skill_commit", "decrements": "owner_turn"},
                        "usage_limit": {"per_match": uses, "per_round": None},
                        "requirements": {"allowed_actions": actions, "condition": condition},
                        "applications": applications}],
            "ui": {"short_description": description, "show_exact_values": True}}


ATTACK = ["attack"]
DEFEND = ["defend"]
EVADE = ["evade"]
ANY = ["attack", "defend", "evade"]
BOOST = ("attack_boost",)

MUH_SKILLS = (
    skill("m01", "묵직한 한 방", "이번 공격의 기본 HP 피해가 있으면 피해 +6.", 12, 2, 5, ATTACK,
          [app("damage", [result_change("hp", 6)], target="opponent")], tags=BOOST),
    skill("m02", "단단한 가드", "이번 턴 받는 HP 피해 30% 감소.", 12, 3, 4, DEFEND,
          [app("guard", [result_change("hp", .7, "multiply", received=True)])]),
    skill("m03", "호흡 정리", "시작 HP 70 이하. 결과 후 HP 10 회복, BRK 8 감소. HP 0에서는 회복 불가.", 16, 4, 3, DEFEND,
          [app("recover", [direct("hp", 10), direct("break_gauge", -8)], timing="after_result_apply")], condition=resource("hp", 70)),
    skill("m04", "발판 잡기", "BRK 6 감소. 다음 턴 공격 강화 스킬 비용 10 감소(최소 8). 준비·회복·제어에는 할인 불가.", 6, 4, 3, EVADE,
          [app("balance", [direct("break_gauge", -6)], timing="on_skill_commit"), discount("m04_ready", "발판 잡기", 10)]),
    skill("m05", "힘 모으기", "다음 턴 공격 HP 피해 +8. 한 턴 후 만료되는 제거 가능한 준비.", 10, 4, 3, DEFEND,
          [preparation("m05_ready", "힘 모으기", 8)]),
    skill("m06", "연결 타격", "공격 HP 피해 +5. 힘 모으기가 있으면 +3 추가(준비의 +8 포함 총 +16).", 14, 3, 3, ATTACK,
          [app("damage", [result_change("hp", 5)], target="opponent"),
           app("combo", [result_change("hp", 3)], target="opponent", condition=present("m05_ready"))], tags=BOOST),
    skill("m07", "준비 끊기", "상대에게 준비가 있을 때 선택. 결과 후 가장 최근 준비 1개 제거.", 12, 4, 3, ATTACK,
          [app("disrupt", [remove("tag", "preparation", "newest")], target="opponent", timing="after_result_apply")], condition=HAS_PREPARATION),
    skill("m08", "중심 잡기", "이번 턴 자기 주사위 최소 3.", 10, 3, 4, ["defend", "evade"],
          [app("dice", [die(3)], timing="before_dice_compare")]),
    skill("m09", "발놀림 흐트리기", "이번 주사위 비교 승리 시 상대의 다음 턴 주사위 최대 4.", 14, 5, 3, ATTACK,
          [app("disrupt", [die(4, maximum=True)], target="opponent", condition=WIN,
               status=status("m09_shaken", "발놀림 흐트리기", negative=True, timing="before_dice_compare"))], tags=("control",)),
    skill("m10", "숨통 조이기", "시작 상대 BRK 50 이상. 이번 공격의 기본 BRK 증가가 있으면 +10.", 16, 4, 3, ATTACK,
          [app("break", [result_change("break_gauge", 10)], target="opponent")], condition=resource("break_gauge", 50, subject="opponent", minimum=True), tags=BOOST),
    skill("u01", "가드 압박", "상대가 이번 턴 방어하면 공격 HP 피해 +8, BRK 증가 +6. 기본 변화가 있어야 적용.", 18, 3, 4, ATTACK,
          [app("pressure", [result_change("hp", 8), result_change("break_gauge", 6)], target="opponent", condition=action("defend", "opponent"))], tags=BOOST),
    skill("u02", "받아치기", "받는 HP 피해 25% 감소. 상대 공격 + 자기 주사위 승리 시 결과 후 상대 HP 8 감소.", 18, 4, 3, DEFEND,
          [app("guard", [result_change("hp", .75, "multiply", received=True)]),
           app("counter", [direct("hp", -8)], target="opponent", timing="after_result_apply", condition=all_of(action("attack", "opponent"), WIN))]),
    skill("u03", "재정비", "시작 HP 50 이하. 결과 후 HP 14 회복, 가장 오래된 제거 가능 디버프 1개 정화.", 22, 5, 2, DEFEND,
          [app("recover", [direct("hp", 14), remove("polarity", "negative")], timing="after_result_apply")], condition=resource("hp", 50)),
    skill("u04", "속행 준비", "다음 턴 공격 강화 스킬 비용 8 감소(최소 8), 사용 CD 1 감소(최소 2). 결정기 CD는 감소 불가.", 8, 5, 3, EVADE,
          [discount("u04_ready", "속행 준비", 8, cooldown=1)]),
    skill("u05", "약점 포착", "다음 턴 공격 HP 피해 +10. 한 턴 후 만료되는 제거 가능한 준비.", 12, 4, 3, DEFEND,
          [preparation("u05_ready", "약점 포착", 10)]),
    skill("u06", "꿰뚫기", "공격 HP 피해 +7. 약점 포착 준비가 있으면 이번 주사위 최소 4(합계 피해 +17).", 20, 4, 3, ATTACK,
          [app("dice", [die(4)], timing="before_dice_compare", condition=present("u05_ready")),
           app("damage", [result_change("hp", 7)], target="opponent")], tags=BOOST),
    skill("u07", "흐름 절단", "상대에게 준비가 있을 때 선택. 결과 후 최신 준비 1개 제거, 상대 STA 6 감소.", 18, 5, 3, ATTACK,
          [app("disrupt", [remove("tag", "preparation", "newest"), direct("stamina", -6)], target="opponent", timing="after_result_apply")], condition=HAS_PREPARATION),
    skill("u08", "측면 몰기", "이번 주사위 비교 승리 시 상대는 다음 턴 회피 선택 불가.", 18, 5, 2, ATTACK,
          [app("restrict", [{"category": "action_control", "operation": "forbid", "actions": ["evade"]}], target="opponent", condition=WIN,
               status=status("u08_trapped", "측면 몰기", tags=("selection_control",), negative=True, timing="before_action_reveal"))], tags=("control",)),
    skill("u09", "침착한 판정", "이번 주사위 최소 4. 대신 이번 턴 자신이 주는 HP 피해 20% 감소.", 16, 4, 3, ANY,
          [app("dice", [die(4)], timing="before_dice_compare"), app("restraint", [result_change("hp", .8, "multiply")], target="opponent")]),
    skill("u10", "브레이크 러시", "시작 상대 BRK 65 이상·자기 BRK 50 이하. 공격 HP 피해 +10, BRK 증가 +12.", 26, 6, 2, ATTACK,
          [app("rush", [result_change("hp", 10), result_change("break_gauge", 12)], target="opponent")],
          condition=all_of(resource("break_gauge", 65, subject="opponent", minimum=True), resource("break_gauge", 50)), tags=BOOST),
    skill("h01", "분쇄 타격", "이번 공격 HP 피해 +12. 이번 턴 받는 HP 피해 20% 증가.", 22, 4, 3, ATTACK,
          [app("damage", [result_change("hp", 12)], target="opponent"), app("risk", [result_change("hp", 1.2, "multiply", received=True)])], tags=BOOST),
    skill("h02", "철벽 자세", "이번 턴 받는 HP 피해 50% 감소. 다음 턴 공격 선택 불가(정화 불가).", 24, 5, 2, DEFEND,
          [app("guard", [result_change("hp", .5, "multiply", received=True)]),
           app("recovery", [{"category": "action_control", "operation": "forbid", "actions": ["attack"]}],
               status=status("h02_recovery", "철벽 후딜", tags=("selection_control",), negative=True, removable=False, timing="before_action_reveal"))]),
    skill("h03", "마지막 호흡", "시작 HP 30 이하·다운 1회 이상. 결과 후 HP 22 회복, BRK 15 감소. HP 0에서는 회복 불가.", 28, 8, 1, DEFEND,
          [app("recover", [direct("hp", 22), direct("break_gauge", -15)], timing="after_result_apply")],
          condition=all_of(resource("hp", 30), predicate("down_count_at_least", value=1))),
    skill("h04", "결전 호흡", "다음 턴 공격 강화 스킬 비용 12 감소(최소 8). 전력 장전을 쓰면 할인만 한 턴 연장(1회).", 8, 7, 2, DEFEND,
          [discount("h04_ready", "결전 호흡", 12, extend="extends_discount")]),
    skill("h05", "전력 장전", "다음 턴 공격 HP 피해 +10. 이번 턴 받는 HP 피해 20% 증가.", 14, 6, 2, ["attack", "defend"],
          [preparation("h05_ready", "전력 장전", 10), app("risk", [result_change("hp", 1.2, "multiply", received=True)])], tags=("extends_discount",)),
    skill("h06", "결전의 일격", "전력 장전 보유·시작 자기 BRK 60 이하. 공격 HP 피해 +12, 주사위 최소 4. 다음 턴 스킬 사용 불가(정화 불가).", 30, 8, 2, ATTACK,
          [app("dice", [die(4)], timing="before_dice_compare"), app("damage", [result_change("hp", 12)], target="opponent"),
           app("recovery", [{"category": "skill_control", "operation": "seal"}],
               status=status("h06_recovery", "결전 후딜", negative=True, removable=False, timing="on_skill_commit"))],
          condition=all_of(present("h05_ready"), resource("break_gauge", 60)), tags=(*BOOST, "finisher")),
    skill("h07", "연결고리 파괴", "상대에게 준비가 있을 때 선택. 결과 후 최신 준비 1개 제거, 상대 STA 12 감소.", 26, 6, 2, ATTACK,
          [app("disrupt", [remove("tag", "preparation", "newest"), direct("stamina", -12)], target="opponent", timing="after_result_apply")], condition=HAS_PREPARATION),
    skill("h08", "도발 압박", "시작 자기 BRK 50 이하. 상대의 다음 턴 행동을 공격으로 강제.", 26, 7, 2, DEFEND,
          [app("taunt", [{"category": "action_control", "operation": "force", "action": "attack"}], target="opponent",
               status=status("h08_taunted", "도발 압박", tags=("selection_control",), negative=True, timing="before_action_reveal"))],
          condition=resource("break_gauge", 50), tags=("control", "forces_attack")),
    skill("h09", "승부수", "시작 HP 40 이하. 이번 주사위 6 고정. 다음 턴 받는 HP 피해 25% 증가(정화 불가).", 30, 8, 1, ATTACK,
          [app("dice", [die(6)], timing="before_dice_compare"),
           app("risk", [result_change("hp", 1.25, "multiply", received=True)],
               status=status("h09_exposed", "승부수 후딜", negative=True, removable=False))],
          condition=resource("hp", 40), tags=(*BOOST, "finisher", "fixed_six")),
    skill("h10", "한계 돌파", "시작 상대 HP 30 이하·BRK 70 이상·자기 STA 40 이상. 결과 후 상대 HP 12 감소, 살아 있으면 BRK 10 증가.", 34, 8, 1, ATTACK,
          [app("execute", [direct("hp", -12), direct("break_gauge", 10)], target="opponent", timing="after_result_apply")],
          condition=all_of(resource("hp", 30, subject="opponent"), resource("break_gauge", 70, subject="opponent", minimum=True), resource("stamina", 40, minimum=True)),
          tags=(*BOOST, "finisher")),
)


def load_muh_skill_registry():
    return load_skill_definitions(MUH_SKILLS)


def validate_loadout(ids, registry):
    """Apply proposal limits when a loadout contains M/U/H skills; legacy unaffected."""
    definitions = [registry[code] for code in ids if code in registry]
    if not any("muh" in item.tags for item in definitions):
        return
    if len(ids) > 5:
        raise ValueError("M/U/H 장착은 최대 5개입니다.")
    for tag, label in (("control", "제어"), ("finisher", "결정기")):
        if sum(tag in item.tags for item in definitions) > 1:
            raise ValueError(f"{label} 스킬은 세트당 최대 1개입니다.")
    tags = {tag for item in definitions for tag in item.tags}
    if {"forces_attack", "fixed_six"} <= tags:
        raise ValueError("도발 압박과 승부수는 함께 장착할 수 없습니다.")
