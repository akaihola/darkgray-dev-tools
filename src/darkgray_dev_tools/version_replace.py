"""Replace old versions and milestones in files with new versions and milestones."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from re import Match
from typing import TYPE_CHECKING, TypedDict

import click

from darkgray_dev_tools.exceptions import NoMatchError
from darkgray_dev_tools.milestones import (
    get_milestone_numbers,
    get_next_milestone_version,
)
from darkgray_dev_tools.versions import get_current_version, get_next_version

if TYPE_CHECKING:
    from packaging.version import Version


class PatternDict(TypedDict):
    r"""Patterns for old and new version and the milestone number for the new version.

    Example:
    -------
    >>> patterns: PatternDict = {
    ...     "any_version": r"\d+(?:\.\d+)*",
    ...     "old_version": r"1\.0",
    ...     "new_version": r"1\.1",
    ...     "any_milestone": r"\d+",
    ... }

    """

    any_version: str
    old_version: str
    new_version: str
    any_milestone: str


class ReplacementDict(TypedDict):
    """Replacement strings of new and next version and milestone num for next version.

    Example:
    -------
    >>> replacement: ReplacementDict = {
    ...     "new_version": "1.1",
    ...     "next_version": "2.0",
    ...     "next_milestone": "23",
    ... }

    """

    new_version: str
    next_version: str
    next_milestone: str


if sys.version_info >= (3, 9):
    PATTERN_NAMES = PatternDict.__required_keys__  # type: ignore[attr-defined]  # pylint: disable=no-member
    REPLACEMENT_NAMES = ReplacementDict.__required_keys__  # type: ignore[attr-defined]  # pylint: disable=no-member
else:
    PATTERN_NAMES = PatternDict.__annotations__  # pylint: disable=no-member
    REPLACEMENT_NAMES = ReplacementDict.__annotations__  # pylint: disable=no-member


def lookup_patterns(
    template_match: Match[str], patterns: PatternDict, replacements: ReplacementDict
) -> tuple[str, str]:
    r"""Look up the search pattern and replacement for the given search->replace names.

    `patterns` must contain regular expressions for finding the old version, the new
    version, and the milestone number corresponding to the new version.

    `replacements` must contain strings for the new version number, the next version
    number after that, and the milestone number corresponding to the next version
    number.

    This function accepts a regular expression match object for a `{OLD->NEW}` string,
    finds the pattern corresponding to the `OLD` string from `patterns`, finds the
    replacement corresponding to the `NEW` string form `replacements`, and returns them
    both.

    Example:
    -------
    >>> patterns_ = {"new_version": r"1\.1"}
    >>> replacements_ = {"next_version": "2.0"}
    >>> template_match_ = re.match(r"(.*)->(.*)", "new_version->next_version")
    >>> lookup_patterns(template_match_, patterns_, replacements_)
    ('1\\.1', '2.0')

    :param template_match: The match object with pattern name and replacement name as
                           capture groups
    :param patterns: The regular expression patterns corresponding to pattern names
    :param replacements: The replacement strings corresponding to replacement names
    :raises RuntimeError: Raised if pattern or replacement names are unknown
    :return: The matching regular expression pattern and replacement string

    """
    current_pattern_name, replacement_name = template_match.groups()
    # example:: template_match.groups() == ("any_milestone", "next_milestone")
    if current_pattern_name not in PATTERN_NAMES:
        message = (
            f"Pattern name {current_pattern_name!r} for a current value is"
            f" unknown. Valid pattern names: {PATTERN_NAMES}"
        )
        raise RuntimeError(message)
    current_pattern = patterns[current_pattern_name]  # type: ignore[literal-required]
    # example:: current_pattern == "14"
    if replacement_name not in REPLACEMENT_NAMES:
        message = (
            f"Replacement name {replacement_name!r} is unknown. Valid replacement"
            f" names: {REPLACEMENT_NAMES}"
        )
        raise RuntimeError(message)
    replacement = replacements[replacement_name]  # type: ignore[literal-required]
    # example:: replacement == "15"
    return current_pattern, replacement


def replace_spans(spans: list[tuple[int, int]], replacement: str, content: str) -> str:
    """Replace given spans in a string with the desired replacement string.

    :param spans: The spans to replace
    :param replacement: The string to use as the replacement
    :param content: The content to replace the span in
    :return: The result after the replacement

    >>> replace_spans([(2, 4), (6, 8)], "BAR", "__FU__FU__")
    '__BAR__BAR__'

    """
    parts = []
    for (_, end1), (start2, end2) in zip(
        [(..., 0), *spans], [*spans, (len(content), ...)]
    ):
        parts.append(content[end1:start2])
        if end2 is not ...:
            parts.append(replacement)
    return "".join(parts)


def replace_group_1(pattern: str, replacement: str, content: str, path: str) -> str:
    """Replace the first capture group of a regex pattern with the given string.

    Raises an exception if the regular expression doesn't match.

    :param pattern: The regular expression pattern with at least one capture group
    :param replacement: The string to replace the capture group with
    :param content: The content to search and do the replacement in
    :param path: The originating file path for the content. Only used in the exception
                 message if the regular expression doesn't find any matches.
    :raises NoMatchError: Raised if the regular expression doesn't find any matches
    :return: The resulting content after the replacement

    """
    matches = re.finditer(pattern, content, flags=re.MULTILINE)
    if not matches:
        raise NoMatchError(pattern, path)
    return replace_spans([match.span(1) for match in matches], replacement, content)


def get_replacements(
    patterns: dict[str, set[str]],
    *,
    increment_major: bool,
    increment_minor: bool,
    token: str | None = None,
    dry_run: bool = False,
) -> tuple[PatternDict, ReplacementDict, Version]:
    """Return search patterns and replacements for version numbers and milestones.

    Gets the current version from `version.py` and the milestone numbers from the GitHub
    API. Based on these, builds the search patterns for the old and new version numbers
    and the milestone number of the new version, as well as replacement strings for the
    new and next version numbers and the milestone number of the next version.

    :param increment_major: `True` to increment the major version number
    :param increment_minor: `True` to increment the minor version number
    :param token: The GitHub access token to use, or `None` to use none
    :param dry_run: `True` if running in dry-run mode
    :param patterns: Regular expression patterns for finding version numbers in files
    :return: Patterns, replacements and the new version number

    """
    version_py_path = next(
        path
        for path, patterns in patterns.items()
        if path.endswith(".py")
        and any("__version__" in pattern for pattern in patterns)
    )
    old_version = get_current_version(version_py_path, patterns)
    new_version = get_next_version(
        old_version, increment_major=increment_major, increment_minor=increment_minor
    )
    milestone_numbers = get_milestone_numbers(token)
    next_version = get_next_milestone_version(
        new_version, milestone_numbers, dry_run=dry_run
    )
    if dry_run:
        milestone_numbers.setdefault(next_version, "MISSING_MILESTONE")
    patterns: PatternDict = {
        "any_version": r"\d+(?:\.\d+)*",
        "old_version": re.escape(str(old_version)),
        "new_version": re.escape(str(new_version)),
        "any_milestone": r"\d+",
    }
    replacements: ReplacementDict = {
        "new_version": str(new_version),
        "next_version": str(next_version),
        "next_milestone": milestone_numbers[next_version],
    }
    return patterns, replacements, new_version


CAPTURE_RE = re.compile(r"\{(\w+)->(\w+)}")


def do_replacements(
    pattern_templates_for_files: dict[str, set[str]],
    patterns: PatternDict,
    replacements: dict[str, str],
    *,
    dry_run: bool,
) -> None:
    """Replace old versions and milestones in files with new versions and milestones.

    :param dry_run: ``True`` to just print the result
    :param pattern_templates_for_files: The file paths and the pattern templates to use
    :param patterns: Regular expression patterns for finding old version and milestone
                     numbers in files, based on the templates above
    :param replacements: Replacement strings with new version and milestone numbers
    :raises NoMatchError: Raised if a pattern template isn't found in a file

    """
    for path_str, pattern_templates in pattern_templates_for_files.items():
        path = Path(path_str)
        content = path.read_text(encoding="utf-8")
        for pattern_template in pattern_templates:
            # example:: pattern_template == r"darker/{any_milestone->next_milestone}"
            template_match = CAPTURE_RE.search(pattern_template)
            if not template_match:
                raise NoMatchError(CAPTURE_RE.pattern, pattern_template)
            current_pattern, replacement = lookup_patterns(
                template_match, patterns, replacements
            )
            # example: current_pattern == "14", replacement == "15"
            pattern = replace_spans(
                [template_match.span()], f"({current_pattern})", pattern_template
            )
            # example:: pattern = r"darker/(14)"
            content = replace_group_1(pattern, replacement, content, path=path_str)
        if dry_run:
            click.echo(f"\n######## {path_str} ########\n")
            click.echo(content)
        else:
            path.write_text(content, encoding="utf-8")
