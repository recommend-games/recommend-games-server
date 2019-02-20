#!/usr/bin/env python
# -*- coding: utf-8 -*-

''' pynt build file '''

from pynt import task
from pyntcontrib import execute


@task()
def test(*args, **kwargs):
    ''' stupid test command '''
    print(args)
    print(kwargs)


__DEFAULT__ = execute
