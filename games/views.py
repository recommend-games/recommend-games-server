# -*- coding: utf-8 -*-

''' views '''

from functools import lru_cache

from django.conf import settings
from rest_framework.decorators import action
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
        return GamesRecommender.load(
            path=path,
            # dir_model='.',
            # dir_games=None,
            # dir_ratings=None,
            # dir_clusters=None,
        )

    except Exception:
        pass

    return None


class GameViewSet(ModelViewSet):
    ''' game view set '''

    # pylint: disable=no-member
    queryset = Game.objects.all()
    serializer_class = GameSerializer

    @action(detail=False)
    def recommend(self, request):
        ''' recommend games '''

        user = request.query_params.get('user')

        if not user:
            return self.list(request)

        path = getattr(settings, 'RECOMMENDER_PATH', None)
        recommender = _load_model(path)

        if recommender is None:
            return Response([])

        # TODO handle case that user is unknown
        # TODO speed up recommendation by pre-computing known games, clusters etc

        recommendation = recommender.recommend(
            users=(user,),
            num_games=10,
            ascending=True,
        )
        recommendation = {game['bgg_id']: game for game in recommendation}

        games = self.get_queryset().filter(bgg_id__in=recommendation)

        for game in games:
            rec = recommendation[game.bgg_id]
            game.rec_rank = rec['rank']
            game.rec_rating = rec['score']

        serializer = self.get_serializer(
            instance=sorted(games, key=lambda game: (game.rec_rank, -game.rec_rating)), many=True)

        return Response(serializer.data)


class PersonViewSet(ModelViewSet):
    ''' person view set '''

    # pylint: disable=no-member
    queryset = Person.objects.all()
    serializer_class = PersonSerializer
