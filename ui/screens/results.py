"""Looking at saved results: experiment tables and graphs, and training graphs."""

from __future__ import annotations

import logging
from pathlib import Path

import pygame

from evaluation.experiment import LABELS
from ui.app import Screen
from ui.components import draw_text, wrap_text
from ui.results_data import (
    ExperimentInfo, list_experiments, list_graphs, read_experiment, scenario_names, scenario_view)
from ui.widgets import draw_table

log = logging.getLogger(__name__)


class ResultsScreen(Screen):
    name = "results"
    heading = "Results"

    def __init__(self, app, folder: Path | None = None) -> None:
        super().__init__(app)
        self.mode = "experiments"  # or "training"
        self.view = "table"  # or "graphs"
        self.items: list[tuple[str, Path | None, str]] = []  # (label, path, problem)
        self.index = 0
        self.sub = 0  # scenario number (table) or graph number (graphs)
        self.preselect = folder
        self.data: dict | None = None
        self.message = ""
        self.pane_top = 0
        self._row_rects: list[pygame.Rect] = []
        self._first_visible = 0
        self._image_cache: tuple[tuple, pygame.Surface | None] | None = None
        mode_exp = self.add("Experiments", None, "", "Tables and graphs of saved experiments",
                            lambda: self.set_mode("experiments"))
        mode_train = self.add("Training graphs", None, "", "Graphs saved after training runs",
                              lambda: self.set_mode("training"))
        self.mode_buttons = (mode_exp, mode_train)
        self.table_button = self.add("Table", pygame.K_t, "T", "Show the numbers", lambda: self.set_view("table"),
                                     lambda: self.mode == "experiments")
        self.graphs_button = self.add("Graphs", pygame.K_g, "G", "Show the graphs", lambda: self.set_view("graphs"),
                                      lambda: self.mode == "experiments")
        self.newer = self.add("Newer", pygame.K_UP, "Up", "Select the next newer item", lambda: self.move(-1),
                              lambda: self.index > 0)
        self.older = self.add("Older", pygame.K_DOWN, "Down", "Select the next older item", lambda: self.move(1),
                              lambda: self.index < len(self.items) - 1)
        self.prev_sub = self.add(lambda: "< Scenario" if self.shows_table else "< Graph", pygame.K_LEFT, "Left",
                                 "Previous scenario or graph", lambda: self.step_sub(-1), lambda: self.sub_count > 1)
        self.next_sub = self.add(lambda: "Scenario >" if self.shows_table else "Graph >", pygame.K_RIGHT, "Right",
                                 "Next scenario or graph", lambda: self.step_sub(1), lambda: self.sub_count > 1)
        self.back_button = self.add("Back", pygame.K_b, "Esc", "Return to the main menu", self.back)

    # ---- data ---------------------------------------------------------------------------------------

    def on_enter(self) -> None:
        self.reload()
        if self.preselect is not None:
            for i, (_, path, _) in enumerate(self.items):
                if path == Path(self.preselect):
                    self.index = i
            self.load_item()

    def set_mode(self, mode: str) -> None:
        self.mode, self.index, self.sub = mode, 0, 0
        self.reload()

    def set_view(self, view: str) -> None:
        self.view, self.sub = view, 0

    def reload(self) -> None:
        paths = self.app.paths
        if self.mode == "experiments":
            self.items = [(self._label(e), e.path, e.problem) for e in list_experiments(paths.results_dir)]
        else:
            graphs = sorted((p for p in Path(paths.graph_dir).glob("*.png")), key=lambda p: p.name, reverse=True) \
                if Path(paths.graph_dir).is_dir() else []
            self.items = [(p.stem, p, "") for p in graphs]
        self.index = min(self.index, max(0, len(self.items) - 1))
        self.load_item()

    @staticmethod
    def _label(info: ExperimentInfo) -> str:
        return info.name.removeprefix("experiment_")

    def load_item(self) -> None:
        self.data, self.message, self.sub = None, "", 0
        if not self.items or self.mode != "experiments":
            return
        _, path, problem = self.items[self.index]
        if problem:
            self.message = f"This folder cannot be shown: {problem}."
            return
        try:
            self.data = read_experiment(path)
        except ValueError as exc:
            self.message = f"This folder cannot be shown: {exc}."

    def move(self, direction: int) -> None:
        self.index = max(0, min(len(self.items) - 1, self.index + direction))
        self.load_item()

    @property
    def shows_table(self) -> bool:
        return self.mode == "experiments" and self.view == "table"

    @property
    def sub_count(self) -> int:
        if not self.items:
            return 0
        if self.shows_table:
            return len(scenario_names(self.data)) if self.data else 0
        if self.mode == "experiments":
            return len(list_graphs(self.items[self.index][1]))
        return 0

    def step_sub(self, direction: int) -> None:
        count = self.sub_count
        if count:
            self.sub = (self.sub + direction) % count

    def on_click(self, pos: tuple[int, int]) -> bool:
        for i, rect in enumerate(self._row_rects):
            if rect.collidepoint(pos):
                self.index = self._first_visible + i
                self.load_item()
                return True
        return False

    # ---- drawing ---------------------------------------------------------------------------------------

    def layout(self, size: tuple[int, int]) -> None:
        s = self.s
        x, width = round(28 * s), round(330 * s)
        half = (width - round(8 * s)) // 2
        self.mode_buttons[0].rect = pygame.Rect(x, round(76 * s), half, round(38 * s))
        self.mode_buttons[1].rect = pygame.Rect(x + half + round(8 * s), round(76 * s), half, round(38 * s))
        bottom = size[1] - round(78 * s)
        self.back_button.rect = pygame.Rect(x, bottom, round(120 * s), round(46 * s))
        self.newer.rect = pygame.Rect(x + round(130 * s), bottom, round(100 * s), round(46 * s))
        self.older.rect = pygame.Rect(x + round(238 * s), bottom, round(92 * s), round(46 * s))
        rx = round(390 * s)
        bw = round(110 * s)
        self.table_button.rect = pygame.Rect(rx, round(76 * s), bw, round(38 * s))
        self.graphs_button.rect = pygame.Rect(rx + bw + round(8 * s), round(76 * s), bw, round(38 * s))
        right = size[0] - round(28 * s)
        nav_w = round(170 * s)
        second_row = right - (rx + 2 * bw + round(8 * s)) < 2 * nav_w + round(30 * s)
        nav_y = round(122 * s) if second_row else round(76 * s)
        self.pane_top = round(172 * s) if second_row else round(126 * s)
        self.next_sub.rect = pygame.Rect(right - nav_w, nav_y, nav_w, round(38 * s))
        self.prev_sub.rect = pygame.Rect(right - 2 * nav_w - round(8 * s), nav_y, nav_w, round(38 * s))

    def draw_content(self, surface: pygame.Surface) -> None:
        theme, fonts, s = self.theme, self.fonts, self.s
        for b in self.mode_buttons:  # show which mode is active by an outline
            active = (b is self.mode_buttons[0]) == (self.mode == "experiments")
            if active:
                pygame.draw.rect(surface, theme.accent, b.rect.inflate(6, 6), width=2, border_radius=8)
        if self.mode == "experiments" and self.view == "table":
            pygame.draw.rect(surface, theme.accent, self.table_button.rect.inflate(6, 6), width=2, border_radius=8)
        elif self.mode == "experiments":
            pygame.draw.rect(surface, theme.accent, self.graphs_button.rect.inflate(6, 6), width=2, border_radius=8)
        self._draw_list(surface)
        pane = pygame.Rect(round(390 * s), self.pane_top, self.size[0] - round(390 * s) - round(28 * s),
                           self.size[1] - self.pane_top - round(96 * s))
        if not self.items:
            text = ("No experiments saved yet. Open 'Run an experiment' in the menu." if self.mode == "experiments"
                    else "No training graphs yet. Train the agent first (they are saved when training ends).")
            for i, line in enumerate(wrap_text(fonts.body, text, pane.width)):
                draw_text(surface, line, fonts.body, theme.text_dim, (pane.x, pane.y + i * round(28 * s)))
            return
        if self.message:
            for i, line in enumerate(wrap_text(fonts.body, self.message, pane.width)):
                draw_text(surface, line, fonts.body, theme.warning, (pane.x, pane.y + i * round(28 * s)))
            return
        if self.mode == "training":
            self._draw_image(surface, pane, self.items[self.index][1])
        elif self.view == "table":
            self._draw_table(surface, pane)
        else:
            graphs = list_graphs(self.items[self.index][1])
            if graphs:
                self.sub %= len(graphs)
                self._draw_image(surface, pane, graphs[self.sub])
            else:
                draw_text(surface, "This experiment has no graphs (matplotlib was not installed).",
                          fonts.body, theme.text_dim, pane.topleft)

    def _draw_list(self, surface: pygame.Surface) -> None:
        theme, fonts, s = self.theme, self.fonts, self.s
        area = pygame.Rect(round(28 * s), round(126 * s), round(330 * s), self.size[1] - round(126 * s) - round(96 * s))
        pygame.draw.rect(surface, theme.panel, area, border_radius=8)
        pygame.draw.rect(surface, theme.panel_border, area, width=1, border_radius=8)
        row_h = round(30 * s)
        visible = max(1, (area.height - 12) // row_h)
        self._first_visible = max(0, min(self.index - visible // 2, len(self.items) - visible))
        self._row_rects = []
        for i in range(self._first_visible, min(len(self.items), self._first_visible + visible)):
            rect = pygame.Rect(area.x + 6, area.y + 6 + (i - self._first_visible) * row_h, area.width - 12, row_h - 2)
            self._row_rects.append(rect)
            if i == self.index:
                pygame.draw.rect(surface, theme.button_hover, rect, border_radius=5)
                pygame.draw.rect(surface, theme.accent, rect, width=1, border_radius=5)
            label = self.items[i][0]
            while fonts.small.size(label)[0] > rect.width - 12 and len(label) > 6:
                label = label[:-2]
            bad = bool(self.items[i][2])
            draw_text(surface, label, fonts.small, theme.warning if bad else theme.text, (rect.x + 8, rect.centery), "midleft")

    def _draw_table(self, surface: pygame.Surface, pane: pygame.Rect) -> None:
        theme, fonts, s = self.theme, self.fonts, self.s
        data = self.data
        names = scenario_names(data)
        self.sub %= len(names)
        view = scenario_view(data, names[self.sub])
        model = data.get("model")
        y = pane.y
        head = (f"Scenario {view.scenario} ({self.sub + 1}/{len(names)})   {data.get('runs_per_scenario')} runs   "
                f"base seed {data.get('base_seed')}   created {str(data.get('created', ''))[:16].replace('T', ' ')}")
        y = draw_text(surface, head, fonts.body, theme.text, (pane.x, y)).bottom + round(8 * s)
        header = ["Metric (mean +/- 95 % interval)"] + [LABELS[k] for k in view.controllers]
        y = draw_table(surface, pygame.Rect(pane.x, y, pane.width, 0), header,
                       [[r.label] + [r.cells[k] for k in view.controllers] for r in view.rows],
                       theme, fonts) + round(10 * s)
        for text in view.verdicts + view.notes + ([f"Model: trained {model['episodes_trained']} episodes"]
                                                  if model else []) + (["The experiment was stopped early."]
                                                                       if data.get("stopped_early") else []):
            for part in wrap_text(fonts.small, text, pane.width, 2):
                if y > pane.bottom - round(18 * s):
                    return
                y = draw_text(surface, part, fonts.small, theme.text_dim if "NO." not in part else theme.warning,
                              (pane.x, y)).bottom + 2

    def _draw_image(self, surface: pygame.Surface, pane: pygame.Rect, path: Path | None) -> None:
        theme, fonts, s = self.theme, self.fonts, self.s
        caption_h = round(26 * s)
        target = pygame.Rect(pane.x, pane.y, pane.width, pane.height - caption_h)
        key = (str(path), target.size)
        if self._image_cache is None or self._image_cache[0] != key:
            try:
                image = pygame.image.load(str(path))
                scale = min(target.width / image.get_width(), target.height / image.get_height(), 1.5)
                image = pygame.transform.smoothscale(
                    image, (max(1, round(image.get_width() * scale)), max(1, round(image.get_height() * scale))))
            except (pygame.error, FileNotFoundError, OSError) as exc:
                log.warning("Cannot show %s: %s", path, exc)
                image = None
            self._image_cache = (key, image)
        image = self._image_cache[1]
        if image is None:
            draw_text(surface, "This picture cannot be shown (file missing or damaged).", fonts.body,
                      theme.warning, target.topleft)
            return
        rect = image.get_rect(midtop=(target.centerx, target.y))
        pygame.draw.rect(surface, (252, 252, 251), rect.inflate(8, 8))
        surface.blit(image, rect)
        draw_text(surface, path.name if path else "", fonts.small, theme.text_dim, (pane.x, pane.bottom), "bottomleft")
