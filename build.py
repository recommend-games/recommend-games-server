#!/usr/bin/env python
# -*- coding: utf-8 -*-

''' pynt build file '''

import logging
import os
import shutil
import sys

from functools import lru_cache

import django

from dotenv import load_dotenv
from pynt import task
from pyntcontrib import execute, safe_cd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv(verbose=True)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ludoj.settings')
os.environ.setdefault('PYTHONPATH', BASE_DIR)
os.environ['DEBUG'] = ''
sys.path.insert(0, BASE_DIR)
django.setup()

from games.utils import parse_bool, parse_date, parse_int, serialize_date

LOGGER = logging.getLogger(__name__)
SETTINGS = django.conf.settings
DATA_DIR = SETTINGS.DATA_DIR
SCRAPER_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', 'ludoj-scraper'))
RECOMMENDER_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', 'ludoj-scraper'))
SCRAPED_DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', 'ludoj-data'))
URL_LIVE = 'https://recommend.games/'
GC_PROJECT = 'recommend-games'

logging.basicConfig(
    stream=sys.stderr,
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)-8.8s [%(name)s:%(lineno)s] %(message)s',
)

# TODO: sync and merge scraped files, retrain recommender

@lru_cache(maxsize=8)
def _server_version(path=os.path.join(BASE_DIR, 'VERSION')):
    with open(path) as file:
        version = file.read()
    return version.strip()


@task()
def cleandata(src_dir=DATA_DIR, bk_dir=f'{DATA_DIR}.bk'):
    ''' clean data file '''
    LOGGER.info(
        'Removing old backup dir <%s> (if any), moving current data dir to backup, '
        'and creating fresh data dir <%s>...', bk_dir, src_dir)
    shutil.rmtree(bk_dir, ignore_errors=True)
    if os.path.exists(src_dir):
        os.rename(src_dir, bk_dir)
    os.makedirs(os.path.join(src_dir, 'recommender'))


@task()
def migrate():
    ''' database migration '''
    assert not SETTINGS.DEBUG
    django.core.management.call_command('migrate')


@task(cleandata, migrate)
def filldb(
        src_dir=SCRAPED_DATA_DIR,
        rec_dir=os.path.join(RECOMMENDER_DIR, '.tc'),
    ):
    ''' fill database '''
    LOGGER.info(
        'Uploading games and other data from <%s>, and recommendations from <%s> to database...',
        src_dir, rec_dir)
    srp_dir = os.path.join(src_dir, 'scraped')
    django.core.management.call_command(
        'filldb',
        os.path.join(srp_dir, 'bgg.jl'),
        collection_paths=[os.path.join(srp_dir, 'bgg_ratings.jl')],
        user_paths=[os.path.join(srp_dir, 'bgg_users.jl')],
        in_format='jl',
        batch=100000,
        recommender=rec_dir,
        links=os.path.join(src_dir, 'links.json'),
    )


@task()
def compressdb(db_file=os.path.join(DATA_DIR, 'db.sqlite3')):
    ''' compress SQLite database file '''
    execute('sqlite3', db_file, 'VACUUM;')


@task()
def cpdirs(
        src_dir=os.path.join(RECOMMENDER_DIR, '.tc'),
        dst_dir=os.path.join(DATA_DIR, 'recommender'),
        sub_dirs=('recommender', 'similarity', 'clusters', 'compilations'),
    ):
    ''' copy recommender files '''
    sub_dirs = sub_dirs.split(',') if isinstance(sub_dirs, str) else sub_dirs
    for sub_dir in sub_dirs:
        src_path = os.path.join(src_dir, sub_dir)
        dst_path = os.path.join(dst_dir, sub_dir)
        LOGGER.info('Copying <%s> to <%s>...', src_path, dst_path)
        shutil.copytree(src_path, dst_path)


@task()
def dateflag(dst=os.path.join(DATA_DIR, 'updated_at'), date=None):
    ''' write date to file '''
    date = parse_date(date) or django.utils.timezone.now()
    date_str = serialize_date(date, tzinfo=django.utils.timezone.utc)
    LOGGER.info('Writing date <%s> to <%s>...', date_str, dst)
    with open(dst, 'w') as file:
        file.write(date_str)


@task()
def syncdata(src=os.path.join(DATA_DIR, ''), bucket='recommend-games-data'):
    ''' sync data with GCS '''
    LOGGER.info('Syncing <%s> with GCS bucket <%s>...', src, bucket)
    os.environ['CLOUDSDK_PYTHON'] = ''
    execute(
        'gsutil', '-m', '-o', 'GSUtil:parallel_composite_upload_threshold=100M',
        'rsync', '-d', '-r', src, f'gs://{bucket}/')


@task(cleandata, filldb, compressdb, cpdirs, dateflag, syncdata)
def releasedb():
    ''' build and release database '''


@task()
def cleanstatic(base_dir=BASE_DIR, sub_dirs=None):
    ''' clean static files '''
    sub_dirs = sub_dirs or ('.temp', 'static')
    for sub_dir in sub_dirs:
        target = os.path.join(base_dir, sub_dir)
        LOGGER.info('Removing dir <%s>...', target)
        shutil.rmtree(target, ignore_errors=True)


@task()
def minify(src=os.path.join(BASE_DIR, 'app'), dst=os.path.join(BASE_DIR, '.temp')):
    ''' copy front-end files and minify HTML, JavaScript, and CSS '''
    LOGGER.info('Copying and minifying files from <%s> to <%s>...', src, dst)
    django.core.management.call_command('minify', src, dst, delete=True, exclude_dot=True)


@task()
def sitemap(url=URL_LIVE, dst=os.path.join(BASE_DIR, '.temp', 'sitemap.xml'), limit=50_000):
    ''' generate sitemap.xml '''
    limit = parse_int(limit) or 50_000
    LOGGER.info('Generating sitemap with URL <%s> to <%s>, limit to %d...', url, dst, limit)
    django.core.management.call_command('sitemap', url=url, limit=limit, output=dst)


@task(cleanstatic, minify, sitemap)
def collectstatic(delete=True):
    ''' generate sitemap.xml '''
    assert not SETTINGS.DEBUG

    static_dirs = SETTINGS.STATICFILES_DIRS
    LOGGER.info('Collecting static files from %s...', static_dirs)
    django.core.management.call_command('collectstatic', no_input=True)

    if not parse_bool(delete):
        return

    for static_dir in static_dirs:
        LOGGER.info('Removing static dir <%s>...', static_dir)
        shutil.rmtree(static_dir, ignore_errors=True)


@task()
def lintpy(*modules):
    ''' lint Python files '''
    modules = modules or ('ludoj', 'games', 'build', 'manage')
    with safe_cd(BASE_DIR):
        execute('pylint', '--exit-zero', *modules)


@task()
def linthtml():
    ''' lint HTML files '''
    with safe_cd(os.path.join(BASE_DIR, 'app')):
        execute('htmlhint', '--ignore', 'google*.html,yandex*.html')
        # execute('htmllint')


@task()
def lintjs():
    ''' lint JavaScript files '''
    with safe_cd(os.path.join(BASE_DIR, 'app')):
        execute('jslint', 'js/*.js')
        execute('jshint', 'js')


@task()
def lintcss():
    ''' lint JavaScript files '''
    with safe_cd(os.path.join(BASE_DIR, 'app')):
        execute('csslint', 'app.css')


@task(lintpy, linthtml, lintjs, lintcss)
def lint():
    ''' lint everything '''


__DEFAULT__ = lint
