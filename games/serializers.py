# -*- coding: utf-8 -*-

''' serializers '''

from __future__ import absolute_import, division, print_function, unicode_literals, with_statement

from rest_framework.serializers import ModelSerializer

from .models import Game, Person


class PersonSerializer(ModelSerializer):
    ''' person serializer '''

    class Meta:
        ''' meta '''
        model = Person
        fields = '__all__'


class GameSerializer(ModelSerializer):
    ''' game serializer '''

    # TODO improve on designer and artist relationship
    # e.g., use StringRelatedField, but add designer_id write only field

    class Meta:
        ''' meta '''
        model = Game
        fields = '__all__'
