# -*- coding: utf-8 -*-

"""TODO."""

import json
import logging
import sys

from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from django.core.management.base import BaseCommand
from pytility import arg_to_iter, parse_date

from ...utils import Timer

LOGGER = logging.getLogger(__name__)


def _process_ratings(lines, keys=("bgg_id", "bgg_user_rating", "updated_at")):
    for line in lines:
        item = json.loads(line)

        if not item or any(not item.get(key) for key in keys):
            LOGGER.debug("Invalid data: %s", line[:100])
            continue

        yield {
            k: parse_date(item.get(k), tzinfo=timezone.utc)
            if k.endswith("_at")
            else item.get(k)
            for k in keys
        }


def _ratings_data(path):
    path = Path(path).resolve()
    LOGGER.info("Reading ratings data from <%s>", path)
    with path.open() as file:
        data = pd.DataFrame.from_records(_process_ratings(file))
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
    days=30,
    percentiles=(0.25, 0.75),
    decay=False,
):
    """Calculate charts for the given timeframe."""

    end_date = end_date or datetime.utcnow().replace(tzinfo=timezone.utc)
    pct_lower, pct_upper = percentiles
    ratings = ratings[ratings["updated_at"] <= end_date]  # don't care past end date

    if decay:
        halflife = 60 * 60 * 24 * days  # convert to seconds
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
        window = timedelta(days=days)
        start_date = end_date - window
        recent_ratings = ratings[ratings["updated_at"] >= start_date]

        tmp = pd.DataFrame()
        tmp["positive"] = (
            recent_ratings[
                recent_ratings["bgg_user_rating"]
                >= recent_ratings["bgg_user_rating"].quantile(pct_upper)
            ]
            .groupby("bgg_id")["item_id"]
            .count()
        )
        tmp["negative"] = (
            recent_ratings[
                recent_ratings["bgg_user_rating"]
                <= recent_ratings["bgg_user_rating"].quantile(pct_lower)
            ]
            .groupby("bgg_id")["item_id"]
            .count()
        )
        tmp.fillna(0, inplace=True)
        raw_scores = tmp["positive"] - tmp["negative"]
        del recent_ratings, tmp

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


class Command(BaseCommand):
    """TODO."""

    help = "TODO."

    def add_arguments(self, parser):
        parser.add_argument("in_file")
        parser.add_argument("--out-dir", "-o", default=".")
        parser.add_argument("--out-file", "-O", default="%Y%m%d-%H%M%S.csv")
        parser.add_argument(
            "--columns", "-c", nargs="+", default=("rank", "bgg_id", "bayes_rating")
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

        columns = list(arg_to_iter(kwargs["columns"]))

        LOGGER.info(columns)

        with Timer(message="Loading ratings", logger=LOGGER):
            ratings = _ratings_data(kwargs["in_file"])

        min_date = ratings["updated_at"].min()
        max_date = ratings["updated_at"].max()

        LOGGER.info("Earliest date: %s; latest date: %s", min_date, max_date)
