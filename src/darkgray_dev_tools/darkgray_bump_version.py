#!/usr/bin/env python

"""Helper script for bumping the version number.

None of the existing tools (like `bump2version`) worked for Darker, Graylint and
Darkgraylib out of the box without modifications. Hence this script.

Usage::

    pip install \
      https://github.com/akaihola/darkgray-dev-tools/archive/refs/heads/main.zip
    darkgray_bump_version {--major|--minor} [--dry-run]

Increments the patch version by default unless `--major` or `--minor` is specified.
With `--dry-run` will print out modified files on the terminal or crash with an
exception and a non-zero return value.

Use a ``.github/workflows/test-bump-version.yml`` workflow to run this with `--dry-run`
to ensure all regular expressions match content of the files to modify::

    ---
    name: darkgray_bump_version check

    on: push  # yamllint disable-line rule:truthy

    jobs:
      test-bump-version:
        runs-on: ubuntu-latest

        steps:
          - uses: actions/checkout@v4
          - uses: actions/setup-python@v5

          - name: Make sure that `darkgray_bump_version` still finds all version strings
                  and that there's a future milestone on GitHub Issues.
            # If this fails, make sure the regular expressions in
            # release_tools/bump-version-patterns.yaml
            # match changes in the files to modify. Also ensure there's a milestone
            # in the GitHub repository with a future version number as its name.
            # This is used to update the call for reviewing pull requests
            # in `README.rst`.
            run: |
              pip install https://github.com/akaihola/darkgray-dev-tools/archive/refs/heads/main.zip
              darkgray_bump_version \
                --minor \
                --dry-run \
                --token=${{ secrets.GITHUB_TOKEN }}

"""

from __future__ import annotations

from pathlib import Path

import click
from ruamel.yaml import YAML

from darkgray_dev_tools.changelog import patch_changelog
from darkgray_dev_tools.version_replace import do_replacements, get_replacements


@click.command()
@click.option("-n", "--dry-run", is_flag=True, default=False)
@click.option("-M", "--major", "increment_major", is_flag=True, default=False)
@click.option("-m", "--minor", "increment_minor", is_flag=True, default=False)
@click.option("--token")
def bump_version(  # pylint: disable=too-many-locals
    *, dry_run: bool, increment_major: bool, increment_minor: bool, token: str | None
) -> None:
    """Bump the version number."""
    with Path("release_tools/bump-version-patterns.yaml").open() as pattern_file:
        yaml = YAML(typ="safe", pure=True)
        pattern_templates_for_files = yaml.load(pattern_file)
    (patterns, replacements, new_version) = get_replacements(
        pattern_templates_for_files,
        increment_major=increment_major,
        increment_minor=increment_minor,
        token=token,
        dry_run=dry_run,
    )
    do_replacements(
        pattern_templates_for_files, patterns, replacements, dry_run=dry_run
    )
    patch_changelog(new_version, dry_run=dry_run)


if __name__ == "__main__":
    bump_version()  # pylint: disable=no-value-for-parameter
