"""Training the Q-Learning agent from the window."""

from __future__ import annotations

import pygame

from training.trainer import EpisodeStats, rolling_mean
from training.workflow import MAX_EPISODES, TrainingOutcome, TrainingPlan, run_training
from ui.app import Screen
from ui.components import draw_text, wrap_text
from ui.jobs import ACTIVE_STATES, DONE, FAILED, PAUSED, STOPPED, BackgroundJob
from ui.screens._common import ScenarioChoice
from ui.widgets import NumberBox, draw_line_chart, draw_progress, format_duration


class TrainingScreen(Screen):
    name = "training"
    heading = "Train the agent"

    def __init__(self, app) -> None:
        super().__init__(app)
        settings = app.settings
        self.job: BackgroundJob | None = None
        self.history: list[EpisodeStats] = []
        self.trainers: list = []
        self.problem = ""
        self.continue_training = False
        self.leave_target: str | None = None
        self.episodes = NumberBox("Episodes", min(max(settings.rl.episodes, 1), MAX_EPISODES), 1, MAX_EPISODES, 50)
        idle = lambda: not self.running  # noqa: E731
        self.scenarios = ScenarioChoice(self, [settings.traffic.scenario], idle)
        self.mode = self.add(lambda: "Continue the saved model" if self.continue_training else "Train a new model",
                             None, "", "Switch between a fresh agent and continuing the saved model",
                             self.toggle_mode, lambda: not self.running and app.model_status()[0] == "ok")
        self.start = self.add("Start training", pygame.K_RETURN, "Enter", "Begin training with these options",
                              self.begin, idle)
        self.pause = self.add(lambda: "Resume" if self.job and self.job.state == PAUSED else "Pause",
                              pygame.K_SPACE, "Space", "Pause or resume training", self.toggle_pause,
                              lambda: self.running)
        self.stop = self.add("Stop and save", pygame.K_s, "S", "Stop after the current episode and save the model",
                             self.stop_job, lambda: self.running and self.job.state != "stopping")
        self.watch = self.add("Watch trained agent", pygame.K_w, "W", "Open the simulation with the saved agent",
                              lambda: self.request_leave("watch_rl"), lambda: app.model_status()[0] == "ok")
        self.delete_model = self.add("Delete model", None, "", "Delete the saved model file (asks first)",
                                     self.confirm_delete_model,
                                     lambda: not self.running and app.paths.model_path.exists())
        self.back_button = self.add("Back", pygame.K_b, "Esc", "Return to the main menu", self.back)
        self._announced = False
        self._series_len = -1
        self._series: list = []

    # ---- state ----------------------------------------------------------------------------------

    @property
    def running(self) -> bool:
        return self.job is not None and self.job.state in ACTIVE_STATES

    def confirm_delete_model(self) -> None:
        self.ask(f"Delete the saved model ({self.app.paths.model_path.name})? You would have to train again "
                 "before the agent can be watched or tested. This cannot be undone.",
                 ("Delete model", self._delete_model), ("Keep it", lambda: None))

    def _delete_model(self) -> None:
        try:
            self.app.paths.model_path.unlink()
        except OSError as exc:
            self.problem = f"The model could not be deleted: {exc.strerror or exc}."
            return
        self.continue_training = False
        self.app._model_cache = None
        self.app.notify("The saved model was deleted.")

    def toggle_mode(self) -> None:
        self.continue_training = not self.continue_training

    def toggle_pause(self) -> None:
        if self.job is None:
            return
        if self.job.state == PAUSED:
            self.job.resume()
        else:
            self.job.pause()

    def close(self) -> None:
        if self.job is not None and self.job.active:
            self.job.request_stop()

    def stop_job(self) -> None:
        if self.job is not None:
            self.job.request_stop()

    def begin(self) -> None:
        self.episodes.commit()
        self.problem = self.episodes.error
        if self.problem:
            return
        plan = TrainingPlan(self.app.settings, self.scenarios.names, self.episodes.value,
                            self.app.paths.model_path, continue_training=self.continue_training)
        problems = plan.problems()
        if problems:
            self.problem = " ".join(problems)
            return
        if plan.would_replace_model:
            self.ask("A trained model already exists and will be replaced by this training. Replace it?",
                     ("Replace model", lambda: self._launch(plan, True)),
                     ("Cancel", lambda: None))
        else:
            self._launch(plan, False)

    def _launch(self, plan: TrainingPlan, replace: bool) -> None:
        plan.replace_existing = replace
        self.history, self.trainers, self.problem = [], [], ""
        self._announced = False
        paths = self.app.paths

        def work(job: BackgroundJob) -> TrainingOutcome:
            def on_episode(stats: EpisodeStats, total: int) -> None:
                self.history.append(stats)
                job.report(stats.episode, total,
                           f"Episode {stats.episode} of {total}   epsilon {stats.epsilon:.3f}")
            return run_training(plan, paths.csv_dir, paths.graph_dir, on_episode=on_episode,
                                trainer_out=self.trainers, should_stop=job.should_stop,
                                wait_if_paused=job.wait_if_paused)

        self.job = BackgroundJob("training", work)
        self.job.start()

    # ---- leaving ----------------------------------------------------------------------------------

    def request_leave(self, target: str) -> None:
        if not self.running:
            super().request_leave(target)
            return
        self.ask("Training is still running. Stop it now and save what the agent has learned so far?",
                 ("Stop and save", lambda: self._stop_then(target)),
                 ("Keep training", lambda: None))

    def _stop_then(self, target: str) -> None:
        self.leave_target = target
        self.stop_job()

    def update(self, seconds: float) -> None:
        job = self.job
        if job is not None and job.state in (DONE, STOPPED, FAILED) and not self._announced:
            self._announced = True
            if job.state == FAILED:
                self.problem = job.error or "Training failed."
                self.app.notify("Training failed - see the message on screen.", "warning")
            else:
                outcome = job.result
                self.app.notify("Training stopped; model saved." if outcome and outcome.stopped_early and outcome.saved
                                else "Training finished; model saved." if outcome and outcome.saved
                                else "Training stopped before any episode finished; nothing was saved.")
        if self.leave_target and job is not None and job.finished:
            target, self.leave_target = self.leave_target, None
            super().request_leave(target)

    # ---- drawing ------------------------------------------------------------------------------------

    def on_key(self, event: pygame.event.Event) -> bool:
        if self.episodes.editing:
            return self.episodes.key(event)
        return False

    def on_click(self, pos: tuple[int, int]) -> bool:
        if self.running:
            return False
        self.episodes.enabled = True
        return self.episodes.click(pos)

    def layout(self, size: tuple[int, int]) -> None:
        s = self.s
        x, width = round(28 * s), round(330 * s)
        y = round(100 * s)
        self.episodes.rect = pygame.Rect(x, y, width, round(40 * s))
        y = self.scenarios.layout(x, y + round(78 * s), width, s) + round(8 * s)
        self.mode.rect = pygame.Rect(x, y, width, round(40 * s))
        y += round(52 * s)
        self.start.rect = pygame.Rect(x, y, width, round(48 * s))
        y += round(56 * s)
        half = (width - round(8 * s)) // 2
        self.pause.rect = pygame.Rect(x, y, half, round(42 * s))
        self.stop.rect = pygame.Rect(x + half + round(8 * s), y, half, round(42 * s))
        bottom = size[1] - round(78 * s)
        self.back_button.rect = pygame.Rect(x, bottom, round(160 * s), round(46 * s))
        self.watch.rect = pygame.Rect(x + round(172 * s), bottom, round(250 * s), round(46 * s))
        self.delete_model.rect = pygame.Rect(x + round(434 * s), bottom, round(190 * s), round(46 * s))

    def _chart_series(self):
        if len(self.history) != self._series_len:
            self._series_len = len(self.history)
            window = max(1, min(25, len(self.history) // 10 or 1))
            self._series = (rolling_mean([h.total_reward for h in self.history], window),
                            rolling_mean([h.average_waiting_time for h in self.history], window))
        return self._series

    def draw_content(self, surface: pygame.Surface) -> None:
        theme, fonts, s = self.theme, self.fonts, self.s
        self.episodes.enabled = not self.running
        draw_text(surface, "Episodes (practice runs)", fonts.small, theme.text_dim,
                  (self.episodes.rect.x, self.episodes.rect.y - round(22 * s)))
        self.episodes.draw(surface, theme, fonts, self.hover)
        draw_text(surface, "Train on these traffic scenarios", fonts.small, theme.text_dim,
                  (self.episodes.rect.x, self.episodes.rect.bottom + round(10 * s)))
        right = pygame.Rect(round(390 * s), round(86 * s), self.size[0] - round(390 * s) - round(28 * s), 0)
        right.height = self.size[1] - right.y - round(96 * s)
        y = right.y
        job = self.job
        if job is None:
            text = ("Training makes the agent practise on simulated traffic. It tries actions, sees the reward, "
                    "and gradually learns which situations call for switching. The best policy found is saved "
                    "to the model file. Choose the options on the left and press Start.")
            for line in wrap_text(fonts.body, text, right.width):
                y = draw_text(surface, line, fonts.body, theme.text_dim, (right.x, y)).bottom + 3
        else:
            done, total, text = job.progress
            draw_text(surface, text or "Starting...", fonts.body, theme.text, (right.x, y))
            y += round(30 * s)
            draw_progress(surface, pygame.Rect(right.x, y, right.width, round(14 * s)), job.fraction, theme)
            y += round(24 * s)
            state = {"running": "Running", "paused": "Paused", "stopping": "Stopping...", "done": "Finished",
                     "stopped": "Stopped", "failed": "Failed"}.get(job.state, job.state)
            eta = f"   time left about {format_duration(job.eta_seconds)}" if job.eta_seconds else ""
            draw_text(surface, f"{state}   elapsed {format_duration(job.elapsed)}{eta}", fonts.small,
                      theme.text_dim, (right.x, y))
            y += round(30 * s)
            reward, wait = self._chart_series()
            half = (right.width - round(12 * s)) // 2
            height = min(round(260 * s), right.bottom - y - round(110 * s))
            if height > 120:
                draw_line_chart(surface, pygame.Rect(right.x, y, half, height),
                                [("reward", theme.accent, reward)], theme, fonts, "Reward per episode", "Reward")
                draw_line_chart(surface, pygame.Rect(right.x + half + round(12 * s), y, half, height),
                                [("wait", theme.warning, wait)], theme, fonts, "Waiting time (s)", "Seconds")
                y += height + round(10 * s)
            last = self.history[-1] if self.history else None
            if last is not None:
                best = [h for h in self.history if h.validation_waiting_time is not None]
                line = f"Episodes {len(self.history)}   safety conflicts {sum(h.safety_violations for h in self.history)}"
                if best:
                    line += f"   best check so far {min(h.validation_waiting_time for h in best):.1f} s average wait"
                y = draw_text(surface, line, fonts.small, theme.text_dim, (right.x, y)).bottom + 4
            if job.state in (DONE, STOPPED) and isinstance(job.result, TrainingOutcome):
                o = job.result
                lines = [f"{o.episodes_done} episodes in {format_duration(o.seconds)}.",
                         (f"Kept the best policy (episode {o.best_episode}, validation wait {o.best_score:.1f} s)."
                          if o.best_episode is not None else ""),
                         (f"Model saved to {o.model_path}" if o.saved else "Nothing saved."),
                         f"Safety check: {'PASSED' if o.safe else 'FAILED'}",
                         o.graph_note or (f"{len(o.graph_files)} graph(s) saved in {self.app.paths.graph_dir}"
                                          if o.graph_files else "")]
                for line in filter(None, lines):
                    for part in wrap_text(fonts.small, line, right.width):
                        y = draw_text(surface, part, fonts.small, theme.good, (right.x, y)).bottom + 2
        if self.problem:
            for part in wrap_text(fonts.body, self.problem, right.width, 4):
                y = draw_text(surface, part, fonts.body, theme.warning, (right.x, y + 4)).bottom
