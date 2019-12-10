#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" pynt build file """

import logging
import os
import shutil
import sys

from datetime import timedelta, timezone
from functools import lru_cache

import django

from dotenv import load_dotenv
from pynt import task
from pyntcontrib import execute, safe_cd
from pytility import parse_bool, parse_date, parse_float, parse_int, to_str

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv(verbose=True)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ludoj.settings")
os.environ.setdefault("PYTHONPATH", BASE_DIR)
os.environ["DEBUG"] = ""
sys.path.insert(0, BASE_DIR)
django.setup()

LOGGER = logging.getLogger(__name__)
SETTINGS = django.conf.settings
DATA_DIR = SETTINGS.DATA_DIR
SCRAPER_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "ludoj-scraper"))
RECOMMENDER_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "ludoj-recommender"))
SCRAPED_DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "ludoj-data"))
URL_LIVE = "https://recommend.games/"
GC_PROJECT = os.getenv("GC_PROJECT") or "recommend-ludoj"
GC_DATA_BUCKET = os.getenv("GC_DATA_BUCKET") or f"{GC_PROJECT}-data"

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8.8s [%(name)s:%(lineno)s] %(message)s",
)

LOGGER.info("currently in Google Cloud project <%s>", GC_PROJECT)


@lru_cache(maxsize=8)
def _server_version(path=os.path.join(BASE_DIR, "VERSION")):
    with open(path) as file:
        version = file.read()
    return version.strip()


def _remove(path):
    LOGGER.info("Removing <%s> if it exists...", path)
    try:
        os.remove(path)
    except OSError:
        shutil.rmtree(path, ignore_errors=True)


@task()
def rsync(
    host="ludoj-hq",
    port=2222,
    src=os.path.join(SCRAPER_DIR, "feeds", ""),
    dst=os.path.join(SCRAPER_DIR, "feeds", ""),
):
    """ sync remote files """
    port = parse_int(port)
    LOGGER.info("Syncing with <%s:%d> from <%s> to <%s>...", host, port, src, dst)
    os.makedirs(dst, exist_ok=True)
    execute(
        "rsync",
        "--archive",
        "--verbose",
        "--human-readable",
        "--progress",
        "--rsh",
        f"ssh -p {port}",
        f"{host}:{src}",
        dst,
    )


@task()
def gitprepare(repo=SCRAPED_DATA_DIR):
    """ check Git repo is clean and up-to-date """
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
    """ commit and push Git repo """
    paths = paths or ("rankings", "scraped", "links.json", "prefixes.txt")
    LOGGER.info("Updating paths %r in Git repo <%s>...", paths, repo)
    with safe_cd(repo):
        try:
            execute("git", "gc", "--prune=now")
            execute("git", "add", "--", *paths)
        except SystemExit:
            LOGGER.exception("There was a problem in repo <%s>...", repo)

        try:
            execute("git", "commit", "--message", f"automatic commit by <{name}>")
            execute("git", "gc", "--prune=now")
        except SystemExit:
            LOGGER.info("Nothing to commit...")

        try:
            execute("git", "push")
        except SystemExit:
            LOGGER.exception("Unable to push...")


@task()
def merge(in_paths, out_path, **kwargs):
    """ merge scraped files """
    from board_game_scraper.merge import merge_files

    kwargs.setdefault("log_level", "WARN")
    out_path = out_path.format(
        date=django.utils.timezone.now().strftime("%Y-%m-%dT%H-%M-%S")
    )

    LOGGER.info(
        "Merging files <%s> into <%s> with args %r...", in_paths, out_path, kwargs
    )

    _remove(out_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    merge_files(in_paths=in_paths, out_path=out_path, **kwargs)


def _merge_kwargs(
    site, item="GameItem", in_paths=None, out_path=None, full=False, **kwargs
):
    kwargs["in_paths"] = in_paths or os.path.join(SCRAPER_DIR, "feeds", site, item, "*")
    kwargs.setdefault("keys", (f"{site}_id",))
    kwargs.setdefault(
        "key_parsers", (parse_int,) if site in ("bgg", "luding") else (to_str,)
    )
    kwargs.setdefault("latest", ("scraped_at",))
    kwargs.setdefault("latest_parsers", (parse_date,))
    kwargs.setdefault("latest_min", django.utils.timezone.now() - timedelta(days=30))
    kwargs.setdefault("concat_output", True)

    if parse_bool(full):
        kwargs["out_path"] = out_path or os.path.join(
            SCRAPER_DIR, "feeds", site, item, "{date}_merged.jl"
        )

    else:
        kwargs["out_path"] = out_path or os.path.join(
            SCRAPED_DATA_DIR, "scraped", f"{site}_{item}.jl"
        )
        kwargs.setdefault(
            "fieldnames_exclude",
            ("image_file", "rules_file", "published_at", "updated_at", "scraped_at"),
        )
        kwargs.setdefault("sort_output", True)

    return kwargs


@task()
def mergebga(in_paths=None, out_path=None, full=False):
    """ merge Board Game Atlas game data """
    merge(**_merge_kwargs(site="bga", in_paths=in_paths, out_path=out_path, full=full))


@task()
def mergebgaratings(in_paths=None, out_path=None, full=False):
    """ merge Board Game Atlas rating data """
    merge(
        **_merge_kwargs(
            site="bga",
            item="RatingItem",
            in_paths=in_paths,
            out_path=out_path,
            full=full,
            keys=("bga_user_id", "bga_id"),
            fieldnames_exclude=("bgg_user_play_count",)
            if parse_bool(full)
            else ("bgg_user_play_count", "published_at", "updated_at", "scraped_at"),
        )
    )


@task()
def mergebgg(in_paths=None, out_path=None, full=False):
    """ merge BoardGameGeek game data """
    merge(**_merge_kwargs(site="bgg", in_paths=in_paths, out_path=out_path, full=full))


@task()
def mergebggusers(in_paths=None, out_path=None, full=False):
    """ merge BoardGameGeek user data """
    from board_game_scraper.utils import to_lower

    merge(
        **_merge_kwargs(
            site="bgg",
            item="UserItem",
            in_paths=in_paths,
            out_path=out_path,
            full=full,
            keys=("bgg_user_name",),
            key_parsers=(to_lower,),
            fieldnames_exclude=None
            if parse_bool(full)
            else ("published_at", "scraped_at"),
        )
    )


@task()
def mergebggratings(in_paths=None, out_path=None, full=False):
    """ merge BoardGameGeek rating data """
    from board_game_scraper.utils import to_lower

    merge(
        **_merge_kwargs(
            site="bgg",
            item="RatingItem",
            in_paths=in_paths,
            out_path=out_path,
            full=full,
            keys=("bgg_user_name", "bgg_id"),
            key_parsers=(to_lower, parse_int),
        )
    )


@task()
def mergebggrankings(in_paths=None, out_path=None, full=False):
    """ merge BoardGameGeek ranking data """
    merge(
        **_merge_kwargs(
            site="bgg_rankings",
            item="GameItem",
            in_paths=in_paths,
            out_path=out_path,
            full=full,
            keys=("published_at", "bgg_id"),
            key_parsers=(parse_date, parse_int),
            latest_min=None,
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
                "image_url",
            ),
            fieldnames_exclude=None,
        )
    )


@task()
def mergedbpedia(in_paths=None, out_path=None, full=False):
    """ merge DBpedia game data """
    merge(
        **_merge_kwargs(site="dbpedia", in_paths=in_paths, out_path=out_path, full=full)
    )


@task()
def mergeluding(in_paths=None, out_path=None, full=False):
    """ merge Luding.org game data """
    merge(
        **_merge_kwargs(site="luding", in_paths=in_paths, out_path=out_path, full=full)
    )


@task()
def mergespielen(in_paths=None, out_path=None, full=False):
    """ merge Spielen.de game data """
    merge(
        **_merge_kwargs(site="spielen", in_paths=in_paths, out_path=out_path, full=full)
    )


@task()
def mergewikidata(in_paths=None, out_path=None, full=False):
    """ merge Wikidata game data """
    merge(
        **_merge_kwargs(
            site="wikidata", in_paths=in_paths, out_path=out_path, full=full
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
    """ merge news articles """
    merge(
        **_merge_kwargs(
            site="news",
            item="ArticleItem",
            in_paths=in_paths,
            out_path=out_path,
            keys=("article_id",),
            latest=("published_at", "scraped_at"),
            latest_parsers=(parse_date, parse_date),
            latest_min=None,
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
            sort_output=False,
            sort_latest="desc",
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
)
def mergeall():
    """ merge all sites and items """


@task()
def split(
    in_file=os.path.join(SCRAPED_DATA_DIR, "scraped", "bgg_RatingItem.jl"),
    out_dir=os.path.join(SCRAPED_DATA_DIR, "scraped", "bgg_RatingItem"),
    trie_file=os.path.join(SCRAPED_DATA_DIR, "prefixes.txt"),
    fields="bgg_user_name",
    limit=300_000,
    construct=False,
):
    """ split file along prefixes """
    from board_game_scraper.prefixes import split_file

    _remove(out_dir)
    split_file(
        in_file=in_file,
        out_file=os.path.join(out_dir, "{prefix}.jl"),
        fields=fields,
        trie_file=trie_file,
        limits=(limit,),
        construct=construct,
    )
    _remove(in_file)


@task()
def link(
    gazetteer=os.path.join(BASE_DIR, "cluster", "gazetteer.pickle"),
    paths=(
        os.path.join(SCRAPED_DATA_DIR, "scraped", "bgg_GameItem.jl"),
        os.path.join(SCRAPED_DATA_DIR, "scraped", "bga_GameItem.jl"),
        os.path.join(SCRAPED_DATA_DIR, "scraped", "spielen_GameItem.jl"),
        os.path.join(SCRAPED_DATA_DIR, "scraped", "luding_GameItem.jl"),
        os.path.join(SCRAPED_DATA_DIR, "scraped", "wikidata_GameItem.jl"),
    ),
    id_prefixes=("bgg", "bga", "spielen", "luding", "wikidata"),
    training_file=os.path.join(BASE_DIR, "cluster", "training.json"),
    manual_labelling=False,
    threshold=None,
    recall_weight=0.5,
    output=os.path.join(SCRAPED_DATA_DIR, "links.json"),
    pretty_print=True,
):
    """ link items """
    from board_game_scraper.cluster import link_games

    LOGGER.info("Using model %r to link files %r...", gazetteer, paths)
    link_games(
        gazetteer=gazetteer,
        paths=paths,
        id_prefixes=id_prefixes,
        training_file=training_file if manual_labelling else None,
        manual_labelling=manual_labelling,
        threshold=parse_float(threshold),
        recall_weight=parse_float(recall_weight),
        output=output,
        pretty_print=pretty_print,
    )


@task()
def labellinks(
    gazetteer=os.path.join(BASE_DIR, "cluster", "gazetteer.pickle"),
    paths=(
        os.path.join(SCRAPED_DATA_DIR, "scraped", "bgg_GameItem.jl"),
        os.path.join(SCRAPED_DATA_DIR, "scraped", "bga_GameItem.jl"),
        os.path.join(SCRAPED_DATA_DIR, "scraped", "spielen_GameItem.jl"),
        os.path.join(SCRAPED_DATA_DIR, "scraped", "luding_GameItem.jl"),
        os.path.join(SCRAPED_DATA_DIR, "scraped", "wikidata_GameItem.jl"),
    ),
    id_prefixes=("bgg", "bga", "spielen", "luding", "wikidata"),
    training_file=os.path.join(BASE_DIR, "cluster", "training.json"),
    threshold=None,
    recall_weight=0.5,
    output=os.path.join(SCRAPED_DATA_DIR, "links.json"),
    pretty_print=True,
):
    """ label new training examples and link items """
    link(
        gazetteer=gazetteer,
        paths=paths,
        id_prefixes=id_prefixes,
        training_file=training_file,
        manual_labelling=True,
        threshold=threshold,
        recall_weight=recall_weight,
        output=output,
        pretty_print=pretty_print,
    )


def _train(
    recommender_cls,
    games_file,
    ratings_file,
    out_path=None,
    users=None,
    max_iterations=100,
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
        max_iterations=max_iterations,
        verbose=True,
    )

    recommendations = recommender.recommend(users=users, num_games=100)
    recommendations.print_rows(num_rows=100)

    if out_path:
        LOGGER.info("Saving model %r to <%s>...", recommender, out_path)
        shutil.rmtree(out_path, ignore_errors=True)
        recommender.save(out_path)


@task()
def trainbgg(
    games_file=os.path.join(SCRAPED_DATA_DIR, "scraped", "bgg_GameItem.jl"),
    ratings_file=os.path.join(SCRAPED_DATA_DIR, "scraped", "bgg_RatingItem.jl"),
    out_path=os.path.join(RECOMMENDER_DIR, ".bgg"),
    users=None,
    max_iterations=1000,
):
    """ train BoardGameGeek recommender model """
    from board_game_recommender import BGGRecommender

    _train(
        recommender_cls=BGGRecommender,
        games_file=games_file,
        ratings_file=ratings_file,
        out_path=out_path,
        users=users,
        max_iterations=max_iterations,
    )


@task()
def trainbga(
    games_file=os.path.join(SCRAPED_DATA_DIR, "scraped", "bga_GameItem.jl"),
    ratings_file=os.path.join(SCRAPED_DATA_DIR, "scraped", "bga_RatingItem.jl"),
    out_path=os.path.join(RECOMMENDER_DIR, ".bga"),
    users=None,
    max_iterations=1000,
):
    """ train Board Game Atlas recommender model """
    from board_game_recommender import BGARecommender

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
    """ train BoardGameGeek and Board Game Atlas recommender models """


def _save_ranking(
    recommender, dst_dir, file_name="%Y%m%d-%H%M%S.csv", similarity_model=False
):
    from games.utils import save_recommender_ranking

    file_name = django.utils.timezone.now().strftime(file_name)
    dst_path = os.path.join(dst_dir, file_name)

    _remove(dst_path)
    os.makedirs(dst_dir, exist_ok=True)

    save_recommender_ranking(recommender, dst_path, similarity_model)


@task()
def savebggrankings(
    recommender_path=os.path.join(RECOMMENDER_DIR, ".bgg"),
    dst_dir=os.path.join(SCRAPED_DATA_DIR, "rankings", "bgg"),
    file_name="%Y%m%d-%H%M%S.csv",
):
    """Take a snapshot of the BoardGameGeek rankings."""
    from games.utils import load_recommender

    LOGGER.info("Loading BoardGameGeek recommender from <%s>...", recommender_path)
    recommender = load_recommender(recommender_path, site="bgg")
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


@task()
def savebgarankings(
    recommender_path=os.path.join(RECOMMENDER_DIR, ".bga"),
    dst_dir=os.path.join(SCRAPED_DATA_DIR, "rankings", "bga"),
    file_name="%Y%m%d-%H%M%S.csv",
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
def cleandata(src_dir=DATA_DIR, bk_dir=f"{DATA_DIR}.bk"):
    """ clean data file """
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
    """ database migration """
    assert not SETTINGS.DEBUG
    django.core.management.call_command("migrate")


@task(cleandata, migrate)
def filldb(src_dir=SCRAPED_DATA_DIR, rec_dir=os.path.join(RECOMMENDER_DIR, ".bgg")):
    """ fill database """
    LOGGER.info(
        "Uploading games and other data from <%s>, and recommendations from <%s> to database...",
        src_dir,
        rec_dir,
    )
    srp_dir = os.path.join(src_dir, "scraped")
    django.core.management.call_command(
        "filldb",
        os.path.join(srp_dir, "bgg_GameItem.jl"),
        collection_paths=[os.path.join(srp_dir, "bgg_RatingItem.jl")],
        user_paths=[os.path.join(srp_dir, "bgg_UserItem.jl")],
        in_format="jl",
        batch=100000,
        recommender=rec_dir,
        links=os.path.join(src_dir, "links.json"),
    )


@task()
def compressdb(db_file=os.path.join(DATA_DIR, "db.sqlite3")):
    """ compress SQLite database file """
    execute("sqlite3", db_file, "VACUUM;")


@task()
def cpdirs(
    src_dir=os.path.join(RECOMMENDER_DIR, ".bgg"),
    dst_dir=os.path.join(DATA_DIR, "recommender_bgg"),
    sub_dirs=("recommender", "similarity", "clusters", "compilations"),
):
    """ copy recommender files """
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
    """ copy BGA recommender files """
    cpdirs(src_dir, dst_dir, sub_dirs)


@task()
def dateflag(dst=SETTINGS.MODEL_UPDATED_FILE, date=None):
    """ write date to file """
    from games.utils import serialize_date

    date = parse_date(date) or django.utils.timezone.now()
    date_str = serialize_date(date, tzinfo=django.utils.timezone.utc)
    LOGGER.info("Writing date <%s> to <%s>...", date_str, dst)
    with open(dst, "w") as file:
        file.write(date_str)


@task()
def bggranking(
    dst=os.path.join(SCRAPED_DATA_DIR, "rankings", "bgg", "bgg", "%Y%m%d-%H%M%S.csv")
):
    """Saves a snapshot of the BGG rankings."""
    from games.utils import model_updated_at

    updated_at = model_updated_at() or django.utils.timezone.now()
    dst = updated_at.strftime(dst)
    django.core.management.call_command("bggranking", output=dst)


@task()
def historicalbggrankings(
    repo=os.path.abspath(os.path.join(BASE_DIR, "..", "bgg-ranking-historicals")),
    dst=os.path.join(SCRAPED_DATA_DIR, "rankings", "bgg", "bgg", "%Y%m%d-%H%M%S.csv"),
    script=os.path.join(BASE_DIR, "scripts", "ranking.sh"),
    overwrite=False,
):
    """Save historical BGG rankings."""

    from games.utils import format_from_path

    LOGGER.info("Loading historical BGG rankings from <%s>...", repo)

    overwrite = parse_bool(overwrite)

    with safe_cd(repo):
        execute("git", "checkout", "master")
        execute("git", "pull", "--ff-only")

        for root, _, files in os.walk("."):
            for file in files:
                if format_from_path(file) != "csv":
                    continue

                date_str, _ = os.path.splitext(file)
                date = parse_date(date_str, tzinfo=timezone.utc)
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
                    "Reading from file <%s> and writing to <%s>...", in_path, dst_path
                )
                execute("bash", script, in_path, dst_path)


@task()
def fillrankingdb(path=os.path.join(SCRAPED_DATA_DIR, "rankings", "bgg")):
    """Parses the ranking CSVs and writes them to the database."""
    django.core.management.call_command("fillrankingdb", path)


@task()
def sitemap(url=URL_LIVE, dst=os.path.join(DATA_DIR, "sitemap.xml"), limit=50_000):
    """Generate sitemap.xml."""
    limit = parse_int(limit) or 50_000
    LOGGER.info(
        "Generating sitemap with URL <%s> to <%s>, limit to %d...", url, dst, limit
    )
    django.core.management.call_command("sitemap", url=url, limit=limit, output=dst)


@task(
    cleandata,
    filldb,
    dateflag,
    historicalbggrankings,
    fillrankingdb,
    compressdb,
    cpdirs,
    cpdirsbga,
    sitemap,
)
def builddb():
    """ build a new database """


@task(gitprepare, mergeall, train, saverankings, builddb, gitupdate)  # link
def builddbfull():
    """ merge, link, train, and build, all relevant files """


@task()
def syncdata(src=os.path.join(DATA_DIR, ""), bucket=GC_DATA_BUCKET):
    """ sync data with GCS """
    LOGGER.info("Syncing <%s> with GCS bucket <%s>...", src, bucket)
    os.environ["CLOUDSDK_PYTHON"] = ""
    execute(
        "gsutil",
        "-m",
        "-o",
        "GSUtil:parallel_composite_upload_threshold=100M",
        "rsync",
        "-d",
        "-r",
        src,
        f"gs://{bucket}/",
    )


@task(builddb, syncdata)
def releasedb():
    """ build and release database """


@task(builddbfull, syncdata)
def releasedbfull():
    """ merge, link, train, build, and release database """


@task()
def cleanstatic(base_dir=BASE_DIR, sub_dirs=None):
    """ clean static files """
    sub_dirs = sub_dirs or (".temp", "static")
    for sub_dir in sub_dirs:
        target = os.path.join(base_dir, sub_dir)
        LOGGER.info("Removing dir <%s>...", target)
        shutil.rmtree(target, ignore_errors=True)


@task()
def minify(src=os.path.join(BASE_DIR, "app"), dst=os.path.join(BASE_DIR, ".temp")):
    """ copy front-end files and minify HTML, JavaScript, and CSS """
    LOGGER.info("Copying and minifying files from <%s> to <%s>...", src, dst)
    django.core.management.call_command(
        "minify", src, dst, delete=True, exclude_dot=True
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
    """ build Docker image """

    images = images or ("ludoj-server", f"gcr.io/{GC_PROJECT}/ludoj-server")
    tags = tags or ("latest", _server_version())
    all_tags = [f"{i}:{t}" for i in images if i for t in tags if t]

    LOGGER.info("Building Docker image with tags %s...", all_tags)

    command = ["docker", "build"]
    for tag in all_tags:
        command.extend(("--tag", tag))
    command.append(".")

    with safe_cd(BASE_DIR):
        execute(*command)


@task()
def pushserver(image=None, version=None):
    """ push Docker image to remote repo """
    image = image or f"gcr.io/{GC_PROJECT}/ludoj-server"
    version = version or _server_version()
    LOGGER.info("Pushing Docker image <%s:%s> to repo...", image, version)
    execute("docker", "push", f"{image}:{version}")


@task(buildserver, pushserver)
def releaseserver(
    app_file=os.path.join(BASE_DIR, "app.yaml"), image=None, version=None
):
    """ build, push, and deploy new server version """
    image = image or f"gcr.io/{GC_PROJECT}/ludoj-server"
    version = version or _server_version()
    date = django.utils.timezone.now().strftime("%Y%m%d%H%M%S")
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
        f"v{version}-{date}",
        "--promote",
        "--quiet",
    )


@task(builddb, buildserver)
def build():
    """ build database and server """


@task(builddbfull, buildserver)
def buildfull():
    """ merge, link, train, and build database and server """


@task(releasedb, releaseserver)
def release():
    """ release database and server """


@task(releasedbfull, releaseserver)
def releasefull():
    """ merge, link, train, build, and release database and server """


@task()
def lintshell(base_dir=BASE_DIR):
    """ lint Shell scripts """
    execute("find", base_dir, "-name", "*.sh", "-ls", "-exec", "shellcheck", "{}", ";")


@task()
def lintdocker(base_dir=BASE_DIR):
    """Lint Dockerfiles."""
    execute(
        "find", base_dir, "-name", "Dockerfile*", "-ls", "-exec", "hadolint", "{}", ";"
    )


@task()
def lintpy(*modules):
    """ lint Python files """
    modules = modules or ("ludoj", "games", "build.py", "manage.py")
    with safe_cd(BASE_DIR):
        execute("black", "--diff", "--exclude", "/migrations/", *modules)
        execute("pylint", "--exit-zero", *modules)


@task()
def linthtml():
    """ lint HTML files """
    with safe_cd(os.path.join(BASE_DIR, "app")):
        execute("htmlhint", "--ignore", "google*.html,yandex*.html")
        # execute('htmllint')


@task()
def lintjs():
    """ lint JavaScript files """
    with safe_cd(os.path.join(BASE_DIR, "app")):
        execute("jslint", "js/*.js")
        execute("jshint", "js")


@task()
def lintcss():
    """ lint JavaScript files """
    with safe_cd(os.path.join(BASE_DIR, "app")):
        execute("csslint", "app.css")


@task(lintshell, lintdocker, lintpy, linthtml, lintjs, lintcss)
def lint():
    """ lint everything """


__DEFAULT__ = lint
