"""The documentation must describe what the program really does.

These tests read the Markdown files and check them against the code: every command-line option, scenario, setting,
file and link they mention must exist, the settings table of the user guide must show the real defaults, and the quoted
number of automated tests must be true.  When code changes and the docs are forgotten, one of these fails.
"""

import os
import re
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

ROOT = Path(__file__).resolve().parent.parent
DOC_FILES = sorted([ROOT / "README.md", *(ROOT / "docs").glob("*.md")])
CODE_DIRS = ("agents", "config", "controllers", "docs", "environment", "evaluation", "simulation",
             "training", "ui", "utils", "tests")
SECTIONS = ("simulation", "lights", "fixed", "traffic", "rl", "display")

#: Phrases that mean "this is not built yet" and are therefore wrong in a finished phase.
STALE_PHRASES = ("later phase", "learns yet", "arrives in Phase", "(later)", "future RL agent",
                 "will be added", "not implemented")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def all_docs() -> dict[Path, str]:
    return {path: read(path) for path in DOC_FILES}


class DocumentationFilesTests(unittest.TestCase):
    def test_the_expected_documents_exist(self):
        names = {p.name for p in DOC_FILES}
        for expected in ("README.md", "USER_GUIDE.md", "DEVELOPER_GUIDE.md", "RL_EXPLAINED.md", "PROJECT_REPORT.md",
                         "VIVA_QUESTIONS.md", "RELIABILITY.md", "EXPERIMENTS.md", "METRICS.md", "Q_LEARNING.md",
                         "RL_ENVIRONMENT.md", "USER_INTERFACE.md", "DEVELOPMENT_PLAN.md"):
            self.assertIn(expected, names)

    def test_every_document_is_linked_from_the_readme(self):
        readme = read(ROOT / "README.md")
        for path in (ROOT / "docs").glob("*.md"):
            self.assertIn(f"docs/{path.name}", readme, f"README.md does not mention docs/{path.name}")

    def test_relative_links_and_images_point_to_existing_files(self):
        problems = []
        for path, text in all_docs().items():
            for target in re.findall(r"\]\(([^)\s]+)\)", text):
                if target.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                target = target.split("#")[0]
                if target and not (path.parent / target).exists():
                    problems.append(f"{path.name}: {target}")
        self.assertEqual(problems, [])

    def test_file_names_in_backticks_exist(self):
        problems = []
        pattern = re.compile(r"`((?:%s)/[A-Za-z0-9_./-]+\.(?:py|md|json|png))`" % "|".join(CODE_DIRS))
        for path, text in all_docs().items():
            for name in pattern.findall(text):
                if "user_settings" in name:  # created by the user, not shipped
                    continue
                if not (ROOT / name).exists():
                    problems.append(f"{path.name}: {name}")
        self.assertEqual(problems, [])

    def test_no_document_or_source_comment_says_something_is_still_to_come(self):
        problems = []
        # only the project's own code: a virtual environment inside the folder (any name) must not be scanned
        sources = [ROOT / "main.py"] + [p for d in CODE_DIRS if d not in ("docs", "tests")
                                        for p in (ROOT / d).rglob("*.py")]
        for path, text in [*all_docs().items(), *((p, read(p)) for p in sources)]:
            for phrase in STALE_PHRASES:
                if phrase in text:
                    problems.append(f"{path.relative_to(ROOT)}: '{phrase}'")
        self.assertEqual(problems, [])


class DocumentationMatchesCodeTests(unittest.TestCase):
    def test_every_command_line_option_in_the_docs_exists(self):
        import main
        real = set(main.build_parser()._option_string_actions)
        problems = []
        for path, text in all_docs().items():
            for option in set(re.findall(r"(?<![\w-])(--[a-z][a-z0-9-]*)", text)):
                if option not in real:
                    problems.append(f"{path.name}: {option}")
        self.assertEqual(problems, [])

    def test_every_documented_scenario_exists(self):
        from config.settings import SCENARIOS
        problems = []
        for path, text in all_docs().items():
            for names in re.findall(r"--(?:scenario|experiment-scenarios|train-scenarios)[ =]([a-z_,]+)", text):
                for name in names.split(","):
                    if name not in SCENARIOS and name not in ("all", "list"):
                        problems.append(f"{path.name}: {name}")
        self.assertEqual(problems, [])
        for name in SCENARIOS:  # the guides must name all of them
            self.assertIn(name, read(ROOT / "docs" / "USER_GUIDE.md"))

    def test_every_setting_named_in_the_docs_exists(self):
        from config.settings import Settings
        settings = Settings()
        problems = []
        pattern = re.compile(r"`(%s)\.([a-z_]+)`" % "|".join(SECTIONS))
        for path, text in all_docs().items():
            for section, key in pattern.findall(text):
                if not hasattr(getattr(settings, section), key):
                    problems.append(f"{path.name}: {section}.{key}")
        self.assertEqual(problems, [])

    def test_the_settings_table_of_the_user_guide_shows_the_real_defaults(self):
        from config.settings import Settings
        settings = Settings()
        lines = read(ROOT / "docs" / "USER_GUIDE.md").splitlines()
        rows = {
            "traffic.scenario": ("traffic.scenario",), "traffic.seed": ("traffic.seed",),
            "traffic.rate_scale": ("traffic.rate_scale",), "simulation.duration": ("simulation.duration",),
            "lights.min_green": ("lights.min_green", "lights.max_green"),
            "lights.yellow": ("lights.yellow", "lights.all_red"),
            "fixed.ns_green": ("fixed.ns_green", "fixed.ew_green"),
            "rl.learning_rate": ("rl.learning_rate", "rl.discount_factor"),
            "rl.epsilon": ("rl.epsilon", "rl.epsilon_decay", "rl.epsilon_min"),
            "rl.episodes": ("rl.episodes",),
            "rl.switch_penalty": ("rl.switch_penalty", "rl.queue_penalty", "rl.queue_limit"),
            "display.theme": ("display.theme",), "display.drive_on": ("display.drive_on",),
        }
        for first, keys in rows.items():
            line = next((ln for ln in lines if ln.startswith(f"| `{first}`")), None)
            self.assertIsNotNone(line, f"no row for {first}")
            default_cell = line.split("|")[2]
            for key in keys:
                section, name = key.split(".")
                value = getattr(getattr(settings, section), name)
                candidates = {str(value), f"{value:g}"} if isinstance(value, (int, float)) else {str(value)}
                found = any(re.search(rf"(?<![\d.]){re.escape(c)}(?![\d])", default_cell) for c in candidates)
                self.assertTrue(found, f"{key} default {value!r} not shown in: {default_cell.strip()}")

    def test_the_documented_settings_ranges_are_enforced(self):
        """The guide tells users that these are limits; make sure each limit really rejects bad values."""
        from config.settings import ConfigError, Settings
        for section, key, bad in (("traffic", "rate_scale", 11), ("rl", "learning_rate", 1.5),
                                  ("lights", "yellow", 0), ("simulation", "dt", 2)):
            with self.assertRaises(ConfigError, msg=f"{section}.{key}={bad} was accepted"):
                Settings().with_changes(section, **{key: bad})

    def test_the_documented_files_are_the_ones_the_program_writes(self):
        from utils import paths
        self.assertEqual(paths.SETTINGS_FILE.name, "user_settings.json")
        self.assertEqual(paths.LOG_DIR.name, "logs")
        self.assertEqual(paths.MODEL_DIR.name, "models")
        guide = read(ROOT / "docs" / "USER_GUIDE.md")
        for name in ("models/q_learning_model.json", "logs/application.log", "config/user_settings.json",
                     "results/csv/", "results/graphs/"):
            self.assertIn(name, guide)
        import main  # the name the guide promises
        self.assertEqual(main.DEFAULT_MODEL_NAME, "q_learning_model.json")

    def test_the_interface_document_names_every_screen(self):
        import main
        text = read(ROOT / "docs" / "USER_INTERFACE.md").lower()
        words = {"menu": "main menu", "compare": "compare side by side", "training": "train the agent",
                 "experiment": "run an experiment", "results": "view results", "settings": "settings",
                 "about": "about"}
        self.assertEqual(set(words), set(main.SCREEN_NAMES))
        for screen, title in words.items():
            self.assertIn(title, text, f"USER_INTERFACE.md does not describe the {screen} screen")


class QuotedNumbersTests(unittest.TestCase):
    def test_the_quoted_number_of_tests_is_true(self):
        loader = unittest.TestLoader()
        actual = loader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT)).countTestCases()
        problems = []
        for name in ("README.md", "docs/PROJECT_REPORT.md", "docs/VIVA_QUESTIONS.md"):
            for number in re.findall(r"\b(\d{3})(?: automated)? tests\b", read(ROOT / name)):
                if int(number) != actual:
                    problems.append(f"{name} says {number}, there are {actual}")
        self.assertEqual(problems, [])

    def test_the_documented_results_match_the_saved_summary_in_the_experiments_document(self):
        """The headline numbers appear in several documents and must agree with each other."""
        report = read(ROOT / "docs" / "PROJECT_REPORT.md")
        experiments = read(ROOT / "docs" / "EXPERIMENTS.md")
        self.assertIn("+3.8 %", report)
        self.assertIn("+3.8 %", experiments)
        for fragment in ("+14.6 %", "+34.7 %", "+30.4 %", "+36.6 %", "+37.2 %", "+31.6 %"):
            self.assertIn(fragment, report)
            self.assertIn(fragment, experiments)
        self.assertIn("-17.1 %", experiments)
        self.assertIn("−17.1 %", report)


if __name__ == "__main__":
    unittest.main()
