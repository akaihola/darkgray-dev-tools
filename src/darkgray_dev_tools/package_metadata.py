from distutils.errors import DistutilsFileError

from pyproject_parser import PyProject
from setuptools.config import setupcfg


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
    if "setuptools" in pyproject.build_system["requires"]:
        return setupcfg.read_configuration("setup.cfg")["metadata"]["url"]
    return pyproject.project["urls"]["Home"]
