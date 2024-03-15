"""Functions for fetching and processing GitHub milestones."""

from __future__ import annotations

from urllib.parse import urlsplit
from warnings import warn

import requests
from packaging.version import Version
from setuptools.config.setupcfg import read_configuration


def get_milestone_numbers(token: str | None) -> dict[Version, str]:
    """Fetch milestone names and numbers from the GitHub API.

    :param token: The GitHub access token to use, or `None` to use none
    :return: Milestone names as version numbers, and corresponding milestone numbers
    :raises TypeError: Raised on unexpected JSON response

    """
    repo_url = urlsplit(read_configuration("setup.cfg")["metadata"]["url"])
    milestones = requests.get(
        f"https://api.github.com/repos{repo_url.path}/milestones",
        headers={"Authorization": f"Bearer {token}"} if token else {},
        timeout=10,
    ).json()
    if not isinstance(milestones, list):
        message = f"Expected a JSON list from GitHub API, got {milestones}"
        raise TypeError(message)
    # Extract milestone numbers from the milestone titles. Titles are expected to be
    # like "Darker x.y.z" or "Darker x.y.z - additional comment".
    return {
        Version(m["title"].split("-")[0].split()[-1]): str(m["number"])
        for m in milestones
    }


def get_next_milestone_version(
    version: Version, milestone_numbers: dict[Version, str], *, dry_run: bool
) -> Version:
    """Get the next larger version number found among milestone names.

    :param version: The version number to search a larger one for
    :param milestone_numbers: Milestone names and numbers from the GitHub API
    :param dry_run: `True` if running in dry-run mode
    :return: The next larger version number found
    :raises RuntimeError: Raised if no larger version number could be found

    """
    for milestone_version in sorted(milestone_numbers):
        if milestone_version > version:
            return milestone_version
    message = f"No milestone exists for a version later than {version}"
    if not dry_run:
        raise RuntimeError(message)
    warn(message, stacklevel=1)
    return Version(f"{version.major}.{version.minor}.{version.micro + 1}")
