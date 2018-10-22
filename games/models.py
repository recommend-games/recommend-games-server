# -*- coding: utf-8 -*-

''' models '''

from django.db.models import (
    BooleanField, CharField, DateTimeField, FloatField, ManyToManyField, Model,
    PositiveIntegerField, PositiveSmallIntegerField, SmallIntegerField, TextField, URLField)
from django.utils import timezone


class Game(Model):
    ''' game model '''

    bgg_id = PositiveIntegerField(primary_key=True)
    name = CharField(max_length=255)
    # alt_name = ListField(CharField(), blank=True)
    year = SmallIntegerField(blank=True, null=True)
    description = TextField(blank=True, null=True)

    designer = ManyToManyField('Person', blank=True, related_name='designer_for')
    artist = ManyToManyField('Person', blank=True, related_name='artist_for')
    # publisher = ListField(CharField(), blank=True)

    url = URLField(blank=True, null=True)
    # image_url = ListField(URLField(), blank=True)
    # video_url = ListField(URLField(), blank=True)
    # external_link = ListField(URLField(), blank=True)
    # list_price = CharField(max_length=100, blank=True, null=True)

    min_players = PositiveSmallIntegerField(blank=True, null=True)
    max_players = PositiveSmallIntegerField(blank=True, null=True)
    min_players_rec = PositiveSmallIntegerField(blank=True, null=True)
    max_players_rec = PositiveSmallIntegerField(blank=True, null=True)
    min_players_best = PositiveSmallIntegerField(blank=True, null=True)
    max_players_best = PositiveSmallIntegerField(blank=True, null=True)
    min_age = PositiveSmallIntegerField(blank=True, null=True)
    max_age = PositiveSmallIntegerField(blank=True, null=True)
    min_age_rec = FloatField(blank=True, null=True)
    max_age_rec = FloatField(blank=True, null=True)
    min_time = PositiveSmallIntegerField(blank=True, null=True)
    max_time = PositiveSmallIntegerField(blank=True, null=True)

    # category = ListField(CharField(), blank=True)
    # mechanic = ListField(CharField(), blank=True)
    cooperative = BooleanField(default=False)
    compilation = BooleanField(default=False)
    # family = ListField(CharField(), blank=True)
    # expansion = ListField(CharField(), blank=True)
    implementation = ManyToManyField(
        'self', symmetrical=False, blank=True, related_name='implemented_by')

    rank = PositiveIntegerField(blank=True, null=True)
    num_votes = PositiveIntegerField(default=0)
    avg_rating = FloatField(blank=True, null=True)
    stddev_rating = FloatField(blank=True, null=True)
    bayes_rating = FloatField(blank=True, null=True)

    complexity = FloatField(blank=True, null=True)
    language_dependency = FloatField(blank=True, null=True)

    scraped_at = DateTimeField(default=timezone.now)
    created_at = DateTimeField(auto_now_add=True)
    modified_at = DateTimeField(auto_now=True)

    class Meta:
        ''' meta '''
        ordering = ('rank',)

    def __str__(self):
        return self.name


class Person(Model):
    ''' person model '''

    name = CharField(max_length=255)

    created_at = DateTimeField(auto_now_add=True)
    modified_at = DateTimeField(auto_now=True)
