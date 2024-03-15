"""Get current version from ``version.py`` and next version based on command line."""

from __future__ import annotations

import re
from pathlib import Path

from packaging.version import Version

from darkgray_dev_tools.exceptions import NoMatchError


def get_current_version(version_py_path: str, patterns: dict[str, set[str]]) -> Version:
    """Find the current version number from ``version.py``.

    :param version_py_path: The relative path from cwd to the ``version.py`` file
    :param patterns: Regular expression patterns for finding version numbers in files
    :return: The current version number
    :raises NoMatchError: Raised if `version.py` doesn't match the expected format

    """
    version_py = Path(version_py_path).read_text(encoding="utf-8")
    current_version_re = next(iter(patterns[version_py_path])).format(
        **{"old_version->new_version": r"([\d\.a-z]+)"},
    )
    match = re.search(current_version_re, version_py, re.MULTILINE)
    if not match:
        raise NoMatchError(current_version_re, version_py_path)
    current_version = match.group(1)
    return Version(current_version)


def get_next_version(
    current_version: Version,
    *,
    increment_major: bool,
    increment_minor: bool,
) -> Version:
    """Return the next version number by incrementing elements as specified.

    :param current_version: The version number to increment
    :param increment_major: `True` to increment the major version number
    :param increment_minor: `True` to increment the minor version number
    :return: The new version number

    """
    major, minor, micro = current_version.release
    if increment_major:
        return Version(f"{major + 1}.0.0")
    if increment_minor:
        return Version(f"{major}.{minor + 1}.0")
    if current_version.is_devrelease or current_version.is_prerelease:
        return current_version
    return Version(f"{major}.{minor}.{micro + 1}")
