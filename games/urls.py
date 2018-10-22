# -*- coding: utf-8 -*-

''' URLs '''

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import GameViewSet

ROUTER = DefaultRouter()
ROUTER.register(r'games', GameViewSet)

# pylint: disable=invalid-name
urlpatterns = [
    path('', include(ROUTER.urls)),
]
