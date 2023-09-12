"""Functions for working with collections of games."""

from typing import Any, Iterable
from games.models import Collection


def any_collection(users: Iterable[str], **filters: Any) -> Iterable[str]:
    """Return a list of game IDs that are in any of the given users' collections."""
    return (
        Collection.objects.filter(user__in=users)
        .filter(**filters)
        .values_list("game", flat=True)
        .distinct()
    )
