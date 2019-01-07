# -*- coding: utf-8 -*-

''' Stress test command '''


import logging
import os.path
import random
import sys
import timeit

import requests

from django.core.management.base import BaseCommand

from ...models import User

LOGGER = logging.getLogger(__name__)


class Command(BaseCommand):
    ''' Stress test '''

    help = 'Stress test'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # pylint: disable=no-member
        self.users = tuple(User.objects.values_list('name', flat=True))

    def add_arguments(self, parser):
        parser.add_argument('--url', '-u', default='https://recommend.games/', help='URL to test')
        parser.add_argument('--number', '-n', type=int, default=100, help='number of requests')

    def handle(self, *args, **kwargs):
        logging.basicConfig(
            stream=sys.stderr,
            level=logging.DEBUG if kwargs['verbosity'] > 1 else logging.INFO,
            format='%(asctime)s %(levelname)-8.8s [%(name)s:%(lineno)s] %(message)s',
        )

        LOGGER.info(kwargs)

        request_url = os.path.join(kwargs['url'], 'api/games/recommend', '')

        LOGGER.info('stress testing <%s> by making %d requests...', request_url, kwargs['number'])

        start = timeit.default_timer()
        for _ in range(kwargs['number']):
            requests.get(request_url, {'user': random.choice(self.users)})
        total = timeit.default_timer() - start

        LOGGER.info(
            'done with %d requests after %.1f seconds (%.3f seconds per request)',
            kwargs['number'], total, total / kwargs['number'])
