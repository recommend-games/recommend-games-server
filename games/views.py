# -*- coding: utf-8 -*-

''' views '''

import json
import logging

from functools import lru_cache, reduce
from operator import or_

from django.conf import settings
from django.db.models import Q
from django_filters import FilterSet
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.exceptions import NotAuthenticated, MethodNotAllowed, PermissionDenied
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .models import Collection, Game, Person, User
from .permissions import ReadOnly
from .serializers import CollectionSerializer, GameSerializer, PersonSerializer, UserSerializer
from .utils import arg_to_iter, load_recommender, parse_bool, parse_int, take_first

LOGGER = logging.getLogger(__name__)


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
def _exclude(user=None, other=None):
    try:
        import turicreate as tc
    except ImportError:
        LOGGER.exception('unable to import <turicreate>')
        return None

    ids = _compilation_ids()

    if other is not None:
        other = (
            other if isinstance(other, tc.SArray)
            else tc.SArray(tuple(arg_to_iter(other)), dtype=int))
        ids = ids.append(other) if ids is not None else other
        del other

    # pylint: disable=len-as-condition
    if ids is None or not len(ids):
        return None

    sframe = tc.SFrame({'bgg_id': ids})
    sframe['bgg_user_name'] = user

    del tc, ids

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

    collection_fields = (
        'owned',
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
        recommender = load_recommender(path)

        if recommender is None or user not in recommender.known_users:
            return self.list(request)

        # TODO speed up recommendation by pre-computing known games, clusters etc (#16)

        params = dict(request.query_params)
        params.setdefault('exclude_known', True)
        params.pop('ordering', None)
        params.pop('page', None)
        params.pop('user', None)

        exclude_known = parse_bool(take_first(params.pop('exclude_known', None)))
        exclude_fields = [
            field for field in self.collection_fields
            if parse_bool(take_first(params.pop(f'exclude_{field}', None)))]
        exclude_wishlist = parse_int(take_first(params.pop('exclude_wishlist', None)))
        exclude_play_count = parse_int(take_first(params.pop('exclude_play_count', None)))
        exclude_clusters = parse_bool(take_first(params.pop('exclude_clusters', None)))

        fqs = self.filter_queryset(self.get_queryset())
        # we should only need this if params are set, but see #90
        games = frozenset(
            fqs.order_by().values_list('bgg_id', flat=True)) & recommender.rated_games
        percentiles = getattr(settings, 'STAR_PERCENTILES', None)

        try:
            collection = User.objects.get(name__iexact=user).collection_set.order_by()
            queries = [Q(**{field: True}) for field in exclude_fields]
            if exclude_wishlist:
                queries.append(Q(wishlist__lte=exclude_wishlist))
            if exclude_play_count:
                queries.append(Q(play_count__gte=exclude_play_count))
            if queries:
                query = reduce(or_, queries)
                exclude = tuple(collection.filter(query).values_list('game_id', flat=True))
            else:
                exclude = None
            del collection, queries
        except Exception:
            exclude = None

        recommendation = recommender.recommend(
            users=(user,),
            games=games,
            exclude=_exclude(user, other=exclude),
            exclude_known=exclude_known,
            exclude_clusters=exclude_clusters,
            star_percentiles=percentiles,
        )
        del user, path, params, percentiles, recommender, exclude, games

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

    def get_permissions(self):
        cls = ReadOnly if settings.READ_ONLY else AllowAny
        return (cls(),)

    def handle_exception(self, exc):
        if settings.READ_ONLY and isinstance(exc, (NotAuthenticated, PermissionDenied)):
            exc = MethodNotAllowed(self.request.method)
        return super().handle_exception(exc)


class UserViewSet(ModelViewSet):
    ''' user view set '''

    # pylint: disable=no-member
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_permissions(self):
        cls = AllowAny if settings.DEBUG else IsAuthenticated
        return (cls(),)


class CollectionViewSet(ModelViewSet):
    ''' user view set '''

    # pylint: disable=no-member
    queryset = Collection.objects.all()
    serializer_class = CollectionSerializer

    def get_permissions(self):
        cls = AllowAny if settings.DEBUG else IsAuthenticated
        return (cls(),)
