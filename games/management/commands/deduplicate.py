"""Remove duplicate files."""

import logging
import sys
from pathlib import Path

from django.core.management.base import BaseCommand

LOGGER = logging.getLogger(__name__)


class Command(BaseCommand):
    """Remove duplicate files."""

    help = "Remove duplicate files."

    def add_arguments(self, parser):
        parser.add_argument(
            "paths",
            nargs="+",
            help="directories to be cleared of duplicates",
        )
        parser.add_argument("--glob", "-g", help="pattern of files to be deleted")
        parser.add_argument(
            "--dry-run",
            "-n",
            action="store_true",
            help="only print files to be deleted",
        )

    def handle(self, *args, **kwargs):
        logging.basicConfig(
            stream=sys.stderr,
            level=logging.DEBUG if kwargs["verbosity"] > 1 else logging.INFO,
            format="%(asctime)s %(levelname)-8.8s [%(name)s:%(lineno)s] %(message)s",
        )

        LOGGER.info(args)
        LOGGER.info(kwargs)

        dry_run = kwargs["dry_run"]
        glob = kwargs["glob"]

        for path in kwargs["paths"]:
            path = Path(path).resolve()
            LOGGER.info("Looking for duplicates in <%s>", path)

            if not path.is_dir():
                LOGGER.warning("<%s> is not an existing directory, skipping...", path)
                continue

            files = path.glob(glob) if glob else path.iterdir()
            prev = None
            counter = 0

            for file in sorted(files):
                if not file.is_file():
                    continue

                LOGGER.debug("Reading from <%s>", file)
                with file.open() as file_obj:
                    curr = file_obj.read()

                duplicate = prev == curr
                prev = curr

                if not duplicate:
                    LOGGER.debug("Keeping <%s>", file)
                    continue

                LOGGER.info("Deleting duplicate file <%s>", file)

                if dry_run:
                    print(file)
                else:
                    file.unlink()

                counter += 1

            LOGGER.info("Done deleting %d file(s) from <%s>", counter, path)
