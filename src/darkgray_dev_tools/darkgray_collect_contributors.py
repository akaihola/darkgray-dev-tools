"""Script to collect GitHub usernames of contributors to a repository."""

from __future__ import annotations

from datetime import datetime

import click
import keyring
import requests

GITHUB_API_URL = "https://api.github.com"
REQUEST_TIMEOUT = 10
HTTP_NOT_FOUND = 404


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

    contributors: set[str] = set()
    since_date = datetime.fromisoformat(since) if since else None

    collect_issues_and_prs(base_url, contributors, headers, since_date)
    collect_discussions(base_url, contributors, headers, since_date)

    click.echo("\n---\n\n")
    for username in sorted(contributors):
        click.echo(username)


def collect_issues_and_prs(
    base_url: str,
    contributors: set[str],
    headers: dict[str, str],
    since_date: datetime | None,
) -> None:
    """Collect issue and PR authors and commenters."""
    for endpoint in ["issues", "pulls"]:
        url = f"{base_url}/{endpoint}?state=all"
        if since_date:
            url += f"&since={since_date.isoformat()}"
        while url:
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            for item in data:
                login = item["user"]["login"]
                if login not in contributors:
                    click.echo(f"{login}  # {endpoint[:-1]} author")
                contributors.add(login)
                comments_url = item["comments_url"]
                comments_response = requests.get(
                    comments_url, headers=headers, timeout=REQUEST_TIMEOUT
                )
                comments_response.raise_for_status()
                comments_data = comments_response.json()
                for comment in comments_data:
                    login = comment["user"]["login"]
                    if login not in contributors:
                        click.echo(f"{login}  # discussion commenter")
                    contributors.add(login)
            url = response.links.get("next", {}).get("url")


def collect_discussions(
    base_url: str,
    contributors: set[str],
    headers: dict[str, str],
    since_date: datetime | None,
) -> None:
    """Collect discussion authors and commenters if discussions are enabled."""
    url = f"{base_url}/discussions"
    if since_date:
        url += f"?since={since_date.isoformat()}"
    try:
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        while url:
            data = response.json()
            for discussion in data:
                login = discussion["author"]["login"]
                if login not in contributors:
                    click.echo(f"{login}  # discussion author")
                contributors.add(login)
                comments_url = discussion["comments_url"]
                comments_response = requests.get(
                    comments_url, headers=headers, timeout=REQUEST_TIMEOUT
                )
                comments_response.raise_for_status()
                comments_data = comments_response.json()
                for comment in comments_data["data"]:
                    login = comment["author"]["login"]
                    if login not in contributors:
                        click.echo(f"{login}  # discussion commenter")
                    contributors.add(login)
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
