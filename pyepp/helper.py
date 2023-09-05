"""
Helper functions
"""
import random
import string
import xml.dom.minidom

from bs4 import BeautifulSoup


def generate_password(length: int) -> str:
    """Generate a random password including letters and digits.

    :param int length: password length

    :return: password
    :rtype: str
    """
    return ''.join([random.choice(string.ascii_letters + string.digits) for _ in range(length)])  # nosec


def xml_pretty(xml_str):
    xml_str = BeautifulSoup(xml_str, 'xml')
    return xml_str.decode(pretty_print=True)
