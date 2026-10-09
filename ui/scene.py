"""Draws the intersection, the vehicles and the signals with pygame.

The road layout never changes while the program runs, so it is drawn once into a
background picture; each frame only the vehicles, signals and labels are drawn on
top of a copy of it.
"""

from __future__ import annotations

import pygame

from config.settings import Settings
from environment.enums import ALL_DIRECTIONS, Direction, LightStage, SignalColor
from ui.components import Fonts, draw_text
from ui.geometry import (
    RoadLayout,
    ViewTransform,
    fit_view,
    heading,
    lane_side,
    right_of,
)
from ui.snapshot import Snapshot, VehicleView
from ui.theme import Theme, blend

# Vehicles fade into the road over this many metres before the end of the exit road,
# so they do not simply vanish in the middle of the picture.
_FADE_METRES = 18.0

_SIGNAL_TEXT = {SignalColor.RED: "RED", SignalColor.YELLOW: "YELLOW", SignalColor.GREEN: "GREEN"}


class SceneRenderer:
    """Draws the road scene into a rectangle of a given size."""

    def __init__(self, settings: Settings, theme: Theme, fonts: Fonts) -> None:
        self.settings = settings
        self.theme = theme
        self.fonts = fonts
        self.layout = RoadLayout.from_settings(settings)
        self.view_range = settings.display.view_range
        self._size = (0, 0)
        self._view: ViewTransform | None = None
        self._background: pygame.Surface | None = None

    # ---- setup -----------------------------------------------------------------------

    @property
    def view(self) -> ViewTransform:
        if self._view is None:
            raise RuntimeError("draw() must be called before the view exists")
        return self._view

    def _prepare(self, size: tuple[int, int]) -> None:
        """(Re)build the view and the background if the size changed."""
        if size == self._size and self._background is not None:
            return
        self._size = size
        self._view = fit_view(size[0], size[1], self.layout.half_extent(self.view_range))
        self._background = self._build_background(size)

    # ---- the static picture ---------------------------------------------------------------

    def _px(self, direction: Direction, d: float, lateral: float = 0.0) -> tuple[float, float]:
        return self.view.to_px(self.layout.point(direction, d, lateral))

    def _build_background(self, size: tuple[int, int]) -> pygame.Surface:
        theme, layout, view = self.theme, self.layout, self.view
        surface = pygame.Surface(size)
        surface.fill(theme.ground)
        width, height = size
        cx, cy = view.centre
        road = max(1, round(layout.road_half_width * view.scale))
        box = round(layout.box_half * view.scale)

        # the two roads and the crossing
        pygame.draw.rect(surface, theme.road, (0, cy - road, width, 2 * road))
        pygame.draw.rect(surface, theme.road, (cx - road, 0, 2 * road, height))
        pygame.draw.rect(surface, theme.box, (cx - box, cy - box, 2 * box, 2 * box))

        # edge lines and the dashed centre line, outside the crossing only
        edge = blend(theme.road, theme.lane_marking, 0.55)
        for sign in (-1, 1):
            pygame.draw.line(surface, edge, (0, cy + sign * (road - 1)), (cx - box, cy + sign * (road - 1)))
            pygame.draw.line(surface, edge, (cx + box, cy + sign * (road - 1)), (width, cy + sign * (road - 1)))
            pygame.draw.line(surface, edge, (cx + sign * (road - 1), 0), (cx + sign * (road - 1), cy - box))
            pygame.draw.line(surface, edge, (cx + sign * (road - 1), cy + box), (cx + sign * (road - 1), height))
        self._dashes(surface, theme.lane_marking, vertical=True, start=cy + box, stop=height, centre=cx)
        self._dashes(surface, theme.lane_marking, vertical=True, start=cy - box, stop=0, centre=cx)
        self._dashes(surface, theme.lane_marking, vertical=False, start=cx + box, stop=width, centre=cy)
        self._dashes(surface, theme.lane_marking, vertical=False, start=cx - box, stop=0, centre=cy)

        # stop lines across the incoming lane of each road
        thickness = max(3, round(0.7 * view.scale))
        for direction in ALL_DIRECTIONS:
            inner = self._px(direction, -layout.box_half, 0.0)
            outer = self._px(direction, -layout.box_half, layout.lane_width)
            pygame.draw.line(surface, theme.stop_line, inner, outer, thickness)
        return surface

    def _dashes(self, surface: pygame.Surface, color, vertical: bool, start: float,
                stop: float, centre: float) -> None:
        dash = max(4, round(3.0 * self.view.scale))
        step = 2 * dash
        direction = 1 if stop > start else -1
        position = start + direction * dash // 2
        while (position - stop) * direction < 0:
            end = position + direction * dash
            end = min(end, stop) if direction > 0 else max(end, stop)
            if vertical:
                pygame.draw.line(surface, color, (centre, position), (centre, end), 2)
            else:
                pygame.draw.line(surface, color, (position, centre), (end, centre), 2)
            position += direction * step

    # ---- each frame --------------------------------------------------------------------------

    def draw(self, target: pygame.Surface, rect: pygame.Rect, vehicles: list[VehicleView],
             state: Snapshot) -> None:
        """Draw one frame of the scene into ``rect`` of ``target``."""
        self._prepare((rect.width, rect.height))
        assert self._background is not None
        surface = target.subsurface(rect)
        surface.blit(self._background, (0, 0))
        for vehicle in sorted(vehicles, key=lambda v: v.id):
            self._draw_vehicle(surface, vehicle)
        for direction in ALL_DIRECTIONS:
            self._draw_signal(surface, direction, state.signals[direction])
            self._draw_road_label(surface, direction, state, vehicles)

    def _draw_vehicle(self, surface: pygame.Surface, vehicle: VehicleView) -> None:
        theme, layout, view = self.theme, self.layout, self.view
        corners = [view.to_px(p) for p in layout.vehicle_corners(
            vehicle.direction, vehicle.position, vehicle.length)]
        xs, ys = [p[0] for p in corners], [p[1] for p in corners]
        if max(xs) < 0 or min(xs) > self._size[0] or max(ys) < 0 or min(ys) > self._size[1]:
            return
        body = theme.vehicle_waiting if vehicle.waiting else theme.vehicle_moving
        glass, outline = theme.windshield, theme.vehicle_outline
        fade = (layout.d_of(vehicle.position) - vehicle.length / 2
                - (layout.box_half + layout.exit_length - _FADE_METRES)) / _FADE_METRES
        if fade > 0:
            body, glass, outline = (blend(c, theme.road, fade) for c in (body, glass, outline))
        pygame.draw.polygon(surface, body, corners)
        pygame.draw.polygon(surface, glass, [view.to_px(p) for p in layout.windshield_corners(
            vehicle.direction, vehicle.position, vehicle.length)])
        pygame.draw.polygon(surface, outline, corners, 1)

    def _draw_signal(self, surface: pygame.Surface, direction: Direction, signal: SignalColor) -> None:
        theme, layout, view = self.theme, self.layout, self.view
        radius = max(5, round(1.1 * view.scale))
        gap = max(2, radius // 3)
        cross = 2 * radius + 8  # size across the road
        along = 3 * 2 * radius + 2 * gap + 8  # size along the road
        vertical_road = heading(direction)[0] == 0
        width, height = (cross, along) if vertical_road else (along, cross)

        lateral = layout.lane_width + (cross / 2 + 7) / view.scale
        cx, cy = self._px(direction, -layout.box_half - (along / 2 + 10) / view.scale, lateral)
        housing = pygame.Rect(0, 0, width, height)
        housing.center = (round(cx), round(cy))
        pygame.draw.rect(surface, theme.signal_housing, housing, border_radius=5)
        pygame.draw.rect(surface, theme.panel_border, housing, width=1, border_radius=5)

        lamps = ((SignalColor.RED, theme.red), (SignalColor.YELLOW, theme.yellow),
                 (SignalColor.GREEN, theme.green))
        for index, (lamp, color) in enumerate(lamps):
            offset = (index - 1) * (2 * radius + gap)
            centre = (housing.centerx, housing.centery + offset) if vertical_road else (
                housing.centerx + offset, housing.centery)
            lit = lamp is signal
            if lit:
                pygame.draw.circle(surface, blend(theme.signal_housing, color, 0.35), centre, radius + 3)
            pygame.draw.circle(surface, color if lit else theme.lamp_off, centre, radius)

        # the colour's name, so the signal never relies on colour alone
        outward = self._outward(direction)
        colour = {SignalColor.RED: theme.red, SignalColor.YELLOW: theme.yellow,
                  SignalColor.GREEN: theme.green}[signal]
        font = self.fonts.get(22, bold=True)
        text = _SIGNAL_TEXT[signal]
        if vertical_road:
            anchor = "midleft" if outward[0] > 0 else "midright"
            pos = (housing.right + 6, housing.centery) if outward[0] > 0 else (housing.left - 6, housing.centery)
        else:
            anchor = "midtop" if outward[1] > 0 else "midbottom"
            pos = (housing.centerx, housing.bottom + 4) if outward[1] > 0 else (housing.centerx, housing.top - 4)
        draw_text(surface, text, font, colour, pos, anchor)

    def _outward(self, direction: Direction) -> tuple[float, float]:
        """Unit vector pointing from the road's centre line out towards the verge on the
        side this direction's vehicles drive on."""
        rx, ry = right_of(heading(direction))
        side = lane_side(self.layout.drive_on)
        return (rx * side, ry * side)

    def _draw_road_label(self, surface: pygame.Surface, direction: Direction, state: Snapshot,
                         vehicles: list[VehicleView]) -> None:
        theme, layout, view = self.theme, self.layout, self.view
        edge = view.visible_distance(direction)  # metres from the centre to the picture's edge
        hidden = state.outside[direction] + sum(
            1 for v in state.vehicles.values()
            if v.direction is direction and layout.d_of(v.position) < -edge)
        lines = [(direction.label.upper(), self.fonts.get(26, bold=True), theme.accent),
                 (f"queue {state.queues[direction]}", self.fonts.get(24), theme.text)]
        if hidden:
            lines.append((f"+{hidden} further out", self.fonts.get(20), theme.text_dim))

        # sits on the verge beside the road, at the far end of the picture
        margin = 10
        outward = self._outward(direction)
        cx, cy = self._px(direction, -edge + 2.0, layout.lane_width + 1.5)
        heights = [font.get_height() for _, font, _ in lines]
        block_h = sum(heights)
        block_w = max(font.size(text)[0] for text, font, _ in lines)
        vertical_road = heading(direction)[0] == 0
        if vertical_road:
            x = cx + margin if outward[0] > 0 else cx - margin - block_w
            y = cy if heading(direction)[1] > 0 else cy - block_h
        else:
            x = cx if heading(direction)[0] < 0 else cx
            y = cy + margin if outward[1] > 0 else cy - margin - block_h
            x = x - block_w if heading(direction)[0] < 0 else x
        x = max(4, min(x, self._size[0] - block_w - 4))
        y = max(4, min(y, self._size[1] - block_h - 4))
        right_aligned = vertical_road and outward[0] < 0
        for (text, font, color), height in zip(lines, heights):
            if right_aligned:
                draw_text(surface, text, font, color, (x + block_w, y), "topright")
            else:
                draw_text(surface, text, font, color, (x, y), "topleft")
            y += height

    def stage_text(self, state: Snapshot) -> str:
        """A short description of the light, for the side panel."""
        if state.stage is LightStage.ALL_RED:
            return "ALL RED"
        return f"{state.phase.value} {state.stage.value}"
