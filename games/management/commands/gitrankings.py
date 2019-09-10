# -*- coding: utf-8 -*-

"""Extract rankings from Git repositories."""

import json
import logging
import os
import sys

from datetime import timezone
from itertools import product

import pandas as pd

from django.core.management.base import BaseCommand
from git import Repo

from ...utils import arg_to_iter, format_from_path

LOGGER = logging.getLogger(__name__)


def _df_from_jl(rows):
    if isinstance(rows, str):
        with open(rows) as file:
            return _df_from_jl(file)

    return pd.DataFrame.from_records(map(json.loads, rows))


def _dfs_from_repo(repo, directories, files):
    LOGGER.info("Loading data from %s...", repo)
    for directory, file in product(arg_to_iter(directories), arg_to_iter(files)):
        path = os.path.join(directory, file)
        LOGGER.info("Looking for all versions of <%s>...", path)
        for commit in repo.iter_commits(paths=path):
            try:
                blob = commit.tree / directory / file
            except Exception:
                LOGGER.exception("Path <%s> not found in commit <%s>...", path, commit)
                continue

            LOGGER.info(
                'Found <%s> from commit <%s>: "%s" (%s)',
                blob,
                commit,
                commit.message,
                commit.authored_datetime,
            )

            file_format = format_from_path(blob.name)

            try:
                data_frame = (
                    pd.read_csv(blob.data_stream)
                    if file_format == "csv"
                    else _df_from_jl(blob.data_stream.read().splitlines())
                    if file_format in ("jl", "jsonl")
                    else None
                )
            except Exception:
                LOGGER.exception("There are a problem loading <%s>...", blob)
                data_frame = None

            if data_frame is not None and not data_frame.empty:
                yield {
                    "data_frame": data_frame,
                    "commit": commit,
                    "blob": blob,
                    "date": commit.authored_datetime,
                }


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
    )


class Command(BaseCommand):
    """Extract rankings from Git repositories."""

    help = "Extract rankings from Git repositories."

    def add_arguments(self, parser):
        parser.add_argument("repos", nargs="+")
        parser.add_argument("--out-dir", "-o", default=".")
        parser.add_argument("--out-file", "-O", default="%Y%m%d-%H%M%S.csv")
        parser.add_argument("--dirs", "-d", nargs="+", default=("results", "scraped"))
        parser.add_argument(
            "--files",
            "-f",
            nargs="+",
            default=("bgg.csv", "bgg_GameItem.csv", "bgg.jl", "bgg_GameItem.jl"),
        )
        parser.add_argument("--dry-run", "-n", action="store_true")

    def handle(self, *args, **kwargs):
        logging.basicConfig(
            stream=sys.stderr,
            level=logging.DEBUG if kwargs["verbosity"] > 1 else logging.INFO,
            format="%(asctime)s %(levelname)-8.8s [%(name)s:%(lineno)s] %(message)s",
        )

        LOGGER.info(kwargs)

        out_template = os.path.join(kwargs["out_dir"], kwargs["out_file"])

        for repo_path in kwargs["repos"]:
            repo = Repo(repo_path)
            for item in _dfs_from_repo(
                repo=repo, directories=kwargs["dirs"], files=kwargs["files"]
            ):
                data_frame = _process_df(item["data_frame"])

                if data_frame is None:
                    continue

                date = item["date"].astimezone(timezone.utc)
                out_path = date.strftime(out_template)

                LOGGER.info("Saving <%d> rows to <%s>...", len(data_frame), out_path)

                if not kwargs["dry_run"]:
                    # TODO make sure output dir exists
                    # TODO check if file exists
                    data_frame.to_csv(out_path, index=False)
