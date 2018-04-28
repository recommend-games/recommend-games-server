# -*- coding: utf-8 -*-

'''checks'''

from __future__ import absolute_import, division, print_function, unicode_literals, with_statement

from django.core.checks import Error
from django.conf import settings
from django import VERSION


def check_session_csrf_enabled(app_configs, **kwargs):
    errors = []

    # Django 1.11 has built-in session-based CSRF tokens, so if that's enabled
    # we don't need to check for the mozilla version
    if VERSION > (1, 11) and getattr(settings, "CSRF_USE_SESSIONS", False):
        return []

    # Django >= 1.10 has a MIDDLEWARE setting, which is None by default. Convert
    # it to a list, it might be a tuple.
    middleware = list(getattr(settings, 'MIDDLEWARE', []) or [])
    middleware.extend(getattr(settings, 'MIDDLEWARE_CLASSES', []))

    if 'session_csrf.CsrfMiddleware' not in middleware:
        errors.append(Error(
            "SESSION_CSRF_DISABLED",
            hint="Please add 'session_csrf.CsrfMiddleware' to MIDDLEWARE_CLASSES",
            id='djangae.E001',
        ))
    return errors


def check_csp_is_not_report_only(app_configs, **kwargs):
    errors = []
    if getattr(settings, "CSP_REPORT_ONLY", False):
        errors.append(Error(
            "CSP_REPORT_ONLY_ENABLED",
            hint="Please set 'CSP_REPORT_ONLY' to False",
        ))
    return errors


CSP_SOURCE_NAMES = [
    'CSP_DEFAULT_SRC',
    'CSP_SCRIPT_SRC',
    'CSP_IMG_SRC',
    'CSP_OBJECT_SRC',
    'CSP_MEDIA_SRC',
    'CSP_FRAME_SRC',
    'CSP_FONT_SRC',
    'CSP_STYLE_SRC',
    'CSP_CONNECT_SRC',
]


def check_csp_sources_not_unsafe(app_configs, **kwargs):
    errors = []
    for csp_src_name in CSP_SOURCE_NAMES:
        csp_src_values = getattr(settings, csp_src_name, [])
        if "'unsafe-inline'" in csp_src_values or "'unsafe-eval'" in csp_src_values:
            errors.append(Error(
                csp_src_name + "_UNSAFE",
                hint="Please remove 'unsafe-inline'/'unsafe-eval' from your CSP policies",
            ))
    return errors


def check_cached_template_loader_used(app_configs, **kwargs):
    """ Ensure that the cached template loader is used for Django's template system. """
    for template in settings.TEMPLATES:
        if template['BACKEND'] != "django.template.backends.django.DjangoTemplates":
            continue
        loaders = template['OPTIONS'].get('loaders', [])
        for loader_tuple in loaders:
            if loader_tuple[0] == 'django.template.loaders.cached.Loader':
                return []
        error = Error(
            "CACHED_TEMPLATE_LOADER_NOT_USED",
            hint="Please use 'django.template.loaders.cached.Loader' for Django templates"
        )
        return [error]
