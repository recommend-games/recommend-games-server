#!/usr/bin/env python
import os
import sys

from server.boot import fix_path
fix_path(include_dev_libs_path=True)

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
