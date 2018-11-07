# -*- coding: utf-8 -*-

''' views '''

from functools import lru_cache

from django.conf import settings
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .models import Game, Person
from .serializers import GameSerializer, PersonSerializer


@lru_cache(maxsize=32)
def _load_model(path):
    if not path:
        return None
    try:
        from ludoj_recommender import GamesRecommender
        return GamesRecommender.load(path=path)
    except Exception:
        pass
    return None


class GameViewSet(ModelViewSet):
    ''' game view set '''

    # pylint: disable=no-member
    queryset = Game.objects.all()
    ordering = (
        '-rec_rating',
        '-bayes_rating',
    )
    serializer_class = GameSerializer
    filter_backends = (
        DjangoFilterBackend,
        OrderingFilter,
        SearchFilter,
    )
    filterset_fields = (
        'year',
        'designer',
        'artist',
        'min_players',
        'max_players',
        'min_players_rec',
        'max_players_rec',
        'min_players_best',
        'max_players_best',
        'min_age',
        'max_age',
        'min_age_rec',
        'max_age_rec',
        'min_time',
        'max_time',
        'cooperative',
        'compilation',
        'implementation_of',
        'bgg_rank',
        'num_votes',
        'avg_rating',
        'bayes_rating',
        'rec_rank',
        'rec_rating',
        'complexity',
        'language_dependency',
    )
    ordering_fields = (
        'year',
        'min_players',
        'max_players',
        'min_players_rec',
        'max_players_rec',
        'min_players_best',
        'max_players_best',
        'min_age',
        'max_age',
        'min_age_rec',
        'max_age_rec',
        'min_time',
        'max_time',
        'bgg_rank',
        'num_votes',
        'avg_rating',
        'bayes_rating',
        'rec_rank',
        'rec_rating',
        'complexity',
        'language_dependency',
    )
    search_fields = (
        'name',
    )

    @action(detail=False)
    def recommend(self, request):
        ''' recommend games '''

        user = request.query_params.get('user')

        if not user:
            return self.list(request)

        path = getattr(settings, 'RECOMMENDER_PATH', None)
        recommender = _load_model(path)

        if recommender is None or user not in recommender.known_users:
            return self.list(request)

        # TODO speed up recommendation by pre-computing known games, clusters etc

        recommendation = recommender.recommend(users=(user,))

        # TODO make filtering and pagination work together
        page = self.paginate_queryset(recommendation)
        if page is None:
            recommendation = recommendation[:10]
            paginate = False
        else:
            recommendation = page
            paginate = True

        recommendation = {game['bgg_id']: game for game in recommendation}

        games = self.filter_queryset(self.get_queryset()).filter(bgg_id__in=recommendation)

        for game in games:
            rec = recommendation[game.bgg_id]
            game.rec_rank = rec['rank']
            game.rec_rating = rec['score']

        serializer = self.get_serializer(
            instance=sorted(games, key=lambda game: (game.rec_rank, -game.rec_rating)),
            many=True,
        )

        return (
            self.get_paginated_response(serializer.data) if paginate
            else Response(serializer.data)
        )


class PersonViewSet(ModelViewSet):
    ''' person view set '''

    # pylint: disable=no-member
    queryset = Person.objects.all()
    serializer_class = PersonSerializer
