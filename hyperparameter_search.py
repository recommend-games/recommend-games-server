"""
Harness for comparing `board_game_recommender.dnn.train()` configurations
against a held-out power-user split.

Generic over both the config varied and the metric optimised, so the same
`run_trial`/`compare_trials` machinery covers a single-config epoch scout as
well as a multi-config comparison.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import os

    import polars as pl
    from board_game_recommender.evaluation import RecommenderTestData

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class TrialConfig:
    """
    Plain fields, not a `lr_scheduler_factory` callable, for the LR
    schedule: callables can't round-trip through `write_comparison_report`'s
    `json.dump`.
    """

    name: str
    train_kwargs: dict[str, Any] = field(default_factory=dict)
    lr_step_size: int | None = None
    lr_gamma: float = 0.5


@dataclass(frozen=True)
class TrialResult:
    name: str
    train_kwargs: dict[str, Any]
    lr_step_size: int | None
    lr_gamma: float | None
    metric: str
    k: int
    stopped: bool
    best_epoch: int | None
    best_value: float | None
    metrics: dict[str, Any]
    seconds: float


def run_trial(
    train_data: pl.DataFrame,
    test_data: RecommenderTestData[int, str],
    config: TrialConfig,
    *,
    metric: str,
    k: int,
    patience: int,
    eval_every: int,
    max_epochs: int,
    seed: int | None,
) -> TrialResult:
    """
    `early_stopping_callback` only restores the best epoch's weights on the
    stop path, so a run that caps out at `max_epochs` without stopping
    returns its *last* epoch, not its best -- not comparable to a run that
    did stop. This raises in that case rather than silently ranking it
    anyway; set `max_epochs` generously.
    """
    import functools

    from board_game_recommender.dnn import early_stopping_callback, train
    from board_game_recommender.evaluation import calculate_metrics
    from board_game_recommender.light import LightGamesRecommender
    from torch import optim

    callback, state = early_stopping_callback(
        test_data,
        metric=metric,
        k=k,
        patience=patience,
        eval_every=eval_every,
    )

    lr_scheduler_factory = (
        functools.partial(
            optim.lr_scheduler.StepLR,
            step_size=config.lr_step_size,
            gamma=config.lr_gamma,
        )
        if config.lr_step_size
        else None
    )

    LOGGER.info("Running trial %r: %s", config.name, config.train_kwargs)
    start = time.monotonic()
    result = train(
        train_data,
        num_epochs=max_epochs,
        lr_scheduler_factory=lr_scheduler_factory,
        seed=seed,
        on_epoch_end=callback,
        **config.train_kwargs,
    )
    seconds = time.monotonic() - start

    if not state.stopped or state.best_value is None or state.best_epoch is None:
        msg = (
            f"Trial {config.name!r} never triggered early stopping in "
            f"{max_epochs} epochs, so its best epoch's weights were never "
            "restored -- it isn't comparable to trials that did stop. "
            "Raise max_epochs or loosen patience/eval_every."
        )
        raise RuntimeError(msg)

    full_metrics = calculate_metrics(
        LightGamesRecommender(result.to_collaborative_filtering_data()),
        test_data,
        k_values=[k],
    )

    LOGGER.info(
        "Trial %r stopped at epoch %d: %s@%d=%.4f (%.1fs)",
        config.name,
        state.best_epoch,
        metric,
        k,
        state.best_value,
        seconds,
    )

    return TrialResult(
        name=config.name,
        train_kwargs=dict(config.train_kwargs),
        lr_step_size=config.lr_step_size,
        lr_gamma=config.lr_gamma if config.lr_step_size else None,
        metric=metric,
        k=k,
        stopped=state.stopped,
        best_epoch=state.best_epoch,
        best_value=state.best_value,
        metrics=asdict(full_metrics),
        seconds=seconds,
    )


def compare_trials(
    train_data: pl.DataFrame,
    test_data: RecommenderTestData[int, str],
    configs: list[TrialConfig],
    *,
    metric: str,
    k: int,
    patience: int = 10,
    eval_every: int = 5,
    max_epochs: int = 1000,
    seed: int | None = None,
) -> list[TrialResult]:
    """
    Runs every config against the same train/test split and seed so results
    are comparable. Returns them ordered best-first on `metric`@`k`.
    """
    higher_is_better = metric != "rmse"
    results = [
        run_trial(
            train_data,
            test_data,
            config,
            metric=metric,
            k=k,
            patience=patience,
            eval_every=eval_every,
            max_epochs=max_epochs,
            seed=seed,
        )
        for config in configs
    ]
    return sorted(results, key=_sort_key, reverse=higher_is_better)


def _sort_key(result: TrialResult) -> float:
    # best_value stays Optional on the dataclass (matching EarlyStoppingState),
    # but run_trial() never returns a result with it unset.
    assert result.best_value is not None
    return result.best_value


def write_comparison_report(
    results: list[TrialResult],
    path: str | os.PathLike[str],
) -> Path:
    """Write `results` as JSON. Use a path outside `DATA_DIR`, which `cleandata` wipes."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump([asdict(r) for r in results], file, indent=2, sort_keys=True)
        file.write("\n")
    LOGGER.info("Wrote comparison report for %d trial(s) to <%s>", len(results), path)
    return path
