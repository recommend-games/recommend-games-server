# -*- coding: utf-8 -*-

'''models'''

from __future__ import absolute_import, division, print_function, unicode_literals, with_statement

# import hashlib
import logging
# import time

# pylint: disable=redefined-builtin
# from builtins import int, map, range, str
# from collections import defaultdict
# from datetime import datetime, timedelta
# from io import BytesIO

# import requests

# from django.conf import settings
# from django.core.files.images import ImageFile
from django.db import models
from django.utils import timezone
# from django.utils.crypto import random
from djangae import fields # storage
# from djangae.contrib.gauth_datastore.models import GaeDatastoreUser
from djangae.contrib.pagination import paginated_model
# from djangae.db.consistency import ensure_instance_consistent
from future.utils import python_2_unicode_compatible
# from gcm import GCM
# from rest_framework import serializers
# from rest_framework.exceptions import ValidationError
# from six import iteritems, itervalues

# GCM_SENDER = GCM(settings.GCM_API_KEY, debug=settings.DEBUG)
LOGGER = logging.getLogger(__name__)
# PUBSUB_SENDER = PubSubSender()
# STORAGE = storage.CloudStorage(bucket='diris-app.appspot.com', google_acl='public-read')


@paginated_model(orderings=('rank',))
@python_2_unicode_compatible
class Game(models.Model):
    ''' game '''

    bgg_id = models.PositiveIntegerField(primary_key=True)

    name = fields.CharField()
    alt_name = fields.ListField(fields.CharField())
    year = models.SmallIntegerField()
    description = fields.CharField()

    designer = fields.ListField(fields.CharField())
    artist = fields.ListField(fields.CharField())
    publisher = fields.ListField(fields.CharField())

    url = models.URLField()
    image_url = fields.ListField(models.URLField())
    video_url = fields.ListField(models.URLField())
    external_link = fields.ListField(models.URLField())
    list_price = fields.CharField()

    min_players = models.PositiveSmallIntegerField()
    max_players = models.PositiveSmallIntegerField()
    min_players_rec = models.PositiveSmallIntegerField()
    max_players_rec = models.PositiveSmallIntegerField()
    min_players_best = models.PositiveSmallIntegerField()
    max_players_best = models.PositiveSmallIntegerField()
    min_age = models.PositiveSmallIntegerField()
    max_age = models.PositiveSmallIntegerField()
    min_age_rec = models.FloatField()
    max_age_rec = models.FloatField()
    min_time = models.PositiveSmallIntegerField()
    max_time = models.PositiveSmallIntegerField()

    category = fields.ListField(fields.CharField())
    mechanic = fields.ListField(fields.CharField())
    cooperative = models.BooleanField()
    compilation = models.BooleanField()
    family = fields.ListField(fields.CharField())
    expansion = fields.ListField(fields.CharField())
    implementation = fields.RelatedSetField('Game', related_name='implemented_by')

    rank = models.PositiveIntegerField()
    num_votes = models.PositiveIntegerField()
    avg_rating = models.FloatField()
    stddev_rating = models.FloatField()
    bayes_rating = models.FloatField()

    complexity = models.FloatField()
    language_dependency = models.FloatField()

    scraped_at = models.DateTimeField(default=timezone.now)
    created = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)

    class Meta(object):
        ''' meta '''
        ordering = ('rank',)
