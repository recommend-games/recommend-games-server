#!/usr/bin/env bash

set -euxo pipefail

export DEBUG=true
export WS="${HOME}/Workspace"

# before starting, make sure that
# - results are sync'ed and merged to "${WS}/ludoj-scraper/results/"
# - recommender models have been trained to "${WS}"/ludoj-recommender/.tc/"
# - pipenv update --dev in "${WS}/ludoj-server"
# - Docker is running

### SERVER ###
cd "${WS}/ludoj-server"
# fresh database
mv db.sqlite3 db.sqlite3.bk || true
python3 manage.py migrate
# run server
nohup python3 manage.py runserver 8000 --noreload >> 'server.log' 2>&1 &
SERVER_PID="$!"
echo "Started server with pid <${SERVER_PID}>..."
while true && ! curl --head --fail 'http://localhost:8000/api/'; do
    echo 'Server is not ready yet'
    sleep 1
done
echo 'Server is up and running!'

### SCRAPER ###
cd "${WS}/ludoj-scraper"
python3 -m ludoj.json \
    'results/bgg.csv' \
    --output 'feeds/bgg.jl' \
    --url 'http://localhost:8000/api/' \
    --id-field 'bgg_id'
python3 -m ludoj.json \
    'feeds/bgg.jl' \
    --url 'http://localhost:8000/api/' \
    --id-field 'bgg_id' \
    --implementation 'implements'
python3 -m ludoj.json \
    'feeds/bgg.jl' \
    --url 'http://localhost:8000/api/' \
    --id-field 'bgg_id' \
    --fields 'designer' 'artist'

### SERVER ###
cd "${WS}/ludoj-server"
# update recommender
rm --recursive --force .tc static
mkdir --parents .tc/recommender
cp "${WS}"/ludoj-recommender/.tc/recommender/* .tc/recommender/
python3 -m ludoj_recommender.load \
    --model '.tc' \
    --url 'http://localhost:8000/api/games/' \
    --id-field 'bgg_id' \
    --percentiles .165 .365 .615 .815 .915 .965 .985 .995
# stop server now
kill "${SERVER_PID}"
sleep 10
export DEBUG=
python3 manage.py collectstatic --no-input
sqlite3 db.sqlite3 'VACUUM;'
heroku container:push web
heroku container:release web
