"""Helper script for showing timestamps and approvers of most recent approved reviews.

Usage::

    pip install darkgray-dev-tools
    darkgray-show-reviews --token=<ghp_your_github_token>

"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import click
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
    """Fetch approved reviews for the repository.

    :param session: The GitHub API session
    :param repo: The repository name (owner/repo)
    :return: A list of approved reviews
    """
    approved_reviews = []
    page = 1
    while True:
        response = session.get(f"/repos/{repo}/pulls", params={"state": "all", "per_page": 100, "page": page})
        if response.status_code != codes.ok:
            raise GitHubApiError(response)
        
        pulls = response.json()
        if not pulls:
            break

        for pull in pulls:
            pr_number = pull["number"]
            pr_title = pull["title"]
            reviews_response = session.get(f"/repos/{repo}/pulls/{pr_number}/reviews")
            if reviews_response.status_code != codes.ok:
                raise GitHubApiError(reviews_response)
            
            reviews = reviews_response.json()
            approved_review = next((r for r in reviews if r["state"] == "APPROVED"), None)
            if approved_review:
                approved_reviews.append(Review(
                    pr_number=pr_number,
                    pr_title=pr_title,
                    reviewer=approved_review["user"]["login"],
                    submitted_at=datetime.fromisoformat(approved_review["submitted_at"].replace("Z", "+00:00"))
                ))
        
        page += 1

    return approved_reviews


@click.command()
@click.option("--token", required=True, help="GitHub API token")
def show_reviews(token: str) -> None:
    """Show timestamps and approvers of most recent approved reviews."""
    session = GitHubSession(token)
    repo = get_github_repository()
    
    approved_reviews = get_approved_reviews(session, repo)
    approved_reviews.sort(key=lambda r: r.submitted_at, reverse=True)

    click.echo(f"Most recent approved reviews for {repo}:")
    for review in approved_reviews:
        click.echo(f"PR #{review.pr_number}: '{review.pr_title}'")
        click.echo(f"  Approved by: {review.reviewer}")
        click.echo(f"  Timestamp: {review.submitted_at}")
        click.echo()


if __name__ == "__main__":
    show_reviews()
