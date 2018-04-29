# -*- coding: utf-8 -*-

''' serializers '''

from __future__ import absolute_import, division, print_function, unicode_literals, with_statement

from rest_framework.serializers import (
    CharField, ListField, ModelSerializer, PrimaryKeyRelatedField, URLField)

from .models import Game


class GameSerializer(ModelSerializer):
    ''' game serializer '''

    alt_name = ListField(child=CharField(), default=list)
    designer = ListField(child=CharField(), default=list)
    artist = ListField(child=CharField(), default=list)
    publisher = ListField(child=CharField(), default=list)
    image_url = ListField(child=URLField(), default=list)
    video_url = ListField(child=URLField(), default=list)
    external_link = ListField(child=URLField(), default=list)
    category = ListField(child=CharField(), default=list)
    mechanic = ListField(child=CharField(), default=list)
    family = ListField(child=CharField(), default=list)
    expansion = ListField(child=CharField(), default=list)
    # pylint: disable=no-member
    implementation = PrimaryKeyRelatedField(
        queryset=Game.objects.all(), many=True, required=False)

    class Meta(object):
        ''' meta '''
        model = Game
        fields = '__all__'
        read_only_fields = ('created_at', 'modified_at')
