"""Save API responses as static files."""

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Union

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
    """Save API responses as static files."""

    help = "Save API responses as static files."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--base-dir",
            "-b",
            default=Path(settings.BASE_DIR).parent.resolve()
            / "recommend-games-api"
            / "public",
            help="base output dir",
        )
        parser.add_argument(
            "--max-items",
            "-m",
            type=int,
            help="maximum number of files to be stored for each model",
        )

    # pylint: disable=no-self-use
    def paginated_result(self, results: List) -> Dict:
        """Mock a paginated API response."""
        return {
            "count": len(results),
            "previous": None,
            "next": None,
            "results": results,
        }

    def save_model_instances(
        self,
        *,
        query_set,
        serializer_class,
        model_dir: Path,
    ) -> None:
        """Save the model instances as JSON files to the output dir."""

        model_dir.mkdir(parents=True, exist_ok=True)

        for instance in tqdm(query_set):
            instance_path = model_dir / f"{instance.pk}.json"

            serializer = serializer_class(instance=instance)
            with instance_path.open("w", encoding="utf-8") as instance_file:
                json.dump(
                    serializer.data,
                    instance_file,
                    indent=4,
                    sort_keys=True,
                )

    def process_games(
        self,
        *,
        query_set,
        base_dir: Path,
    ) -> None:
        """Save games and rankings data to the output dir."""

        games_dir = base_dir / "games"
        self.save_model_instances(
            query_set=query_set,
            serializer_class=GameSerializer,
            model_dir=games_dir,
        )

        for game in tqdm(query_set):
            ranking_path = games_dir / str(game.pk) / "rankings.json"

            ranking_serializer = RankingSerializer(
                instance=game.ranking_set.all(),
                many=True,
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
        self,
        *,
        query_set,
        serializer_class,
        base_dir: Union[Path, str],
        model_name: str,
    ) -> None:
        """Save model data to a give output dir."""

        base_dir = Path(base_dir).resolve()
        model_path = base_dir / f"{model_name}.json"
        model_dir = base_dir / model_name
        self.save_model_instances(
            query_set=query_set,
            serializer_class=serializer_class,
            model_dir=model_dir,
        )

        serializer = serializer_class(instance=query_set, many=True)
        with model_path.open("w", encoding="utf-8") as model_file:
            json.dump(
                self.paginated_result(serializer.data),
                model_file,
                indent=4,
                sort_keys=True,
            )

    def handle(self, *args: Any, **kwargs: Any) -> None:
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

        self.process_games(
            query_set=games,
            base_dir=base_dir,
        )

        self.process_model(
            query_set=GameType.objects.all(),
            serializer_class=GameTypeSerializer,
            base_dir=base_dir,
            model_name="types",
        )

        self.process_model(
            query_set=Category.objects.all(),
            serializer_class=CategorySerializer,
            base_dir=base_dir,
            model_name="categories",
        )

        self.process_model(
            query_set=Mechanic.objects.all(),
            serializer_class=MechanicSerializer,
            base_dir=base_dir,
            model_name="mechanics",
        )
