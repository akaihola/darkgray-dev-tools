"""Suggest version limit for first matching unbounded dependency in ``pyproject.toml``.

Output in GitHub Actions log and as a GitHub Actions annotation

This script reads the ``pyproject.toml`` file and finds the first dependency without a
version limit among those mentioned on the command line (or all if none provided). It
then fetches the latest version from PyPI and suggests adding a version limit to the
dependency in the ``pyproject.toml`` file.

The script outputs a GitHub Actions annotation with the suggestion and a notice
message in the log.

The script is intended to be run in a GitHub Actions workflow.

Example usage in a GitHub Actions workflow:

```yaml
- name: Suggest dependency downgrade
  run: uvx --from=darkgray-dev-tools suggest_constraint black isort
```
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from pathlib import Path
from textwrap import dedent
from typing import cast

import click
from packaging.requirements import InvalidRequirement, Requirement
from packaging.version import Version
from pyproject_parser import PyProject


def parse_quoted_package(line: str) -> str | None:
    """Extract a quoted package name from a line in a TOML file."""
    try:
        match = re.match(r' *"(.*?)"', line)
        return Requirement(match.group(1)).name.lower() if match else None
    except (AttributeError, InvalidRequirement):
        return None


def _get_all_dependencies(pyproject: PyProject) -> list[Requirement]:
    """Get all dependencies from the project."""
    project = pyproject.project
    if not project:
        msg = "Missing [project] table in pyproject.toml"
        raise ValueError(msg)
    optional_dependencies = [
        requirement
        for requirements in project.get("optional-dependencies", {}).values()
        for requirement in requirements
    ]
    return cast(
        "list[Requirement]",
        project["dependencies"] + optional_dependencies,
    )


@click.command()
@click.argument("packages", nargs=-1)
def suggest_constraint(packages: list[str]) -> None:
    """Suggest a version constraint for a dependency in pyproject.toml."""
    # Convert all package names to lowercase for consistent comparison
    packages_to_check = [pkg.lower() for pkg in packages]
    all_dependencies = _get_all_dependencies(PyProject.load("pyproject.toml"))
    for requirement in all_dependencies:
        if packages_to_check and requirement.name.lower() not in packages_to_check:
            continue
        if any(
            specifier.operator in ["<", "<=", "~="]
            for specifier in requirement.specifier
        ):
            continue
        with Path("pyproject.toml").open(encoding="utf-8") as pyproject_file:
            line_num, line = next(
                (_, _line)
                for _, _line in enumerate(pyproject_file)
                if parse_quoted_package(_line) == requirement.name.lower()
            )
        end_column = len(line)
        column = end_column - len(line.strip())
        with urllib.request.urlopen(
            f"https://pypi.org/pypi/{requirement.name}/json"
        ) as response:
            content = json.loads(response.read().decode())
        latest_version = max(
            Version(version_str) for version_str in content["releases"]
        )

        github_step_summary_path = os.getenv("GITHUB_STEP_SUMMARY")
        if github_step_summary_path:
            Path(github_step_summary_path).write_text(
                dedent(
                    f"""
                    ### :x: Future dependency incompatibility? :x:

                    You could add a maximum version constraint for a dependency on
                    `pyproject.toml` line {line_num + 1}, e.g.
                    `{requirement.name},<={latest_version}`

                    See [#382](/akaihola/darker/issues/382)
                    for more information
                    """
                ),
                encoding="utf-8",
            )

        print(  # noqa: T201
            "::notice "
            "file=pyproject.toml,"
            f"line={line_num + 1},"
            f"col={column},"
            f"endColumn={end_column},"
            "title=Future dependency incompatibility?::"
            "You could add a maximum version constraint for a dependency "
            f"here, e.g. {requirement.name}<={latest_version}"
        )
        break

    else:
        msg_parts = [">= line not found in pyproject.toml"]
        if packages_to_check:
            msg_parts.append(f"for packages: {', '.join(packages_to_check)}")
        raise RuntimeError(" ".join(msg_parts))


if __name__ == "__main__":
    suggest_constraint()  # pylint: disable=no-value-for-parameter
