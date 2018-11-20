#!/usr/bin/env bash

set -euxo pipefail

export DEBUG=true
export WORK_SPACE="${HOME}/Workspace"

# before starting, make sure that
# - results are sync'ed and merged to "${WORK_SPACE}/ludoj-scraper/results/"
# - recommender models have been trained to "${WORK_SPACE}/ludoj-recommender/.tc/"
# - pipenv update --dev in "${WORK_SPACE}/ludoj-server"
# - Docker is running
# - no other instance of server is running (e.g., from previous run)

### SERVER ###
cd "${WORK_SPACE}/ludoj-server"
# fresh database
mv db.sqlite3 db.sqlite3.bk || true
python3 manage.py migrate
# run server
mkdir -p logs
nohup python3 manage.py runserver 8000 --noreload >> 'logs/server.log' 2>&1 &
SERVER_PID="$!"
echo "Started server with pid <${SERVER_PID}>..."
while true && ! curl --head --fail 'http://localhost:8000/api/'; do
    echo 'Server is not ready yet'
    sleep 1
done
echo 'Server is up and running!'

### SCRAPER ###
cd "${WORK_SPACE}/ludoj-scraper"
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
cd "${WORK_SPACE}/ludoj-server"
# update recommender
rm --recursive --force .tc* .temp* static
mkdir --parents .tc/recommender
cp "${WORK_SPACE}"/ludoj-recommender/.tc/recommender/* .tc/recommender/
python3 -m ludoj_recommender.load \
    --model '.tc' \
    --url 'http://localhost:8000/api/games/' \
    --id-field 'bgg_id' \
    --percentiles .165 .365 .615 .815 .915 .965 .985 .995
# stop server now
kill "${SERVER_PID}" || true
sleep 10
# minify static
mkdir --parents .temp
cp --recursive app/* .temp/
css-html-js-minify --overwrite .temp
export DEBUG=
python3 manage.py collectstatic --no-input
rm --recursive --force .temp
sqlite3 db.sqlite3 'VACUUM;'
heroku container:push web
heroku container:release web
