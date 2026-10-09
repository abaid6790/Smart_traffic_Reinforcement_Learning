import logging
import tempfile
import unittest
from pathlib import Path

from utils.logging_setup import LOG_FILE_NAME, setup_logging, teardown_logging
from utils.paths import PROJECT_ROOT, REQUIRED_DIRECTORIES, ensure_directories, safe_join


class PathTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)

    def test_project_root_contains_main(self):
        self.assertTrue((PROJECT_ROOT / "main.py").is_file())

    def test_required_directories_are_inside_the_project(self):
        for directory in REQUIRED_DIRECTORIES:
            self.assertTrue(directory.is_relative_to(PROJECT_ROOT))

    def test_ensure_directories_creates_missing_folders_once(self):
        wanted = [self.base / "a", self.base / "b" / "c"]
        self.assertEqual(ensure_directories(wanted), wanted)
        self.assertTrue(all(p.is_dir() for p in wanted))
        self.assertEqual(ensure_directories(wanted), [])

    def test_safe_join_accepts_plain_names(self):
        self.assertEqual(safe_join(self.base, "model.json"), (self.base / "model.json").resolve())
        self.assertEqual(safe_join(self.base, "sub", "x.csv"), (self.base / "sub" / "x.csv").resolve())

    def test_safe_join_rejects_escapes(self):
        for parts in (("..", "evil.txt"), ("../../evil.txt",), ("sub", "..", "..", "x"), (str(self.base.parent / "x"),)):
            with self.assertRaises(ValueError, msg=str(parts)):
                safe_join(self.base, *parts)

    def test_safe_join_rejects_empty_names_and_the_base_itself(self):
        for parts in ((), ("",), (".",)):
            with self.assertRaises(ValueError, msg=str(parts)):
                safe_join(self.base, *parts)


class LoggingTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name) / "logs"
        self.addCleanup(self._tmp.cleanup)
        self.addCleanup(teardown_logging)

    def test_messages_reach_the_log_file(self):
        path = setup_logging(self.dir)
        logging.getLogger("test").info("hello from the test")
        teardown_logging()
        self.assertEqual(path, self.dir / LOG_FILE_NAME)
        self.assertIn("hello from the test", path.read_text(encoding="utf-8"))

    def test_setup_twice_does_not_duplicate_messages(self):
        setup_logging(self.dir)
        path = setup_logging(self.dir)
        logging.getLogger("test").info("only once")
        teardown_logging()
        self.assertEqual(path.read_text(encoding="utf-8").count("only once"), 1)

    def test_unusable_log_folder_does_not_crash(self):
        blocker = Path(self._tmp.name) / "file"
        blocker.write_text("x", encoding="utf-8")
        with self.assertLogs("utils.logging_setup", level="WARNING") as captured:
            result = setup_logging(blocker / "logs")
        self.assertIsNone(result)
        self.assertIn("continuing without it", captured.output[0])


if __name__ == "__main__":
    unittest.main()
