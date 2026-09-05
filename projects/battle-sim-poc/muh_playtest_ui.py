"""Freely equipped 30-skill testbed with asynchronous NG+ enemy decisions."""
from queue import Queue, Empty
from threading import Event, Thread
import tkinter as tk
from tkinter import messagebox, ttk

from battle_sim import ACTION_LABELS, Action, InvalidTurnIntent, TurnIntent
from muh_skills import load_muh_skill_registry
from muh_testbed import create_muh_testbed_engine
from skill_playtest_ui import NO_SKILL_LABEL, SkillPlaytestApp
from skill_testbed import effective_stamina_cost
from playtest_ui import NPC_OPTIONS
from ng_plus_ai import create_request, SearchCancelled


class MuhPlaytestApp(SkillPlaytestApp):
    TITLE = "NG+ AI · M/U/H 30종 자유 장착 테스트베드"
    DESCRIPTION = "양측 최대 5개 자유 장착 · 제어/결정기 각 1개 · NG+는 행동과 스킬을 함께 판단 · 강제 턴도 한 번씩 진행"
    NPC_CHOICES = (*NPC_OPTIONS, ("NG+ · 행동+스킬 통합 · 3턴 탐색", "ng_plus"))
    DEFAULT_NPC_INDEX = len(NPC_OPTIONS)
    DEFAULT_SKILLS = ("m01", "m02", "m05", "m06", "u03")
    MAX_SKILLS = 5
    USE_TEST_STATUSES = False
    load_registry = staticmethod(load_muh_skill_registry)

    def _build_ui(self):
        super()._build_ui()
        self.root.geometry("1280x1000")
        self.loadout_list.configure(height=5)
        self.skill_details.configure(height=4)
        self.seed_var.set("20260904")
        self.enemy_panel.configure(text="Enemy · 최대 5개 스킬")
        self.runtime_tree.master.configure(text="양측 스킬 상태")
        self.runtime_tree.configure(height=6)
        setup = self.setup_frame
        ttk.Label(setup, text="Enemy 장착 · Ctrl/Shift로 최대 5개").grid(row=3, column=0, columnspan=3, sticky="w")
        enemy_frame = ttk.Frame(setup)
        enemy_frame.grid(row=4, column=0, columnspan=3, sticky="nsew", padx=(0, 12))
        self.enemy_loadout = tk.Listbox(enemy_frame, selectmode="extended", exportselection=False, height=5)
        for code in self.skill_ids:
            self.enemy_loadout.insert("end", self.skill_label_by_id[code])
        self.enemy_loadout.pack(side="left", fill="both", expand=True)
        bar = ttk.Scrollbar(enemy_frame, command=self.enemy_loadout.yview)
        bar.pack(side="right", fill="y")
        self.enemy_loadout.configure(yscrollcommand=bar.set)
        self.enemy_loadout.bind("<<ListboxSelect>>", self._show_enemy_detail)
        for code in ("m01", "m02", "m07", "u03", "h08"):
            self.enemy_loadout.selection_set(self.skill_ids.index(code))
        settings = ttk.Frame(setup)
        settings.grid(row=4, column=3, columnspan=5, sticky="nw")
        ttk.Label(settings, text="Enemy 모드 (새 경기에서 적용)").grid(row=0, column=0, sticky="w")
        self.enemy_mode = tk.StringVar(value="NG+ 자동")
        self.enemy_mode_combo = ttk.Combobox(settings, textvariable=self.enemy_mode, state="readonly", width=16)
        self.enemy_mode_combo.grid(row=0, column=1, sticky="w")
        ttk.Label(settings, text="수동 행동 / 스킬").grid(row=1, column=0, sticky="w")
        self.enemy_action = tk.StringVar(value="공격")
        self.enemy_action_combo = ttk.Combobox(settings, textvariable=self.enemy_action, values=list(ACTION_LABELS.values()),
                     state="readonly", width=10)
        self.enemy_action_combo.grid(row=1, column=1, sticky="w")
        self.enemy_skill = tk.StringVar(value=NO_SKILL_LABEL)
        self.enemy_skill_combo = ttk.Combobox(settings, textvariable=self.enemy_skill, state="readonly", width=32)
        self.enemy_skill_combo.grid(row=2, column=0, columnspan=2, sticky="ew")
        self.enemy_valid_label = ttk.Label(settings, text="", wraplength=620)
        self.enemy_valid_label.grid(row=3, column=0, columnspan=3, sticky="w")
        self.judgment_var = tk.StringVar(value="1.00")
        ttk.Label(settings, text="판단 충실도 (새 경기 적용)").grid(row=4, column=0, sticky="w")
        self.judgment_input = ttk.Spinbox(settings, from_=0, to=1, increment=.05, width=8, textvariable=self.judgment_var)
        self.judgment_input.grid(row=4, column=1, sticky="w")
        ttk.Label(settings, text="1: 평가 우선 / 0: 합법 후보 중 무작위").grid(row=5, column=0, columnspan=3, sticky="w")
        self.ng_decision_label = ttk.Label(setup, text="NG+ 판단 결과는 턴 실행 후 표시됩니다.", wraplength=1150)
        self.ng_decision_label.grid(row=5, column=0, columnspan=8, sticky="w", pady=(6,0))
        self.ng_log = self._make_log_tab(self.log_notebook, "NG+ 판단")
        self._pending_ng = None
        self.npc_var.trace_add("write", lambda *_: self._sync_enemy_controls())
        self._sync_enemy_controls()
        self.root.bind("<Destroy>", self._on_destroy, add="+")
        self.enemy_action.trace_add("write", lambda *_: self.refresh_validation())
        self.enemy_skill.trace_add("write", lambda *_: self.refresh_validation())

    def _show_enemy_detail(self, _event=None):
        indexes = self.enemy_loadout.curselection()
        if indexes:
            self._show_skill_details(indexes[-1])

    def create_engine(self, seed, **kwargs):
        engine = create_muh_testbed_engine(seed, **kwargs,
            enemy_skill_ids=[self.skill_ids[i] for i in self.enemy_loadout.curselection()],
            enemy_skill_policy="random" if self.enemy_mode.get() == "무작위 스킬" else "none",
            ng_judgment=float(self.judgment_var.get()) if kwargs["enemy_strategy"] == "ng_plus" else 1.0)
        engine.manual_enemy = self.enemy_mode.get() == "수동 입력"
        return engine

    def start_match(self):
        self._cancel_ng()
        previous = self.engine
        super().start_match()
        if self.engine is not None and self.engine is not previous:
            values = [self.skill_label_by_id[s.skill_id] for s in self.engine.enemy.skill_loadout]
            self.enemy_skill_combo.configure(values=[NO_SKILL_LABEL, *values])
            self.enemy_skill.set(NO_SKILL_LABEL)
            self._clear_log(self.ng_log)
            self.ng_decision_label.configure(text="새 경기 · Enemy 장착과 판단 충실도가 적용되었습니다.")
        self.refresh_validation()

    def _sync_enemy_controls(self):
        ng = dict(self.NPC_CHOICES).get(self.npc_var.get()) == "ng_plus"
        self.enemy_mode_combo.configure(values=("NG+ 자동",) if ng else ("수동 입력", "무작위 스킬", "무스킬"))
        if ng:
            self.enemy_mode.set("NG+ 자동")
        elif self.enemy_mode.get() == "NG+ 자동":
            self.enemy_mode.set("무작위 스킬")
        self.enemy_action_combo.configure(state="disabled" if ng else "readonly")
        self.enemy_skill_combo.configure(state="disabled" if ng else "readonly")
        self.judgment_input.configure(state="normal" if ng else "disabled")

    def _cancel_ng(self):
        pending = getattr(self, "_pending_ng", None)
        if pending is not None:
            pending[0].set()
        self._pending_ng = None

    def _on_destroy(self, event):
        if event.widget is self.root:
            self._cancel_ng()

    def _enemy_intent(self):
        code = self.skill_id_by_label.get(self.enemy_skill.get())
        action = next(a for a, label in ACTION_LABELS.items() if label == self.enemy_action.get())
        return TurnIntent("enemy", action, code)

    def refresh_validation(self, _event=None):
        super().refresh_validation(_event)
        if self.engine is None or not hasattr(self, "enemy_valid_label"):
            return
        b = self.engine
        if b.outcome:
            return
        if not b.player_can_choose:
            self.execute_button.configure(state="normal", text="강제 턴 진행")
        else:
            self.execute_button.configure(text="턴 실행")
        if b.manual_enemy and b.enemy_can_choose:
            result = b.validate_intent(self._enemy_intent())
            text = "Enemy 입력 사용 가능" if result.valid else " / ".join(self._validation_issue_text(issue) for issue in result.issues)
            self.enemy_valid_label.configure(text=text)
            if not result.valid:
                self.execute_button.configure(state="disabled")
        else:
            self.enemy_valid_label.configure(text="Enemy 자동/행동 불가 · 수동 입력은 적용하지 않습니다.")
        if getattr(self, "_pending_ng", None) is not None:
            self.execute_button.configure(state="disabled")
            self.enemy_valid_label.configure(text="NG+ 판단 중… 새 경기로 취소할 수 있습니다.")

    def execute_turn(self):
        if self.engine is None or self._pending_ng is not None or self.engine.outcome:
            return
        if self.engine.strategies[1] == "ng_plus" and self.engine.enemy_can_choose:
            player = self._current_intent() if self.engine.player_can_choose else None
            if player is not None:
                validation = self.engine.validate_intent(player)
                if not validation.valid:
                    self.refresh_validation()
                    return
            request = create_request(self.engine)
            cancel, results = Event(), Queue()
            pending = (cancel, results, self.engine, self.engine.match_turn, player)
            self._pending_ng = pending
            self.refresh_validation()
            def work():
                try:
                    results.put(request.decide(cancel))
                except Exception as error:
                    results.put(error)
            Thread(target=work, daemon=True, name="battle-ng-plus").start()
            self.root.after(20, lambda: self._poll_ng(pending))
            return
        try:
            self.engine.submit_test_turn(
                self._current_intent() if self.engine.player_can_choose else None,
                self._enemy_intent() if self.engine.manual_enemy else None)
        except (InvalidTurnIntent, ValueError, RuntimeError) as error:
            messagebox.showerror("턴 입력 오류", str(error))
            return
        self._render_new_trace()
        self.refresh()

    def _poll_ng(self, pending):
        if self._pending_ng is not pending:
            return
        cancel, results, engine, match_turn, player = pending
        try:
            decision = results.get_nowait()
        except Empty:
            self.root.after(20, lambda: self._poll_ng(pending))
            return
        self._pending_ng = None
        if self.engine is not engine or engine.match_turn != match_turn or cancel.is_set():
            self.refresh_validation()
            return
        if isinstance(decision, Exception):
            if not isinstance(decision, SearchCancelled):
                messagebox.showerror("NG+ 판단 오류", str(decision))
            self.refresh_validation()
            return
        try:
            engine.record_ng_decision(1, decision)
            engine.submit_test_turn(player, decision.intent)
        except (InvalidTurnIntent, ValueError, RuntimeError) as error:
            messagebox.showerror("턴 입력 오류", str(error))
            self.refresh_validation()
            return
        self._render_ng_decision(decision)
        self._render_new_trace()
        self.refresh()

    def _render_ng_decision(self, decision):
        def label(intent):
            skill = self.registry[intent.active_skill_id].name if intent.active_skill_id else "스킬 없음"
            return f"{ACTION_LABELS[intent.base_action]} + {skill}"
        text = (f"NG+ 선택: {label(decision.intent)} · {'무작위 선택' if decision.random_choice else '평가 우선'} · "
                f"{decision.elapsed_ms:.0f}ms · 가상 턴 {decision.transitions:,}회 · 깊이 {decision.depth_completed}")
        self.ng_decision_label.configure(text=text)
        self._append_log(self.ng_log, text + "\n평가 점수는 승률이 아닙니다. 아래 계획은 다음 턴에 다시 계산합니다.")
        for candidate in decision.candidates:
            risk = "" if candidate.first_turn_ko_risk is None else f" / 즉시 KO 위험 {candidate.first_turn_ko_risk:.1%}"
            self._append_log(self.ng_log, f"{candidate.score:+.2f}{risk} · " + " → ".join(label(i) for i in candidate.plan))

    def _refresh_skill_runtime(self):
        for item in self.runtime_tree.get_children():
            self.runtime_tree.delete(item)
        if self.engine is None:
            return
        for index, actor in enumerate(self.engine.characters):
            for owned in actor.skill_loadout:
                self.runtime_tree.insert("", "end", text=f"{'P' if index == 0 else 'E'} · {self.registry[owned.skill_id].name}",
                    values=(f"{effective_stamina_cost(self.engine, owned.skill_id, index):g}",
                            actor.skill_cooldowns[owned.skill_id], actor.skill_uses_remaining[owned.skill_id]))


def main():
    root = tk.Tk()
    MuhPlaytestApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
