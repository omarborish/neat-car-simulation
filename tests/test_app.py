"""Real Pygame events exercise presentation controls without a desktop."""
import importlib
import importlib.util
import os
from pathlib import Path
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame
from workspace_temp import WorkspaceTemp


class AppTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("app"),
                             "Presentation controls have not been implemented")
        self.module = importlib.import_module("app")
        self.folder = WorkspaceTemp()
        self.addCleanup(self.folder.cleanup)
        self.app = self.module.App(size=(960, 600), save_dir=Path(self.folder.name))
        self.addCleanup(pygame.quit)

    def key(self, key):
        self.app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key))

    def test_pause_stops_time_and_resume_moves_cars(self):
        self.app.start("training")
        self.key(pygame.K_SPACE)
        positions = [tuple(a.car.position) for a in self.app.session.agents]
        self.app.update()
        self.assertEqual(self.app.session.ticks, 0)
        self.assertEqual([tuple(a.car.position) for a in self.app.session.agents], positions)
        self.key(pygame.K_SPACE)
        self.app.update()
        self.assertEqual(self.app.session.ticks, 1)

    def test_switching_track_restarts_the_population(self):
        self.app.start("training")
        self.app.update()
        self.key(pygame.K_t)
        self.assertEqual(self.app.session.track.id, "track02")
        self.assertEqual(self.app.session.ticks, 0)
        self.assertEqual(self.app.session.generation, 1)

    def test_changing_color_keeps_training_progress(self):
        self.app.start("training")
        self.app.update()
        positions = [tuple(a.car.position) for a in self.app.session.agents]
        self.key(pygame.K_c)
        self.assertEqual(self.app.session.ticks, 1)
        self.assertEqual([tuple(a.car.position) for a in self.app.session.agents], positions)
        self.assertTrue(all(a.car.color == "red" for a in self.app.session.agents))

    def test_menu_and_restart_are_responsive(self):
        self.app.start("training")
        self.app.update()
        self.key(pygame.K_r)
        self.assertEqual(self.app.session.ticks, 0)
        self.key(pygame.K_ESCAPE)
        self.assertEqual(self.app.screen, "menu")

    def test_resized_window_maps_mouse_to_correct_button(self):
        self.app.draw()
        button = next(b for b in self.app.buttons if b.action == "start")
        x, y = button.rect.center
        position = (round(x * 960 / 1280), round(y * 600 / 800))
        self.app.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN,
                                                button=1, pos=position))
        self.assertEqual(self.app.screen, "simulation")

    def test_radar_toggle_and_render(self):
        self.app.start("training")
        self.key(pygame.K_s)
        self.assertTrue(self.app.radars)
        self.app.update()
        self.app.draw()
        self.assertEqual(self.app.canvas.get_size(), (1280, 800))

    def test_replay_displays_the_training_track_when_transferring(self):
        from models import save_driver
        self.app.start("training")
        network = self.app.session.agents[0].network
        save_driver(Path(self.folder.name) / "track02.json", network, "classic", 1, 1.0, 7)
        self.app.track_index = 1
        self.app.start("replay")
        self.assertEqual(self.app.screen, "simulation")
        self.assertIn("Transfer test", self.app.status)
        self.assertEqual(self.app.driver.track_id, "classic")
        self.app.update()

    def test_bad_saved_driver_returns_to_menu_with_error(self):
        (Path(self.folder.name) / "classic.json").write_text("broken driver")
        self.app.start("replay")
        self.assertEqual(self.app.screen, "menu")
        self.assertIn("Could not read saved driver", self.app.status)


if __name__ == "__main__":
    unittest.main()
