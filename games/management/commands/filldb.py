""" fill database """

import json
import logging
import re
import sys
from collections import defaultdict
from datetime import timezone
from functools import partial
from itertools import combinations, groupby
from pathlib import Path
from typing import Iterable, Optional

import jmespath
import turicreate as tc
import yaml
from board_game_recommender.utils import percentile_buckets, star_rating
from board_game_scraper.utils import load_premium_users
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.transaction import atomic
from django.utils.timezone import now
from pytility import arg_to_iter, batchify, parse_date, parse_int, take_first

from ...models import Category, Collection, Game, GameType, Mechanic, Person, User
from ...utils import format_from_path, load_recommender

LOGGER = logging.getLogger(__name__)
VALUE_ID_REGEX = re.compile(r"^(.*?)(:(\d+))?$")
LINK_ID_REGEX = re.compile(r"^([a-z]+):(.+)$")
FAMILY_ID_BGA = 70360


def _load_yaml(path):
    LOGGER.info("Loading YAML from <%s>…", path)
    with open(path) as yaml_file:
        yield from yaml.safe_load(yaml_file)


def _load_json(path):
    LOGGER.info("loading JSON from <%s>...", path)
    with open(path) as json_file:
        yield from json.load(json_file)


def _load_jl(path):
    LOGGER.info("loading JSON lines from <%s>...", path)
    with open(path) as json_file:
        for line in json_file:
            yield json.loads(line)


def _load(*paths, in_format=None):
    for path in paths:
        file_format = in_format or format_from_path(path)
        if file_format in ("yaml", "yml"):
            yield from _load_yaml(path)
        elif file_format in ("jl", "jsonl"):
            yield from _load_jl(path)
        else:
            yield from _load_json(path)


def _find_latest_ranking(
    path_dir: Path,
    glob: str = "*.csv",
    star_percentiles=Optional[Iterable[float]],
) -> tc.SFrame:
    path_dir = path_dir.resolve()
    LOGGER.info("Searching <%s> for latest ranking", path_dir)
    path_file = max(
        path_dir.glob(glob),
        key=lambda p: parse_date(p.stem, tzinfo=timezone.utc),
    )

    LOGGER.info("Loading ranking from <%s>", path_file)
    recommendations = tc.SFrame.read_csv(str(path_file))["rank", "bgg_id", "score"]

    if star_percentiles:
        buckets = tuple(percentile_buckets(recommendations["score"], star_percentiles))
        recommendations["stars"] = [
            star_rating(score=score, buckets=buckets, low=1.0, high=5.0)
            for score in recommendations["score"]
        ]

    return recommendations


def _rating_data(
    recommender_path=getattr(settings, "RECOMMENDER_PATH", None),
    pk_field="bgg_id",
    rankings_path=None,
    r_g_ranking_effective_date=getattr(settings, "R_G_RANKING_EFFECTIVE_DATE", None),
):
    recommender = load_recommender(recommender_path, "bgg")

    if not recommender:
        return {}

    r_g_ranking_effective_date = parse_date(
        r_g_ranking_effective_date,
        tzinfo=timezone.utc,
    )

    if (
        rankings_path
        and r_g_ranking_effective_date
        and now() >= r_g_ranking_effective_date
    ):
        LOGGER.info(
            "Using new R.G ranking effective from %s",
            r_g_ranking_effective_date,
        )
        recommendations = _find_latest_ranking(
            path_dir=Path(rankings_path),
            star_percentiles=getattr(settings, "STAR_PERCENTILES", None),
        )
    else:
        recommendations = recommender.recommend(
            users=(),
            star_percentiles=getattr(settings, "STAR_PERCENTILES", None),
        )

    LOGGER.info("Loaded recommendations for %d games", len(recommendations))

    count = -1
    result = {}

    for count, game in enumerate(recommendations):
        if count and count % 1000 == 0:
            LOGGER.info("processed %d items so far", count)

        pkey = game.get(pk_field)
        if pkey is None:
            continue

        result[pkey] = {
            "rec_rank": game.get("rank"),
            "rec_rating": game.get("score"),
            "rec_stars": game.get("stars"),
        }

    LOGGER.info("processed %d items in total", count)

    return result


def _parse_item(item, fields=None, fields_mapping=None, item_mapping=None):
    result = (
        {k: v for k, v in item.items() if k in fields}
        if fields is not None
        else dict(item)
    )

    if fields_mapping:
        for map_from, map_to in fields_mapping.items():
            if item.get(map_from):
                if callable(map_to):
                    result[map_from] = map_to(item[map_from])
                else:
                    result.setdefault(map_to, item[map_from])

    if item_mapping:
        for field, function in item_mapping.items():
            result[field] = function(item)

    return result


def _parse_value_id(string, regex=VALUE_ID_REGEX):
    if not string:
        return None

    match = regex.match(string)

    if not match:
        return None

    value = match.group(1) or None
    id_ = parse_int(match.group(3))
    result = {}

    if value:
        result["value"] = value
    if id_:
        result["id"] = id_

    return result or None


def _make_instances(
    model,
    items,
    fields=None,
    fields_mapping=None,
    item_mapping=None,
    add_data=None,
):
    add_data = add_data or {}
    pk_field = model._meta.pk.name
    count = -1

    for count, item in enumerate(items):
        try:
            data = _parse_item(item, fields, fields_mapping, item_mapping)
            extra = add_data.get(data.get(pk_field)) or {}
            for key, value in extra.items():
                data.setdefault(key, value)
            yield model(**data)
        except Exception:
            LOGGER.exception("error while parsing an item: %r", item)
        if (count + 1) % 10_000 == 0:
            LOGGER.info("processed %d items so far", count + 1)
    LOGGER.info("processed %d items in total", count + 1)


def _create_from_items(
    model,
    items,
    fields=None,
    fields_mapping=None,
    item_mapping=None,
    add_data=None,
    batch_size=None,
    dry_run=False,
):
    LOGGER.info("creating instances of %r", model)

    instances = _make_instances(
        model=model,
        items=items,
        fields=fields,
        fields_mapping=fields_mapping,
        item_mapping=item_mapping,
        add_data=add_data,
    )

    batches = batchify(instances, batch_size) if batch_size else (instances,)

    for count, batch in enumerate(batches):
        LOGGER.info("processing batch #%d...", count + 1)
        if not dry_run:
            model.objects.bulk_create(batch)

    LOGGER.info("done processing")


def _create_references(
    model,
    items,
    foreign=None,
    recursive=None,
    batch_size=None,
    dry_run=False,
):
    foreign = foreign or {}
    foreign = {k: tuple(arg_to_iter(v)) for k, v in foreign.items()}
    foreign = {k: v for k, v in foreign.items() if len(v) == 2}

    recursive = (
        {r: r for r in arg_to_iter(recursive)}
        if not isinstance(recursive, dict)
        else recursive
    )

    if not foreign and not recursive:
        LOGGER.warning(
            "neither foreign nor recursive references given, got nothing to do..."
        )
        return

    LOGGER.info("creating foreign references: %r", foreign)
    LOGGER.info("creating recursive references: %r", recursive)

    count = -1
    foreign_values = {f[0]: defaultdict(set) for f in foreign.values()}
    updates = {}

    for count, item in enumerate(items):
        update = defaultdict(list)

        for field, (fmodel, _) in foreign.items():
            for value in filter(
                None, map(_parse_value_id, arg_to_iter(item.get(field)))
            ):
                id_ = value.get("id")
                value = value.get("value")
                if id_ and value:
                    foreign_values[fmodel][id_].add(value)
                    update[field].append(id_)

        for rec_from, rec_to in recursive.items():
            rec = {parse_int(r) for r in arg_to_iter(item.get(rec_from)) if r}
            rec = (
                sorted(
                    model.objects.filter(pk__in=rec)
                    .values_list("pk", flat=True)
                    .distinct()
                )
                if rec
                else None
            )
            if rec:
                update[rec_to] = rec

        pkey = parse_int(item.get(model._meta.pk.name))
        if pkey and any(update.values()):
            updates[pkey] = update

        if (count + 1) % 1000 == 0:
            LOGGER.info("processed %d items so far", count + 1)

    del items, recursive

    LOGGER.info("processed %d items in total", count + 1)

    for fmodel, value_field in frozenset(foreign.values()):
        id_field = fmodel._meta.pk.name
        LOGGER.info(
            "found %d items for model %r to create", len(foreign_values[fmodel]), fmodel
        )
        values = (
            {id_field: k, value_field: take_first(v)}
            for k, v in foreign_values[fmodel].items()
            if k and v
        )
        _create_from_items(
            model=fmodel,
            items=values,
            batch_size=batch_size,
            dry_run=dry_run,
        )

    del foreign, foreign_values

    LOGGER.info("found %d items for model %r to update", len(updates), model)

    batches = (
        batchify(updates.items(), batch_size) if batch_size else (updates.items(),)
    )

    for count, batch in enumerate(batches):
        LOGGER.info("processing batch #%d...", count + 1)
        if not dry_run:
            with atomic():
                for pkey, update in batch:
                    try:
                        instance = model.objects.get(pk=pkey)
                        for field, values in update.items():
                            getattr(instance, field).set(values)
                        instance.save()
                    except Exception:
                        LOGGER.exception(
                            "an error ocurred when updating <%s> with %r",
                            pkey,
                            update,
                        )

    del batches, updates

    LOGGER.info("done updating")


def _generate_cluster_pairs(model, recommender):
    for cluster in recommender.clusters:
        for pk_1, pk_2 in combinations(cluster, 2):
            instance_1 = model.objects.filter(pk=pk_1).first()
            instance_2 = model.objects.filter(pk=pk_2).first()
            if instance_1 and instance_2:
                yield instance_1, instance_2


def _create_clusters(
    model,
    recommender_path=getattr(settings, "RECOMMENDER_PATH", None),
    batch_size=None,
    dry_run=False,
):
    recommender = load_recommender(recommender_path, "bgg")

    if not recommender:
        return

    LOGGER.info(
        "Loaded a total of %d clusters from recommender %s",
        len(recommender.clusters),
        recommender,
    )

    cluster_pairs = _generate_cluster_pairs(model, recommender)

    batches = (
        batchify(
            cluster_pairs,
            batch_size,
        )
        if batch_size
        else (cluster_pairs,)
    )

    for count, batch in enumerate(batches):
        LOGGER.info("Processing batch #%d...", count + 1)
        if not dry_run:
            with atomic():
                for instance_1, instance_2 in batch:
                    try:
                        instance_1.cluster.add(instance_2)
                        instance_1.save()
                    except Exception:
                        LOGGER.exception(
                            "an error ocurred when updating %r and %r",
                            instance_1,
                            instance_2,
                        )

    LOGGER.info("Done updating clusters")


def _make_secondary_instances(*, model, secondary, items, **kwargs):
    instances = _make_instances(model=model, items=items, **kwargs)

    if not secondary.get("model") or not secondary.get("from"):
        LOGGER.warning("cannot create secondary models with information %r", secondary)
        yield from instances
        return

    if not secondary.get("to"):
        secondary["to"] = secondary["model"]._meta.pk.name

    include_pks = frozenset(arg_to_iter(secondary.get("include_pks")))
    if include_pks:
        LOGGER.info(
            "Including collection info only for %d premium user(s)",
            len(include_pks),
        )

    for value, group in groupby(
        iterable=instances,
        key=lambda instance: getattr(instance, secondary["from"], None),
    ):
        if value:
            yield secondary["model"](**{secondary["to"]: value})
        if not include_pks or value in include_pks:
            yield from group


def _create_secondary_instances(
    model,
    secondary,
    items,
    models_order=(),
    batch_size=None,
    dry_run=False,
    **kwargs,
):
    instances = _make_secondary_instances(
        model=model,
        secondary=secondary,
        items=items,
        **kwargs,
    )
    del items
    batches = batchify(instances, batch_size) if batch_size else (instances,)
    del instances
    models_order = tuple(arg_to_iter(models_order))

    for count, batch in enumerate(batches):
        LOGGER.info("processing batch #%d...", count + 1)

        models = defaultdict(list)
        for instance in batch:
            models[type(instance)].append(instance)
        order = models_order or tuple(models.keys())
        del batch

        for mdl in order:
            instances = models.pop(mdl, ())
            if not dry_run and instances:
                LOGGER.info("creating %d instances of %r", len(instances), mdl)
                mdl.objects.bulk_create(instances)

        if any(models.values()):
            LOGGER.warning(
                "some models have not been processed properly: %r",
                tuple(models.keys()),
            )

        del models

    del batches

    LOGGER.info("done processing")


def _parse_link_id(string, regex=LINK_ID_REGEX):
    if not string:
        return None, None

    match = regex.match(string)

    if not match:
        return None, None

    site = match.group(1) or None
    id_str = match.group(2) or None
    id_int = parse_int(id_str)
    id_ = id_str if id_int is None else id_int

    return site, id_


def _parse_link_ids(data, regex=LINK_ID_REGEX):
    result = defaultdict(lambda: defaultdict(list))
    for origin, links in data.items():
        _, id_orig = _parse_link_id(origin, regex)
        if id_orig is None:
            continue
        for site, id_dest in map(_parse_link_id, arg_to_iter(links)):
            if site and id_dest is not None:
                result[id_orig][site].append(id_dest)
    LOGGER.info("found links for %d items", len(result))
    return result


def _parse_link_file(file, regex=LINK_ID_REGEX):
    if isinstance(file, str):
        LOGGER.info("loading links from <%s>", file)
        with open(file) as file_obj:
            return _parse_link_file(file_obj, regex)
    data = json.load(file)
    return _parse_link_ids(data, regex)


def _load_add_data(files, id_field, *fields, in_format=None):
    objs = _load(*arg_to_iter(files), in_format=in_format)
    result = {
        o.get(id_field): {field: o[field] for field in fields if field in o}
        for o in objs
    }
    LOGGER.info("loaded %d data items", len(result))
    return result


def _make_user(name, add_data):
    if not name:
        return None
    name = name.lower()
    data = add_data.get(name) or {}
    data["name"] = name
    return User(**data)


class Command(BaseCommand):
    """Loads a file to the database"""

    help = "Loads files to the database"

    game_fields = frozenset(
        {
            "alt_name",
            "avg_rating",
            "bayes_rating",
            "bgg_id",
            "bgg_rank",
            "compilation",
            "complexity",
            "cooperative",
            "created_at",
            "description",
            "external_link",
            "image_url",
            "language_dependency",
            "max_age",
            "max_age_rec",
            "max_players",
            "max_players_best",
            "max_players_rec",
            "max_time",
            "min_age",
            "min_age_rec",
            "min_players",
            "min_players_best",
            "min_players_rec",
            "min_time",
            "modified_at",
            "name",
            "num_votes",
            "rec_rank",
            "rec_rating",
            "scraped_at",
            "stddev_rating",
            "url",
            "video_url",
            "year",
        }
    )

    game_fields_mapping = {
        "rank": "bgg_rank",
        "image_blurhash": jmespath.compile("[].blurhash").search,
    }

    game_item_mapping = {
        "available_on_bga": lambda item: any(
            family and family.get("id") == FAMILY_ID_BGA
            for family in map(_parse_value_id, arg_to_iter(item.get("family")))
        ),
    }

    game_fields_foreign = {
        "artist": (Person, "name"),
        "category": (Category, "name"),
        "designer": (Person, "name"),
        "game_type": (GameType, "name"),
        "mechanic": (Mechanic, "name"),
    }

    game_fields_recursive = {
        "compilation_of": "compilation_of",
        "implementation": "implements",
        "integration": "integrates_with",
    }

    collection_fields = ()

    collection_fields_mapping = {
        "bgg_id": "game_id",
        # 'bgg_user_name': 'user_id',
        "bgg_user_rating": "rating",
        "bgg_user_wishlist": "wishlist",
        "bgg_user_play_count": "play_count",
    }

    collection_item_mapping = {
        "user_id": lambda item: item.get("bgg_user_name", "").lower() or None,
        "owned": lambda item: bool(
            item.get("bgg_user_owned")
            or item.get("bgg_user_prev_owned")
            or item.get("bgg_user_preordered")
        ),
    }

    user_fields = ()

    user_fields_mapping = {"updated_at": parse_date}

    user_item_mapping = {
        "name": lambda item: item.get("bgg_user_name", "").lower() or None,
    }

    linked_sites = (
        "freebase",
        "wikidata",
        "wikipedia",
        "dbpedia",
        "luding",
        "spielen",
    )

    def add_arguments(self, parser):
        parser.add_argument("paths", nargs="+", help="game file(s) to be processed")
        parser.add_argument(
            "--collection-paths",
            "-c",
            nargs="+",
            help="collection file(s) to be processed",
        )
        parser.add_argument(
            "--user-paths",
            "-u",
            nargs="+",
            help="user file(s) to be processed",
        )
        parser.add_argument(
            "--premium-user-dirs",
            "-p",
            nargs="+",
            help="premium user dirs(s) to be processed",
        )
        parser.add_argument(
            "--premium-user-paths",
            "-P",
            nargs="+",
            help="premium user file(s) to be processed",
        )
        parser.add_argument(
            "--in-format",
            "-f",
            choices=("json", "jsonl", "jl", "yaml", "yml"),
            help="input format",
        )
        parser.add_argument(
            "--batch",
            "-b",
            type=int,
            default=100_000,
            help="batch size for DB transactions",
        )
        parser.add_argument(
            "--recommender",
            "-r",
            default=getattr(settings, "RECOMMENDER_PATH", None),
            help="path to recommender model",
        )
        parser.add_argument(
            "--rankings",
            "-R",
            help="path to recommendation CSVs",
        )
        parser.add_argument(
            "--ranking-date",
            "-d",
            default=getattr(settings, "R_G_RANKING_EFFECTIVE_DATE", None),
            help="effective date for new R.G ranking",
        )
        parser.add_argument("--links", "-l", help="links JSON file location")
        parser.add_argument(
            "--dry-run",
            "-n",
            action="store_true",
            help="don't write to the database",
        )

    def handle(self, *args, **kwargs):
        logging.basicConfig(
            stream=sys.stderr,
            level=logging.DEBUG if kwargs["verbosity"] > 1 else logging.INFO,
            format="%(asctime)s %(levelname)-8.8s [%(name)s:%(lineno)s] %(message)s",
        )

        LOGGER.info(kwargs)

        items = tuple(_load(*kwargs["paths"]))
        # pylint: disable=no-member
        add_data = _rating_data(
            recommender_path=kwargs["recommender"],
            pk_field=Game._meta.pk.name,
            rankings_path=kwargs["rankings"],
            r_g_ranking_effective_date=kwargs["ranking_date"],
        )
        game_item_mapping = dict(self.game_item_mapping or {})

        if kwargs["links"] and self.linked_sites:
            links = _parse_link_file(kwargs["links"])

            def _find_links(item, site, links=links):
                return links[item.get("bgg_id")][site]

            for site in self.linked_sites:
                game_item_mapping[f"{site}_id"] = partial(
                    _find_links,
                    site=site,
                    links=links,
                )

        _create_from_items(
            model=Game,
            items=items,
            fields=self.game_fields,
            fields_mapping=self.game_fields_mapping,
            item_mapping=game_item_mapping,
            add_data=add_data,
            batch_size=kwargs["batch"],
            dry_run=kwargs["dry_run"],
        )

        del add_data

        _create_references(
            model=Game,
            items=items,
            foreign=self.game_fields_foreign,
            recursive=self.game_fields_recursive,
            batch_size=kwargs["batch"],
            dry_run=kwargs["dry_run"],
        )

        _create_clusters(
            model=Game,
            recommender_path=kwargs["recommender"],
            batch_size=kwargs["batch"],
            dry_run=kwargs["dry_run"],
        )

        if kwargs["collection_paths"]:
            game_pks = frozenset(item.get("bgg_id") for item in items)
            items = _load(*kwargs["collection_paths"], in_format=kwargs["in_format"])
            items = (item for item in items if item.get("bgg_id") in game_pks)

            add_data = _load_add_data(
                kwargs["user_paths"],
                "bgg_user_name",
                "updated_at",
                in_format=kwargs["in_format"],
            )
            premium_users = load_premium_users(
                dirs=kwargs.get("premium_user_dirs"),
                files=kwargs.get("premium_user_paths"),
            )
            secondary = {
                "model": partial(_make_user, add_data=add_data) if add_data else User,
                "from": "user_id",
                "to": "name",
                "include_pks": premium_users,
            }
            del add_data, premium_users

            _create_secondary_instances(
                model=Collection,
                secondary=secondary,
                items=items,
                models_order=(User, Collection),
                fields=self.collection_fields,
                fields_mapping=self.collection_fields_mapping,
                item_mapping=self.collection_item_mapping,
                batch_size=kwargs["batch"],
                dry_run=kwargs["dry_run"],
            )

        elif kwargs["user_paths"]:
            items = _load(*kwargs["user_paths"], in_format=kwargs["in_format"])
            _create_from_items(
                model=User,
                items=items,
                fields=self.user_fields,
                fields_mapping=self.user_fields_mapping,
                item_mapping=self.user_item_mapping,
                batch_size=kwargs["batch"],
                dry_run=kwargs["dry_run"],
            )

        del items

        LOGGER.info("done filling the database")
