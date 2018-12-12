# -*- coding: utf-8 -*-

''' utils '''

import logging
import os.path

from functools import lru_cache
from itertools import groupby

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


@lru_cache(maxsize=32)
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
