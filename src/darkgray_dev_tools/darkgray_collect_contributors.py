"""Script to collect GitHub usernames of contributors to a repository."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import TypeVar

import click
import keyring
import requests
import ruamel.yaml

from darkgray_dev_tools.darkgray_update_contributors import Contribution
from darkgray_dev_tools.exceptions import GitHubRepoNameError

UNSUPPORTED_GIT_URL_ERROR = "Unsupported Git remote URL format"

GITHUB_API_URL = "https://api.github.com"
GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"
REQUEST_TIMEOUT = 10
HTTP_NOT_FOUND = 404

yaml = ruamel.yaml.YAML(typ="safe", pure=True)
yaml.indent(offset=2)


def get_repo_from_git() -> str:
    """Get the repository name from the Git remote URL."""
    git_path = shutil.which("git")
    if git_path is None:
        raise GitHubRepoNameError(Path.cwd()) from None

    def execute_git_command() -> str:
        try:
            return subprocess.check_output(
                [git_path, "config", "--get", "remote.origin.url"],  # noqa: S603
                universal_newlines=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except subprocess.CalledProcessError as err:
            raise GitHubRepoNameError(Path.cwd()) from err

    def parse_remote_url(remote_url: str) -> str:
        if remote_url.startswith("git@github.com:"):
            return remote_url.split(":")[-1].rstrip(".git")
        if remote_url.startswith(("https://github.com/", "git://github.com/")):
            return "/".join(remote_url.split("/")[-2:]).rstrip(".git")
        raise ValueError(UNSUPPORTED_GIT_URL_ERROR)

    try:
        remote_url = execute_git_command()
        return parse_remote_url(remote_url)
    except ValueError as err:
        raise GitHubRepoNameError(Path.cwd()) from err


@click.command()
@click.option("--repo", help="Repository in the format owner/repo")
@click.option(
    "--since", help="ISO date to collect contributions from (e.g., 2023-01-01)"
)
def collect_contributors(repo: str | None, since: str | None) -> None:
    """Collect and print GitHub usernames of contributors to a repository."""
    if repo is None:
        repo = get_repo_from_git()
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
    collect_discussions(repo, contributors, headers, since_date)

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
                f"  - {login}  "
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
            click.echo(f"{endpoint} and their comments:")
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            if since_date and all(item["updated_at"] < since_date for item in data):
                break
            for item in data:
                number = item["number"]
                contributors.add_contribution(
                    item["user"]["login"],
                    endpoint,
                    "author",
                    number,
                    item["updated_at"],
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
                    contributors.add_contribution(
                        comment["user"]["login"],
                        endpoint,
                        "commenter",
                        number,
                        comment["updated_at"],
                    )
            url = response.links.get("next", {}).get("url")


def collect_discussions(
    repo: str,
    contributors: Contributors,
    headers: dict[str, str],
    since_date: str | None,
) -> None:
    """Collect discussion authors and commenters using GraphQL API."""
    owner, name = repo.split("/")
    query = """
    query($owner: String!, $name: String!, $cursor: String) {
      repository(owner: $owner, name: $name) {
        discussions(first: 100,
                    after: $cursor,
                    orderBy: {field: UPDATED_AT, direction: DESC}) {
          pageInfo {
            hasNextPage
            endCursor
          }
          nodes {
            id
            number
            author {
              login
            }
            updatedAt
            comments(first: 100) {
              nodes {
                author {
                  login
                }
                updatedAt
              }
            }
          }
        }
      }
    }
    """

    variables = {"owner": owner, "name": name, "cursor": None}

    has_next_page = True
    while has_next_page:
        click.echo("discussions and their comments:")
        response = requests.post(
            GITHUB_GRAPHQL_URL,
            headers=headers,
            json={"query": query, "variables": variables},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()

        discussions = data["data"]["repository"]["discussions"]["nodes"]
        for discussion in discussions:
            discussion_number = discussion["number"]
            updated_at = discussion["updatedAt"]

            if since_date and updated_at < since_date:
                has_next_page = False
                break

            contributors.add_contribution(
                discussion["author"]["login"],
                "discussions",
                "author",
                discussion_number,
                updated_at,
            )

            for comment in discussion["comments"]["nodes"]:
                comment_updated_at = comment["updatedAt"]

                if since_date and comment_updated_at < since_date:
                    continue

                contributors.add_contribution(
                    comment["author"]["login"],
                    "discussions",
                    "commenter",
                    discussion_number,
                    comment_updated_at,
                )

        page_info = data["data"]["repository"]["discussions"]["pageInfo"]
        has_next_page = has_next_page and page_info["hasNextPage"]
        variables["cursor"] = page_info["endCursor"]
