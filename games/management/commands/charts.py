# -*- coding: utf-8 -*-

"""Generate board game charts from ratings data."""

import json
import logging
import sys

from datetime import datetime, timedelta, timezone
from itertools import islice, tee
from pathlib import Path

import numpy as np
import pandas as pd

from dateutil.rrule import MONTHLY, WEEKLY, YEARLY, rrule
from django.core.management.base import BaseCommand
from pytility import arg_to_iter, parse_date
from snaptime import snap
from tqdm import tqdm

from ...utils import Timer

LOGGER = logging.getLogger(__name__)


def _process_ratings(lines, keys=("bgg_id", "bgg_user_rating", "updated_at")):
    for line in tqdm(lines):
        item = json.loads(line)

        if not item or any(not item.get(key) for key in keys):
            continue

        yield {
            k: parse_date(item.get(k), tzinfo=timezone.utc)
            if k.endswith("_at")
            else item.get(k)
            for k in keys
        }


def _ratings_data(path, max_rows=None):
    path = Path(path).resolve()
    LOGGER.info("Reading ratings data from <%s>", path)
    with path.open() as file:
        lines = islice(file, max_rows) if max_rows else file
        data = pd.DataFrame.from_records(_process_ratings(lines))
    LOGGER.info("Read %d rows", len(data))
    return data


def exp_decay(
    dates,
    anchor=None,
    halflife=60 * 60 * 24 * 30,  # 30 days
):
    """Calculate exponential decay with given halflife."""
    anchor = anchor or datetime.utcnow().replace(tzinfo=timezone.utc)
    ages = (anchor - dates).total_seconds()
    return np.exp2(-ages / halflife)


def calculate_charts(
    ratings,
    end_date=None,
    start_date=None,
    days=30,
    percentiles=(0.25, 0.75),
    min_raw_score=None,
    decay=False,
) -> pd.DataFrame:
    """Calculate charts for the given timeframe."""

    end_date = end_date or datetime.utcnow().replace(tzinfo=timezone.utc)
    pct_lower, pct_upper = percentiles
    ratings = ratings[ratings["updated_at"] <= end_date]  # don't care past end date

    if decay:
        halflife = 60 * 60 * 24 * days  # convert to seconds
        LOGGER.debug(
            "Using exponential decay with a halflife of %.1f seconds", halflife
        )
        weights = exp_decay(
            dates=ratings["updated_at"], anchor=end_date, halflife=halflife
        )

        tmp = pd.DataFrame(
            data={
                "bgg_id": ratings["bgg_id"],
                "positive": np.where(
                    ratings["bgg_user_rating"]
                    >= ratings["bgg_user_rating"].quantile(pct_upper),
                    weights,
                    0,
                ),
                "negative": np.where(
                    ratings["bgg_user_rating"]
                    <= ratings["bgg_user_rating"].quantile(pct_lower),
                    weights,
                    0,
                ),
            }
        )

        grouped = tmp.groupby("bgg_id").sum()
        raw_scores = grouped["positive"] - grouped["negative"]
        del grouped, tmp, weights

    else:
        start_date = start_date or end_date - timedelta(days=days)
        LOGGER.debug("Considering ratings between %s and %s", start_date, end_date)
        recent_ratings = ratings[ratings["updated_at"] >= start_date]

        tmp = pd.DataFrame()
        tmp["positive"] = (
            recent_ratings[
                recent_ratings["bgg_user_rating"]
                >= recent_ratings["bgg_user_rating"].quantile(pct_upper)
            ]
            .groupby("bgg_id")["bgg_user_rating"]
            .count()
        )
        tmp["negative"] = (
            recent_ratings[
                recent_ratings["bgg_user_rating"]
                <= recent_ratings["bgg_user_rating"].quantile(pct_lower)
            ]
            .groupby("bgg_id")["bgg_user_rating"]
            .count()
        )
        tmp.fillna(0, inplace=True)
        raw_scores = tmp["positive"] - tmp["negative"]
        del recent_ratings, tmp

    if min_raw_score is not None:
        raw_scores = raw_scores[raw_scores >= min_raw_score]

    games = ratings.groupby("bgg_id")["bgg_user_rating"].count()
    scores = raw_scores * games.rank(pct=True, ascending=False)
    scores.dropna(inplace=True)

    ranking = pd.DataFrame(
        data={
            "rank": scores.rank(ascending=False, method="min").astype(int),
            "score": scores,
        },
        index=scores.index,
    )
    return ranking.sort_values("rank").reset_index()


def _pairwise(iterable):
    it1, it2 = tee(iterable)
    next(it2, None)
    return zip(it1, it2)


class Command(BaseCommand):
    """Generate board game charts from ratings data."""

    help = "Generate board game charts from ratings data."

    def add_arguments(self, parser):
        parser.add_argument("in_file")
        parser.add_argument("--min-date", "-d")
        parser.add_argument("--max-date", "-D")
        parser.add_argument(
            "--freq", "-f", choices=("week", "month", "year"), default="week"
        )
        parser.add_argument("--out-dir", "-o", default=".")
        parser.add_argument("--out-file", "-O", default="%Y%m%d-%H%M%S.csv")
        parser.add_argument("--max-rows", "-m", type=int)
        parser.add_argument(
            "--columns", "-c", nargs="+", default=("rank", "bgg_id", "score")
        )
        parser.add_argument("--overwrite", "-W", action="store_true")
        parser.add_argument("--dry-run", "-n", action="store_true")

    def handle(self, *args, **kwargs):
        logging.basicConfig(
            stream=sys.stderr,
            level=logging.DEBUG if kwargs["verbosity"] > 1 else logging.INFO,
            format="%(asctime)s %(levelname)-8.8s [%(name)s:%(lineno)s] %(message)s",
        )

        LOGGER.info(kwargs)

        out_dir = Path(kwargs["out_dir"]).resolve()
        LOGGER.info("Writing charts to <%s>", out_dir)
        if not kwargs["dry_run"]:
            out_dir.mkdir(parents=True, exist_ok=True)

        columns = list(arg_to_iter(kwargs["columns"]))

        with Timer(message="Loading ratings", logger=LOGGER):
            ratings = _ratings_data(path=kwargs["in_file"], max_rows=kwargs["max_rows"])

        min_date_args = parse_date(kwargs["min_date"], tzinfo=timezone.utc)
        min_date_ratings = ratings["updated_at"].min()
        min_date = (
            max(min_date_args, min_date_ratings) if min_date_args else min_date_ratings
        )
        max_date_args = parse_date(kwargs["max_date"], tzinfo=timezone.utc)
        max_date_ratings = ratings["updated_at"].max()
        max_date = (
            min(max_date_args, max_date_ratings) if max_date_args else max_date_ratings
        )

        LOGGER.info("Earliest date: %s; latest date: %s", min_date, max_date)

        if kwargs["freq"] == "week":
            instruction = "@week1"  # previous Monday
            freq = WEEKLY
            chart_str = "weekly"
            min_raw_score = 10
        elif kwargs["freq"] == "month":
            instruction = "@month"  # beginning of the month
            freq = MONTHLY
            chart_str = "monthly"
            min_raw_score = 25
        elif kwargs["freq"] == "year":
            instruction = "@year"  # beginning of the year
            freq = YEARLY
            chart_str = "annual"
            min_raw_score = 100

        for start_date, end_date in _pairwise(
            rrule(
                dtstart=snap(min_date, instruction),
                until=max_date,
                freq=freq,
            )
        ):
            LOGGER.info(
                "Calculating %s charts for %s", chart_str, end_date.strftime("%Y-%m-%d")
            )
            out_path = out_dir / end_date.strftime(kwargs["out_file"])

            if not kwargs["overwrite"] and out_path.exists():
                LOGGER.info("Output path <%s> exists, skipping...", out_path)
                continue

            charts = calculate_charts(
                ratings=ratings,
                start_date=start_date,
                end_date=end_date,
                min_raw_score=min_raw_score,
            )
            LOGGER.info("Found %d chart entries", len(charts))

            if not kwargs["dry_run"] and not charts.empty:
                LOGGER.info("Writing charts to <%s>", out_path)
                # pylint: disable=unsubscriptable-object
                charts[columns].to_csv(out_path, index=False)

        LOGGER.info("Done.")
