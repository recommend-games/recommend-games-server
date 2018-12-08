# -*- coding: utf-8 -*-

''' fill database '''

import json
import logging
import re
import sys

from django.core.management.base import BaseCommand

from ...models import Game
from ...utils import batchify, format_from_path, take_first

LOGGER = logging.getLogger(__name__)
VALUE_ID_REGEX = re.compile(r'^(.*?)(:(\d+))?$')


def _load_json(path):
    LOGGER.info('loading JSON from <%s>...', path)
    with open(path, 'r') as json_file:
        yield from json.load(json_file)


def _load_jl(path):
    LOGGER.info('loading JSON lines from <%s>...', path)
    with open(path, 'r') as json_file:
        for line in json_file:
            yield json.loads(line)


def _load(*paths):
    for path in paths:
        if format_from_path(path) in ('jl', 'jsonl'):
            yield from _load_jl(path)
        else:
            yield from _load_json(path)


def _parse_item(item, fields=None, fields_mapping=None):
    result = {
        k: v for k, v in item.items() if k in fields
    } if fields else dict(item)

    if not fields_mapping:
        return result

    for map_from, map_to in fields_mapping.items():
        if item.get(map_from):
            if callable(map_to):
                result[map_from] = map_to(item[map_from])
            else:
                result.setdefault(map_to, item[map_from])

    return result


def _make_instances(model, items, fields=None, fields_mapping=None):
    count = -1
    for count, item in enumerate(items):
        try:
            data = _parse_item(item, fields, fields_mapping)
            yield model(**data)
        except Exception:
            LOGGER.exception('error while parsing an item: %r', item)
        if (count + 1) % 1000 == 0:
            LOGGER.info('processed %d items so far', count + 1)
    LOGGER.info('processed %d items in total', count + 1)


def _create_from_items(model, items, fields=None, fields_mapping=None, batch_size=None):
    LOGGER.info('creating instances of %r', model)
    instances = _make_instances(model, items, fields, fields_mapping)
    batches = batchify(instances, batch_size) if batch_size else (instances,)
    for count, batch in enumerate(batches):
        LOGGER.info('processing batch #%d...', count + 1)
        model.objects.bulk_create(batch)
    LOGGER.info('done processing',)


class Command(BaseCommand):
    ''' Loads a file to the database '''

    help = 'Loads a file to the database'

    game_fields = frozenset((
        'avg_rating',
        'bayes_rating',
        'bgg_id',
        'bgg_rank',
        'compilation',
        'complexity',
        'cooperative',
        'created_at',
        'description',
        'language_dependency',
        'max_age',
        'max_age_rec',
        'max_players',
        'max_players_best',
        'max_players_rec',
        'max_time',
        'min_age',
        'min_age_rec',
        'min_players',
        'min_players_best',
        'min_players_rec',
        'min_time',
        'modified_at',
        'name',
        'num_votes',
        'rec_rank',
        'rec_rating',
        'scraped_at',
        'stddev_rating',
        'url',
        'year',
    ))

    game_fields_mapping = {
        'rank': 'bgg_rank',
        # 'implementation': 'implementation_of',
        'image_url': take_first,
        'video_url': take_first,
        'external_link': take_first,
    }

    def add_arguments(self, parser):
        parser.add_argument('paths', nargs='+', help='file(s) to be processed')
        parser.add_argument(
            '--batch', '-b', type=int, default=1000, help='batch size for DB transactions')

    def handle(self, *args, **kwargs):
        logging.basicConfig(
            stream=sys.stderr,
            level=logging.DEBUG if kwargs['verbosity'] else logging.INFO,
            format='%(asctime)s %(levelname)-8.8s [%(name)s:%(lineno)s] %(message)s'
        )

        items = _load(*kwargs['paths'])
        _create_from_items(
            model=Game,
            items=items,
            fields=self.game_fields,
            fields_mapping=self.game_fields_mapping,
            batch_size=kwargs['batch'],
        )
