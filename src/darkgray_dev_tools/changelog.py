"""Prepare a change log for a release."""

from datetime import datetime, timezone
from pathlib import Path

import click
from packaging.version import Version


def patch_changelog(next_version: Version, *, dry_run: bool) -> None:
    """Insert the new version and create a new unreleased section in the change log.

    :param next_version: The next version after the new version
    :param dry_run: ``True`` to just print the result

    """
    path = Path("CHANGES.rst")
    content = path.read_text(encoding="utf-8")
    before_unreleased = "These features will be included in the next release:\n\n"
    try:
        insert_point = content.index(before_unreleased) + len(before_unreleased)
    except ValueError as exc:
        msg = f"{exc} {before_unreleased!r}"
        raise ValueError(msg) from exc
    before = content[:insert_point]
    after = content[insert_point:]
    title = f"{next_version}_ - {datetime.now(tz=timezone.utc).date()}"
    new_content = (
        f"{before}"
        "Added\n"
        "-----\n\n"
        "Fixed\n"
        "-----\n\n\n"
        f"{title}\n"
        f"{len(title) * '='}\n\n"
        f"{after}"
    )
    if dry_run:
        click.echo("######## CHANGES.rst ########")
        click.echo(new_content[:200])
    else:
        path.write_text(new_content, encoding="utf-8")
