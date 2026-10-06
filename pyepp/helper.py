"""
Helper functions
"""

import secrets
import string

from bs4 import BeautifulSoup


def generate_password(length: int = 16) -> str:
    """Generate a cryptographically secure random password including letters and digits.

    :param int length: password length, defaults to 16

    :return: password
    :rtype: str
    :raises ValueError: if length is not a positive integer
    """
    if isinstance(length, bool) or not isinstance(length, int) or length <= 0:
        raise ValueError("Password length must be a positive integer.")
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def xml_pretty(bxml: bytes) -> str:
    """
    Convert bytes xml to string and prettify it.

    :param bxml: xml content

    :return: xml in string
    """
    xml_str = BeautifulSoup(bxml, "xml")
    return xml_str.decode(pretty_print=True)
