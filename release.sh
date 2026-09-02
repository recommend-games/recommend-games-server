#!/usr/bin/env bash

set -euo pipefail

SAVE_DIR="$(pwd)"
SERVER_DIR="${HOME}/Recommend.Games/recommend-games-server"

export LC_ALL=en_US.utf-8
export LANG=en_US.utf-8

cd "${SERVER_DIR}"
uv run invoke -c build releasefull

cd "${SAVE_DIR}"
