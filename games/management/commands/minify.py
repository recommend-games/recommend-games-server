# -*- coding: utf-8 -*-

''' minify static files '''

import logging
import os
# import re
# import sys

from functools import partial
from shutil import copyfileobj

# from django.conf import settings
# from django.core.management.base import BaseCommand
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

        LOGGER.info('copying file <%s> to <%s> using processor %r', src_path, dst_path, processor)

        with open(src_path, 'rb') as fsrc, open(dst_path, 'wb') as fdst:
            processor(fsrc, fdst)
