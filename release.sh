#!/usr/bin/env bash

set -euo pipefail

SAVE_DIR="$(pwd)"
SERVER_DIR="$(dirname "$(readlink --canonicalize "${BASH_SOURCE[0]}")")"
STATIC_DIR="$(readlink --canonicalize "${SERVER_DIR}/../recommend-games-api/public/")"

export LC_ALL=en_US.utf-8
export LANG=en_US.utf-8

cd "${SERVER_DIR}"
# docker login -u _json_key --password-stdin 'https://gcr.io' < 'gs.json'
pipenv run pynt builddbfull

cd "${STATIC_DIR}"
git rm -rf "${STATIC_DIR}"

cd "${SERVER_DIR}"
pipenv run ./manage.py staticapi \
    --base-dir "${STATIC_DIR}" \
    --max-items 10000

cd "${STATIC_DIR}"
git add "${STATIC_DIR}"
git commit --message "Update <$(cat "${SERVER_DIR}/data/updated_at")>"
git push

cd "${SAVE_DIR}"
