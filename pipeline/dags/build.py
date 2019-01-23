# -*- coding: utf-8 -*-

''' build workflow '''

import os

from datetime import datetime, timedelta, timezone
from functools import partial

from airflow import DAG
from airflow.operators.bash_operator import BashOperator
from airflow.operators.python_operator import PythonOperator
from ludoj_scraper.cluster import link_games
from ludoj_scraper.merge import csv_merge
from ludoj_scraper.utils import normalize_space, parse_date, parse_int, to_str

URL_LIVE = 'https://recommend.games/'
WORK_SPACE = '/Users/markus/Workspace'
VERSION = normalize_space(open(os.path.join(WORK_SPACE, 'ludoj-server', 'VERSION')).read())

def _execute_django_command(*args):
    os.environ['DJANGO_SETTINGS_MODULE'] = 'ludoj.settings'
    os.environ['DEBUG'] = ''
    from django.core.management import execute_from_command_line
    return execute_from_command_line(('manage.py',) + args)

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2019, 1, 23),
    'email': ['recommend.ludoj@gmail.com'],
    'email_on_failure': True,
    'email_on_retry': True,
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
}

merge_args = {
    'bgg': {
        'key_parsers': (parse_int,),
        'fieldnames_exclude': frozenset({
            'game_type',
            'list_price',
            'image_file',
            'freebase_id',
            'wikidata_id',
            'wikipedia_id',
            'dbpedia_id',
            'luding_id',
            'published_at',
            'updated_at',
            'scraped_at',
        }),
    },
    'dbpedia': {
        'fieldnames': frozenset({
            'name',
            'alt_name',
            'year',
            'description',
            'designer',
            'publisher',
            'url',
            'image_url',
            'external_link',
            'min_players',
            'max_players',
            'min_age',
            'max_age',
            'bgg_id',
            'freebase_id',
            'wikidata_id',
            'wikipedia_id',
            'dbpedia_id',
            'luding_id',
            'spielen_id',
        }),
    },
    'luding': {
        'key_parsers': (parse_int,),
        'fieldnames': frozenset({
            'name',
            'year',
            'game_type',
            'description',
            'designer',
            'artist',
            'publisher',
            'url',
            'image_url',
            'external_link',
            'min_players',
            'max_players',
            'min_age',
            'max_age',
            'bgg_id',
            'freebase_id',
            'wikidata_id',
            'wikipedia_id',
            'dbpedia_id',
            'luding_id',
            'spielen_id',
        }),
    },
    'spielen': {
        'fieldnames': frozenset({
            'name',
            'year',
            'description',
            'designer',
            'artist',
            'publisher',
            'url',
            'image_url',
            'video_url',
            'min_players',
            'max_players',
            'min_age',
            'max_age',
            'min_time',
            'max_time',
            'family',
            'num_votes',
            'avg_rating',
            'worst_rating',
            'best_rating',
            'complexity',
            'easiest_complexity',
            'hardest_complexity',
            'bgg_id',
            'freebase_id',
            'wikidata_id',
            'wikipedia_id',
            'dbpedia_id',
            'luding_id',
            'spielen_id',
        }),
    },
    'wikidata': {
        'fieldnames': frozenset({
            'name',
            'alt_name',
            'year',
            'designer',
            'artist',
            'publisher',
            'url',
            'image_url',
            'external_link',
            'min_players',
            'max_players',
            'min_age',
            'max_age',
            'min_time',
            'max_time',
            'family',
            'bgg_id',
            'freebase_id',
            'wikidata_id',
            'wikipedia_id',
            'dbpedia_id',
            'luding_id',
            'spielen_id',
        }),
    },
}

merge_operators = {}

with DAG('build', default_args=default_args, schedule_interval=timedelta(days=1)) as dag:
    for site, kwargs in merge_args.items():
        kwargs = dict(kwargs)
        kwargs.setdefault(
            'in_paths', os.path.join(WORK_SPACE, f'ludoj-scraper/feeds/{site}/GameItem/*'))
        kwargs.setdefault('out_path', os.path.join(WORK_SPACE, f'ludoj-data/scraped/{site}.jl'))
        kwargs.setdefault('keys', (f'{site}_id',))
        kwargs.setdefault('key_parsers', (to_str,))
        kwargs.setdefault('latest', ('scraped_at',))
        kwargs.setdefault('latest_parsers', (partial(parse_date, tzinfo=timezone.utc),))
        kwargs.setdefault('sort_output', True)
        kwargs.setdefault('concat_output', True)
        kwargs.setdefault('log_level', 'INFO')

        merge_operators[site] = PythonOperator(
            task_id=f'merge_{site}',
            python_callable=csv_merge,
            op_kwargs=kwargs,
        )

    link_games_operator = PythonOperator(
        task_id='link_games',
        python_callable=link_games,
        op_kwargs={
            'gazetteer': os.path.join(WORK_SPACE, 'ludoj-scraper/cluster/gazetteer.pickle'),
            'paths': (
                os.path.join(WORK_SPACE, 'ludoj-data/scraped/bgg.jl'),
                # os.path.join(WORK_SPACE, 'ludoj-data/scraped/dbpedia.jl'),
                os.path.join(WORK_SPACE, 'ludoj-data/scraped/luding.jl'),
                os.path.join(WORK_SPACE, 'ludoj-data/scraped/spielen.jl'),
                os.path.join(WORK_SPACE, 'ludoj-data/scraped/wikidata.jl'),
            ),
            'threshold': .8,
            # 'recall_weight': .5,
            'output': os.path.join(WORK_SPACE, 'ludoj-data/links.json'),
        },
    )

    mv_old_db_operator = BashOperator(
        task_id='mv_old_db',
        bash_command=f'''
            mv {WORK_SPACE}/ludoj-server/db.sqlite3 \
                {WORK_SPACE}/ludoj-server/db.sqlite3.bk || true
        ''',
    )

    init_db_operator = PythonOperator(
        task_id='init_db',
        python_callable=_execute_django_command,
        op_args=('migrate',),
    )

    fill_db_operator = PythonOperator(
        task_id='fill_db',
        python_callable=_execute_django_command,
        op_args=(
            'filldb',
            os.path.join(WORK_SPACE, 'ludoj-data/scraped/bgg.jl'),
            '--collection-paths', os.path.join(WORK_SPACE, 'ludoj-data/scraped/bgg_ratings.jl'),
            '--in-format', 'jl',
            '--batch', '100000',
            '--recommender', os.path.join(WORK_SPACE, 'ludoj-recommender/.tc'),
            '--links', os.path.join(WORK_SPACE, 'ludoj-data/links.json'),
        ),
    )

    vacuum_db_operator = BashOperator(
        task_id='vacuum_db',
        bash_command=f"sqlite3 {WORK_SPACE}/ludoj-server/db.sqlite3 'VACUUM;'",
    )

    cp_static_files_operator = BashOperator(
        task_id='cp_static_files',
        bash_command=f'''
            cd '{WORK_SPACE}/ludoj-server'
            rm --recursive --force .tc* .temp* static
            mkdir --parents .tc
            cp --recursive \
                '{WORK_SPACE}/ludoj-recommender/.tc/recommender' \
                '{WORK_SPACE}/ludoj-recommender/.tc/similarity' \
                '{WORK_SPACE}/ludoj-recommender/.tc/clusters' \
                '{WORK_SPACE}/ludoj-recommender/.tc/compilations' \
                .tc/
            mkdir --parents .temp
            cp --recursive app/* .temp/
        ''',
    )

    sitemap_operator = PythonOperator(
        task_id='sitemap',
        python_callable=_execute_django_command,
        op_args=(
            'sitemap',
            '--url', URL_LIVE,
            '--limit', '50000',
            '--output', os.path.join(WORK_SPACE, 'ludoj-server/.temp/sitemap.xml'),
        ),
    )

    collect_static_files_operator = PythonOperator(
        task_id='collect_static_files',
        python_callable=_execute_django_command,
        op_args=('collectstatic', '--no-input'),
    )

    docker_operator = BashOperator(
        task_id='docker',
        bash_command=f'''
            docker build \
                --file '{WORK_SPACE}/ludoj-server/Dockerfile' \
                --tag 'ludoj-server:{VERSION}' \
                    'ludoj-server:latest' \
                    'registry.heroku.com/ludoj/web:latest' \
                '{WORK_SPACE}/ludoj-server/'
            # docker push 'registry.heroku.com/ludoj/web:latest'
        ''',
    )

    [merge_operators[site] for site in ('bgg', 'luding', 'spielen', 'wikidata')] \
        >> link_games_operator
    mv_old_db_operator >> init_db_operator
    [link_games_operator, init_db_operator] \
        >> fill_db_operator \
        >> vacuum_db_operator
    [vacuum_db_operator, cp_static_files_operator] \
        >> sitemap_operator \
        >> collect_static_files_operator \
        >> docker_operator
