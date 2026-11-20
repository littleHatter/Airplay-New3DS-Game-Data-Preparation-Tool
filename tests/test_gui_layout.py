"""Tkinter layout regression: the primary action must never disappear behind the log."""
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location('installer_ui', ROOT / '3ds_game_data_installer.py')
installer_ui = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer_ui)


class FooterLayoutTests(unittest.TestCase):

    def test_window_title(self):
        try:
            window = installer_ui.GameDataInstaller()
        except installer_ui.tk.TclError as error:
            self.skipTest(f'No graphical display available: {error}')
        self.addCleanup(window.destroy)
        self.assertEqual(window.title(), 'Airplay New 3DS Game Data Preparation Tool')
    def test_prepare_button_visible_for_all_games(self):
        try:
            window = installer_ui.GameDataInstaller()
        except installer_ui.tk.TclError as error:
            self.skipTest(f'No graphical display available: {error}')
        self.addCleanup(window.destroy)
        for height in (780, 660):
            window.geometry(f'800x{height}')
            for game in installer_ui.GAME_LABELS:
                with self.subTest(game=game, height=height):
                    window.game.set(game)
                    window._show_game_fields()
                    window.update()
                    top = window.start.winfo_rooty() - window.winfo_rooty()
                    bottom = top + window.start.winfo_height()
                    self.assertTrue(window.start.winfo_ismapped())
                    self.assertGreaterEqual(top, 0)
                    self.assertLessEqual(bottom, window.winfo_height(), 'Prepare button clipped')
                    # A visible activity log must not overlap the pinned footer.
                    if window.logs.winfo_ismapped():
                        log_bottom = window.logs.winfo_rooty() - window.winfo_rooty() + window.logs.winfo_height()
                        self.assertLessEqual(log_bottom, top)


if __name__ == '__main__':
    unittest.main()
