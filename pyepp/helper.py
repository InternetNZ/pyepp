"""
Helper functions
"""
import random
import string


def generate_password(length: int) -> str:
    """Generate a random password including letters and digits.

    :param int length: password length

    :return: password
    :rtype: str
    """
    return ''.join([random.choice(string.ascii_letters + string.digits) for _ in range(length)])  # nosec
