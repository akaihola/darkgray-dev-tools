"""Helper script for templating contributor lists in ``README`` and ``CONTRIBUTORS``.

Usage::

    pip install darkgray-dev-tools
    darkgray-update-contributors \
        --token=<ghp_your_github_token> \
        --modify-readme \
        --modify-contributors
    darkgray-verify-contributors

"""

# pylint: disable=too-few-public-methods,abstract-method

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache, total_ordering
from itertools import groupby
from pathlib import Path
from subprocess import run
from textwrap import dedent, indent
from typing import TYPE_CHECKING, Any, Iterable, MutableMapping, TypedDict, cast
from xml.etree import ElementTree  # nosec

import click
import defusedxml.ElementTree
from airium import Airium
from requests import codes
from requests_cache.session import CachedSession
from ruamel.yaml import YAML

from darkgray_dev_tools.exceptions import (
    GitHubApiError,
    GitHubApiNotFoundError,
    GitHubRepoNameError,
    InvalidGitHubUrlError,
    SectionNotFoundError,
    WrongContributionTypeError,
)

if TYPE_CHECKING:
    from requests.models import Response


@click.group()
def cli() -> None:
    """Create the main command group for command line parsing."""


def _load_contributor_table(path: Path) -> ElementTree.Element:
    """Load and parse the HTML contributor table as seen in ``README.rst``.

    :param path: Path to ``README.rst``
    :return: The parsed HTML as an element tree

    """
    readme = Path(path).read_text(encoding="utf-8")
    match = re.search(r"<table>.*</table>", readme, re.DOTALL)
    if not match:
        section = "contributors HTML table"
        raise SectionNotFoundError(section, "README.rst")
    contributor_table = match.group(0)
    contributor_table = contributor_table.replace("&", "&amp;")
    try:
        return cast(
            ElementTree.Element, defusedxml.ElementTree.fromstring(contributor_table)
        )
    except ElementTree.ParseError as exc_info:
        linenum, column = exc_info.position
        line = contributor_table.splitlines()[linenum - 1]
        click.echo(line, err=True)
        click.echo((column - 1) * " ", nl=False, err=True)
        click.echo("^", err=True)
        raise


def verify_contribution_type(url: str, contribution_type: str, *args: str) -> None:
    """Raise an exception if the contribution type for the URL isn't valid.

    :param url: The URL of the search for the author's contributions
    :param contribution_type: The name of the contribution type
    :param args: Valid contribution types for this type of URL path
    :raises RuntimeError: Raised if the contribution type isn't valid

    """
    valid_contribution_types = args
    if contribution_type not in valid_contribution_types:
        raise WrongContributionTypeError(
            url, contribution_type, valid_contribution_types
        )


@lru_cache(maxsize=1)
def get_github_repository() -> str:
    """Get the name of the GitHub repository from the current directory.

    :return: The name of the GitHub repository, including the owner

    """
    # Call `git remote get-url origin` to get the URL of the `origin` remote.
    # Then extract the repository name from the URL.
    result = run(
        ["git", "remote", "get-url", "origin"],  # noqa: S603,S607
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise GitHubRepoNameError(Path.cwd())
    return result.stdout.split(":")[-1].split(".")[0]


CONTRIBUTION_TYPE_VERIFICATION = {
    "{repo}/issues?q=author%3A": (["Bug reports"], "issues"),
    "{repo}/commits?author=": (["Code", "Documentation", "Maintenance"], "commits"),
    "{repo}/pulls?q=is%3Apr+reviewed-by%3A": (
        ["Reviewed Pull Requests"],
        "pulls-reviewed",
    ),
    "{repo}/pulls?q=is%3Apr+author%3A": (["Code", "Documentation"], "pulls-author"),
    "{repo}/search?q=commenter": (
        ["Bug reports", "Reviewed Pull Requests"],
        "search-comments",
    ),
    "{repo}/search?q=": (["Bug reports", "Answering Questions"], "search"),
    "{repo}/discussions?discussions_q=": (["Bug reports"], "search-discussions"),
    "conda-forge/staged-recipes/search?q={repo_name}&type=issues&author=": (
        ["Code"],
        "conda-issues",
    ),
    "conda-forge/{repo_name}-feedstock/search?q=": (["Code"], "feedstock-issues"),
}


@cli.command()
def verify() -> None:
    """Verify generated contributor table HTML in ``README.rst``.

    Output the corresponding YAML source.

    """
    repo = get_github_repository()
    repo_name = repo.split("/")[1]
    users = {}
    for td_user in _load_contributor_table(Path("README.rst")).findall("tr/td"):
        profile_link = td_user[0]
        username = profile_link.attrib["href"].rsplit("/", 1)[-1]
        avatar_alt = profile_link[0].attrib["alt"]
        if username != avatar_alt[1:]:
            click.echo(f"@{username} != {avatar_alt}")
        contributions = []
        for contribution_link in td_user.findall("a")[1:]:
            url = contribution_link.attrib["href"]
            if not url.startswith("https://github.com/"):
                raise InvalidGitHubUrlError(url)
            path = url[19:]
            contribution_type = contribution_link.attrib["title"]
            for path_pattern, (
                valid_types,
                link_type,
            ) in CONTRIBUTION_TYPE_VERIFICATION.items():
                if path.startswith(path_pattern.format(repo=repo, repo_name=repo_name)):
                    verify_contribution_type(url, contribution_type, *valid_types)
                    contributions.append(
                        {"type": contribution_type, "link_type": link_type}
                    )
                    break
            else:
                raise AssertionError((username, path, contribution_type))
        users[username] = contributions
    yaml = YAML(typ="safe", pure=True)
    click.echo(yaml.dump(users))


CONTRIBUTION_SYMBOLS = {
    "Bug reports": "🐛",
    "Code": "💻",
    "Documentation": "📖",
    "Reviewed Pull Requests": "👀",
    "Answering Questions": "💬",
    "Maintenance": "🚧",
}
CONTRIBUTION_LINKS = {
    "issues": "{repo}/issues?q=author%3A{{username}}",
    "commits": "{repo}/commits?author={{username}}",
    "pulls-reviewed": "{repo}/pulls?q=is%3Apr+reviewed-by%3A{{username}}",
    "pulls-author": "{repo}/pulls?q=is%3Apr+author%3A{{username}}",
    "search": "{repo}/search?q={{username}}",
    "search-comments": "{repo}/search?q=commenter%3A{{username}}&type=issues",
    "search-discussions": "{repo}/discussions?discussions_q=author%3A{{username}}",
    "conda-issues": (
        "conda-forge/staged-recipes/search"
        "?q={repo_name}&type=issues&author={{username}}"
    ),
    "feedstock-issues": (
        "conda-forge/{repo_name}-feedstock/search"
        "?q={repo_name}+author%3A{{username}}&type=issues"
    ),
}


class GitHubSession(CachedSession):
    """Caching HTTP request session with useful defaults.

    - GitHub authorization header generated from a given token
    - Accept HTTP paths and prefix them with the GitHub API server name

    """

    def __init__(  # type: ignore[misc]
        self, token: str, *args: Any, **kwargs: Any  # noqa: ANN401
    ) -> None:
        """Create the cached requests session with the given GitHub token."""
        super().__init__(*args, **kwargs)
        self.token = token

    def request(  # type: ignore[override,misc]  # pylint: disable=arguments-differ
        self,
        method: str,
        url: str,
        headers: MutableMapping[str, str] | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> Response:
        """Query GitHub API with authorization, caching and host auto-fill-in.

        Complete the request information with the GitHub API HTTP scheme and hostname,
        and add a GitHub authorization header. Serve requests from the cache if they
        match.

        :param method: method for the new `Request` object.
        :param url: URL for the new `Request` object.
        :param headers: (optional) dictionary of HTTP Headers to send with the
                        `Request`.
        :return: The response object

        """
        hdrs = {"Authorization": f"token {self.token}", **(headers or {})}
        if url.startswith("/"):
            url = f"https://api.github.com{url}"
        response = super().request(method, url, headers=hdrs, **kwargs)
        if (
            response.status_code == codes.not_found
            and response.json()["message"] == "Not Found"
        ):
            raise GitHubApiNotFoundError
        if response.status_code != codes.ok:
            raise GitHubApiError(response)
        return response


AVATAR_URL_TEMPLATE = "https://avatars.githubusercontent.com/u/{}?v=3"


ALL_CONTRIBUTORS_START = (
    "   <!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section\n"
    "        This is automatically generated. Please update `contributors.yaml` and\n"
    "        see `CONTRIBUTING.rst` for how to re-generate this table. -->\n"
)
ALL_CONTRIBUTORS_END = "   <!-- ALL-CONTRIBUTORS-LIST:END -->"


@cli.command()
@click.option("--token")
@click.option("-r/+r", "--modify-readme/--no-modify-readme", default=False)
@click.option("-c/+c", "--modify-contributors/--no-modify-contributors", default=False)
def update(
    token: str, modify_readme: bool, modify_contributors: bool  # noqa: FBT001
) -> None:
    """Generate an HTML table for ``README.rst`` and a list for ``CONTRIBUTORS.rst``.

    These contributor lists are generated based on ``contributors.yaml``.

    :param token: The GitHub authorization token for avoiding throttling

    """
    with Path("contributors.yaml").open(encoding="utf-8") as yaml_file:
        yaml = YAML(typ="safe", pure=True)
        users_and_contributions: dict[str, list[Contribution]] = {
            login: [Contribution(**c) for c in contributions]
            for login, contributions in yaml.load(yaml_file).items()
        }
    session = GitHubSession(token)
    users = join_github_users_with_contributions(users_and_contributions, session)
    doc = render_html(users)
    click.echo(doc)
    contributor_list = render_contributor_list(users)
    contributors_text = "\n".join(sorted(contributor_list, key=lambda s: s.lower()))
    click.echo(contributors_text)
    if modify_readme:
        write_readme(doc)
    if modify_contributors:
        write_contributors(contributors_text)


@dataclass
class Contribution:
    """A type of contribution from a user."""

    type: str
    link_type: str

    def github_search_link(self, login: str) -> str:
        """Return a link to a GitHub search for a user's contributions.

        :param login: The GitHub username for the user
        :return: A URL link to a GitHub search

        """
        link_template = CONTRIBUTION_LINKS[self.link_type].format(
            repo=get_github_repository(),
            repo_name=get_github_repository().split("/")[1],
        )
        return f"https://github.com/{link_template}".format(username=login)


class GitHubUser(TypedDict):
    """User record as returned by GitHub API ``/users/`` endpoint."""

    id: int
    name: str | None
    login: str


@dataclass
@total_ordering
class Contributor:
    """GitHub user information coupled with a list of repository contributions."""

    user_id: int
    name: str | None
    login: str
    contributions: list[Contribution]

    def __eq__(self, other: object) -> bool:
        """Return ``True`` if the object is equal to another `Contributor` object."""
        if not isinstance(other, Contributor):
            return NotImplemented
        return self.login == other.login

    def __lt__(self, other: object) -> bool:
        """Return ``True`` if a contributor is alphabetically earlier than another."""
        if not isinstance(other, Contributor):
            return NotImplemented
        return self.display_name < other.display_name

    @property
    def avatar_url(self) -> str:
        """Return a link to the user's avatar image on GitHub.

        :return: A URL to the avatar image

        """
        return AVATAR_URL_TEMPLATE.format(self.user_id)

    @property
    def display_name(self) -> str:
        """A user's display name - either the full name or the login username.

        :return: The user's display name

        """
        return self.name or self.login


RTL_OVERRIDE = "\u202e"


def _normalize_rtl_override(text: str | None) -> str | None:
    """Normalize text surrounded by right-to-left override characters.

    :param text: Text to normalize
    :return: Normalized text

    """
    if not text:
        return text
    if text[0] != RTL_OVERRIDE or text[-1] != RTL_OVERRIDE:
        return text
    return text[-2:0:-1]


DELETED_USERS: dict[str, GitHubUser] = {
    "qubidt": {"id": 6306455, "name": "Bao", "login": "qubidt"},
}


def join_github_users_with_contributions(
    users_and_contributions: dict[str, list[Contribution]],
    session: GitHubSession,
) -> list[Contributor]:
    """Join GitHub user information with their repository contributions.

    :param users_and_contributions: GitHub logins and their repository contributions
    :param session: A GitHub API HTTP session
    :return: GitHub user info and the user's repository contributions merged together

    """
    users: list[Contributor] = []
    for username, contributions in users_and_contributions.items():
        try:
            gh_user = cast(GitHubUser, session.get(f"/users/{username}").json())
        except GitHubApiNotFoundError:
            gh_user = DELETED_USERS[username]
        name = _normalize_rtl_override(gh_user["name"])
        try:
            contributor = Contributor(
                gh_user["id"], name, gh_user["login"], contributions
            )
        except KeyError:
            click.echo(gh_user, err=True)
            raise
        users.append(contributor)
    return users


def make_rows(users: list[Contributor], columns: int) -> list[list[Contributor]]:
    """Partition users into table rows.

    :param users: User and contribution information for each contributor
    :param columns: Number of columns in the table
    :return: A list of contributor objects for each table row

    """
    users_and_contributions_by_row = groupby(
        enumerate(sorted(users)), lambda item: item[0] // columns
    )
    return [
        [user for _, user in rownum_and_users]
        for _, rownum_and_users in users_and_contributions_by_row
    ]


def render_html(users: list[Contributor]) -> Airium:
    """Convert users and contributions into an HTML table for ``README.rst``.

    :param users: GitHub user records and the users' contributions to the repository
    :return: An Airium document describing the HTML table

    """
    doc = Airium()
    rows_of_users: list[list[Contributor]] = make_rows(users, columns=6)
    with doc.table():
        for row_of_users in rows_of_users:
            with doc.tr():
                for user in row_of_users:
                    with doc.td(align="center"):
                        with doc.a(href=f"https://github.com/{user.login}"):
                            doc.img(
                                src=user.avatar_url,
                                width="100px;",
                                alt=f"@{user.login}",
                            )
                            doc.br()
                            doc.sub().b(_t=user.display_name)
                        doc.br()
                        for contribution in user.contributions:
                            doc.a(
                                href=contribution.github_search_link(user.login),
                                title=contribution.type,
                                _t=CONTRIBUTION_SYMBOLS[contribution.type],
                            )
    return doc


def render_contributor_list(users: Iterable[Contributor]) -> list[str]:
    """Render a list of contributors for ``CONTRIBUTORS.rst``.

    :param users_and_contributions: Data from ``contributors.yaml``
    :return: A list of strings to go into ``CONTRIBUTORS.rst``

    """
    return [f"- {user.display_name} (@{user.login})" for user in users]


def write_readme(doc: Airium) -> None:
    """Write an updated ``README.rst`` file.

    :param doc: The generated contributors HTML table

    """
    readme_content = Path("README.rst").read_text(encoding="utf-8")
    start_index = readme_content.index(ALL_CONTRIBUTORS_START) + len(
        ALL_CONTRIBUTORS_START
    )
    end_index = readme_content.index(ALL_CONTRIBUTORS_END)
    before = readme_content[:start_index]
    after = readme_content[end_index:]
    table = indent(str(doc), "   ")
    new_readme_content = f"{before}{table}{after}"
    Path("README.rst").write_text(new_readme_content, encoding="utf-8")


def write_contributors(text: str) -> None:
    """Write an updated ``CONTRIBUTORS.rst`` file.

    :param text: The generated list of contributors using reStructuredText markup

    """
    project = get_github_repository().split("/")[1].title()
    eqsigns = "=" * len(project)
    Path("CONTRIBUTORS.rst").write_text(
        dedent(
            f"""\
            ================={eqsigns}=
             Contributors to {project}
            ================={eqsigns}=

            (in alphabetic order and with GitHub handles)

            .. This file is automatically generated. Please update ``contributors.yaml``
               instead and see ``CONTRIBUTING.rst`` for instructions on how to update
               this file.

            {{}}
            """
        ).format(text),
        encoding="utf-8",
    )


if __name__ == "__main__":
    cli()
