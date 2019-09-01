# -*- coding: utf-8 -*-

"""Saves a snapshot of the BGG rankings."""

import csv
import logging
import sys

from django.core.management.base import BaseCommand

from ...models import Game

LOGGER = logging.getLogger(__name__)


def _write_games(games, output):
    writer = csv.writer(output)
    writer.writerow(("rank", "bgg_id", "score"))
    writer.writerows(games.values_list("bgg_rank", "bgg_id", "bayes_rating"))


class Command(BaseCommand):
    """Saves a snapshot of the BGG rankings."""

    help = "Saves a snapshot of the BGG rankings."

    def add_arguments(self, parser):
        parser.add_argument("--output", "-o", help="output destination")

    def handle(self, *args, **kwargs):
        logging.basicConfig(
            stream=sys.stderr,
            level=logging.DEBUG if kwargs["verbosity"] > 1 else logging.INFO,
            format="%(asctime)s %(levelname)-8.8s [%(name)s:%(lineno)s] %(message)s",
        )

        LOGGER.info(kwargs)

        # pylint: disable=no-member
        games = Game.objects.filter(
            bgg_rank__isnull=False, avg_rating__isnull=False, bayes_rating__isnull=False
        ).order_by("bgg_rank", "-bayes_rating", "-avg_rating")

        if kwargs["output"] and kwargs["output"] != "-":
            with open(kwargs["output"], "w") as file:
                _write_games(games, file)
        else:
            _write_games(games, sys.stdout)
