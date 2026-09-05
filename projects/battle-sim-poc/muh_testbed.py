"""M/U/H testbed with independent loadouts and optional manual enemy input."""
from battle_sim import InvalidTurnIntent, ManualBattleEngine, OwnedSkill
from muh_skills import load_muh_skill_registry


class MuhTestbedEngine(ManualBattleEngine):
    enemy_override = None

    def _choose_intent(self, actor_index):
        if actor_index == 1 and self.enemy_override is not None:
            intent, self.enemy_override = self.enemy_override, None
            return intent
        return super()._choose_intent(actor_index)

    @property
    def enemy_can_choose(self):
        return (self.outcome is None and not self.enemy.is_down and not self.enemy.is_groggy
                and not self.enemy.is_ko and not self.player.is_down)

    def submit_test_turn(self, player_intent=None, enemy_intent=None):
        if self.outcome is not None:
            return
        if self.player_can_choose:
            if player_intent is None or player_intent.actor_id != "player":
                raise ValueError("Player 입력이 필요합니다.")
            result = self.validate_intent(player_intent)
            if not result.valid:
                raise InvalidTurnIntent(result)
        if enemy_intent is not None and self.enemy_can_choose:
            if enemy_intent.actor_id != "enemy":
                raise ValueError("Enemy 입력의 actor_id가 잘못되었습니다.")
            result = self.validate_intent(enemy_intent)
            if not result.valid:
                raise InvalidTurnIntent(result)
            self.enemy_override = enemy_intent
        try:
            if self.player_can_choose:
                self.submit_player_intent(player_intent)
            else:
                self.advance_forced_turn()
        finally:
            self.enemy_override = None


def create_muh_testbed_engine(seed, *, enemy_strategy="random", equipped_skill_ids=(),
                             enemy_skill_ids=(), enemy_skill_policy="none", add_test_statuses=False,
                             ng_judgment=1.0):
    return MuhTestbedEngine(seed, enemy_strategy=enemy_strategy,
                           skill_registry=load_muh_skill_registry(),
                           player_skills=[OwnedSkill(code, 1) for code in equipped_skill_ids],
                           enemy_skills=[OwnedSkill(code, 1) for code in enemy_skill_ids],
                           enemy_skill_policy=enemy_skill_policy, ng_judgment=ng_judgment)
