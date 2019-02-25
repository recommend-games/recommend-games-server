#!/usr/bin/env python
# -*- coding: utf-8 -*-

''' pynt build file '''

import os
import sys

import django

from dotenv import load_dotenv
from pynt import task

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv(verbose=True)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ludoj.settings')
os.environ.setdefault('PYTHONPATH', BASE_DIR)
sys.path.insert(0, BASE_DIR)
django.setup()


@task()
def command(cmd, *args, **kwargs):
    ''' execute Django command '''
    django.core.management.call_command(cmd, *args, **kwargs)


__DEFAULT__ = command
