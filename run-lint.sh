#!/usr/bin/env bash

uv sync --all-extras

errors=0
.venv/bin/pre-commit run --all-files graylint || errors=$?
exit $errors
