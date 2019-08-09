#!/usr/bin/env bash

set -euxo pipefail

TARGET="${TARGET:-data}"
GC_PROJECT="${GC_PROJECT:-recommend-ludoj}"
GC_DATA_BUCKET="${GC_DATA_BUCKET:-"${GC_PROJECT}-data"}"

if [[ -d "${TARGET}" ]] && [[ "$(find "${TARGET}" -type f | wc -m)" != '0' ]]; then
	echo "Directory ${TARGET} already exists, skip syncing..."
else
	echo "Directory ${TARGET} is empty, syncing with <gs://${GC_DATA_BUCKET}/>..."
	mkdir --parent "${TARGET}"
	gsutil -D version -l
	gsutil -m rsync -r "gs://${GC_DATA_BUCKET}/" "${TARGET}"
fi

exec "$@"
