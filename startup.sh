#!/usr/bin/env bash

set -euxo pipefail

DATA_DIR="${DATA_DIR:-data}"
SITEMAP_SRC="${SITEMAP_SRC:-"${DATA_DIR}/sitemap.xml"}"
SITEMAP_DST="${SITEMAP_DST:-"static/sitemap.xml"}"
GC_PROJECT="${GC_PROJECT:-recommend-games}"
GC_DATA_BUCKET="${GC_DATA_BUCKET:-"${GC_PROJECT}-data"}"

if [[ -d "${DATA_DIR}" ]] && [[ "$(find "${DATA_DIR}" -type f | wc -m)" != '0' ]]; then
	echo "Directory <${DATA_DIR}> already exists, skip syncing..."
else
	echo "Directory <${DATA_DIR}> is empty, syncing with <gs://${GC_DATA_BUCKET}/>..."
	mkdir --parent "${DATA_DIR}"
	gsutil -D version -l
	gsutil -m rsync -r "gs://${GC_DATA_BUCKET}/" "${DATA_DIR}"
fi

if [[ ! -s "${SITEMAP_DST}" ]] && [[ -s "${SITEMAP_SRC}" ]]; then
	echo "Coping <${SITEMAP_SRC}> to <${SITEMAP_DST}>..."
	cp "${SITEMAP_SRC}" "${SITEMAP_DST}"
fi

exec "$@"
