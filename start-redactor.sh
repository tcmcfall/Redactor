#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
if [[ -x ./Redactor ]]; then exec ./Redactor; fi
if [[ -d ./Redactor.app ]]; then exec open ./Redactor.app; fi
exec .venv/bin/python -m redactor
