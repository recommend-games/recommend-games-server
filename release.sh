#!/usr/bin/env bash

# before starting, make sure that
# - results are sync'ed and merged to "${WORK_SPACE}/ludoj-scraper/results/"
# - recommender models have been trained to "${WORK_SPACE}/ludoj-recommender/.tc/"
# - pipenv update --dev in "${WORK_SPACE}/ludoj-server"
# - Docker is running

set -euxo pipefail

export DEBUG=true
export WORK_SPACE="${HOME}/Workspace"

PORT=8000
URL="http://localhost:${PORT}/api"
URL_LIVE='https://recommend.games/'

if curl --head --fail "${URL}/"; then
    echo "The server appears to be already running on port <$PORT>, aborting..."
    exit 1
fi

### SERVER ###
cd "${WORK_SPACE}/ludoj-server"

# fresh database
mv db.sqlite3 db.sqlite3.bk || true
python3 manage.py migrate

# run server
mkdir -p logs
nohup python3 manage.py runserver "$PORT" --noreload >> 'logs/server.log' 2>&1 &
SERVER_PID="${!}"
echo "Started server with pid <${SERVER_PID}>..."

while true && ! curl --head --fail "${URL}/"; do
    echo 'Server is not ready yet'
    sleep 1
done
echo 'Server is up and running!'

### SCRAPER ###
cd "${WORK_SPACE}/ludoj-scraper"

# games
echo 'Uploading games to database...'
python3 -m ludoj.json \
    'results/bgg.csv' \
    --output 'feeds/bgg.jl' \
    --url "${URL}/" \
    --id-field 'bgg_id'

# implementations
echo 'Uploading implementations to database...'
python3 -m ludoj.json \
    'feeds/bgg.jl' \
    --url "${URL}/" \
    --id-field 'bgg_id' \
    --implementation 'implements'

# persons
echo 'Uploading persons to database...'
python3 -m ludoj.json \
    'feeds/bgg.jl' \
    --url "${URL}/" \
    --id-field 'bgg_id' \
    --fields 'designer' 'artist'

### SERVER ###
cd "${WORK_SPACE}/ludoj-server"

# update recommender
rm --recursive --force .tc* .temp* static
mkdir --parents .tc/recommender
cp "${WORK_SPACE}"/ludoj-recommender/.tc/recommender/* .tc/recommender/

# recommendations
echo 'Uploading recommendations to database...'
python3 -m ludoj_recommender.load \
    --model '.tc' \
    --url "${URL}/games/" \
    --id-field 'bgg_id' \
    --percentiles .165 .365 .615 .815 .915 .965 .985 .995

# minify static
mkdir --parents .temp
cp --recursive app/* .temp/
for FILE in $(find app -name '*.css'); do
    python3 -m rcssmin < "${FILE}" > ".temp/${FILE#app/}"
done
for FILE in $(find app -name '*.js'); do
    python3 -m rjsmin < "${FILE}" > ".temp/${FILE#app/}"
done
# TODO minify HTML

# sitemap
echo 'Generating sitemap...'
python3 sitemap.py \
    --url "${URL_LIVE}" \
    --api-url "${URL}/games/" \
    --limit 50000 \
    --output .temp/sitemap.xml

# stop server now
echo 'Stopping the server...'
kill "${SERVER_PID}" || true
sleep 10

# static files
DEBUG='' python3 manage.py collectstatic --no-input
rm --recursive --force .temp

# clean up database
sqlite3 db.sqlite3 'VACUUM;'

# release
echo 'Building, pushing, and releasing container to Heroku'
heroku container:push web --app ludoj
heroku container:release web --app ludoj

echo 'Done.'
