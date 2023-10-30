#!/usr/bin/env bash

set -euo pipefail

SAVE_DIR="$(pwd)"
SCRIPT_DIR="$(dirname "$(readlink --canonicalize "${BASH_SOURCE[0]}")")"
SERVER_DIR="$(readlink --canonicalize "${SCRIPT_DIR}/../")"
FEEDS_DIR="$(readlink --canonicalize "${SERVER_DIR}/../board-game-scraper/feeds/")"

export LC_ALL=en_US.utf-8
export LANG=en_US.utf-8

cd "${SERVER_DIR}"

for TYPE in 'rankings' 'abstract' 'children' 'customizable' 'family' 'party' 'strategy' 'thematic' 'war'
do
    [[ "${TYPE}" == 'rankings' ]] && SITE='bgg_rankings' || SITE="bgg_rankings_${TYPE}"
    echo "Processing rankings of type <${TYPE}>…"
    pipenv run pynt "mergebgg${TYPE}[in_paths=${FEEDS_DIR}/${SITE}/GameItem/*-json-*,days=365]" "split${TYPE}[overwrite=1]"
done

pipenv run pynt deduplicate updatecount gitupdate

echo 'Done.'

cd "${SAVE_DIR}"
