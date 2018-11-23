#!/usr/bin/env python3
# -*- coding: utf-8 -*-

''' generate a sitemap '''

import argparse
import logging
import sys

from datetime import datetime
from itertools import islice

import requests

from lxml import etree, objectify

LOGGER = logging.getLogger(__name__)
ELM = objectify.ElementMaker(
    annotate=False,
    namespace='http://www.sitemaps.org/schemas/sitemap/0.9',
    nsmap={None : 'http://www.sitemaps.org/schemas/sitemap/0.9'},
)


def _fetch_ids(url):
    while url:
        LOGGER.info('fetching IDs from <%s>...', url)

        response = requests.get(url).json()
        results = response.get('results') or ()

        for result in results:
            if result.get('bgg_id'):
                yield result['bgg_id']

        url = response.get('next')


def _url_elements(url, ids, lastmod=None):
    lastmod = '{:s}Z'.format(datetime.utcnow().isoformat()) if lastmod is None else lastmod

    # pylint: disable=no-member
    yield ELM.url(
        ELM.loc(url),
        ELM.lastmod(lastmod),
        ELM.changefreq('weekly'),
        ELM.priority(1),
    )

    yield ELM.url(
        ELM.loc(f'{url}#/about'),
        ELM.lastmod(lastmod),
        ELM.changefreq('weekly'),
        ELM.priority(1),
    )

    for id_ in ids:
        yield ELM.url(
            ELM.loc(f'{url}#/game/{id_}'),
            ELM.lastmod(lastmod),
            ELM.changefreq('weekly'),
        )


def sitemap(url, url_api=None, limit=None):
    ''' return sitemap XML element '''

    ids = _fetch_ids(url_api or url)
    ids = islice(ids, max(limit - 2, 0)) if limit else ids
    # pylint: disable=no-member
    return ELM.urlset(*_url_elements(url, ids))


def _parse_args():
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('--url', '-u', default='https://recommend.games/', help='')
    parser.add_argument('--api-url', '-a', default='http://localhost:8000/api/games/', help='')
    parser.add_argument('--limit', '-l', type=int, help='')
    parser.add_argument('--output', '-o', help='')
    parser.add_argument(
        '--verbose', '-v', action='count', default=0, help='log level (repeat for more verbosity)')

    return parser.parse_args()


def _main():
    args = _parse_args()

    logging.basicConfig(
        stream=sys.stdout,
        level=logging.DEBUG if args.verbose > 0 else logging.INFO,
        format='%(asctime)s %(levelname)-8.8s [%(name)s:%(lineno)s] %(message)s'
    )

    LOGGER.info(args)

    root = sitemap(
        url=args.url,
        url_api=args.api_url,
        limit=args.limit,
    )

    if args.output:
        with open(args.output, 'wb') as output:
            output.write(etree.tostring(
                root,
                encoding='utf-8',
                xml_declaration=True,
                pretty_print=False,
                standalone=True,
            ))

    else:
        print(etree.tostring(
            root,
            encoding='utf-8',
            xml_declaration=True,
            pretty_print=True,
            standalone=True,
        ).decode())


if __name__ == '__main__':
    _main()
