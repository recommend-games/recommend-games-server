#!/usr/bin/env bash

set -euo pipefail

SAVEDIR="$(pwd)"
cd "$(dirname "$(readlink --canonicalize "${BASH_SOURCE[0]}")")"

source .env
export LC_ALL=en_US.utf-8
export LANG=en_US.utf-8

pipenv run pynt releasefull

cd "${SAVEDIR}"
