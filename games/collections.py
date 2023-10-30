"""Functions for working with collections of games."""

from typing import Any, Iterable
from games.models import Collection, Game


def any_collection(users: Iterable[str], **filters: Any) -> Iterable[str]:
    """Return a list of game IDs that are in any of the given users' collections."""
    return (
        Collection.objects.filter(user__in=users)
        .filter(**filters)
        .values_list("game", flat=True)
        .order_by()
        .distinct()
    )


def none_collection(users: Iterable[str], **filters: Any) -> Iterable[str]:
    """Return a list of game IDs that are in none of the given users' collections."""
    return (
        Game.objects.exclude(bgg_id__in=any_collection(users, **filters))
        .values_list("bgg_id", flat=True)
        .order_by()
    )


def all_collection(users: Iterable[str], **filters: Any) -> Iterable[str]:
    """Return a list of game IDs that are in all of the given users' collections."""
    collections = (
        Collection.objects.filter(user=user)
        .filter(**filters)
        .values_list("game", flat=True)
        .order_by()
        for user in users
    )
    return (
        Game.objects.values_list("bgg_id", flat=True)
        .order_by()
        .intersection(*collections)
    )
