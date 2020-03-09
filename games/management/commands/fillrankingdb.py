# -*- coding: utf-8 -*-

"""Parses the ranking CSVs and writes them to the database."""

import csv
import logging
import os
import sys

from datetime import timezone
from functools import lru_cache
from itertools import groupby
from pathlib import Path

import pandas as pd

from django.core.management.base import BaseCommand
from pytility import batchify, parse_date
from snaptime import snap

from ...models import Game, Ranking
from ...utils import format_from_path

csv.field_size_limit(sys.maxsize)

LOGGER = logging.getLogger(__name__)
WEEK_DAYS = ("SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT")


@lru_cache(maxsize=128)
def _week_day_number(day):
    if not isinstance(day, str):
        return None
    try:
        return WEEK_DAYS.index(day.upper())
    except Exception:
        pass
    return None


@lru_cache(maxsize=128)
def _make_instruction(day):
    day_number = day if isinstance(day, int) else _week_day_number(day)
    return f"@w{day_number + 1}+1w-1d" if isinstance(day_number, int) else day


def _following(date, week_day="SUN", tzinfo=timezone.utc):
    date = parse_date(date, tzinfo=tzinfo).astimezone(tzinfo)
    instruction = _make_instruction(week_day)
    return snap(date, instruction).date()


def _extract_date(path_file, tzinfo=timezone.utc):
    file_name = os.path.basename(path_file)
    date_str, _ = os.path.splitext(file_name)
    return parse_date(date_str, tzinfo=tzinfo)


def parse_ranking_csv(path_file, date=None, tzinfo=timezone.utc):
    """Parses a ranking CSV file."""

    LOGGER.info("Reading ranking from <%s>...", path_file)

    date = _extract_date(path_file=path_file, tzinfo=tzinfo) if date is None else date

    ranking = pd.read_csv(path_file)
    ranking["date"] = date

    return ranking


def parse_ranking_csvs(path_dir, week_day="SUN", tzinfo=timezone.utc):
    """Parses all ranking CSV files in a directory."""

    path_dir = Path(path_dir)
    LOGGER.info("Iterating through all CSV files in <%s>...", path_dir)

    files = (file for file in path_dir.iterdir() if format_from_path(file) == "csv")
    files = (
        (_extract_date(path_file=file, tzinfo=tzinfo), file) for file in sorted(files)
    )

    for group_date, group in groupby(
        files,
        key=lambda pair: _following(date=pair[0], week_day=week_day, tzinfo=tzinfo),
    ):
        LOGGER.info("Processing rankings from the week ending in %s...", group_date)
        dfs = (
            parse_ranking_csv(path_file=path_file, date=date)
            for date, path_file in group
        )
        yield group_date, pd.concat(dfs, ignore_index=True)


def _last_ranking(data, date=None):
    data.sort_values(["bgg_id", "date"], inplace=True)
    groups = data.groupby("bgg_id")
    rankings = groups.last()
    rankings.reset_index(inplace=True)
    rankings.sort_values("rank", inplace=True)
    if date is not None:
        rankings["date"] = date
    return rankings


def _avg_ranking(data, date=None):
    groups = data.groupby("bgg_id")
    rankings = groups["score"].mean().reset_index()
    rankings.sort_values("score", ascending=False, inplace=True)
    rankings["rank"] = range(1, len(rankings) + 1)
    if date is not None:
        rankings["date"] = date
    return rankings


def _create_instances(
    path_dir, ranking_type=Ranking.BGG, filter_ids=None, method="last", week_day="SUN"
):
    LOGGER.info(
        "Finding all rankings of type <%s> in <%s>, aggregating <%s>...",
        ranking_type,
        path_dir,
        method,
    )

    for date, week in parse_ranking_csvs(path_dir, week_day=week_day):
        rankings = (
            _avg_ranking(week, date=date)
            if method == "mean"
            else _last_ranking(week, date=date)
        )
        for item in rankings.itertuples(index=False):
            if filter_ids is None or item.bgg_id in filter_ids:
                yield Ranking(
                    game_id=item.bgg_id,
                    ranking_type=ranking_type,
                    rank=item.rank,
                    date=item.date,
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
            choices=WEEK_DAYS,
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
