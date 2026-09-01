"""Tkinter UI for manually exercising Player-only Phase C active skills."""

from __future__ import annotations

import json
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from battle_sim import (
    ACTION_LABELS,
    DICE_RESULT_LABELS,
    GROGGY_TABLE,
    RESULT_CONCEPTS,
    RESULT_TABLE,
    Action,
    InvalidTurnIntent,
)
from playtest_ui import NPC_ID_BY_LABEL, NPC_OPTIONS, OUTCOME_LABELS, signed
from skill_testbed import (
    MAX_EQUIPPED_SKILLS,
    TEST_STATUS_NAMES,
    create_testbed_engine,
    effective_stamina_cost,
    load_test_skill_registry,
    make_player_intent,
)


NO_SKILL_LABEL = "스킬 사용 안 함"
CATEGORY_LABELS = {
    "resource_change": "자원 직접 변화",
    "result_modifier": "결과 변화량 수정",
    "dice_modifier": "주사위 범위 제한",
    "action_control": "행동 제어",
    "status_control": "상태 제어",
    "skill_control": "스킬 제어",
}
TIMING_LABELS = {
    "on_skill_commit": "스킬 확정",
    "before_action_reveal": "행동 공개 전",
    "before_roll": "굴림 전",
    "after_raw_roll": "원본 굴림 후",
    "before_dice_compare": "주사위 비교 전",
    "before_result_apply": "결과 적용 전",
    "after_result_apply": "결과 적용 후",
    "on_round_end": "라운드 종료",
    "on_interval": "인터벌",
}
REASON_LABELS = {
    "condition_not_met": "발동 조건 불충족",
    "polarity_not_matched": "변화 방향 불일치",
    "lower_priority_action_control": "더 높은 priority 제어가 이미 적용됨",
    "skill_not_owned": "대상 스킬을 장착하지 않음",
}
VALIDATION_LABELS = {
    "action_not_allowed": "선택한 행동과 함께 사용할 수 없습니다.",
    "requirements_not_met": "사용 조건을 만족하지 않습니다.",
    "insufficient_resource": "스태미너가 부족합니다.",
    "skill_on_cooldown": "쿨다운이 남아 있습니다.",
    "match_uses_exhausted": "경기당 사용 횟수를 모두 사용했습니다.",
    "round_uses_exhausted": "라운드당 사용 횟수를 모두 사용했습니다.",
    "actor_cannot_act": "현재 Player가 행동할 수 없습니다.",
}


class SkillCharacterPanel(ttk.LabelFrame):
    def __init__(self, parent: tk.Misc, title: str) -> None:
        super().__init__(parent, text=title, padding=10)
        self.columnconfigure(1, weight=1)
        self.value_labels: dict[str, ttk.Label] = {}
        self.bars: dict[str, ttk.Progressbar] = {}
        for row, (key, label) in enumerate((
            ("hp", "HP"),
            ("stamina", "STA"),
            ("break_gauge", "BRK"),
        )):
            ttk.Label(self, text=label, width=5).grid(row=row, column=0, sticky="w")
            bar = ttk.Progressbar(self, maximum=100, mode="determinate")
            bar.grid(row=row, column=1, sticky="ew", padx=5, pady=2)
            value = ttk.Label(self, text="0 / 100", width=11, anchor="e")
            value.grid(row=row, column=2, sticky="e")
            self.bars[key] = bar
            self.value_labels[key] = value
        self.combat_state = ttk.Label(self, text="상태: 정상")
        self.combat_state.grid(row=3, column=0, columnspan=3, sticky="w", pady=(6, 0))
        self.statuses = ttk.Label(self, text="효과: 없음", wraplength=430)
        self.statuses.grid(row=4, column=0, columnspan=3, sticky="w")

    def update_state(self, character) -> None:
        for key in ("hp", "stamina", "break_gauge"):
            current = getattr(character, key)
            maximum = getattr(character, f"max_{key}")
            self.bars[key].configure(maximum=maximum, value=current)
            self.value_labels[key].configure(text=f"{current} / {maximum}")
        if character.is_ko:
            state = "KO"
        elif character.is_down:
            state = f"다운 대기 {character.skipped_turns_remaining}턴"
        elif character.is_groggy:
            state = "완전 그로기"
        else:
            state = "정상"
        self.combat_state.configure(
            text=f"상태: {state} · 다운 {character.down_count}/{character.max_down_count}"
        )
        status_text = ", ".join(
            f"{TEST_STATUS_NAMES.get(status.name, status.name)} "
            f"({status.remaining_turns}턴)"
            for status in character.statuses
        ) or "없음"
        self.statuses.configure(text=f"효과: {status_text}")


class SkillPlaytestApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Battle Simulator POC · Phase C 스킬 테스트베드")
        self.root.geometry("1180x900")
        self.root.minsize(1000, 760)
        self.registry = load_test_skill_registry()
        self.skill_ids = tuple(self.registry)
        self.skill_label_by_id = {
            skill_id: f"{definition.name} [{skill_id}]"
            for skill_id, definition in self.registry.items()
        }
        self.skill_id_by_label = {
            label: skill_id for skill_id, label in self.skill_label_by_id.items()
        }
        self.engine = None
        self._result_table_window = None
        self.rendered_trace_count = 0
        self.result_announced = False

        self._configure_style()
        self._build_ui()
        self._select_default_loadout()
        self._show_skill_details(0)
        self.start_match()

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Malgun Gothic", 16, "bold"))
        style.configure("Turn.TLabel", font=("Malgun Gothic", 11, "bold"))
        style.configure("Valid.TLabel", foreground="#176c2f")
        style.configure("Invalid.TLabel", foreground="#a32626")

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(5, weight=1)

        ttk.Label(
            main,
            text="Phase C · Player 액티브 스킬 테스트베드",
            style="Title.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            main,
            text=(
                "Player만 액티브 스킬을 사용합니다. Enemy는 선택한 기존 행동 AI만 "
                "사용하며 스킬을 장착하지 않습니다."
            ),
        ).grid(row=1, column=0, sticky="w", pady=(2, 8))

        setup = ttk.LabelFrame(main, text="경기 설정과 스킬 장착", padding=10)
        setup.grid(row=2, column=0, sticky="ew")
        setup.columnconfigure(1, weight=1)
        setup.columnconfigure(5, weight=1)
        ttk.Label(setup, text="Enemy AI").grid(row=0, column=0, sticky="w")
        self.npc_var = tk.StringVar(value=NPC_OPTIONS[3][0])
        ttk.Combobox(
            setup,
            textvariable=self.npc_var,
            values=[label for label, _ in NPC_OPTIONS],
            state="readonly",
            width=44,
        ).grid(row=0, column=1, columnspan=2, sticky="ew", padx=(6, 12))
        ttk.Label(setup, text="시드").grid(row=0, column=3)
        self.seed_var = tk.StringVar(value="20260901")
        ttk.Entry(setup, textvariable=self.seed_var, width=13).grid(
            row=0, column=4, padx=(6, 12)
        )
        self.test_status_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            setup,
            text="상태 제어 시험용 초기 상태 추가",
            variable=self.test_status_var,
        ).grid(row=0, column=5, sticky="w")
        ttk.Button(setup, text="선택한 장착으로 새 경기", command=self.start_match).grid(
            row=0, column=6, padx=(10, 0)
        )
        ttk.Button(
            setup, text="기본 결과표 보기", command=self.show_result_table
        ).grid(row=0, column=7, padx=(10, 0))

        ttk.Label(
            setup,
            text=f"장착 스킬 · Ctrl/Shift로 최대 {MAX_EQUIPPED_SKILLS}개 선택",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(10, 3))
        ttk.Label(setup, text="선택 스킬 설명").grid(
            row=1, column=3, columnspan=4, sticky="w", pady=(10, 3)
        )
        self.loadout_list = tk.Listbox(
            setup,
            selectmode="extended",
            exportselection=False,
            height=7,
            font=("Malgun Gothic", 9),
        )
        for skill_id in self.skill_ids:
            self.loadout_list.insert("end", self.skill_label_by_id[skill_id])
        self.loadout_list.grid(
            row=2, column=0, columnspan=3, sticky="nsew", padx=(0, 12)
        )
        self.loadout_list.bind("<<ListboxSelect>>", self._on_loadout_selection)
        self.skill_details = tk.Text(
            setup,
            height=7,
            wrap="word",
            font=("Malgun Gothic", 9),
            state="disabled",
            relief="solid",
            borderwidth=1,
        )
        self.skill_details.grid(row=2, column=3, columnspan=4, sticky="nsew")

        states = ttk.Frame(main)
        states.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        states.columnconfigure(0, weight=1)
        states.columnconfigure(1, weight=1)
        self.player_panel = SkillCharacterPanel(states, "Player")
        self.player_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self.enemy_panel = SkillCharacterPanel(states, "Enemy · 무스킬")
        self.enemy_panel.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

        turn_box = ttk.LabelFrame(main, text="이번 턴 입력", padding=10)
        turn_box.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        turn_box.columnconfigure(4, weight=1)
        self.turn_label = ttk.Label(turn_box, text="", style="Turn.TLabel")
        self.turn_label.grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 6))
        self.action_var = tk.StringVar(value=Action.ATTACK.value)
        for column, action in enumerate(Action):
            ttk.Radiobutton(
                turn_box,
                text=ACTION_LABELS[action],
                value=action.value,
                variable=self.action_var,
                command=self.refresh_validation,
            ).grid(row=1, column=column, padx=(0, 8), sticky="w")
        ttk.Label(turn_box, text="액티브 스킬").grid(row=1, column=3, padx=(16, 5))
        self.active_skill_var = tk.StringVar(value=NO_SKILL_LABEL)
        self.active_skill_combo = ttk.Combobox(
            turn_box,
            textvariable=self.active_skill_var,
            values=[NO_SKILL_LABEL],
            state="readonly",
            width=37,
        )
        self.active_skill_combo.grid(row=1, column=4, sticky="ew")
        self.active_skill_combo.bind("<<ComboboxSelected>>", self.refresh_validation)
        self.execute_button = ttk.Button(
            turn_box, text="턴 실행", command=self.execute_turn
        )
        self.execute_button.grid(row=1, column=5, padx=(10, 0))
        self.validation_label = ttk.Label(turn_box, text="")
        self.validation_label.grid(
            row=2, column=0, columnspan=6, sticky="w", pady=(7, 0)
        )

        lower = ttk.Panedwindow(main, orient="horizontal")
        lower.grid(row=5, column=0, sticky="nsew", pady=(10, 0))
        runtime_box = ttk.LabelFrame(lower, text="Player 장착 스킬 상태", padding=6)
        self.runtime_tree = ttk.Treeview(
            runtime_box,
            columns=("cost", "cooldown", "uses"),
            show="tree headings",
            height=9,
        )
        self.runtime_tree.heading("#0", text="스킬")
        self.runtime_tree.heading("cost", text="현재 STA 비용")
        self.runtime_tree.heading("cooldown", text="쿨다운")
        self.runtime_tree.heading("uses", text="남은 횟수")
        self.runtime_tree.column("#0", width=155)
        self.runtime_tree.column("cost", width=90, anchor="center")
        self.runtime_tree.column("cooldown", width=70, anchor="center")
        self.runtime_tree.column("uses", width=70, anchor="center")
        self.runtime_tree.pack(fill="both", expand=True)
        lower.add(runtime_box, weight=0)

        notebook = ttk.Notebook(lower)
        self.battle_log = self._make_log_tab(notebook, "전투 로그")
        self.effect_log = self._make_log_tab(notebook, "Phase C 효과 검사")
        self.raw_log = self._make_log_tab(notebook, "Raw trace")
        lower.add(notebook, weight=1)

    @staticmethod
    def _make_log_tab(notebook: ttk.Notebook, title: str) -> ScrolledText:
        frame = ttk.Frame(notebook, padding=5)
        log = ScrolledText(
            frame,
            wrap="word",
            height=16,
            font=("Malgun Gothic", 9),
            state="disabled",
        )
        log.pack(fill="both", expand=True)
        notebook.add(frame, text=title)
        return log

    def _select_default_loadout(self) -> None:
        for index in range(min(MAX_EQUIPPED_SKILLS, len(self.skill_ids))):
            self.loadout_list.selection_set(index)

    def _on_loadout_selection(self, _event=None) -> None:
        selected = self.loadout_list.curselection()
        if selected:
            self._show_skill_details(selected[-1])

    def _show_skill_details(self, index: int) -> None:
        skill_id = self.skill_ids[index]
        definition = self.registry[skill_id]
        level = definition.level(1)
        actions = ", ".join(
            ACTION_LABELS[Action(value)] for value in level.requirements.allowed_actions
        )
        cost = next(
            (cost.amount for cost in level.costs if cost.resource.value == "stamina"), 0
        )
        categories = sorted({
            effect.category.value
            for application in level.applications
            for effect in application.effects
        })
        text = (
            f"{definition.name} [{skill_id}]\n"
            f"{definition.description}\n\n"
            f"카테고리: {', '.join(CATEGORY_LABELS.get(value, value) for value in categories)}\n"
            f"허용 행동: {actions} · STA {cost:g} · 쿨다운 {level.cooldown.turns}턴\n"
            f"대상: {definition.targeting.type.value}"
        )
        self._replace_text(self.skill_details, text)

    def _selected_loadout(self) -> tuple[str, ...]:
        return tuple(self.skill_ids[index] for index in self.loadout_list.curselection())

    @staticmethod
    def _format_delta(delta) -> str:
        parts = []
        for label, value in (
            ("HP", delta.hp),
            ("STA", delta.stamina),
            ("BRK", delta.break_gauge),
        ):
            if value:
                parts.append(f"{label} {signed(value)}")
        return ", ".join(parts) if parts else "변화 없음"

    def show_result_table(self) -> None:
        if getattr(self, "_result_table_window", None) is not None:
            self._result_table_window.deiconify()
            self._result_table_window.lift()
            return

        window = self._result_table_window = tk.Toplevel(self.root)
        window.title("기본 결과표 · 27 + 그로기 3")
        window.geometry("980x680")
        window.minsize(860, 420)

        ttk.Label(
            window,
            text="공격/방어/회피 조합의 기본 결과값 테이블",
            style="Title.TLabel",
        ).pack(anchor="w", padx=12, pady=(10, 4))
        ttk.Label(
            window,
            text=(
                "표기 기준은 Player입니다. 그로기 표는 행동 측(완전 그로기 대상)과 "
                "상대 측의 변화를 보여 줍니다."
            ),
        ).pack(anchor="w", padx=12, pady=(0, 8))

        frame = ttk.Frame(window, padding=(12, 0, 12, 12))
        frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(
            frame,
            columns=("dice", "player_delta", "enemy_delta", "concept"),
            show="tree headings",
        )
        tree.heading("#0", text="판정")
        tree.heading("dice", text="주사위")
        tree.heading("player_delta", text="Player 변화")
        tree.heading("enemy_delta", text="Enemy 변화")
        tree.heading("concept", text="개요")
        tree.column("#0", width=210, anchor="w")
        tree.column("dice", width=150, anchor="w")
        tree.column("player_delta", width=150, anchor="w")
        tree.column("enemy_delta", width=150, anchor="w")
        tree.column("concept", width=300, anchor="w")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        for (player_action, enemy_action, dice_result), entry in sorted(
            RESULT_TABLE.items(), key=lambda item: item[1].entry_id
        ):
            tree.insert(
                "",
                "end",
                text=(
                    f"{entry.entry_id} · "
                    f"{ACTION_LABELS[player_action]} vs {ACTION_LABELS[enemy_action]}"
                ),
                values=(
                    DICE_RESULT_LABELS[dice_result],
                    self._format_delta(entry.player),
                    self._format_delta(entry.enemy),
                    RESULT_CONCEPTS.get(entry.entry_id, ""),
                ),
            )
        for action, entry in GROGGY_TABLE.items():
            tree.insert(
                "",
                "end",
                text=f"{entry.entry_id} · 그로기 {ACTION_LABELS[action]}",
                values=(
                    "확정 판정",
                    self._format_delta(entry.player),
                    self._format_delta(entry.enemy),
                    RESULT_CONCEPTS.get(entry.entry_id, ""),
                ),
            )

        def _on_close() -> None:
            self._result_table_window = None
            window.destroy()

        window.protocol("WM_DELETE_WINDOW", _on_close)

    def start_match(self) -> None:
        try:
            seed = int(self.seed_var.get().strip())
        except ValueError:
            messagebox.showerror("잘못된 시드", "시드는 정수로 입력해주세요.")
            return
        loadout = self._selected_loadout()
        if len(loadout) > MAX_EQUIPPED_SKILLS:
            messagebox.showerror(
                "장착 제한",
                f"Player 스킬은 최대 {MAX_EQUIPPED_SKILLS}개까지 장착할 수 있습니다.",
            )
            return
        enemy_strategy = NPC_ID_BY_LABEL.get(self.npc_var.get())
        if enemy_strategy is None:
            messagebox.showerror("Enemy 선택 오류", "Enemy AI를 다시 선택해주세요.")
            return
        try:
            self.engine = create_testbed_engine(
                seed,
                enemy_strategy=enemy_strategy,
                equipped_skill_ids=loadout,
                add_test_statuses=self.test_status_var.get(),
            )
        except ValueError as error:
            messagebox.showerror("경기 설정 오류", str(error))
            return

        self.rendered_trace_count = 0
        self.result_announced = False
        self._clear_log(self.battle_log)
        self._clear_log(self.effect_log)
        self._clear_log(self.raw_log)
        skill_labels = [self.skill_label_by_id[skill_id] for skill_id in loadout]
        self.active_skill_combo.configure(values=[NO_SKILL_LABEL, *skill_labels])
        self.active_skill_var.set(NO_SKILL_LABEL)
        self._append_log(self.battle_log, f"새 경기 · 시드 {seed}")
        self._append_log(
            self.battle_log,
            f"Enemy: {self.npc_var.get()} · 스킬 없음",
        )
        self._append_log(
            self.battle_log,
            "Player 장착: " + (", ".join(skill_labels) if skill_labels else "없음"),
        )
        if self.test_status_var.get():
            self._append_log(
                self.battle_log,
                "상태 제어 시험용 초기 상태: 흔들림 4턴, 숨고르기 5턴",
            )
        self.refresh()

    def _selected_skill_id(self) -> str | None:
        label = self.active_skill_var.get()
        return None if label == NO_SKILL_LABEL else self.skill_id_by_label.get(label)

    def _current_intent(self):
        return make_player_intent(
            Action(self.action_var.get()),
            self._selected_skill_id(),
            self.registry,
        )

    def execute_turn(self) -> None:
        if self.engine is None or not self.engine.player_can_choose:
            return
        intent = self._current_intent()
        try:
            self.engine.submit_player_intent(intent)
            self.engine.advance_until_player_choice()
        except InvalidTurnIntent as error:
            messagebox.showerror(
                "스킬 입력 오류",
                "\n".join(self._validation_issue_text(issue) for issue in error.result.issues),
            )
            return
        except RuntimeError as error:
            messagebox.showerror("턴 처리 오류", str(error))
            return
        self._render_new_trace()
        self.refresh()

    def refresh(self) -> None:
        if self.engine is None:
            return
        self.player_panel.update_state(self.engine.player)
        self.enemy_panel.update_state(self.engine.enemy)
        self._refresh_skill_runtime()
        if self.engine.outcome:
            result = OUTCOME_LABELS.get(self.engine.outcome, self.engine.outcome)
            self.turn_label.configure(
                text=f"경기 종료 · {result} · 총 {self.engine.match_turn}턴"
            )
        else:
            self.turn_label.configure(
                text=(
                    f"라운드 {self.engine.round_number} · "
                    f"턴 {self.engine.turn_in_round + 1}/8 · "
                    f"전체 {self.engine.match_turn + 1}턴"
                )
            )
        self.refresh_validation()
        if self.engine.outcome and not self.result_announced:
            self.result_announced = True
            result = OUTCOME_LABELS.get(self.engine.outcome, self.engine.outcome)
            self._append_log(
                self.battle_log,
                f"\n=== 경기 종료: {result} · {self.engine.match_turn}턴 ===",
            )
            messagebox.showinfo("경기 종료", f"{result}\n총 {self.engine.match_turn}턴")

    def refresh_validation(self, _event=None) -> None:
        if self.engine is None:
            return
        if self.engine.outcome is not None:
            self.validation_label.configure(text="경기가 종료되었습니다.", style="Invalid.TLabel")
            self.execute_button.configure(state="disabled")
            return
        if not self.engine.player_can_choose:
            self.validation_label.configure(
                text="강제 진행 상태입니다.", style="Invalid.TLabel"
            )
            self.execute_button.configure(state="disabled")
            return
        validation = self.engine.validate_intent(self._current_intent())
        if validation.valid:
            skill_id = self._selected_skill_id()
            if skill_id is None:
                text = "사용 가능 · 선택 행동만 실행합니다."
            else:
                cost = effective_stamina_cost(self.engine, skill_id)
                target = self.registry[skill_id].targeting.type.value
                text = f"사용 가능 · 현재 STA 비용 {cost:g} · 자동 대상 {target}"
            self.validation_label.configure(text=text, style="Valid.TLabel")
            self.execute_button.configure(state="normal")
        else:
            text = " / ".join(
                self._validation_issue_text(issue) for issue in validation.issues
            )
            self.validation_label.configure(text=text, style="Invalid.TLabel")
            self.execute_button.configure(state="disabled")

    @staticmethod
    def _validation_issue_text(issue) -> str:
        return VALIDATION_LABELS.get(issue.code, issue.message)

    def _refresh_skill_runtime(self) -> None:
        for item in self.runtime_tree.get_children():
            self.runtime_tree.delete(item)
        if self.engine is None:
            return
        for owned in self.engine.player.skill_loadout:
            definition = self.registry[owned.skill_id]
            cooldown = self.engine.player.skill_cooldowns[owned.skill_id]
            remaining = self.engine.player.skill_uses_remaining[owned.skill_id]
            self.runtime_tree.insert(
                "",
                "end",
                text=definition.name,
                values=(
                    f"{effective_stamina_cost(self.engine, owned.skill_id):g}",
                    cooldown,
                    "무제한" if remaining is None else remaining,
                ),
            )

    def _render_new_trace(self) -> None:
        if self.engine is None:
            return
        for event in self.engine.trace[self.rendered_trace_count:]:
            self._append_log(
                self.raw_log,
                json.dumps(event, ensure_ascii=False, indent=2, default=str),
            )
            if event["event"] == "turn":
                self._render_turn_event(event)
            elif event["event"] == "interval":
                self._append_log(
                    self.battle_log,
                    f"  [인터벌] 라운드 {event['round']} 종료 · 기본 회복 적용",
                )
                self._render_effects(event.get("effects", ()), "인터벌")
        self.rendered_trace_count = len(self.engine.trace)

    def _render_turn_event(self, event: dict) -> None:
        resolution = event["resolution"]
        prefix = (
            f"R{event['round']} T{event['turn_in_round']} "
            f"(전체 {event['match_turn']})"
        )
        if resolution["kind"] == "normal":
            player_action = ACTION_LABELS[Action(resolution["player_action"])]
            enemy_action = ACTION_LABELS[Action(resolution["enemy_action"])]
            raw = f"{resolution['player_die']}:{resolution['enemy_die']}"
            final = (
                f"{resolution['player_final_die']}:"
                f"{resolution['enemy_final_die']}"
            )
            skill = resolution.get("player_skill") or "없음"
            line = (
                f"\n{prefix} · {player_action} vs {enemy_action} · "
                f"스킬 {skill} · 주사위 {raw}→{final} · "
                f"결과표 {resolution['entry_id']}"
            )
        elif resolution["kind"] == "groggy":
            action = ACTION_LABELS[Action(resolution["action"])]
            line = (
                f"\n{prefix} · {resolution['actor']}의 {action} · "
                f"스킬 {resolution.get('skill') or '없음'} · "
                f"결과표 {resolution['entry_id']}"
            )
        elif resolution["kind"] == "both_groggy_idle":
            line = f"\n{prefix} · 양측 완전 그로기, 행동 없이 경과"
        else:
            line = f"\n{prefix} · 다운 대기 및 기상 처리"
        self._append_log(self.battle_log, line)
        for index, label in enumerate(("Player", "Enemy")):
            before = event["before"][index]
            after = event["after"][index]
            changes = []
            for key, resource in (("hp", "HP"), ("stamina", "STA"), ("break_gauge", "BRK")):
                delta = after[key] - before[key]
                if delta:
                    changes.append(
                        f"{resource} {before[key]}→{after[key]}({signed(delta)})"
                    )
            self._append_log(
                self.battle_log,
                f"  {label}: " + (", ".join(changes) if changes else "자원 변화 없음"),
            )
        self._render_effects(resolution.get("effects", ()), prefix)

    def _render_effects(self, effects, context_label: str) -> None:
        if not effects:
            return
        self._append_log(self.effect_log, f"\n=== {context_label} ===")
        for effect in effects:
            timing = TIMING_LABELS.get(effect.get("timing"), effect.get("timing", "?"))
            applied = effect.get("applied", False)
            if "category" not in effect:
                result = REASON_LABELS.get(effect.get("reason"), effect.get("reason", "미적용"))
                self._append_log(
                    self.effect_log,
                    f"[{timing}] {effect.get('skill_id')} / {effect.get('application_id')} · {result}",
                )
                continue
            category = CATEGORY_LABELS.get(effect["category"], effect["category"])
            result = "적용" if applied else REASON_LABELS.get(
                effect.get("reason"), effect.get("reason", "미적용")
            )
            line = (
                f"[{timing}][P{effect.get('priority', '?')}] "
                f"{effect.get('skill_id')} · {category}/{effect.get('operation')} · "
                f"{effect.get('actor')}→{effect.get('target')} · {result}"
            )
            details = []
            for key, label in (
                ("before", "전"),
                ("after", "후"),
                ("raw_die", "원본"),
                ("final_die", "최종"),
                ("range", "범위"),
                ("selected", "범위 선택"),
            ):
                if key in effect:
                    details.append(f"{label}={effect[key]}")
            if details:
                line += " · " + ", ".join(details)
            self._append_log(self.effect_log, line)

    @staticmethod
    def _append_log(widget: ScrolledText, text: str) -> None:
        widget.configure(state="normal")
        widget.insert("end", text + "\n")
        widget.see("end")
        widget.configure(state="disabled")

    @staticmethod
    def _clear_log(widget: ScrolledText) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.configure(state="disabled")

    @staticmethod
    def _replace_text(widget: tk.Text, text: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")


def main() -> None:
    root = tk.Tk()
    SkillPlaytestApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

