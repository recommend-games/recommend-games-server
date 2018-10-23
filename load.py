#!/usr/bin/env python
# -*- coding: utf-8 -*-

''' command line script '''

import argparse
import json
import logging
import os.path
import sys

import requests

# from games.models import Game

LOGGER = logging.getLogger(__name__)
# pylint: disable=no-member
# FIELDS = frozenset(f.name for f in Game._meta.get_fields() if not f.is_relation)
FIELDS = frozenset((
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
FIELDS_MAPPING = {
    'rank': 'bgg_rank',
    # 'implementation': 'implementation_of',
}


def _parse_item(item, fields=FIELDS, fields_mapping=FIELDS_MAPPING):
    result = {k: v for k, v in item.items() if k in fields}

    for map_from, map_to in fields_mapping.items():
        if item.get(map_from):
            result.setdefault(map_to, item[map_from])

    return result


def _upload(items, url, id_field='id'):
    count = -1
    for count, data in enumerate(map(_parse_item, items)):
        if count and count % 1000 == 0:
            LOGGER.info('uploaded %d items so far', count)

        id_ = data.get(id_field)
        if id_ is None:
            continue

        url_item = os.path.join(url, str(id_), '')
        response = requests.head(url_item)

        if response.ok:
            requests.put(url=url_item, data=data)
        else:
            requests.post(url=url, data=data)
    return count + 1


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
        _, ext = os.path.splitext(path)
        ext = ext.lower() if ext else '.'
        ext = ext[1:]

        if ext in ('jl', 'jsonl'):
            yield from _load_jl(path)
        else:
            yield from _load_json(path)

def _parse_args():
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('paths', nargs='+', help='')
    parser.add_argument('--url', '-u', required=True, help='')
    parser.add_argument('--id-field', '-i', default='id', help='')
    parser.add_argument(
        '--verbose', '-v', action='count', default=0, help='log level (repeat for more verbosity)')

    return parser.parse_args()


def _main():
    args = _parse_args()

    logging.basicConfig(
        stream=sys.stderr,
        level=logging.DEBUG if args.verbose > 0 else logging.INFO,
        format='%(asctime)s %(levelname)-8.8s [%(name)s:%(lineno)s] %(message)s'
    )

    LOGGER.info(args)
    LOGGER.info('uploading items to <%s>...', args.url)

    items = _load(*args.paths)
    count = _upload(
        items=items,
        url=args.url,
        id_field=args.id_field,
    )

    LOGGER.info('done uploading %d items', count)


if __name__ == '__main__':
    _main()
