# -*- coding: utf-8 -*-

''' views '''

from rest_framework.viewsets import ModelViewSet

from .models import Game
from .serializers import GameSerializer


class GameViewSet(ModelViewSet):
    ''' game view set '''

    # pylint: disable=no-member
    queryset = Game.objects.all()
    serializer_class = GameSerializer
