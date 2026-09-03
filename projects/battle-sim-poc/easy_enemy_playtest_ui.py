"""Playable easy-enemy testbed reusing the existing manual skill UI."""

import tkinter as tk
from tkinter import ttk

from battle_sim import ACTION_LABELS, Action
from easy_enemy_profiles import EASY_ENEMY_PROFILES
from easy_enemy_skills import POWER_STRIKE, RECOVERY_FORM, SAFE_FOOTWORK, load_easy_skill_registry
from easy_enemy_testbed import MAX_PLAYER_SKILLS, create_easy_testbed_engine
from skill_playtest_ui import SkillPlaytestApp
from skill_testbed import effective_stamina_cost


class EasyEnemyPlaytestApp(SkillPlaytestApp):
    TITLE = "쉬움 적 3종 · 스킬 플레이테스트"
    DESCRIPTION = "Player는 새 스킬 5종 중 최대 3개를 장착합니다. Enemy는 고정된 3개 스킬과 합의한 사용 규칙으로 싸웁니다."
    NPC_CHOICES = (
        ("쉬움 · 훈련생 — rookie_cycle", "rookie_cycle"),
        ("쉬움 · 초급 방패병 — rookie_guard", "rookie_guard"),
        ("쉬움 · 돌격병 — reckless_raider", "reckless_raider"),
    )
    DEFAULT_NPC_INDEX = 0
    DEFAULT_SKILLS = (POWER_STRIKE, RECOVERY_FORM, SAFE_FOOTWORK)
    MAX_SKILLS = MAX_PLAYER_SKILLS
    USE_TEST_STATUSES = False
    load_registry = staticmethod(load_easy_skill_registry)
    create_engine = staticmethod(create_easy_testbed_engine)

    def _build_ui(self):
        super()._build_ui()
        self.root.geometry("1280x940")
        self.root.minsize(1100, 860)
        self.seed_var.set("20260903")
        self.loadout_list.configure(height=5)
        self.skill_details.configure(height=4)
        self.enemy_panel.configure(text="Enemy · 스킬 3개")
        # This catalog has no status or queued effects; leave room for the turn log.
        for panel in (self.player_panel, self.enemy_panel):
            panel.statuses.grid_remove()
            panel.queued.grid_remove()
        self.runtime_tree.master.configure(text="양측 장착 스킬 상태")
        self.runtime_tree.configure(height=6)
        self.runtime_tree.column("#0", width=210)
        self.runtime_tree.column("cost", width=110)
        self.same_loadout_button = ttk.Button(
            self.setup_frame, text="적과 같은 장착으로 새 경기", command=self.start_equal_loadout_match,
        )
        self.same_loadout_button.grid(row=3, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(
            self.setup_frame, text="전 스킬: 1레벨 · STA 8 · 개별 쿨다운 없음 · 이번 턴에만 적용",
        ).grid(row=3, column=3, columnspan=5, sticky="w", pady=(8, 0))
        self.enemy_rule_label = ttk.Label(self.setup_frame, wraplength=1150)
        self.enemy_rule_label.grid(row=4, column=0, columnspan=8, sticky="w", pady=(6, 0))

    def _show_skill_details(self, index):
        definition = self.registry[self.skill_ids[index]]
        actions = ", ".join(ACTION_LABELS[Action(action)] for action in definition.level(1).requirements.allowed_actions)
        self._replace_text(
            self.skill_details,
            f"{definition.name} · 1레벨\n{definition.description}\n"
            f"{actions}에서 사용 · STA 8 · 효과가 없어도 사용 비용은 소비합니다.",
        )

    def start_equal_loadout_match(self):
        enemy = dict(self.NPC_CHOICES)[self.npc_var.get()]
        self.loadout_list.selection_clear(0, "end")
        for index, skill_id in enumerate(self.skill_ids):
            if skill_id in EASY_ENEMY_PROFILES[enemy].skill_ids:
                self.loadout_list.selection_set(index)
        self.start_match()

    def refresh(self):
        super().refresh()
        if self.engine is not None:
            enemy = self.engine.strategies[1]
            action_number = len(self.engine.action_history[1]) + 1
            self.enemy_rule_label.configure(
                text=f"현재 Enemy 규칙: {EASY_ENEMY_PROFILES[enemy].description} "
                f"다음 자기 행동 {action_number}회째. 사용 실패 시 이월 없음."
            )

    def _refresh_skill_runtime(self):
        for item in self.runtime_tree.get_children():
            self.runtime_tree.delete(item)
        if self.engine is None:
            return
        for index, actor in enumerate(self.engine.characters):
            for owned in actor.skill_loadout:
                self.runtime_tree.insert(
                    "", "end", text=f"{actor.name} · {self.registry[owned.skill_id].name}",
                    values=(
                        f"{effective_stamina_cost(self.engine, owned.skill_id, index):g}",
                        actor.skill_cooldowns[owned.skill_id], "무제한",
                    ),
                )


def main():
    root = tk.Tk()
    EasyEnemyPlaytestApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
