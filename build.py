#!/usr/bin/env python

"""
Invoke build file.

Install the Python dependencies (including the build group) with uv, then run
tasks against this file:

```bash
uv sync
uv run invoke -c build --list
uv run invoke -c build builddb
```

Note the `build` dependency group installs torch, which publishes no macOS
x86_64 wheels -- so the data pipeline requires Linux or Apple Silicon.

Non-Python dependencies:

* Docker
* `brew install git sqlite shellcheck hadolint markdownlint-cli`
* `npm install --global htmlhint jslint jshint csslint`
* `gem install mdl`
* `brew tap heroku/brew && brew install heroku`
* `heroku login`
"""

import logging
import os
import shutil
import subprocess
import sys
from contextlib import contextmanager
from datetime import UTC
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

import django
from dotenv import load_dotenv
from git import Repo
from invoke import task
from pytility import arg_to_iter, parse_bool, parse_date, parse_float, parse_int
from snaptime import snap

if TYPE_CHECKING:
    import polars as pl

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv(verbose=True)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "rg.settings")
os.environ.setdefault("PYTHONPATH", BASE_DIR)
os.environ.setdefault("CLOUDSDK_PYTHON", "python3")
os.environ["DEBUG"] = ""
sys.path.insert(0, BASE_DIR)
django.setup()

LOGGER = logging.getLogger(__name__)


# invoke's --dry/-R only suppresses its own c.run(), so execute() has to honour
# it itself -- otherwise `invoke --dry release` would really push to Heroku.
DRY_RUN = bool({"-R", "--dry"} & set(sys.argv))


# Replacements for pyntcontrib's execute() and safe_cd(). Deliberately kept
# instead of invoke's c.run()/c.cd(): those take a shell string, while the ~30
# call sites here pass argv lists, some of them variadic -- re-quoting them
# would be a needless source of bugs with paths containing spaces.
def execute(*args, **kwargs):
    """Run a command, raising CalledProcessError if it fails."""
    if DRY_RUN:
        LOGGER.info("[DRY RUN] Would execute %s", " ".join(map(str, args)))
        return None
    LOGGER.info("Executing %s", " ".join(map(str, args)))
    return subprocess.run([str(arg) for arg in args], check=True, **kwargs)


@contextmanager
def safe_cd(path):
    """Change into a directory, always restoring the previous one."""
    prev = os.getcwd()
    LOGGER.info("Changing directory to <%s>", path)
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev)


SETTINGS = django.conf.settings

DATA_DIR = SETTINGS.DATA_DIR
MODELS_DIR = SETTINGS.MODELS_DIR
CONFIG_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "recommend-games-config"))
SCRAPER_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "board-game-scraper"))
RECOMMENDER_DIR = os.path.abspath(
    os.path.join(BASE_DIR, "..", "board-game-recommender")
)
SCRAPED_DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "board-game-data"))
# Outside DATA_DIR, which cleandata wipes every build.
MODEL_ARCHIVE_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "model-archive"))
EPOCH_CALIBRATION_CACHE_PATH = os.path.join(MODELS_DIR, "epoch_calibration_cache.json")

# Tier 2 (#428) defaults, shared by trainbgg and epochcalibrate below.
TIER2_LEARNING_RATE = 1e-3
TIER2_LR_STEP_SIZE = None
TIER2_LR_GAMMA = 0.5
TIER2_LR_DECAY_GAMMA = None

DATE_FORMAT_DASH = "%Y-%m-%dT%H-%M-%S"
DATE_FORMAT_COMPACT = "%Y%m%d-%H%M%S"

MIN_VOTES_ANCHOR_DATE = SETTINGS.MIN_VOTES_ANCHOR_DATE
MIN_VOTES_SECONDS_PER_STEP = SETTINGS.MIN_VOTES_SECONDS_PER_STEP

URL_LIVE = "https://recommend.games/"
HEROKU_APP = os.getenv("HEROKU_APP") or "recommend-games"

GAMES_CSV_COLUMNS = (
    "bgg_id",
    "name",
    "year",
    "game_type",
    "designer",
    "artist",
    "publisher",
    "min_players",
    "max_players",
    "min_players_rec",
    "max_players_rec",
    "min_players_best",
    "max_players_best",
    "min_age",
    "min_age_rec",
    "min_time",
    "max_time",
    "category",
    "mechanic",
    "cooperative",
    "compilation",
    "compilation_of",
    "family",
    "implementation",
    "integration",
    "rank",
    "num_votes",
    "avg_rating",
    "stddev_rating",
    "bayes_rating",
    "complexity",
    "language_dependency",
    "dbpedia_id",
    "luding_id",
    "spielen_id",
    "wikidata_id",
    "wikipedia_id",
)

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8.8s [%(name)s:%(lineno)s] %(message)s",
)


@lru_cache(maxsize=8)
def _server_version(path=os.path.join(BASE_DIR, "VERSION")):
    with open(path, encoding="utf-8") as file:
        version = file.read()
    return version.strip()


def _remove(path):
    if DRY_RUN:
        LOGGER.info("[DRY RUN] Would remove <%s>", path)
        return
    LOGGER.info("Removing <%s> if it exists...", path)
    try:
        os.remove(path)
    except OSError:
        shutil.rmtree(path, ignore_errors=True)


def _git_provenance(repo_path: str) -> dict[str, object] | None:
    """
    Return the checked-out commit SHA and dirty state of a Git repo, or None
    if `repo_path` isn't one (e.g. no `.git` in a stripped-down container).
    """
    try:
        repo = Repo(repo_path)
        return {
            "sha": repo.head.commit.hexsha,
            "dirty": repo.is_dirty(untracked_files=True),
        }
    except Exception:
        LOGGER.exception("Unable to determine Git provenance for <%s>", repo_path)
        return None


def _ratings_provenance(
    ratings_file: str | os.PathLike[str],
    ratings: pl.DataFrame,
) -> dict[str, object]:
    """
    Row count/size/mtime, not just git SHA: `gitupdate` commits
    `SCRAPED_DATA_DIR` after training runs, so the SHA alone can predate
    the data used.
    """
    ratings_stat = os.stat(ratings_file)
    return {
        "path": str(ratings_file),
        "row_count": len(ratings),
        "size_bytes": ratings_stat.st_size,
        "modified": ratings_stat.st_mtime,
        "git": _git_provenance(SCRAPED_DATA_DIR),
    }


def _training_provenance(
    ratings_file: str | os.PathLike[str],
    ratings: pl.DataFrame,
    hyperparameters: dict[str, object],
) -> dict[str, object]:
    from board_game_recommender.dnn import training_metadata

    metadata = training_metadata(hyperparameters=hyperparameters)
    metadata["recommend_games_server_git"] = _git_provenance(BASE_DIR)
    metadata["ratings_data"] = _ratings_provenance(ratings_file, ratings)
    return metadata


@task()
def gitprepare(c, repo=SCRAPED_DATA_DIR):
    """check Git repo is clean and up-to-date"""
    LOGGER.info("Preparing Git repo <%s>...", repo)
    try:
        with safe_cd(repo):
            execute("git", "checkout", "main")
            execute("git", "pull", "--ff-only")
            execute("git", "diff", "HEAD", "--name-only")
    except Exception:
        LOGGER.exception("There was a problem preparing <%s>...", repo)


@task()
def gitprepareconfig(c, repo=CONFIG_DIR):
    """Check config Git repo is clean and up-to-date."""
    LOGGER.info("Preparing Git repo <%s>...", repo)
    try:
        with safe_cd(repo):
            execute("git", "checkout", "main")
            execute("git", "pull", "--ff-only")
            execute("git", "diff", "HEAD", "--name-only")
    except Exception:
        LOGGER.exception("There was a problem preparing <%s>...", repo)


@task()
def gitupdate(c, *paths, repo=SCRAPED_DATA_DIR, name=__name__):
    """commit and push Git repo"""
    paths = paths or ("COUNT.md", "rankings", "scraped", "links.json")
    LOGGER.info("Updating paths %r in Git repo <%s>...", paths, repo)
    try:
        with safe_cd(repo):
            try:
                execute("git", "gc", "--prune=now")
                execute("git", "add", "--", *paths)
            except Exception:
                LOGGER.exception("There was a problem in repo <%s>...", repo)

            try:
                execute(
                    "git",
                    "commit",
                    "--no-gpg-sign",
                    "--message",
                    f"automatic commit by <{name}>",
                )
                execute("git", "gc", "--prune=now")
            except Exception:
                LOGGER.info("Nothing to commit...")

            try:
                execute("git", "push", "framagit", "main")
            except Exception:
                LOGGER.exception("Unable to push...")
    except Exception:
        LOGGER.exception("There was a problem updating repo <%s>...", repo)


def _run_merge(
    merge_config,
    overwrite=True,
    drop_empty=True,
    sort_keys=True,
    progress_bar=False,
):
    from board_game_merger.merge import merge_files

    if DRY_RUN:
        LOGGER.info(
            "[DRY RUN] Would merge <%s> into <%s>",
            merge_config.in_paths,
            merge_config.out_path,
        )
        return

    LOGGER.info(
        "Merging files <%s> into <%s>...",
        merge_config.in_paths,
        merge_config.out_path,
    )

    try:
        merge_files(
            merge_config=merge_config,
            overwrite=overwrite,
            drop_empty=drop_empty,
            sort_keys=sort_keys,
            progress_bar=progress_bar,
        )
    except Exception:
        LOGGER.exception(
            "Unable to merge files <%s> into <%s>...",
            merge_config.in_paths,
            merge_config.out_path,
        )


def _site_merge_config(
    site,
    item="GameItem",
    in_paths=None,
    out_path=None,
    clean=True,
    days=None,
):
    from board_game_merger.config import MergeConfig

    clean = parse_bool(clean)
    days = parse_float(days)

    in_paths = in_paths or (Path(SCRAPER_DIR) / "feeds" / site / item)
    if clean:
        out_path = out_path or (
            Path(SCRAPED_DATA_DIR) / "scraped" / f"{site}_{item}.jl"
        )
    else:
        date_str = django.utils.timezone.now().strftime(DATE_FORMAT_DASH)
        out_path = out_path or (
            Path(SCRAPER_DIR) / "feeds" / site / item / f"{date_str}-merged.jl"
        )

    return MergeConfig.site_config(
        site=site,
        item=item,
        in_paths=in_paths,
        out_path=out_path,
        clean_results=clean,
        latest_min_days=days,
    )


@task()
def merge(
    c,
    site="all",
    item="GameItem",
    in_paths=None,
    out_path=None,
    clean=True,
    overwrite=True,
    days=None,
    progress_bar=False,
):
    """Merge scraped data files using board-game-merger."""
    from board_game_merger.config import MergeConfig

    clean = parse_bool(clean)
    overwrite = parse_bool(overwrite)
    days = parse_float(days)
    progress_bar = parse_bool(progress_bar)

    if site == "all":
        for config in MergeConfig.all_sites_config(
            clean_results=clean,
            latest_min_days=days,
        ):
            site_name = (
                "bgg_hotness"
                if "bgg_hotness" in str(config.in_paths)
                else "bgg"
                if "/bgg/" in str(config.in_paths)
                else Path(config.in_paths).parent.name
            )
            item_name = Path(config.in_paths).name
            cfg = _site_merge_config(
                site=site_name,
                item=item_name,
                in_paths=in_paths,
                out_path=out_path,
                clean=clean,
                days=days,
            )
            _run_merge(
                cfg,
                overwrite=overwrite,
                drop_empty=True,
                sort_keys=clean,
                progress_bar=progress_bar,
            )
    else:
        cfg = _site_merge_config(
            site=site,
            item=item,
            in_paths=in_paths,
            out_path=out_path,
            clean=clean,
            days=days,
        )
        _run_merge(
            cfg,
            overwrite=overwrite,
            drop_empty=True,
            sort_keys=clean,
            progress_bar=progress_bar,
        )


@task()
def mergebgg(c, in_paths=None, out_path=None, clean=True, overwrite=True):
    """Merge BoardGameGeek game data."""
    merge(
        c,
        site="bgg",
        item="GameItem",
        in_paths=in_paths,
        out_path=out_path,
        clean=clean,
        overwrite=overwrite,
    )


@task()
def mergebggusers(c, in_paths=None, out_path=None, clean=True, overwrite=True):
    """Merge BoardGameGeek user data."""
    merge(
        c,
        site="bgg",
        item="UserItem",
        in_paths=in_paths,
        out_path=out_path,
        clean=clean,
        overwrite=overwrite,
    )


@task()
def mergebggratings(c, in_paths=None, out_path=None, clean=True, overwrite=True):
    """Merge BoardGameGeek rating data."""
    merge(
        c,
        site="bgg",
        item="RatingItem",
        in_paths=in_paths,
        out_path=out_path,
        clean=clean,
        overwrite=overwrite,
    )


@task()
def mergebgghotness(
    c, in_paths=None, out_path=None, clean=True, overwrite=True, days=None
):
    """Merge BoardGameGeek hotness data."""
    merge(
        c,
        site="bgg_hotness",
        item="GameItem",
        in_paths=in_paths,
        out_path=out_path,
        clean=clean,
        overwrite=overwrite,
        days=days,
    )


@task()
def mergedbpedia(c, in_paths=None, out_path=None, clean=True, overwrite=True):
    """Merge DBpedia game data."""
    merge(
        c,
        site="dbpedia",
        item="GameItem",
        in_paths=in_paths,
        out_path=out_path,
        clean=clean,
        overwrite=overwrite,
    )


@task()
def mergeluding(c, in_paths=None, out_path=None, clean=True, overwrite=True):
    """Merge Luding.org game data."""
    merge(
        c,
        site="luding",
        item="GameItem",
        in_paths=in_paths,
        out_path=out_path,
        clean=clean,
        overwrite=overwrite,
    )


@task()
def mergespielen(c, in_paths=None, out_path=None, clean=True, overwrite=True):
    """Merge Spielen.de game data."""
    merge(
        c,
        site="spielen",
        item="GameItem",
        in_paths=in_paths,
        out_path=out_path,
        clean=clean,
        overwrite=overwrite,
    )


@task()
def mergewikidata(c, in_paths=None, out_path=None, clean=True, overwrite=True):
    """Merge Wikidata game data."""
    merge(
        c,
        site="wikidata",
        item="GameItem",
        in_paths=in_paths,
        out_path=out_path,
        clean=clean,
        overwrite=overwrite,
    )


@task(
    mergebgghotness,
    mergedbpedia,
    mergeluding,
    mergespielen,
    mergewikidata,
    mergebgg,
    mergebggusers,
    mergebggratings,
)
def mergeall(
    c,
):
    """Merge all sites and items."""


# Held constant across production training and every tier2search candidate,
# which varies only learning_rate/LR schedule.
TIER1_HYPERPARAMETERS = {
    "num_factors": 32,
    "batch_size": 1 << 16,
    "regularization": 1e-9,
    "linear_regularization": 1e-9,
    "ranking_regularization": 0.25,
    "num_sampled_negative_examples": 4,
}


@task()
def epochcalibrate(
    c,
    ratings_file=os.path.join(SCRAPED_DATA_DIR, "scraped", "bgg_RatingItem.jl"),
    cache_path=EPOCH_CALIBRATION_CACHE_PATH,
    num_factors=TIER1_HYPERPARAMETERS["num_factors"],
    batch_size=TIER1_HYPERPARAMETERS["batch_size"],
    learning_rate=TIER2_LEARNING_RATE,
    lr_step_size=TIER2_LR_STEP_SIZE,
    lr_gamma=TIER2_LR_GAMMA,
    lr_decay_gamma=TIER2_LR_DECAY_GAMMA,
    power_users=200,
    test_rows=100,
    metric="ndcg",
    k=25,
    patience=30,
    eval_every=2,
    max_epochs=1000,
    seed=None,
):
    """Force a fresh epoch calibration and refresh the cache `trainbgg` reads."""

    from games.epoch_calibration import CalibrationConfig, calibrate_num_epochs

    config = CalibrationConfig(
        num_factors=parse_int(num_factors) or TIER1_HYPERPARAMETERS["num_factors"],
        batch_size=parse_int(batch_size) or TIER1_HYPERPARAMETERS["batch_size"],
        learning_rate=parse_float(learning_rate) or TIER2_LEARNING_RATE,
        lr_step_size=parse_int(lr_step_size),
        lr_gamma=parse_float(lr_gamma) or TIER2_LR_GAMMA,
        lr_decay_gamma=parse_float(lr_decay_gamma),
        power_users=parse_int(power_users) or 200,
        test_rows=parse_int(test_rows) or 100,
        metric=metric,
        k=parse_int(k) or 25,
        patience=parse_int(patience) or 30,
        eval_every=parse_int(eval_every) or 2,
        max_epochs=parse_int(max_epochs) or 1000,
        seed=parse_int(seed),
    )
    num_epochs = calibrate_num_epochs(
        ratings_file,
        cache_path,
        config,
        max_age_days=0,
        force=True,
        now=django.utils.timezone.now(),
    )
    LOGGER.info("Calibrated epoch count: %d", num_epochs)


@task()
def trainbgg(
    c,
    ratings_file=os.path.join(SCRAPED_DATA_DIR, "scraped", "bgg_RatingItem.jl"),
    out_path_light=os.path.join(RECOMMENDER_DIR, ".bgg.light.npz"),
    archive_dir=MODEL_ARCHIVE_DIR,
    num_factors=TIER1_HYPERPARAMETERS["num_factors"],
    num_epochs=None,
    batch_size=TIER1_HYPERPARAMETERS["batch_size"],
    learning_rate=TIER2_LEARNING_RATE,
    lr_step_size=TIER2_LR_STEP_SIZE,
    lr_gamma=TIER2_LR_GAMMA,
    lr_decay_gamma=TIER2_LR_DECAY_GAMMA,
    epoch_calibration_cache=EPOCH_CALIBRATION_CACHE_PATH,
    epoch_calibration_max_age_days=7,
    force_calibration=False,
    calibration_power_users=200,
    calibration_test_rows=100,
    calibration_metric="ndcg",
    calibration_k=25,
    calibration_patience=30,
    calibration_eval_every=2,
    calibration_max_epochs=1000,
    seed=None,
):
    """train BoardGameGeek recommender model"""

    import functools

    import polars as pl
    from board_game_recommender.dnn import train, write_training_metadata
    from torch import optim

    from games.epoch_calibration import CalibrationConfig, calibrate_num_epochs

    num_factors = parse_int(num_factors) or TIER1_HYPERPARAMETERS["num_factors"]
    num_epochs = parse_int(num_epochs)
    batch_size = parse_int(batch_size) or TIER1_HYPERPARAMETERS["batch_size"]
    learning_rate = parse_float(learning_rate) or TIER2_LEARNING_RATE
    lr_step_size = parse_int(lr_step_size)
    lr_gamma = parse_float(lr_gamma) or TIER2_LR_GAMMA
    lr_decay_gamma = parse_float(lr_decay_gamma)
    seed = parse_int(seed)

    if lr_step_size and lr_decay_gamma:
        msg = "Set at most one of lr_step_size or lr_decay_gamma."
        raise ValueError(msg)

    # An explicit --num-epochs always wins over the cached/calibrated value (#429).
    epoch_count_calibrated = num_epochs is None
    if epoch_count_calibrated:
        calibration_config = CalibrationConfig(
            num_factors=num_factors,
            batch_size=batch_size,
            learning_rate=learning_rate,
            lr_step_size=lr_step_size,
            lr_gamma=lr_gamma,
            lr_decay_gamma=lr_decay_gamma,
            power_users=parse_int(calibration_power_users) or 200,
            test_rows=parse_int(calibration_test_rows) or 100,
            metric=calibration_metric,
            k=parse_int(calibration_k) or 25,
            patience=parse_int(calibration_patience) or 30,
            eval_every=parse_int(calibration_eval_every) or 2,
            max_epochs=parse_int(calibration_max_epochs) or 1000,
            seed=seed,
        )
        num_epochs = calibrate_num_epochs(
            ratings_file,
            epoch_calibration_cache,
            calibration_config,
            max_age_days=parse_int(epoch_calibration_max_age_days) or 7,
            force=parse_bool(force_calibration),
            now=django.utils.timezone.now(),
        )

    LOGGER.info(
        "Training recommender model from ratings <%s> with %d factors for %d epochs...",
        ratings_file,
        num_factors,
        num_epochs,
    )

    ratings = pl.read_ndjson(
        ratings_file,
        schema={
            "bgg_user_name": pl.String,
            "bgg_id": pl.Int64,
            "bgg_user_rating": pl.Float64,
        },
    )
    LOGGER.info("Loaded %d ratings", len(ratings))

    # Always trains on the full dataset, never the calibration run's held-out split.
    if lr_step_size:
        lr_scheduler_factory = functools.partial(
            optim.lr_scheduler.StepLR, step_size=lr_step_size, gamma=lr_gamma
        )
    elif lr_decay_gamma:
        lr_scheduler_factory = functools.partial(
            optim.lr_scheduler.ExponentialLR, gamma=lr_decay_gamma
        )
    else:
        lr_scheduler_factory = None
    result = train(
        ratings,
        num_factors=num_factors,
        num_epochs=num_epochs,
        batch_size=batch_size,
        learning_rate=learning_rate,
        lr_scheduler_factory=lr_scheduler_factory,
        regularization=TIER1_HYPERPARAMETERS["regularization"],
        linear_regularization=TIER1_HYPERPARAMETERS["linear_regularization"],
        ranking_regularization=TIER1_HYPERPARAMETERS["ranking_regularization"],
        num_sampled_negative_examples=TIER1_HYPERPARAMETERS[
            "num_sampled_negative_examples"
        ],
        seed=seed,
    )

    LOGGER.info("Saving model to <%s>...", out_path_light)
    _remove(out_path_light)
    os.makedirs(os.path.dirname(out_path_light), exist_ok=True)
    result.to_collaborative_filtering_data().to_npz(out_path_light)

    metadata = _training_provenance(
        ratings_file,
        ratings,
        hyperparameters={
            "num_factors": num_factors,
            "num_epochs": num_epochs,
            "batch_size": batch_size,
            "learning_rate": learning_rate,
            "lr_step_size": lr_step_size,
            "lr_gamma": lr_gamma if lr_step_size else None,
            "lr_decay_gamma": lr_decay_gamma,
            "unobserved_rating_value": result.unobserved_rating_value,
            "seed": seed,
        },
    )
    if epoch_count_calibrated:
        metadata["epoch_calibration"] = {"cache_path": str(epoch_calibration_cache)}

    timestamp = django.utils.timezone.now().strftime(DATE_FORMAT_COMPACT)
    archive_path = os.path.join(archive_dir, f"{timestamp}.npz")
    LOGGER.info("Archiving model and provenance to <%s>...", archive_path)
    os.makedirs(archive_dir, exist_ok=True)
    shutil.copy2(out_path_light, archive_path)
    write_training_metadata(archive_path, metadata)

    LOGGER.info("Done training.")


@task()
def tier2search(
    c,
    ratings_file=os.path.join(SCRAPED_DATA_DIR, "scraped", "bgg_RatingItem.jl"),
    out_dir=os.path.join(MODELS_DIR, "hp_search"),
    power_users=200,
    test_rows=100,
    metric="ndcg",
    k=25,
    patience=30,
    eval_every=2,
    max_epochs=1000,
    seed=None,
):
    """Compare trainbgg's optimizer/LR candidates on nDCG@25, ECS@25 as a degeneracy check."""

    import time

    import polars as pl
    from board_game_recommender.evaluation import (
        recommender_test_data_from_frame,
        split_train_test,
    )

    from games.hyperparameter_search import (
        TrialConfig,
        compare_trials,
        write_comparison_report,
    )

    power_users = parse_int(power_users) or 200
    test_rows = parse_int(test_rows) or 100
    k = parse_int(k) or 25
    patience = parse_int(patience) or 30
    eval_every = parse_int(eval_every) or 2
    max_epochs = parse_int(max_epochs) or 1000
    # Nanosecond resolution: second resolution risks two invocations
    # scripted back-to-back landing on the same seed.
    seed = parse_int(seed) if seed is not None else time.time_ns()

    LOGGER.info("Using seed %d", seed)
    LOGGER.info("Loading ratings from <%s>...", ratings_file)
    ratings = pl.read_ndjson(
        ratings_file,
        schema={
            "bgg_user_name": pl.String,
            "bgg_id": pl.Int64,
            "bgg_user_rating": pl.Float64,
        },
    )
    LOGGER.info("Loaded %d ratings", len(ratings))

    train_data, test_data_raw = split_train_test(
        ratings,
        threshold_power_users=power_users,
        num_test_rows=test_rows,
        seed=seed,
    )
    test_data = recommender_test_data_from_frame(
        test_data_raw,
        ratings_per_user=test_rows,
    )

    configs = [
        TrialConfig(
            name="flat_adam_1e-3",
            train_kwargs={**TIER1_HYPERPARAMETERS, "learning_rate": 1e-3},
        ),
        # Gammas anchored to flat_adam_1e-3's ~265-epoch horizon: leaves
        # 50%/10% of the start LR by epoch 265, well above the near-zero LR
        # that killed the earlier step=5/step=10 schedules.
        TrialConfig(
            name="adam_decay_1e-3_exp_gamma0.9974",
            train_kwargs={**TIER1_HYPERPARAMETERS, "learning_rate": 1e-3},
            lr_decay_gamma=0.9974,
        ),
        TrialConfig(
            name="adam_decay_1e-3_exp_gamma0.9913",
            train_kwargs={**TIER1_HYPERPARAMETERS, "learning_rate": 1e-3},
            lr_decay_gamma=0.9913,
        ),
    ]

    results = compare_trials(
        train_data,
        test_data,
        configs,
        metric=metric,
        k=k,
        patience=patience,
        eval_every=eval_every,
        max_epochs=max_epochs,
        seed=seed,
    )

    LOGGER.info(
        "Winner: %s (%s@%d=%.4f)",
        results[0].name,
        metric,
        k,
        results[0].best_value,
    )
    for result in results:
        LOGGER.info(
            "  %-30s %s@%d=%.4f  nDCG_exp@%d=%.4f  RMSE=%.4f  ECS@%d=%.1f  "
            "coverage@%d=%.4f  novelty@%d=%.4f  best_epoch=%s  stopped=%s",
            result.name,
            metric,
            k,
            result.best_value,
            k,
            result.metrics["ndcg_exp"][k],
            result.metrics["rmse"],
            k,
            result.metrics["effective_catalog_size"][k],
            k,
            result.metrics["catalog_coverage"][k],
            k,
            result.metrics["novelty"][k],
            result.best_epoch,
            result.stopped,
        )

    # Everything else already lives on TrialResult; only what has no
    # per-trial home goes here, merged into each trial's record on write.
    provenance = {
        "recommend_games_server_git": _git_provenance(BASE_DIR),
        "ratings_data": _ratings_provenance(ratings_file, ratings),
        "power_users": power_users,
        "test_rows": test_rows,
    }

    out_path = Path(out_dir) / django.utils.timezone.now().strftime(
        f"tier2_{DATE_FORMAT_COMPACT}.json"
    )
    write_comparison_report(results, out_path, provenance=provenance)


def _save_rg_ranking(
    recommender,
    path_ratings,
    games_file,
    top,
    min_ratings,
    dst_dir,
    file_name=f"{DATE_FORMAT_COMPACT}.csv",
):
    import polars as pl

    from games.rankings import calculate_rankings

    dst_dir = Path(dst_dir).resolve()
    dst_path = dst_dir / django.utils.timezone.now().strftime(file_name)
    path_ratings = Path(path_ratings).resolve()

    LOGGER.info(
        "Calculate R.G rankings from model <%s> and ratings from <%s>",
        recommender,
        path_ratings,
    )
    LOGGER.info(
        "Using top %d games and %d min ratings, saving results to <%s>...",
        top,
        min_ratings,
        dst_path,
    )

    # Compilations used to come off the Turi Create model, which read them from
    # this same games file. Taking them straight from the file keeps that
    # behaviour and avoids depending on database state -- savebggrankings runs
    # before filldb, so the database still holds the previous build's data.
    compilations = frozenset(
        pl.scan_ndjson(
            games_file,
            schema={"bgg_id": pl.Int64, "compilation": pl.Boolean},
        )
        .filter(pl.col("compilation"))
        .collect()["bgg_id"]
        .to_list()
    )

    rankings = calculate_rankings(
        recommender=recommender,
        ratings_path=path_ratings,
        top=top,
        min_ratings=min_ratings,
        exclude_games=compilations,
    )

    LOGGER.info("Calculated R.G rankings for %d games", len(rankings))

    _remove(dst_path)
    dst_dir.mkdir(parents=True, exist_ok=True)

    # The published ranking is the trust-weighted one; the unweighted variant is
    # carried alongside as "raw".
    rankings = rankings.rename(
        {
            "rank": "rank_raw",
            "score": "score_raw",
            "rank_weighted": "rank",
            "score_weighted": "score",
        }
    ).select(
        "rank",
        "bgg_id",
        "score",
        "rank_raw",
        "score_raw",
        "avg_rating",
        "num_votes",
    )

    rankings.sort("rank").write_csv(dst_path)


@task()
def savebggrankings(
    c,
    recommender_path=os.path.join(RECOMMENDER_DIR, ".bgg.light.npz"),
    ratings_path=Path(SCRAPED_DATA_DIR).resolve() / "scraped" / "bgg_RatingItem.jl",
    games_file=Path(SCRAPED_DATA_DIR).resolve() / "scraped" / "bgg_GameItem.jl",
    dst_dir=os.path.join(SCRAPED_DATA_DIR, "rankings", "bgg"),
    file_name=f"{DATE_FORMAT_COMPACT}.csv",
    top_k_games=100,
    min_ratings=10,
):
    """Take a snapshot of the BoardGameGeek rankings."""
    from games.utils import load_recommender

    recommender_path = Path(recommender_path).resolve()
    ratings_path = Path(ratings_path).resolve()
    dst_dir = Path(dst_dir).resolve()
    top_k_games = parse_int(top_k_games) or 100
    min_ratings = parse_int(min_ratings) or 10

    LOGGER.info("Loading BoardGameGeek recommender from <%s>...", recommender_path)
    # trainbgg may have just rewritten this file in the same process, and
    # load_recommender is lru_cache'd -- drop the cache so we read from disk.
    load_recommender.cache_clear()
    recommender = load_recommender(recommender_path)
    if recommender is None:
        raise ValueError(f"Unable to load recommender from <{recommender_path}>")

    _save_rg_ranking(
        recommender=recommender,
        path_ratings=ratings_path,
        games_file=Path(games_file).resolve(),
        top=top_k_games,
        min_ratings=min_ratings,
        dst_dir=dst_dir / "r_g",
        file_name=file_name,
    )


@task()
def weeklycharts(
    c,
    src_file=Path(SCRAPED_DATA_DIR) / "scraped" / "bgg_RatingItem.jl",
    dst_dir=Path(SCRAPED_DATA_DIR) / "rankings" / "bgg" / "charts",
    dst_file=f"{DATE_FORMAT_COMPACT}.csv",
    overwrite=False,
):
    """Generate charts files."""

    src_file = Path(src_file).resolve()
    dst_dir = Path(dst_dir).resolve()
    max_date = snap(django.utils.timezone.now(), "@week5@week1")
    latest_file = dst_dir / max_date.strftime(dst_file)
    overwrite = parse_bool(overwrite)

    if not overwrite and latest_file.exists():
        LOGGER.info(
            "Latest charts at <%s> already exist, skipping chart generation",
            latest_file,
        )
        return

    django.core.management.call_command(
        "charts",
        src_file,
        max_date=max_date,
        freq="week",
        out_dir=dst_dir,
        overwrite=overwrite,
    )


@task()
def cleandata(c, src_dir=DATA_DIR, bk_dir=f"{DATA_DIR}.bk"):
    """clean data file"""
    LOGGER.info(
        "Removing old backup dir <%s> (if any), moving current data dir to backup, "
        "and creating fresh data dir <%s>...",
        bk_dir,
        src_dir,
    )
    if DRY_RUN:
        LOGGER.info("[DRY RUN] Would rotate <%s> to <%s>", src_dir, bk_dir)
        return
    shutil.rmtree(bk_dir, ignore_errors=True)
    if os.path.exists(src_dir):
        os.rename(src_dir, bk_dir)
    os.makedirs(src_dir)


@task()
def migrate(
    c,
):
    """database migration"""
    assert not SETTINGS.DEBUG
    if DRY_RUN:
        LOGGER.info("[DRY RUN] Would run migrations")
        return
    django.core.management.call_command("migrate")


@task(cleandata, gitprepareconfig, migrate)
def filldb(
    c,
    src_dir=SCRAPED_DATA_DIR,
    ranking_date=getattr(SETTINGS, "R_G_RANKING_EFFECTIVE_DATE", None),
    dry_run=False,
):
    """fill database"""
    LOGGER.info(
        "Uploading games and other data from <%s> to database...",
        src_dir,
    )

    srp_dir = os.path.join(src_dir, "scraped")
    dry_run = parse_bool(dry_run) or DRY_RUN

    django.core.management.call_command(
        "filldb",
        os.path.join(srp_dir, "bgg_GameItem.jl"),
        collection_paths=[os.path.join(srp_dir, "bgg_RatingItem.jl")],
        user_paths=[os.path.join(srp_dir, "bgg_UserItem.jl")],
        premium_user_dirs=[os.path.join(CONFIG_DIR, "users", "premium")],
        premium_user_paths=[os.path.join(BASE_DIR, "config", "premium.yaml")],
        in_format="jl",
        batch=100_000,
        rankings=Path(SCRAPED_DATA_DIR) / "rankings" / "bgg" / "r_g",
        ranking_date=ranking_date,
        links=os.path.join(src_dir, "links.json"),
        dry_run=dry_run,
    )


@task()
def kennerspiel(
    c,
    model_path=Path(MODELS_DIR) / "kennerspiel.joblib",
    batch_size=10_000,
    dry_run=False,
):
    """Calculate Kennerspiel scores and add them to the database."""

    model_path = Path(model_path).resolve()
    batch_size = parse_int(batch_size)
    dry_run = parse_bool(dry_run) or DRY_RUN

    LOGGER.info(
        "Calculate Kennerspiel scores with model <%s> and write them to the database",
        model_path,
    )

    django.core.management.call_command(
        "kennerspiel",
        model_path,
        batch=batch_size,
        dry_run=dry_run,
    )


@task()
def compressdb(c, db_file=os.path.join(DATA_DIR, "db.sqlite3")):
    """compress SQLite database file"""
    execute("sqlite3", db_file, "VACUUM;")


@task()
def cplight(
    c,
    src_path=os.path.join(RECOMMENDER_DIR, ".bgg.light.npz"),
    dst_path=os.path.join(DATA_DIR, "recommender_light.npz"),
):
    """Copy a light recommender file."""
    LOGGER.info("Copying <%s> to <%s>...", src_path, dst_path)
    shutil.copy2(src_path, dst_path)


@task()
def dateflag(c, dst=SETTINGS.MODEL_UPDATED_FILE, date=None):
    """write date to file"""
    from games.utils import serialize_date

    date = parse_date(date) or django.utils.timezone.now()
    date_str = serialize_date(date, tzinfo=UTC)
    LOGGER.info("Writing date <%s> to <%s>...", date_str, dst)
    with open(dst, "w", encoding="utf-8") as file:
        file.write(date_str)


@task()
def bggranking(
    c,
    dst=os.path.join(
        SCRAPED_DATA_DIR,
        "rankings",
        "bgg",
        "bgg",
        f"{DATE_FORMAT_COMPACT}.csv",
    ),
):
    """Saves a snapshot of the BGG rankings."""
    from games.utils import model_updated_at

    updated_at = model_updated_at() or django.utils.timezone.now()
    dst = updated_at.strftime(dst)
    django.core.management.call_command("bggranking", output=dst)


@task()
def historicalbggrankings(
    c,
    repo=os.path.abspath(os.path.join(BASE_DIR, "..", "bgg-ranking-historicals")),
    dst=os.path.join(
        SCRAPED_DATA_DIR,
        "rankings",
        "bgg",
        "bgg",
        f"{DATE_FORMAT_COMPACT}.csv",
    ),
    script=os.path.join(BASE_DIR, "scripts", "ranking.sh"),
    overwrite=False,
):
    """Save historical BGG rankings."""

    from games.utils import format_from_path

    LOGGER.info("Loading historical BGG rankings from <%s>...", repo)

    overwrite = parse_bool(overwrite)

    try:
        with safe_cd(repo):
            try:
                execute("git", "checkout", "master")
                execute("git", "pull", "--ff-only")
            except Exception:
                LOGGER.exception(
                    "There was a problem updating BGG rankings repo <%s>",
                    repo,
                )

            for root, _, files in os.walk("."):
                for file in files:
                    if format_from_path(file) != "csv":
                        continue

                    date_str, _ = os.path.splitext(file)
                    date = parse_date(
                        date_str,
                        tzinfo=UTC,
                        format_str=DATE_FORMAT_DASH,
                    )
                    if date is None:
                        continue

                    in_path = os.path.abspath(os.path.join(root, file))
                    dst_path = date.strftime(dst)

                    if not overwrite and os.path.exists(dst_path):
                        LOGGER.debug(
                            "Output file <%s> already exists, skipping <%s>...",
                            dst_path,
                            in_path,
                        )
                        continue

                    LOGGER.info(
                        "Reading from file <%s> and writing to <%s>...",
                        in_path,
                        dst_path,
                    )
                    execute("bash", script, in_path, dst_path)
    except Exception:
        LOGGER.exception(
            "There was a problem loading historical BGG rankings from <%s>",
            repo,
        )


@task()
def fillrankingdb(c, path=os.path.join(SCRAPED_DATA_DIR, "rankings", "bgg")):
    """Parses the ranking CSVs and writes them to the database."""
    django.core.management.call_command("fillrankingdb", path)


@task()
def deduplicate(c, rankings_path=os.path.join(SCRAPED_DATA_DIR, "rankings")):
    """Deduplicate rankings files."""
    rankings_path = Path(rankings_path).resolve()
    LOGGER.info("Finding sub dirs in <%s>", rankings_path)
    sub_dirs = (d for d in rankings_path.iterdir() if d.is_dir())
    paths = (d2 for d1 in sub_dirs for d2 in d1.iterdir() if d2.is_dir())
    django.core.management.call_command("deduplicate", *paths)


@task()
def updatecount(
    c,
    dst=os.path.join(SCRAPED_DATA_DIR, "COUNT.md"),
    template=os.path.join(BASE_DIR, "templates", "COUNT.md"),
    paths_lines=os.path.join(SCRAPED_DATA_DIR, "scraped"),
    line_glob="*.jl",
    paths_files=os.path.join(SCRAPED_DATA_DIR, "rankings"),
    file_glob="*.csv",
):
    """Update the line and file counts in the destination file."""

    from games.utils import count_lines_and_files

    counts = count_lines_and_files(
        paths_lines=paths_lines,
        line_glob=line_glob,
        paths_files=paths_files,
        file_glob=file_glob,
    )

    now = django.utils.timezone.now()
    counts["date"] = now.date().isoformat()
    counts["date_iso"] = now.isoformat(timespec="seconds")

    template = Path(template).resolve()
    dst = Path(dst).resolve()
    dst.parent.mkdir(parents=True, exist_ok=True)
    LOGGER.info("Reading template from <%s>, writing result to <%s>...", template, dst)

    with (
        template.open(encoding="utf-8") as template_file,
        dst.open("w", encoding="utf-8") as dst_file,
    ):
        template_str = template_file.read()
        count_str = template_str.format(**counts)
        dst_file.write(count_str)


@task()
def makecsvs(
    c,
    in_dir=os.path.join(SCRAPED_DATA_DIR, "scraped"),
    glob="*_GameItem.jl",
    file_ext=".csv",
    columns=GAMES_CSV_COLUMNS,
    joiner=",",
    exclude=(
        "bgg_hotness_GameItem.jl",
        "bgg_rankings_GameItem.jl",
        "bgg_rankings_abstract_GameItem.jl",
        "bgg_rankings_children_GameItem.jl",
        "bgg_rankings_customizable_GameItem.jl",
        "bgg_rankings_family_GameItem.jl",
        "bgg_rankings_party_GameItem.jl",
        "bgg_rankings_strategy_GameItem.jl",
        "bgg_rankings_thematic_GameItem.jl",
        "bgg_rankings_war_GameItem.jl",
    ),
):
    """Create CSV versions of JSON lines files in in_dir."""

    from games.utils import jl_to_csv

    in_dir = Path(in_dir)
    exclude = frozenset(arg_to_iter(exclude))
    LOGGER.info("Processing JSON lines files in <%s>, excluding %s...", in_dir, exclude)

    for in_path in in_dir.rglob(glob):
        if os.path.basename(in_path) in exclude:
            LOGGER.info("Skipping <%s>...", in_path)
        else:
            out_path = os.path.splitext(in_path)[0] + file_ext
            jl_to_csv(
                in_path=in_path,
                out_path=out_path,
                columns=columns,
                joiner=joiner,
            )


@task()
def referencecsvs(
    c,
    in_file=os.path.join(SCRAPED_DATA_DIR, "scraped", "bgg_GameItem.jl"),
    out_dir=os.path.join(SCRAPED_DATA_DIR, "scraped"),
    out_file="bgg_{entity}.csv",
):
    """Parse a file for foreign references and store those in separate CSVs."""
    LOGGER.info("Parsing <%s> for foreign references", in_file)
    django.core.management.call_command(
        "referencecsvs",
        in_file,
        out_dir=out_dir,
        out_file=out_file,
    )


@task()
def sitemap(c, url=URL_LIVE, dst=os.path.join(DATA_DIR, "sitemap.xml"), limit=50_000):
    """Generate sitemap.xml."""
    limit = parse_int(limit) or 50_000
    LOGGER.info(
        "Generating sitemap with URL <%s> to <%s>, limit to %d...",
        url,
        dst,
        limit,
    )
    django.core.management.call_command("sitemap", url=url, limit=limit, output=dst)


@task(
    cleandata,
    filldb,
    kennerspiel,
    dateflag,
    compressdb,
    cplight,
    sitemap,
)
def builddb(
    c,
):
    """build a new database"""


@task(
    gitprepare,
    mergeall,
    makecsvs,
    referencecsvs,
    trainbgg,
    savebggrankings,
    historicalbggrankings,
    weeklycharts,
    builddb,
    deduplicate,
    updatecount,
    gitupdate,
)
def builddbfull(
    c,
):
    """merge, link, train, and build, all relevant files"""


@task()
def cleanstatic(c, base_dir=BASE_DIR, sub_dirs=None):
    """clean static files"""
    sub_dirs = sub_dirs or (".temp", "static")
    for sub_dir in sub_dirs:
        target = os.path.join(base_dir, sub_dir)
        if DRY_RUN:
            LOGGER.info("[DRY RUN] Would remove dir <%s>", target)
            continue
        LOGGER.info("Removing dir <%s>...", target)
        shutil.rmtree(target, ignore_errors=True)


@task()
def minify(c, src=os.path.join(BASE_DIR, "app"), dst=os.path.join(BASE_DIR, ".temp")):
    """copy front-end files and minify HTML, JavaScript, and CSS"""
    LOGGER.info("Copying and minifying files from <%s> to <%s>...", src, dst)
    django.core.management.call_command(
        "minify",
        src,
        dst,
        delete=True,
        exclude_dot=True,
    )


@task()
def cpsitemap(
    c,
    src_path=os.path.join(DATA_DIR, "sitemap.xml"),
    dst_path=os.path.join(BASE_DIR, ".temp", "sitemap.xml"),
):
    """Copy the sitemap into the static files dir."""

    if not os.path.isfile(src_path):
        raise FileNotFoundError(
            f"Sitemap <{src_path}> does not exist, run the `sitemap` task first"
        )

    LOGGER.info("Copying <%s> to <%s>...", src_path, dst_path)
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    shutil.copy2(src_path, dst_path)


@task(cleanstatic, minify, cpsitemap)
def collectstatic(c, delete=True):
    """Collect static files."""

    assert not SETTINGS.DEBUG

    static_dirs = SETTINGS.STATICFILES_DIRS
    LOGGER.info("Collecting static files from %s...", static_dirs)
    django.core.management.call_command("collectstatic", no_input=True)

    if not parse_bool(delete):
        return

    for static_dir in static_dirs:
        LOGGER.info("Removing static dir <%s>...", static_dir)
        shutil.rmtree(static_dir, ignore_errors=True)


@task(collectstatic)
def buildserver(c, images=None, tags=None):
    """build Docker image"""

    images = images or (f"registry.heroku.com/{HEROKU_APP}/web",)
    version = _server_version()
    date = django.utils.timezone.now().strftime(DATE_FORMAT_COMPACT)
    tags = tags or (f"{version}-{date}", "latest")
    all_tags = [f"{i}:{t}" for i in images if i for t in tags if t]

    LOGGER.info("Building Docker image with tags %s...", all_tags)

    command = ["docker", "build", "--platform", "linux/amd64"]
    for tag in all_tags:
        command.extend(("--tag", tag))
    command.append(".")

    with safe_cd(BASE_DIR):
        execute(*command)

        if not version:
            return

        LOGGER.info("Adding Git tag <v%s> if it doesn't exist", version)
        try:
            execute("git", "tag", f"v{version}")
        except Exception:
            pass  # tag already exists


@task()
def pushserver(c, image=None):
    """push Docker image to remote repo"""
    image = image or f"registry.heroku.com/{HEROKU_APP}/web"
    LOGGER.info("Pushing Docker image <%s> to repo…", image)
    execute("heroku", "container:login")
    execute("docker", "push", image)


@task(buildserver, pushserver)
def releaseserver(c, heroku_app=HEROKU_APP):
    """build, push, and deploy new server version"""
    LOGGER.info("Releasing new version of Heroku app <%s>…", heroku_app)
    execute("heroku", "container:release", f"--app={heroku_app}", "--verbose", "web")


@task(builddb, buildserver)
def build(
    c,
):
    """build database and server"""


@task(builddbfull, buildserver)
def buildfull(
    c,
):
    """merge, link, train, and build database and server"""


@task(builddb, releaseserver)
def release(
    c,
):
    """release database and server"""


@task(builddbfull, releaseserver)
def releasefull(
    c,
):
    """merge, link, train, build, and release database and server"""


@task()
def lintshell(c, base_dir=BASE_DIR):
    """lint Shell scripts"""
    execute("find", base_dir, "-iname", "*.sh", "-ls", "-exec", "shellcheck", "{}", ";")


@task()
def lintdocker(c, base_dir=BASE_DIR):
    """Lint Dockerfiles."""
    execute(
        "find",
        base_dir,
        "-iname",
        "Dockerfile*",
        "-ls",
        "-exec",
        "hadolint",
        "{}",
        ";",
    )


@task()
def lintmarkdown(c, base_dir=BASE_DIR):
    """Lint Markdown documents."""
    execute(
        "find",
        base_dir,
        "-iname",
        "*.md",
        "-ls",
        "-exec",
        "markdownlint",
        "{}",
        ";",
    )
    execute("find", base_dir, "-iname", "*.md", "-ls", "-exec", "mdl", "{}", ";")


@task()
def lintpy(c, *modules):
    """lint Python files"""
    modules = modules or ("games", "rg", "build.py", "manage.py")
    with safe_cd(BASE_DIR):
        execute("black", "--diff", "--exclude", "/migrations/", *modules)
        execute("pylint", "--exit-zero", *modules)


@task()
def linthtml(
    c,
):
    """lint HTML files"""
    with safe_cd(os.path.join(BASE_DIR, "app")):
        execute("htmlhint", "--ignore", "google*.html,yandex*.html")
        # execute('htmllint')


@task()
def lintjs(
    c,
):
    """lint JavaScript files"""
    with safe_cd(os.path.join(BASE_DIR, "app")):
        execute("jslint", "js/*.js")
        execute("jshint", "js")


@task()
def lintcss(
    c,
):
    """lint JavaScript files"""
    with safe_cd(os.path.join(BASE_DIR, "app")):
        execute("csslint", "app.css")


@task(
    lintshell,
    lintdocker,
    lintmarkdown,
    lintpy,
    linthtml,
    lintjs,
    lintcss,
    default=True,
)
def lint(c):
    """lint everything"""
