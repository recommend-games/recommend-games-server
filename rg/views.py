# -*- coding: utf-8 -*-

"""Views."""

from urllib.parse import urlencode

from django.shortcuts import redirect


def hashbang_redirect(request):
    """Redirect to hashbang."""

    path = f"/#{request.path}"

    if request.GET:
        query = urlencode(dict(request.GET), doseq=True)
        path = f"{path}?{query}"

    return redirect(path, permanent=True)
