#!/usr/bin/env bash

VIRTUAL_ENV=
uv sync --all-extras
UV_PYTHON=.venv

errors=0
uv run darkgray_collect_contributors \
  --repo akaihola/darkgray-dev-tools \
  || errors=$?
uv run pytest || errors=$?

exit $errors
