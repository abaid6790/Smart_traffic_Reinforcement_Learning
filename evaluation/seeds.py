"""Which traffic seed each kind of run uses.

Three ranges that never overlap (unless more than a million episodes are trained), so a
controller is never judged on traffic it practised or was tuned on:

* training episode ``i``      -> ``base_seed + i``
* validation / tuning run ``k`` -> ``base_seed + 2,000,000 + k``  (used to pick the best
  Q-Learning policy while training, and to tune the fixed-time controller)
* evaluation run ``k``        -> ``base_seed + 1,000,000 + k``  (experiments and tests)
"""

from __future__ import annotations

from config.settings import MAX_SEED

#: Evaluation seeds start this far above the training seeds.
EVALUATION_SEED_OFFSET = 1_000_000
#: Validation and tuning seeds start this far above the training seeds.
VALIDATION_SEED_OFFSET = 2_000_000


def training_seed(base_seed: int, episode: int) -> int:
    """Traffic seed of training episode number ``episode`` (counting from 0)."""
    return (base_seed + episode) % (MAX_SEED + 1)


def evaluation_seed(base_seed: int, run: int) -> int:
    """Traffic seed of evaluation run number ``run`` (counting from 0)."""
    return (base_seed + EVALUATION_SEED_OFFSET + run) % (MAX_SEED + 1)


def validation_seed(base_seed: int, run: int) -> int:
    """Traffic seed of validation (or tuning) run number ``run`` (counting from 0)."""
    return (base_seed + VALIDATION_SEED_OFFSET + run) % (MAX_SEED + 1)
