====================
 darkgray-dev-tools
====================

Development tools for Darker, Graylint and Darkgraylib projects.

This package provides four command-line tools:

1. ``darkgray_bump_version``
2. ``darkgray_update_contributors``
3. ``darkgray_show_reviews``
4. ``darkgray_collect_contributors``

Installation
------------

Install the package from PyPI::

    pip install darkgray_dev_tools

Usage
-----

darkgray_bump_version
^^^^^^^^^^^^^^^^^^^^^

Bump the version number in project files::

    darkgray_bump_version {--major|--minor} [--dry-run] [--token=<github_token>]

Options:
  --major            Increment the major version
  --minor            Increment the minor version
  --dry-run          Print changes without modifying files
  --token            GitHub API token for checking milestones

If neither --major nor --minor is specified, the patch version is incremented.

darkgray_update_contributors
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Update contributor lists in README.rst and CONTRIBUTORS.rst::

    darkgray_update_contributors
      --token=<github_token>
      [--modify-readme] [--modify-contributors]

Options:
  --token                GitHub API token (required)
  --modify-readme        Update README.rst
  --modify-contributors  Update CONTRIBUTORS.rst

darkgray_show_reviews
^^^^^^^^^^^^^^^^^^^^^

Show timestamps and reviewers of most recent approved reviews::

    darkgray_show_reviews --token=<github_token> [--include-owner] [--stats]

Options:
  --token          GitHub API token (required)
  --include-owner  Include reviews by the repository owner
  --stats          Show monthly statistics instead of individual reviews

The output is in YAML format.

darkgray_collect_contributors
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Collect GitHub usernames of contributors to a repository::

    darkgray_collect_contributors [--repo=<owner/repo>] [--since=<ISO_date>]

Options:
  --repo   Repository in the format owner/repo (optional, defaults to current git repository)
  --since  ISO date to collect contributions from (e.g., 2023-01-01)

The output is in YAML format and includes contributors' GitHub usernames along with their contribution types.

Development
-----------

To contribute to this project, please see the CONTRIBUTING.rst file for guidelines.

License
-------

This project is licensed under the BSD 3-Clause License - see the LICENSE file for details.
