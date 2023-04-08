"""Calculate Kennerspiel scores and add them to the database."""

import logging
import sys
from pathlib import Path

import joblib
import pandas as pd
from django.core.management.base import BaseCommand
from pytility import parse_int
from tqdm import tqdm

from ...models import Game

LOGGER = logging.getLogger(__name__)


def _concat(values):
    return ",".join(map(str, filter(None, map(parse_int, values))))


class Command(BaseCommand):
    """Calculate Kennerspiel scores and add them to the database."""

    help = "Calculate Kennerspiel scores and add them to the database."

    features = (
        "min_players",
        "max_players",
        "min_age",
        "min_time",
        "max_time",
        "cooperative",
        "complexity",
    )
    cat_features = (
        "game_type",
        "mechanic",
        "category",
    )

    def add_arguments(self, parser):
        parser.add_argument("model", help="TODO")
        parser.add_argument(
            "--batch",
            "-b",
            type=int,
            default=10_000,
            help="batch size for DB transactions",
        )
        parser.add_argument("--dry-run", "-n", action="store_true", help="TODO")

    def handle(self, *args, **kwargs):
        logging.basicConfig(
            stream=sys.stderr,
            level=logging.DEBUG if kwargs["verbosity"] > 1 else logging.INFO,
            format="%(asctime)s %(levelname)-8.8s [%(name)s:%(lineno)s] %(message)s",
        )

        LOGGER.info(kwargs)

        model_path = Path(kwargs["model"]).resolve()

        LOGGER.info("Loading model from <%s>", model_path)
        model = joblib.load(model_path)
        LOGGER.info("Using model %r", model)

        LOGGER.info("Loading existing games data from database")
        # pylint: disable=no-member
        games = Game.objects.order_by("bgg_id")
        data = pd.DataFrame.from_records(
            data=games.values("bgg_id", *self.features),
            index="bgg_id",
        )
        LOGGER.info("Loaded %d rows and %d columns", *data.shape)

        for feature in self.cat_features:
            LOGGER.info("Adding categorical feature <%s>", feature)
            tmp = pd.DataFrame.from_records(Game.objects.values("bgg_id", feature))
            data[feature] = tmp.groupby("bgg_id")[feature].apply(_concat)
            del tmp
        LOGGER.info("Using %d columns in total", data.shape[1])

        LOGGER.info("Calculating Kennerspiel scores for %d games", len(data))
        data["kennerspiel"] = model.predict_proba(data)[:, 1]

        if kwargs["dry_run"]:
            for bgg_id, score in data["kennerspiel"].items():
                print(f"{bgg_id}\t{score:.5f}")
        else:
            LOGGER.info("Writing scores to the database")
            games = tuple(games)
            assert len(games) == len(data)
            for game, (bgg_id, score) in tqdm(
                zip(games, data["kennerspiel"].items()), total=len(games)
            ):
                assert game.bgg_id == bgg_id
                game.kennerspiel_score = score
            Game.objects.bulk_update(
                objs=games, fields=["kennerspiel_score"], batch_size=kwargs["batch"]
            )

        LOGGER.info("Done.")
