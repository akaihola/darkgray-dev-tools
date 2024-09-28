"""Script to collect GitHub usernames of contributors to a repository."""

from __future__ import annotations

import click
import keyring
import requests

GITHUB_API_URL = "https://api.github.com"
REQUEST_TIMEOUT = 10
HTTP_NOT_FOUND = 404


@click.command()
@click.option("--repo", required=True, help="Repository in the format owner/repo")
def collect_contributors(repo: str) -> None:
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

    contributors: set[str] = set()

    collect_issues_and_prs(base_url, contributors, headers)
    collect_discussions(base_url, contributors, headers)

    for username in sorted(contributors):
        click.echo(username)


def collect_issues_and_prs(
    base_url: str, contributors: set[str], headers: dict[str, str]
) -> None:
    """Collect issue and PR authors and commenters."""
    for endpoint in ["issues", "pulls"]:
        url = f"{base_url}/{endpoint}?state=all"
        while url:
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            for item in data:
                contributors.add(item["user"]["login"])
                comments_url = item["comments_url"]
                comments_response = requests.get(
                    comments_url, headers=headers, timeout=REQUEST_TIMEOUT
                )
                comments_response.raise_for_status()
                comments_data = comments_response.json()
                for comment in comments_data:
                    contributors.add(comment["user"]["login"])
            url = response.links.get("next", {}).get("url")


def collect_discussions(
    base_url: str, contributors: set[str], headers: dict[str, str]
) -> None:
    """Collect discussion authors and commenters if discussions are enabled."""
    url = f"{base_url}/discussions"
    try:
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        while url:
            data = response.json()
            for discussion in data:
                contributors.add(discussion["author"]["login"])
                comments_url = discussion["comments_url"]
                comments_response = requests.get(
                    comments_url, headers=headers, timeout=REQUEST_TIMEOUT
                )
                comments_response.raise_for_status()
                comments_data = comments_response.json()
                for comment in comments_data["data"]:
                    contributors.add(comment["author"]["login"])
            url = response.links.get("next", {}).get("url")
            if url:
                response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == HTTP_NOT_FOUND:
            click.echo(
                "Discussions are not enabled for this repository. Skipping.", err=True
            )
        else:
            raise
