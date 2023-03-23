"""
Helper functions
"""
import xml.dom.minidom


def xml_pretty(xml_str, indent="  "):
    """
    Make the xml doc pretty,

    :param str xml_str: xml
    :param str indent: indentation

    :return: Pretty XML
    :rtype: str
    """
    return xml.dom.minidom.parseString(xml_str.decode('utf-8')).toprettyxml(indent=indent)
