Unreleased_
===========

These features will be included in the next release:

Added
-----

Fixed
-----


0.3.0_ - 2025-08-25
===================

Added
-----
- ``suggest_constraint`` command to suggest a new maximum version constraint for a
  dependency.

Fixed
-----
- Support ``[dependency-groups]`` in ``pyproject.toml`` by upgrading to
  ``pyproject-parser`` 0.13.0b1.
- Ignore the ``github-actions`` user for issues, discussions and comments in
  ``darkgray_collect_contributors``.


0.2.0_ - 2024-09-29
===================

Added
-----
- New ``darkgray_show_reviews`` command to display timestamps and reviewers of recent
  approved pull request reviews. The command supports options for including repository
  owner reviews and generating monthly statistics.
- Added ``darkgray_collect_contributors`` tool to gather GitHub usernames of
  contributors to a repository, including issue authors, PR authors, and commenters.
- A ``README.rst`` file and a guide for contributors in ``CONTRIBUTING.rst``.
- In ``darkgray_update_contributors``, support and automatically detect ``README.md``
  in addition to ``README.rst``.
- The repo-summary-post_ GitHub action now auto-generates a weekly project activity
  summary in the Announcements_ discussion category.
- Pytest_ and keyring_ as dependencies.
- Use uv_ and pre-commit_ for testing and linting.
- Basic configuration for using use Aider_ as a coding assistant to develop these tools.
- Ruff_ configuration settings.

Fixed
-----


0.1.1_ - 2024-07-28
===================

Fixed
-----
- Upgrade the Airium_ HTML builder for compatibility with recent Pip versions.


0.1.0_ - 2024-04-21
===================

Added
-----
- Multiple repositories can now be specified in a separate configuration section in
  ``contributors.yaml``.
- Contribution search links now point to the `/search` page on GitHub and support
  searching multiple repositories.

Fixed
-----


0.0.2_ - 2024-03-30
===================

Added
-----
- Moved the ``darkgray_update_contributors`` and ``darkgray_verify_contributors`` tools
  from Darker_.
- Support `PEP 621`_ packages in ``darkgray_bump_version``.
- Support package names with dashes in ``darkgray_bump_version``.
- Take ``darkgray_bump_version`` into use in the package itself.


0.0.1_ - 2024-03-15
===================

Added
-----
- Created the package.
- Moved the ``darkgray_bump_version`` tool from Darker_.


.. _Unreleased: https://github.com/akaihola/darkgray-dev-tools/compare/v0.3.0...HEAD
.. _0.2.0: https://github.com/akaihola/darkgray-dev-tools/compare/v0.1.1...v0.2.0
.. _0.1.1: https://github.com/akaihola/darkgray-dev-tools/compare/v0.1.0...v0.1.1
.. _0.1.0: https://github.com/akaihola/darkgray-dev-tools/compare/v0.0.2...v0.1.0
.. _0.0.2: https://github.com/akaihola/darkgray-dev-tools/compare/v0.0.1...v0.0.2
.. _0.0.1: https://github.com/akaihola/darkgray-dev-tools/compare/4afdc29...v0.0.1
.. _repo-summary-post: https://github.com/akaihola/repo-summary-post
.. _Announcements: https://github.com/akaihola/darkgray-dev-tools/discussions/categories/announcements
.. _Pytest: https://pytest.org/
.. _keyring: https://pypi.org/project/keyring/
.. _uv: https://docs.astral.sh/uv
.. _pre-commit: https://pre-commit.com/
.. _Aider: https://aider.chat/
.. _Ruff: https://docs.astral.sh/ruff
.. _Airium: https://pypi.org/project/airium/
.. _Darker: https://pypi.org/project/darker/
.. _PEP 621: https://packaging.python.org/en/latest/specifications/pyproject-toml/#pyproject-toml-spec
