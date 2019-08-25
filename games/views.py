# -*- coding: utf-8 -*-

""" views """

import logging

from functools import reduce
from operator import or_

from django.conf import settings
from django.db.models import Count, Q
from django_filters import FilterSet
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.exceptions import (
    NotAuthenticated,
    NotFound,
    MethodNotAllowed,
    PermissionDenied,
)
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .models import Category, Collection, Game, GameType, Mechanic, Person, User
from .permissions import ReadOnly
from .serializers import (
    CategorySerializer,
    CollectionSerializer,
    GameSerializer,
    GameTypeSerializer,
    MechanicSerializer,
    PersonSerializer,
    UserSerializer,
)
from .utils import (
    arg_to_iter,
    load_recommender,
    model_updated_at,
    parse_bool,
    parse_int,
    pubsub_push,
    take_first,
)

LOGGER = logging.getLogger(__name__)


class PermissionsModelViewSet(ModelViewSet):
    """ add permissions based on settings """

    def get_permissions(self):
        cls = ReadOnly if settings.READ_ONLY else AllowAny
        return (cls(),)

    def handle_exception(self, exc):
        if settings.READ_ONLY and isinstance(exc, (NotAuthenticated, PermissionDenied)):
            exc = MethodNotAllowed(self.request.method)
        return super().handle_exception(exc)


class GamesActionViewSet(PermissionsModelViewSet):
    """ add a games action """

    # pylint: disable=unused-argument,invalid-name
    @action(detail=True)
    def games(self, request, pk=None):
        """ find all games """

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


def _exclude(user=None, ids=None):
    if ids is None:
        return None

    try:
        import turicreate as tc
    except ImportError:
        LOGGER.exception("unable to import <turicreate>")
        return None

    ids = (
        ids
        if isinstance(ids, tc.SArray)
        else tc.SArray(tuple(arg_to_iter(ids)), dtype=int)
    )

    # pylint: disable=len-as-condition
    if ids is None or not len(ids):
        return None

    sframe = tc.SFrame({"bgg_id": ids})
    sframe["bgg_user_name"] = user

    del tc, ids

    return sframe


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


class GameFilter(FilterSet):
    """ game filter """

    class Meta:
        """ meta """

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
        }


class GameViewSet(PermissionsModelViewSet):
    """ game view set """

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

    def _excluded_games(self, user, params):
        params = params or {}
        params.setdefault("exclude_known", True)

        exclude_known = parse_bool(take_first(params.get("exclude_known")))
        exclude_fields = [
            field
            for field in self.collection_fields
            if parse_bool(take_first(params.get(f"exclude_{field}")))
        ]
        exclude_wishlist = parse_int(take_first(params.get("exclude_wishlist")))
        exclude_play_count = parse_int(take_first(params.get("exclude_play_count")))
        exclude_clusters = parse_bool(take_first(params.get("exclude_clusters")))

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
                    .collection_set.order_by()
                    .filter(query)
                    .values_list("game_id", flat=True)
                )

        except Exception:
            pass

        return None

    def _recommend_rating(self, user, recommender, params):
        user = user.lower()
        if user not in recommender.known_users:
            raise NotFound(f"user <{user}> could not be found")

        # we should only need this if params are set, but see #90
        games = (
            frozenset(
                self.filter_queryset(self.get_queryset())
                .order_by()
                .values_list("bgg_id", flat=True)
            )
            & recommender.rated_games
        )

        if not games:
            return ()

        params = params or {}
        exclude = self._excluded_games(user, params)
        similarity_model = take_first(params.get("model")) == "similarity"

        return recommender.recommend(
            users=(user,),
            games=games,
            similarity_model=similarity_model,
            exclude=_exclude(user, ids=exclude),
            exclude_known=parse_bool(take_first(params.get("exclude_known"))),
            exclude_clusters=parse_bool(take_first(params.get("exclude_clusters"))),
            star_percentiles=getattr(settings, "STAR_PERCENTILES", None),
        )

    # pylint: disable=no-self-use
    def _recommend_group_rating(self, users, recommender, params):
        import turicreate as tc

        users = (user.lower() for user in users if user)
        users = [user for user in users if user in recommender.known_users]
        if not users:
            raise NotFound("none of the users could be found")

        similarity_model = take_first(params.get("model")) == "similarity"

        recommendations = (
            recommender.recommend(
                users=users, similarity_model=similarity_model, exclude_known=False
            )
            .groupby(
                key_column_names="bgg_id",
                operations={"score": tc.aggregate.MEAN("score")},
            )
            .sort("score", ascending=False)
        )

        recommendations.materialize()
        recommendations["rank"] = range(1, len(recommendations) + 1)
        recommendations.materialize()

        return recommendations

    def _recommend_similar(self, like, recommender):
        games = (
            frozenset(
                self.filter_queryset(self.get_queryset())
                .order_by()
                .values_list("bgg_id", flat=True)
            )
            & recommender.rated_games
        )

        if not games:
            return ()

        return recommender.recommend_similar(games=like, items=games)

    @action(detail=False)
    def recommend(self, request):
        """ recommend games """

        site = request.query_params.get("site")

        if site == "bga":
            return self.recommend_bga(request)

        users = list(_parse_parts(request.query_params.getlist("user")))
        like = list(_parse_ints(request.query_params.getlist("like")))

        if not users and not like:
            return self.list(request)

        if settings.PUBSUB_PUSH_ENABLED and users:
            for user in users:
                pubsub_push(user)

        path = getattr(settings, "RECOMMENDER_PATH", None)
        recommender = load_recommender(path, "bgg")

        if recommender is None:
            return self.list(request)

        recommendation = (
            self._recommend_rating(users[0], recommender, dict(request.query_params))
            if len(users) == 1
            else self._recommend_group_rating(
                users, recommender, dict(request.query_params)
            )
            if users
            else self._recommend_similar(like, recommender)
        )

        del like, path, recommender

        page = self.paginate_queryset(recommendation)
        if page is None:
            recommendation = recommendation[:10]
            paginate = False
        else:
            recommendation = page
            paginate = True
        del page

        recommendation = {game["bgg_id"]: game for game in recommendation}
        games = self.filter_queryset(self.get_queryset()).filter(
            bgg_id__in=recommendation
        )
        for game in games:
            rec = recommendation[game.bgg_id]
            game.rec_rank = rec["rank"]
            game.rec_rating = rec["score"] if users else None
            game.rec_stars = rec.get("stars") if users else None
        del recommendation

        serializer = self.get_serializer(
            instance=sorted(games, key=lambda game: game.rec_rank), many=True
        )
        del games

        return (
            self.get_paginated_response(serializer.data)
            if paginate
            else Response(serializer.data)
        )

    @action(detail=False)
    def recommend_bga(self, request):
        """ recommend games with Board Game Atlas data """

        path = getattr(settings, "BGA_RECOMMENDER_PATH", None)
        recommender = load_recommender(path, "bga")

        if recommender is None:
            return self.list(request)

        user = request.query_params.get("user")
        like = list(_parse_parts(request.query_params.getlist("like")))

        recommendation = (
            recommender.recommend(
                users=(user,),
                similarity_model=request.query_params.get("model") == "similarity",
                # exclude_known=parse_bool(take_first(params.get('exclude_known'))),
                # exclude_clusters=parse_bool(take_first(params.get('exclude_clusters'))),
                star_percentiles=getattr(settings, "STAR_PERCENTILES", None),
            )
            if user or not like
            else recommender.recommend_similar(games=like)
        )

        del path, recommender, user, like

        page = self.paginate_queryset(recommendation)
        return (
            self.get_paginated_response(page)
            if page is not None
            else Response(list(recommendation[:10]))
        )

    # pylint: disable=invalid-name
    @action(detail=True)
    def similar(self, request, pk=None):
        """ find games similar to this game """

        site = request.query_params.get("site")

        if site == "bga":
            return self.similar_bga(request, pk)

        path = getattr(settings, "RECOMMENDER_PATH", None)
        recommender = load_recommender(path)

        if recommender is None:
            raise NotFound(f"cannot find similar games to <{pk}>")

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

        games = {game["similar"]: game for game in games}
        results = self.get_queryset().filter(bgg_id__in=games)
        for game in results:
            game.sort_rank = games[game.bgg_id]["rank"]
        del games

        serializer = self.get_serializer(
            instance=sorted(results, key=lambda game: game.sort_rank), many=True
        )
        del results

        return (
            self.get_paginated_response(serializer.data)
            if paginate
            else Response(serializer.data)
        )

    # pylint: disable=unused-argument,invalid-name
    @action(detail=True)
    def similar_bga(self, request, pk=None):
        """ find games similar to this game with BGA data """

        path = getattr(settings, "BGA_RECOMMENDER_PATH", None)
        recommender = load_recommender(path, "bga")

        if recommender is None:
            raise NotFound(f"cannot find similar games to <{pk}>")

        games = recommender.similar_games(pk, num_games=0)

        del path, recommender

        page = self.paginate_queryset(games)
        return (
            self.get_paginated_response(page)
            if page is not None
            else Response(list(games[:10]))
        )

    @action(detail=False)
    def updated_at(self, request):
        """ recommend games """
        updated_at = model_updated_at()
        if not updated_at:
            raise NotFound("unable to retrieve latest update")
        return Response({"updated_at": updated_at})

    @action(detail=False)
    def stats(self, request):
        """ get games stats """

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
                    queryset.annotate(top=Count(field, filter=Q(**filters)))
                    .filter(top__gt=0)
                    .order_by("-top")[:top_items]
                )
                serializer = serializer_class(
                    objs, many=True, context=self.get_serializer_context()
                )
                for d, obj in zip(serializer.data, objs):
                    d["count"] = obj.top
                    d["pct"] = 100 * obj.top / total if total else 0
                site_result[key] = serializer.data

        return Response(result)


class PersonViewSet(PermissionsModelViewSet):
    """ person view set """

    # pylint: disable=no-member
    queryset = Person.objects.all()
    serializer_class = PersonSerializer

    # pylint: disable=unused-argument,invalid-name
    @action(detail=True)
    def games(self, request, pk=None):
        """ find all games for a person """

        person = self.get_object()
        role = request.query_params.get("role")
        queryset = person.artist_of if role == "artist" else person.designer_of
        queryset = self.filter_queryset(queryset.all())

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
    """ game type view set """

    # pylint: disable=no-member
    queryset = (
        GameType.objects.annotate(count=Count("games"))
        .filter(count__gt=100)
        .order_by("-count")
    )
    serializer_class = GameTypeSerializer


class CategoryViewSet(GamesActionViewSet):
    """ category view set """

    # pylint: disable=no-member
    queryset = (
        Category.objects.annotate(count=Count("games"))
        .filter(count__gt=5)
        .order_by("-count")
    )
    serializer_class = CategorySerializer


class MechanicViewSet(GamesActionViewSet):
    """ mechanic view set """

    # pylint: disable=no-member
    queryset = (
        Mechanic.objects.annotate(count=Count("games"))
        .filter(count__gt=10)
        .order_by("-count")
    )
    serializer_class = MechanicSerializer


class UserViewSet(PermissionsModelViewSet):
    """ user view set """

    # pylint: disable=no-member
    queryset = User.objects.all()
    serializer_class = UserSerializer
    lookup_field = "name__iexact"
    lookup_url_kwarg = "pk"
    stats_sites = GameViewSet.stats_sites

    # pylint: disable=unused-argument,invalid-name
    @action(detail=True)
    def stats(self, request, pk=None):
        """ get user stats """
        user = self.get_object()

        data = {"user": user.name, "updated_at": user.updated_at}

        top_games = next(_parse_ints(request.query_params.get("top_games")), 100)

        for key, rank in self.stats_sites.items():
            games = frozenset(
                Game.objects.filter(**{f"{rank}__lte": top_games})
                .order_by()
                .values_list("bgg_id", flat=True)
            )
            filters = {f"game__in": games}
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
    """ user view set """

    # pylint: disable=no-member
    queryset = Collection.objects.all()
    serializer_class = CollectionSerializer

    def get_permissions(self):
        cls = AllowAny if settings.DEBUG else IsAuthenticated
        return (cls(),)
