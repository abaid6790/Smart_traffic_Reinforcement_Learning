"""The user interface.

Everything that needs pygame lives in ``ui.components``, ``ui.scene`` and
``ui.simulation_screen`` and is imported only when a window is requested, so the
rest of the project (and its tests) works without pygame installed.  The modules
``ui.geometry``, ``ui.snapshot``, ``ui.session`` and ``ui.theme`` are plain Python.
"""

import os

# pygame prints a greeting when imported; keep the console quiet.
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
