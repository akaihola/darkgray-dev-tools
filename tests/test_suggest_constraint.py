"""Tests for ``darkgray_dev_tools.suggest_constraint``."""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, mock_open, patch

import pytest
from click.testing import CliRunner
from packaging.requirements import Requirement

from darkgray_dev_tools.darkgray_suggest_constraint import (
    parse_quoted_package,
    suggest_constraint,
)


@pytest.mark.parametrize(
    ("input_str", "expected"),
    [
        ('"package>=1.0.0"', "package"),
        ('    "package>=1.0.0"', "package"),
        ('"package"', "package"),
        ("package>=1.0.0", None),
        ('""', None),
    ],
)
def test_parse_quoted_package(input_str: str, expected: str | None) -> None:
    """Test the parse_quoted_package function with different input formats."""
    assert parse_quoted_package(input_str) == expected


# Sample pyproject.toml content with different constraint patterns
MOCK_PYPROJECT_CONTENT = """
[project]
dependencies = [
    "airium>=0.2.6",
    "click>=8.0.0",
    "keyring",
    "pyproject-parser>=0.13.0b1",
    "requests_cache>=0.7",
    "ruamel.yaml>=0.15.78,<0.17",
    "setuptools>=61",
    "gql>=3.0.0",
]
"""


@pytest.mark.parametrize(
    ("packages", "expected_output", "expected_exit_code"),
    [
        # Test with no arguments (should find the first without upper bound - airium)
        ([], "airium<=2.0.0", 0),
        # Test with keyring package (no constraints)
        (["keyring"], "keyring<=2.0.0", 0),
        # Test with a package that has only a lower bound
        (["airium"], "airium<=2.0.0", 0),
        # Test with a package that has an upper bound
        (["ruamel.yaml"], "", 1),
        # Test with multiple packages, one has upper bound, one doesn't
        (["airium", "ruamel.yaml"], "airium<=2.0.0", 0),
        # Test with a non-existent package
        (["nonexistent"], "", 1),
    ],
)
def test_suggest_constraint(
    packages: list[str],
    expected_output: str,
    expected_exit_code: int,
) -> None:
    """Test the suggest_constraint function with different package combinations."""
    runner = CliRunner()

    # Mock the PyPI response to return a specific version
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(
        {"releases": {"1.0.0": {}, "2.0.0": {}}}
    ).encode()
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=None)

    # Mock PyProject to return specific requirements
    mock_pyproject = MagicMock()
    mock_pyproject.project = {
        "dependencies": [
            Requirement("airium>=0.2.6"),
            Requirement("click>=8.0.0"),
            Requirement("keyring"),
            Requirement("pyproject-parser>=0.13.0b1"),
            Requirement("requests_cache>=0.7"),
            Requirement("ruamel.yaml>=0.15.78,<0.17"),
            Requirement("setuptools>=61"),
            Requirement("gql>=3.0.0"),
        ],
        "optional-dependencies": {},
    }

    # Set up patches
    with patch("pathlib.Path.open", mock_open(read_data=MOCK_PYPROJECT_CONTENT)), patch(
        "pyproject_parser.PyProject.load", return_value=mock_pyproject
    ), patch("urllib.request.urlopen", return_value=mock_response), patch.dict(
        os.environ, {"GITHUB_STEP_SUMMARY": "mock_summary.md"}
    ), patch("pathlib.Path.write_text") as mock_write:
        # Run test with the provided parameters
        result = runner.invoke(suggest_constraint, packages)
        assert result.exit_code == expected_exit_code

        if expected_output:
            assert expected_output in result.output
            assert "::notice" in result.output
            mock_write.assert_called_once()
        else:
            assert result.output == ""
            mock_write.assert_not_called()
