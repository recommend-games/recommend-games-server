# -*- coding: utf-8 -*-

''' URLs '''

from __future__ import absolute_import, division, print_function, unicode_literals, with_statement

from django.conf.urls import url, include
from rest_framework.routers import DefaultRouter

from .views import GameViewSet

# Create a router and register our viewsets with it.
# pylint: disable=invalid-name
router = DefaultRouter()
router.register(r'games', GameViewSet)

urlpatterns = [
    url(r'^', include(router.urls)),
]
