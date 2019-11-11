# -*- coding: utf-8 -*-

"""Extract ratings from Git repositories and train recommenders."""

import logging
import os
import shutil
import sys

from datetime import timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management.base import BaseCommand
from git import Repo
from board_game_recommender import BGARecommender, BGGRecommender
from pytility import arg_to_iter

from ...models import Ranking
from ...utils import save_recommender_ranking

DATE_TEMPLATE = "%Y%m%d-%H%M%S"
LOGGER = logging.getLogger(__name__)


def _exists(dst, overwrite=False):
    if not dst:
        return False

    dst = Path(dst)

    if not dst.exists():
        return False

    if overwrite:
        LOGGER.info("File <%s> already exists, removing...", dst)
        dst.unlink()
        return False

    return True


def _cp_jl_files(dst, tree, game_item, rating_item):
    game_file = f"{game_item}.jl"
    games_blob = tree / game_file
    games_dst = dst / game_file

    with games_dst.open("wb") as games_fp:
        shutil.copyfileobj(games_blob.data_stream, games_fp)

    try:
        ratings_blob = tree / f"{rating_item}.jl"
    except Exception:
        pass
    else:
        ratings_dst = dst / f"{rating_item}.jl"
        with ratings_dst.open("wb") as ratings_fp:
            shutil.copyfileobj(ratings_blob.data_stream, ratings_fp)
        return games_dst, ratings_dst

    ratings_tree = tree / rating_item
    ratings_dir = dst / rating_item
    ratings_dir.mkdir(parents=True, exist_ok=True)

    for ratings_blob in ratings_tree.blobs:
        ratings_dst = ratings_dir / ratings_blob.name
        with ratings_dst.open("wb") as ratings_fp:
            shutil.copyfileobj(ratings_blob.data_stream, ratings_fp)

    return games_dst, ratings_dir


def _cp_any_files(dst, tree, files):
    dst_files = []

    for file in arg_to_iter(files):
        blob = tree / file
        dst_file = dst / file
        with dst_file.open("wb") as dst_fp:
            shutil.copyfileobj(blob.data_stream, dst_fp)
        dst_files.append(dst_file)

    return tuple(dst_files)


def _cp_files(dst, tree, game_item, rating_item, game_csv, rating_csv, dry_run=False):
    dst = Path(dst)

    LOGGER.debug("Copying files from <%s> to <%s>", tree, dst)

    if dry_run:
        return None, None

    dst.mkdir(parents=True, exist_ok=True)

    try:
        return _cp_jl_files(
            dst=dst, tree=tree, game_item=game_item, rating_item=rating_item
        )
    except Exception:
        pass

    return _cp_any_files(dst=dst, tree=tree, files=(game_csv, rating_csv))


def _process_commit(
    commit,
    directory,
    game_item,
    rating_item,
    game_csv,
    rating_csv,
    recommender_cls=BGGRecommender,
    recommender_dir=None,
    ranking_fac_dir=None,
    ranking_sim_dir=None,
    max_iterations=100,
    date_str=DATE_TEMPLATE,
    overwrite=False,
    dry_run=False,
):
    date = commit.authored_datetime.astimezone(timezone.utc)

    LOGGER.info("Processing commit <%s> from %s", commit, date)

    recommender_dir = Path(recommender_dir) if recommender_dir else None
    ranking_fac_dir = Path(ranking_fac_dir) if ranking_fac_dir else None
    ranking_sim_dir = Path(ranking_sim_dir) if ranking_sim_dir else None

    ranking_file = date.strftime(f"{date_str}.csv")
    ranking_fac_dst = ranking_fac_dir / ranking_file if ranking_fac_dir else None
    ranking_sim_dst = ranking_sim_dir / ranking_file if ranking_sim_dir else None

    if _exists(ranking_fac_dst, overwrite) or _exists(ranking_sim_dst, overwrite):
        LOGGER.info(
            "File <%s> or <%s> already exist, skipping <%s>...",
            ranking_fac_dst,
            ranking_sim_dst,
            commit,
        )
        return

    recommender_dst = (
        recommender_dir / date.strftime(date_str) if recommender_dir else None
    )
    if not dry_run and recommender_dst:
        shutil.rmtree(recommender_dst, ignore_errors=True)
        recommender_dst.mkdir(parents=True, exist_ok=True)

    LOGGER.debug(
        "Will save recommender to <%s> and rankings to <%s> and <%s>...",
        recommender_dst,
        ranking_fac_dst,
        ranking_sim_dst,
    )

    tree = commit.tree / directory

    with TemporaryDirectory() as dst:
        games_file, ratings_file = _cp_files(
            dst=dst,
            tree=tree,
            game_item=game_item,
            rating_item=rating_item,
            game_csv=game_csv,
            rating_csv=rating_csv,
            dry_run=dry_run,
        )

        if not games_file or not ratings_file:
            return

        LOGGER.debug(
            "Loading games from <%s> and ratings from <%s>...", games_file, ratings_file
        )

        recommender = recommender_cls.train_from_files(
            games_file=str(games_file),
            ratings_file=str(ratings_file),
            similarity_model=True,
            max_iterations=max_iterations,
            verbose=True,
        )

        if recommender_dst:
            recommender.save(
                path=recommender_dst,
                dir_games=None,
                dir_ratings=None,
                dir_clusters=None,
                dir_compilations=None,
            )

    LOGGER.debug(
        "Saving rankings from <%s> to <%s> and <%s>...",
        recommender,
        ranking_fac_dst,
        ranking_sim_dst,
    )
    if ranking_fac_dst:
        save_recommender_ranking(
            recommender=recommender, dst=ranking_fac_dst, similarity_model=False
        )
    if ranking_sim_dst:
        save_recommender_ranking(
            recommender=recommender, dst=ranking_sim_dst, similarity_model=True
        )
    LOGGER.info("Done processing commit <%s>...", commit)


class Command(BaseCommand):
    """Extract ratings from Git repositories and train recommenders."""

    help = "Extract ratings from Git repositories and train recommenders."

    ranking_types = {Ranking.FACTOR: "factor", Ranking.SIMILARITY: "similarity"}

    def add_arguments(self, parser):
        parser.add_argument("repos", nargs="+")
        parser.add_argument("--site", "-s", default="bgg", choices=("bgg", "bga"))
        parser.add_argument("--dirs", "-d", nargs="+", default=("scraped", "results"))
        parser.add_argument("--out-recommender", "-e")
        parser.add_argument("--out-rankings", "-a")
        parser.add_argument("--max-iterations", "-m", default=100)
        parser.add_argument("--date-str", "-D", default=DATE_TEMPLATE)
        parser.add_argument("--overwrite", "-O", action="store_true")
        parser.add_argument("--dry-run", "-n", action="store_true")

    def _process_repo(
        self,
        repo,
        directories,
        game_item,
        rating_item,
        game_csv,
        rating_csv,
        recommender_cls=BGGRecommender,
        recommender_dir=None,
        ranking_dir=None,
        max_iterations=100,
        date_str=DATE_TEMPLATE,
        overwrite=False,
        dry_run=False,
    ):
        if isinstance(repo, (str, os.PathLike)):
            repo = Repo(repo)

        LOGGER.info("Processing repository %s...", repo)

        recommender_dir = Path(recommender_dir) if recommender_dir else None
        ranking_dir = Path(ranking_dir) if recommender_dir else None

        if ranking_dir:
            ranking_fac_dir = ranking_dir / self.ranking_types[Ranking.FACTOR]
            ranking_sim_dir = ranking_dir / self.ranking_types[Ranking.SIMILARITY]
            if not dry_run:
                ranking_fac_dir.mkdir(parents=True, exist_ok=True)
                ranking_sim_dir.mkdir(parents=True, exist_ok=True)
        else:
            ranking_fac_dir = None
            ranking_sim_dir = None

        for directory in arg_to_iter(directories):
            LOGGER.info("Looking for all versions of <%s>...", directory)
            for commit in repo.iter_commits(paths=directory):
                try:
                    _process_commit(
                        commit=commit,
                        directory=directory,
                        recommender_cls=recommender_cls,
                        recommender_dir=recommender_dir,
                        ranking_fac_dir=ranking_fac_dir,
                        ranking_sim_dir=ranking_sim_dir,
                        game_item=game_item,
                        rating_item=rating_item,
                        game_csv=game_csv,
                        rating_csv=rating_csv,
                        max_iterations=max_iterations,
                        date_str=date_str,
                        overwrite=overwrite,
                        dry_run=dry_run,
                    )
                except Exception:
                    LOGGER.warning(
                        "There was an error processing commit <%s>, skipping...", commit
                    )

    def handle(self, *args, **kwargs):
        logging.basicConfig(
            stream=sys.stderr,
            level=logging.DEBUG if kwargs["verbosity"] > 1 else logging.INFO,
            format="%(asctime)s %(levelname)-8.8s [%(name)s:%(lineno)s] %(message)s",
        )

        LOGGER.info(kwargs)

        site = kwargs["site"]

        recommender_dir = (
            Path(kwargs["out_recommender"]).resolve() / site
            if kwargs["out_recommender"]
            else None
        )
        ranking_dir = (
            Path(kwargs["out_rankings"]).resolve() / site
            if kwargs["out_rankings"]
            else None
        )

        if not recommender_dir and not ranking_dir:
            kwargs["dry_run"] = True

        for repo in kwargs["repos"]:
            self._process_repo(
                repo=Path(repo).resolve(),
                directories=kwargs["dirs"],
                recommender_cls=BGARecommender if site == "bga" else BGGRecommender,
                recommender_dir=recommender_dir,
                ranking_dir=ranking_dir,
                game_item=f"{site}_GameItem",
                rating_item=f"{site}_RatingItem",
                game_csv=f"{site}.csv",
                rating_csv=f"{site}_ratings.csv",
                max_iterations=kwargs["max_iterations"],
                date_str=kwargs["date_str"],
                overwrite=False if kwargs["dry_run"] else kwargs["overwrite"],
                dry_run=kwargs["dry_run"],
            )

        LOGGER.info("Done.")
