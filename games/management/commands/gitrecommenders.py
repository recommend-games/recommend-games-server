import shutil
from pathlib import Path
import turicreate as tc
from git import Blob, Repo, Tree
from ludoj_recommender import BGGRecommender


def _cp_files(dst, tree, game_file="bgg_GameItem.jl", rating_dir="bgg_RatingItem"):
    dst = Path(dst)
    dst.mkdir(parents=True, exist_ok=True)
    print(dst)

    games_blob = tree / game_file
    print(games_blob)
    games_dst = dst / game_file
    with games_dst.open("wb") as games_fp:
        shutil.copyfileobj(games_blob.data_stream, games_fp)

    try:
        ratings_blob = tree / f"{rating_dir}.jl"
    except Exception:
        pass
    else:
        print(ratings_blob)
        ratings_dst = dst / f"{rating_dir}.jl"
        with ratings_dst.open("wb") as ratings_fp:
            shutil.copyfileobj(ratings_blob.data_stream, ratings_fp)
        return

    ratings_tree = tree / rating_dir
    ratings_dir = dst / rating_dir
    ratings_dir.mkdir(parents=True, exist_ok=True)
    for ratings_blob in ratings_tree.blobs:
        print(ratings_blob)
        ratings_dst = ratings_dir / ratings_blob.name
        with ratings_dst.open("wb") as ratings_fp:
            shutil.copyfileobj(ratings_blob.data_stream, ratings_fp)


repo = Repo("/Users/markus/Workspace/ludoj-data-archived/")
for commit in repo.iter_commits(paths="scraped"):
    tree = commit.tree / "scraped"
    print(tree)
    _cp_files("/Users/markus/test-tmp", tree)
    break
