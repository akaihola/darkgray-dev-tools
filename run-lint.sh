#!/usr/bin/env bash

unset VIRTUAL_ENV
uv sync --all-extras

errors=0
uv run pre-commit run --all-files graylint || errors=$?
exit $errors
