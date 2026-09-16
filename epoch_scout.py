"""
Epoch-count scouting and caching for trainbgg (#429).

Scouts one config's epoch count via hyperparameter_search's run_trial, then
caches it so a full-dataset production run doesn't repeat that every build.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import os

    from hyperparameter_search import TrialResult

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScoutConfig:
    """The knobs a scout run and the production `trainbgg` run must share."""

    num_factors: int
    batch_size: int
    learning_rate: float
    lr_step_size: int | None
    lr_gamma: float
    lr_decay_gamma: float | None
    power_users: int
    test_rows: int
    metric: str
    k: int
    patience: int
    eval_every: int
    max_epochs: int
    seed: int | None


def load_cache(cache_path: str | os.PathLike[str]) -> dict[str, Any] | None:
    """Read the cached scout result, or None if there isn't one yet."""
    path = Path(cache_path)
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def cache_is_stale(cache: dict[str, Any], max_age_days: float, now: datetime) -> bool:
    scouted_at = datetime.fromisoformat(cache["scouted_at"])
    return now - scouted_at > timedelta(days=max_age_days)


def run_scout(ratings_file: str | os.PathLike[str], config: ScoutConfig) -> TrialResult:
    """Scout `config`'s epoch count against the held-out power-user split."""

    import polars as pl
    from board_game_recommender.evaluation import (
        recommender_test_data_from_frame,
        split_train_test,
    )

    from hyperparameter_search import TrialConfig, run_trial

    ratings = pl.read_ndjson(
        ratings_file,
        schema={
            "bgg_user_name": pl.String,
            "bgg_id": pl.Int64,
            "bgg_user_rating": pl.Float64,
        },
    )
    train_data, test_data_raw = split_train_test(
        ratings,
        threshold_power_users=config.power_users,
        num_test_rows=config.test_rows,
        seed=config.seed,
    )
    test_data = recommender_test_data_from_frame(
        test_data_raw,
        ratings_per_user=config.test_rows,
    )

    trial_config = TrialConfig(
        name="epoch_scout",
        train_kwargs={
            "num_factors": config.num_factors,
            "batch_size": config.batch_size,
            "learning_rate": config.learning_rate,
        },
        lr_step_size=config.lr_step_size,
        lr_gamma=config.lr_gamma,
        lr_decay_gamma=config.lr_decay_gamma,
    )
    result = run_trial(
        train_data,
        test_data,
        trial_config,
        metric=config.metric,
        k=config.k,
        patience=config.patience,
        eval_every=config.eval_every,
        max_epochs=config.max_epochs,
        seed=config.seed,
    )

    LOGGER.info(
        "Scouted %d epochs: %s@%d=%.4f  ECS@%d=%.1f",
        result.best_epoch,
        config.metric,
        config.k,
        result.best_value,
        config.k,
        result.metrics["effective_catalog_size"][config.k],
    )

    return result


def resolve_num_epochs(
    ratings_file: str | os.PathLike[str],
    cache_path: str | os.PathLike[str],
    config: ScoutConfig,
    *,
    max_age_days: float,
    force: bool,
    now: datetime,
) -> int:
    """Reuse the cached epoch count unless it's missing, stale, or `force`d."""

    cache = None if force else load_cache(cache_path)
    if cache is not None and not cache_is_stale(cache, max_age_days, now):
        LOGGER.info(
            "Reusing cached epoch count %d (scouted %s)",
            cache["num_epochs"],
            cache["scouted_at"],
        )
        return cache["num_epochs"]

    result = run_scout(ratings_file, config)

    cache_entry = {
        "num_epochs": result.best_epoch,
        "scouted_at": now.isoformat(),
        "metric": config.metric,
        "k": config.k,
        "best_value": result.best_value,
        "effective_catalog_size": result.metrics["effective_catalog_size"][config.k],
        "hyperparameters": {
            "num_factors": config.num_factors,
            "batch_size": config.batch_size,
            "learning_rate": config.learning_rate,
            "lr_step_size": config.lr_step_size,
            "lr_gamma": config.lr_gamma if config.lr_step_size else None,
            "lr_decay_gamma": config.lr_decay_gamma,
            "power_users": config.power_users,
            "test_rows": config.test_rows,
            "seed": config.seed,
        },
    }
    path = Path(cache_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(cache_entry, file, indent=2, sort_keys=True)
        file.write("\n")
    LOGGER.info("Cached scouted epoch count %d to <%s>", result.best_epoch, path)

    return result.best_epoch
