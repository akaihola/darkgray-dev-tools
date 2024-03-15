"""Exceptions for `darkgray_dev_tools`."""


class NoMatchError(Exception):
    """Raised if pattern couldn't be found in the content."""

    def __init__(self, regex: str, path: str) -> None:
        """Initialize the exception.

        :param regex: The regular expression that couldn't be found
        :param path: The path of the file in which the regex couldn't be found

        """
        super().__init__(f"Can't find `{regex}` in `{path}`")
