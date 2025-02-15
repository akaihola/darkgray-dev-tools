#!/usr/bin/env bash

VIRTUAL_ENV=
uv sync --quiet --all-extras --all-groups
UV_PYTHON=.venv

errors=0
.venv/bin/pre-commit run --all-files graylint || errors=$?
exit $errors
