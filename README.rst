====================
 darkgray-dev-tools
====================

Development tools for Darker, Graylint and Darkgraylib projects.

This package provides three command-line tools:

1. ``darkgray_bump_version``
2. ``darkgray_update_contributors``
3. ``darkgray_show_reviews``

Installation
------------

Install the package from PyPI:

.. code-block:: bash

    pip install darkgray_dev_tools

Usage
-----

darkgray_bump_version
^^^^^^^^^^^^^^^^^^^^^

Bump the version number in project files.

.. code-block:: bash

    darkgray_bump_version {--major|--minor} [--dry-run] [--token=<github_token>]

Options:
  --major            Increment the major version
  --minor            Increment the minor version
  --dry-run          Print changes without modifying files
  --token            GitHub API token for checking milestones

If neither --major nor --minor is specified, the patch version is incremented.

darkgray_update_contributors
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Update contributor lists in README.rst and CONTRIBUTORS.rst.

.. code-block:: bash

    darkgray_update_contributors --token=<github_token> [--modify-readme] [--modify-contributors]

Options:
  --token                GitHub API token (required)
  --modify-readme        Update README.rst
  --modify-contributors  Update CONTRIBUTORS.rst

darkgray_show_reviews
^^^^^^^^^^^^^^^^^^^^^

Show timestamps and reviewers of most recent approved reviews.

.. code-block:: bash

    darkgray_show_reviews --token=<github_token> [--include-owner] [--stats]

Options:
  --token          GitHub API token (required)
  --include-owner  Include reviews by the repository owner
  --stats          Show monthly statistics instead of individual reviews

The output is in YAML format.

Development
-----------

To contribute to this project, please see the CONTRIBUTING.rst file for guidelines.

License
-------

This project is licensed under the BSD 3-Clause License - see the LICENSE file for details.
