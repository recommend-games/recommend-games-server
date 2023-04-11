""" views """
import logging
from datetime import timezone
from functools import lru_cache, reduce
from itertools import chain
from operator import or_
from typing import Callable, Iterable, Optional, Union

import pandas as pd
from django.conf import settings
from django.db.models import Count, Min, Q
from django.shortcuts import redirect
from django.utils.timezone import now
from django_filters import FilterSet
from django_filters.rest_framework import DjangoFilterBackend
from pytility import (
    arg_to_iter,
    clear_list,
    parse_bool,
    parse_date,
    parse_int,
    take_first,
    to_str,
)
from rest_framework.decorators import action
from rest_framework.exceptions import (
    MethodNotAllowed,
    NotAuthenticated,
    NotFound,
    PermissionDenied,
)
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.utils.urls import remove_query_param, replace_query_param
from rest_framework.viewsets import ModelViewSet

from .models import (
    Category,
    Collection,
    Game,
    GameType,
    Mechanic,
    Person,
    Ranking,
    User,
)
from .permissions import AlwaysAllowAny, ReadOnly
from .serializers import (
    CategorySerializer,
    CollectionSerializer,
    GameSerializer,
    GameTypeSerializer,
    MechanicSerializer,
    PersonSerializer,
    RankingFatSerializer,
    RankingSerializer,
    UserSerializer,
)
from .utils import load_recommender, model_updated_at, server_version

LOGGER = logging.getLogger(__name__)
PAGE_SIZE = api_settings.PAGE_SIZE or 25


class PermissionsModelViewSet(ModelViewSet):
    """add permissions based on settings"""

    def get_permissions(self):
        for permission in super().get_permissions():
            if isinstance(permission, AlwaysAllowAny):
                return (permission,)
        cls = ReadOnly if settings.READ_ONLY else AllowAny
        return (cls(),)

    def handle_exception(self, exc):
        if settings.READ_ONLY and isinstance(exc, (NotAuthenticated, PermissionDenied)):
            exc = MethodNotAllowed(self.request.method)
        return super().handle_exception(exc)


class GamesActionViewSet(PermissionsModelViewSet):
    """add a games action"""

    # pylint: disable=invalid-name,redefined-builtin,unused-argument
    @action(detail=True)
    def games(self, request, pk=None, format=None):
        """find all games"""

        obj = self.get_object()
        queryset = self.filter_queryset(obj.games.all())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = GameSerializer(
                page, many=True, context=self.get_serializer_context()
            )
            return self.get_paginated_response(serializer.data)

        serializer = GameSerializer(
            queryset, many=True, context=self.get_serializer_context()
        )
        return Response(serializer.data)


class BodyParamsPagination(PageNumberPagination):
    """Parse params from body and use in pagination."""

    keys: Union[str, Iterable[str]]
    parsers: Union[Callable, Iterable[Optional[Callable]]]

    def get_next_link(self):
        url = super().get_next_link()
        if url is None:
            return None
        for key, parser in zip(arg_to_iter(self.keys), arg_to_iter(self.parsers)):
            params = ",".join(
                map(str, sorted(_extract_params(self.request, key, parser)))
            )
            url = (
                replace_query_param(url, key, params)
                if params
                else remove_query_param(url, key)
            )
        return url

    def get_previous_link(self):
        url = super().get_previous_link()
        if url is None:
            return None
        for key, parser in zip(arg_to_iter(self.keys), arg_to_iter(self.parsers)):
            params = ",".join(
                map(str, sorted(_extract_params(self.request, key, parser)))
            )
            url = (
                replace_query_param(url, key, params)
                if params
                else remove_query_param(url, key)
            )
        return url


class BGGParamsPagination(BodyParamsPagination):
    """Pagination for /recommend endpoints."""

    keys = ("user", "like")
    parsers = (to_str, parse_int)


def _parse_parts(args):
    for arg in arg_to_iter(args):
        if isinstance(arg, str):
            for parsed in arg.split(","):
                parsed = parsed.strip()
                if parsed:
                    yield parsed
        elif isinstance(arg, (list, tuple)):
            yield from _parse_parts(arg)
        else:
            yield arg


def _parse_ints(args):
    for parsed in map(parse_int, _parse_parts(args)):
        if parsed is not None:
            yield parsed


def _extract_params(request, key, parser=None):
    data_values = (
        arg_to_iter(request.data.get(key))
        if isinstance(request.data, dict)
        else arg_to_iter(request.data)
    )
    query_values = arg_to_iter(request.query_params.getlist(key))
    values = _parse_parts(chain(data_values, query_values))

    if not callable(parser):
        yield from values
        return

    values = map(parser, values)
    for value in values:
        if value is not None:
            yield value


def _light_games(bgg_ids=None):
    # pylint: disable=no-member
    games = (
        Game.objects.all()
        if bgg_ids is None
        else Game.objects.filter(bgg_id__in=arg_to_iter(bgg_ids))
    )
    return games.values("bgg_id", "name", "year", "image_url")


def _light_games_dict(bgg_ids=None):
    games = _light_games(bgg_ids)
    return {game["bgg_id"]: game for game in games}


def _add_games(data, bgg_ids=None, key="game"):
    games = _light_games_dict(bgg_ids)
    for item in data:
        game = games.get(item.get(key))
        if game:
            item[key] = game
    return data


@lru_cache(maxsize=8)
def _get_compilations():
    return frozenset(
        Game.objects.filter(compilation=True)
        .order_by()
        .values_list("bgg_id", flat=True)
    )


class GameFilter(FilterSet):
    """game filter"""

    class Meta:
        """meta"""

        model = Game
        fields = {
            "year": ["exact", "gt", "gte", "lt", "lte", "isnull"],
            "designer": ["exact"],
            "designer__name": ["exact", "iexact"],
            "artist": ["exact"],
            "artist__name": ["exact", "iexact"],
            "min_players": ["exact", "gt", "gte", "lt", "lte", "isnull"],
            "max_players": ["exact", "gt", "gte", "lt", "lte", "isnull"],
            "min_players_rec": ["exact", "gt", "gte", "lt", "lte", "isnull"],
            "max_players_rec": ["exact", "gt", "gte", "lt", "lte", "isnull"],
            "min_players_best": ["exact", "gt", "gte", "lt", "lte", "isnull"],
            "max_players_best": ["exact", "gt", "gte", "lt", "lte", "isnull"],
            "min_age": ["exact", "gt", "gte", "lt", "lte", "isnull"],
            "max_age": ["exact", "gt", "gte", "lt", "lte", "isnull"],
            "min_age_rec": ["exact", "gt", "gte", "lt", "lte", "isnull"],
            "max_age_rec": ["exact", "gt", "gte", "lt", "lte", "isnull"],
            "min_time": ["exact", "gt", "gte", "lt", "lte", "isnull"],
            "max_time": ["exact", "gt", "gte", "lt", "lte", "isnull"],
            "game_type": ["exact"],
            "category": ["exact"],
            "mechanic": ["exact"],
            "cooperative": ["exact"],
            "compilation": ["exact"],
            "compilation_of": ["exact"],
            "implements": ["exact"],
            "integrates_with": ["exact"],
            "bgg_rank": ["exact", "gt", "gte", "lt", "lte", "isnull"],
            "num_votes": ["exact", "gt", "gte", "lt", "lte", "isnull"],
            "avg_rating": ["exact", "gt", "gte", "lt", "lte", "isnull"],
            "bayes_rating": ["exact", "gt", "gte", "lt", "lte", "isnull"],
            "rec_rank": ["exact", "gt", "gte", "lt", "lte", "isnull"],
            "rec_rating": ["exact", "gt", "gte", "lt", "lte", "isnull"],
            "complexity": ["exact", "gt", "gte", "lt", "lte", "isnull"],
            "language_dependency": ["exact", "gt", "gte", "lt", "lte", "isnull"],
            "kennerspiel_score": ["exact", "gt", "gte", "lt", "lte", "isnull"],
        }


class GameViewSet(PermissionsModelViewSet):
    """game view set"""

    # pylint: disable=no-member
    queryset = Game.objects.all()
    ordering = ("-rec_rating", "-bayes_rating", "-avg_rating")
    serializer_class = GameSerializer

    filter_backends = (DjangoFilterBackend, OrderingFilter, SearchFilter)
    filterset_class = GameFilter

    ordering_fields = (
        "year",
        "min_players",
        "max_players",
        "min_players_rec",
        "max_players_rec",
        "min_players_best",
        "max_players_best",
        "min_age",
        "max_age",
        "min_age_rec",
        "max_age_rec",
        "min_time",
        "max_time",
        "bgg_rank",
        "num_votes",
        "avg_rating",
        "bayes_rating",
        "rec_rank",
        "rec_rating",
        "complexity",
        "language_dependency",
        "kennerspiel_score",
    )
    search_fields = ("name",)

    collection_fields = ("owned",)

    stats_sites = {"rg_top": "rec_rank", "bgg_top": "bgg_rank"}

    stats_models = {
        "designer": (Person.objects.exclude(bgg_id=3), "designer_of", PersonSerializer),
        "artist": (Person.objects.exclude(bgg_id=3), "artist_of", PersonSerializer),
        "game_type": (GameType.objects.all(), "games", GameTypeSerializer),
        "category": (Category.objects.all(), "games", CategorySerializer),
        "mechanic": (Mechanic.objects.all(), "games", MechanicSerializer),
    }

    def _excluded_games(
        self,
        *,
        user=None,
        exclude_ids=None,
        exclude_compilations=True,
        exclude_known=True,
        exclude_owned=True,
        exclude_wishlist=None,
        exclude_play_count=None,
        exclude_clusters=False,
    ):
        exclude_ids = frozenset(arg_to_iter(exclude_ids))

        if user:
            queries = []

            if exclude_known:
                queries.append(Q(rating__isnull=False))
            if exclude_owned:
                queries.append(Q(owned=True))
            if exclude_wishlist:
                queries.append(Q(wishlist__lte=exclude_wishlist))
            if exclude_play_count:
                queries.append(Q(play_count__gte=exclude_play_count))

            if queries:
                query = reduce(or_, queries)
                exclude_ids |= frozenset(
                    Collection.objects.filter(user=user)
                    .filter(query)
                    .order_by()
                    .values_list("game_id", flat=True)
                )

        if exclude_clusters and exclude_ids:
            exclude_ids |= frozenset(
                self.get_queryset()
                .filter(cluster__in=exclude_ids)
                .order_by()
                .values_list("bgg_id", flat=True)
            )

        if exclude_compilations:
            exclude_ids |= _get_compilations()

        return exclude_ids

    def _included_games(
        self,
        *,
        recommender,
        user=None,
        include_ids=None,
        exclude_ids=None,
        exclude_compilations=True,
        exclude_known=True,
        exclude_owned=True,
        exclude_wishlist=None,
        exclude_play_count=None,
        exclude_clusters=False,
    ):
        include_ids = frozenset(arg_to_iter(include_ids))
        exclude_ids = self._excluded_games(
            user=user,
            exclude_ids=exclude_ids,
            exclude_compilations=exclude_compilations,
            exclude_known=exclude_known,
            exclude_owned=exclude_owned,
            exclude_wishlist=exclude_wishlist,
            exclude_play_count=exclude_play_count,
            exclude_clusters=exclude_clusters,
        )
        # If explicitly included, we don't exclude them here
        exclude_ids -= include_ids

        # Add all potential games not filtered out by query
        include_ids |= frozenset(
            self.filter_queryset(self.get_queryset())
            .order_by()
            .values_list("bgg_id", flat=True)
        )
        # We can only recommend games known to the recommender
        include_ids &= recommender.rated_games
        # Remove all excluded games
        return include_ids - exclude_ids

    def _recommend_rating(
        self,
        *,
        user,
        recommender,
        include_ids=None,
        exclude_ids=None,
        exclude_clusters=False,
        exclude_compilations=True,
    ):
        user = user.lower()
        if user not in recommender.known_users:
            raise NotFound(f"user <{user}> could not be found")

        include_ids = self._included_games(
            recommender=recommender,
            include_ids=include_ids,
            exclude_ids=exclude_ids,
            exclude_clusters=exclude_clusters,
            exclude_compilations=exclude_compilations,
        )

        if not include_ids:
            return ()

        recommendations = recommender.recommend(users=(user,))
        recommendations = recommendations[
            recommendations.index.isin(include_ids)
        ].copy()
        recommendations[(user, "rank")] = range(1, len(recommendations) + 1)

        return recommendations

    def _recommend_group_rating(
        self,
        *,
        users,
        recommender,
        include_ids=None,
        exclude_ids=None,
        exclude_clusters=False,
        exclude_compilations=True,
    ):
        users = (user.lower() for user in users if user)
        users = [user for user in users if user in recommender.known_users]
        if not users:
            raise NotFound("none of the users could be found")

        include_ids = self._included_games(
            recommender=recommender,
            include_ids=include_ids,
            exclude_ids=exclude_ids,
            exclude_clusters=exclude_clusters,
            exclude_compilations=exclude_compilations,
        )

        recommendations = recommender.recommend(users=users)
        recommendations = recommendations[recommendations.index.isin(include_ids)]
        recommendations = (
            recommendations.xs(axis=1, key="score", level=1)
            .mean(axis=1)
            .sort_values(ascending=False)
        )

        return pd.DataFrame(
            index=recommendations.index,
            data={
                ("_all", "score"): recommendations,
                ("_all", "rank"): range(1, len(recommendations) + 1),
            },
        )

    # pylint: disable=redefined-builtin,unused-argument
    @action(
        detail=False,
        methods=("GET", "POST"),
        permission_classes=(AlwaysAllowAny,),
        pagination_class=BGGParamsPagination,
    )
    def recommend(self, request, format=None):
        """recommend games"""

        users = list(_extract_params(request, "user", str))
        like = list(_extract_params(request, "like", parse_int))

        if not users and not like:
            return self.list(request)

        path_light = getattr(settings, "LIGHT_RECOMMENDER_PATH", None)
        recommender = load_recommender(path=path_light, site="light")

        if recommender is None:
            return self.list(request)

        include = frozenset(_extract_params(request, "include", parse_int))
        exclude = frozenset(_extract_params(request, "exclude", parse_int))
        exclude_clusters = parse_bool(request.query_params.get("exclude_clusters"))
        exclude_compilations = parse_bool(
            request.query_params.get("exclude_compilations", True)
        )

        recommendation = (
            self._recommend_rating(
                user=users[0],
                recommender=recommender,
                include_ids=include,
                exclude_ids=exclude,
                exclude_clusters=exclude_clusters,
                exclude_compilations=exclude_compilations,
            )
            if len(users) == 1
            else self._recommend_group_rating(
                users=users,
                recommender=recommender,
                include_ids=include,
                exclude_ids=exclude,
                exclude_clusters=exclude_clusters,
                exclude_compilations=exclude_compilations,
            )
            if users
            else None  # TODO support <like>
        )

        del like, path_light, recommender

        if recommendation is None:
            return self.list(request)

        key = users[0].lower() if len(users) == 1 else "_all"
        recommendation = recommendation.xs(axis=1, key=key)
        recommendation.sort_values("rank", inplace=True)
        recommendation = list(recommendation.itertuples(index=True))

        page = self.paginate_queryset(recommendation)
        if page is None:
            recommendation = recommendation[:PAGE_SIZE]
            paginate = False
        else:
            recommendation = page
            paginate = True
        del page

        recommendation = {game.Index: game for game in recommendation}
        queryset = self.filter_queryset(self.get_queryset())
        if include:
            queryset |= self.get_queryset().filter(bgg_id__in=include)
        games = queryset.filter(bgg_id__in=recommendation)

        for game in games:
            rec = recommendation[game.bgg_id]
            game.rec_rank = int(rec.rank)
            game.rec_rating = rec.score if users else None
            game.rec_stars = rec.stars if users and hasattr(rec, "stars") else None
        games = sorted(games, key=lambda game: game.rec_rank)
        del recommendation

        serializer = self.get_serializer(instance=games, many=True)
        del games

        return (
            self.get_paginated_response(serializer.data)
            if paginate
            else Response(serializer.data)
        )

    @action(detail=True)
    def rankings(self, request, pk=None, format=None):
        """Find historical rankings of a game."""

        filters = {
            "game": pk,
            "ranking_type__in": clear_list(_extract_params(request, "ranking_type")),
            "date__gte": parse_date(
                request.query_params.get("date__gte"), tzinfo=timezone.utc
            ),
            "date__lte": parse_date(
                request.query_params.get("date__lte"), tzinfo=timezone.utc
            ),
        }
        filters = {k: v for k, v in filters.items() if v}
        queryset = Ranking.objects.filter(**filters)
        serializer = RankingSerializer(
            queryset, many=True, context=self.get_serializer_context()
        )
        return Response(serializer.data)

    @action(detail=False)
    def history(self, request, format=None):
        """History of the top rankings."""

        top = parse_int(request.query_params.get("top")) or 100
        ranking_type = request.query_params.get("ranking_type") or Ranking.BGG

        filters = {
            "ranking_type": ranking_type,
            "date__gte": parse_date(
                request.query_params.get("date__gte"), tzinfo=timezone.utc
            ),
            "date__lte": parse_date(
                request.query_params.get("date__lte"), tzinfo=timezone.utc
            ),
        }
        filters = {k: v for k, v in filters.items() if v}
        queryset = Ranking.objects.filter(**filters)

        last_date = queryset.filter(rank=1).dates("date", "day", order="ASC").last()
        games = [
            r.game
            for r in queryset.filter(date=last_date, rank__lte=top)
            .order_by("rank")
            .select_related("game")
        ]

        assert len(games) == top

        game_ids = frozenset(g.bgg_id for g in games)
        rankings = queryset.filter(game__in=game_ids).order_by("date")

        data = [
            {
                "game": self.get_serializer(game).data,
                "rankings": RankingSerializer(
                    rankings.filter(game=game.bgg_id),
                    many=True,
                    context=self.get_serializer_context(),
                ).data,
            }
            for game in games
        ]
        return Response(data)

    @action(detail=False)
    def updated_at(self, request, format=None):
        """Get date of last model update."""
        updated_at = model_updated_at()
        if not updated_at:
            raise NotFound("unable to retrieve latest update")
        return Response({"updated_at": updated_at})

    @action(detail=False)
    def version(self, request, format=None):
        """Get project and server version."""
        return Response(server_version())

    @action(detail=False)
    def stats(self, request, format=None):
        """get games stats"""

        result = {"updated_at": model_updated_at()}

        top_games = next(_parse_ints(request.query_params.get("top_games")), 100)
        top_items = next(_parse_ints(request.query_params.get("top_items")), 10)

        for site_key, site_rank in self.stats_sites.items():
            site_filters = {f"{site_rank}__isnull": False}
            games = frozenset(
                self.filter_queryset(self.get_queryset())
                .filter(**site_filters)
                .order_by(site_rank)[:top_games]
                .values_list("bgg_id", flat=True)
            )
            total = len(games)
            site_result = {"total": total}
            result[site_key] = site_result

            for key, (queryset, field, serializer_class) in self.stats_models.items():
                filters = {f"{field}__in": games}
                objs = (
                    queryset.annotate(
                        top=Count(field, filter=Q(**filters)),
                        best=Min(f"{field}__{site_rank}"),
                    )
                    .filter(top__gt=0)
                    .order_by("-top", "best")[:top_items]
                )
                # pylint: disable=not-callable
                serializer = serializer_class(
                    objs, many=True, context=self.get_serializer_context()
                )
                for d, obj in zip(serializer.data, objs):
                    d["count"] = obj.top
                    d["pct"] = 100 * obj.top / total if total else 0
                    d["best"] = obj.best
                site_result[key] = serializer.data

        return Response(result)


class PersonViewSet(PermissionsModelViewSet):
    """person view set"""

    # pylint: disable=no-member
    queryset = Person.objects.all()
    serializer_class = PersonSerializer

    # pylint: disable=invalid-name,redefined-builtin,unused-argument
    @action(detail=True)
    def games(self, request, pk=None, format=None):
        """find all games for a person"""

        person = self.get_object()
        role = request.query_params.get("role")
        queryset = person.artist_of if role == "artist" else person.designer_of

        ordering = _parse_parts(request.query_params.getlist("ordering"))
        queryset = queryset.order_by(*ordering)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = GameSerializer(
                page, many=True, context=self.get_serializer_context()
            )
            return self.get_paginated_response(serializer.data)

        serializer = GameSerializer(
            queryset, many=True, context=self.get_serializer_context()
        )
        return Response(serializer.data)


class GameTypeViewSet(GamesActionViewSet):
    """game type view set"""

    # pylint: disable=no-member
    queryset = (
        GameType.objects.annotate(count=Count("games"))
        .filter(count__gt=100)
        .order_by("-count")
    )
    serializer_class = GameTypeSerializer


class CategoryViewSet(GamesActionViewSet):
    """category view set"""

    # pylint: disable=no-member
    queryset = (
        Category.objects.annotate(count=Count("games"))
        .filter(count__gt=5)
        .order_by("-count")
    )
    serializer_class = CategorySerializer


class MechanicViewSet(GamesActionViewSet):
    """mechanic view set"""

    # pylint: disable=no-member
    queryset = (
        Mechanic.objects.annotate(count=Count("games"))
        .filter(count__gt=10)
        .order_by("-count")
    )
    serializer_class = MechanicSerializer


class UserViewSet(PermissionsModelViewSet):
    """user view set"""

    # pylint: disable=no-member
    queryset = User.objects.all()
    serializer_class = UserSerializer
    lookup_field = "name__iexact"
    lookup_url_kwarg = "pk"
    stats_sites = GameViewSet.stats_sites

    # pylint: disable=invalid-name,redefined-builtin,unused-argument
    @action(detail=True)
    def stats(self, request, pk=None, format=None):
        """get user stats"""
        user = self.get_object()

        data = {"user": user.name, "updated_at": user.updated_at}

        top_games = next(_parse_ints(request.query_params.get("top_games")), 100)

        for key, rank in self.stats_sites.items():
            games = frozenset(
                Game.objects.filter(**{f"{rank}__lte": top_games})
                .order_by()
                .values_list("bgg_id", flat=True)
            )
            filters = {"game__in": games}
            collection = user.collection_set.filter(**filters)
            result = {
                "total": len(games),
                "owned": collection.filter(owned=True).count(),
                "played": collection.filter(play_count__gt=0).count(),
                "rated": collection.filter(rating__isnull=False).count(),
            }
            data[key] = result

        return Response(data)


class CollectionViewSet(ModelViewSet):
    """user view set"""

    # pylint: disable=no-member
    queryset = Collection.objects.all()
    serializer_class = CollectionSerializer

    def get_permissions(self):
        cls = AllowAny if settings.DEBUG else IsAuthenticated
        return (cls(),)


class RankingFilter(FilterSet):
    """Ranking filter."""

    class Meta:
        """Meta."""

        model = Ranking
        fields = {
            "game": ["exact"],
            "game__name": ["exact", "iexact"],
            "ranking_type": ["exact", "iexact"],
            "rank": ["exact", "gt", "gte", "lt", "lte"],
            "date": ["exact", "gt", "gte", "lt", "lte"],
        }


class RankingPagination(PageNumberPagination):
    """Ranking pagination."""

    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 1000


class RankingViewSet(PermissionsModelViewSet):
    """Ranking view set."""

    # pylint: disable=no-member
    queryset = Ranking.objects.all()
    ordering = ("ranking_type", "date", "rank")
    serializer_class = RankingSerializer
    pagination_class = RankingPagination

    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = RankingFilter

    ordering_fields = (
        "game",
        "ranking_type",
        "rank",
        "date",
    )

    # pylint: disable=redefined-builtin,unused-argument
    @action(detail=False)
    def dates(self, request, format=None):
        """Find all available dates with rankings."""

        query_set = self.get_queryset().order_by("ranking_type", "date")

        ranking_types = clear_list(_extract_params(request, "ranking_type"))
        if ranking_types:
            query_set = query_set.filter(ranking_type__in=ranking_types)

        return Response(query_set.values("ranking_type", "date").distinct())

    @action(detail=False)
    def games(self, request, format=None):
        """Similar to self.list(), but with full game details."""

        fat = parse_bool(next(_extract_params(request, "fat"), None))

        query_set = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(query_set)

        if page is not None:
            if fat:
                serializer = RankingFatSerializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            serializer = self.get_serializer(page, many=True)
            data = _add_games(serializer.data, (r.game_id for r in page))
            return self.get_paginated_response(data)

        if fat:
            serializer = RankingFatSerializer(query_set, many=True)
            return Response(serializer.data)

        serializer = self.get_serializer(query_set, many=True)
        data = _add_games(serializer.data, query_set.values_list("game", flat=True))
        return Response(data)


def redirect_view(request):
    """Redirect to a given path."""
    path = request.GET.get("to") or "/"
    return redirect(path if path.startswith("/") else f"/{path}", permanent=True)
