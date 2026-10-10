"""Running an experiment from the window: fixed-time vs tuned fixed-time vs Q-Learning."""

from __future__ import annotations

from pathlib import Path

import pygame

from evaluation.experiment import MAX_RUNS, run_experiment
from evaluation.export import save_experiment
from ui.app import Screen
from ui.components import draw_text, wrap_text
from ui.jobs import ACTIVE_STATES, DONE, FAILED, STOPPED, BackgroundJob
from ui.screens._common import ScenarioChoice
from ui.widgets import NumberBox, draw_progress, format_duration


class ExperimentScreen(Screen):
    name = "experiment"
    heading = "Run an experiment"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.job: BackgroundJob | None = None
        self.problem = ""
        self.use_tuned = True
        self.use_rl = app.model_status()[0] == "ok"
        self.leave_target: str | None = None
        self.saved_folder: Path | None = None
        self._announced = False
        self.runs = NumberBox("Runs", 10, 1, MAX_RUNS, 5)
        idle = lambda: not self.running  # noqa: E731
        self.scenarios = ScenarioChoice(self, [app.settings.traffic.scenario], idle)
        self.tuned_button = self.add(lambda: f"Tuned fixed-time: {'on' if self.use_tuned else 'off'}", None, "",
                                     "A fairer baseline: green times searched on separate traffic",
                                     lambda: setattr(self, "use_tuned", not self.use_tuned), idle)
        self.rl_button = self.add(lambda: f"Q-Learning agent: {'on' if self.use_rl else 'off'}", None, "",
                                  "Include the trained agent (needs a model)",
                                  lambda: setattr(self, "use_rl", not self.use_rl),
                                  lambda: not self.running and app.model_status()[0] == "ok")
        self.start = self.add("Start experiment", pygame.K_RETURN, "Enter", "Run all controllers on the same traffic",
                              self.begin, idle)
        self.stop = self.add("Stop", pygame.K_s, "S", "Stop after the current run (runs finished by every controller are kept)",
                             self.stop_job, lambda: self.running and self.job.state != "stopping")
        self.view = self.add("View results", pygame.K_v, "V", "Open the saved results",
                             lambda: self.request_leave("results"), lambda: self.saved_folder is not None)
        self.back_button = self.add("Back", pygame.K_b, "Esc", "Return to the main menu", self.back)

    @property
    def running(self) -> bool:
        return self.job is not None and self.job.state in ACTIVE_STATES

    def close(self) -> None:
        if self.job is not None and self.job.active:
            self.job.request_stop()

    def stop_job(self) -> None:
        if self.job is not None:
            self.job.request_stop()

    def begin(self) -> None:
        self.runs.commit()
        self.problem = self.runs.error
        if self.problem:
            return
        names = self.scenarios.names
        if not names:
            self.problem = "Choose at least one scenario."
            return
        use_rl = self.use_rl and self.app.model_status()[0] == "ok"
        agent = self.app.load_agent() if use_rl else None
        if use_rl and agent is None:
            self.problem = self.app.model_status()[1]
            return
        settings, paths, runs, tune = self.app.settings, self.app.paths, self.runs.value, self.use_tuned
        self.saved_folder, self._announced = None, False

        def work(job: BackgroundJob):
            result = run_experiment(
                settings, names, runs=runs, agent=agent, tune=tune,
                on_progress=lambda done, total, text: job.report(done, total, text),
                should_stop=job.should_stop)
            if not result.scenarios:
                return None  # stopped before every controller finished a run: nothing to compare
            try:
                folder = save_experiment(result, paths.results_dir, graphs=True)
            except ImportError:
                folder = save_experiment(result, paths.results_dir, graphs=False)
            return folder, result

        self.job = BackgroundJob("experiment", work)
        self.job.start()

    def request_leave(self, target: str) -> None:
        if not self.running:
            self._go(target)
            return
        self.ask("An experiment is still running. Stop it now? Runs that every controller already finished are saved.",
                 ("Stop", lambda: self._stop_then(target)), ("Keep running", lambda: None))

    def _stop_then(self, target: str) -> None:
        self.leave_target = target
        self.stop_job()

    def update(self, seconds: float) -> None:
        job = self.job
        if job is not None and job.state in (DONE, STOPPED, FAILED) and not self._announced:
            self._announced = True
            if job.state == FAILED:
                self.problem = job.error or "The experiment failed."
                self.app.notify("The experiment failed - see the message on screen.", "warning")
            elif job.result is None:
                self.app.notify("Stopped before every controller finished a run; nothing was saved.")
            else:
                self.saved_folder = job.result[0]
                self.app.notify("Experiment saved." if job.state == DONE else "Experiment stopped; partial results saved.")
        if self.leave_target and job is not None and job.finished:
            target, self.leave_target = self.leave_target, None
            self._go(target)

    def _go(self, target: str) -> None:
        if target == "results" and self.saved_folder is not None:
            self.app.go("results", folder=self.saved_folder)
        else:
            super().request_leave(target)

    def on_key(self, event: pygame.event.Event) -> bool:
        return self.runs.key(event) if self.runs.editing else False

    def on_click(self, pos: tuple[int, int]) -> bool:
        return (not self.running) and self.runs.click(pos)

    def layout(self, size: tuple[int, int]) -> None:
        s = self.s
        x, width = round(28 * s), round(330 * s)
        y = round(100 * s)
        self.runs.rect = pygame.Rect(x, y, width, round(40 * s))
        y = self.scenarios.layout(x, y + round(78 * s), width, s) + round(8 * s)
        for button in (self.tuned_button, self.rl_button):
            button.rect = pygame.Rect(x, y, width, round(38 * s))
            y += round(46 * s)
        y += round(6 * s)
        self.start.rect = pygame.Rect(x, y, width, round(48 * s))
        y += round(56 * s)
        self.stop.rect = pygame.Rect(x, y, width, round(42 * s))
        bottom = size[1] - round(78 * s)
        self.back_button.rect = pygame.Rect(x, bottom, round(160 * s), round(46 * s))
        self.view.rect = pygame.Rect(x + round(172 * s), bottom, round(200 * s), round(46 * s))

    def draw_content(self, surface: pygame.Surface) -> None:
        theme, fonts, s = self.theme, self.fonts, self.s
        self.runs.enabled = not self.running
        draw_text(surface, "Runs per controller and scenario", fonts.small, theme.text_dim,
                  (self.runs.rect.x, self.runs.rect.y - round(22 * s)))
        self.runs.draw(surface, theme, fonts, self.hover)
        draw_text(surface, "Scenarios to test", fonts.small, theme.text_dim,
                  (self.runs.rect.x, self.runs.rect.bottom + round(10 * s)))
        x, width = round(390 * s), self.size[0] - round(390 * s) - round(28 * s)
        y = round(90 * s)
        job = self.job
        if job is None:
            text = ("An experiment runs every controller on exactly the same traffic (same seeds) and compares "
                    "them with confidence intervals. More runs give more reliable answers but take longer: "
                    "10 runs on one scenario takes about a minute; all 7 scenarios with 20 runs takes several minutes. "
                    "Results are saved in the results folder and can be opened with View results.")
            for line in wrap_text(fonts.body, text, width):
                y = draw_text(surface, line, fonts.body, theme.text_dim, (x, y)).bottom + 3
            if self.use_rl:
                agent_note = self._scenario_note()
                if agent_note:
                    y += round(10 * s)
                    for line in wrap_text(fonts.small, agent_note, width):
                        y = draw_text(surface, line, fonts.small, theme.warning, (x, y)).bottom + 2
        else:
            done, total, text = job.progress
            draw_text(surface, text or "Starting...", fonts.body, theme.text, (x, y))
            y += round(30 * s)
            draw_progress(surface, pygame.Rect(x, y, width, round(14 * s)), job.fraction, theme)
            y += round(24 * s)
            eta = f"   time left about {format_duration(job.eta_seconds)}" if job.eta_seconds else ""
            draw_text(surface, f"{job.state.capitalize()}   {done}/{total} runs   elapsed {format_duration(job.elapsed)}{eta}",
                      fonts.small, theme.text_dim, (x, y))
            y += round(34 * s)
            if self.saved_folder is not None:
                result = job.result[1]
                lines = [f"Saved to {self.saved_folder}",
                         f"{result.runs} runs per controller, {len(result.scenarios)} scenario(s), "
                         f"{format_duration(result.seconds)}."]
                if result.stopped_early:
                    lines.append("Stopped early: some runs are missing.")
                for line in lines:
                    for part in wrap_text(fonts.small, line, width):
                        y = draw_text(surface, part, fonts.small, theme.good, (x, y)).bottom + 2
        if self.problem:
            for part in wrap_text(fonts.body, self.problem, width, 4):
                y = draw_text(surface, part, fonts.body, theme.warning, (x, y + 6)).bottom

    def _scenario_note(self) -> str:
        agent, _ = self.app._load_model()
        trained = (agent.info.get("training", {}) or {}).get("scenarios") if agent and agent.info else None
        outside = [n for n in self.scenarios.names if trained and n not in trained]
        if outside:
            return (f"The model was trained on {', '.join(trained)}, not on {', '.join(outside)}; "
                    "the agent may do worse there.")
        return ""
