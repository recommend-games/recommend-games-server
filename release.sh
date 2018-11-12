#!/usr/bin/env bash

set -euo pipefail

WS="${HOME}/Workspace"

### SERVER ###
cd "${WS}/ludoj-server"
rm db.sqlite3
python3 manage.py migrate
python3 manage.py runserver 8000 --noreload # need to keep running

### SCRAPER ###
cd "${WS}/ludoj-scraper"
# load latest files
rsync --archive \
    --rsh='ssh -p 2222' \
    --verbose \
    'monkeybear:~/Workspace/ludoj-scraper/feeds/' \
    "${WS}/ludoj-scraper/feeds/"
./merge.sh # expand
# git add -A ; git commit -m 'updated results' ; git push
# load data into SQLite
python3 -m ludoj.json \
    "${WS}/ludoj-scraper/results/bgg.csv" \
    --output "${WS}/ludoj-scraper/feeds/bgg.jl" \
    --url 'http://localhost:8000/api/games/' \
    --id-field 'bgg_id'

### RECOMMENDER ###
cd "${WS}/ludoj-recommender"
rm --recursive --force .tc
mkdir --parents .tc
# train new recommender model
python3 -m ludoj_recommender \
    --train \
    --model .tc \
    --games-file "${WS}/ludoj-scraper/results/bgg.csv" \
    --ratings-file "${WS}/ludoj-scraper/results/bgg_ratings.csv" \
    --verbose
# load recommender file
python3 -m ludoj_recommender.load \
    --model .tc \
    --url 'http://localhost:8000/api/games/' \
    --id-field 'bgg_id'

# stop server now

### SERVER ###
cd "${WS}/ludoj-server"
rm --recursive --force .tc static
mkdir --parents .tc/recommender
cp ${WS}/ludoj-recommender/.tc/recommender/* .tc/recommender/
python3 manage.py collectstatic --no-input
heroku container:push web
heroku container:release web