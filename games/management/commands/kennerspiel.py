from bg_utils import transform
import joblib
from games.models import Game
from pytility import parse_int

model = joblib.load("../recommend-games-blog/experiments/kennerspiel/model.joblib")

features = [
    "min_players",
    "max_players",
    "min_age",
    "min_time",
    "max_time",
    "cooperative",
    "complexity",
]

cat_features = [
    "game_type",
    "mechanic",
    "category",
]

data = pd.DataFrame.from_records(
    Game.objects.values("bgg_id", *features), index="bgg_id"
)


def concat(values):
    return ",".join(map(str, filter(None, map(parse_int, values))))


for col in cat_features:
    tmp = pd.DataFrame.from_records(Game.objects.values("bgg_id", col))
    data[col] = tmp.groupby("bgg_id")[col].apply(concat)

data["kennerspiel_score"] = model.predict_proba(data)[:, 1]
