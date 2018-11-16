#!/usr/bin/env bash

set -euo pipefail

export DEBUG=true
export WS="${HOME}/Workspace"

### SERVER ###
cd "${WS}/ludoj-server"
# linting
pylint ludoj games manage.py
cd app
htmlhint
htmllint
jslint "$(find . -name '*.js')"
jshint "$(find . -name '*.js')"
csslint .
# fresh database
cd ..
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
    --url 'http://localhost:8000/api/' \
    --id-field 'bgg_id'
python3 -m ludoj.json \
    "${WS}/ludoj-scraper/feeds/bgg.jl" \
    --url 'http://localhost:8000/api/' \
    --id-field 'bgg_id' \
    --implementation 'implements'
python3 -m ludoj.json \
    "${WS}/ludoj-scraper/feeds/bgg.jl" \
    --url 'http://localhost:8000/api/' \
    --id-field 'bgg_id' \
    --fields 'designer' 'artist'

### RECOMMENDER ###
cd "${WS}/ludoj-recommender"
rm --recursive --force '.tc'
mkdir --parents '.tc'
# train new recommender model
python3 -m ludoj_recommender \
    --train \
    --model '.tc' \
    --games-file "${WS}/ludoj-scraper/results/bgg.csv" \
    --ratings-file "${WS}/ludoj-scraper/results/bgg_ratings.csv" \
    --verbose
# load recommender file
python3 -m ludoj_recommender.load \
    --model '.tc' \
    --url 'http://localhost:8000/api/games/' \
    --id-field 'bgg_id' \
    --percentiles .165 .365 .615 .815 .915 .965 .985 .995

# stop server now

export DEBUG=

### SERVER ###
cd "${WS}/ludoj-server"
rm --recursive --force .tc static
mkdir --parents .tc/recommender
cp "${WS}"/ludoj-recommender/.tc/recommender/* .tc/recommender/
python3 manage.py collectstatic --no-input
sqlite3 db.sqlite3 'VACUUM;'
heroku container:push web
heroku container:release web
