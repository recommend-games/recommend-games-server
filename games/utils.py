# -*- coding: utf-8 -*-

""" utils """

import logging
import os.path
import timeit

from datetime import datetime, timezone
from functools import lru_cache
from itertools import groupby

import dateutil.parser

from django.conf import settings

ITERABLE_SINGLE_VALUES = (dict, str, bytes)
LOGGER = logging.getLogger(__name__)


def arg_to_iter(arg):
    """ wraps arg into tuple if not an iterable """
    if arg is None:
        return ()
    if not isinstance(arg, ITERABLE_SINGLE_VALUES) and hasattr(arg, "__iter__"):
        return arg
    return (arg,)


def take_first(items):
    """ take first item """
    for item in arg_to_iter(items):
        if item is not None and item != "":
            return item
    return None


def batchify(iterable, size):
    """ make batches of given size """
    for _, group in groupby(enumerate(iterable), key=lambda x: x[0] // size):
        yield (x[1] for x in group)


def format_from_path(path):
    """ get file extension """
    try:
        _, ext = os.path.splitext(path)
        return ext.lower()[1:] if ext else None
    except Exception:
        pass
    return None


def parse_int(string, base=10):
    """ safely convert an object to int if possible, else return None """
    if isinstance(string, int):
        return string
    try:
        return int(string, base=base)
    except Exception:
        pass
    try:
        return int(string)
    except Exception:
        pass
    return None


def parse_float(number):
    """ safely convert an object to float if possible, else return None """
    try:
        return float(number)
    except Exception:
        pass
    return None


def parse_bool(item):
    """ parses an item and converts it to a boolean """
    if isinstance(item, int):
        return bool(item)
    if item in ("True", "true", "Yes", "yes"):
        return True
    integer = parse_int(item)
    if integer is not None:
        return bool(integer)
    return False


def _add_tz(date, tzinfo=None):
    return (
        date if not tzinfo or not date or date.tzinfo else date.replace(tzinfo=tzinfo)
    )


def parse_date(date, tzinfo=None, format_str=None):
    """try to turn input into a datetime object"""

    if not date:
        return None

    # already a datetime
    if isinstance(date, datetime):
        return _add_tz(date, tzinfo)

    # parse as epoch time
    timestamp = parse_float(date)
    if timestamp is not None:
        return datetime.fromtimestamp(timestamp, tzinfo or timezone.utc)

    if format_str:
        try:
            # parse as string in given format
            return _add_tz(datetime.strptime(date, format_str), tzinfo)
        except Exception:
            pass

    try:
        # parse as string
        return _add_tz(dateutil.parser.parse(date), tzinfo)
    except Exception:
        pass

    try:
        # parse as (year, month, day, hour, minute, second, microsecond, tzinfo)
        return datetime(*date)
    except Exception:
        pass

    try:
        # parse as time.struct_time
        return datetime(*date[:6], tzinfo=tzinfo or timezone.utc)
    except Exception:
        pass

    return None


def serialize_date(date, tzinfo=None):
    """seralize a date into ISO format if possible"""
    parsed = parse_date(date, tzinfo)
    return parsed.strftime("%Y-%m-%dT%T%z") if parsed else str(date) if date else None


@lru_cache(maxsize=8)
def load_recommender(path, site="bgg"):
    """ load recommender from given path """
    if not path:
        return None
    try:
        if site == "bga":
            from board_game_recommender import BGARecommender

            return BGARecommender.load(path=path)
        from board_game_recommender import BGGRecommender

        return BGGRecommender.load(path=path)
    except Exception:
        LOGGER.exception("unable to load recommender model from <%s>", path)
    return None


@lru_cache(maxsize=8)
def pubsub_client():
    """ Google Cloud PubSub client """
    try:
        from google.cloud import pubsub

        return pubsub.PublisherClient()
    except Exception:
        LOGGER.exception("unable to initialise PubSub client")
    return None


def pubsub_push(
    message,
    project=settings.PUBSUB_QUEUE_PROJECT,
    topic=settings.PUBSUB_QUEUE_TOPIC,
    encoding="utf-8",
    **kwargs,
):
    """ publish message """

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
    """ latest model update """
    try:
        with open(file_path) as file_obj:
            updated_at = file_obj.read()
        updated_at = " ".join(updated_at.split())
        return parse_date(updated_at, tzinfo=timezone.utc)
    except Exception:
        pass
    return None


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


class Timer:
    """ log execution time: with Timer('message'): do_something() """

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
