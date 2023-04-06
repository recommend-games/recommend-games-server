""" utils """

import json
import logging
import os.path
import re
import timeit
from csv import DictWriter
from datetime import timezone
from functools import lru_cache, partial
from pathlib import Path

from django.conf import settings
from pytility import arg_to_iter, normalize_space, parse_date

LOGGER = logging.getLogger(__name__)
VERSION_REGEX = re.compile(r"^\D*(.+)$")


def format_from_path(path):
    """get file extension"""
    try:
        _, ext = os.path.splitext(path)
        return ext.lower()[1:] if ext else None
    except Exception:
        pass
    return None


def serialize_date(date, tzinfo=None):
    """seralize a date into ISO format if possible"""
    parsed = parse_date(date, tzinfo)
    return parsed.strftime("%Y-%m-%dT%T%z") if parsed else str(date) if date else None


@lru_cache(maxsize=8)
def load_recommender(path, site="bgg"):
    """load recommender from given path"""

    if not path:
        return None

    try:
        if site == "light":
            from board_game_recommender import LightGamesRecommender

            LOGGER.info("Trying to load <LightGamesRecommender> from <%s>", path)
            return LightGamesRecommender.from_npz(path)

        if site == "bga":
            from board_game_recommender import BGARecommender

            LOGGER.info("Trying to load <BGARecommender> from <%s>", path)
            return BGARecommender.load(path=path)

        from board_game_recommender import BGGRecommender

        LOGGER.info("Trying to load <BGGRecommender> from <%s>", path)
        return BGGRecommender.load(path=path)

    except Exception:
        LOGGER.exception("unable to load recommender model from <%s>", path)

    return None


@lru_cache(maxsize=8)
def pubsub_client():
    """Google Cloud PubSub client"""

    try:
        from google.cloud import pubsub

        return pubsub.PublisherClient()

    except Exception:
        LOGGER.exception("unable to initialise PubSub client")

    return None


def pubsub_push(
    *,
    message,
    project,
    topic,
    encoding="utf-8",
    **kwargs,
):
    """publish message"""

    if not project or not topic:
        return None

    client = pubsub_client()

    if client is None:
        return None

    if isinstance(message, str):
        message = message.encode(encoding)
    assert isinstance(message, bytes)

    # pylint: disable=no-member
    path = client.topic_path(project, topic)

    LOGGER.debug("pushing message %r to <%s>", message, path)

    try:
        return client.publish(topic=path, data=message, **kwargs)
    except Exception:
        LOGGER.exception("unable to send message %r", message)
    return None


@lru_cache(maxsize=8)
def model_updated_at(file_path=settings.MODEL_UPDATED_FILE):
    """latest model update"""
    try:
        with open(file_path, encoding="utf-8") as file_obj:
            updated_at = file_obj.read()
        updated_at = normalize_space(updated_at)
        return parse_date(updated_at, tzinfo=timezone.utc)
    except Exception:
        pass
    return None


def parse_version(version):
    """Parse a version string to strip leading "v" etc."""
    version = normalize_space(version)
    if not version:
        return None
    match = VERSION_REGEX.match(version)
    return match.group(1) if match else None


@lru_cache(maxsize=8)
def project_version(file_path=settings.PROJECT_VERSION_FILE):
    """Project version."""
    try:
        with open(file_path, encoding="utf-8") as file_obj:
            version = file_obj.read()
        return parse_version(version)
    except Exception:
        pass
    return None


@lru_cache(maxsize=8)
def server_version(file_path=settings.PROJECT_VERSION_FILE) -> dict:
    """Full server version."""
    release_version = project_version(file_path=file_path)
    heroku_version = parse_version(os.getenv("HEROKU_RELEASE_VERSION"))
    server_version = "-".join(filter(None, (release_version, heroku_version)))
    return {
        "project_version": release_version,
        "server_version": server_version or None,
    }


def save_recommender_ranking(recommender, dst, similarity_model=False):
    """Save the rankings generated by a recommender to a CSV file."""

    LOGGER.info(
        "Saving <%s> ranking to <%s>...",
        recommender.similarity_model if similarity_model else recommender.model,
        dst,
    )

    recommendations = recommender.recommend(similarity_model=similarity_model)
    if "name" in recommendations.column_names():
        recommendations.remove_column("name", inplace=True)

    if similarity_model:
        recommendations = recommendations[recommendations["score"] > 0]

    recommendations.export_csv(str(dst))


def count_lines(path) -> int:
    """Return the line count of a given path."""
    with open(path, encoding="utf-8") as file:
        return sum(1 for _ in file)


def count_files(path, glob=None) -> int:
    """Return the number of files in a given directory."""
    path = Path(path)
    files = path.glob(glob) if glob else path.iterdir()
    return sum(1 for file in files if file.is_file())


def count_lines_and_files(
    paths_lines=None,
    paths_files=None,
    line_glob=None,
    file_glob=None,
) -> dict:
    """Counts lines and files in the given paths."""

    result = {}

    for path in arg_to_iter(paths_lines):
        path = Path(path).resolve()
        if path.is_dir():
            files = path.glob(line_glob) if line_glob else path.iterdir()
        elif path.is_file():
            files = (path,)
        else:
            files = ()
        for file in files:
            LOGGER.info("Counting lines in <%s>...", file)
            name = os.path.splitext(file.name)[0]
            result[f"lc_{name}"] = count_lines(file)

    for path in arg_to_iter(paths_files):
        path = Path(path).resolve()
        if not path.is_dir():
            continue
        for subdir in path.glob("**"):
            LOGGER.info("Counting files in <%s>...", subdir)
            if path == subdir:
                name = path.name
            else:
                relative = subdir.relative_to(path)
                name = "_".join(relative.parts)
            result[f"fc_{name}"] = count_files(subdir, glob=file_glob)

    return result


def _process_value(value, joiner=","):
    if value is None:
        return ""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (list, tuple)):
        return joiner.join(
            str(v).rsplit(":", maxsplit=1)[-1]
            for v in value
            if v is not None and v != ""
        )
    return value


def _process_row(row, columns=None, joiner=","):
    if isinstance(row, str):
        row = json.loads(row)
    if columns is None:
        return {key: _process_value(value, joiner=joiner) for key, value in row.items()}
    return {
        column: _process_value(row.get(column), joiner=joiner) for column in columns
    }


def jl_to_csv(in_path, out_path, columns=None, joiner=","):
    """Convert a JSON lines file into CSV."""

    columns = tuple(arg_to_iter(columns))

    LOGGER.info(
        "Reading JSON lines from <%s> and writing CSV to <%s>...", in_path, out_path
    )

    with open(in_path, encoding="utf-8") as in_file, open(
        out_path,
        "w",
        encoding="utf-8",
    ) as out_file:
        if not columns:
            row = next(in_file, None)
            row = _process_row(row, joiner=joiner) if row else {}
            columns = tuple(row.keys())
        else:
            row = None

        rows = map(partial(_process_row, columns=columns, joiner=joiner), in_file)

        writer = DictWriter(out_file, fieldnames=columns)
        writer.writeheader()
        if row:
            writer.writerow(row)
        writer.writerows(rows)


class Timer:
    """log execution time: with Timer('message'): do_something()"""

    def __init__(self, message, logger=None):
        self.message = f'"{message}" execution time: %.1f ms'
        self.logger = logger
        self.start = None

    def __enter__(self):
        self.start = timeit.default_timer()
        return self

    def __exit__(self, *args, **kwargs):
        duration = 1000 * (timeit.default_timer() - self.start)
        if self.logger is None:
            print(self.message % duration)
        else:
            self.logger.info(self.message, duration)
