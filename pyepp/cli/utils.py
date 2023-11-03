"""
Utilities module
"""
from typing import Optional, Any

import click

OUTPUT_FILE = None


def echo(message: Optional[Any] = None,
         new_line: bool = True,
         err: bool = False,
         color: Optional[bool] = None) -> None:
    """

    :param message: The string or bytes to output. Other objects are
        converted to strings.
    :param err: Write to ``stderr`` instead of ``stdout``.
    :param new_line: Print a newline after the message. Enabled by default.
    :param color: Force showing or hiding colors and other styles. By
        default, Click will remove color if the output does not look like
        an interactive terminal.
    """
    # Convert the string to bytes if writing to a file
    if OUTPUT_FILE:
        message = str.encode(message)

    click.echo(message, file=OUTPUT_FILE, nl=new_line, err=err, color=color)
