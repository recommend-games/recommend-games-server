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

URL_LIVE='https://recommend.games/'

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
    "${WORK_SPACE}"/ludoj-recommender/.tc/compilations \
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

# sitemap
echo 'Generating sitemap...'
pipenv run pipenv run python3 manage.py sitemap \
    --url "${URL_LIVE}" \
    --limit 50000 \
    --output .temp/sitemap.xml

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
