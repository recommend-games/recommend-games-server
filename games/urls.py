""" URLs """

from django.urls import include, path, re_path
from rest_framework.routers import DefaultRouter
from rest_framework_proxy.views import ProxyView

from .views import (
    CategoryViewSet,
    CollectionViewSet,
    GameTypeViewSet,
    GameViewSet,
    MechanicViewSet,
    PersonViewSet,
    RankingViewSet,
    UserViewSet,
    redirect_view,
)

ROUTER = DefaultRouter()
ROUTER.register("categories", CategoryViewSet)
ROUTER.register("collections", CollectionViewSet)
ROUTER.register("games", GameViewSet)
ROUTER.register("mechanics", MechanicViewSet)
ROUTER.register("persons", PersonViewSet)
ROUTER.register("rankings", RankingViewSet)
ROUTER.register("types", GameTypeViewSet)
ROUTER.register("users", UserViewSet)

# pylint: disable=invalid-name
urlpatterns = [
    path("", include(ROUTER.urls)),
    path("redirect", redirect_view),
    path("redirect/", redirect_view),
    re_path(
        r"^news/(?P<path>.+)$", ProxyView.as_view(source="%(path)s"), name="news-list"
    ),
]
