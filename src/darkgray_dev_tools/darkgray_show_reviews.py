"""Helper script for showing timestamps and approvers of most recent approved reviews.

Usage::

    pip install darkgray-dev-tools
    darkgray-show-reviews --token=<ghp_your_github_token>

"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import click
from requests import codes
from ruamel.yaml import YAML

from darkgray_dev_tools.darkgray_update_contributors import (
    GitHubSession,
    get_github_repository,
)
from darkgray_dev_tools.exceptions import GitHubApiError


@dataclass
class Review:
    """Represents a pull request review."""

    pr_number: int
    pr_title: str
    reviewer: str
    submitted_at: datetime


def get_approved_reviews(session: GitHubSession, repo: str) -> list[Review]:
    """Fetch approved reviews for the repository using GraphQL API.

    :param session: The GitHub API session
    :param repo: The repository name (owner/repo)
    :return: A list of approved reviews
    """
    owner, name = repo.split("/")
    query = """
    query($owner: String!, $name: String!, $cursor: String) {
      repository(owner: $owner, name: $name) {
        pullRequests(first: 100,
                     after: $cursor,
                     orderBy: {field: UPDATED_AT, direction: DESC}) {
          pageInfo {
            hasNextPage
            endCursor
          }
          nodes {
            number
            title
            reviews(first: 1, states: APPROVED) {
              nodes {
                author {
                  login
                }
                submittedAt
              }
            }
          }
        }
      }
    }
    """

    approved_reviews = []
    variables = {"owner": owner, "name": name, "cursor": None}

    while True:
        response = session.post(
            "https://api.github.com/graphql",
            json={"query": query, "variables": variables},
        )
        if response.status_code != codes.ok:
            raise GitHubApiError(response)

        data = response.json()["data"]["repository"]["pullRequests"]

        for pr in data["nodes"]:
            if pr["reviews"]["nodes"]:
                review = pr["reviews"]["nodes"][0]
                approved_reviews.append(
                    Review(
                        pr_number=pr["number"],
                        pr_title=pr["title"],
                        reviewer=review["author"]["login"],
                        submitted_at=datetime.fromisoformat(
                            review["submittedAt"].replace("Z", "+00:00")
                        ),
                    )
                )

        if not data["pageInfo"]["hasNextPage"]:
            break

        variables["cursor"] = data["pageInfo"]["endCursor"]

    return approved_reviews


def generate_monthly_stats(approved_reviews: list[Review]) -> dict[str, dict[str, int]]:
    """Generate monthly statistics of approvals by reviewer."""
    stats: dict[str, dict[str, int]] = {}
    for review in approved_reviews:
        month_key = review.submitted_at.strftime("%Y-%m")
        if month_key not in stats:
            stats[month_key] = {}
        stats[month_key][review.reviewer] = stats[month_key].get(review.reviewer, 0) + 1
    return stats


@click.command()
@click.option("--token", required=True, help="GitHub API token")
@click.option(
    "--include-owner", is_flag=True, help="Include reviews by the repository owner"
)
@click.option(
    "--stats",
    is_flag=True,
    help="Show monthly statistics instead of individual reviews",
)
def show_reviews(token: str, include_owner: bool, stats: bool) -> None:  # noqa: FBT001
    """Show timestamps and reviewers of most recent approved reviews in YAML format."""
    session = GitHubSession(token)
    repo = get_github_repository()
    owner, _ = repo.split("/")

    approved_reviews = get_approved_reviews(session, repo)
    approved_reviews.sort(key=lambda r: r.submitted_at, reverse=True)

    if not include_owner:
        approved_reviews = [
            review for review in approved_reviews if review.reviewer != owner
        ]

    if stats:
        yaml_data = {
            "repository": repo,
            "monthly_stats": generate_monthly_stats(approved_reviews),
        }
    else:
        yaml_data = {
            "repository": repo,
            "approved_reviews": [
                {
                    "pr_number": review.pr_number,
                    "pr_title": review.pr_title,
                    "approved_by": review.reviewer,
                    "timestamp": review.submitted_at.isoformat(),
                }
                for review in approved_reviews
            ],
        }

    yaml = YAML()
    yaml.default_flow_style = False
    yaml.dump(yaml_data, click.get_text_stream("stdout"))


if __name__ == "__main__":
    show_reviews()
