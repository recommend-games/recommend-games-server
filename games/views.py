# -*- coding: utf-8 -*-

''' views '''

import json
import logging

from functools import lru_cache

from django.conf import settings
from django_filters import FilterSet
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.exceptions import NotAuthenticated, MethodNotAllowed, PermissionDenied
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .models import Collection, Game, Person, User
from .permissions import ReadOnly
from .serializers import CollectionSerializer, GameSerializer, PersonSerializer, UserSerializer

LOGGER = logging.getLogger(__name__)


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


@lru_cache(maxsize=8)
def _compilation_ids():
    try:
        import turicreate as tc
    except ImportError:
        LOGGER.exception('unable to import <turicreate>')
        return None

    compilations_path = getattr(settings, 'COMPILATIONS_PATH', None)

    if compilations_path:
        try:
            with open(compilations_path) as compilations_file:
                ids = json.load(compilations_file)
            return tc.SArray(data=ids, dtype=int)
        except Exception:
            pass

    try:
        # pylint: disable=no-member
        ids = list(
            Game.objects.all()
            .filter(compilation=True)
            .values_list('bgg_id', flat=True))
        if compilations_path:
            with open(compilations_path, 'w') as compilations_file:
                json.dump(ids, compilations_file, separators=(',', ':'))
        return tc.SArray(data=ids, dtype=int)
    except Exception:
        LOGGER.exception('unable to fetch or write compilation IDs')

    return None


@lru_cache(maxsize=8)
def _compilations(user=None):
    try:
        import turicreate as tc
    except ImportError:
        LOGGER.exception('unable to import <turicreate>')
        return None

    compilations = _compilation_ids()
    if compilations is None:
        return None

    sframe = tc.SFrame({'bgg_id': compilations})
    sframe['bgg_user_name'] = user

    del tc, compilations

    return sframe


class GameFilter(FilterSet):
    ''' game filter '''
    class Meta:
        ''' meta '''
        model = Game
        fields = {
            'year': ['exact', 'gt', 'gte', 'lt', 'lte'],
            'designer': ['exact',],
            'designer__name': ['exact', 'iexact'],
            'artist': ['exact',],
            'artist__name': ['exact', 'iexact'],
            'min_players': ['exact', 'gt', 'gte', 'lt', 'lte'],
            'max_players': ['exact', 'gt', 'gte', 'lt', 'lte'],
            'min_players_rec': ['exact', 'gt', 'gte', 'lt', 'lte'],
            'max_players_rec': ['exact', 'gt', 'gte', 'lt', 'lte'],
            'min_players_best': ['exact', 'gt', 'gte', 'lt', 'lte'],
            'max_players_best': ['exact', 'gt', 'gte', 'lt', 'lte'],
            'min_age': ['exact', 'gt', 'gte', 'lt', 'lte'],
            'max_age': ['exact', 'gt', 'gte', 'lt', 'lte'],
            'min_age_rec': ['exact', 'gt', 'gte', 'lt', 'lte'],
            'max_age_rec': ['exact', 'gt', 'gte', 'lt', 'lte'],
            'min_time': ['exact', 'gt', 'gte', 'lt', 'lte'],
            'max_time': ['exact', 'gt', 'gte', 'lt', 'lte'],
            'cooperative': ['exact',],
            'compilation': ['exact',],
            'implements': ['exact',],
            'bgg_rank': ['exact', 'gt', 'gte', 'lt', 'lte'],
            'num_votes': ['exact', 'gt', 'gte', 'lt', 'lte'],
            'avg_rating': ['exact', 'gt', 'gte', 'lt', 'lte'],
            'bayes_rating': ['exact', 'gt', 'gte', 'lt', 'lte'],
            'rec_rank': ['exact', 'gt', 'gte', 'lt', 'lte'],
            'rec_rating': ['exact', 'gt', 'gte', 'lt', 'lte'],
            'complexity': ['exact', 'gt', 'gte', 'lt', 'lte'],
            'language_dependency': ['exact', 'gt', 'gte', 'lt', 'lte'],
        }


class GameViewSet(ModelViewSet):
    ''' game view set '''

    # pylint: disable=no-member
    queryset = Game.objects.all()
    ordering = (
        '-rec_rating',
        '-bayes_rating',
        '-avg_rating',
    )
    serializer_class = GameSerializer
    filter_backends = (
        DjangoFilterBackend,
        OrderingFilter,
        SearchFilter,
    )
    filterset_class = GameFilter
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

    def get_permissions(self):
        cls = ReadOnly if settings.READ_ONLY else AllowAny
        return (cls(),)

    def handle_exception(self, exc):
        if settings.READ_ONLY and isinstance(exc, (NotAuthenticated, PermissionDenied)):
            exc = MethodNotAllowed(self.request.method)
        return super().handle_exception(exc)

    @action(detail=False)
    def recommend(self, request):
        ''' recommend games '''

        user = request.query_params.get('user')

        if not user:
            return self.list(request)

        user = user.lower()
        path = getattr(settings, 'RECOMMENDER_PATH', None)
        recommender = _load_model(path)

        if recommender is None or user not in recommender.known_users:
            return self.list(request)

        # TODO speed up recommendation by pre-computing known games, clusters etc (#16)

        params = dict(request.query_params)
        params.pop('ordering', None)
        params.pop('page', None)
        params.pop('user', None)

        fqs = self.filter_queryset(self.get_queryset())
        games = list(fqs.values_list('bgg_id', flat=True)) if params else None
        percentiles = getattr(settings, 'STAR_PERCENTILES', None)
        recommendation = recommender.recommend(
            users=(user,),
            games=games,
            exclude=_compilations(user),
            exclude_clusters=False,
            star_percentiles=percentiles,
        )
        del user, path, params, percentiles, recommender

        page = self.paginate_queryset(recommendation)
        if page is None:
            recommendation = recommendation[:10]
            paginate = False
        else:
            recommendation = page
            paginate = True
        del page

        recommendation = {game['bgg_id']: game for game in recommendation}
        games = fqs.filter(bgg_id__in=recommendation)
        for game in games:
            rec = recommendation[game.bgg_id]
            game.rec_rank = rec['rank']
            game.rec_rating = rec['score']
            game.rec_stars = rec.get('stars')
        del fqs, recommendation

        serializer = self.get_serializer(
            instance=sorted(games, key=lambda game: game.rec_rank),
            many=True,
        )
        del games

        return (
            self.get_paginated_response(serializer.data) if paginate
            else Response(serializer.data)
        )


class PersonViewSet(ModelViewSet):
    ''' person view set '''

    # pylint: disable=no-member
    queryset = Person.objects.all()
    serializer_class = PersonSerializer


class UserViewSet(ModelViewSet):
    ''' user view set '''

    # pylint: disable=no-member
    queryset = User.objects.all()
    serializer_class = UserSerializer


class CollectionViewSet(ModelViewSet):
    ''' user view set '''

    # pylint: disable=no-member
    queryset = Collection.objects.all()
    serializer_class = CollectionSerializer
