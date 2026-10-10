"""The settings screen: edit the common settings, validate them, save them."""

from __future__ import annotations

import pygame

from config.settings import ConfigError
from ui.app import Screen
from ui.components import draw_text, wrap_text
from ui.settings_form import PAGES, Field, SettingsForm
from ui.widgets import TextEntry


class SettingsScreen(Screen):
    name = "settings"
    heading = "Settings"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.form = SettingsForm(app.settings)
        self.page = next(iter(PAGES))
        self.editing: tuple[Field, TextEntry] | None = None
        self.rows: list[tuple[Field, pygame.Rect, pygame.Rect, pygame.Rect, pygame.Rect]] = []
        self.status = ""
        self.tabs = [self.add(name, None, "", f"Show the {name.lower()} settings", lambda n=name: self.set_page(n))
                     for name in PAGES]
        self.save_button = self.add("Save", pygame.K_s, "S", "Check the values and save them to the settings file",
                                    self.save, lambda: self.form.dirty or bool(self.form.messages))
        self.revert_button = self.add("Revert", pygame.K_r, "R", "Throw away unsaved changes",
                                      self.revert, lambda: self.form.dirty or bool(self.form.messages))
        self.defaults_button = self.add("Defaults", pygame.K_d, "D", "Put back the original values (then Save)",
                                        self.confirm_defaults)
        self.back_button = self.add("Back", pygame.K_b, "Esc", "Return to the main menu", self.back)

    # ---- actions ------------------------------------------------------------------------------------

    def set_page(self, name: str) -> None:
        self._finish_edit()
        self.page = name
        self.layout(self.size)

    def save(self) -> None:
        self._finish_edit()
        try:
            settings = self.form.save(self.app.paths.settings_file)
        except ConfigError as exc:
            self.status = "Not saved: " + " ".join(exc.problems)
            return
        self.app.apply_settings(settings)
        self.status = ""
        self.app.notify(f"Settings saved to {self.app.paths.settings_file}")

    def revert(self) -> None:
        self.editing = None
        self.form.revert()
        self.status = ""

    def confirm_defaults(self) -> None:
        self.ask("Put every setting back to its original value? Nothing is saved until you press Save.",
                 ("Use defaults", self._defaults), ("Cancel", lambda: None))

    def _defaults(self) -> None:
        self.editing = None
        self.form.reset_to_defaults()
        self.status = ""

    def request_leave(self, target: str) -> None:
        self._finish_edit()
        if not (self.form.dirty or self.form.messages):
            super().request_leave(target)
            return
        self.ask("You have unsaved changes. Leave without saving them?",
                 ("Discard changes", lambda: Screen.request_leave(self, target)),
                 ("Stay here", lambda: None))

    # ---- editing a number --------------------------------------------------------------------------------

    def _finish_edit(self) -> None:
        if self.editing is not None:
            field, entry = self.editing
            self.editing = None
            self.form.set_text(field, entry.text)

    def on_key(self, event: pygame.event.Event) -> bool:
        if self.editing is None:
            return False
        field, entry = self.editing
        result = entry.key(event)
        if result == "commit":
            self._finish_edit()
        elif result == "cancel":
            self.editing = None
        return True

    def on_click(self, pos: tuple[int, int]) -> bool:
        for field, _, minus, value, plus in self.rows:
            if minus.collidepoint(pos):
                self._finish_edit()
                self.form.adjust(field, -1)
                return True
            if plus.collidepoint(pos):
                self._finish_edit()
                self.form.adjust(field, 1)
                return True
            if value.collidepoint(pos):
                self._finish_edit()
                if field.kind in ("int", "float"):
                    self.editing = (field, TextEntry(f"{self.form.value(field):g}" if field.kind == "float"
                                                     else str(self.form.value(field)), "0123456789.-", 12))
                else:
                    self.form.adjust(field, 1)
                return True
        self._finish_edit()
        return False

    # ---- drawing --------------------------------------------------------------------------------------------

    def layout(self, size: tuple[int, int]) -> None:
        s = self.s
        x = round(28 * s)
        tab_w = round(140 * s)
        for i, tab in enumerate(self.tabs):
            tab.rect = pygame.Rect(x + i * (tab_w + round(8 * s)), round(76 * s), tab_w, round(38 * s))
        bottom = size[1] - round(78 * s)
        self.back_button.rect = pygame.Rect(x, bottom, round(130 * s), round(46 * s))
        self.save_button.rect = pygame.Rect(x + round(142 * s), bottom, round(130 * s), round(46 * s))
        self.revert_button.rect = pygame.Rect(x + round(284 * s), bottom, round(130 * s), round(46 * s))
        self.defaults_button.rect = pygame.Rect(x + round(426 * s), bottom, round(150 * s), round(46 * s))
        self.rows = []
        row_h, gap = round(44 * s), round(10 * s)
        y = round(132 * s)
        label_w = round(330 * s)
        box = round(36 * s)
        value_w = round(220 * s)
        for field in PAGES[self.page]:
            minus = pygame.Rect(x + label_w, y, box, row_h)
            value = pygame.Rect(minus.right + 4, y, value_w, row_h)
            plus = pygame.Rect(value.right + 4, y, box, row_h)
            self.rows.append((field, pygame.Rect(x, y, label_w, row_h), minus, value, plus))
            y += row_h + gap

    def draw_content(self, surface: pygame.Surface) -> None:
        theme, fonts, s = self.theme, self.fonts, self.s
        for tab in self.tabs:
            if tab.label == self.page:
                pygame.draw.rect(surface, theme.accent, tab.rect.inflate(6, 6), width=2, border_radius=8)
        hint = ""
        for field, label, minus, value, plus in self.rows:
            draw_text(surface, field.label, fonts.body, theme.text, (label.x, label.centery), "midleft")
            error = field.key in self.form.messages
            for rect, text in ((minus, "<" if field.kind != "float" and field.kind != "int" else "-"),
                               (plus, ">" if field.kind != "float" and field.kind != "int" else "+")):
                hot = self.hover is not None and rect.collidepoint(self.hover)
                pygame.draw.rect(surface, theme.button_hover if hot else theme.button, rect, border_radius=6)
                pygame.draw.rect(surface, theme.panel_border, rect, width=1, border_radius=6)
                draw_text(surface, text, fonts.strong, theme.button_text, rect.center, "center")
            editing = self.editing is not None and self.editing[0] is field
            pygame.draw.rect(surface, theme.panel, value)
            pygame.draw.rect(surface, theme.warning if error else (theme.accent if editing else theme.panel_border),
                             value, width=2 if editing or error else 1)
            shown = self.editing[1].text + "|" if editing else self.form.text(field)
            draw_text(surface, shown, fonts.strong, theme.text, value.center, "center")
            if self.hover is not None and (label.collidepoint(self.hover) or value.collidepoint(self.hover)):
                hint = field.help
        right = self.rows[-1][4].right + round(30 * s) if self.rows else round(700 * s)
        width = self.size[0] - right - round(28 * s)
        y = round(132 * s)
        problems = self.form.problems()
        if width > round(200 * s):
            if problems:
                y = draw_text(surface, "Needs fixing before saving:", fonts.strong, theme.warning, (right, y)).bottom + 4
                for problem in problems[:8]:
                    for line in wrap_text(fonts.small, problem, width, 3):
                        y = draw_text(surface, line, fonts.small, theme.warning, (right, y)).bottom + 2
                    y += 4
            elif self.form.dirty:
                draw_text(surface, "Unsaved changes. Press Save.", fonts.body, theme.text_dim, (right, y))
            else:
                draw_text(surface, "All values are valid and saved.", fonts.body, theme.good, (right, y))
        base = self.rows[-1][1].bottom + round(24 * s) if self.rows else round(300 * s)
        if hint:
            for line in wrap_text(fonts.body, hint, round(660 * s), 3):
                base = draw_text(surface, line, fonts.body, theme.text_dim, (round(28 * s), base)).bottom + 2
        if self.status:
            for line in wrap_text(fonts.body, self.status, self.size[0] - round(56 * s), 3):
                base = draw_text(surface, line, fonts.body, theme.warning, (round(28 * s), base + 4)).bottom
