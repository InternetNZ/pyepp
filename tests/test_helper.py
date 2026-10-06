"""
Helper unit tests
"""
import string
import unittest

from pyepp import helper


class HelperTest(unittest.TestCase):
    def test_beautify_xml(self) -> None:
        xml_content = b"<test><node>1</node></test>"
        result = helper.xml_pretty(xml_content)
        self.assertIn("<?xml version=\"1.0\" encoding=\"utf-8\"?>", result)
        self.assertIn("<test>\n", result)

    def test_generate_password_default_length(self) -> None:
        password = helper.generate_password()
        self.assertEqual(len(password), 16)
        valid_chars = set(string.ascii_letters + string.digits)
        self.assertTrue(set(password).issubset(valid_chars))

    def test_generate_password_custom_length(self) -> None:
        for length in (8, 20, 32):
            password = helper.generate_password(length)
            self.assertEqual(len(password), length)
            valid_chars = set(string.ascii_letters + string.digits)
            self.assertTrue(set(password).issubset(valid_chars))

    def test_generate_password_randomness(self) -> None:
        passwords = {helper.generate_password(16) for _ in range(100)}
        self.assertEqual(len(passwords), 100)

    def test_generate_password_invalid_length(self) -> None:
        for invalid_length in (0, -1, -10):
            with self.assertRaises(ValueError):
                helper.generate_password(invalid_length)