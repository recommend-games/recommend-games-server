#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''command line script'''

from __future__ import absolute_import, division, print_function, unicode_literals, with_statement

import os
import sys

from server.boot import fix_path
fix_path(include_dev_libs_path=True)

from djangae.contrib.consistency.signals import connect_signals
connect_signals()

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.settings")

    from djangae.core.management import (
        execute_from_command_line,
        test_execute_from_command_line,
    )

    # use the correct sandbox environment
    if "test" in sys.argv:
        test_execute_from_command_line(sys.argv)
    else:
        execute_from_command_line(sys.argv)
