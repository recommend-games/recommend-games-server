# -*- coding: utf-8 -*-

''' serializers '''

from __future__ import absolute_import, division, print_function, unicode_literals, with_statement

from rest_framework.serializers import ModelSerializer, PrimaryKeyRelatedField, StringRelatedField

from .models import Collection, Game, Person, User


class GameSerializer(ModelSerializer):
    ''' game serializer '''

    designer_name = StringRelatedField(source='designer', many=True, read_only=True)
    artist_name = StringRelatedField(source='artist', many=True, read_only=True)
    implemented_by = PrimaryKeyRelatedField(many=True, read_only=True)

    class Meta:
        ''' meta '''
        model = Game
        fields = '__all__'


class PersonSerializer(ModelSerializer):
    ''' person serializer '''

    class Meta:
        ''' meta '''
        model = Person
        fields = '__all__'


class CollectionSerializer(ModelSerializer):
    ''' collection serializer '''

    game_name = StringRelatedField(source='game', read_only=True)

    class Meta:
        ''' meta '''
        model = Collection
        fields = '__all__'


class UserSerializer(ModelSerializer):
    ''' user serializer '''

    games = CollectionSerializer(source='collection_set', many=True, read_only=True)

    class Meta:
        ''' meta '''
        model = User
        fields = '__all__'
