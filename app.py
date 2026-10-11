"""Small native Pygame interface for training and presenting the experiment."""
import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import sys
import traceback

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame

from models import load_driver
from simulator import Car, COLORS, MAX_STEPS, choose_action
from tracks import ROOT, TRACKS, get_spec, load_track
from training import CAR_COLORS, Session

CANVAS_SIZE = (1280, 800)
BG = (19, 23, 29)
PANEL = (28, 33, 40)
LINE = (54, 62, 72)
TEXT = (237, 240, 243)
MUTED = (156, 165, 175)
ACCENT = (205, 58, 65)
GREEN = (94, 196, 142)
COLOR_RGB = {"mixed": (225, 225, 225), "red": (239, 48, 59),
             "green": (55, 186, 94), "blue": (67, 132, 242),
             "yellow": (242, 211, 63), "orange": (241, 146, 52),
             "pink": (232, 123, 176), "purple": (167, 103, 215)}


@dataclass
class Button:
    rect: pygame.Rect
    action: str
    value: object = None


class App:
    def __init__(self, size=None, save_dir=None, seed=7):
        pygame.init()
        if size is None:
            info = pygame.display.Info()
            scale = min(1, max(640, info.current_w - 80) / 1280,
                        max(400, info.current_h - 100) / 800)
            size = (int(1280 * scale), int(800 * scale))
        self.window = pygame.display.set_mode(size, pygame.RESIZABLE)
        pygame.display.set_caption("NEAT Car Simulation")
        self.canvas = pygame.Surface(CANVAS_SIZE)
        self.fonts = {size: pygame.font.SysFont("Segoe UI", size)
                      for size in (11, 12, 14, 16, 18, 22, 28, 32)}
        self.clock = pygame.time.Clock()
        self.save_dir = Path(save_dir) if save_dir is not None else ROOT / "saved"
        self.seed = seed
        self.screen = "menu"
        self.mode = "training"
        self.track_index = 0
        self.color_index = 0
        self.paused = False
        self.radars = False
        self.speed_multiplier = 1
        self.running = True
        self.session = None
        self.driver = None
        self.replay_car = None
        self.replay_ticks = 0
        self.replay_wait = 0
        self.replay_runs = 1
        self.status = "Choose a circuit and start a session."
        self.buttons = []
        self.preview_cache = {}
        self.sprite_cache = {}
        self.viewport = pygame.Rect(344, 168, 912, 513)
        # Fail clearly at startup if the project was copied without its assets.
        for color in CAR_COLORS:
            self.sprite(color, 0, 1)
        load_track(self.track_id)

    @property
    def track_id(self):
        return TRACKS[self.track_index].id

    @property
    def color(self):
        return COLORS[self.color_index]

    def find_driver(self):
        local = self.save_dir / f"{self.track_id}.json"
        if local.is_file():
            return local
        bundled = ROOT / "demos" / "classic.json"
        return bundled if bundled.is_file() else None

    def start(self, mode=None):
        self.mode = mode or self.mode
        try:
            if self.mode == "training":
                self.session = Session(self.track_id, self.color, self.seed, self.save_dir)
                self.status = "New best drivers are saved after each generation."
            else:
                path = self.find_driver()
                if path is None:
                    raise ValueError("No saved driver yet. Run training first.")
                self.driver = load_driver(path)
                self.replay_car = Car(load_track(self.track_id),
                                      "red" if self.color == "mixed" else self.color)
                self.replay_ticks = self.replay_wait = 0
                self.replay_runs = 1
                trained_name = get_spec(self.driver.track_id).name
                self.status = f"Saved driver trained on {trained_name}."
                if self.driver.track_id != self.track_id:
                    self.status += " Transfer test: performance may differ."
            self.paused = False
            self.screen = "simulation"
        except (ValueError, OSError, pygame.error) as error:
            self.status = str(error)
            self.screen = "menu"

    def switch_track(self, offset):
        self.track_index = (self.track_index + offset) % len(TRACKS)
        if self.screen == "simulation":
            self.start()

    def change_color(self, index=None):
        self.color_index = (self.color_index + 1) % len(COLORS) if index is None else index
        if self.screen == "simulation":
            if self.mode == "training":
                self.session.set_color(self.color)
            else:
                self.replay_car.color = "red" if self.color == "mixed" else self.color

    def action(self, action, value=None):
        if action == "start":
            self.start()
        elif action == "mode":
            self.mode = value
        elif action == "track":
            self.switch_track(value)
        elif action == "select_track":
            self.track_index = value
        elif action == "color":
            self.change_color(value)
        elif action == "pause":
            self.paused = not self.paused
        elif action == "restart":
            self.start()
        elif action == "radar":
            self.radars = not self.radars
        elif action == "speed":
            self.speed_multiplier = 4 if self.speed_multiplier == 1 else 1
        elif action == "menu":
            self.screen = "menu"
            self.status = "Choose a circuit and start a session."

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.VIDEORESIZE:
            self.window = pygame.display.set_mode((max(640, event.w), max(400, event.h)),
                                                  pygame.RESIZABLE)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            x, y = event.pos
            position = (x * 1280 / self.window.get_width(),
                        y * 800 / self.window.get_height())
            for button in reversed(self.buttons):
                if button.rect.collidepoint(position):
                    self.action(button.action, button.value)
                    break
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.screen == "menu":
                    self.running = False
                else:
                    self.action("menu")
            elif event.key == pygame.K_RETURN and self.screen == "menu":
                self.start()
            elif event.key in (pygame.K_LEFT, pygame.K_RIGHT) and self.screen == "menu":
                self.switch_track(-1 if event.key == pygame.K_LEFT else 1)
            elif event.key == pygame.K_c:
                self.change_color()
            elif self.screen == "simulation":
                actions = {pygame.K_SPACE: "pause", pygame.K_r: "restart",
                           pygame.K_s: "radar", pygame.K_t: "track", pygame.K_f: "speed"}
                if event.key in actions:
                    self.action(actions[event.key], 1 if event.key == pygame.K_t else None)

    def update(self):
        if self.screen != "simulation" or self.paused:
            return
        for _ in range(self.speed_multiplier):
            if self.mode == "training":
                self.session.step()
            elif self.replay_wait:
                self.replay_wait -= 1
                if self.replay_wait == 0:
                    self.replay_car = Car(load_track(self.track_id), self.replay_car.color)
                    self.replay_ticks = 0
                    self.replay_runs += 1
            else:
                self.replay_car.step(choose_action(self.driver.network, self.replay_car))
                self.replay_ticks += 1
                if not self.replay_car.alive or self.replay_ticks >= MAX_STEPS:
                    self.replay_wait = 90

    def text(self, text, x, y, size=16, color=TEXT):
        rendered = self.fonts[size].render(str(text), True, color)
        self.canvas.blit(rendered, (x, y))

    def button(self, label, rect, action, value=None, selected=False, primary=False):
        rect = pygame.Rect(rect)
        mouse = pygame.mouse.get_pos()
        mouse = (mouse[0] * 1280 / self.window.get_width(),
                 mouse[1] * 800 / self.window.get_height())
        fill = ACCENT if primary else (48, 56, 66) if selected else (35, 41, 49)
        if rect.collidepoint(mouse):
            fill = tuple(min(255, channel + 13) for channel in fill)
        pygame.draw.rect(self.canvas, fill, rect, border_radius=4)
        if selected:
            pygame.draw.rect(self.canvas, MUTED, rect, 1, border_radius=4)
        font = self.fonts[14]
        rendered = font.render(label, True, TEXT)
        self.canvas.blit(rendered, rendered.get_rect(center=rect.center))
        self.buttons.append(Button(rect, action, value))

    def preview(self, track_id, size):
        key = (track_id, size)
        if key not in self.preview_cache:
            self.preview_cache[key] = pygame.transform.smoothscale(
                load_track(track_id).surface, size)
        return self.preview_cache[key]

    def sprite(self, color, angle, scale):
        key = (color, int(angle) % 360, round(scale, 3))
        if key not in self.sprite_cache:
            path = ROOT / "assets" / "cars" / f"car{color}.png"
            image = pygame.image.load(str(path)).convert()
            image.set_colorkey((0, 0, 0))
            image = pygame.transform.smoothscale(image,
                (max(1, round(60 * scale)), max(1, round(30 * scale))))
            self.sprite_cache[key] = pygame.transform.rotate(image, angle)
        return self.sprite_cache[key]

    def draw_car(self, car, sensors=False):
        scale = self.viewport.w / car.track.width
        center = (self.viewport.x + car.position[0] * scale,
                  self.viewport.y + car.position[1] * scale)
        if sensors:
            for endpoint, _ in car.radars:
                end = (self.viewport.x + endpoint[0] * scale,
                       self.viewport.y + endpoint[1] * scale)
                pygame.draw.line(self.canvas, GREEN, center, end, 1)
                pygame.draw.circle(self.canvas, GREEN, end, 2)
        image = self.sprite(car.color, car.angle, scale)
        self.canvas.blit(image, image.get_rect(center=center))

    def draw_menu(self):
        pygame.draw.rect(self.canvas, PANEL, (24, 128, 296, 638), border_radius=5)
        self.text("SESSION", 44, 150, 12, MUTED)
        self.button("Train live", (44, 180, 122, 38), "mode", "training",
                    self.mode == "training")
        self.button("Replay saved", (174, 180, 126, 38), "mode", "replay",
                    self.mode == "replay")
        self.text("TRACK", 44, 247, 12, MUTED)
        self.text(TRACKS[self.track_index].name, 44, 275, 22)
        self.button("< Previous", (44, 315, 122, 36), "track", -1)
        self.button("Next >", (174, 315, 126, 36), "track", 1)
        self.text(f"{self.track_index + 1:02d} / {len(TRACKS):02d} circuits", 44, 361, 12, MUTED)
        self.text("CAR COLOR", 44, 410, 12, MUTED)
        for index, color in enumerate(COLORS):
            rect = pygame.Rect(44 + index % 4 * 65, 442 + index // 4 * 44, 58, 36)
            self.button("", rect, "color", index, selected=index == self.color_index)
            pygame.draw.circle(self.canvas, COLOR_RGB[color], rect.center, 9)
            if color == "mixed":
                pygame.draw.circle(self.canvas, COLOR_RGB["red"], (rect.centerx - 5, rect.centery), 5)
                pygame.draw.circle(self.canvas, COLOR_RGB["blue"], (rect.centerx + 5, rect.centery), 5)
        self.text(self.color.capitalize(), 44, 537, 14, MUTED)
        selected_sprite = self.sprite("red" if self.color == "mixed" else self.color, 0, 1.7)
        self.canvas.blit(selected_sprite, selected_sprite.get_rect(center=(250, 558)))
        self.text("30 cars  /  5 sensors  /  NEAT", 44, 600, 14, MUTED)
        self.button("Start training" if self.mode == "training" else "Replay driver",
                    (44, 652, 256, 48), "start", primary=True)
        self.text("Enter to start", 44, 715, 12, MUTED)
        self.text("TRACK PREVIEW", 344, 138, 12, MUTED)
        self.text("Click a thumbnail to choose a circuit", 916, 138, 12, MUTED)
        self.canvas.blit(self.preview(self.track_id, self.viewport.size), self.viewport)
        track = load_track(self.track_id)
        start = Car(track, "red" if self.color == "mixed" else self.color)
        self.draw_car(start)
        self.text("START", self.viewport.x + 416, self.viewport.y + 468, 11, (70, 90, 70))
        self.text(self.status, 344, 689, 12, MUTED)
        for index, spec in enumerate(TRACKS):
            rect = pygame.Rect(344 + index * 83, 720, 74, 42)
            self.canvas.blit(self.preview(spec.id, rect.size), rect)
            pygame.draw.rect(self.canvas, ACCENT if index == self.track_index else LINE,
                             rect.inflate(4, 4), 2)
            self.buttons.append(Button(rect, "select_track", index))
            self.text(f"{index + 1:02d}", rect.x + 27, 769, 11, MUTED)

    def draw_simulation(self):
        pygame.draw.rect(self.canvas, PANEL, (24, 128, 296, 638), border_radius=5)
        training = self.mode == "training"
        cars = [agent.car for agent in self.session.agents] if training else [self.replay_car]
        living = [car for car in cars if car.alive]
        leader = max(living or cars, key=lambda car: car.fitness)
        ticks = self.session.ticks if training else self.replay_ticks
        self.text("LIVE TRAINING" if training else "SAVED DRIVER", 44, 150, 12,
                  ACCENT if training else GREEN)
        label = "Generation" if training else "Replay run"
        value = self.session.generation if training else self.replay_runs
        self.text(label, 44, 188, 14, MUTED)
        self.text(f"{value:03d}", 44, 213, 32)
        self.text("On track", 174, 188, 14, MUTED)
        self.text(f"{len(living):02d} / {len(cars):02d}", 174, 213, 28)
        pygame.draw.line(self.canvas, LINE, (44, 265), (300, 265))
        self.text("Best fitness this session" if training else "Replay fitness", 44, 285, 14, MUTED)
        fitness = max(self.session.best_fitness, leader.fitness) if training else leader.fitness
        self.text(f"{fitness:.1f}", 44, 309, 28)
        self.text(f"{ticks / 60:.1f} / {MAX_STEPS / 60:.0f} seconds", 185, 323, 12, MUTED)
        self.text("LEADING CAR / SENSORS", 44, 375, 12, MUTED)
        for index, value in enumerate(leader.inputs()):
            y = 410 + index * 22
            self.text(("-90", "-45", "0", "+45", "+90")[index], 44, y - 4, 12, MUTED)
            pygame.draw.rect(self.canvas, LINE, (83, y, 182, 7))
            pygame.draw.rect(self.canvas, GREEN, (83, y, round(182 * value), 7))
            self.text(f"{value:.2f}", 270, y - 6, 11, MUTED)
        self.button("Resume" if self.paused else "Pause", (44, 547, 122, 36), "pause")
        self.button("Restart", (174, 547, 126, 36), "restart")
        self.button("Sensors on" if self.radars else "Sensors off",
                    (44, 592, 122, 36), "radar", selected=self.radars)
        self.button(f"Speed {self.speed_multiplier}x", (174, 592, 126, 36), "speed")
        self.button("Next track", (44, 637, 122, 36), "track", 1)
        self.button("Color: " + self.color, (174, 637, 126, 36), "color")
        self.button("Back to menu", (44, 703, 256, 36), "menu")
        self.text(TRACKS[self.track_index].name, 344, 135, 18)
        self.text("PAUSED" if self.paused else f"{self.speed_multiplier}x playback", 1140, 139, 12, MUTED)
        self.canvas.blit(self.preview(self.track_id, self.viewport.size), self.viewport)
        self.canvas.set_clip(self.viewport)
        for car in living:
            self.draw_car(car, sensors=self.radars and car is leader)
        if not living and not training:
            self.draw_car(self.replay_car, sensors=self.radars)
        self.canvas.set_clip(None)
        if self.paused:
            banner = pygame.Rect(673, 391, 250, 58)
            pygame.draw.rect(self.canvas, PANEL, banner, border_radius=4)
            self.text("Paused / Space to resume", 696, 409, 18)
        self.text(self.status, 344, 700, 12, MUTED)
        if not training:
            name = get_spec(self.driver.track_id).name
            self.text(f"Trained on: {name}  /  Generation {self.driver.generation}  /  Saved fitness {self.driver.fitness:.1f}",
                      344, 727, 14, MUTED)
        self.text("Space  Pause     R  Restart     S  Sensors     T  Track     C  Color     F  Speed     Esc  Menu",
                  344, 763, 12, MUTED)

    def draw(self):
        self.buttons = []
        self.canvas.fill(BG)
        pygame.draw.rect(self.canvas, ACCENT, (24, 27, 5, 34))
        self.text("NEAT Car Simulation", 42, 23, 32)
        self.text("A 2D neuroevolution experiment", 44, 70, 16, MUTED)
        self.text("TRAIN / OBSERVE / REPLAY", 1040, 39, 12, MUTED)
        pygame.draw.line(self.canvas, LINE, (24, 108), (1256, 108))
        if self.screen == "menu":
            self.draw_menu()
        else:
            self.draw_simulation()
        self.window.blit(pygame.transform.smoothscale(self.canvas, self.window.get_size()), (0, 0))
        pygame.display.flip()

    def run(self, max_frames=None):
        frames = 0
        while self.running:
            for event in pygame.event.get():
                self.handle_event(event)
            self.update()
            self.draw()
            self.clock.tick(60)
            frames += 1
            if max_frames is not None and frames >= max_frames:
                break


def main():
    parser = argparse.ArgumentParser(description="NEAT car training and presentation demo")
    parser.add_argument("--track", choices=[track.id for track in TRACKS], default="classic")
    parser.add_argument("--mode", choices=("menu", "training", "replay"), default="menu")
    parser.add_argument("--color", choices=COLORS, default="mixed")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--frames", type=int, help="Exit after this many displayed frames")
    parser.add_argument("--screenshot", type=Path, help="Save the final rendered frame")
    args = parser.parse_args()
    try:
        app = App(seed=args.seed)
        app.track_index = next(index for index, track in enumerate(TRACKS) if track.id == args.track)
        app.color_index = COLORS.index(args.color)
        if args.mode != "menu":
            app.start(args.mode)
        app.run(args.frames)
        if args.screenshot:
            args.screenshot.parent.mkdir(parents=True, exist_ok=True)
            pygame.image.save(app.canvas, str(args.screenshot))
        return 0
    except Exception:
        log = ROOT / "logs" / "error.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(traceback.format_exc(), encoding="utf-8")
        print(f"Could not start the simulation. Details: {log}", file=sys.stderr)
        return 1
    finally:
        pygame.quit()


if __name__ == "__main__":
    raise SystemExit(main())
