#!/usr/bin/env bash

set -euxo pipefail

TARGET="${TARGET:-data}"
GS_BUCKET="${GS_BUCKET:-recommend-games-data}"

if [[ -d "${TARGET}" ]] && [[ "$(find "${TARGET}" -type f | wc -m)" != '0' ]]; then
	echo "Directory ${TARGET} already exists, skip syncing..."
else
	echo "Directory ${TARGET} is empty, syncing with <gs://${GS_BUCKET}/>..."
	mkdir --parent "${TARGET}"
	gsutil -D version -l
	gsutil -m rsync -r "gs://${GS_BUCKET}/" "${TARGET}"
fi

exec "$@"
