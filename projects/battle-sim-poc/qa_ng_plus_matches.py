"""Small deterministic stability/performance sample, not a difficulty benchmark."""
import json
import math
import random
from statistics import median

from muh_testbed import create_muh_testbed_engine
from ng_plus_ai import legal_intents, public_model


def main():
    decks = [
        ("m01", "m02", "m05", "m06", "u03"),
        ("h04", "h05", "h06", "m02", "u03"),
        ("m09", "u07", "u06", "m01", "u03"),
    ]
    rows, times, counts = [], [], []
    for offset, deck in enumerate(decks):
        seed = 20260904 + offset
        rng = random.Random(seed)
        battle = create_muh_testbed_engine(seed, enemy_strategy="ng_plus",
            equipped_skill_ids=deck, enemy_skill_ids=deck)
        used = set()
        while battle.outcome is None:
            intent = rng.choice(legal_intents(public_model(battle), 0)) if battle.player_can_choose else None
            before = battle.last_ng_decisions[1]
            battle.submit_test_turn(intent)
            decision = battle.last_ng_decisions[1]
            if decision is not None and decision is not before:
                times.append(decision.elapsed_ms)
                counts.append(decision.transitions)
                if decision.intent.active_skill_id:
                    used.add(decision.intent.active_skill_id)
        rows.append(dict(seed=seed, deck=deck, turns=battle.match_turn,
                         outcome=str(battle.outcome), enemy_skills_used=sorted(used)))
    ordered = sorted(times)
    print(json.dumps(dict(matches=rows, decisions=len(times), median_ms=round(median(times), 2),
        p95_ms=round(ordered[math.ceil(.95*len(ordered))-1], 2), max_ms=round(max(times), 2),
        max_transitions=max(counts)), indent=2))


if __name__ == "__main__":
    main()
