# -*- coding: utf-8 -*-

''' models '''

from django.db.models import (
    CASCADE, BooleanField, CharField, FloatField, ForeignKey, Index, ManyToManyField, Model,
    PositiveIntegerField, PositiveSmallIntegerField, SmallIntegerField, TextField, URLField)


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
    image_url = URLField(blank=True, null=True) # should be list
    video_url = URLField(blank=True, null=True) # should be list
    external_link = URLField(blank=True, null=True) # should be list
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
    implements = ManyToManyField(
        'self', symmetrical=False, blank=True, related_name='implemented_by')

    bgg_rank = PositiveIntegerField(blank=True, null=True, db_index=True)
    num_votes = PositiveIntegerField(default=0, db_index=True)
    avg_rating = FloatField(blank=True, null=True, db_index=True)
    stddev_rating = FloatField(blank=True, null=True, db_index=True)
    bayes_rating = FloatField(blank=True, null=True, db_index=True)

    rec_rank = PositiveIntegerField(blank=True, null=True, db_index=True)
    rec_rating = FloatField(blank=True, null=True, db_index=True)
    rec_stars = FloatField(blank=True, null=True, db_index=True)

    complexity = FloatField(blank=True, null=True, db_index=True)
    language_dependency = FloatField(blank=True, null=True, db_index=True)

    class Meta:
        ''' meta '''
        ordering = (
            '-rec_rating',
            '-bayes_rating',
            '-avg_rating',
        )
        indexes = (
            Index(fields=('-rec_rating', '-bayes_rating', '-avg_rating')),
        )

    def __str__(self):
        return self.name


class Person(Model):
    ''' person model '''

    bgg_id = PositiveIntegerField(primary_key=True)
    name = CharField(max_length=255, db_index=True)

    class Meta:
        ''' meta '''
        ordering = (
            'name',
        )

    def __str__(self):
        return self.name


class User(Model):
    ''' user model '''

    name = CharField(primary_key=True, max_length=255)
    games = ManyToManyField(Game, through='Collection', blank=True)

    class Meta:
        ''' meta '''
        ordering = (
            'name',
        )

    def __str__(self):
        return self.name


class Collection(Model):
    ''' collection model '''

    game = ForeignKey(Game, on_delete=CASCADE)
    user = ForeignKey(User, on_delete=CASCADE)

    rating = FloatField(blank=True, null=True, db_index=True)
    owned = BooleanField(default=False, db_index=True)
    wishlist = PositiveSmallIntegerField(blank=True, null=True, db_index=True)
    play_count = PositiveIntegerField(default=0, db_index=True)

    class Meta:
        ''' meta '''
        indexes = (
            Index(fields=('user', 'owned')),
        )

    def __str__(self):
        # pylint: disable=no-member
        return f'{self.game_id}: {self.user_id}'
