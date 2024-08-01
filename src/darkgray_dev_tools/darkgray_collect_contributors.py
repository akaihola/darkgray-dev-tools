"""Script to collect GitHub usernames of contributors to a repository."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import TypeVar

import click
import keyring
import requests
import ruamel.yaml

from darkgray_dev_tools.darkgray_update_contributors import Contribution

GITHUB_API_URL = "https://api.github.com"
REQUEST_TIMEOUT = 10
HTTP_NOT_FOUND = 404

yaml = ruamel.yaml.YAML(typ="safe", pure=True)
yaml.indent(offset=2)


@click.command()
@click.option("--repo", required=True, help="Repository in the format owner/repo")
@click.option(
    "--since", help="ISO date to collect contributions from (e.g., 2023-01-01)"
)
def collect_contributors(repo: str, since: str | None) -> None:
    """Collect and print GitHub usernames of contributors to a repository."""
    token = keyring.get_password("gh:github.com", "")
    if not token:
        error_message = (
            "GitHub API token not found in keyring. "
            'Please set it using \'secret-tool store --label="GitHub API Token" '
            "service gh:github.com github_api_token'"
        )
        raise click.ClickException(error_message)
    headers = {"Authorization": f"token {token}"}
    base_url = f"{GITHUB_API_URL}/repos/{repo}"

    contributors = Contributors.load()

    since_date = (
        datetime.fromisoformat(since).strftime("%Y-%m-%dT%H:%M:%SZ") if since else None
    )

    collect_issues_and_prs(base_url, contributors, headers, since_date)
    collect_discussions(base_url, contributors, headers, since_date)

    click.echo("\n---\n\n")
    # write contributors to stdout as YAML
    contributors.dump()


T = TypeVar("T", bound="Contributors")


class Contributors:
    """Class to store contributors and their contributions."""

    def __init__(self) -> None:
        """Initialize a missing contributors list."""
        self._contributors: dict[str, list[Contribution]] = {}

    @classmethod
    def load(cls: type[T]) -> T:
        """Load contributors from a YAML file."""
        result = cls()
        with Path("contributors.yaml").open() as yaml_file:
            raw_contributors = yaml.load(yaml_file)
            result._contributors = {  # noqa: SLF001
                login: [Contribution(**c) for c in contributions]
                for login, contributions in raw_contributors.items()
            }
        return result

    def dump(self) -> None:
        """Dump contributors to stdout and write to a YAML file."""
        contributors_raw = {
            login: [asdict(c) for c in contributions]
            for login, contributions in self._contributors.items()
        }
        yaml.dump(
            contributors_raw,
            stream=click.get_text_stream("stdout"),
        )
        with Path("contributors.yaml").open("w") as yaml_file:
            yaml.dump(contributors_raw, yaml_file)

    def add_contribution(  # noqa: PLR0913
        self,
        login: str,
        endpoint: str,
        role: str,
        object_num: int,
        updated_at: str,
    ) -> None:
        """Add contribution type to contributors."""
        if login not in self._contributors:
            click.echo(
                f"{login}  "
                f"# {role} for {endpoint[:-1]} #{object_num} "
                f"(updated {updated_at[:10]})"
            )

        self._contributors.setdefault(login, [])
        if CONTRIBUTION_TYPES[endpoint, role] not in self._contributors[login]:
            self._contributors[login].append(CONTRIBUTION_TYPES[endpoint, role])


CONTRIBUTION_TYPES: dict[tuple[str, str], Contribution] = {
    ("issues", "author"): Contribution(
        link_type="issues",
        type="Bug reports",
    ),
    ("issues", "commenter"): Contribution(
        link_type="search-comments",
        type="Bug reports",
    ),
    ("pulls", "author"): Contribution(
        link_type="pulls-author",
        type="Code",
    ),
    ("pulls", "commenter"): Contribution(
        link_type="search-comments",
        type="Reviewed Pull Requests",
    ),
    ("commits", "author"): Contribution(
        link_type="commits",
        type="Code",
    ),
    ("discussions", "author"): Contribution(
        link_type="search-discussions",
        type="Bug reports",
    ),
    ("discussions", "commenter"): Contribution(
        link_type="search-comments",
        type="Bug reports",
    ),
}


def collect_issues_and_prs(
    base_url: str,
    contributors: Contributors,
    headers: dict[str, str],
    since_date: str | None,
) -> None:
    """Collect issue and PR authors and commenters."""
    for endpoint in ["issues", "pulls"]:
        url = f"{base_url}/{endpoint}?state=all&sort=updated&direction=desc"
        if since_date:
            url += f"&since={since_date}"
        while url:
            click.echo(url)
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            if since_date and all(item["updated_at"] < since_date for item in data):
                break
            for item in data:
                login = item["user"]["login"]
                number = item["number"]
                contributors.add_contribution(
                    login, endpoint, "author", number, item["updated_at"]
                )

                if since_date and item["updated_at"] < since_date:
                    continue
                comments_url = item["comments_url"]
                comments_response = requests.get(
                    comments_url, headers=headers, timeout=REQUEST_TIMEOUT
                )
                comments_response.raise_for_status()
                comments_data = comments_response.json()
                for comment in comments_data:
                    comment_login = comment["user"]["login"]
                    contributors.add_contribution(
                        comment_login,
                        endpoint,
                        "commenter",
                        number,
                        comment["updated_at"],
                    )
            url = response.links.get("next", {}).get("url")


def collect_discussions(
    base_url: str,
    contributors: Contributors,
    headers: dict[str, str],
    since_date: str | None,
) -> None:
    """Collect discussion authors and commenters if discussions are enabled."""
    url = f"{base_url}/discussions?sort=updated&direction=desc"
    if since_date:
        url += f"?since={since_date}"
    try:
        while url:
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            if since_date and all(item["updated_at"] < since_date for item in data):
                break
            for discussion in data:
                login = discussion["author"]["login"]
                object_id = discussion["id"]
                updated_at = discussion["updated_at"]
                contributors.add_contribution(
                    login,
                    "discussions",
                    "author",
                    object_id,
                    updated_at,
                )

                if since_date and discussion["updated_at"] < since_date:
                    continue
                comments_url = discussion["comments_url"]
                comments_response = requests.get(
                    comments_url, headers=headers, timeout=REQUEST_TIMEOUT
                )
                comments_response.raise_for_status()
                comments_data = comments_response.json()
                for comment in comments_data["data"]:
                    comment_login = comment["author"]["login"]
                    if comment_login not in contributors:
                        click.echo(
                            f"{comment_login}  "
                            f"# commenter for discussion #{object_id} "
                            f"(updated {comment["updated_at"][:10]})"
                        )
                    contributors.add_contribution(
                        comment_login,
                        "discussions",
                        "commenter",
                        object_id,
                        comment["updated_at"],
                    )
            url = response.links.get("next", {}).get("url")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == HTTP_NOT_FOUND:
            click.echo(
                "Discussions are not enabled for this repository. Skipping.", err=True
            )
        else:
            raise
