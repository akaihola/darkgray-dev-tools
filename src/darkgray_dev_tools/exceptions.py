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


class SectionNotFoundError(Exception):
    """Raised if an expected text section can't be found in a text file."""

    def __init__(self, section: str, filename: str) -> None:
        """Initialize the exception.

        :param section: The name of the section which was not found.
        :param filename: The name of the file in which the section couldn't be found

        """
        super().__init__(f"No {section} could be found in `{filename}`")


class WrongContributionTypeError(Exception):
    """Raised if verification finds a mismatching URL and contribution type."""

    def __init__(
        self,
        url: str,
        contribution_type: str,
        valid_contribution_types: tuple[str, ...],
    ) -> None:
        """Initialize the exception.

        :param url: The link to a GitHub search
        :param contribution_type: The type of contribution to be found in search results
        :param valid_contribution_types: Contribution types which can appear in the
                                         search results

        """
        super().__init__(
            f"Contribution type for {url} was {contribution_type}, "
            f"expected {valid_contribution_types}"
        )


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


class InvalidGitHubUrlError(Exception):
    """Raised if a contribution link doesn't point to GitHub."""

    def __init__(self, url: str) -> None:
        """Initialize the exception.

        :param url: A link to search results for contributions of a contributor

        """
        super().__init__(f"{url} is not a valid GitHub URL")


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
