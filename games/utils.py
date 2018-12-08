# -*- coding: utf-8 -*-

''' utils '''

import os.path

from itertools import groupby

ITERABLE_SINGLE_VALUES = (dict, str, bytes)


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
