# -*- coding: utf-8 -*-

''' serializers '''

from __future__ import absolute_import, division, print_function, unicode_literals, with_statement

from rest_framework.serializers import ModelSerializer, PrimaryKeyRelatedField, StringRelatedField

from .models import Game, Person


class PersonSerializer(ModelSerializer):
    ''' person serializer '''

    class Meta:
        ''' meta '''
        model = Person
        exclude = ('created_at', 'modified_at')


class GameSerializer(ModelSerializer):
    ''' game serializer '''

    designer_name = StringRelatedField(source='designer', many=True, read_only=True)
    artist_name = StringRelatedField(source='artist', many=True, read_only=True)
    implemented_by = PrimaryKeyRelatedField(many=True, read_only=True)

    class Meta:
        ''' meta '''
        model = Game
        exclude = ('scraped_at', 'created_at', 'modified_at')
