"""TODO."""

import json
import logging
import sys

from pathlib import Path
from typing import Any, Optional, Union

from django.conf import settings
from django.core.management.base import BaseCommand
from tqdm import tqdm

from ...models import Category, Game, GameType, Mechanic
from ...serializers import (
    CategorySerializer,
    GameSerializer,
    GameTypeSerializer,
    MechanicSerializer,
    RankingSerializer,
)

LOGGER = logging.getLogger(__name__)


class Command(BaseCommand):
    """TODO."""

    help = "TODO."

    def add_arguments(self: "Command", parser) -> None:
        parser.add_argument(
            "--base-dir",
            "-b",
            default=Path(settings.BASE_DIR).parent.resolve()
            / "recommend-games-api"
            / "public",
            help="TODO",
        )
        parser.add_argument("--max-items", "-m", type=int, help="TODO")

    # pylint: disable=no-self-use
    def process_games(
        self: "Command",
        *,
        base_dir: Path,
        max_items: Optional[int] = None,
    ) -> None:
        """TODO."""

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

            game_serializer = GameSerializer(instance=game)
            with game_path.open("w", encoding="utf-8") as game_file:
                json.dump(
                    game_serializer.data,
                    game_file,
                    indent=4,
                    sort_keys=True,
                )

            ranking_serializer = RankingSerializer(
                instance=game.ranking_set.all(), many=True
            )
            ranking_path.parent.mkdir(parents=True, exist_ok=True)
            with ranking_path.open("w", encoding="utf-8") as ranking_file:
                json.dump(
                    ranking_serializer.data,
                    ranking_file,
                    indent=4,
                    sort_keys=True,
                )

    def process_model(
        self: "Command",
        *,
        query_set: "TODO",
        serializer_class: "TODO",
        dest_dir: Union[Path, str],
    ) -> None:
        """TODO."""

        dest_dir = Path(dest_dir).resolve()
        dest_dir.mkdir(parents=True, exist_ok=True)

        for instance in tqdm(query_set):
            instance_path = dest_dir / f"{instance.pk}.json"

            serializer = serializer_class(instance=instance)
            with instance_path.open("w", encoding="utf-8") as instance_file:
                json.dump(
                    serializer.data,
                    instance_file,
                    indent=4,
                    sort_keys=True,
                )

    def handle(self: "Command", *args: Any, **kwargs: Any) -> None:
        logging.basicConfig(
            stream=sys.stderr,
            level=logging.DEBUG if kwargs["verbosity"] > 1 else logging.INFO,
            format="%(asctime)s %(levelname)-8.8s [%(name)s:%(lineno)s] %(message)s",
        )

        LOGGER.info(kwargs)

        base_dir = Path(kwargs["base_dir"]).resolve()
        LOGGER.info("Storing files in dir <%s>", base_dir)
        max_items = kwargs.get("max_items")

        self.process_games(
            base_dir=base_dir,
            max_items=max_items,
        )

        # pylint: disable=no-member
        self.process_model(
            query_set=GameType.objects.all(),
            serializer_class=GameTypeSerializer,
            dest_dir=base_dir / "types",
        )

        self.process_model(
            query_set=Category.objects.all(),
            serializer_class=CategorySerializer,
            dest_dir=base_dir / "categories",
        )

        self.process_model(
            query_set=Mechanic.objects.all(),
            serializer_class=MechanicSerializer,
            dest_dir=base_dir / "mechanics",
        )
