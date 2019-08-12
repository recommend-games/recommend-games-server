# -*- coding: utf-8 -*-

""" generate a sitemap """

import logging
import sys

from datetime import datetime

from django.core.management.base import BaseCommand
from lxml import etree, objectify

from ...models import Game

LOGGER = logging.getLogger(__name__)
ELM = objectify.ElementMaker(
    annotate=False,
    namespace="http://www.sitemaps.org/schemas/sitemap/0.9",
    nsmap={None: "http://www.sitemaps.org/schemas/sitemap/0.9"},
)


def _url_elements(url, ids, lastmod=None):
    lastmod = (
        "{:s}Z".format(datetime.utcnow().isoformat()) if lastmod is None else lastmod
    )

    # pylint: disable=no-member
    yield ELM.url(
        ELM.loc(f"{url}#/"),
        ELM.lastmod(lastmod),
        ELM.changefreq("weekly"),
        ELM.priority(1),
    )

    yield ELM.url(
        ELM.loc(f"{url}#/news"),
        ELM.lastmod(lastmod),
        ELM.changefreq("hourly"),
        ELM.priority(1),
    )

    yield ELM.url(
        ELM.loc(f"{url}#/about"),
        ELM.lastmod(lastmod),
        ELM.changefreq("weekly"),
        ELM.priority(1),
    )

    yield ELM.url(
        ELM.loc(f"{url}#/faq"),
        ELM.lastmod(lastmod),
        ELM.changefreq("weekly"),
        ELM.priority(1),
    )

    for id_ in ids:
        yield ELM.url(
            ELM.loc(f"{url}#/game/{id_}"),
            ELM.lastmod(lastmod),
            ELM.changefreq("weekly"),
        )


def sitemap(url, limit=None):
    """ return sitemap XML element """

    limit = limit or 50000
    # pylint: disable=no-member
    ids = Game.objects.values_list("bgg_id", flat=True)
    ids = ids[: max(limit - 4, 0)]
    return ELM.urlset(*_url_elements(url, ids))


class Command(BaseCommand):
    """ Creates a sitemap """

    help = "Creates a sitemap"

    def add_arguments(self, parser):
        parser.add_argument("--url", "-u", default="https://recommend.games/", help="")
        parser.add_argument("--limit", "-l", type=int, help="")
        parser.add_argument("--output", "-o", help="")

    def handle(self, *args, **kwargs):
        logging.basicConfig(
            stream=sys.stderr,
            level=logging.DEBUG if kwargs["verbosity"] > 1 else logging.INFO,
            format="%(asctime)s %(levelname)-8.8s [%(name)s:%(lineno)s] %(message)s",
        )

        LOGGER.info(kwargs)

        root = sitemap(url=kwargs["url"], limit=kwargs["limit"])

        if kwargs["output"] and kwargs["output"] != "-":
            with open(kwargs["output"], "wb") as output:
                output.write(
                    etree.tostring(
                        root,
                        encoding="utf-8",
                        xml_declaration=True,
                        pretty_print=False,
                        standalone=True,
                    )
                )

        else:
            print(
                etree.tostring(
                    root,
                    encoding="utf-8",
                    xml_declaration=True,
                    pretty_print=True,
                    standalone=True,
                ).decode()
            )
