"""
Helper functions
"""
import random
import string

from bs4 import BeautifulSoup


def generate_password(length: int) -> str:
    """Generate a random password including letters and digits.

    :param int length: password length

    :return: password
    :rtype: str
    """
    return ''.join([random.choice(string.ascii_letters + string.digits) for _ in range(length)])  # nosec


def xml_pretty(bxml: bytes) -> str:
    """
    Convert bytes xml to string and prettify it.

    :param bxml: xml content

    :return: xml in string
    """
    xml_str = BeautifulSoup(bxml, 'xml')
    return xml_str.decode(pretty_print=True)
