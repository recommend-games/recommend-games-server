#!/usr/bin/env bash

set -euo pipefail

SAVEDIR="$(pwd)"
cd "$(dirname "$(readlink --canonicalize "${BASH_SOURCE[0]}")")"

export LC_ALL=en_US.utf-8
export LANG=en_US.utf-8

# docker login -u _json_key --password-stdin 'https://gcr.io' < 'gs.json'

pipenv run pynt builddbfull

cd "${SAVEDIR}"
