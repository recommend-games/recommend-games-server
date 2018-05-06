# -*- coding: utf-8 -*-

''' views '''

from __future__ import absolute_import, division, print_function, unicode_literals, with_statement

import logging

from django.conf import settings
from rest_framework.decorators import list_route # detail_route
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .models import Game
from .serializers import GameSerializer
from ..recommend import GamesRecommender


class GameViewSet(ModelViewSet):
    ''' game view set '''

    # pylint: disable=no-member
    queryset = Game.objects.all()
    serializer_class = GameSerializer

    logger = logging.getLogger('GameViewSet')

    def __init__(self, *args, **kwargs):
        super(GameViewSet, self).__init__(*args, **kwargs)

        recommender_path = getattr(settings, 'RECOMMENDER_PATH', None)

        if recommender_path:
            self.logger.info('loading games recommender from <%s>', recommender_path)

            try:
                self.recommender = GamesRecommender.load(recommender_path)
            except Exception as exc:
                self.logger.exception(exc)
                self.recommender = None
        else:
            self.recommender = None

        self.logger.info('loaded recommender: %r', self.recommender)

    @list_route()
    # pylint: disable=unused-argument
    def recommend(self, request, *args, **kwargs):
        ''' recommend games '''

        if self.recommender is None:
            return Response([])

        recommendation = self.recommender.recommend(
            num_games=10,
            ascending=True,
        )

        self.logger.info(recommendation)
        self.logger.info(recommendation['bgg_id'])

        games = self.get_queryset().filter(bgg_id__in=recommendation['bgg_id'])
        serializer = self.get_serializer(instance=games, many=True)
        return Response(serializer.data)
