# -*- coding: utf-8 -*-

"""Extract ratings from Git repositories and train recommenders."""

import logging
import shutil
import sys

from datetime import timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management.base import BaseCommand
from git import Repo
from ludoj_recommender import BGGRecommender

from ...utils import save_recommender_ranking

LOGGER = logging.getLogger(__name__)
DATE_TEMPLATE = "%Y%m%d-%H%M%S"
OVERWRITE = False


def _cp_files(dst, tree, game_file="bgg_GameItem.jl", rating_dir="bgg_RatingItem"):
    dst = Path(dst)
    dst.mkdir(parents=True, exist_ok=True)

    LOGGER.info("Copying files from <%s> to <%s>", tree, dst)

    games_blob = tree / game_file
    games_dst = dst / game_file

    with games_dst.open("wb") as games_fp:
        shutil.copyfileobj(games_blob.data_stream, games_fp)

    try:
        ratings_blob = tree / f"{rating_dir}.jl"
    except Exception:
        pass
    else:
        ratings_dst = dst / f"{rating_dir}.jl"
        with ratings_dst.open("wb") as ratings_fp:
            shutil.copyfileobj(ratings_blob.data_stream, ratings_fp)
        return games_dst, ratings_dst

    ratings_tree = tree / rating_dir
    ratings_dir = dst / rating_dir
    ratings_dir.mkdir(parents=True, exist_ok=True)

    for ratings_blob in ratings_tree.blobs:
        ratings_dst = ratings_dir / ratings_blob.name
        with ratings_dst.open("wb") as ratings_fp:
            shutil.copyfileobj(ratings_blob.data_stream, ratings_fp)

    return games_dst, ratings_dir


def _exists(dst, overwrite=False):
    dst = Path(dst)

    if not dst.exists():
        return False

    if overwrite:
        LOGGER.info("File <%s> already exists, removing...", dst)
        dst.unlink()
        return False

    return True


def _process_commit(
    commit,
    recommender_dir,
    ranking_fac_dir,
    ranking_sim_dir,
    date_str=DATE_TEMPLATE,
    overwrite=False,
):
    date = commit.authored_datetime.astimezone(timezone.utc)

    LOGGER.info("Processing commit <%s> from %s", commit, date)

    recommender_dir = Path(recommender_dir)
    ranking_fac_dir = Path(ranking_fac_dir)
    ranking_sim_dir = Path(ranking_sim_dir)

    ranking_file = date.strftime(f"{date_str}.csv")
    ranking_fac_dst = ranking_fac_dir / ranking_file
    ranking_sim_dst = ranking_sim_dir / ranking_file

    if _exists(ranking_fac_dst, overwrite) or _exists(ranking_sim_dst, overwrite):
        LOGGER.info(
            "File <%s> or <%s> already exist, skipping <%s>...",
            ranking_fac_dst,
            ranking_sim_dst,
            commit,
        )
        return

    recommender_dst = recommender_dir / date.strftime(date_str)
    shutil.rmtree(recommender_dst, ignore_errors=True)
    recommender_dst.mkdir(parents=True, exist_ok=True)

    LOGGER.info(
        "Will save recommender to <%s> and rankings to <%s> and <%s>...",
        recommender_dst,
        ranking_fac_dst,
        ranking_sim_dst,
    )

    tree = commit.tree / "scraped"

    with TemporaryDirectory() as dst:
        games_file, ratings_file = _cp_files(dst, tree)

        LOGGER.info(
            "Loading games from <%s> and ratings from <%s>...", games_file, ratings_file
        )

        recommender = BGGRecommender.train_from_files(
            games_file=str(games_file),
            ratings_file=str(ratings_file),
            similarity_model=True,
            max_iterations=100,
            verbose=True,
        )
        recommender.save(recommender_dst)

    LOGGER.info(
        "Saving rankings from <%s> to <%s> and <%s>...",
        recommender,
        ranking_fac_dst,
        ranking_sim_dst,
    )
    save_recommender_ranking(
        recommender=recommender, dst=ranking_fac_dst, similarity_model=False
    )
    save_recommender_ranking(
        recommender=recommender, dst=ranking_sim_dst, similarity_model=True
    )
    LOGGER.info("Done processing commit <%s>...", commit)


def _process_repo(repo):
    if isinstance(repo, str):
        repo = Repo(repo)

    LOGGER.info("Processing repository %s...", repo)

    recommender_dir = Path.home() / "recommenders-hist"
    ranking_dir = recommender_dir / "rankings"

    ranking_fac_dir = ranking_dir / "factor"
    ranking_fac_dir.mkdir(parents=True, exist_ok=True)

    ranking_sim_dir = ranking_dir / "similarity"
    ranking_sim_dir.mkdir(parents=True, exist_ok=True)

    for commit in repo.iter_commits(paths="scraped"):
        try:
            _process_commit(
                commit=commit,
                recommender_dir=recommender_dir,
                ranking_fac_dir=ranking_fac_dir,
                ranking_sim_dir=ranking_sim_dir,
                date_str=DATE_TEMPLATE,
                overwrite=OVERWRITE,
            )
        except Exception:
            LOGGER.exception("There was an error processing commit <%s>...", commit)


class Command(BaseCommand):
    """Extract ratings from Git repositories and train recommenders."""

    help = "Extract ratings from Git repositories and train recommenders."

    def add_arguments(self, parser):
        parser.add_argument("repos", nargs="+")

    def handle(self, *args, **kwargs):
        logging.basicConfig(
            stream=sys.stderr,
            level=logging.DEBUG if kwargs["verbosity"] > 1 else logging.INFO,
            format="%(asctime)s %(levelname)-8.8s [%(name)s:%(lineno)s] %(message)s",
        )

        LOGGER.info(kwargs)

        for repo in kwargs["repos"]:
            _process_repo(repo)

        LOGGER.info("Done.")
