"""
Helper unit tests
"""
import unittest

from pyepp import helper


class HelperTest(unittest.TestCase):
    def test_beautify_xml(self) -> None:
        xml_content = b"<test><node>1</node></test>"
        result = helper.xml_pretty(xml_content)
        self.assertIn("<?xml version=\"1.0\" encoding=\"utf-8\"?>", result)
        self.assertIn("<test>\n", result)