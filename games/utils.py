# -*- coding: utf-8 -*-

''' utils '''

import logging
import os.path
import timeit

from functools import lru_cache
from itertools import groupby

from django.conf import settings

ITERABLE_SINGLE_VALUES = (dict, str, bytes)
LOGGER = logging.getLogger(__name__)


def arg_to_iter(arg):
    ''' wraps arg into tuple if not an iterable '''
    if arg is None:
        return ()
    if not isinstance(arg, ITERABLE_SINGLE_VALUES) and hasattr(arg, '__iter__'):
        return arg
    return (arg,)


def take_first(items):
    ''' take first item '''
    for item in arg_to_iter(items):
        if item is not None and item != '':
            return item
    return None


def batchify(iterable, size):
    ''' make batches of given size '''
    for _, group in groupby(enumerate(iterable), key=lambda x: x[0] // size):
        yield (x[1] for x in group)


def format_from_path(path):
    ''' get file extension '''
    try:
        _, ext = os.path.splitext(path)
        return ext.lower()[1:] if ext else None
    except Exception:
        pass
    return None


def parse_int(string, base=10):
    ''' safely convert an object to int if possible, else return None '''
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


def parse_bool(item):
    ''' parses an item and converts it to a boolean '''
    if isinstance(item, int):
        return bool(item)
    if item in ('True', 'true', 'Yes', 'yes'):
        return True
    integer = parse_int(item)
    if integer is not None:
        return bool(integer)
    return False


@lru_cache(maxsize=8)
def load_recommender(path):
    ''' load recommender from given path '''
    if not path:
        return None
    try:
        from ludoj_recommender import GamesRecommender
        return GamesRecommender.load(path=path)
    except Exception:
        LOGGER.exception('unable to load recommender model from <%s>', path)
    return None


@lru_cache(maxsize=8)
def pubsub_client():
    ''' Google Cloud PubSub client '''
    try:
        from google.cloud import pubsub
        return pubsub.PublisherClient()
    except Exception:
        LOGGER.exception('unable to initialise PubSub client')
    return None


def pubsub_push(
        message,
        project=settings.PUBSUB_QUEUE_PROJECT,
        topic=settings.PUBSUB_QUEUE_TOPIC,
        encoding='utf-8',
        **kwargs,
    ):
    ''' publish message '''

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

    LOGGER.debug('pushing message %r to <%s>', message, path)

    try:
        return client.publish(topic=path, data=message, **kwargs)
    except Exception:
        LOGGER.exception('unable to send message %r', message)
    return None


class Timer:
    ''' log execution time: with Timer('message'): do_something() '''

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
