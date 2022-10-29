"""Parse a file for foreign references and store those in separate CSVs."""

import csv
import json
import logging
import sys
from pathlib import Path
from typing import Any, Generator, Optional, Tuple

from django.core.management.base import BaseCommand
from pytility import arg_to_iter, parse_int
from tqdm import tqdm

LOGGER = logging.getLogger(__name__)


def _parse_id(string: Any) -> Tuple[Optional[int], Optional[str]]:
    if not string or not isinstance(string, str):
        return None, None
    name, id_ = string.rsplit(":", 1)
    return parse_int(id_), name


def _parse_ids(values: Any) -> Generator[Tuple[int, str], None, None]:
    for value in arg_to_iter(values):
        id_, name = _parse_id(value)
        if id_ and name:
            yield id_, name


class Command(BaseCommand):
    """Parse a file for foreign references and store those in separate CSVs."""

    help = "Parse a file for foreign references and store those in separate CSVs."

    game_fields_foreign = {
        "artist": "Person",
        "category": "Category",
        "designer": "Person",
        "family": "GameFamily",
        "game_type": "GameType",
        "mechanic": "Mechanic",
        "publisher": "Publisher",
    }

    def add_arguments(self, parser):
        parser.add_argument("in_file")
        parser.add_argument("--out-dir", "-o", default=".")
        parser.add_argument("--out-file", "-O", default="{entity}.csv")
        parser.add_argument("--dry-run", "-n", action="store_true")

    def handle(self, *args, **kwargs):
        logging.basicConfig(
            stream=sys.stderr,
            level=logging.DEBUG if kwargs["verbosity"] > 1 else logging.INFO,
            format="%(asctime)s %(levelname)-8.8s [%(name)s:%(lineno)s] %(message)s",
        )

        LOGGER.info(kwargs)

        entities = frozenset(self.game_fields_foreign.values())
        results = {entity: {} for entity in entities}

        LOGGER.info("Parsing file <%s>", kwargs["in_file"])

        with open(kwargs["in_file"]) as file:
            for line in tqdm(file):
                game = json.loads(line)
                for field, entity in self.game_fields_foreign.items():
                    results[entity].update(_parse_ids(game.get(field)))

        base_path = Path(kwargs["out_dir"]).resolve()

        for entity in entities:
            result = results[entity]
            out_file = kwargs["out_file"].format(entity=entity)
            out_path = base_path / out_file

            LOGGER.info(
                "Writing %d <%s> entities to <%s>", len(result), entity, out_path
            )

            if not kwargs["dry_run"]:
                with out_path.open("w") as file:
                    writer = csv.writer(file)
                    writer.writerow(("bgg_id", "name"))
                    writer.writerows(sorted(result.items()))

        LOGGER.info("Done.")
