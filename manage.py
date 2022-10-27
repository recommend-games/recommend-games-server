#!/usr/bin/env python

""" command line script """

import os
import sys

from dotenv import load_dotenv

if __name__ == "__main__":
    load_dotenv(verbose=True)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "rg.settings")

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc

    execute_from_command_line(sys.argv)
