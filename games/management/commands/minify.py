# -*- coding: utf-8 -*-

''' Minify static files '''

import logging
import os
import re
import sys

from functools import partial
from shutil import copyfileobj, rmtree

from django.core.management.base import BaseCommand
from rcssmin import cssmin
from rjsmin import jsmin

from ...utils import arg_to_iter

LOGGER = logging.getLogger(__name__)


def _minify_css(fsrc, fdst, keep_bang_comments=False, encoding='utf-8'):
    str_in = fsrc.read().decode(encoding)
    str_out = cssmin(str_in, keep_bang_comments=keep_bang_comments)
    fdst.write(str_out.encode(encoding))


def _minify_js(fsrc, fdst, keep_bang_comments=False, encoding='utf-8'):
    str_in = fsrc.read().decode(encoding)
    str_out = jsmin(str_in, keep_bang_comments=keep_bang_comments)
    fdst.write(str_out.encode(encoding))


def _minify_html(fsrc, fdst, encoding='utf-8'):
    str_in = fsrc.read().decode(encoding)
    str_out = ' '.join(str_in.split())
    fdst.write(str_out.encode(encoding))


DEFAULT_PROCESSORS = {
    'css': _minify_css,
    'htm': _minify_html,
    'html': _minify_html,
    'js': _minify_js,
    'mjs': _minify_js,
}


def _filter_file(file, exclude_files=None):
    for exclude in arg_to_iter(exclude_files):
        if isinstance(exclude, str):
            if file == exclude:
                return False
        elif exclude.match(file):
            return False
    return True


def _walk_files(path, exclude_files=None):
    exclude_files = tuple(arg_to_iter(exclude_files))
    filter_file = partial(_filter_file, exclude_files=exclude_files) if exclude_files else None
    for curr_dir, _, files in os.walk(path):
        for file in filter(filter_file, files):
            yield os.path.join(curr_dir, file)


def minify(src, dst, exclude_files=None, file_processors=None):
    ''' copy file from src to dst and minify web files along the way '''

    LOGGER.info('copying files in <%s> to <%s>', src, dst)

    file_processors = DEFAULT_PROCESSORS if file_processors is None else file_processors
    prefix = os.path.join(src, '')

    for src_path in _walk_files(src, exclude_files):
        assert src_path.startswith(prefix)

        dst_path = os.path.join(dst, src_path[len(prefix):])
        dst_dir, dst_file = os.path.split(dst_path)
        os.makedirs(dst_dir, exist_ok=True)

        _, ext = os.path.splitext(dst_file)
        ext = ext[1:].lower() if ext else None
        processor = file_processors.get(ext, copyfileobj)

        LOGGER.debug('copying file <%s> to <%s> using processor %r', src_path, dst_path, processor)

        with open(src_path, 'rb') as fsrc, open(dst_path, 'wb') as fdst:
            processor(fsrc, fdst)


class Command(BaseCommand):
    ''' Minify static files '''

    help = 'Minify static files'

    def add_arguments(self, parser):
        parser.add_argument('source', help='source path')
        parser.add_argument('destination', help='destination path')
        parser.add_argument(
            '--delete', '-d', action='store_true', help='delete destination before copying')
        parser.add_argument('--exclude', '-e', nargs='+', help='exclude these file names')
        parser.add_argument(
            '--exclude-dot', '-E', action='store_true',
            help='exclude dot (hidden and system) files')

    def handle(self, *args, **kwargs):
        logging.basicConfig(
            stream=sys.stderr,
            level=logging.DEBUG if kwargs['verbosity'] > 1 else logging.INFO,
            format='%(asctime)s %(levelname)-8.8s [%(name)s:%(lineno)s] %(message)s',
        )

        LOGGER.info(kwargs)

        if kwargs['delete']:
            LOGGER.info('deleting destination dir <%s>', kwargs['destination'])
            rmtree(kwargs['destination'], ignore_errors=True)

        exclude = tuple(arg_to_iter(kwargs['exclude']))
        exclude = exclude + (re.compile(r'^\.'),) if kwargs['exclude_dot'] else exclude

        LOGGER.info('excluding files: %s', exclude)

        minify(
            src=kwargs['source'],
            dst=kwargs['destination'],
            exclude_files=exclude,
            file_processors=DEFAULT_PROCESSORS,
        )
