#!/usr/bin/env bash

uv sync --all-extras

errors=0
.venv/bin/darkgray_collect_contributors \
  --repo akaihola/darkgray-dev-tools \
  || errors=$?
.venv/bin/pytest || errors=$?

exit $errors
