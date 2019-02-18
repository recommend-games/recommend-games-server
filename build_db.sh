#!/usr/bin/env bash

# before starting, make sure that
# - results are sync'ed and merged to "${WORK_SPACE}/ludoj-data/scraped/"
# - recommender models have been trained to "${WORK_SPACE}/ludoj-recommender/.tc/"
# - python3 manage.py makemigrations
# - git commit in case anything changed

set -euxo pipefail

SAVEDIR="$(pwd)"
cd "$(dirname "$(readlink --canonicalize "${BASH_SOURCE[0]}")")"

export DEBUG=''
export GC_PROJECT="${GC_PROJECT:-recommend-games}"
export GS_BUCKET="${GS_BUCKET:-"${GC_PROJECT}-data"}"

# fresh database
rm --recursive --force data.bk*
mv data data.bk || true
mkdir --parents data/recommender
python3 manage.py migrate

# fill database
echo 'Uploading games, persons, and recommendations to database...'
python3 manage.py filldb \
    '../ludoj-data/scraped/bgg.jl' \
    --collection-paths '../ludoj-data/scraped/bgg_ratings.jl' \
    --user-paths '../ludoj-data/scraped/bgg_users.jl' \
    --in-format jl \
    --batch 100000 \
    --recommender '../ludoj-recommender/.tc' \
    --links '../ludoj-data/links.json'

# clean up and compress database
echo 'Making database more compact...'
sqlite3 'data/db.sqlite3' 'VACUUM;'

# update recommender
echo 'Copying recommender model files...'
cp --recursive \
    '../ludoj-recommender/.tc/recommender' \
    '../ludoj-recommender/.tc/similarity' \
    '../ludoj-recommender/.tc/clusters' \
    '../ludoj-recommender/.tc/compilations' \
    'data/recommender/'

# last update flag
echo 'Creating last update flag...'
date --utc +'%Y-%m-%dT%H:%M:%SZ' > data/updated_at

# sync data to GCS
CLOUDSDK_PYTHON='' gsutil -m -o GSUtil:parallel_composite_upload_threshold=100M \
    rsync -d -r \
    'data/' "gs://${GS_BUCKET}/"

echo 'Done.'

cd "${SAVEDIR}"
