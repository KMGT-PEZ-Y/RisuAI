"""Explicit desktop smoke check; not part of headless unittest discovery."""
import time
import tkinter as tk
from unittest.mock import patch

from muh_playtest_ui import MuhPlaytestApp


def main():
    root = tk.Tk()
    root.withdraw()
    errors = []
    root.report_callback_exception = lambda *args: errors.append(args)
    with patch("tkinter.messagebox.showerror", side_effect=lambda *args: errors.append(args)):
        app = MuhPlaytestApp(root)
        assert app.engine.strategies[1] == "ng_plus"
        assert len(app.skill_ids) == 30
        custom = ("h04", "h05", "h06", "m02", "u03")
        app.enemy_loadout.selection_clear(0, "end")
        for code in custom:
            app.enemy_loadout.selection_set(app.skill_ids.index(code))
        app.start_match()
        assert {s.skill_id for s in app.engine.enemy.skill_loadout} == set(custom)
        app.execute_turn()
        assert app._pending_ng is not None
        deadline = time.monotonic() + 15
        while app._pending_ng is not None and time.monotonic() < deadline:
            root.update()
            time.sleep(.01)
        assert app._pending_ng is None, "NG+ worker timed out"
        assert app.engine.match_turn == 1
        assert app.engine.last_ng_decisions[1] is not None
        assert app.ng_log.get("1.0", "end").strip()
        app.execute_turn()
        cancelled = app._pending_ng
        app.enemy_loadout.selection_clear(0, "end")
        app.judgment_var.set("0")
        app.start_match()
        assert cancelled[0].is_set()
        app._poll_ng(cancelled)
        assert app.engine.match_turn == 0
        assert not app.engine.enemy.skill_loadout
        assert app.engine.ng_judgment == 0
        app.execute_turn()
        deadline = time.monotonic() + 5
        while app._pending_ng is not None and time.monotonic() < deadline:
            root.update()
            time.sleep(.01)
        assert app.engine.match_turn == 1
        assert app.engine.last_ng_decisions[1].transitions == 0
        app.npc_var.set(app.NPC_CHOICES[0][0])
        app.enemy_mode.set("수동 입력")
        app.start_match()
        assert app.engine.manual_enemy
        app.execute_turn()
        assert app.engine.match_turn == 1
        assert not errors, errors
        print("UI OK: 30 skills, custom NG+ deck, async turn/log, cancel, empty deck, judgment=0, legacy manual")
    root.destroy()


if __name__ == "__main__":
    main()
