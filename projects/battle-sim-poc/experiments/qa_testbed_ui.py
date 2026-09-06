"""Withdrawn Tk smoke checks for the three legacy testbeds and NG+ UI."""
from pathlib import Path
import sys
import tkinter as tk
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from battle_sim import Action
from playtest_ui import BattlePlaytestApp
from skill_playtest_ui import SkillPlaytestApp
from easy_enemy_playtest_ui import EasyEnemyPlaytestApp
from qa_ng_plus_ui import main as check_ng_ui


def main():
    for cls in (BattlePlaytestApp, SkillPlaytestApp, EasyEnemyPlaytestApp):
        root = tk.Tk()
        root.withdraw()
        errors = []
        root.report_callback_exception = lambda *args: errors.append(args)
        try:
            with patch("tkinter.messagebox.showerror", side_effect=lambda *args: errors.append(args)):
                app = cls(root)
                app.start_match()
                assert app.engine is not None, cls.__name__
                if cls is BattlePlaytestApp:
                    app.take_action(Action.ATTACK)
                else:
                    app.execute_turn()
                root.update_idletasks()
                assert app.engine.match_turn >= 1, cls.__name__
                assert not errors, (cls.__name__, errors)
                print(f"UI OK: {cls.__name__}, initialize / start / turn / refresh")
        finally:
            root.destroy()
    check_ng_ui()


if __name__ == "__main__":
    main()
