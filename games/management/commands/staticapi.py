"""TODO."""

import json
import logging
import sys

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from tqdm import tqdm

from ...models import Game
from ...serializers import GameSerializer, RankingSerializer

LOGGER = logging.getLogger(__name__)


class Command(BaseCommand):
    """TODO."""

    help = "TODO."

    def add_arguments(self, parser):
        parser.add_argument(
            "--base-dir",
            "-b",
            default=Path(settings.BASE_DIR).parent.resolve()
            / "recommend-games-api"
            / "public",
            help="TODO",
        )
        parser.add_argument("--max-items", "-m", type=int, help="TODO")

    def handle(self, *args, **kwargs):
        logging.basicConfig(
            stream=sys.stderr,
            level=logging.DEBUG if kwargs["verbosity"] > 1 else logging.INFO,
            format="%(asctime)s %(levelname)-8.8s [%(name)s:%(lineno)s] %(message)s",
        )

        LOGGER.info(kwargs)

        base_dir = Path(kwargs["base_dir"]).resolve()
        LOGGER.info("Storing files in dir <%s>", base_dir)
        max_items = kwargs.get("max_items")

        # pylint: disable=no-member
        games = Game.objects.order_by(
            "-num_votes",
            "rec_rank",
            "bgg_rank",
            "-avg_rating",
        )
        if max_items:
            games = games[:max_items]

        games_dir = base_dir / "games"
        games_dir.mkdir(parents=True, exist_ok=True)

        for game in tqdm(games):
            game_path = games_dir / f"{game.pk}.json"
            ranking_path = games_dir / str(game.pk) / "rankings.json"

            game_serializer = GameSerializer(game)
            with game_path.open("w", encoding="utf-8") as game_file:
                json.dump(
                    game_serializer.data,
                    game_file,
                    indent=4,
                    sort_keys=True,
                )

            ranking_serializer = RankingSerializer(game.ranking_set.all(), many=True)
            ranking_path.parent.mkdir(parents=True, exist_ok=True)
            with ranking_path.open("w", encoding="utf-8") as ranking_file:
                json.dump(
                    ranking_serializer.data,
                    ranking_file,
                    indent=4,
                    sort_keys=True,
                )
