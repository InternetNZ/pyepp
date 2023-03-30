"""
pyepp module unit tests
"""
import unittest

from unittest.mock import MagicMock, patch, Mock

from pyepp.command_templates import HELLO_XML
from pyepp.epp import EppCommunicator, EppCommunicatorException


class PyEPPTests(unittest.TestCase):

    def setUp(self):
        self.epp_config = {
            "host": "0.0.0.0",
            "port": "700",
            "client_cert": "path_to_cert",
            "client_key": "path_to_key",
        }
        patch("pyepp.epp.socket.socket").start()
        patch("pyepp.epp.ssl.SSLContext").start()

    @patch.object(EppCommunicator, "_read")
    def test_connect(self, mock_read):
        mock_read.return_value = "greeting"
        epp = EppCommunicator(**self.epp_config)
        greeting = epp.connect()
        self.assertEqual(greeting, "greeting")

    @patch.object(EppCommunicator, "_read")
    def test_hello(self, mock_read):
        mock_read.return_value = "greeting"
        epp = EppCommunicator(**self.epp_config)
        epp.connect()
        hello = epp.hello()
        self.assertEqual(hello, "greeting")

    def test_login_1000(self):
        epp = EppCommunicator(**self.epp_config)
        expected_result = \
            {'code': 1000, 'message': "Command completed successfully", 'reason': None, 'response': "response"}
        epp.execute = MagicMock(return_value=expected_result)
        epp.connect = MagicMock(return_value=None)

        result = epp.login("user", "pass")
        self.assertDictEqual(expected_result, result)

    def test_login_2004(self):
        epp = EppCommunicator(**self.epp_config)
        expected_result = \
            {'code': 2004, 'message': "Command completed successfully", 'reason': None, 'response': "response"}
        epp.execute = MagicMock(return_value=expected_result)
        epp.connect = MagicMock(return_value=None)

        self.assertRaises(EppCommunicatorException, epp.login, "user", "pass")

    def test_login_other(self):
        epp = EppCommunicator(**self.epp_config)
        expected_result = \
            {'code': 3000, 'message': "Command completed successfully", 'reason': None, 'response': "response"}
        epp.execute = MagicMock(return_value=expected_result)
        epp.connect = MagicMock(return_value=None)

        self.assertRaises(EppCommunicatorException, epp.login, "user", "pass")

    def test_logout(self):
        epp = EppCommunicator(**self.epp_config)
        expected_result = \
            {'code': 1500, 'message': 'Command completed successfully; ending session', 'reason': None, 'response': None}
        epp.execute = MagicMock(return_value=expected_result)
        epp.connect = MagicMock(return_value=None)
        epp._socket = MagicMock(close=MagicMock())

        result = epp.logout()
        self.assertDictEqual(expected_result, result)

    def test_execute_not_connected(self):
        epp = EppCommunicator(**self.epp_config)
        self.assertRaises(EppCommunicatorException, epp.execute, HELLO_XML)

    def test_execute_no_result(self):
        epp = EppCommunicator(**self.epp_config)
        epp.connect = MagicMock(return_value=None)
        raw_response = b'<?xml version="1.0" encoding="UTF-8"?>\n<epp xmlns="urn:ietf:params:xml:ns:epp-1.0" xmlns:host="urn:ietf:params:xml:ns:host-1.0" xmlns:contact="urn:ietf:params:xml:ns:contact-1.0" xmlns:domain="urn:ietf:params:xml:ns:domain-1.0" xmlns:rgp="urn:ietf:params:xml:ns:rgp-1.0" xmlns:secDNS="urn:ietf:params:xml:ns:secDNS-1.1">\n    <response>\n            <msg>Command completed successfully</msg>\n        </result>\n        <trID>\n            <svTRID>CIRA-000057351729-0000000001</svTRID>\n        </trID>\n    </response>\n</epp>'
        epp._execute_command = MagicMock(return_value=raw_response)
        self.assertRaises(EppCommunicatorException, epp.execute, HELLO_XML)

    def test_execute_with_error(self):
        epp = EppCommunicator(**self.epp_config)
        epp.connect = MagicMock(return_value=None)
        epp.greeting = "greeting"
        raw_response = b'<?xml version="1.0" encoding="UTF-8"?>\n<epp xmlns="urn:ietf:params:xml:ns:epp-1.0" xmlns:host="urn:ietf:params:xml:ns:host-1.0" xmlns:contact="urn:ietf:params:xml:ns:contact-1.0" xmlns:domain="urn:ietf:params:xml:ns:domain-1.0" xmlns:rgp="urn:ietf:params:xml:ns:rgp-1.0" xmlns:secDNS="urn:ietf:params:xml:ns:secDNS-1.1">\n    <response>\n        <result code="2000">\n            <msg>There is an error</msg>\n  <reason>Because!</reseaon>\n        </result>\n        <trID>\n            <svTRID>CIRA-000057351729-0000000001</svTRID>\n        </trID>\n    </response>\n</epp>'
        epp._execute_command = MagicMock(return_value=raw_response)
        expected_result = \
            {'code': 2000, 'message': 'There is an error', 'reason': 'Because!', 'response': '''<response>
<result code="2000">
<msg>There is an error</msg>
<reason>Because!</reason>
</result>
<trID>
<svTRID>CIRA-000057351729-0000000001</svTRID>
</trID>
</response>'''}

        epp.connect()
        result = epp.execute(HELLO_XML)
        self.assertDictEqual(result, expected_result)

    def test_execute_with_error(self):
        epp = EppCommunicator(**self.epp_config)
        epp.connect = MagicMock(return_value=None)
        epp.greeting = "greeting"
        raw_response = b'<?xml version="1.0" encoding="UTF-8"?>\n<epp xmlns="urn:ietf:params:xml:ns:epp-1.0" xmlns:host="urn:ietf:params:xml:ns:host-1.0" xmlns:contact="urn:ietf:params:xml:ns:contact-1.0" xmlns:domain="urn:ietf:params:xml:ns:domain-1.0" xmlns:rgp="urn:ietf:params:xml:ns:rgp-1.0" xmlns:secDNS="urn:ietf:params:xml:ns:secDNS-1.1">\n    <response>\n        <result code="1000">\n            <msg>Command completed successfully</msg>\n        </result>\n        <trID>\n            <svTRID>CIRA-000057351729-0000000001</svTRID>\n        </trID>\n    </response>\n</epp>'
        epp._execute_command = MagicMock(return_value=raw_response)
        expected_result = \
            {'code': 1000, 'message': 'Command completed successfully', 'reason': None, 'response': '''<response>
<result code="1000">
<msg>Command completed successfully</msg>
</result>
<trID>
<svTRID>CIRA-000057351729-0000000001</svTRID>
</trID>
</response>'''}

        epp.connect()
        result = epp.execute(HELLO_XML)
        self.assertDictEqual(result, expected_result)



if __name__ == "__main__":
    unittest.main()
