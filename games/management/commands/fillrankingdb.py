# -*- coding: utf-8 -*-

"""Parses the ranking CSVs and writes them to the database."""

import csv
import logging
import os
import sys

from datetime import timezone

import pandas as pd

from django.core.management.base import BaseCommand
from pytility import batchify

from ...models import Game, Ranking
from ...utils import format_from_path, parse_date

csv.field_size_limit(sys.maxsize)

LOGGER = logging.getLogger(__name__)


def parse_ranking_csv(path_file):
    """Parses a ranking CSV file."""

    LOGGER.info("Reading ranking from <%s>...", path_file)

    file_name = os.path.basename(path_file)
    date_str, _ = os.path.splitext(file_name)
    date = parse_date(date_str, tzinfo=timezone.utc)

    ranking = pd.read_csv(path_file)
    ranking["date"] = date

    return ranking


def parse_ranking_csvs(path_dir):
    """Parses all ranking CSV files in a directory."""

    LOGGER.info("Iterating through all CSV files in <%s>...", path_dir)

    for file_name in os.listdir(path_dir):
        if format_from_path(file_name) == "csv":
            yield parse_ranking_csv(os.path.join(path_dir, file_name))


def _last_ranking(data, week_day="SUN"):
    data.sort_values(["bgg_id", "date"], inplace=True)
    groups = data.groupby(["bgg_id", pd.Grouper(key="date", freq=f"W-{week_day}")])
    rankings = groups.last()
    rankings.reset_index(inplace=True)
    return rankings


def _add_rank(data):
    data.sort_values("score", ascending=False, inplace=True)
    data["rank"] = range(1, len(data) + 1)
    return data


def _avg_ranking(data, week_day="SUN"):
    groups = data.groupby(["bgg_id", pd.Grouper(key="date", freq=f"W-{week_day}")])
    scores = groups["score"].mean().reset_index()
    return scores.groupby("date").apply(_add_rank)


def _create_instances(
    path_dir, ranking_type=Ranking.BGG, filter_ids=None, method="last", week_day="SUN"
):
    LOGGER.info(
        "Finding all rankings of type <%s> in <%s>, aggregating <%s>...",
        ranking_type,
        path_dir,
        method,
    )

    # TODO it is inefficient to load all the rankings into memory, see #269
    data = pd.concat(parse_ranking_csvs(path_dir), ignore_index=True)
    rankings = (
        _avg_ranking(data, week_day=week_day)
        if method == "mean"
        else _last_ranking(data, week_day=week_day)
    )
    for item in rankings.itertuples(index=False):
        if filter_ids is None or item.bgg_id in filter_ids:
            yield Ranking(
                game_id=item.bgg_id,
                ranking_type=ranking_type,
                rank=item.rank,
                date=item.date.date(),
            )


class Command(BaseCommand):
    """Parses the ranking CSVs and writes them to the database."""

    help = "Parses the ranking CSVs and writes them to the database."

    ranking_types = {
        Ranking.BGG: ("bgg", "last"),
        Ranking.FACTOR: ("factor", "mean"),
        Ranking.SIMILARITY: ("similarity", "mean"),
    }

    def add_arguments(self, parser):
        parser.add_argument("path", help="input directory")
        parser.add_argument(
            "--batch",
            "-b",
            type=int,
            default=100_000,
            help="batch size for DB transactions",
        )
        parser.add_argument(
            "--week-day",
            "-w",
            default="SUN",
            choices=("SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"),
            help="anchor week day when aggregating weeks",
        )
        parser.add_argument(
            "--dry-run", "-n", action="store_true", help="don't write to the database"
        )

    def _create_all_instances(self, path, filter_ids=None, week_day="SUN"):
        for ranking_type, (sub_dir, method) in self.ranking_types.items():
            yield from _create_instances(
                path_dir=os.path.join(path, sub_dir),
                ranking_type=ranking_type,
                filter_ids=filter_ids,
                method=method,
                week_day=week_day,
            )

    def handle(self, *args, **kwargs):
        logging.basicConfig(
            stream=sys.stderr,
            level=logging.DEBUG if kwargs["verbosity"] > 1 else logging.INFO,
            format="%(asctime)s %(levelname)-8.8s [%(name)s:%(lineno)s] %(message)s",
        )

        LOGGER.info(kwargs)

        # pylint: disable=no-member
        game_ids = frozenset(Game.objects.order_by().values_list("bgg_id", flat=True))
        instances = self._create_all_instances(
            kwargs["path"], filter_ids=game_ids, week_day=kwargs["week_day"]
        )
        batches = (
            batchify(instances, kwargs["batch"]) if kwargs["batch"] else (instances,)
        )

        for count, batch in enumerate(batches):
            LOGGER.info("Processing batch #%d...", count + 1)
            if kwargs["dry_run"]:
                for item in batch:
                    print(item)
            else:
                Ranking.objects.bulk_create(batch)

        LOGGER.info("Done filling the database.")
