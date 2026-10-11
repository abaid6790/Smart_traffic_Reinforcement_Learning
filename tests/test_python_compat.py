"""The project supports Python 3.11, so no file may use syntax that only newer versions accept
(for example the same quote character nested inside an f-string)."""

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class SyntaxCompatibilityTests(unittest.TestCase):
    def test_no_nested_same_quote_in_fstrings(self):
        """Python 3.11 cannot parse f"...{x["a"]}..."; Python 3.12+ can, so check the source directly."""
        import io
        import tokenize
        problems = []
        # only the project's own code; a virtual environment inside the folder (whatever its name) is not ours
        own = [ROOT / "main.py"] + [p for d in ("agents", "config", "controllers", "environment", "evaluation",
                                                 "simulation", "training", "ui", "utils", "tests")
                                    for p in (ROOT / d).rglob("*.py")]
        for path in sorted(own):
            source = path.read_text(encoding="utf-8")
            ast.parse(source, str(path))
            try:
                tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
            except tokenize.TokenError:
                continue
            fstart = getattr(tokenize, "FSTRING_START", None)
            if fstart is None:  # Python 3.11 itself rejects the bad syntax in ast.parse above
                continue
            stack = []
            for tok in tokens:
                if tok.type == fstart:
                    quote = tok.string.lstrip("rRbBfF")
                    if stack and stack[-1] == quote:
                        problems.append(f"{path.relative_to(ROOT)}:{tok.start[0]}")
                    stack.append(quote)
                elif tok.type == tokenize.FSTRING_END if hasattr(tokenize, "FSTRING_END") else False:
                    stack.pop()
                elif tok.type == tokenize.STRING and stack and tok.string.lstrip("rRbBuU")[:1] == stack[-1][:1]:
                    problems.append(f"{path.relative_to(ROOT)}:{tok.start[0]}")
        self.assertEqual(problems, [], "f-string reuses its own quote character inside {} (fails on Python 3.11)")


if __name__ == "__main__":
    unittest.main()
