#!/usr/bin/env bash

# before starting, make sure that
# - results are sync'ed and merged to "${WORK_SPACE}/ludoj-data/scraped/"
# - recommender models have been trained to "${WORK_SPACE}/ludoj-recommender/.tc/"
# - pipenv update --dev in "${WORK_SPACE}/ludoj-server"
# - python3 manage.py makemigrations
# - git commit in case anything changed
# - Docker is running

set -euxo pipefail

SAVEDIR="$(pwd)"
cd "$(dirname "$(readlink --canonicalize "${BASH_SOURCE[0]}")")"

sh build_db.sh
sh build_server.sh

echo 'Done.'

cd "${SAVEDIR}"
