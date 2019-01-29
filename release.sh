#!/usr/bin/env bash

# before starting, make sure that
# - results are sync'ed and merged to "${WORK_SPACE}/ludoj-data/scraped/"
# - recommender models have been trained to "${WORK_SPACE}/ludoj-recommender/.tc/"
# - pipenv update --dev in "${WORK_SPACE}/ludoj-server"
# - python3 manage.py makemigrations
# - git commit in case anything changed
# - Docker is running

set -euxo pipefail

export DEBUG=''
export WORK_SPACE="${HOME}/Workspace"
export URL_LIVE='https://recommend.games/'

### SERVER ###
cd "${WORK_SPACE}/ludoj-server"

VERSION="$(tr -d '[:space:]' < VERSION)"
echo "Building Ludoj server v${VERSION}..."

# fresh database
rm --recursive --force data.bk .temp* static
mv data data.bk || true
mkdir --parents data/recommender
python3 manage.py migrate

# fill database
echo 'Uploading games, persons, and recommendations to database...'
python3 manage.py filldb \
    "${WORK_SPACE}/ludoj-data/scraped/bgg.jl" \
    --collection-paths "${WORK_SPACE}/ludoj-data/scraped/bgg_ratings.jl" \
    --in-format jl \
    --batch 100000 \
    --recommender "${WORK_SPACE}/ludoj-recommender/.tc" \
    --links "${WORK_SPACE}/ludoj-data/links.json"

# clean up and compress database
echo 'Making database more compact...'
sqlite3 data/db.sqlite3 'VACUUM;'

# update recommender
echo 'Copying recommender model files...'
cp --recursive \
    "${WORK_SPACE}/ludoj-recommender/.tc/recommender" \
    "${WORK_SPACE}/ludoj-recommender/.tc/similarity" \
    "${WORK_SPACE}/ludoj-recommender/.tc/clusters" \
    "${WORK_SPACE}/ludoj-recommender/.tc/compilations" \
    data/recommender/

# minify static
echo 'Copying files and minifying HTML, CSS, and JS...'
python3 manage.py minify \
    'app' \
    '.temp' \
    --delete \
    --exclude-dot

# sitemap
echo 'Generating sitemap...'
python3 manage.py sitemap \
    --url "${URL_LIVE}" \
    --limit 50000 \
    --output .temp/sitemap.xml

# static files
echo 'Collecting static files...'
DEBUG='' python3 manage.py collectstatic --no-input
rm --recursive --force .temp

# build
echo 'Building Docker image...'
docker build --tag 'ludoj-server:${VERSION}' 'ludoj-server:latest' .

# release
# echo 'Building, pushing, and releasing container to Heroku...'
# heroku container:push web --app ludoj
# heroku container:release web --app ludoj

echo 'Done.'
