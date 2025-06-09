"""Tests for the `darkgray_dev_tools.darkgray_collect_contributors` module."""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest
import requests
from click.testing import CliRunner

from darkgray_dev_tools.darkgray_collect_contributors import (
    CONTRIBUTION_TYPES,
    GITHUB_API_URL,
    GITHUB_GRAPHQL_URL,
    HTTP_NOT_FOUND,
    REQUEST_TIMEOUT,
    UNSUPPORTED_GIT_URL_ERROR,
    Contributors,
    collect_contributors,
    collect_discussions,
    collect_issues_and_prs,
    get_repo_from_git,
)
from darkgray_dev_tools.darkgray_update_contributors import Contribution
from darkgray_dev_tools.exceptions import GitHubRepoNameError


class TestGetRepoFromGit:
    """Test the get_repo_from_git function."""

    @pytest.mark.kwparametrize(
        dict(remote_url="git@github.com:owner/repo.git", expected="owner/repo"),
        dict(remote_url="git@github.com:owner/repo", expected="owner/repo"),
        dict(remote_url="git@github.com:owner/repo.git/", expected="owner/repo"),
        dict(remote_url="git@github.com:owner/repo/", expected="owner/repo"),
        dict(remote_url="https://github.com/owner/repo.git", expected="owner/repo"),
        dict(remote_url="https://github.com/owner/repo", expected="owner/repo"),
        dict(remote_url="https://github.com/owner/repo.git/", expected="owner/repo"),
        dict(remote_url="https://github.com/owner/repo/", expected="owner/repo"),
        dict(remote_url="git://github.com/owner/repo.git", expected="owner/repo"),
        dict(remote_url="git://github.com/owner/repo", expected="owner/repo"),
        dict(remote_url="git://github.com/owner/repo.git/", expected="owner/repo"),
        dict(remote_url="git://github.com/owner/repo/", expected="owner/repo"),
        dict(
            remote_url="https://github.com/Company-Login/Project.Name/",
            expected="Company-Login/Project.Name",
        ),
        dict(
            remote_url="https://github.com/Company-Login/Project.Name",
            expected="Company-Login/Project.Name",
        ),
    )
    def test_get_repo_from_git_success(self, remote_url: str, expected: str) -> None:
        """Test successful parsing of various Git remote URL formats."""
        with patch("shutil.which", return_value="/usr/bin/git"), patch(
            "subprocess.check_output", return_value=remote_url + "\n"
        ):
            result = get_repo_from_git()
            assert result == expected

    @pytest.mark.kwparametrize(
        dict(remote_url="https://gitlab.com/owner/repo.git"),
        dict(remote_url="ssh://git@example.com/owner/repo.git"),
        dict(remote_url="ftp://github.com/owner/repo.git"),
        dict(remote_url="github.com/owner/repo"),
        dict(remote_url="owner/repo"),
    )
    def test_get_repo_from_git_unsupported_url(self, remote_url: str) -> None:
        """Test error handling for unsupported Git remote URL formats."""
        with patch("shutil.which", return_value="/usr/bin/git"), patch(
            "subprocess.check_output", return_value=remote_url + "\n"
        ), pytest.raises(GitHubRepoNameError):
            get_repo_from_git()

    def test_get_repo_from_git_no_git_command(self) -> None:
        """Test error when git command is not available."""
        with patch("shutil.which", return_value=None), pytest.raises(
            GitHubRepoNameError
        ):
            get_repo_from_git()

    def test_get_repo_from_git_command_fails(self) -> None:
        """Test error when git command fails."""
        with patch("shutil.which", return_value="/usr/bin/git"), patch(
            "subprocess.check_output",
            side_effect=subprocess.CalledProcessError(1, "git"),
        ), pytest.raises(GitHubRepoNameError):
            get_repo_from_git()


class TestContributors:
    """Test the Contributors class."""

    def test_contributors_init(self) -> None:
        """Test Contributors initialization."""
        contributors = Contributors()
        assert contributors._contributors == {}

    def test_contributors_load(self) -> None:
        """Test loading contributors from YAML file."""
        yaml_content = {
            "user1": [
                {"link_type": "issues", "type": "Bug reports"},
                {"link_type": "pulls-author", "type": "Code"},
            ],
            "user2": [
                {"link_type": "search-comments", "type": "Reviewed Pull Requests"}
            ],
        }

        mock_yaml = Mock()
        mock_yaml.load.return_value = yaml_content

        with patch("pathlib.Path.open", mock_open()), patch(
            "darkgray_dev_tools.darkgray_collect_contributors.yaml", mock_yaml
        ):
            contributors = Contributors.load()

            assert len(contributors._contributors) == 2
            assert "user1" in contributors._contributors
            assert "user2" in contributors._contributors
            assert len(contributors._contributors["user1"]) == 2
            assert len(contributors._contributors["user2"]) == 1

    def test_contributors_dump(self) -> None:
        """Test dumping contributors to stdout and YAML file."""
        contributors = Contributors()
        contributors._contributors = {
            "user1": [
                Contribution(link_type="issues", type="Bug reports"),
                Contribution(link_type="pulls-author", type="Code"),
            ],
        }

        mock_yaml = Mock()
        mock_stream = Mock()

        with patch("pathlib.Path.open", mock_open()), patch(
            "darkgray_dev_tools.darkgray_collect_contributors.yaml", mock_yaml
        ), patch("click.get_text_stream", return_value=mock_stream):
            contributors.dump()

            assert mock_yaml.dump.call_count == 2
            # Check that data was dumped to both stdout and file
            dump_calls = mock_yaml.dump.call_args_list
            assert dump_calls[0][1]["stream"] == mock_stream  # stdout
            # File dump doesn't have stream parameter

    @pytest.mark.kwparametrize(
        dict(
            endpoint="issues",
            role="author",
            expected_contribution=Contribution(link_type="issues", type="Bug reports"),
        ),
        dict(
            endpoint="issues",
            role="commenter",
            expected_contribution=Contribution(
                link_type="search-comments", type="Bug reports"
            ),
        ),
        dict(
            endpoint="pulls",
            role="author",
            expected_contribution=Contribution(link_type="pulls-author", type="Code"),
        ),
        dict(
            endpoint="pulls",
            role="commenter",
            expected_contribution=Contribution(
                link_type="search-comments", type="Reviewed Pull Requests"
            ),
        ),
        dict(
            endpoint="discussions",
            role="author",
            expected_contribution=Contribution(
                link_type="search-discussions", type="Bug reports"
            ),
        ),
        dict(
            endpoint="discussions",
            role="commenter",
            expected_contribution=Contribution(
                link_type="search-comments", type="Bug reports"
            ),
        ),
    )
    def test_add_contribution_new_user(
        self,
        endpoint: str,
        role: str,
        expected_contribution: Contribution,
    ) -> None:
        """Test adding contributions for new users."""
        contributors = Contributors()

        with patch("click.echo") as mock_echo:
            contributors.add_contribution(
                "newuser", endpoint, role, 123, "2023-01-01T00:00:00Z"
            )

            assert "newuser" in contributors._contributors
            assert expected_contribution in contributors._contributors["newuser"]
            mock_echo.assert_called_once()

    def test_add_contribution_existing_user_new_type(self) -> None:
        """Test adding new contribution type for existing user."""
        contributors = Contributors()
        contributors._contributors["existinguser"] = [
            Contribution(link_type="issues", type="Bug reports")
        ]

        with patch("click.echo"):
            contributors.add_contribution(
                "existinguser", "pulls", "author", 456, "2023-01-02T00:00:00Z"
            )

            assert len(contributors._contributors["existinguser"]) == 2
            assert (
                Contribution(link_type="pulls-author", type="Code")
                in contributors._contributors["existinguser"]
            )

    def test_add_contribution_existing_user_duplicate_type(self) -> None:
        """Test adding duplicate contribution type for existing user."""
        contributors = Contributors()
        existing_contribution = Contribution(link_type="issues", type="Bug reports")
        contributors._contributors["existinguser"] = [existing_contribution]

        with patch("click.echo"):
            contributors.add_contribution(
                "existinguser", "issues", "author", 789, "2023-01-03T00:00:00Z"
            )

            # Should not add duplicate
            assert len(contributors._contributors["existinguser"]) == 1
            assert (
                contributors._contributors["existinguser"][0] == existing_contribution
            )


class TestContributionTypes:
    """Test the CONTRIBUTION_TYPES constant."""

    def test_contribution_types_completeness(self) -> None:
        """Test that all expected contribution types are defined."""
        expected_keys = [
            ("issues", "author"),
            ("issues", "commenter"),
            ("pulls", "author"),
            ("pulls", "commenter"),
            ("commits", "author"),
            ("discussions", "author"),
            ("discussions", "commenter"),
        ]

        for key in expected_keys:
            assert key in CONTRIBUTION_TYPES

    def test_contribution_types_structure(self) -> None:
        """Test that contribution types have correct structure."""
        for contribution in CONTRIBUTION_TYPES.values():
            assert isinstance(contribution, Contribution)
            assert hasattr(contribution, "link_type")
            assert hasattr(contribution, "type")
            assert isinstance(contribution.link_type, str)
            assert isinstance(contribution.type, str)


class TestCollectIssuesAndPrs:
    """Test the collect_issues_and_prs function."""

    def test_collect_issues_and_prs_success(self) -> None:
        """Test successful collection of issues and PRs."""
        base_url = f"{GITHUB_API_URL}/repos/owner/repo"
        contributors = Contributors()
        headers = {"Authorization": "token fake_token"}

        # Mock API responses
        issues_response = Mock()
        issues_response.json.return_value = [
            {
                "number": 1,
                "user": {"login": "user1"},
                "updated_at": "2023-01-01T00:00:00Z",
                "comments_url": f"{base_url}/issues/1/comments",
            }
        ]
        issues_response.links = {}

        comments_response = Mock()
        comments_response.json.return_value = [
            {
                "user": {"login": "user2"},
                "updated_at": "2023-01-01T01:00:00Z",
            }
        ]

        def mock_get(url: str, **kwargs) -> Mock:
            if "issues" in url and "comments" not in url:
                return issues_response
            if "pulls" in url and "comments" not in url:
                issues_response.json.return_value = []
                return issues_response
            return comments_response

        with patch("requests.get", side_effect=mock_get), patch("click.echo"):
            collect_issues_and_prs(base_url, contributors, headers, None)

            assert "user1" in contributors._contributors
            assert "user2" in contributors._contributors

    def test_collect_issues_and_prs_with_since_date(self) -> None:
        """Test collection with since date filtering."""
        base_url = f"{GITHUB_API_URL}/repos/owner/repo"
        contributors = Contributors()
        headers = {"Authorization": "token fake_token"}
        since_date = "2023-01-02T00:00:00Z"

        # Mock API responses with dates before and after since_date
        issues_response = Mock()
        issues_response.json.return_value = [
            {
                "number": 1,
                "user": {"login": "user1"},
                "updated_at": "2023-01-01T00:00:00Z",  # Before since_date
                "comments_url": f"{base_url}/issues/1/comments",
            },
            {
                "number": 2,
                "user": {"login": "user2"},
                "updated_at": "2023-01-03T00:00:00Z",  # After since_date
                "comments_url": f"{base_url}/issues/2/comments",
            },
        ]
        issues_response.links = {}

        comments_response = Mock()
        comments_response.json.return_value = []

        def mock_get(url: str, **kwargs) -> Mock:
            if "issues" in url and "comments" not in url:
                return issues_response
            if "pulls" in url and "comments" not in url:
                issues_response.json.return_value = []
                return issues_response
            return comments_response

        with patch("requests.get", side_effect=mock_get), patch("click.echo"):
            collect_issues_and_prs(base_url, contributors, headers, since_date)

            # Both users should be added as authors
            assert "user1" in contributors._contributors
            assert "user2" in contributors._contributors

    def test_collect_issues_and_prs_pagination(self) -> None:
        """Test handling of paginated responses."""
        base_url = f"{GITHUB_API_URL}/repos/owner/repo"
        contributors = Contributors()
        headers = {"Authorization": "token fake_token"}

        # First page response
        first_response = Mock()
        first_response.json.return_value = [
            {
                "number": 1,
                "user": {"login": "user1"},
                "updated_at": "2023-01-01T00:00:00Z",
                "comments_url": f"{base_url}/issues/1/comments",
            }
        ]
        first_response.links = {"next": {"url": f"{base_url}/issues?page=2"}}

        # Second page response
        second_response = Mock()
        second_response.json.return_value = [
            {
                "number": 2,
                "user": {"login": "user2"},
                "updated_at": "2023-01-02T00:00:00Z",
                "comments_url": f"{base_url}/issues/2/comments",
            }
        ]
        second_response.links = {}

        comments_response = Mock()
        comments_response.json.return_value = []

        call_count = 0

        def mock_get(url: str, **kwargs) -> Mock:
            nonlocal call_count
            if "comments" in url:
                return comments_response
            if "pulls" in url:
                return Mock(json=lambda: [], links={})

            call_count += 1
            if call_count == 1:
                return first_response
            return second_response

        with patch("requests.get", side_effect=mock_get), patch("click.echo"):
            collect_issues_and_prs(base_url, contributors, headers, None)

            assert "user1" in contributors._contributors
            assert "user2" in contributors._contributors


class TestCollectDiscussions:
    """Test the collect_discussions function."""

    def test_collect_discussions_success(self) -> None:
        """Test successful collection of discussions."""
        repo = "owner/repo"
        contributors = Contributors()
        headers = {"Authorization": "token fake_token"}

        # Mock GraphQL response
        graphql_response = Mock()
        graphql_response.json.return_value = {
            "data": {
                "repository": {
                    "discussions": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": [
                            {
                                "id": "discussion1",
                                "number": 1,
                                "author": {"login": "user1"},
                                "updatedAt": "2023-01-01T00:00:00Z",
                                "comments": {
                                    "nodes": [
                                        {
                                            "author": {"login": "user2"},
                                            "updatedAt": "2023-01-01T01:00:00Z",
                                        }
                                    ]
                                },
                            }
                        ],
                    }
                }
            }
        }

        with patch("requests.post", return_value=graphql_response), patch("click.echo"):
            collect_discussions(repo, contributors, headers, None)

            assert "user1" in contributors._contributors
            assert "user2" in contributors._contributors

    def test_collect_discussions_with_since_date(self) -> None:
        """Test collection with since date filtering."""
        repo = "owner/repo"
        contributors = Contributors()
        headers = {"Authorization": "token fake_token"}
        since_date = "2023-01-02T00:00:00Z"

        # Mock GraphQL response with discussion after since_date
        graphql_response = Mock()
        graphql_response.json.return_value = {
            "data": {
                "repository": {
                    "discussions": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": [
                            {
                                "id": "discussion1",
                                "number": 1,
                                "author": {"login": "user1"},
                                "updatedAt": "2023-01-03T00:00:00Z",  # After since_date
                                "comments": {
                                    "nodes": [
                                        {
                                            "author": {"login": "user2"},
                                            "updatedAt": "2023-01-01T01:00:00Z",  # Before since_date
                                        },
                                        {
                                            "author": {"login": "user3"},
                                            "updatedAt": "2023-01-03T00:00:00Z",  # After since_date
                                        },
                                    ]
                                },
                            }
                        ],
                    }
                }
            }
        }

        with patch("requests.post", return_value=graphql_response), patch("click.echo"):
            collect_discussions(repo, contributors, headers, since_date)

            # user1 should be added (discussion after since_date)
            # user3 should be added (comment after since_date)
            # user2 should not be added (comment before since_date)
            assert "user1" in contributors._contributors
            assert "user3" in contributors._contributors

    def test_collect_discussions_pagination(self) -> None:
        """Test handling of paginated GraphQL responses."""
        repo = "owner/repo"
        contributors = Contributors()
        headers = {"Authorization": "token fake_token"}

        # Mock responses for pagination
        first_response = Mock()
        first_response.json.return_value = {
            "data": {
                "repository": {
                    "discussions": {
                        "pageInfo": {"hasNextPage": True, "endCursor": "cursor1"},
                        "nodes": [
                            {
                                "id": "discussion1",
                                "number": 1,
                                "author": {"login": "user1"},
                                "updatedAt": "2023-01-01T00:00:00Z",
                                "comments": {"nodes": []},
                            }
                        ],
                    }
                }
            }
        }

        second_response = Mock()
        second_response.json.return_value = {
            "data": {
                "repository": {
                    "discussions": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": [
                            {
                                "id": "discussion2",
                                "number": 2,
                                "author": {"login": "user2"},
                                "updatedAt": "2023-01-02T00:00:00Z",
                                "comments": {"nodes": []},
                            }
                        ],
                    }
                }
            }
        }

        call_count = 0

        def mock_post(url: str, **kwargs) -> Mock:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return first_response
            return second_response

        with patch("requests.post", side_effect=mock_post), patch("click.echo"):
            collect_discussions(repo, contributors, headers, None)

            assert "user1" in contributors._contributors
            assert "user2" in contributors._contributors


class TestCollectContributorsCommand:
    """Test the collect_contributors CLI command."""

    def test_collect_contributors_with_repo_option(self) -> None:
        """Test command with explicit repo option."""
        runner = CliRunner()

        mock_contributors = Mock(spec=Contributors)
        mock_contributors.load.return_value = mock_contributors

        with patch("keyring.get_password", return_value="fake_token"), patch(
            "darkgray_dev_tools.darkgray_collect_contributors.Contributors.load",
            return_value=mock_contributors,
        ), patch(
            "darkgray_dev_tools.darkgray_collect_contributors.collect_issues_and_prs"
        ), patch(
            "darkgray_dev_tools.darkgray_collect_contributors.collect_discussions"
        ):
            result = runner.invoke(collect_contributors, ["--repo", "owner/repo"])

            assert result.exit_code == 0
            mock_contributors.dump.assert_called_once()

    def test_collect_contributors_with_since_option(self) -> None:
        """Test command with since date option."""
        runner = CliRunner()

        mock_contributors = Mock(spec=Contributors)
        mock_contributors.load.return_value = mock_contributors

        with patch("keyring.get_password", return_value="fake_token"), patch(
            "darkgray_dev_tools.darkgray_collect_contributors.get_repo_from_git",
            return_value="owner/repo",
        ), patch(
            "darkgray_dev_tools.darkgray_collect_contributors.Contributors.load",
            return_value=mock_contributors,
        ), patch(
            "darkgray_dev_tools.darkgray_collect_contributors.collect_issues_and_prs"
        ) as mock_issues, patch(
            "darkgray_dev_tools.darkgray_collect_contributors.collect_discussions"
        ) as mock_discussions:
            result = runner.invoke(collect_contributors, ["--since", "2023-01-01"])

            assert result.exit_code == 0
            # Verify since date was converted and passed correctly
            expected_since = datetime.fromisoformat("2023-01-01").strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            mock_issues.assert_called_once()
            mock_discussions.assert_called_once()
            # Check that since_date parameter was passed
            assert mock_issues.call_args[0][3] == expected_since
            assert mock_discussions.call_args[0][3] == expected_since

    def test_collect_contributors_no_token(self) -> None:
        """Test command when GitHub token is not available."""
        runner = CliRunner()

        with patch("keyring.get_password", return_value=None):
            result = runner.invoke(collect_contributors, ["--repo", "owner/repo"])

            assert result.exit_code == 1
            assert "GitHub API token not found" in result.output

    def test_collect_contributors_auto_detect_repo(self) -> None:
        """Test command with automatic repo detection from Git."""
        runner = CliRunner()

        mock_contributors = Mock(spec=Contributors)
        mock_contributors.load.return_value = mock_contributors

        with patch("keyring.get_password", return_value="fake_token"), patch(
            "darkgray_dev_tools.darkgray_collect_contributors.get_repo_from_git",
            return_value="auto/detected",
        ), patch(
            "darkgray_dev_tools.darkgray_collect_contributors.Contributors.load",
            return_value=mock_contributors,
        ), patch(
            "darkgray_dev_tools.darkgray_collect_contributors.collect_issues_and_prs"
        ), patch(
            "darkgray_dev_tools.darkgray_collect_contributors.collect_discussions"
        ):
            result = runner.invoke(collect_contributors, [])

            assert result.exit_code == 0
            mock_contributors.dump.assert_called_once()

    def test_collect_contributors_git_detection_fails(self) -> None:
        """Test command when Git repo detection fails."""
        runner = CliRunner()

        with patch("keyring.get_password", return_value="fake_token"), patch(
            "darkgray_dev_tools.darkgray_collect_contributors.get_repo_from_git",
            side_effect=GitHubRepoNameError(Path("/tmp")),
        ):
            result = runner.invoke(collect_contributors, [])

            assert result.exit_code != 0


class TestApiErrorHandling:
    """Test API error handling scenarios."""

    def test_collect_issues_and_prs_api_error(self) -> None:
        """Test handling of API errors in collect_issues_and_prs."""
        base_url = f"{GITHUB_API_URL}/repos/owner/repo"
        contributors = Contributors()
        headers = {"Authorization": "token fake_token"}

        with patch(
            "requests.get", side_effect=requests.RequestException("API Error")
        ), patch("click.echo"):
            with pytest.raises(requests.RequestException):
                collect_issues_and_prs(base_url, contributors, headers, None)

    def test_collect_discussions_api_error(self) -> None:
        """Test handling of API errors in collect_discussions."""
        repo = "owner/repo"
        contributors = Contributors()
        headers = {"Authorization": "token fake_token"}

        with patch(
            "requests.post", side_effect=requests.RequestException("GraphQL Error")
        ), patch("click.echo"):
            with pytest.raises(requests.RequestException):
                collect_discussions(repo, contributors, headers, None)

    def test_collect_issues_and_prs_http_error(self) -> None:
        """Test handling of HTTP errors in collect_issues_and_prs."""
        base_url = f"{GITHUB_API_URL}/repos/owner/repo"
        contributors = Contributors()
        headers = {"Authorization": "token fake_token"}

        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")

        with patch("requests.get", return_value=mock_response), patch("click.echo"):
            with pytest.raises(requests.HTTPError):
                collect_issues_and_prs(base_url, contributors, headers, None)

    def test_collect_discussions_http_error(self) -> None:
        """Test handling of HTTP errors in collect_discussions."""
        repo = "owner/repo"
        contributors = Contributors()
        headers = {"Authorization": "token fake_token"}

        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("403 Forbidden")

        with patch("requests.post", return_value=mock_response), patch("click.echo"):
            with pytest.raises(requests.HTTPError):
                collect_discussions(repo, contributors, headers, None)


class TestConstants:
    """Test module constants."""

    def test_constants_defined(self) -> None:
        """Test that all expected constants are defined."""
        assert GITHUB_API_URL == "https://api.github.com"
        assert GITHUB_GRAPHQL_URL == "https://api.github.com/graphql"
        assert REQUEST_TIMEOUT == 10
        assert HTTP_NOT_FOUND == 404
        assert UNSUPPORTED_GIT_URL_ERROR == "Unsupported Git remote URL format"
