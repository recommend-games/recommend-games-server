#!/usr/bin/env bash

set -euo pipefail

SAVE_DIR="$(pwd)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
FEEDS_DIR="$(cd "${SERVER_DIR}/../board-game-scraper/feeds" && pwd)"

export LC_ALL=en_US.utf-8
export LANG=en_US.utf-8

cd "${SERVER_DIR}"

for TYPE in 'rankings' 'abstract' 'children' 'customizable' 'family' 'party' 'strategy' 'thematic' 'war'
do
    [[ "${TYPE}" == 'rankings' ]] && SITE='bgg_rankings' || SITE="bgg_rankings_${TYPE}"
    echo "Processing rankings of type <${TYPE}>…"
    uv run invoke -c build \
        "mergebgg${TYPE}" --in-paths "${FEEDS_DIR}/${SITE}/GameItem/*-json-*" --days 365 \
        "split${TYPE}" --overwrite
done

uv run invoke -c build deduplicate updatecount gitupdate

echo 'Done.'

cd "${SAVE_DIR}"
