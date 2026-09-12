# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Redactor contributors
"""Entry point used by native application packagers."""
from redactor.portable import configure
configure()
from redactor.app import main
import sys

if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--smoke-test":
        from redactor.smoke import run
        run(sys.argv[2])
    else:
        main()
