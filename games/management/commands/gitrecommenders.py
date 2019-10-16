# -*- coding: utf-8 -*-

import logging
import shutil
import sys

from datetime import timezone
from pathlib import Path
from tempfile import TemporaryDirectory

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


def _main():
    repo = Repo("/Users/markus/Workspace/ludoj-data-archived")
    recommender_dir = Path.home() / "recommenders-hist"
    ranking_dir = recommender_dir / "rankings"

    ranking_fac_dir = ranking_dir / "factor"
    ranking_fac_dir.mkdir(parents=True, exist_ok=True)

    ranking_sim_dir = ranking_dir / "similarity"
    ranking_sim_dir.mkdir(parents=True, exist_ok=True)

    for commit in repo.iter_commits(paths="scraped"):
        date = commit.authored_datetime.astimezone(timezone.utc)

        LOGGER.info("Processing commit <%s> from %s", commit, date)

        ranking_file = date.strftime(f"{DATE_TEMPLATE}.csv")
        ranking_fac_dst = ranking_fac_dir / ranking_file
        ranking_sim_dst = ranking_sim_dir / ranking_file

        if ranking_fac_dst.exists():
            if OVERWRITE:
                LOGGER.info("File <%s> already exists, removing...", ranking_fac_dst)
                ranking_fac_dst.unlink()
            else:
                LOGGER.info(
                    "File <%s> already exists, skipping <%s>...",
                    ranking_fac_dst,
                    commit,
                )
                continue

        if ranking_sim_dst.exists():
            if OVERWRITE:
                LOGGER.info("File <%s> already exists, removing...", ranking_sim_dst)
                ranking_sim_dst.unlink()
            else:
                LOGGER.info(
                    "File <%s> already exists, skipping <%s>...",
                    ranking_sim_dst,
                    commit,
                )
                continue

        recommender_dst = recommender_dir / date.strftime(DATE_TEMPLATE)
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
                "Loading games from <%s> and ratings from <%s>...",
                games_file,
                ratings_file,
            )

            recommender = BGGRecommender.train_from_files(
                games_file=str(games_file),
                ratings_file=str(ratings_file),
                similarity_model=True,
                max_iterations=1000,
                verbose=True,
            )
            recommender.save(recommender_dst)

        LOGGER.info(
            "Saving recommender <%s> to <%s> and <%s>...",
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

    LOGGER.info("Done.")


if __name__ == "__main__":
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8.8s [%(name)s:%(lineno)s] %(message)s",
    )
    _main()
