#!/usr/bin/env bash

set -euo pipefail

SAVE_DIR="$(pwd)"
SERVER_DIR="${HOME}/Recommend.Games/recommend-games-server"
STATIC_DIR="${HOME}/Recommend.Games/recommend-games-api/public"

export LC_ALL=en_US.utf-8
export LANG=en_US.utf-8

cd "${SERVER_DIR}"
pipenv run pynt \
    gitprepare \
    makecsvs \
    referencecsvs \
    link \
    trainbgg \
    savebggrankings \
    cleandata \
    filldb \
    kennerspiel \
    dateflag \
    splithotness \
    historicalbggrankings \
    weeklycharts \
    compressdb \
    cplight \
    sitemap \
    deduplicate \
    updatecount \
    gitupdate

cd "${STATIC_DIR}"
git rm -rf "${STATIC_DIR}"

cd "${SERVER_DIR}"
pipenv run ./manage.py staticapi \
    --base-dir "${STATIC_DIR}" \
    --max-items 10000

cd "${STATIC_DIR}"
git add "${STATIC_DIR}"
git commit --no-gpg-sign \
    --message "Update <$(cat "${SERVER_DIR}/data/updated_at")>"
git push

cd "${SAVE_DIR}"
