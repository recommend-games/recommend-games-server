# -*- coding: utf-8 -*-

"""TODO."""

import json
import logging
import os
import sys

from itertools import groupby

import pandas as pd

from django.core.management.base import BaseCommand
from pytility import parse_date

LOGGER = logging.getLogger(__name__)


def _parse_json(line):
    try:
        return json.loads(line)
    except Exception:
        pass
    return None


def _process_row(row):
    row["published_at"] = parse_date(row.get("published_at"))
    return row


def _process_file(file):
    if isinstance(file, str):
        with open(file) as file_obj:
            yield from _process_file(file_obj)

    for row in filter(None, map(_parse_json, file)):
        yield _process_row(row)


def _process_files(files):
    for file in files:
        yield from _process_file(file)


def _process_df(data_frame):
    if data_frame is None or data_frame.empty:
        LOGGER.error("DataFrame is empty")
        return None

    columns = ["rank", "bgg_id", "bayes_rating"]
    if any(column not in data_frame for column in columns):
        LOGGER.error("DataFrame does not contain the expected columns")
        return None

    return (
        data_frame[columns][~data_frame["rank"].isna()]
        .sort_values("rank")
        .rename(columns={"bayes_rating": "score"})
        .astype({"rank": int, "bgg_id": int})
    )


class Command(BaseCommand):
    """TODO."""

    help = "TODO."

    def add_arguments(self, parser):
        parser.add_argument("in_files", nargs="+")
        parser.add_argument("--out-dir", "-o", default=".")
        parser.add_argument("--out-file", "-O", default="%Y%m%d-%H%M%S.csv")
        # parser.add_argument("--window", "-w", type=float)
        parser.add_argument("--dry-run", "-n", action="store_true")

    def handle(self, *args, **kwargs):
        logging.basicConfig(
            stream=sys.stderr,
            level=logging.DEBUG if kwargs["verbosity"] > 1 else logging.INFO,
            format="%(asctime)s %(levelname)-8.8s [%(name)s:%(lineno)s] %(message)s",
        )

        LOGGER.info(kwargs)

        out_template = os.path.join(kwargs["out_dir"], kwargs["out_file"])

        for published_at, group in groupby(
            _process_files(kwargs["in_files"]), key=lambda row: row.get("published_at")
        ):
            data_frame = _process_df(pd.DataFrame.from_records(group))

            if data_frame is None:
                continue

            out_path = published_at.strftime(out_template)

            LOGGER.info("Saving <%d> rows to <%s>...", len(data_frame), out_path)

            if not kwargs["dry_run"]:
                # TODO make sure output dir exists
                # TODO check if file exists
                data_frame.to_csv(out_path, index=False)
