# -*- coding: utf-8 -*-

''' views '''

import logging

from functools import reduce
from operator import or_

from django.conf import settings
from django.db.models import Q
from django_filters import FilterSet
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.exceptions import NotAuthenticated, NotFound, MethodNotAllowed, PermissionDenied
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .models import Category, Collection, Game, Mechanic, Person, User
from .permissions import ReadOnly
from .serializers import (
    CategorySerializer, CollectionSerializer, GameSerializer,
    MechanicSerializer, PersonSerializer, UserSerializer)
from .utils import arg_to_iter, load_recommender, parse_bool, parse_int, pubsub_push, take_first

LOGGER = logging.getLogger(__name__)


class PermissionsModelViewSet(ModelViewSet):
    ''' add permissions based on settings '''

    def get_permissions(self):
        cls = ReadOnly if settings.READ_ONLY else AllowAny
        return (cls(),)

    def handle_exception(self, exc):
        if settings.READ_ONLY and isinstance(exc, (NotAuthenticated, PermissionDenied)):
            exc = MethodNotAllowed(self.request.method)
        return super().handle_exception(exc)


def _exclude(user=None, ids=None):
    if ids is None:
        return None

    try:
        import turicreate as tc
    except ImportError:
        LOGGER.exception('unable to import <turicreate>')
        return None

    ids = (
        ids if isinstance(ids, tc.SArray)
        else tc.SArray(tuple(arg_to_iter(ids)), dtype=int))

    # pylint: disable=len-as-condition
    if ids is None or not len(ids):
        return None

    sframe = tc.SFrame({'bgg_id': ids})
    sframe['bgg_user_name'] = user

    del tc, ids

    return sframe


def _parse_ints(args):
    for arg in arg_to_iter(args):
        if isinstance(arg, int):
            yield arg
        elif isinstance(arg, str):
            for parsed in map(parse_int, arg.split(',')):
                if parsed is not None:
                    yield parsed
        elif isinstance(arg, (list, tuple)):
            yield from _parse_ints(arg)


class GameFilter(FilterSet):
    ''' game filter '''
    class Meta:
        ''' meta '''
        model = Game
        fields = {
            'year': ['exact', 'gt', 'gte', 'lt', 'lte', 'isnull'],
            'designer': ['exact',],
            'designer__name': ['exact', 'iexact'],
            'artist': ['exact',],
            'artist__name': ['exact', 'iexact'],
            'min_players': ['exact', 'gt', 'gte', 'lt', 'lte', 'isnull'],
            'max_players': ['exact', 'gt', 'gte', 'lt', 'lte', 'isnull'],
            'min_players_rec': ['exact', 'gt', 'gte', 'lt', 'lte', 'isnull'],
            'max_players_rec': ['exact', 'gt', 'gte', 'lt', 'lte', 'isnull'],
            'min_players_best': ['exact', 'gt', 'gte', 'lt', 'lte', 'isnull'],
            'max_players_best': ['exact', 'gt', 'gte', 'lt', 'lte', 'isnull'],
            'min_age': ['exact', 'gt', 'gte', 'lt', 'lte', 'isnull'],
            'max_age': ['exact', 'gt', 'gte', 'lt', 'lte', 'isnull'],
            'min_age_rec': ['exact', 'gt', 'gte', 'lt', 'lte', 'isnull'],
            'max_age_rec': ['exact', 'gt', 'gte', 'lt', 'lte', 'isnull'],
            'min_time': ['exact', 'gt', 'gte', 'lt', 'lte', 'isnull'],
            'max_time': ['exact', 'gt', 'gte', 'lt', 'lte', 'isnull'],
            'cooperative': ['exact',],
            'compilation': ['exact',],
            'implements': ['exact',],
            'bgg_rank': ['exact', 'gt', 'gte', 'lt', 'lte', 'isnull'],
            'num_votes': ['exact', 'gt', 'gte', 'lt', 'lte', 'isnull'],
            'avg_rating': ['exact', 'gt', 'gte', 'lt', 'lte', 'isnull'],
            'bayes_rating': ['exact', 'gt', 'gte', 'lt', 'lte', 'isnull'],
            'rec_rank': ['exact', 'gt', 'gte', 'lt', 'lte', 'isnull'],
            'rec_rating': ['exact', 'gt', 'gte', 'lt', 'lte', 'isnull'],
            'complexity': ['exact', 'gt', 'gte', 'lt', 'lte', 'isnull'],
            'language_dependency': ['exact', 'gt', 'gte', 'lt', 'lte', 'isnull'],
        }


class GameViewSet(PermissionsModelViewSet):
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

    def _excluded_games(self, user, params):
        params = params or {}
        params.setdefault('exclude_known', True)

        exclude_known = parse_bool(take_first(params.get('exclude_known')))
        exclude_fields = [
            field for field in self.collection_fields
            if parse_bool(take_first(params.get(f'exclude_{field}')))]
        exclude_wishlist = parse_int(take_first(params.get('exclude_wishlist')))
        exclude_play_count = parse_int(take_first(params.get('exclude_play_count')))
        exclude_clusters = parse_bool(take_first(params.get('exclude_clusters')))

        try:
            queries = [Q(**{field: True}) for field in exclude_fields]
            if exclude_known and exclude_clusters:
                queries.append(Q(rating__isnull=False))
            if exclude_wishlist:
                queries.append(Q(wishlist__lte=exclude_wishlist))
            if exclude_play_count:
                queries.append(Q(play_count__gte=exclude_play_count))
            if queries:
                query = reduce(or_, queries)
                return tuple(
                    User.objects.get(name=user)
                    .collection_set
                    .order_by()
                    .filter(query)
                    .values_list('game_id', flat=True))

        except Exception:
            pass

        return None

    def _recommend_rating(self, user, recommender, params):
        user = user.lower()
        if user not in recommender.known_users:
            raise NotFound(f'user <{user}> could not be found')

        # we should only need this if params are set, but see #90
        games = frozenset(
            self.filter_queryset(self.get_queryset())
            .order_by()
            .values_list('bgg_id', flat=True)) & recommender.rated_games

        if not games:
            return ()

        params = params or {}
        exclude = self._excluded_games(user, params)
        similarity_model = take_first(params.get('model')) == 'similarity'

        return recommender.recommend(
            users=(user,),
            games=games,
            similarity_model=similarity_model,
            exclude=_exclude(user, ids=exclude),
            exclude_known=parse_bool(take_first(params.get('exclude_known'))),
            exclude_clusters=parse_bool(take_first(params.get('exclude_clusters'))),
            star_percentiles=getattr(settings, 'STAR_PERCENTILES', None),
        )

    def _recommend_similar(self, like, recommender):
        like = list(_parse_ints(like))
        games = frozenset(
            self.filter_queryset(self.get_queryset())
            .order_by()
            .values_list('bgg_id', flat=True)) & recommender.rated_games

        if not games:
            return ()

        return recommender.recommend_similar(games=like, items=games)

    @action(detail=False)
    def recommend(self, request):
        ''' recommend games '''

        user = request.query_params.get('user')
        like = request.query_params.getlist('like')

        if not user and not like:
            return self.list(request)

        if settings.PUBSUB_PUSH_ENABLED and user:
            pubsub_push(user)

        path = getattr(settings, 'RECOMMENDER_PATH', None)
        recommender = load_recommender(path)

        if recommender is None:
            return self.list(request)

        recommendation = (
            self._recommend_rating(user, recommender, dict(request.query_params))
            if user else self._recommend_similar(like, recommender))

        del like, path, recommender

        page = self.paginate_queryset(recommendation)
        if page is None:
            recommendation = recommendation[:10]
            paginate = False
        else:
            recommendation = page
            paginate = True
        del page

        recommendation = {game['bgg_id']: game for game in recommendation}
        games = self.filter_queryset(self.get_queryset()).filter(bgg_id__in=recommendation)
        for game in games:
            rec = recommendation[game.bgg_id]
            game.rec_rank = rec['rank']
            game.rec_rating = rec['score'] if user else None
            game.rec_stars = rec.get('stars') if user else None
        del recommendation

        serializer = self.get_serializer(
            instance=sorted(games, key=lambda game: game.rec_rank),
            many=True,
        )
        del games

        return (
            self.get_paginated_response(serializer.data) if paginate
            else Response(serializer.data)
        )

    # pylint: disable=unused-argument,invalid-name
    @action(detail=True)
    def similar(self, request, pk=None):
        ''' find games similar to this game '''

        path = getattr(settings, 'RECOMMENDER_PATH', None)
        recommender = load_recommender(path)

        if recommender is None:
            raise NotFound(f'cannot find similar games to <{pk}>')

        games = recommender.similar_games(parse_int(pk), num_games=0)
        del recommender

        page = self.paginate_queryset(games)
        if page is None:
            games = games[:10]
            paginate = False
        else:
            games = page
            paginate = True
        del page

        games = {game['similar']: game for game in games}
        results = self.get_queryset().filter(bgg_id__in=games)
        for game in results:
            game.sort_rank = games[game.bgg_id]['rank']
        del games

        serializer = self.get_serializer(
            instance=sorted(results, key=lambda game: game.sort_rank),
            many=True,
        )
        del results

        return (
            self.get_paginated_response(serializer.data) if paginate
            else Response(serializer.data)
        )


class PersonViewSet(PermissionsModelViewSet):
    ''' person view set '''

    # pylint: disable=no-member
    queryset = Person.objects.all()
    serializer_class = PersonSerializer

    # pylint: disable=unused-argument,invalid-name
    @action(detail=True)
    def games(self, request, pk=None):
        ''' find all games for a person '''

        person = self.get_object()
        role = request.query_params.get('role')
        queryset = person.artist_of if role == 'artist' else person.designer_of
        queryset = self.filter_queryset(queryset.all())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = GameSerializer(page, many=True, context=self.get_serializer_context())
            return self.get_paginated_response(serializer.data)

        serializer = GameSerializer(queryset, many=True, context=self.get_serializer_context())
        return Response(serializer.data)


class CategoryViewSet(PermissionsModelViewSet):
    ''' category view set '''

    # pylint: disable=no-member
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

    # pylint: disable=unused-argument,invalid-name
    @action(detail=True)
    def games(self, request, pk=None):
        ''' find all games in a category '''

        category = self.get_object()
        queryset = self.filter_queryset(category.games.all())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = GameSerializer(page, many=True, context=self.get_serializer_context())
            return self.get_paginated_response(serializer.data)

        serializer = GameSerializer(queryset, many=True, context=self.get_serializer_context())
        return Response(serializer.data)


class MechanicViewSet(PermissionsModelViewSet):
    ''' mechanic view set '''

    # pylint: disable=no-member
    queryset = Mechanic.objects.all()
    serializer_class = MechanicSerializer

    # pylint: disable=unused-argument,invalid-name
    @action(detail=True)
    def games(self, request, pk=None):
        ''' find all games with a mechanic '''

        mechanic = self.get_object()
        queryset = self.filter_queryset(mechanic.games.all())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = GameSerializer(page, many=True, context=self.get_serializer_context())
            return self.get_paginated_response(serializer.data)

        serializer = GameSerializer(queryset, many=True, context=self.get_serializer_context())
        return Response(serializer.data)


class UserViewSet(PermissionsModelViewSet):
    ''' user view set '''

    # pylint: disable=no-member
    queryset = User.objects.all()
    serializer_class = UserSerializer
    lookup_field = 'name__iexact'
    lookup_url_kwarg = 'pk'

    # pylint: disable=unused-argument,invalid-name
    @action(detail=True)
    def stats(self, request, pk=None):
        ''' get user stats '''
        user = self.get_object()

        rg_top_100 = user.collection_set.filter(game__rec_rank__lte=100)
        bgg_top_100 = user.collection_set.filter(game__bgg_rank__lte=100)

        data = {
            'user': user.name,
            'rg_top_100': {
                'owned': rg_top_100.filter(owned=True).count(),
                'played': rg_top_100.filter(play_count__gt=0).count(),
                'rated': rg_top_100.filter(rating__isnull=False).count(),
            },
            'bgg_top_100': {
                'owned': bgg_top_100.filter(owned=True).count(),
                'played': bgg_top_100.filter(play_count__gt=0).count(),
                'rated': bgg_top_100.filter(rating__isnull=False).count(),
            },
        }

        return Response(data)


class CollectionViewSet(ModelViewSet):
    ''' user view set '''

    # pylint: disable=no-member
    queryset = Collection.objects.all()
    serializer_class = CollectionSerializer

    def get_permissions(self):
        cls = AllowAny if settings.DEBUG else IsAuthenticated
        return (cls(),)
