#!/usr/bin/env bash

# before starting, make sure that
# - results are sync'ed and merged to "${WORK_SPACE}/ludoj-scraper/results/"
# - recommender models have been trained to "${WORK_SPACE}/ludoj-recommender/.tc/"
# - pipenv update --dev in "${WORK_SPACE}/ludoj-server"
# - python3 manage.py makemigrations
# - git commit in case anything changed
# - Docker is running

set -euxo pipefail

export PIPENV_DONT_LOAD_ENV=1
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
pipenv run python3 manage.py migrate

# fill database
echo 'Uploading games, persons, and recommendations to database...'
pipenv run python3 manage.py filldb \
    "${WORK_SPACE}/ludoj-scraper/results/bgg.jl" \
    --collection-paths "${WORK_SPACE}/ludoj-scraper/results/bgg_ratings.jl" \
    --in-format jl \
    --batch 100000 \
    --recommender "${WORK_SPACE}/ludoj-recommender/.tc"

# update recommender
rm --recursive --force .tc* .temp* static
mkdir --parents .tc
cp --recursive \
    "${WORK_SPACE}"/ludoj-recommender/.tc/recommender \
    "${WORK_SPACE}"/ludoj-recommender/.tc/clusters \
    .tc/

# minify static
mkdir --parents .temp
cp --recursive app/* .temp/
for FILE in $(find app -name '*.css'); do
    pipenv run python3 -m rcssmin < "${FILE}" > ".temp/${FILE#app/}"
done
for FILE in $(find app -name '*.js'); do
    pipenv run python3 -m rjsmin < "${FILE}" > ".temp/${FILE#app/}"
done
# TODO minify HTML

# run server
mkdir -p logs
nohup pipenv run python3 manage.py runserver "$PORT" --noreload >> 'logs/server.log' 2>&1 &
SERVER_PID="${!}"
echo "Started server with pid <${SERVER_PID}>..."

while true && ! curl --head --fail "${URL}/"; do
    echo 'Server is not ready yet'
    sleep 1
done
echo 'Server is up and running!'

# sitemap
echo 'Generating sitemap...'
pipenv run python3 sitemap.py \
    --url "${URL_LIVE}" \
    --api-url "${URL}/games/" \
    --limit 50000 \
    --output .temp/sitemap.xml

# stop server now
echo 'Stopping the server...'
kill "${SERVER_PID}" || true
sleep 10

# static files
DEBUG='' pipenv run python3 manage.py collectstatic --no-input
rm --recursive --force .temp

# clean up database
sqlite3 db.sqlite3 'VACUUM;'

# release
echo 'Building, pushing, and releasing container to Heroku'
heroku container:push web --app ludoj
heroku container:release web --app ludoj

echo 'Done.'
