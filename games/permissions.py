# -*- coding: utf-8 -*-

''' permissions '''

from rest_framework.permissions import BasePermission, SAFE_METHODS

class ReadOnly(BasePermission):
    ''' read-only permission '''

    message = 'You cannot write this resource.'

    def has_permission(self, request, view):
        return request.method in SAFE_METHODS
