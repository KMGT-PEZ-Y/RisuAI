"""Content schedules count completed own actions, never rounds or successful casts."""

from dataclasses import dataclass
from types import MappingProxyType

from easy_enemy_skills import (
    CREATE_DISTANCE, POWER_STRIKE, RECOVERY_FORM, SAFE_FOOTWORK, TUCK_CHIN,
)


@dataclass(frozen=True)
class EasyEnemyProfile:
    skill_ids: tuple[str, ...]
    description: str
    # Fixed schedules: slot 1 is tuple index 0; None means a basic-action-only slot.
    schedule: tuple[str | None, ...] = ()
    # Action-matched schedules: every Nth own action, with no success-based reset.
    action_interval: int = 0
    action_skills: tuple[tuple[str, str], ...] = ()

    def planned_skill(self, action_number: int, action: str) -> str | None:
        if action_number < 1:
            raise ValueError("action_number must be at least 1")
        if self.schedule:
            return self.schedule[(action_number - 1) % len(self.schedule)]
        if action_number % self.action_interval == 0:
            return dict(self.action_skills).get(action)
        return None


EASY_ENEMY_PROFILES = MappingProxyType({
    "rookie_cycle": EasyEnemyProfile(
        (POWER_STRIKE, RECOVERY_FORM, SAFE_FOOTWORK),
        "공격→방어→회피 반복. 자기 행동 1·3·5번째에 힘주어 치기·안전한 발놀림·자세 정비, 6회 반복.",
        schedule=(POWER_STRIKE, None, SAFE_FOOTWORK, None, RECOVERY_FORM, None),
    ),
    "rookie_guard": EasyEnemyProfile(
        (RECOVERY_FORM, POWER_STRIKE, CREATE_DISTANCE),
        "방어 45%·공격 30%·회피 25%. 자기 행동 3·6·9…번째에 이미 선택한 행동에 맞는 스킬.",
        action_interval=3,
        action_skills=(("defend", RECOVERY_FORM), ("attack", POWER_STRIKE), ("evade", CREATE_DISTANCE)),
    ),
    "reckless_raider": EasyEnemyProfile(
        (POWER_STRIKE, TUCK_CHIN, RECOVERY_FORM),
        "공격→공격→방어, BRK 80 이상이면 방어. 자기 행동 2·4·6번째에 힘주어 치기·턱 당기기·자세 정비, 6회 반복.",
        schedule=(None, POWER_STRIKE, None, TUCK_CHIN, None, RECOVERY_FORM),
    ),
})
