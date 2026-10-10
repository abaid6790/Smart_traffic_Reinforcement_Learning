"""One module per screen of the application."""

from __future__ import annotations

from ui.screens.about import AboutScreen
from ui.screens.compare import CompareScreen
from ui.screens.experiment import ExperimentScreen
from ui.screens.menu import MenuScreen
from ui.screens.results import ResultsScreen
from ui.screens.settings import SettingsScreen
from ui.screens.training import TrainingScreen
from ui.screens.watch import WatchScreen

#: Screen name -> function that builds it.  ``app.go(name)`` uses this table.
SCREENS = {
    "menu": MenuScreen,
    "watch_fixed": lambda app, **kw: WatchScreen(app, "fixed"),
    "watch_rl": lambda app, **kw: WatchScreen(app, "rl"),
    "compare": CompareScreen,
    "training": TrainingScreen,
    "experiment": ExperimentScreen,
    "results": ResultsScreen,
    "settings": SettingsScreen,
    "about": AboutScreen,
}
