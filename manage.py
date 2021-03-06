#!/usr/bin/env python
from __future__ import absolute_import, unicode_literals, print_function, division

import confy
import os
import sys

confy.read_environment_file(confy.env('ENV_FILE'))
if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "biosys.settings")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)
