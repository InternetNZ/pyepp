"""
pyepp module unit tests
"""
import unittest

from unittest.mock import MagicMock, patch

from pyepp.command_templates import HELLO_XML
from pyepp.epp import EppCommunicator, EppCommunicatorException, EppResultCode, EppResultData


class PyEPPTests(unittest.TestCase):

    def setUp(self) -> None:
        self.epp_config = {
            "server": "0.0.0.0",
            "port": "700",
            "client_cert": "path_to_cert",
            "client_key": "path_to_key",
        }
        patch("pyepp.epp.socket.socket").start()
        patch("pyepp.epp.ssl.SSLContext").start()

        self.maxDiff = None

    @patch.object(EppCommunicator, "_read")
    def test_connect(self, mock_read) -> None:
        mock_read.return_value = "greeting"
        epp = EppCommunicator(**self.epp_config)
        greeting = epp.connect()
        self.assertEqual(greeting, "greeting")

    @patch.object(EppCommunicator, "_read")
    def test_connect_exception(self, mock_read) -> None:
        mock_read.side_effect = Exception
        epp = EppCommunicator(**self.epp_config)

        self.assertRaises(EppCommunicatorException, epp.connect)

    @patch.object(EppCommunicator, "_read")
    def test_hello(self, mock_read) -> None:
        mock_read.return_value = "greeting"
        epp = EppCommunicator(**self.epp_config)
        epp.connect()
        hello = epp.hello()
        self.assertEqual(hello, "greeting")

    def test_login_1000(self) -> None:
        epp = EppCommunicator(**self.epp_config)
        expected_result = \
            EppResultData(**{'code': 1000, 'message': "Command completed successfully",
                             'reason': None, 'raw_response': "response", 'result_data': None})
        epp.execute = MagicMock(return_value=expected_result)
        epp.connect = MagicMock(return_value=None)

        result = epp.login("user", "pass")
        self.assertEqual(expected_result, result)

    def test_login_2004(self) -> None:
        epp = EppCommunicator(**self.epp_config)
        expected_result = \
            EppResultData(**{'code': 2004, 'message': "Command completed successfully",
                             'reason': None, 'raw_response': "response", 'result_data': None})
        epp.execute = MagicMock(return_value=expected_result)
        epp.connect = MagicMock(return_value=None)

        self.assertRaises(EppCommunicatorException, epp.login, "user", "pass")

    def test_login_other(self) -> None:
        epp = EppCommunicator(**self.epp_config)
        expected_result = \
            EppResultData(**{'code': 3000, 'message': "Command completed successfully",
                             'reason': None, 'raw_response': "response", 'result_data': None})
        epp.execute = MagicMock(return_value=expected_result)
        epp.connect = MagicMock(return_value=None)

        self.assertRaises(EppCommunicatorException, epp.login, "user", "pass")

    def test_logout(self) -> None:
        epp = EppCommunicator(**self.epp_config)
        expected_result = \
            EppResultData(**{'code': 1500, 'message': "Command completed successfully",
                             'reason': None, 'raw_response': "response", 'result_data': None})
        epp.execute = MagicMock(return_value=expected_result)
        epp.connect = MagicMock(return_value=None)
        epp._socket = MagicMock(close=MagicMock())

        result = epp.logout()
        self.assertEqual(expected_result, result)

    def test_execute_not_connected(self) -> None:
        epp = EppCommunicator(**self.epp_config)
        self.assertRaises(EppCommunicatorException, epp.execute, HELLO_XML)

    def test_execute_no_result(self) -> None:
        epp = EppCommunicator(**self.epp_config)
        epp.connect = MagicMock(return_value=None)
        raw_response = b'<?xml version="1.0" encoding="UTF-8"?>\n<epp xmlns="urn:ietf:params:xml:ns:epp-1.0" xmlns:host="urn:ietf:params:xml:ns:host-1.0" xmlns:contact="urn:ietf:params:xml:ns:contact-1.0" xmlns:domain="urn:ietf:params:xml:ns:domain-1.0" xmlns:rgp="urn:ietf:params:xml:ns:rgp-1.0" xmlns:secDNS="urn:ietf:params:xml:ns:secDNS-1.1">\n    <response>\n            <msg>Command completed successfully</msg>\n        </result>\n        <trID>\n            <svTRID>CIRA-000057351729-0000000001</svTRID>\n        </trID>\n    </response>\n</epp>'
        epp._execute_command = MagicMock(return_value=raw_response)
        self.assertRaises(EppCommunicatorException, epp.execute, HELLO_XML)

    def test_execute_with_error(self) -> None:
        epp = EppCommunicator(**self.epp_config)
        epp.connect = MagicMock(return_value=None)
        epp.greeting = "greeting"
        raw_response = b'''<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0" xmlns:contact="urn:ietf:params:xml:ns:contact-1.0" xmlns:domain="urn:ietf:params:xml:ns:domain-1.0" xmlns:host="urn:ietf:params:xml:ns:host-1.0" xmlns:rgp="urn:ietf:params:xml:ns:rgp-1.0" xmlns:secDNS="urn:ietf:params:xml:ns:secDNS-1.1"><response><result code="2000"><msg>There is an error</msg><reason>Because!</reason></result><trID><svTRID>CIRA-000057351729-0000000001</svTRID></trID></response></epp>'''
        epp._execute_command = MagicMock(return_value=raw_response)
        expected_result = \
            EppResultData(**{'code': 2000,
                             'message': 'There is an error',
                             'reason': 'Because!',
                             'raw_response': raw_response,
                             'client_transaction_id': None,
                             'server_transaction_id': 'CIRA-000057351729-0000000001',
                             'repository_object_id': None,
                             'result_data': None
                             })

        epp.connect()
        result = epp.execute(HELLO_XML)
        self.assertEqual(result, expected_result)

    def test_execute(self) -> None:
        epp = EppCommunicator(**self.epp_config)
        epp.connect = MagicMock(return_value=None)
        epp.greeting = "greeting"
        raw_response = b'<?xml version="1.0" encoding="UTF-8"?>\n<epp xmlns="urn:ietf:params:xml:ns:epp-1.0" xmlns:host="urn:ietf:params:xml:ns:host-1.0" xmlns:contact="urn:ietf:params:xml:ns:contact-1.0" xmlns:domain="urn:ietf:params:xml:ns:domain-1.0" xmlns:rgp="urn:ietf:params:xml:ns:rgp-1.0" xmlns:secDNS="urn:ietf:params:xml:ns:secDNS-1.1">\n    <response>\n<result code="1000">\n<msg>Command completed successfully</msg>\n</result>\n<trID>\n<svTRID>CIRA-000057351729-0000000001</svTRID>\n</trID>\n</response>\n</epp>'
        epp._execute_command = MagicMock(return_value=raw_response)
        expected_result = \
            EppResultData(**{'code': 1000, 'message': 'Command completed successfully', 'reason': None,
                             'raw_response': raw_response,
                             'client_transaction_id': None,
                             'server_transaction_id': 'CIRA-000057351729-0000000001',
                             'repository_object_id': None,
                             'result_data': None
                             })

        epp.connect()
        result = epp.execute(HELLO_XML)
        self.assertEqual(result, expected_result)

    def test_execute_epp_exception(self) -> None:
        epp = EppCommunicator(**self.epp_config)
        epp.connect = MagicMock(return_value=None)
        epp.greeting = "greeting"
        epp._execute_command = MagicMock(side_effect=EppCommunicatorException)

        self.assertRaises(EppCommunicatorException, epp.execute, HELLO_XML)

    def test_execute_general_exception(self) -> None:
        epp = EppCommunicator(**self.epp_config)
        epp.connect = MagicMock(return_value=None)
        epp.greeting = "greeting"
        epp._execute_command = MagicMock(side_effect=Exception)

        self.assertRaises(EppCommunicatorException, epp.execute, HELLO_XML)

    def test_read(self) -> None:
        epp = EppCommunicator(**self.epp_config)
        expected_result = b'<?xml version="1.0" encoding="UTF-8"?>\n<epp xmlns="urn:ietf:params:xml:ns:epp-1.0" xmlns:fury="urn:ietf:params:xml:ns:fury-1.0" xmlns:droplist="urn:ietf:params:xml:ns:droplist-1.0" xmlns:idn="urn:ietf:params:xml:ns:idn-1.0" xmlns:host="urn:ietf:params:xml:ns:host-1.0" xmlns:contact="urn:ietf:params:xml:ns:contact-1.0" xmlns:domain="urn:ietf:params:xml:ns:domain-1.0" xmlns:secDNS="urn:ietf:params:xml:ns:secDNS-1.1" xmlns:launch="urn:ietf:params:xml:ns:launch-1.0" xmlns:mark="urn:ietf:params:xml:ns:mark-1.0" xmlns:smd="urn:ietf:params:xml:ns:signedMark-1.0" xmlns:ds="http://www.w3.org/2000/09/xmldsig#" xmlns:rgp="urn:ietf:params:xml:ns:rgp-1.0" xmlns:fee="urn:ietf:params:xml:ns:fee-0.11">\n    <greeting>\n        <svID>EPP Server Version: 8.0.4 (de4e6cbdab9536033563b335e4fa4555cf24c931)</svID>\n        <svDate>2023-03-30T20:56:22.740Z</svDate>\n        <svcMenu>\n            <version>1.0</version>\n            <lang>fr</lang>\n            <lang>en</lang>\n            <objURI>urn:ietf:params:xml:ns:epp-1.0</objURI>\n            <objURI>urn:ietf:params:xml:ns:domain-1.0</objURI>\n            <objURI>urn:ietf:params:xml:ns:host-1.0</objURI>\n            <objURI>urn:ietf:params:xml:ns:contact-1.0</objURI>\n            <svcExtension>\n                <extURI>urn:ietf:params:xml:ns:rgp-1.0</extURI>\n                <extURI>urn:ietf:params:xml:ns:fury-1.0</extURI>\n                <extURI>urn:ietf:params:xml:ns:fury-2.0</extURI>\n                <extURI>urn:ietf:params:xml:ns:droplist-1.0</extURI>\n                <extURI>urn:ietf:params:xml:ns:fury-rgp-1.0</extURI>\n                <extURI>urn:ietf:params:xml:ns:idn-1.0</extURI>\n                <extURI>urn:ietf:params:xml:ns:secDNS-1.1</extURI>\n                <extURI>urn:ietf:params:xml:ns:launch-1.0</extURI>\n                <extURI>urn:ietf:params:xml:ns:mark-1.0</extURI>\n                <extURI>urn:ietf:params:xml:ns:signedMark-1.0</extURI>\n                <extURI>urn:ietf:params:xml:ns:fee-0.11</extURI>\n                <extURI>urn:ietf:params:xml:ns:fee-0.9</extURI>\n                <extURI>http://www.w3.org/2000/09/xmldsig#</extURI>\n            </svcExtension>\n        </svcMenu>\n        <dcp>\n            <access>\n                <none/>\n            </access>\n            <statement>\n                <purpose>\n                    <admin/>\n                </purpose>\n                <recipient>\n                    <ours/>\n                </recipient>\n                <retention>\n                    <legal/>\n                </retention>\n            </statement>\n        </dcp>\n    </greeting>\n</epp>'
        epp._ssl_socket = MagicMock(
            read=MagicMock(return_value=b'\x00\x00\n\t'),
            recv=MagicMock(return_value=expected_result)
        )

        result = epp._read()
        self.assertEqual(result, expected_result)

    def test_write(self) -> None:
        epp = EppCommunicator(**self.epp_config)
        expected_result = 103
        epp._ssl_socket = MagicMock(
            send=MagicMock(return_value=expected_result),
        )

        result = epp._write(HELLO_XML)

        self.assertEqual(result, expected_result)


if __name__ == "__main__":
    unittest.main()
