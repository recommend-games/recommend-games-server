# -*- coding: utf-8 -*-

''' serializers '''

from __future__ import absolute_import, division, print_function, unicode_literals, with_statement

from rest_framework.serializers import ModelSerializer

from .models import Game


class GameSerializer(ModelSerializer):
    ''' game serializer '''

    class Meta(object):
        ''' meta '''
        model = Game
        fields = '__all__'
        read_only_fields = ('created_at', 'modified_at')
