# -*- coding: utf-8 -*-

"""Split rankings from a GameItem file into separate CSVs."""

import json
import logging
import os
import sys

from pathlib import Path
from itertools import groupby

import pandas as pd

from django.core.management.base import BaseCommand
from pytility import arg_to_iter, clear_list, parse_date

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
    if isinstance(file, (str, Path)):
        LOGGER.info("Loading rows from <%s>...", file)
        with open(file) as file_obj:
            yield from _process_file(file_obj)
        return

    for row in filter(None, map(_parse_json, file)):
        yield _process_row(row)


def _process_files(files):
    for file in files:
        file = Path(file).resolve()
        yield from _process_file(file)


def _process_df(data_frame, columns, target_column=None):
    if data_frame is None or data_frame.empty:
        LOGGER.error("DataFrame is empty")
        return None

    columns = clear_list(arg_to_iter(columns))
    if not columns:
        LOGGER.error("No columns given")
        return None

    if any(column not in data_frame for column in columns):
        LOGGER.error("DataFrame does not contain the expected columns")
        return None

    target_column = target_column or columns[0]
    return (
        data_frame[columns][data_frame[target_column].notna()]
        .sort_values(target_column)
        .rename(columns={"bayes_rating": "score"})
        .astype({"rank": int, "bgg_id": int})
    )


class Command(BaseCommand):
    """Split rankings from a GameItem file into separate CSVs."""

    help = "Split rankings from a GameItem file into separate CSVs."

    def add_arguments(self, parser):
        parser.add_argument("in_files", nargs="+")
        parser.add_argument("--out-dir", "-o", default=".")
        parser.add_argument("--out-file", "-O", default="%Y%m%d-%H%M%S.csv")
        parser.add_argument(
            "--columns", "-c", nargs="+", default=("rank", "bgg_id", "bayes_rating")
        )
        parser.add_argument("--target-column", "-t")
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
        if not kwargs["dry_run"]:
            out_dir.mkdir(parents=True, exist_ok=True)
            assert out_dir.is_dir()
        LOGGER.info("Write results to dir <%s>", out_dir)
        out_template = os.path.join(out_dir, kwargs["out_file"])

        for published_at, group in groupby(
            _process_files(kwargs["in_files"]), key=lambda row: row.get("published_at")
        ):
            out_path = published_at.strftime(out_template)

            if not kwargs["overwrite"] and os.path.exists(out_path):
                LOGGER.debug(
                    "Output file <%s> already exists, skipping <%s>...",
                    out_path,
                    published_at,
                )
                continue

            data_frame = _process_df(
                data_frame=pd.DataFrame.from_records(group),
                columns=kwargs["columns"],
                target_column=kwargs["target_column"],
            )

            if data_frame is None:
                continue

            LOGGER.info("Saving <%d> rows to <%s>...", len(data_frame), out_path)

            if not kwargs["dry_run"]:
                data_frame.to_csv(out_path, index=False)
