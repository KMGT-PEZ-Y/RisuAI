"""Tkinter playtest UI for the Battle Simulator POC."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from battle_sim import ACTION_LABELS, Action, ManualBattleEngine


NPC_OPTIONS = (
    ("쉬움 · 훈련생 — 고정 순환", "rookie_cycle"),
    ("쉬움 · 초급 방패병 — 방어 혼합", "rookie_guard"),
    ("쉬움(재검증 중) · 돌격병 — 공격→공격→방어", "reckless_raider"),
    ("보통 · 균형병 — 연속 행동 제한", "balanced_soldier"),
    ("보통 · 숙련 방패병 — 방어 적응형", "veteran_guard"),
    ("보통 · 신중 추격자 — 완만한 압박", "cautious_hunter"),
    ("어려움 · 압박자 — 상태 기반 공격", "pressure"),
    ("어려움 · 관찰자 — 최근 행동 카운터", "adaptive"),
    ("어려움 · 전술 평가자 — 기대값 판단", "tactical_evaluator"),
    ("매우 어려움 · 분석관 — 최근 가중 기대값", "weighted_analyst"),
    ("매우 어려움(재조정 예정) · 적응 결투가", "regret_duelist"),
    ("매우 어려움 · 집행자 — 후속 기회 평가", "executor"),
)

NPC_ID_BY_LABEL = dict(NPC_OPTIONS)
NPC_LABEL_BY_ID = {strategy: label for label, strategy in NPC_OPTIONS}

OUTCOME_LABELS = {
    "PLAYER_WIN": "플레이어 승리",
    "ENEMY_WIN": "NPC 승리",
    "DOUBLE_KO": "더블 KO",
    "STALEMATE": "교착",
}


def signed(value: int) -> str:
    return f"+{value}" if value > 0 else str(value)


class CharacterPanel(ttk.LabelFrame):
    def __init__(self, parent: tk.Misc, title: str) -> None:
        super().__init__(parent, text=title, padding=12)
        self.columnconfigure(1, weight=1)
        self.value_labels: dict[str, ttk.Label] = {}
        self.bars: dict[str, ttk.Progressbar] = {}

        resources = (
            ("hp", "HP"),
            ("stamina", "스태미너"),
            ("break_gauge", "브레이크"),
        )
        for row, (key, label) in enumerate(resources):
            ttk.Label(self, text=label, width=9).grid(
                row=row, column=0, sticky="w", pady=3
            )
            bar = ttk.Progressbar(self, maximum=100, mode="determinate")
            bar.grid(row=row, column=1, sticky="ew", padx=(4, 8), pady=3)
            value_label = ttk.Label(self, text="0 / 100", width=11, anchor="e")
            value_label.grid(row=row, column=2, sticky="e", pady=3)
            self.bars[key] = bar
            self.value_labels[key] = value_label

        self.status_label = ttk.Label(self, text="상태: 정상")
        self.status_label.grid(row=3, column=0, columnspan=3, sticky="w", pady=(8, 0))
        self.down_label = ttk.Label(self, text="다운: 0 / 3")
        self.down_label.grid(row=4, column=0, columnspan=3, sticky="w")

    def update_state(self, character) -> None:
        values = {
            "hp": (character.hp, character.max_hp),
            "stamina": (character.stamina, character.max_stamina),
            "break_gauge": (
                character.break_gauge,
                character.max_break_gauge,
            ),
        }
        for key, (current, maximum) in values.items():
            self.bars[key].configure(maximum=maximum, value=current)
            self.value_labels[key].configure(text=f"{current} / {maximum}")

        if character.is_ko:
            status = "KO"
        elif character.is_down:
            status = f"다운 대기 {character.skipped_turns_remaining}턴"
        elif character.is_groggy:
            status = "완전 그로기"
        else:
            status = "정상"
        self.status_label.configure(text=f"상태: {status}")
        self.down_label.configure(
            text=f"다운: {character.down_count} / {character.max_down_count}"
        )


class BattlePlaytestApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Battle Simulator POC · 플레이테스트")
        self.root.geometry("980x760")
        self.root.minsize(820, 650)
        self.engine: ManualBattleEngine | None = None
        self.rendered_trace_count = 0
        self.result_announced = False

        self._configure_style()
        self._build_ui()
        self.start_match()

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Malgun Gothic", 16, "bold"))
        style.configure("Status.TLabel", font=("Malgun Gothic", 11, "bold"))
        style.configure("Action.TButton", font=("Malgun Gothic", 11, "bold"), padding=9)

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=14)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(4, weight=1)

        ttk.Label(main, text="Battle Simulator POC", style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            main,
            text="무스킬 1 대 1 플레이테스트 · CPU는 현재 턴 선택을 보지 않습니다.",
        ).grid(row=1, column=0, sticky="w", pady=(2, 10))

        controls = ttk.Frame(main)
        controls.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        controls.columnconfigure(1, weight=1)
        ttk.Label(controls, text="NPC").grid(row=0, column=0, padx=(0, 6))
        self.npc_var = tk.StringVar(value=NPC_OPTIONS[3][0])
        self.npc_combo = ttk.Combobox(
            controls,
            textvariable=self.npc_var,
            values=[label for label, _ in NPC_OPTIONS],
            state="readonly",
            width=49,
        )
        self.npc_combo.grid(row=0, column=1, sticky="ew")
        ttk.Label(controls, text="시드").grid(row=0, column=2, padx=(12, 6))
        self.seed_var = tk.StringVar(value="20260829")
        ttk.Entry(controls, textvariable=self.seed_var, width=14).grid(row=0, column=3)
        ttk.Button(controls, text="새 경기", command=self.start_match).grid(
            row=0, column=4, padx=(10, 0)
        )

        states = ttk.Frame(main)
        states.grid(row=3, column=0, sticky="ew")
        states.columnconfigure(0, weight=1)
        states.columnconfigure(1, weight=1)
        self.player_panel = CharacterPanel(states, "플레이어")
        self.player_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.enemy_panel = CharacterPanel(states, "NPC")
        self.enemy_panel.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        lower = ttk.Panedwindow(main, orient="vertical")
        lower.grid(row=4, column=0, sticky="nsew", pady=(12, 0))

        action_box = ttk.LabelFrame(lower, text="행동 선택", padding=12)
        for column in range(3):
            action_box.columnconfigure(column, weight=1)
        self.turn_label = ttk.Label(action_box, text="", style="Status.TLabel")
        self.turn_label.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))

        self.action_buttons: dict[Action, ttk.Button] = {}
        for column, action in enumerate(Action):
            button = ttk.Button(
                action_box,
                text=ACTION_LABELS[action],
                style="Action.TButton",
                command=lambda selected=action: self.take_action(selected),
            )
            button.grid(row=1, column=column, sticky="ew", padx=4)
            self.action_buttons[action] = button
        ttk.Label(
            action_box,
            text="공격 > 회피 > 방어 > 공격 · 주사위 우위에 따라 역전 가능",
        ).grid(row=2, column=0, columnspan=3, pady=(9, 0))
        lower.add(action_box, weight=0)

        log_box = ttk.LabelFrame(lower, text="전투 로그", padding=8)
        self.log = ScrolledText(
            log_box,
            wrap="word",
            height=18,
            font=("Malgun Gothic", 10),
            state="disabled",
        )
        self.log.pack(fill="both", expand=True)
        lower.add(log_box, weight=1)

    def start_match(self) -> None:
        try:
            seed = int(self.seed_var.get().strip())
        except ValueError:
            messagebox.showerror("잘못된 시드", "시드는 정수로 입력해주세요.")
            return
        label = self.npc_var.get()
        strategy = NPC_ID_BY_LABEL.get(label)
        if strategy is None:
            messagebox.showerror("NPC 선택 오류", "NPC를 다시 선택해주세요.")
            return

        self.engine = ManualBattleEngine(seed, enemy_strategy=strategy)
        self.rendered_trace_count = 0
        self.result_announced = False
        self._clear_log()
        self._append_log(f"새 경기 시작 · 시드 {seed}")
        self._append_log(f"상대: {label} [{strategy}]\n")
        self.refresh()

    def take_action(self, action: Action) -> None:
        if self.engine is None or not self.engine.player_can_choose:
            return
        try:
            self.engine.submit_player_action(action)
            self.engine.advance_until_player_choice()
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

        if self.engine.outcome:
            status = OUTCOME_LABELS.get(self.engine.outcome, self.engine.outcome)
            self.turn_label.configure(
                text=f"경기 종료 · {status} · 총 {self.engine.match_turn}턴"
            )
        else:
            next_turn = self.engine.turn_in_round + 1
            self.turn_label.configure(
                text=(
                    f"라운드 {self.engine.round_number} · "
                    f"라운드 턴 {next_turn}/8 · "
                    f"전체 {self.engine.match_turn + 1}턴 행동 선택"
                )
            )

        enabled = self.engine.player_can_choose and self.engine.outcome is None
        for button in self.action_buttons.values():
            button.configure(state="normal" if enabled else "disabled")

        if self.engine.outcome and not self.result_announced:
            self.result_announced = True
            result = OUTCOME_LABELS.get(self.engine.outcome, self.engine.outcome)
            self._append_log(
                f"\n=== 경기 종료: {result} · {self.engine.match_turn}턴 ==="
            )
            messagebox.showinfo("경기 종료", f"{result}\n총 {self.engine.match_turn}턴")

    def _render_new_trace(self) -> None:
        if self.engine is None:
            return
        new_events = self.engine.trace[self.rendered_trace_count :]
        for event in new_events:
            if event["event"] == "turn":
                for line in self._format_turn_event(event):
                    self._append_log(line)
            elif event["event"] == "interval":
                self._append_log(
                    f"  [인터벌] 라운드 {event['round']} 종료 · HP/STA/BRK 회복"
                )
        self.rendered_trace_count = len(self.engine.trace)

    def _format_turn_event(self, event: dict) -> list[str]:
        resolution = event["resolution"]
        prefix = (
            f"R{event['round']} T{event['turn_in_round']} "
            f"(전체 {event['match_turn']})"
        )
        kind = resolution["kind"]
        if kind == "normal":
            player_action = ACTION_LABELS[Action(resolution["player_action"])]
            enemy_action = ACTION_LABELS[Action(resolution["enemy_action"])]
            headline = (
                f"{prefix} · 플레이어 {player_action} vs NPC {enemy_action} · "
                f"주사위 {resolution['player_die']}:{resolution['enemy_die']} · "
                f"결과표 {resolution['entry_id']}"
            )
        elif kind == "groggy":
            action = ACTION_LABELS[Action(resolution["action"])]
            headline = (
                f"{prefix} · {resolution['actor']}가 그로기 상태의 "
                f"{resolution['target']}에게 {action} · 결과표 {resolution['entry_id']}"
            )
        elif kind == "both_groggy_idle":
            headline = f"{prefix} · 양측 완전 그로기, 행동 없이 턴 경과"
        else:
            healed = ", ".join(resolution.get("healed", [])) or "없음"
            woke = ", ".join(resolution.get("woke", [])) or "없음"
            headline = f"{prefix} · 다운 대기 · 회복 {healed} · 기상 {woke}"

        lines = ["", headline]
        for index, label in enumerate(("플레이어", "NPC")):
            before = event["before"][index]
            after = event["after"][index]
            changes = []
            for key, resource in (
                ("hp", "HP"),
                ("stamina", "STA"),
                ("break_gauge", "BRK"),
            ):
                delta = after[key] - before[key]
                if delta:
                    changes.append(
                        f"{resource} {before[key]}→{after[key]}({signed(delta)})"
                    )
            if not changes:
                changes.append("자원 변화 없음")
            lines.append(f"  {label}: " + ", ".join(changes))
            if not before["is_groggy"] and after["is_groggy"]:
                lines.append(f"  {label}: 완전 그로기 진입")
            if after["down_count"] > before["down_count"]:
                lines.append(
                    f"  {label}: 다운 {after['down_count']}회"
                    + (" · KO" if after["is_ko"] else "")
                )
            if before["is_down"] and not after["is_down"]:
                lines.append(f"  {label}: 기상")
        return lines

    def _append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")


def main() -> None:
    root = tk.Tk()
    BattlePlaytestApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
