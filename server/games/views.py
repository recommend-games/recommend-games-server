# -*- coding: utf-8 -*-

'''views'''

from __future__ import absolute_import, unicode_literals

# import json
import logging
# import os.path

# from base64 import b64decode

# pylint: disable=redefined-builtin
# from builtins import str
# from django.conf import settings
# from django.contrib.auth import login
# from django.db.models import Q
# from django.utils.crypto import get_random_string, random
# from djangae.contrib.gauth_datastore.models import GaeDatastoreUser
# from djangae.contrib.pagination import Paginator
# pylint: disable=import-error
# from google.appengine.api.mail import send_mail
from rest_framework import viewsets # mixins, permissions, status, views
# from rest_framework.decorators import detail_route, list_route
# from rest_framework.exceptions import ValidationError, NotAuthenticated, NotFound
# from rest_framework.response import Response
# from rest_framework.parsers import FileUploadParser, MultiPartParser
# from rest_framework_jwt.settings import api_settings
# from six import itervalues, raise_from, string_types

from .models import Game
from .serializers import GameSerializer
# from .utils import calculate_id, get_player, merge, normalize_space, random_string

LOGGER = logging.getLogger(__name__)


class GameViewSet(viewsets.ModelViewSet):
    ''' game view set '''

    # pylint: disable=no-member
    queryset = Game.objects.all()
    # permission_classes = (IsOwnerOrCreateAndRead,)
    serializer_class = GameSerializer
    ordering = ('rank',)
