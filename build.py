#!/usr/bin/env python
# -*- coding: utf-8 -*-

''' pynt build file '''

import logging
import os
import shutil
import sys

import django

from dotenv import load_dotenv
from pynt import task
from pyntcontrib import execute, safe_cd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv(verbose=True)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ludoj.settings')
os.environ.setdefault('PYTHONPATH', BASE_DIR)
sys.path.insert(0, BASE_DIR)
django.setup()

from games.utils import parse_date, serialize_date

LOGGER = logging.getLogger(__name__)
SETTINGS = django.conf.settings
DATA_DIR = SETTINGS.DATA_DIR


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
    django.core.management.call_command('migrate')


@task(cleandata, migrate)
def filldb(
        src_dir=os.path.join(BASE_DIR, '..', 'ludoj-data'),
        rec_dir=os.path.join(BASE_DIR, '..', 'ludoj-recommender', '.tc'),
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
        src_dir=os.path.join(BASE_DIR, '..', 'ludoj-recommender', '.tc'),
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
