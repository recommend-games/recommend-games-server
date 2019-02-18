#!/usr/bin/env bash

# before starting, make sure that
# - pipenv update --dev in "${WORK_SPACE}/ludoj-server"
# - git commit in case anything changed
# - Docker is running

set -euxo pipefail

SAVEDIR="$(pwd)"
cd "$(dirname "$(readlink --canonicalize "${BASH_SOURCE[0]}")")"

export DEBUG=''
export URL_LIVE='https://recommend.games/'
export GC_PROJECT="${GC_PROJECT:-recommend-games}"

VERSION="$(tr -d '[:space:]' < VERSION)"
echo "Building Ludoj server v${VERSION}..."

# clear files
rm --recursive --force .temp* static

# minify static
echo 'Copying files and minifying HTML, CSS, and JS...'
python3 manage.py minify \
    'app' \
    '.temp' \
    --delete \
    --exclude-dot

# sitemap
echo 'Generating sitemap...'
python3 manage.py sitemap \
    --url "${URL_LIVE}" \
    --limit 50000 \
    --output .temp/sitemap.xml

# static files
echo 'Collecting static files...'
python3 manage.py collectstatic --no-input
rm --recursive --force .temp

# build
echo 'Building Docker image...'
docker build \
    --tag "ludoj-server:${VERSION}" \
    --tag 'ludoj-server:latest' \
    --tag "gcr.io/${GC_PROJECT}/ludoj-server:${VERSION}" \
    --tag "gcr.io/${GC_PROJECT}/ludoj-server:latest" \
    .
docker push "gcr.io/${GC_PROJECT}/ludoj-server:${VERSION}"
gcloud app deploy \
    --project "${GC_PROJECT}" \
    --image-url "gcr.io/${GC_PROJECT}/ludoj-server:${VERSION}" \
    --version "${VERSION}" \
    --promote \
    --quiet

echo 'Done.'

cd "${SAVEDIR}"
