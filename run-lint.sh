#!/usr/bin/env bash

VIRTUAL_ENV=
uv sync --quiet --all-extras --all-groups
UV_PYTHON=.venv

errors=0
uv run graylint . || errors=$?
exit $errors
