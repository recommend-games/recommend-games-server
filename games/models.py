# -*- coding: utf-8 -*-

''' models '''

from django.db.models import (
    BooleanField, CharField, DateTimeField, FloatField, Index, ManyToManyField, Model,
    PositiveIntegerField, PositiveSmallIntegerField, SmallIntegerField, TextField, URLField)
from django.utils import timezone


class Game(Model):
    ''' game model '''

    bgg_id = PositiveIntegerField(primary_key=True)
    name = CharField(max_length=255, db_index=True)
    # alt_name = ListField(CharField(), blank=True)
    year = SmallIntegerField(blank=True, null=True, db_index=True)
    description = TextField(blank=True, null=True)

    designer = ManyToManyField('Person', blank=True, related_name='designer_of')
    artist = ManyToManyField('Person', blank=True, related_name='artist_of')
    # publisher = ListField(CharField(), blank=True)

    url = URLField(blank=True, null=True)
    # image_url = ListField(URLField(), blank=True)
    # video_url = ListField(URLField(), blank=True)
    # external_link = ListField(URLField(), blank=True)
    # list_price = CharField(max_length=100, blank=True, null=True)

    min_players = PositiveSmallIntegerField(blank=True, null=True, db_index=True)
    max_players = PositiveSmallIntegerField(blank=True, null=True, db_index=True)
    min_players_rec = PositiveSmallIntegerField(blank=True, null=True, db_index=True)
    max_players_rec = PositiveSmallIntegerField(blank=True, null=True, db_index=True)
    min_players_best = PositiveSmallIntegerField(blank=True, null=True, db_index=True)
    max_players_best = PositiveSmallIntegerField(blank=True, null=True, db_index=True)
    min_age = PositiveSmallIntegerField(blank=True, null=True, db_index=True)
    max_age = PositiveSmallIntegerField(blank=True, null=True, db_index=True)
    min_age_rec = FloatField(blank=True, null=True, db_index=True)
    max_age_rec = FloatField(blank=True, null=True, db_index=True)
    min_time = PositiveSmallIntegerField(blank=True, null=True, db_index=True)
    max_time = PositiveSmallIntegerField(blank=True, null=True, db_index=True)

    # category = ListField(CharField(), blank=True)
    # mechanic = ListField(CharField(), blank=True)
    cooperative = BooleanField(default=False, db_index=True)
    compilation = BooleanField(default=False, db_index=True)
    # family = ListField(CharField(), blank=True)
    # expansion = ListField(CharField(), blank=True)
    implementation_of = ManyToManyField(
        'self', symmetrical=False, blank=True, related_name='implemented_by')

    bgg_rank = PositiveIntegerField(blank=True, null=True, db_index=True)
    num_votes = PositiveIntegerField(default=0, db_index=True)
    avg_rating = FloatField(blank=True, null=True, db_index=True)
    stddev_rating = FloatField(blank=True, null=True, db_index=True)
    bayes_rating = FloatField(blank=True, null=True, db_index=True)

    rec_rank = PositiveIntegerField(blank=True, null=True, db_index=True)
    rec_rating = FloatField(blank=True, null=True, db_index=True)

    complexity = FloatField(blank=True, null=True, db_index=True)
    language_dependency = FloatField(blank=True, null=True, db_index=True)

    scraped_at = DateTimeField(default=timezone.now, db_index=True)
    created_at = DateTimeField(auto_now_add=True, editable=False, db_index=True)
    modified_at = DateTimeField(auto_now=True, editable=False, db_index=True)

    class Meta:
        ''' meta '''
        ordering = ('-rec_rating', '-bayes_rating')
        indexes = (Index(fields=('-rec_rating', '-bayes_rating')),)

    def __str__(self):
        return self.name


class Person(Model):
    ''' person model '''

    name = CharField(max_length=255, db_index=True)

    created_at = DateTimeField(auto_now_add=True, editable=False, db_index=True)
    modified_at = DateTimeField(auto_now=True, editable=False, db_index=True)

    def __str__(self):
        return self.name
