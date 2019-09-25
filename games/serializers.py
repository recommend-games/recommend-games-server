# -*- coding: utf-8 -*-

""" serializers """

from rest_framework.serializers import (
    CharField,
    FloatField,
    IntegerField,
    ListField,
    ModelSerializer,
    PrimaryKeyRelatedField,
    StringRelatedField,
    URLField,
)

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


class GameSerializer(ModelSerializer):
    """ game serializer """

    designer_name = StringRelatedField(source="designer", many=True, read_only=True)
    artist_name = StringRelatedField(source="artist", many=True, read_only=True)
    game_type_name = StringRelatedField(source="game_type", many=True, read_only=True)
    category_name = StringRelatedField(source="category", many=True, read_only=True)
    mechanic_name = StringRelatedField(source="mechanic", many=True, read_only=True)
    contained_in = PrimaryKeyRelatedField(many=True, read_only=True)
    implemented_by = PrimaryKeyRelatedField(many=True, read_only=True)

    alt_name = ListField(child=CharField(), required=False)
    image_url = ListField(child=URLField(), required=False)
    video_url = ListField(child=URLField(), required=False)
    external_link = ListField(child=URLField(), required=False)

    freebase_id = ListField(child=CharField(), required=False)
    wikidata_id = ListField(child=CharField(), required=False)
    wikipedia_id = ListField(child=CharField(), required=False)
    dbpedia_id = ListField(child=CharField(), required=False)
    luding_id = ListField(child=IntegerField(min_value=1), required=False)
    spielen_id = ListField(child=CharField(), required=False)
    bga_id = ListField(child=CharField(), required=False)

    class Meta:
        """ meta """

        model = Game
        fields = "__all__"


class PersonSerializer(ModelSerializer):
    """ person serializer """

    class Meta:
        """ meta """

        model = Person
        fields = "__all__"


class GameTypeSerializer(ModelSerializer):
    """ game type serializer """

    count = IntegerField(read_only=True)

    class Meta:
        """ meta """

        model = GameType
        fields = "__all__"


class CategorySerializer(ModelSerializer):
    """ category serializer """

    count = IntegerField(read_only=True)

    class Meta:
        """ meta """

        model = Category
        fields = "__all__"


class MechanicSerializer(ModelSerializer):
    """ mechanic serializer """

    count = IntegerField(read_only=True)

    class Meta:
        """ meta """

        model = Mechanic
        fields = "__all__"


class RankingSerializer(ModelSerializer):
    """Ranking serializer."""

    avg = FloatField(read_only=True)

    class Meta:
        """Meta."""

        model = Ranking
        exclude = ("id", "game")


class CollectionSerializer(ModelSerializer):
    """ collection serializer """

    game_name = StringRelatedField(source="game", read_only=True)

    class Meta:
        """ meta """

        model = Collection
        fields = "__all__"


class UserSerializer(ModelSerializer):
    """ user serializer """

    games = CollectionSerializer(source="collection_set", many=True, read_only=True)

    class Meta:
        """ meta """

        model = User
        fields = "__all__"
