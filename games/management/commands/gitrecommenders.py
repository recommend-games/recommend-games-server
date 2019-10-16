import shutil
from datetime import timezone
from pathlib import Path
from tempfile import TemporaryDirectory
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
        return games_dst, ratings_dst

    ratings_tree = tree / rating_dir
    ratings_dir = dst / rating_dir
    ratings_dir.mkdir(parents=True, exist_ok=True)
    for ratings_blob in ratings_tree.blobs:
        print(ratings_blob)
        ratings_dst = ratings_dir / ratings_blob.name
        with ratings_dst.open("wb") as ratings_fp:
            shutil.copyfileobj(ratings_blob.data_stream, ratings_fp)
    return games_dst, ratings_dir


repo = Repo("/Users/markus/Workspace/ludoj-data-archived")
recommender_dir = Path.home() / "recommenders-hist"

for commit in repo.iter_commits(paths="scraped"):
    date = commit.authored_datetime.astimezone(timezone.utc)
    recommender_dst = recommender_dir / date.strftime("%Y%m%d-%H%M%S")
    shutil.rmtree(recommender_dst, ignore_errors=True)
    recommender_dst.mkdir(parents=True, exist_ok=True)
    print(recommender_dst)

    tree = commit.tree / "scraped"
    print(tree)
    with TemporaryDirectory() as dst:
        games_file, ratings_file = _cp_files(dst, tree)
        print(games_file, ratings_file)
        recommender = BGGRecommender.train_from_files(
            games_file=games_file,
            ratings_file=ratings_file,
            similarity_model=True,
            max_iterations=1000,
            verbose=True,
        )
        recommender.save(recommender_dst)
    break
