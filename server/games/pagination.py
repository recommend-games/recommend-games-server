# -*- coding: utf-8 -*-

'''paginator'''

from __future__ import absolute_import, division, print_function, unicode_literals, with_statement

from djangae.contrib.pagination import Paginator as DjangaePaginator
from rest_framework.pagination import PageNumberPagination

class GaePageNumberPagination(PageNumberPagination):
    ''' paginator '''

    django_paginator_class = DjangaePaginator
    page_size_query_param = 'page_size'
    max_page_size = 50
