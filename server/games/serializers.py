# -*- coding: utf-8 -*-

'''serializers'''

from __future__ import absolute_import, unicode_literals

import logging
# import re

# pylint: disable=redefined-builtin
# from builtins import str, zip
from rest_framework import serializers
# from rest_framework.exceptions import ValidationError
# from rest_framework.validators import UniqueValidator
# from django.utils.crypto import random
# from djangae.contrib.gauth_datastore.models import GaeDatastoreUser

from .models import Game

LOGGER = logging.getLogger(__name__)


class GameSerializer(serializers.ModelSerializer):
    ''' game serializer '''

    class Meta(object):
        ''' meta '''
        model = Game
        fields = (
            'bgg_id',
            'name',
            'alt_name',
            'year',
            'description',
            'designer',
            'artist',
            'publisher',
            'url',
            'image_url',
            'video_url',
            'external_link',
            'list_price',
            'min_players',
            'max_players',
            'min_players_rec',
            'max_players_rec',
            'min_players_best',
            'max_players_best',
            'min_age',
            'max_age',
            'min_age_rec',
            'max_age_rec',
            'min_time',
            'max_time',
            'category',
            'mechanic',
            'cooperative',
            'compilation',
            'family',
            'expansion',
            'implementation',
            'rank',
            'num_votes',
            'avg_rating',
            'stddev_rating',
            'bayes_rating',
            'complexity',
            'language_dependency',
            'scraped_at',
            'created',
            'last_modified',
        )
        # read_only_fields = ()
