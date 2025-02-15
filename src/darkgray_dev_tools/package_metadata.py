"""Module for getting metadata about a package."""

from urllib.parse import urlsplit

from pyproject_parser import PyProject
from setuptools.config import setupcfg


def is_valid_github_repo_url(url: str) -> bool:
    """Check if a URL is a valid GitHub repository URL.

    :param url: The URL to check
    :return: True if the URL is a valid GitHub repository URL, False otherwise

    """
    # split the URL into parts
    parsed = urlsplit(url)
    if parsed.scheme != "https":
        return False
    if parsed.netloc != "github.com":
        return False
    # check if the path contains two parts
    path_parts = [part for part in parsed.path.split("/") if part]
    return len(path_parts) == 2 and not path_parts[1].endswith(".git")  # noqa: PLR2004


def get_repo_url() -> str:
    """Get the URL of the repository from the setup configuration file.

    Supports repositories which have a ``pyproject.toml`` file, and use one of the
    following build systems:
    - `setuptools` with a ``setup.cfg`` file
    - PEP621 compliant systems (e.g. Flit) with ``project.Home`` in
      ``pyproject.toml`` pointing to the repository URL

    :return: The URL of the repository

    """
    pyproject = PyProject.load("pyproject.toml")
    if not pyproject.project:
        message = "No [project] information found in pyproject.toml"
        raise ValueError(message)
    url_candidates: dict[str, str] = pyproject.project["urls"].copy()
    for url_key in ["Source Code", "Homepage", "Home"]:
        if url_key not in url_candidates:
            continue
        url = url_candidates[url_key]
        if is_valid_github_repo_url(url):
            return url
        del url_candidates[url_key]
    for url in url_candidates.values():
        if is_valid_github_repo_url(url):
            return url
    metadata: dict[str, str] = setupcfg.read_configuration("setup.cfg")["metadata"]
    return metadata["url"]
