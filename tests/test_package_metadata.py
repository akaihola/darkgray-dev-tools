"""Tests for the `darkgray_dev_tools.package_metadata` module."""

import pytest

from darkgray_dev_tools.package_metadata import is_valid_github_repo_url


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        # Valid GitHub URLs
        ("https://github.com/user/repo", True),
        ("https://github.com/user/repo/", True),
        ("https://github.com/Company-Login/Project.Name/", True),

        # Invalid URLs
        ("http://github.com/user/repo", False),          # Wrong scheme
        ("https://example.com/user/repo", False),        # Wrong domain
        ("https://github.com/user", False),              # Only 1 path part
        ("https://github.com/user/repo/issues", False),  # 3 path parts
        ("https://github.com/", False),                  # No path parts
        ("ftp://github.com/user/repo", False),           # Non-http scheme
        ("https://github.com/user/repo.git", False),     # .git extension
        ("https://api.github.com/user/repo", False),     # API subdomain
    ]
)
def test_is_valid_github_repo_url(url: str, *, expected: bool) -> None:
    """Test URL validation for GitHub repository URLs."""
    assert is_valid_github_repo_url(url) is expected
