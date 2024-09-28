Contributing to darkgray-dev-tools
==================================

Thank you for your interest in contributing to darkgray-dev-tools!
We welcome contributions from the community to help improve and grow this project.


Getting Started
---------------

1. Fork the repository on GitHub.

2. Clone your fork locally::

       git clone https://github.com/your-username/darkgray-dev-tools.git
       cd darkgray-dev-tools

3. Create a new branch for your feature or bug fix::

       git checkout -b your-feature-branch


Development Setup
-----------------

1. Create a virtual environment and install the package in editable mode with development dependencies::

       python -m venv .venv
       source .venv/bin/activate  # On Windows, use `.venv\Scripts\activate`
       pip install -e '.[dev]'

   If you prefer the uv_ tool, you can do the same with::

       uv sync --all-extras
       source .venv/bin/activate

3. Install pre-commit hooks::

       pre-commit install


Making Changes
--------------

1. Make your changes in your feature branch.

2. Add or update tests as necessary.

3. Run the tests::

       ./run-tests.sh

4. Run the linter::

       ./run-lint.sh

5. Commit your changes::

       git commit -am "Add a brief description of your changes"


Submitting a Pull Request
-------------------------

1. Push your changes to your fork on GitHub::

       git push origin your-feature-branch

2. Open a pull request from your fork to the main repository.

3. Describe your changes and the problem they solve in the pull request description.

4. Wait for a maintainer to review your pull request. They may ask for changes or clarifications.


Code Style
----------

We use `ruff format`_ for code formatting, isort_ for import sorting, and `ruff check`_ for linting.
Darker_ and Graylint_ are used to limit the output of those tools
only to the changed lines in your pull request.
These tools are configured in the ``pyproject.toml`` file.
The pre-commit hooks will automatically check and fix most style issues when you commit changes.


Reporting Issues
----------------

If you find a bug or have a suggestion for improvement, please open an issue on the GitHub repository.
Provide as much detail as possible, including steps to reproduce the issue if applicable.

Thank you for contributing to darkgray-dev-tools!


.. _uv: https://docs.astral.sh/uv/
.. _ruff format: https://docs.astral.sh/ruff/formatter/
.. _ruff check: https://docs.astral.sh/ruff/linter/
.. _isort: https://pycqa.github.io/isort/
.. _Darker: https://github.com/akaihola/darker
.. _Graylint: https://github.com/akaihola/graylint
