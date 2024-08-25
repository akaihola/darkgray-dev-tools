"""Helper script for showing timestamps and approvers of most recent approved reviews.

Usage::

    pip install darkgray-dev-tools
    darkgray-show-reviews --token=<ghp_your_github_token>

"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List

import click
from ruamel.yaml import YAML
from requests import codes

from darkgray_dev_tools.darkgray_update_contributors import GitHubSession, get_github_repository
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
    owner, name = repo.split('/')
    query = """
    query($owner: String!, $name: String!, $cursor: String) {
      repository(owner: $owner, name: $name) {
        pullRequests(first: 100, after: $cursor, orderBy: {field: UPDATED_AT, direction: DESC}) {
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
        response = session.post("https://api.github.com/graphql", json={"query": query, "variables": variables})
        if response.status_code != codes.ok:
            raise GitHubApiError(response)
        
        data = response.json()["data"]["repository"]["pullRequests"]
        
        for pr in data["nodes"]:
            if pr["reviews"]["nodes"]:
                review = pr["reviews"]["nodes"][0]
                approved_reviews.append(Review(
                    pr_number=pr["number"],
                    pr_title=pr["title"],
                    reviewer=review["author"]["login"],
                    submitted_at=datetime.fromisoformat(review["submittedAt"].replace("Z", "+00:00"))
                ))
        
        if not data["pageInfo"]["hasNextPage"]:
            break
        
        variables["cursor"] = data["pageInfo"]["endCursor"]
    
    return approved_reviews


@click.command()
@click.option("--token", required=True, help="GitHub API token")
@click.option("--include-owner", is_flag=True, help="Include reviews by the repository owner")
def show_reviews(token: str, include_owner: bool) -> None:
    """Show timestamps and approvers of most recent approved reviews in YAML format."""
    session = GitHubSession(token)
    repo = get_github_repository()
    owner, _ = repo.split('/')
    
    approved_reviews = get_approved_reviews(session, repo)
    approved_reviews.sort(key=lambda r: r.submitted_at, reverse=True)

    if not include_owner:
        approved_reviews = [review for review in approved_reviews if review.reviewer != owner]

    yaml_data: Dict[str, List[Dict[str, Any]]] = {
        "repository": repo,
        "approved_reviews": [
            {
                "pr_number": review.pr_number,
                "pr_title": review.pr_title,
                "approved_by": review.reviewer,
                "timestamp": review.submitted_at.isoformat()
            }
            for review in approved_reviews
        ]
    }

    yaml = YAML()
    yaml.default_flow_style = False
    yaml.dump(yaml_data, click.get_text_stream('stdout'))


if __name__ == "__main__":
    show_reviews()
