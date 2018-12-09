# -*- coding: utf-8 -*-

''' fill database '''

import json
import logging
import re
import sys

from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db.transaction import atomic

from ...models import Game, Person
from ...utils import arg_to_iter, batchify, format_from_path, parse_int, take_first

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


def _parse_value_id(string, regex=VALUE_ID_REGEX):
    if not string:
        return None

    match = regex.match(string)

    if not match:
        return None

    value = match.group(1) or None
    id_ = parse_int(match.group(3))
    result = {}

    if value:
        result['value'] = value
    if id_:
        result['id'] = id_

    return result or None


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
    LOGGER.info('done processing')


def _create_references(
        model,
        items,
        foreign=None,
        recursive=None,
        batch_size=None,
    ):
    foreign = foreign or {}
    foreign = {k: tuple(arg_to_iter(v)) for k, v in foreign.items()}
    foreign = {k: v for k, v in foreign.items() if len(v) == 2}

    recursive = {
        r: r for r in arg_to_iter(recursive)
    } if not isinstance(recursive, dict) else recursive

    if not foreign and not recursive:
        LOGGER.warning('neither foreign nor recursive references given, got nothing to do...')
        return

    LOGGER.info('creating foreign references: %r', foreign)
    LOGGER.info('creating recursive references: %r', recursive)

    count = -1
    foreign_values = {f[0]: defaultdict(set) for f in foreign.values()}
    updates = {}

    for count, item in enumerate(items):
        update = defaultdict(list)

        for field, (fmodel, _) in foreign.items():
            for value in filter(None, map(_parse_value_id, arg_to_iter(item.get(field)))):
                id_ = value.get('id')
                value = value.get('value')
                if id_ and value:
                    foreign_values[fmodel][id_].add(value)
                    update[field].append(id_)

        for rec_from, rec_to in recursive.items():
            rec = {parse_int(r) for r in arg_to_iter(item.get(rec_from)) if r}
            rec = sorted(
                model.objects.filter(pk__in=rec).values_list('pk', flat=True)
            ) if rec else None
            if rec:
                update[rec_to] = rec

        pkey = parse_int(item.get(model._meta.pk.name))
        if pkey and any(update.values()):
            updates[pkey] = update

        if (count + 1) % 1000 == 0:
            LOGGER.info('processed %d items so far', count + 1)

    del items, recursive

    LOGGER.info('processed %d items in total', count + 1)

    for fmodel, value_field in frozenset(foreign.values()):
        id_field = fmodel._meta.pk.name
        LOGGER.info('found %d items for model %r to create', len(foreign_values[fmodel]), fmodel)
        values = ((k, tuple(v)) for k, v in foreign_values[fmodel].items() if k and v)
        values = ({id_field: k, value_field: v[0]} for k, v in values if k and len(v) == 1)
        _create_from_items(fmodel, values, batch_size=batch_size)

    del foreign, foreign_values

    LOGGER.info('found %d items for model %r to update', len(updates), model)

    batches = batchify(updates.items(), batch_size) if batch_size else (updates.items(),)

    for count, batch in enumerate(batches):
        LOGGER.info('processing batch #%d...', count + 1)
        with atomic():
            for pkey, update in batch:
                try:
                    instance = model.objects.get(pk=pkey)
                    for field, values in update.items():
                        getattr(instance, field).set(values)
                    instance.save()
                except Exception:
                    LOGGER.exception('an error ocurred when updating <%s> with %r', pkey, update)

    del batches, updates

    LOGGER.info('done updating')


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
        'image_url': take_first,
        'video_url': take_first,
        'external_link': take_first,
    }

    game_fields_foreign = {
        'designer': (Person, 'name'),
        'artist': (Person, 'name'),
    }

    game_fields_recursive = {
        'implementation': 'implements',
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

        items = tuple(_load(*kwargs['paths']))
        _create_from_items(
            model=Game,
            items=items,
            fields=self.game_fields,
            fields_mapping=self.game_fields_mapping,
            batch_size=kwargs['batch'],
        )
        _create_references(
            model=Game,
            items=items,
            foreign=self.game_fields_foreign,
            recursive=self.game_fields_recursive,
            batch_size=kwargs['batch'],
        )

        del items

        LOGGER.info('done filling the database')
