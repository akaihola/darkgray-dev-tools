"""Helper script for templating contributor lists in ``README`` and ``CONTRIBUTORS``.

Usage::

    pip install darkgray-dev-tools
    darkgray-update-contributors \
        --token=<ghp_your_github_token> \
        --modify-readme \
        --modify-contributors

"""

# pylint: disable=too-few-public-methods,abstract-method

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache, total_ordering
from itertools import groupby
from pathlib import Path
from subprocess import run
from textwrap import dedent, indent
from typing import (
    TYPE_CHECKING,
    Any,
    Iterable,
    MutableMapping,
    Protocol,
    TypedDict,
    cast,
)
from urllib.parse import urlencode, urljoin

import click
from airium import Airium
from requests import codes
from requests_cache.session import CachedSession
from ruamel.yaml import YAML

from darkgray_dev_tools.exceptions import (
    GitHubApiError,
    GitHubApiNotFoundError,
    GitHubRepoNameError,
)

if TYPE_CHECKING:
    from requests.models import Response


@click.group()
def cli() -> None:
    """Create the main command group for command line parsing."""


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


@dataclass
class FormatAndJoin:
    """Format a delimited list from the given key in the keyword arguments.

    >>> fmt = FormatAndJoin(" OR ", "repos", "repo:{}")
    >>> print(fmt.format(repos=["me/repo1", "me.repo2"]))
    repo:me/repo1 OR repo:me.repo2

    """

    sep: str
    key: str
    fmt: str

    def format(self, **kwargs: list[SupportsFormat]) -> str:
        """Emulate the `str.format` method.

        :param kwargs: The keyword arguments, containing the key to get the list of
                       items from
        :return: A string with the formatted items joined by the separator

        """
        items = kwargs[self.key]
        formatted_items = (self.fmt.format(item) for item in items)
        return self.sep.join(formatted_items)


class SupportsFormat(Protocol):
    """Protocol for objects that support a `str.format` like formatting method.

    This is used only for type checking with Mypy.

    """

    def format(self, **kwargs: Any) -> str:  # type: ignore[misc]  # noqa: ANN401
        """Signature for the ``format`` method."""


class UrlPath:
    """A URL path with query parameters as lists of format strings.

    >>> p = UrlPath(
    ...     "search",
    ...     q=[FormatAndJoin(" ", "repos", "repo:{}"), " who:me"],
    ...     type=["issues"]
    ... )
    >>> print(p.render("https://github.com", repos=["me/repo1", "me/repo2"]))
    https://github.com/search?q=repo%3Ame%2Frepo1+repo%3Ame%2Frepo2+who%3Ame&type=issues

    """

    def __init__(self, path: str, **query_params: list[SupportsFormat]) -> None:
        """Create a new URL path with query parameters.

        :param path: The URL path, e.g. ``search``
        :param query_params: Query parameters as lists of format strings

        """
        self.path = path
        self.query_params = query_params

    def render(  # type: ignore[misc]
        self, base_url: str, **kwargs: Any  # noqa: ANN401
    ) -> str:
        """Render the URL path with the given keyword arguments.

        :param base_url: The base URL path, e.g. ``https://github.com/``
        :param kwargs: The keyword arguments to format the query parameters with
        :return: The rendered URL path

        """
        path = urljoin(base_url, self.path)
        query_params = [
            (key, "".join(part.format(**kwargs) for part in fmt))
            for key, fmt in self.query_params.items()
        ]
        encoded_query_params = urlencode(query_params)
        return f"{path}?{encoded_query_params}"


CONTRIBUTION_SYMBOLS = {
    "Bug reports": "🐛",
    "Code": "💻",
    "Documentation": "📖",
    "Reviewed Pull Requests": "👀",
    "Answering Questions": "💬",
    "Maintenance": "🚧",
}
CONTRIBUTION_LINKS = {
    "issues": UrlPath(
        "search",
        q=[FormatAndJoin(" ", "repos", "repo:{}"), " author:{username}"],
        type=["issues"],
    ),
    "commits": UrlPath(
        "search",
        q=[FormatAndJoin(" ", "repos", "repo:{}"), " author:{username}"],
        type=["commits"],
    ),
    "pulls-reviewed": UrlPath(
        "search",
        q=[FormatAndJoin(" ", "repos", "repo:{}"), " reviewed-by:{username}"],
        type=["pullrequests"],
    ),
    "pulls-author": UrlPath(
        "search",
        q=[FormatAndJoin(" ", "repos", "repo:{}"), " author:{username}"],
        type=["pullrequests"],
    ),
    "search": UrlPath(
        "search",
        q=[FormatAndJoin(" ", "repos", "repo:{}"), " {username}"],
    ),
    "search-comments": UrlPath(
        "search",
        q=[FormatAndJoin(" ", "repos", "repo:{}"), " commenter:{username}"],
        type=["issues"],
    ),
    "search-discussions": UrlPath(
        "search",
        q=[FormatAndJoin(" ", "repos", "repo:{}"), " involves:{username}"],
        type=["discussions"],
    ),
    "conda-issues": UrlPath(
        "search",
        q=[
            "repo:conda-forge/staged-recipes ",
            FormatAndJoin(" OR ", "repos", "{}"),
            " involves:{username}",
        ],
        type=["pullrequests"],
    ),
    "feedstock-issues": UrlPath(
        "search",
        q=[
            FormatAndJoin(" OR ", "repo_names", "repo:conda-forge/{}-feedstock"),
            " involves:{username}",
        ],
        type=["issues"],
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
        *configs, contributors_src = yaml.load_all(yaml_file)
        if len(configs) > 1:
            message = "Too many YAML documents in contributors.yaml"
            raise ValueError(message)
        config = Configuration(**(configs[0] if configs else {}))
        users_and_contributions: dict[str, list[Contribution]] = {
            login: [Contribution(**c) for c in contributions]
            for login, contributions in contributors_src.items()
        }
    session = GitHubSession(token)
    users = join_github_users_with_contributions(users_and_contributions, session)
    doc = render_html(users, config)
    click.echo(doc)
    contributor_list = render_contributor_list(users)
    contributors_text = "\n".join(sorted(contributor_list, key=lambda s: s.lower()))
    click.echo(contributors_text)
    if modify_readme:
        write_readme(doc)
    if modify_contributors:
        write_contributors(contributors_text)


def get_cwd_repository() -> list[str]:
    """Get the GitHub repository name from the current working directory.

    :return: The GitHub repository name

    """
    return [get_github_repository()]


@dataclass
class Configuration:
    """Configuration for updating contributors."""

    repositories: list[str] = field(default_factory=get_cwd_repository)


@dataclass
class Contribution:
    """A type of contribution from a user."""

    type: str
    link_type: str

    def github_search_link(self, login: str, config: Configuration) -> str:
        """Return a link to a GitHub search for a user's contributions.

        :param login: The GitHub username for the user
        :param config: Configuration for updating contributors
        :return: A URL link to a GitHub search

        """
        contribution_link = CONTRIBUTION_LINKS[self.link_type]
        return contribution_link.render(
            "https://github.com/",
            repos=config.repositories,
            repo_names=[repo.split("/")[1] for repo in config.repositories],
            username=login,
        )


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


def render_html(users: list[Contributor], config: Configuration) -> Airium:
    """Convert users and contributions into an HTML table for ``README.rst``.

    :param users: GitHub user records and the users' contributions to the repository
    :param config: Configuration for updating contributors
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
                                href=contribution.github_search_link(
                                    user.login, config
                                ),
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
