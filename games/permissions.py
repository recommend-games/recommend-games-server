# -*- coding: utf-8 -*-

""" permissions """

from rest_framework.permissions import AllowAny, BasePermission, SAFE_METHODS


class ReadOnly(BasePermission):
    """ read-only permission """

    message = "You cannot write this resource."

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS


class AlwaysAllowAny(AllowAny):
    """Always allow everything. Always."""
