"""Exceptions for `darkgray_dev_tools`."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from requests.models import Response


class NoMatchError(Exception):
    """Raised if pattern couldn't be found in the content."""

    def __init__(self, regex: str, path: str) -> None:
        """Initialize the exception.

        :param regex: The regular expression that couldn't be found
        :param path: The path of the file in which the regex couldn't be found

        """
        super().__init__(f"Can't find `{regex}` in `{path}`")


class GitHubRepoNameError(Exception):
    """Raised if ``git remote get-url`` fails & repository name can't be determined."""

    def __init__(self, cwd: Path) -> None:
        """Initialize the exception.

        :param cwd: The directory in which Git was run

        """
        super().__init__(
            f"Could not run Git to determine the name of the GitHub repository for "
            f"the working directory in {cwd}"
        )


class GitHubApiNotFoundError(Exception):
    """Raised when a GitHub API resource is not found."""


class GitHubApiError(Exception):
    """Raised when a GitHub API resource returns a non-OK response."""

    def __init__(self, response: Response) -> None:
        """Initialize the exception.

        :param response: The `Response` object for the request which was made to GitHub

        """
        super().__init__(
            f"{response.status_code} {response.text} when requesting {response.url}"
        )
