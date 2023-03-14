#!/usr/bin/env python

"""
Pynt build file.

Make sure you installed all the Python dependencies (including dev) from Pipfile.lock:

```bash
pipenv shell
pipenv install --dev
```

Non-Python dependencies:

* Docker
* Google Cloud SDK: `gcloud components install docker-credential-gcr gsutil`
* `brew install git sqlite shellcheck hadolint`
* `npm install --global htmlhint jslint jshint csslint`
"""

import logging
import os
import shutil
import sys
from datetime import timedelta, timezone
from functools import lru_cache
from pathlib import Path

import django
from board_game_recommender import BGARecommender, BGGRecommender
from dotenv import load_dotenv
from pynt import task
from pyntcontrib import execute, safe_cd
from pytility import arg_to_iter, parse_bool, parse_date, parse_float, parse_int
from snaptime import snap

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv(verbose=True)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "rg.settings")
os.environ.setdefault("PYTHONPATH", BASE_DIR)
os.environ.setdefault("CLOUDSDK_PYTHON", "python3")
os.environ["DEBUG"] = ""
sys.path.insert(0, BASE_DIR)
django.setup()

LOGGER = logging.getLogger(__name__)
SETTINGS = django.conf.settings

DATA_DIR = SETTINGS.DATA_DIR
MODELS_DIR = SETTINGS.MODELS_DIR
SCRAPER_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "board-game-scraper"))
RECOMMENDER_DIR = os.path.abspath(
    os.path.join(BASE_DIR, "..", "board-game-recommender")
)
SCRAPED_DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "board-game-data"))

DATE_FORMAT_DASH = "%Y-%m-%dT%H-%M-%S"
DATE_FORMAT_COMPACT = "%Y%m%d-%H%M%S"

MIN_VOTES_ANCHOR_DATE = SETTINGS.MIN_VOTES_ANCHOR_DATE
MIN_VOTES_SECONDS_PER_STEP = SETTINGS.MIN_VOTES_SECONDS_PER_STEP

URL_LIVE = "https://recommend.games/"
GC_PROJECT = os.getenv("GC_PROJECT") or "recommend-games"
GC_DATA_BUCKET = os.getenv("GC_DATA_BUCKET") or f"{GC_PROJECT}-data"

GAMES_CSV_COLUMNS = (
    "bgg_id",
    "name",
    "year",
    "game_type",
    "designer",
    "artist",
    "publisher",
    "min_players",
    "max_players",
    "min_players_rec",
    "max_players_rec",
    "min_players_best",
    "max_players_best",
    "min_age",
    "min_age_rec",
    "min_time",
    "max_time",
    "category",
    "mechanic",
    "cooperative",
    "compilation",
    "compilation_of",
    "family",
    "implementation",
    "integration",
    "rank",
    "num_votes",
    "avg_rating",
    "stddev_rating",
    "bayes_rating",
    "complexity",
    "language_dependency",
    "bga_id",
    "dbpedia_id",
    "luding_id",
    "spielen_id",
    "wikidata_id",
    "wikipedia_id",
)

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8.8s [%(name)s:%(lineno)s] %(message)s",
)

LOGGER.info("currently in Google Cloud project <%s>", GC_PROJECT)


@lru_cache(maxsize=8)
def _server_version(path=os.path.join(BASE_DIR, "VERSION")):
    with open(path, encoding="utf-8") as file:
        version = file.read()
    return version.strip()


def _remove(path):
    LOGGER.info("Removing <%s> if it exists...", path)
    try:
        os.remove(path)
    except OSError:
        shutil.rmtree(path, ignore_errors=True)


@task()
def gitprepare(repo=SCRAPED_DATA_DIR):
    """check Git repo is clean and up-to-date"""
    LOGGER.info("Preparing Git repo <%s>...", repo)
    with safe_cd(repo):
        try:
            execute("git", "checkout", "master")
            execute("git", "pull", "--ff-only")
            execute("git", "diff", "HEAD", "--name-only")
        except SystemExit:
            LOGGER.exception("There was a problem preparing <%s>...", repo)


@task()
def gitupdate(*paths, repo=SCRAPED_DATA_DIR, name=__name__):
    """commit and push Git repo"""
    paths = paths or ("COUNT.md", "rankings", "scraped", "links.json", "prefixes.txt")
    LOGGER.info("Updating paths %r in Git repo <%s>...", paths, repo)
    with safe_cd(repo):
        try:
            execute("git", "gc", "--prune=now")
            execute("git", "add", "--", *paths)
        except SystemExit:
            LOGGER.exception("There was a problem in repo <%s>...", repo)

        try:
            execute(
                "git",
                "commit",
                "--no-gpg-sign",
                "--message",
                f"automatic commit by <{name}>",
            )
            execute("git", "gc", "--prune=now")
        except SystemExit:
            LOGGER.info("Nothing to commit...")

        try:
            execute("git", "push", "framagit", "master")
        except SystemExit:
            LOGGER.exception("Unable to push...")


@task()
def merge(in_paths, out_path, **kwargs):
    """merge scraped files"""
    from board_game_scraper.merge import merge_files

    kwargs.setdefault("log_level", "WARN")
    out_path = str(out_path).format(
        date=django.utils.timezone.now().strftime(DATE_FORMAT_DASH),
    )

    LOGGER.info(
        "Merging files <%s> into <%s> with args %r...",
        in_paths,
        out_path,
        kwargs,
    )

    _remove(out_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    merge_files(in_paths=in_paths, out_path=out_path, **kwargs)


# TODO use merge_config from board-game-scraper (#328)
def _merge_kwargs(
    site,
    item="GameItem",
    in_paths=None,
    out_path=None,
    full=False,
    **kwargs,
):
    kwargs["in_paths"] = in_paths or os.path.join(SCRAPER_DIR, "feeds", site, item, "*")
    kwargs.setdefault("keys", f"{site}_id")
    kwargs.setdefault("key_types", "int" if site in ("bgg", "luding") else "str")
    kwargs.setdefault("latest", "scraped_at")
    kwargs.setdefault("latest_types", "date")
    kwargs.setdefault("concat_output", True)

    if parse_bool(full):
        kwargs["out_path"] = out_path or os.path.join(
            SCRAPER_DIR,
            "feeds",
            site,
            item,
            "{date}_merged.jl",
        )

    else:
        kwargs["out_path"] = out_path or os.path.join(
            SCRAPED_DATA_DIR,
            "scraped",
            f"{site}_{item}.jl",
        )
        kwargs.setdefault(
            "fieldnames_exclude",
            ("published_at", "updated_at", "scraped_at"),
        )
        kwargs.setdefault("sort_keys", True)

    return kwargs


@task()
def mergebga(in_paths=None, out_path=None, full=False):
    """merge Board Game Atlas game data"""
    latest_min = None  # django.utils.timezone.now() - timedelta(days=days)
    merge(
        **_merge_kwargs(
            site="bga",
            in_paths=in_paths,
            out_path=out_path,
            full=full,
            latest_min=latest_min,
        )
    )


@task()
def mergebgaratings(in_paths=None, out_path=None, full=False):
    """merge Board Game Atlas rating data"""
    latest_min = None  # django.utils.timezone.now() - timedelta(days=days)
    merge(
        **_merge_kwargs(
            site="bga",
            item="RatingItem",
            in_paths=in_paths,
            out_path=out_path,
            full=full,
            latest_min=latest_min,
            keys=("bga_user_id", "bga_id"),
            fieldnames_exclude=("bgg_user_play_count",)
            if parse_bool(full)
            else ("bgg_user_play_count", "published_at", "updated_at", "scraped_at"),
        )
    )


@task()
def mergebgg(in_paths=None, out_path=None, full=False):
    """merge BoardGameGeek game data"""
    merge(**_merge_kwargs(site="bgg", in_paths=in_paths, out_path=out_path, full=full))


@task()
def mergebggusers(in_paths=None, out_path=None, full=False):
    """merge BoardGameGeek user data"""
    merge(
        **_merge_kwargs(
            site="bgg",
            item="UserItem",
            in_paths=in_paths,
            out_path=out_path,
            full=full,
            keys="bgg_user_name",
            key_types="istr",
            fieldnames_exclude=None
            if parse_bool(full)
            else ("published_at", "scraped_at"),
        )
    )


@task()
def mergebggratings(in_paths=None, out_path=None, full=False):
    """merge BoardGameGeek rating data"""
    merge(
        **_merge_kwargs(
            site="bgg",
            item="RatingItem",
            in_paths=in_paths,
            out_path=out_path,
            full=full,
            keys=("bgg_user_name", "bgg_id"),
            key_types=("istr", "int"),
            fieldnames_exclude=None
            if parse_bool(full)
            else ("published_at", "scraped_at"),
        )
    )


@task()
def mergebggrankings(in_paths=None, out_path=None, full=False, days=None):
    """merge BoardGameGeek ranking data"""

    full = parse_bool(full)
    days = parse_int(days)
    days = 7 if not days and not full else days
    latest_min = django.utils.timezone.now() - timedelta(days=days) if days else None

    merge(
        **_merge_kwargs(
            site="bgg_rankings",
            item="GameItem",
            in_paths=in_paths,
            out_path=out_path,
            full=full,
            keys=("published_at", "bgg_id"),
            key_types=("date", "int"),
            latest_min=latest_min,
            fieldnames=None
            if full
            else (
                "published_at",
                "bgg_id",
                "rank",
                "name",
                "year",
                "num_votes",
                "bayes_rating",
                "avg_rating",
            ),
            fieldnames_exclude=None,
            sort_keys=False,
            sort_fields=("published_at", "rank"),
        )
    )


@task()
def mergebgghotness(in_paths=None, out_path=None, full=False, days=None):
    """Merge BoardGameGeek hotness data."""

    full = parse_bool(full)
    days = parse_int(days)
    latest_min = django.utils.timezone.now() - timedelta(days=days) if days else None

    merge(
        **_merge_kwargs(
            site="bgg_hotness",
            item="GameItem",
            in_paths=in_paths,
            out_path=out_path,
            full=full,
            keys=("published_at", "bgg_id"),
            key_types=("date", "int"),
            latest_min=latest_min,
            fieldnames=None
            if full
            else (
                "published_at",
                "rank",
                "bgg_id",
                "name",
                "year",
                "image_url",
            ),
            fieldnames_exclude=None,
            sort_keys=False,
            sort_fields=("published_at", "rank"),
        )
    )


@task()
def mergebggabstract(in_paths=None, out_path=None, full=False, days=None):
    """merge BoardGameGeek abstract ranking data"""

    full = parse_bool(full)
    days = parse_int(days)
    days = 7 if not days and not full else days
    latest_min = django.utils.timezone.now() - timedelta(days=days) if days else None

    merge(
        **_merge_kwargs(
            site="bgg_rankings_abstract",
            item="GameItem",
            in_paths=in_paths,
            out_path=out_path,
            full=full,
            keys=("published_at", "bgg_id"),
            key_types=("date", "int"),
            latest_min=latest_min,
            fieldnames=None
            if full
            else (
                "published_at",
                "bgg_id",
                "rank",
                "name",
                "year",
                "num_votes",
                "bayes_rating",
                "avg_rating",
            ),
            fieldnames_exclude=None,
            sort_keys=False,
            sort_fields=("published_at", "rank"),
        )
    )


@task()
def mergebggchildren(in_paths=None, out_path=None, full=False, days=None):
    """merge BoardGameGeek children ranking data"""

    full = parse_bool(full)
    days = parse_int(days)
    days = 7 if not days and not full else days
    latest_min = django.utils.timezone.now() - timedelta(days=days) if days else None

    merge(
        **_merge_kwargs(
            site="bgg_rankings_children",
            item="GameItem",
            in_paths=in_paths,
            out_path=out_path,
            full=full,
            keys=("published_at", "bgg_id"),
            key_types=("date", "int"),
            latest_min=latest_min,
            fieldnames=None
            if full
            else (
                "published_at",
                "bgg_id",
                "rank",
                "name",
                "year",
                "num_votes",
                "bayes_rating",
                "avg_rating",
            ),
            fieldnames_exclude=None,
            sort_keys=False,
            sort_fields=("published_at", "rank"),
        )
    )


@task()
def mergebggcustomizable(in_paths=None, out_path=None, full=False, days=None):
    """merge BoardGameGeek customizable ranking data"""

    full = parse_bool(full)
    days = parse_int(days)
    days = 7 if not days and not full else days
    latest_min = django.utils.timezone.now() - timedelta(days=days) if days else None

    merge(
        **_merge_kwargs(
            site="bgg_rankings_customizable",
            item="GameItem",
            in_paths=in_paths,
            out_path=out_path,
            full=full,
            keys=("published_at", "bgg_id"),
            key_types=("date", "int"),
            latest_min=latest_min,
            fieldnames=None
            if full
            else (
                "published_at",
                "bgg_id",
                "rank",
                "name",
                "year",
                "num_votes",
                "bayes_rating",
                "avg_rating",
            ),
            fieldnames_exclude=None,
            sort_keys=False,
            sort_fields=("published_at", "rank"),
        )
    )


@task()
def mergebggfamily(in_paths=None, out_path=None, full=False, days=None):
    """merge BoardGameGeek family ranking data"""

    full = parse_bool(full)
    days = parse_int(days)
    days = 7 if not days and not full else days
    latest_min = django.utils.timezone.now() - timedelta(days=days) if days else None

    merge(
        **_merge_kwargs(
            site="bgg_rankings_family",
            item="GameItem",
            in_paths=in_paths,
            out_path=out_path,
            full=full,
            keys=("published_at", "bgg_id"),
            key_types=("date", "int"),
            latest_min=latest_min,
            fieldnames=None
            if full
            else (
                "published_at",
                "bgg_id",
                "rank",
                "name",
                "year",
                "num_votes",
                "bayes_rating",
                "avg_rating",
            ),
            fieldnames_exclude=None,
            sort_keys=False,
            sort_fields=("published_at", "rank"),
        )
    )


@task()
def mergebggparty(in_paths=None, out_path=None, full=False, days=None):
    """merge BoardGameGeek party ranking data"""

    full = parse_bool(full)
    days = parse_int(days)
    days = 7 if not days and not full else days
    latest_min = django.utils.timezone.now() - timedelta(days=days) if days else None

    merge(
        **_merge_kwargs(
            site="bgg_rankings_party",
            item="GameItem",
            in_paths=in_paths,
            out_path=out_path,
            full=full,
            keys=("published_at", "bgg_id"),
            key_types=("date", "int"),
            latest_min=latest_min,
            fieldnames=None
            if full
            else (
                "published_at",
                "bgg_id",
                "rank",
                "name",
                "year",
                "num_votes",
                "bayes_rating",
                "avg_rating",
            ),
            fieldnames_exclude=None,
            sort_keys=False,
            sort_fields=("published_at", "rank"),
        )
    )


@task()
def mergebggstrategy(in_paths=None, out_path=None, full=False, days=None):
    """merge BoardGameGeek strategy ranking data"""

    full = parse_bool(full)
    days = parse_int(days)
    days = 7 if not days and not full else days
    latest_min = django.utils.timezone.now() - timedelta(days=days) if days else None

    merge(
        **_merge_kwargs(
            site="bgg_rankings_strategy",
            item="GameItem",
            in_paths=in_paths,
            out_path=out_path,
            full=full,
            keys=("published_at", "bgg_id"),
            key_types=("date", "int"),
            latest_min=latest_min,
            fieldnames=None
            if full
            else (
                "published_at",
                "bgg_id",
                "rank",
                "name",
                "year",
                "num_votes",
                "bayes_rating",
                "avg_rating",
            ),
            fieldnames_exclude=None,
            sort_keys=False,
            sort_fields=("published_at", "rank"),
        )
    )


@task()
def mergebggthematic(in_paths=None, out_path=None, full=False, days=None):
    """merge BoardGameGeek thematic ranking data"""

    full = parse_bool(full)
    days = parse_int(days)
    days = 7 if not days and not full else days
    latest_min = django.utils.timezone.now() - timedelta(days=days) if days else None

    merge(
        **_merge_kwargs(
            site="bgg_rankings_thematic",
            item="GameItem",
            in_paths=in_paths,
            out_path=out_path,
            full=full,
            keys=("published_at", "bgg_id"),
            key_types=("date", "int"),
            latest_min=latest_min,
            fieldnames=None
            if full
            else (
                "published_at",
                "bgg_id",
                "rank",
                "name",
                "year",
                "num_votes",
                "bayes_rating",
                "avg_rating",
            ),
            fieldnames_exclude=None,
            sort_keys=False,
            sort_fields=("published_at", "rank"),
        )
    )


@task()
def mergebggwar(in_paths=None, out_path=None, full=False, days=None):
    """merge BoardGameGeek war ranking data"""

    full = parse_bool(full)
    days = parse_int(days)
    days = 7 if not days and not full else days
    latest_min = django.utils.timezone.now() - timedelta(days=days) if days else None

    merge(
        **_merge_kwargs(
            site="bgg_rankings_war",
            item="GameItem",
            in_paths=in_paths,
            out_path=out_path,
            full=full,
            keys=("published_at", "bgg_id"),
            key_types=("date", "int"),
            latest_min=latest_min,
            fieldnames=None
            if full
            else (
                "published_at",
                "bgg_id",
                "rank",
                "name",
                "year",
                "num_votes",
                "bayes_rating",
                "avg_rating",
            ),
            fieldnames_exclude=None,
            sort_keys=False,
            sort_fields=("published_at", "rank"),
        )
    )


@task()
def mergedbpedia(in_paths=None, out_path=None, full=False):
    """merge DBpedia game data"""
    merge(
        **_merge_kwargs(
            site="dbpedia",
            in_paths=in_paths,
            out_path=out_path,
            full=full,
        )
    )


@task()
def mergeluding(in_paths=None, out_path=None, full=False):
    """merge Luding.org game data"""
    merge(
        **_merge_kwargs(
            site="luding",
            in_paths=in_paths,
            out_path=out_path,
            full=full,
        )
    )


@task()
def mergespielen(in_paths=None, out_path=None, full=False):
    """merge Spielen.de game data"""
    merge(
        **_merge_kwargs(
            site="spielen",
            in_paths=in_paths,
            out_path=out_path,
            full=full,
        )
    )


@task()
def mergewikidata(in_paths=None, out_path=None, full=False):
    """merge Wikidata game data"""
    merge(
        **_merge_kwargs(
            site="wikidata",
            in_paths=in_paths,
            out_path=out_path,
            full=full,
        )
    )


@task()
def mergenews(
    in_paths=(
        os.path.join(SCRAPER_DIR, "feeds", "news", "*.jl"),
        os.path.join(SCRAPER_DIR, "feeds", "news", "*", "*", "*.jl"),
    ),
    out_path=None,
):
    """merge news articles"""
    merge(
        **_merge_kwargs(
            site="news",
            item="ArticleItem",
            in_paths=in_paths,
            out_path=out_path,
            keys=("article_id",),
            latest=("published_at", "scraped_at"),
            latest_types=("date", "date"),
            latest_min=None,
            latest_required=True,
            fieldnames=(
                "article_id",
                "url_canonical",
                "url_mobile",
                "url_amp",
                "url_thumbnail",
                "published_at",
                "title_full",
                "title_short",
                "author",
                "description",
                "summary",
                "category",
                "keyword",
                "section_inferred",
                "country",
                "language",
                "source_name",
            ),
            fieldnames_exclude=None,
            sort_keys=False,
            sort_latest=True,
            sort_descending=True,
        )
    )


@task(
    mergebga,
    mergebgg,
    mergedbpedia,
    mergeluding,
    mergespielen,
    mergewikidata,
    mergenews,
    mergebgaratings,
    mergebggusers,
    mergebggratings,
    mergebggrankings,
    mergebgghotness,
    mergebggabstract,
    mergebggchildren,
    mergebggcustomizable,
    mergebggfamily,
    mergebggparty,
    mergebggstrategy,
    mergebggthematic,
    mergebggwar,
)
def mergeall():
    """merge all sites and items"""


@task()
def split(
    in_file=os.path.join(SCRAPED_DATA_DIR, "scraped", "bgg_RatingItem.jl"),
    out_dir=os.path.join(SCRAPED_DATA_DIR, "scraped", "bgg_RatingItem"),
    trie_file=os.path.join(SCRAPED_DATA_DIR, "prefixes.txt"),
    fields="bgg_user_name",
    limit=300_000,
    construct=False,
):
    """split file along prefixes"""
    from board_game_scraper.prefixes import split_file

    _remove(out_dir)
    split_file(
        in_file=in_file,
        out_file=os.path.join(out_dir, "{prefix}.jl"),
        fields=fields,
        trie_file=trie_file,
        limits=(parse_int(limit),),
        construct=parse_bool(construct),
    )
    _remove(in_file)


@task()
def link(
    gazetteer=os.path.join(MODELS_DIR, "cluster", "gazetteer.pickle"),
    paths=(
        os.path.join(SCRAPED_DATA_DIR, "scraped", "bgg_GameItem.jl"),
        os.path.join(SCRAPED_DATA_DIR, "scraped", "bga_GameItem.jl"),
        os.path.join(SCRAPED_DATA_DIR, "scraped", "spielen_GameItem.jl"),
        os.path.join(SCRAPED_DATA_DIR, "scraped", "luding_GameItem.jl"),
        os.path.join(SCRAPED_DATA_DIR, "scraped", "wikidata_GameItem.jl"),
    ),
    training_file=os.path.join(MODELS_DIR, "cluster", "training.json"),
    manual_labelling=False,
    threshold=None,
    output=os.path.join(SCRAPED_DATA_DIR, "links.json"),
    pretty_print=True,
):
    """link items"""

    try:
        from board_game_scraper.cluster import link_games

        LOGGER.info("Using model %r to link files %r...", gazetteer, paths)

        link_games(
            gazetteer=gazetteer,
            paths=paths,
            training_file=training_file if manual_labelling else None,
            manual_labelling=parse_bool(manual_labelling),
            threshold=parse_float(threshold),
            output=output,
            pretty_print=parse_bool(pretty_print),
        )
    except Exception:
        LOGGER.exception("Linking failed…")


@task()
def labellinks(
    gazetteer=os.path.join(MODELS_DIR, "cluster", "gazetteer.pickle"),
    paths=(
        os.path.join(SCRAPED_DATA_DIR, "scraped", "bgg_GameItem.jl"),
        os.path.join(SCRAPED_DATA_DIR, "scraped", "bga_GameItem.jl"),
        os.path.join(SCRAPED_DATA_DIR, "scraped", "spielen_GameItem.jl"),
        os.path.join(SCRAPED_DATA_DIR, "scraped", "luding_GameItem.jl"),
        os.path.join(SCRAPED_DATA_DIR, "scraped", "wikidata_GameItem.jl"),
    ),
    training_file=os.path.join(MODELS_DIR, "cluster", "training.json"),
    threshold=None,
    output=os.path.join(SCRAPED_DATA_DIR, "links.json"),
    pretty_print=True,
):
    """label new training examples and link items"""
    link(
        gazetteer=gazetteer,
        paths=paths,
        training_file=training_file,
        manual_labelling=True,
        threshold=parse_float(threshold),
        output=output,
        pretty_print=parse_bool(pretty_print),
    )


def _train(
    recommender_cls,
    games_file,
    ratings_file,
    out_path=None,
    users=None,
    max_iterations=100,
    **filters,
):
    LOGGER.info(
        "Training %r recommender model with games <%s> and ratings <%s>...",
        recommender_cls,
        games_file,
        ratings_file,
    )
    recommender = recommender_cls.train_from_files(
        games_file=games_file,
        ratings_file=ratings_file,
        similarity_model=True,
        max_iterations=parse_int(max_iterations),
        verbose=True,
        **filters,
    )

    recommendations = recommender.recommend(users=users, num_games=100)
    recommendations.print_rows(num_rows=100)

    if out_path:
        LOGGER.info("Saving model %r to <%s>...", recommender, out_path)
        shutil.rmtree(out_path, ignore_errors=True)
        recommender.save(out_path)


def _min_votes_from_date(
    first_date,
    second_date,
    seconds_per_step,
    max_value,
    min_value=1,
):
    first_date = parse_date(first_date, tzinfo=timezone.utc)
    second_date = (
        parse_date(second_date, tzinfo=timezone.utc) or django.utils.timezone.now()
    )
    seconds_per_step = parse_float(seconds_per_step)
    max_value = parse_int(max_value)
    min_value = parse_int(min_value)

    if (
        not first_date
        or not second_date
        or not seconds_per_step
        or max_value is None
        or min_value is None
    ):
        return None

    LOGGER.info(
        "Comparing %s and %s to compute required votes",
        first_date,
        second_date,
    )

    delta = second_date - first_date
    seconds = delta.total_seconds()
    steps = parse_int(seconds / seconds_per_step)

    LOGGER.info(
        "%.1f seconds have passed between first and second date, i.e., %d steps",
        seconds,
        steps,
    )

    return min(max(max_value - steps, min_value), max_value)


@task()
def trainbgg(
    games_file=os.path.join(SCRAPED_DATA_DIR, "scraped", "bgg_GameItem.jl"),
    ratings_file=os.path.join(SCRAPED_DATA_DIR, "scraped", "bgg_RatingItem.jl"),
    out_path=os.path.join(RECOMMENDER_DIR, ".bgg"),
    users=None,
    max_iterations=1000,
    min_votes=None,
    min_votes_anchor_date=MIN_VOTES_ANCHOR_DATE,
    min_votes_seconds_per_step=MIN_VOTES_SECONDS_PER_STEP,
    # pylint: disable=no-member
    min_votes_max_value=BGGRecommender.default_filters.get("num_votes__gte"),
):
    """train BoardGameGeek recommender model"""

    filters = {}

    min_votes = parse_int(min_votes) or _min_votes_from_date(
        first_date=min_votes_anchor_date,
        second_date=None,
        seconds_per_step=min_votes_seconds_per_step,
        max_value=min_votes_max_value,
        min_value=1,
    )

    if min_votes is not None:
        LOGGER.info("Filter out games with less than %d votes", min_votes)
        filters["num_votes__gte"] = min_votes

    _train(
        recommender_cls=BGGRecommender,
        games_file=games_file,
        ratings_file=ratings_file,
        out_path=out_path,
        users=users,
        max_iterations=max_iterations,
        **filters,
    )


@task()
def trainbga(
    games_file=os.path.join(SCRAPED_DATA_DIR, "scraped", "bga_GameItem.jl"),
    ratings_file=os.path.join(SCRAPED_DATA_DIR, "scraped", "bga_RatingItem.jl"),
    out_path=os.path.join(RECOMMENDER_DIR, ".bga"),
    users=None,
    max_iterations=1000,
):
    """train Board Game Atlas recommender model"""
    _train(
        recommender_cls=BGARecommender,
        games_file=games_file,
        ratings_file=ratings_file,
        out_path=out_path,
        users=users,
        max_iterations=max_iterations,
    )


@task(trainbgg, trainbga)
def train():
    """train BoardGameGeek and Board Game Atlas recommender models"""


def _save_ranking(
    recommender,
    dst_dir,
    file_name=f"{DATE_FORMAT_COMPACT}.csv",
    similarity_model=False,
):
    from games.utils import save_recommender_ranking

    file_name = django.utils.timezone.now().strftime(file_name)
    dst_path = os.path.join(dst_dir, file_name)

    _remove(dst_path)
    os.makedirs(dst_dir, exist_ok=True)

    save_recommender_ranking(recommender, dst_path, similarity_model)


def _save_rg_ranking(
    recommender,
    path_ratings,
    top,
    min_ratings,
    dst_dir,
    file_name=f"{DATE_FORMAT_COMPACT}.csv",
):
    from board_game_recommender.rankings import calculate_rankings

    dst_dir = Path(dst_dir).resolve()
    dst_path = dst_dir / django.utils.timezone.now().strftime(file_name)
    path_ratings = Path(path_ratings).resolve()

    LOGGER.info(
        "Calculate R.G rankings from model <%s> and ratings from <%s>",
        recommender,
        path_ratings,
    )
    LOGGER.info(
        "Using top %d games and %d min ratings, saving results to <%s>…",
        top,
        min_ratings,
        dst_path,
    )

    rankings = calculate_rankings(
        recommender=recommender,
        path_ratings=str(path_ratings),
        top=top,
        min_ratings=min_ratings,
    )

    LOGGER.info("Calculated R.G rankings for %d games", len(rankings))

    _remove(dst_path)
    dst_dir.mkdir(parents=True, exist_ok=True)

    rankings.rename({"rank": "rank_raw", "score": "score_raw"}, inplace=True)
    rankings.rename({"rank_weighted": "rank", "score_weighted": "score"}, inplace=True)
    rankings = rankings[
        "rank",
        "bgg_id",
        "score",
        "rank_raw",
        "score_raw",
        "avg_rating",
        "num_votes",
    ]
    rankings = rankings.sort("rank")

    rankings.export_csv(str(dst_path))


@task()
def savebggrankings(
    recommender_path=os.path.join(RECOMMENDER_DIR, ".bgg"),
    ratings_path=Path(SCRAPED_DATA_DIR).resolve() / "scraped" / "bgg_RatingItem.jl",
    dst_dir=os.path.join(SCRAPED_DATA_DIR, "rankings", "bgg"),
    file_name=f"{DATE_FORMAT_COMPACT}.csv",
    top_k_games=100,
    min_ratings=10,
):
    """Take a snapshot of the BoardGameGeek rankings."""
    from games.utils import load_recommender

    recommender_path = Path(recommender_path).resolve()
    ratings_path = Path(ratings_path).resolve()
    dst_dir = Path(dst_dir).resolve()
    top_k_games = parse_int(top_k_games) or 100
    min_ratings = parse_int(min_ratings) or 10

    LOGGER.info("Loading BoardGameGeek recommender from <%s>...", recommender_path)
    recommender = load_recommender(recommender_path, site="bgg")

    _save_ranking(
        recommender=recommender,
        dst_dir=dst_dir / "factor",
        file_name=file_name,
        similarity_model=False,
    )

    _save_ranking(
        recommender=recommender,
        dst_dir=dst_dir / "similarity",
        file_name=file_name,
        similarity_model=True,
    )

    _save_rg_ranking(
        recommender=recommender,
        path_ratings=ratings_path,
        top=top_k_games,
        min_ratings=min_ratings,
        dst_dir=dst_dir / "r_g",
        file_name=file_name,
    )


@task()
def savebgarankings(
    recommender_path=os.path.join(RECOMMENDER_DIR, ".bga"),
    dst_dir=os.path.join(SCRAPED_DATA_DIR, "rankings", "bga"),
    file_name=f"{DATE_FORMAT_COMPACT}.csv",
):
    """Take a snapshot of the Board Game Atlas rankings."""
    from games.utils import load_recommender

    LOGGER.info("Loading Board Game Atlas recommender from <%s>...", recommender_path)
    recommender = load_recommender(recommender_path, site="bga")
    _save_ranking(
        recommender=recommender,
        dst_dir=os.path.join(dst_dir, "factor"),
        file_name=file_name,
        similarity_model=False,
    )
    _save_ranking(
        recommender=recommender,
        dst_dir=os.path.join(dst_dir, "similarity"),
        file_name=file_name,
        similarity_model=True,
    )


@task(savebggrankings, savebgarankings)
def saverankings():
    """Take a snapshot of both BoardGameGeek and Board Game Atlas rankings."""


@task()
def weeklycharts(
    src_file=Path(SCRAPED_DATA_DIR) / "scraped" / "bgg_RatingItem.jl",
    dst_dir=Path(SCRAPED_DATA_DIR) / "rankings" / "bgg" / "charts",
    dst_file=f"{DATE_FORMAT_COMPACT}.csv",
    overwrite=False,
):
    """Generate charts files."""

    src_file = Path(src_file).resolve()
    dst_dir = Path(dst_dir).resolve()
    max_date = snap(django.utils.timezone.now(), "@week5@week1")
    latest_file = dst_dir / max_date.strftime(dst_file)
    overwrite = parse_bool(overwrite)

    if not overwrite and latest_file.exists():
        LOGGER.info(
            "Latest charts at <%s> already exist, skipping chart generation",
            latest_file,
        )
        return

    django.core.management.call_command(
        "charts",
        src_file,
        max_date=max_date,
        freq="week",
        out_dir=dst_dir,
        overwrite=overwrite,
    )


@task()
def cleandata(src_dir=DATA_DIR, bk_dir=f"{DATA_DIR}.bk"):
    """clean data file"""
    LOGGER.info(
        "Removing old backup dir <%s> (if any), moving current data dir to backup, "
        "and creating fresh data dir <%s>...",
        bk_dir,
        src_dir,
    )
    shutil.rmtree(bk_dir, ignore_errors=True)
    if os.path.exists(src_dir):
        os.rename(src_dir, bk_dir)
    os.makedirs(os.path.join(src_dir, "recommender_bgg"))
    os.makedirs(os.path.join(src_dir, "recommender_bga"))


@task()
def migrate():
    """database migration"""
    assert not SETTINGS.DEBUG
    django.core.management.call_command("migrate")


@task(cleandata, migrate)
def filldb(
    src_dir=SCRAPED_DATA_DIR,
    rec_dir=os.path.join(RECOMMENDER_DIR, ".bgg"),
    ranking_date=getattr(SETTINGS, "R_G_RANKING_EFFECTIVE_DATE", None),
    dry_run=False,
):
    """fill database"""
    LOGGER.info(
        "Uploading games and other data from <%s>, and recommendations from <%s> to database...",
        src_dir,
        rec_dir,
    )

    srp_dir = os.path.join(src_dir, "scraped")
    dry_run = parse_bool(dry_run)

    django.core.management.call_command(
        "filldb",
        os.path.join(srp_dir, "bgg_GameItem.jl"),
        collection_paths=[os.path.join(srp_dir, "bgg_RatingItem.jl")],
        user_paths=[os.path.join(srp_dir, "bgg_UserItem.jl")],
        in_format="jl",
        batch=100_000,
        recommender=rec_dir,
        rankings=Path(SCRAPED_DATA_DIR) / "rankings" / "bgg" / "r_g",
        ranking_date=ranking_date,
        links=os.path.join(src_dir, "links.json"),
        dry_run=dry_run,
    )


@task()
def kennerspiel(
    model_path=Path(MODELS_DIR) / "kennerspiel.joblib",
    batch_size=10_000,
    dry_run=False,
):
    """Calculate Kennerspiel scores and add them to the database."""

    model_path = Path(model_path).resolve()
    batch_size = parse_int(batch_size)
    dry_run = parse_bool(dry_run)

    LOGGER.info(
        "Calculate Kennerspiel scores with model <%s> and write them to the database",
        model_path,
    )

    django.core.management.call_command(
        "kennerspiel",
        model_path,
        batch=batch_size,
        dry_run=dry_run,
    )


@task()
def compressdb(db_file=os.path.join(DATA_DIR, "db.sqlite3")):
    """compress SQLite database file"""
    execute("sqlite3", db_file, "VACUUM;")


@task()
def cpdirs(
    src_dir=os.path.join(RECOMMENDER_DIR, ".bgg"),
    dst_dir=os.path.join(DATA_DIR, "recommender_bgg"),
    sub_dirs=("recommender", "similarity", "clusters", "compilations"),
):
    """copy recommender files"""
    sub_dirs = sub_dirs.split(",") if isinstance(sub_dirs, str) else sub_dirs
    for sub_dir in sub_dirs:
        src_path = os.path.join(src_dir, sub_dir)
        dst_path = os.path.join(dst_dir, sub_dir)
        LOGGER.info("Copying <%s> to <%s>...", src_path, dst_path)
        shutil.copytree(src_path, dst_path)


@task()
def cpdirsbga(
    src_dir=os.path.join(RECOMMENDER_DIR, ".bga"),
    dst_dir=os.path.join(DATA_DIR, "recommender_bga"),
    sub_dirs=("recommender", "similarity"),
):
    """copy BGA recommender files"""
    cpdirs(src_dir, dst_dir, sub_dirs)


@task()
def dateflag(dst=SETTINGS.MODEL_UPDATED_FILE, date=None):
    """write date to file"""
    from games.utils import serialize_date

    date = parse_date(date) or django.utils.timezone.now()
    date_str = serialize_date(date, tzinfo=django.utils.timezone.utc)
    LOGGER.info("Writing date <%s> to <%s>...", date_str, dst)
    with open(dst, "w", encoding="utf-8") as file:
        file.write(date_str)


@task()
def bggranking(
    dst=os.path.join(
        SCRAPED_DATA_DIR,
        "rankings",
        "bgg",
        "bgg",
        f"{DATE_FORMAT_COMPACT}.csv",
    ),
):
    """Saves a snapshot of the BGG rankings."""
    from games.utils import model_updated_at

    updated_at = model_updated_at() or django.utils.timezone.now()
    dst = updated_at.strftime(dst)
    django.core.management.call_command("bggranking", output=dst)


@task()
def splitrankings(
    src=os.path.join(SCRAPED_DATA_DIR, "scraped", "bgg_rankings_GameItem.jl"),
    dst_dir=os.path.join(SCRAPED_DATA_DIR, "rankings", "bgg", "bgg"),
    dst_file=f"{DATE_FORMAT_COMPACT}.csv",
    overwrite=False,
):
    """Split the rankings data as one CSV file per date."""
    django.core.management.call_command(
        "splitrankings",
        src,
        out_dir=dst_dir,
        out_file=dst_file,
        overwrite=parse_bool(overwrite),
    )


@task()
def splithotness(
    src=os.path.join(SCRAPED_DATA_DIR, "scraped", "bgg_hotness_GameItem.jl"),
    dst_dir=os.path.join(SCRAPED_DATA_DIR, "rankings", "bgg", "hotness"),
    dst_file=f"{DATE_FORMAT_COMPACT}.csv",
    overwrite=False,
):
    """Split the hotness data as one CSV file per date."""
    django.core.management.call_command(
        "splitrankings",
        src,
        out_dir=dst_dir,
        out_file=dst_file,
        columns=("rank", "bgg_id"),
        overwrite=parse_bool(overwrite),
    )


@task()
def splitabstract(
    src=os.path.join(SCRAPED_DATA_DIR, "scraped", "bgg_rankings_abstract_GameItem.jl"),
    dst_dir=os.path.join(SCRAPED_DATA_DIR, "rankings", "bgg", "bgg_abstract"),
    dst_file=f"{DATE_FORMAT_COMPACT}.csv",
    overwrite=False,
):
    """Split the abstract rankings data as one CSV file per date."""
    django.core.management.call_command(
        "splitrankings",
        src,
        out_dir=dst_dir,
        out_file=dst_file,
        overwrite=parse_bool(overwrite),
    )


@task()
def splitchildren(
    src=os.path.join(SCRAPED_DATA_DIR, "scraped", "bgg_rankings_children_GameItem.jl"),
    dst_dir=os.path.join(SCRAPED_DATA_DIR, "rankings", "bgg", "bgg_children"),
    dst_file=f"{DATE_FORMAT_COMPACT}.csv",
    overwrite=False,
):
    """Split the children rankings data as one CSV file per date."""
    django.core.management.call_command(
        "splitrankings",
        src,
        out_dir=dst_dir,
        out_file=dst_file,
        overwrite=parse_bool(overwrite),
    )


@task()
def splitcustomizable(
    src=os.path.join(
        SCRAPED_DATA_DIR, "scraped", "bgg_rankings_customizable_GameItem.jl"
    ),
    dst_dir=os.path.join(SCRAPED_DATA_DIR, "rankings", "bgg", "bgg_customizable"),
    dst_file=f"{DATE_FORMAT_COMPACT}.csv",
    overwrite=False,
):
    """Split the customizable rankings data as one CSV file per date."""
    django.core.management.call_command(
        "splitrankings",
        src,
        out_dir=dst_dir,
        out_file=dst_file,
        overwrite=parse_bool(overwrite),
    )


@task()
def splitfamily(
    src=os.path.join(SCRAPED_DATA_DIR, "scraped", "bgg_rankings_family_GameItem.jl"),
    dst_dir=os.path.join(SCRAPED_DATA_DIR, "rankings", "bgg", "bgg_family"),
    dst_file=f"{DATE_FORMAT_COMPACT}.csv",
    overwrite=False,
):
    """Split the family rankings data as one CSV file per date."""
    django.core.management.call_command(
        "splitrankings",
        src,
        out_dir=dst_dir,
        out_file=dst_file,
        overwrite=parse_bool(overwrite),
    )


@task()
def splitparty(
    src=os.path.join(SCRAPED_DATA_DIR, "scraped", "bgg_rankings_party_GameItem.jl"),
    dst_dir=os.path.join(SCRAPED_DATA_DIR, "rankings", "bgg", "bgg_party"),
    dst_file=f"{DATE_FORMAT_COMPACT}.csv",
    overwrite=False,
):
    """Split the party rankings data as one CSV file per date."""
    django.core.management.call_command(
        "splitrankings",
        src,
        out_dir=dst_dir,
        out_file=dst_file,
        overwrite=parse_bool(overwrite),
    )


@task()
def splitstrategy(
    src=os.path.join(SCRAPED_DATA_DIR, "scraped", "bgg_rankings_strategy_GameItem.jl"),
    dst_dir=os.path.join(SCRAPED_DATA_DIR, "rankings", "bgg", "bgg_strategy"),
    dst_file=f"{DATE_FORMAT_COMPACT}.csv",
    overwrite=False,
):
    """Split the strategy rankings data as one CSV file per date."""
    django.core.management.call_command(
        "splitrankings",
        src,
        out_dir=dst_dir,
        out_file=dst_file,
        overwrite=parse_bool(overwrite),
    )


@task()
def splitthematic(
    src=os.path.join(SCRAPED_DATA_DIR, "scraped", "bgg_rankings_thematic_GameItem.jl"),
    dst_dir=os.path.join(SCRAPED_DATA_DIR, "rankings", "bgg", "bgg_thematic"),
    dst_file=f"{DATE_FORMAT_COMPACT}.csv",
    overwrite=False,
):
    """Split the thematic rankings data as one CSV file per date."""
    django.core.management.call_command(
        "splitrankings",
        src,
        out_dir=dst_dir,
        out_file=dst_file,
        overwrite=parse_bool(overwrite),
    )


@task()
def splitwar(
    src=os.path.join(SCRAPED_DATA_DIR, "scraped", "bgg_rankings_war_GameItem.jl"),
    dst_dir=os.path.join(SCRAPED_DATA_DIR, "rankings", "bgg", "bgg_war"),
    dst_file=f"{DATE_FORMAT_COMPACT}.csv",
    overwrite=False,
):
    """Split the war rankings data as one CSV file per date."""
    django.core.management.call_command(
        "splitrankings",
        src,
        out_dir=dst_dir,
        out_file=dst_file,
        overwrite=parse_bool(overwrite),
    )


@task(
    splitrankings,
    splithotness,
    splitabstract,
    splitchildren,
    splitcustomizable,
    splitfamily,
    splitparty,
    splitstrategy,
    splitthematic,
    splitwar,
)
def splitall():
    """Split all rankings data."""


@task()
def historicalbggrankings(
    repo=os.path.abspath(os.path.join(BASE_DIR, "..", "bgg-ranking-historicals")),
    dst=os.path.join(
        SCRAPED_DATA_DIR,
        "rankings",
        "bgg",
        "bgg",
        f"{DATE_FORMAT_COMPACT}.csv",
    ),
    script=os.path.join(BASE_DIR, "scripts", "ranking.sh"),
    overwrite=False,
):
    """Save historical BGG rankings."""

    from games.utils import format_from_path

    LOGGER.info("Loading historical BGG rankings from <%s>...", repo)

    overwrite = parse_bool(overwrite)

    with safe_cd(repo):
        try:
            execute("git", "checkout", "master")
            execute("git", "pull")
        except SystemExit:
            LOGGER.exception(
                "There was a problem updating BGG rankings repo <%s>",
                repo,
            )

        for root, _, files in os.walk("."):
            for file in files:
                if format_from_path(file) != "csv":
                    continue

                date_str, _ = os.path.splitext(file)
                date = parse_date(
                    date_str,
                    tzinfo=timezone.utc,
                    format_str=DATE_FORMAT_DASH,
                )
                if date is None:
                    continue

                in_path = os.path.abspath(os.path.join(root, file))
                dst_path = date.strftime(dst)

                if not overwrite and os.path.exists(dst_path):
                    LOGGER.debug(
                        "Output file <%s> already exists, skipping <%s>...",
                        dst_path,
                        in_path,
                    )
                    continue

                LOGGER.info(
                    "Reading from file <%s> and writing to <%s>...",
                    in_path,
                    dst_path,
                )
                execute("bash", script, in_path, dst_path)


@task()
def fillrankingdb(path=os.path.join(SCRAPED_DATA_DIR, "rankings", "bgg")):
    """Parses the ranking CSVs and writes them to the database."""
    django.core.management.call_command("fillrankingdb", path)


@task()
def deduplicate(rankings_path=os.path.join(SCRAPED_DATA_DIR, "rankings")):
    """Deduplicate rankings files."""
    rankings_path = Path(rankings_path).resolve()
    LOGGER.info("Finding sub dirs in <%s>", rankings_path)
    sub_dirs = (d for d in rankings_path.iterdir() if d.is_dir())
    paths = (d2 for d1 in sub_dirs for d2 in d1.iterdir() if d2.is_dir())
    django.core.management.call_command("deduplicate", *paths)


@task()
def updatecount(
    dst=os.path.join(SCRAPED_DATA_DIR, "COUNT.md"),
    template=os.path.join(BASE_DIR, "templates", "COUNT.md"),
    paths_lines=os.path.join(SCRAPED_DATA_DIR, "scraped"),
    line_glob="*.jl",
    paths_files=os.path.join(SCRAPED_DATA_DIR, "rankings"),
    file_glob="*.csv",
):
    """Update the line and file counts in the destination file."""

    from games.utils import count_lines_and_files

    counts = count_lines_and_files(
        paths_lines=paths_lines,
        line_glob=line_glob,
        paths_files=paths_files,
        file_glob=file_glob,
    )

    now = django.utils.timezone.now()
    counts["date"] = now.date().isoformat()
    counts["date_iso"] = now.isoformat(timespec="seconds")

    template = Path(template).resolve()
    dst = Path(dst).resolve()
    dst.parent.mkdir(parents=True, exist_ok=True)
    LOGGER.info("Reading template from <%s>, writing result to <%s>...", template, dst)

    with template.open(encoding="utf-8") as template_file, dst.open(
        "w", encoding="utf-8"
    ) as dst_file:
        template_str = template_file.read()
        count_str = template_str.format(**counts)
        dst_file.write(count_str)


@task()
def makecsvs(
    in_dir=os.path.join(SCRAPED_DATA_DIR, "scraped"),
    glob="*_GameItem.jl",
    file_ext=".csv",
    columns=GAMES_CSV_COLUMNS,
    joiner=",",
    exclude=(
        "bgg_hotness_GameItem.jl",
        "bgg_rankings_GameItem.jl",
        "bgg_rankings_abstract_GameItem.jl",
        "bgg_rankings_children_GameItem.jl",
        "bgg_rankings_customizable_GameItem.jl",
        "bgg_rankings_family_GameItem.jl",
        "bgg_rankings_party_GameItem.jl",
        "bgg_rankings_strategy_GameItem.jl",
        "bgg_rankings_thematic_GameItem.jl",
        "bgg_rankings_war_GameItem.jl",
    ),
):
    """Create CSV versions of JSON lines files in in_dir."""

    from games.utils import jl_to_csv

    in_dir = Path(in_dir)
    exclude = frozenset(arg_to_iter(exclude))
    LOGGER.info("Processing JSON lines files in <%s>, excluding %s...", in_dir, exclude)

    for in_path in in_dir.rglob(glob):
        if os.path.basename(in_path) in exclude:
            LOGGER.info("Skipping <%s>...", in_path)
        else:
            out_path = os.path.splitext(in_path)[0] + file_ext
            jl_to_csv(
                in_path=in_path,
                out_path=out_path,
                columns=columns,
                joiner=joiner,
            )


@task()
def referencecsvs(
    in_file=os.path.join(SCRAPED_DATA_DIR, "scraped", "bgg_GameItem.jl"),
    out_dir=os.path.join(SCRAPED_DATA_DIR, "scraped"),
    out_file="bgg_{entity}.csv",
):
    """Parse a file for foreign references and store those in separate CSVs."""
    LOGGER.info("Parsing <%s> for foreign references", in_file)
    django.core.management.call_command(
        "referencecsvs",
        in_file,
        out_dir=out_dir,
        out_file=out_file,
    )


@task()
def sitemap(url=URL_LIVE, dst=os.path.join(DATA_DIR, "sitemap.xml"), limit=50_000):
    """Generate sitemap.xml."""
    limit = parse_int(limit) or 50_000
    LOGGER.info(
        "Generating sitemap with URL <%s> to <%s>, limit to %d...",
        url,
        dst,
        limit,
    )
    django.core.management.call_command("sitemap", url=url, limit=limit, output=dst)


@task(
    cleandata,
    filldb,
    dateflag,
    kennerspiel,
    splitall,
    historicalbggrankings,
    weeklycharts,
    fillrankingdb,
    compressdb,
    cpdirs,
    cpdirsbga,
    sitemap,
)
def builddb():
    """build a new database"""


@task(
    gitprepare,
    mergeall,
    makecsvs,
    referencecsvs,
    link,
    train,
    saverankings,
    builddb,
    deduplicate,
    updatecount,
    gitupdate,
)
def builddbfull():
    """merge, link, train, and build, all relevant files"""


def _sync_data(src, dst, retries=0):
    LOGGER.info("Syncing <%s> with <%s>...", src, dst)
    try:
        execute(
            "gsutil",
            "-m",
            "-o",
            "GSUtil:parallel_process_count=1",
            "rsync",
            "-d",
            "-r",
            src,
            dst,
        )

    except SystemExit:
        LOGGER.exception("An error occurred when syncing <%s> with <%s>", src, dst)

        if retries <= 0:
            raise

        LOGGER.info("%d retries left...", retries)
        _sync_data(src, dst, retries - 1)


@task()
def syncdata(src=os.path.join(DATA_DIR, ""), bucket=GC_DATA_BUCKET, retries=3):
    """sync data with GCS"""
    _sync_data(src=src, dst=f"gs://{bucket}/", retries=parse_int(retries))


@task(builddb, syncdata)
def releasedb():
    """build and release database"""


@task(builddbfull, syncdata)
def releasedbfull():
    """merge, link, train, build, and release database"""


@task()
def cleanstatic(base_dir=BASE_DIR, sub_dirs=None):
    """clean static files"""
    sub_dirs = sub_dirs or (".temp", "static")
    for sub_dir in sub_dirs:
        target = os.path.join(base_dir, sub_dir)
        LOGGER.info("Removing dir <%s>...", target)
        shutil.rmtree(target, ignore_errors=True)


@task()
def minify(src=os.path.join(BASE_DIR, "app"), dst=os.path.join(BASE_DIR, ".temp")):
    """copy front-end files and minify HTML, JavaScript, and CSS"""
    LOGGER.info("Copying and minifying files from <%s> to <%s>...", src, dst)
    django.core.management.call_command(
        "minify",
        src,
        dst,
        delete=True,
        exclude_dot=True,
    )


@task(cleanstatic, minify)
def collectstatic(delete=True):
    """Collect static files."""

    assert not SETTINGS.DEBUG

    static_dirs = SETTINGS.STATICFILES_DIRS
    LOGGER.info("Collecting static files from %s...", static_dirs)
    django.core.management.call_command("collectstatic", no_input=True)

    if not parse_bool(delete):
        return

    for static_dir in static_dirs:
        LOGGER.info("Removing static dir <%s>...", static_dir)
        shutil.rmtree(static_dir, ignore_errors=True)


@task(collectstatic)
def buildserver(images=None, tags=None):
    """build Docker image"""

    images = images or ("rg-server", f"gcr.io/{GC_PROJECT}/rg-server")
    version = _server_version()
    tags = tags or ("latest", version)
    all_tags = [f"{i}:{t}" for i in images if i for t in tags if t]

    LOGGER.info("Building Docker image with tags %s...", all_tags)

    command = ["docker", "build"]
    for tag in all_tags:
        command.extend(("--tag", tag))
    command.append(".")

    with safe_cd(BASE_DIR):
        execute(*command)

        if not version:
            return

        LOGGER.info("Adding Git tag <v%s> if it doesn't exist", version)
        try:
            execute("git", "tag", f"v{version}")
        except SystemExit:
            pass  # tag already exists


@task()
def pushserver(image=None, version=None):
    """push Docker image to remote repo"""
    image = image or f"gcr.io/{GC_PROJECT}/rg-server"
    version = version or _server_version()
    LOGGER.info("Pushing Docker image <%s:%s> to repo...", image, version)
    execute("docker", "push", f"{image}:{version}")


@task(buildserver, pushserver)
def releaseserver(
    app_file=os.path.join(BASE_DIR, "app.yaml"),
    image=None,
    version=None,
):
    """build, push, and deploy new server version"""
    image = image or f"gcr.io/{GC_PROJECT}/rg-server"
    version = version or _server_version()
    date = django.utils.timezone.now().strftime(DATE_FORMAT_COMPACT)
    LOGGER.info("Deploying server v%s-%s from file <%s>...", version, date, app_file)
    execute(
        "gcloud",
        "app",
        "deploy",
        app_file,
        "--project",
        GC_PROJECT,
        "--image-url",
        f"{image}:{version}",
        "--version",
        f"{version}-{date}",
        "--promote",
        "--quiet",
    )


@task(builddb, buildserver)
def build():
    """build database and server"""


@task(builddbfull, buildserver)
def buildfull():
    """merge, link, train, and build database and server"""


@task(releasedb, releaseserver)
def release():
    """release database and server"""


@task(releasedbfull, releaseserver)
def releasefull():
    """merge, link, train, build, and release database and server"""


@task()
def lintshell(base_dir=BASE_DIR):
    """lint Shell scripts"""
    execute("find", base_dir, "-name", "*.sh", "-ls", "-exec", "shellcheck", "{}", ";")


@task()
def lintdocker(base_dir=BASE_DIR):
    """Lint Dockerfiles."""
    execute(
        "find",
        base_dir,
        "-name",
        "Dockerfile*",
        "-ls",
        "-exec",
        "hadolint",
        "{}",
        ";",
    )


@task()
def lintpy(*modules):
    """lint Python files"""
    modules = modules or ("games", "rg", "build.py", "manage.py")
    with safe_cd(BASE_DIR):
        execute("black", "--diff", "--exclude", "/migrations/", *modules)
        execute("pylint", "--exit-zero", *modules)


@task()
def linthtml():
    """lint HTML files"""
    with safe_cd(os.path.join(BASE_DIR, "app")):
        execute("htmlhint", "--ignore", "google*.html,yandex*.html")
        # execute('htmllint')


@task()
def lintjs():
    """lint JavaScript files"""
    with safe_cd(os.path.join(BASE_DIR, "app")):
        execute("jslint", "js/*.js")
        execute("jshint", "js")


@task()
def lintcss():
    """lint JavaScript files"""
    with safe_cd(os.path.join(BASE_DIR, "app")):
        execute("csslint", "app.css")


@task(lintshell, lintdocker, lintpy, linthtml, lintjs, lintcss)
def lint():
    """lint everything"""


__DEFAULT__ = lint
