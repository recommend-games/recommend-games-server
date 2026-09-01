"""Calculate the Recommend.Games rankings.

A polars/numpy port of the Turi Create implementation that used to live in
``board_game_recommender.rankings`` and ``board_game_recommender.trust`` (v3).
The algorithm is unchanged:

* score each user's trustworthiness from the shape of their rating distribution
  and how long they have been rating,
* take every trusted ("heavy") user's top-N recommendations,
* Borda-count those into a per-game score, once unweighted and once weighted by
  user trust.

The one structural difference is that scoring is batched. ``recommend_as_numpy``
materialises a dense ``users x games`` matrix, and with ~100k heavy users over
~100k games that is far too large to hold at once, so users are processed in
chunks and only the per-game running totals are kept.
"""

import logging
import math
from pathlib import Path

import numpy as np
import polars as pl

LOGGER = logging.getLogger(__name__)

USER_ID_KEY = "bgg_user_name"
GAME_ID_KEY = "bgg_id"
RATING_KEY = "bgg_user_rating"
DATE_KEY = "updated_at"

RATINGS_SCHEMA = {
    USER_ID_KEY: pl.String,
    GAME_ID_KEY: pl.Int64,
    RATING_KEY: pl.Float64,
    DATE_KEY: pl.String,
}

#: Users per batch when scoring. 500 users x ~100k games x 8 bytes ~ 400 MB.
DEFAULT_BATCH_SIZE = 500


def _trust_score(ratings, months: int) -> float:
    """Trust in a single user: normality of their ratings, scaled by longevity.

    Mirrors ``board_game_recommender.trust._user_trust``: users who always give
    the same rating, or who have only ever rated within a single month, are not
    trusted at all.
    """

    from scipy.stats import shapiro

    if months < 2 or len(ratings) < 2:
        return 0.0
    if np.all(ratings == ratings[0]):
        return 0.0

    try:
        score = float(shapiro(ratings).statistic)
    except Exception:
        return 0.0

    if not math.isfinite(score):
        return 0.0

    return score * math.log2(months)


def user_trust(ratings: pl.LazyFrame, *, min_ratings: int = 10) -> pl.DataFrame:
    """Trust score per user, as a (user, trust, ratings_count) frame."""

    LOGGER.info("Calculating trust scores...")

    grouped = (
        ratings.filter(pl.col(RATING_KEY).is_not_null() & pl.col(USER_ID_KEY).is_not_null())
        .group_by(USER_ID_KEY)
        .agg(
            pl.col(RATING_KEY).alias("ratings"),
            pl.len().alias("ratings_count"),
            # "2024-05-17T..." -> "2024-05"; distinct months the user was active
            pl.col(DATE_KEY).str.slice(0, 7).n_unique().alias("months"),
        )
        # Users below the threshold score 0 by definition -- skip the maths.
        .filter(pl.col("ratings_count") >= min_ratings)
        .filter(pl.col("months") >= 2)
        .collect(engine="streaming")
    )

    LOGGER.info("Scoring %d users above the rating threshold...", len(grouped))

    trust = [
        _trust_score(np.asarray(row["ratings"], dtype=np.float64), row["months"])
        for row in grouped.iter_rows(named=True)
    ]

    result = grouped.select(USER_ID_KEY, "ratings_count").with_columns(
        pl.Series("trust", trust, dtype=pl.Float64)
    )

    LOGGER.info(
        "Calculated trust scores for %d users, %d of which are trusted",
        len(result),
        result.filter(pl.col("trust") > 0).height,
    )

    return result


def _borda_scores(
    recommender,
    *,
    users: list[str],
    trust: np.ndarray,
    game_ids: np.ndarray,
    top: int,
    batch_size: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Borda-count each user's top-N recommendations into per-game totals.

    Returns the unweighted and trust-weighted sums, both indexed like
    ``game_ids``.
    """

    num_games = len(game_ids)
    top = min(top, num_games)
    scores = np.zeros(num_games, dtype=np.float64)
    scores_weighted = np.zeros(num_games, dtype=np.float64)

    # rank 1 scores `top` points, rank 2 scores `top - 1`, ... (v3: top + 1 - rank)
    points = np.arange(top, 0, -1, dtype=np.float64)

    for start in range(0, len(users), batch_size):
        batch_users = users[start : start + batch_size]
        batch_trust = trust[start : start + batch_size]

        LOGGER.info(
            "Scoring users %d-%d of %d...",
            start,
            start + len(batch_users),
            len(users),
        )

        # (len(batch_users), num_games)
        predictions = recommender.recommend_as_numpy(
            users=batch_users,
            games=game_ids,
        )

        # Partition out the top `top` per user, then order just those.
        rows = np.arange(len(batch_users))[:, None]
        candidates = np.argpartition(-predictions, top - 1, axis=1)[:, :top]
        order = np.argsort(-predictions[rows, candidates], axis=1)
        ranked = candidates[rows, order]

        flat = ranked.ravel()
        scores += np.bincount(
            flat,
            weights=np.broadcast_to(points, ranked.shape).ravel(),
            minlength=num_games,
        )
        scores_weighted += np.bincount(
            flat,
            weights=(points * batch_trust[:, None]).ravel(),
            minlength=num_games,
        )

        del predictions, candidates, order, ranked

    return scores, scores_weighted


def calculate_rankings(
    recommender,
    ratings_path: Path | str,
    *,
    top: int = 100,
    min_ratings: int = 10,
    exclude_games=None,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> pl.DataFrame:
    """Calculate the Recommend.Games rankings.

    Returns a frame with ``bgg_id``, the weighted and unweighted ``score`` /
    ``rank`` pairs, plus ``score_standard``, ``avg_rating`` and ``num_votes``.
    """

    ratings_path = Path(ratings_path).resolve()
    LOGGER.info("Scanning ratings from <%s>...", ratings_path)

    # The ratings file runs to several GB, so it is scanned lazily and never
    # materialised in full -- only the per-user and per-game aggregates are.
    ratings = pl.scan_ndjson(ratings_path, schema=RATINGS_SCHEMA)

    trust = user_trust(ratings, min_ratings=min_ratings)

    games = (
        ratings.filter(pl.col(GAME_ID_KEY).is_not_null())
        .group_by(GAME_ID_KEY)
        .agg(
            pl.col(RATING_KEY).mean().alias("avg_rating"),
            pl.len().alias("num_votes"),
        )
        .collect(engine="streaming")
    )
    LOGGER.info("Found %d games in total", len(games))
    del ratings

    exclude_games = frozenset(exclude_games or ())
    if exclude_games:
        games = games.filter(~pl.col(GAME_ID_KEY).is_in(list(exclude_games)))
        LOGGER.info(
            "Restrict recommendations to %d games after removing %d compilations",
            len(games),
            len(exclude_games),
        )

    # Only rank games the model actually knows about.
    games = games.filter(pl.col(GAME_ID_KEY).is_in(list(recommender.rated_games)))
    games = games.sort(GAME_ID_KEY)
    game_ids = games[GAME_ID_KEY].to_numpy()
    LOGGER.info("Ranking %d games known to the recommender", len(game_ids))

    heavy_users = trust.filter(
        (pl.col("ratings_count") >= min_ratings) & (pl.col("trust") > 0)
    ).filter(pl.col(USER_ID_KEY).is_in(list(recommender.known_users)))
    LOGGER.info("Using %d heavy users for the rankings", len(heavy_users))

    if not len(heavy_users) or not len(game_ids):
        raise ValueError("No heavy users or games to rank")

    scores, scores_weighted = _borda_scores(
        recommender,
        users=heavy_users[USER_ID_KEY].to_list(),
        trust=heavy_users["trust"].to_numpy(),
        game_ids=game_ids,
        top=top,
        batch_size=batch_size,
    )

    scores /= len(heavy_users)
    scores_weighted /= heavy_users["trust"].sum()

    # The "standard" score is what an unknown user would be predicted -- v3 got
    # this from Turi Create's recommend(users=[None]). In the light model
    # unknown users map to the appended zero row, so the result is exactly the
    # per-game linear term plus the intercept (verified against the real model:
    # identical for any unknown name, and bit-for-bit equal to
    # items_linear_terms + intercept). Used only as a tie-breaker below.
    score_standard = recommender.recommend_as_numpy(
        users=["\x00-unknown-user-\x00"],
        games=game_ids,
    )[0]

    result = games.with_columns(
        pl.Series("score", scores),
        pl.Series("score_weighted", scores_weighted),
        pl.Series("score_standard", score_standard),
    ).fill_null(0)

    LOGGER.info("Calculated ranking scores for %d games", len(result))

    tie_breakers = ["score_standard", "avg_rating", "num_votes"]
    result = result.sort(
        ["score_weighted", "score", *tie_breakers], descending=True
    ).with_row_index("rank_weighted", offset=1)
    result = result.sort(
        ["score", "score_weighted", *tie_breakers], descending=True
    ).with_row_index("rank", offset=1)

    return result
