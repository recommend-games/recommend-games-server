#!/usr/bin/env bash

set -euxo pipefail

export DEBUG=''
export WORK_SPACE="${HOME}/Workspace"
export NEWS_HOSTING_BUCKET='news.recommend.games'
export NEWS_DATA_BUCKET='scrape.news.recommend.games'

### SCRAPER ###
cd "${WORK_SPACE}/ludoj-scraper"
mkdir --parents 'feeds/news' 'feeds/news_hosting'
aws s3 sync "s3://${NEWS_DATA_BUCKET}/" 'feeds/news/'
python3 -m ludoj.merge \
    'feeds/news/*/*/*.jl' \
    --out-path 'feeds/news_merged.jl' \
    --keys article_id \
    --key-types string \
    --latest published_at scraped_at \
    --latest-types date date \
    --sort-latest desc \
    --concat

### SERVER ###
cd "${WORK_SPACE}/ludoj-server"
python3 manage.py splitfile \
    "${WORK_SPACE}/ludoj-scraper/feeds/news_merged.jl" \
    --out-file "${WORK_SPACE}/ludoj-scraper/feeds/news_hosting/news_{number:05d}.json" \
    --batch 25
aws s3 sync --acl public-read \
    --exclude '.gitignore' \
    --exclude '.DS_Store' \
    --exclude '.bucket' \
    --delete \
    "${WORK_SPACE}/ludoj-scraper/feeds/news_hosting/" "s3://${NEWS_HOSTING_BUCKET}/"

echo 'Done.'
