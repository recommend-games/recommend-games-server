# -*- coding: utf-8 -*-

''' split a file '''

import json
import logging
import sys

from functools import partial

from django.core.management.base import BaseCommand
from smart_open import smart_open

from ...utils import batchify

LOGGER = logging.getLogger(__name__)
FIELDS = frozenset({
    'article_id',
    'url_canonical',
    'url_mobile',
    'url_amp',
    'url_thumbnail',
    'published_at',
    'title_short',
    'author',
    'description',
    'category',
    'keyword',
    'section_inferred',
    'country',
    'language',
    'source_name',
})


def _filter_fields(item, fields=None, exclude_empty=False):
    return {
        k: v for k, v in item.items()
        if (not fields or k in fields) and (not exclude_empty or v)
    }


def _load_items(iterable, fields=None):
    if isinstance(iterable, str):
        with smart_open(iterable, 'r') as file_obj:
            yield from _load_items(file_obj, fields=fields)
        return

    items = map(json.loads, iterable)
    items = map(partial(_filter_fields, fields=fields, exclude_empty=True), items)

    yield from items


class Command(BaseCommand):
    ''' Split a file '''

    help = 'Split a file'

    def add_arguments(self, parser):
        parser.add_argument('in-file', help='input file')
        parser.add_argument('--batch', '-b', type=int, help='batch size')
        parser.add_argument('--out-file', '-o', help='output file path')

    def handle(self, *args, **kwargs):
        logging.basicConfig(
            stream=sys.stderr,
            level=logging.DEBUG if kwargs['verbosity'] else logging.INFO,
            format='%(asctime)s %(levelname)-8.8s [%(name)s:%(lineno)s] %(message)s',
        )

        LOGGER.info(kwargs)

        LOGGER.info('loading items from <%s>...', kwargs['in-file'])

        items = tuple(_load_items(kwargs['in-file'], fields=FIELDS))
        batches = batchify(items, kwargs['batch']) if kwargs['batch'] else (items,)
        total = len(items)
        count = 0

        for i, batch in enumerate(batches):
            batch = list(batch)
            count += len(batch)
            result = {
                'count': total,
                'previous': i - 1 if i else None,
                'next': i + 1 if count < total else None,
                'results': batch,
            }

            if not kwargs['out_file'] or kwargs['out_file'] == '-':
                json.dump(result, sys.stdout)
                print()

            else:
                out_path = kwargs['out_file'].format(number=i)
                LOGGER.info('writing batch #%d to <%s>...', i, out_path)
                with smart_open(out_path, 'w') as out_file:
                    json.dump(result, out_file)
