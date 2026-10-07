"""
EPP Communicator unit tests
"""
import unittest
from unittest.mock import MagicMock, patch
import sys
import struct
import socket

from pyepp.epp import (
    EppCommunicator,
    EppResultData,
    EppCommunicatorException,
    EppDryRunException,
    mask_sensitive_xml,
    _find_tag_end,
)

class EppResultDataTest(unittest.TestCase):
    def test_dunder_methods_and_to_dict(self):
        data = EppResultData(code=1000, message='Success', raw_response='raw', result_data=None)
        # test __setitem__
        data['reason'] = 'No reason'
        # test __getitem__
        self.assertEqual(data['reason'], 'No reason')
        # test __len__
        self.assertTrue(len(data) > 3)
        # test to_dict
        d = data.to_dict()
        self.assertEqual(d['code'], 1000)
        self.assertEqual(d['message'], 'Success')


class EppCommunicatorTest(unittest.TestCase):
    def setUp(self):
        self.epp = EppCommunicator('localhost', '700', dry_run=False)

    def test_execute_command_dry_run(self):
        self.epp._dry_run = True
        cmd = "<epp><command><clTRID>TEST-123</clTRID></command></epp>"
        raw = self.epp._execute_command(cmd)
        self.assertEqual(raw, cmd.encode("utf-8"))

    def test_execute_dry_run_with_cltrid(self):
        self.epp._dry_run = True
        cmd = "<epp><command><clTRID>TEST-TRID-123</clTRID></command></epp>"
        result = self.epp.execute(cmd)
        self.assertEqual(result.code, 1000)
        self.assertEqual(result.message, "Dry run")
        self.assertEqual(result.raw_response, cmd)
        self.assertEqual(result.client_transaction_id, "TEST-TRID-123")
        self.assertIsNone(result.server_transaction_id)
        self.assertIsNone(result.result_data)

    def test_execute_dry_run_without_cltrid(self):
        self.epp._dry_run = True
        cmd = "<epp><command></command></epp>"
        result = self.epp.execute(cmd)
        self.assertEqual(result.code, 1000)
        self.assertEqual(result.message, "Dry run")
        self.assertEqual(result.raw_response, cmd)
        self.assertIsNone(result.client_transaction_id)

    def test_execute_dry_run_invalid_xml(self):
        self.epp._dry_run = True
        cmd = "invalid <xml"
        result = self.epp.execute(cmd)
        self.assertEqual(result.code, 1000)
        self.assertEqual(result.message, "Dry run")
        self.assertEqual(result.raw_response, cmd)
        self.assertIsNone(result.client_transaction_id)

    @patch("pyepp.epp.BeautifulSoup", side_effect=Exception("Parsing failed"))
    def test_execute_dry_run_bs4_exception(self, _mock_bs4):
        self.epp._dry_run = True
        cmd = "<epp><command></command></epp>"
        result = self.epp.execute(cmd)
        self.assertEqual(result.code, 1000)
        self.assertEqual(result.message, "Dry run")
        self.assertIsNone(result.client_transaction_id)

    def test_dry_run_hello(self):
        self.epp._dry_run = True
        res = self.epp.hello()
        self.assertIn(b"<hello/>", res)

    def test_dry_run_logout_without_socket(self):
        self.epp._dry_run = True
        self.epp._socket = None
        result = self.epp.logout()
        self.assertEqual(result.code, 1000)
        self.assertEqual(result.message, "Dry run")

    def test_dry_run_exception(self):
        mock_result = EppResultData(code=1000, message="Dry run", raw_response="<xml/>", result_data=None)
        exc = EppDryRunException("<xml/>", result=mock_result)
        self.assertEqual(exc.cmd, "<xml/>")
        self.assertEqual(exc.result, mock_result)
        self.assertIn("Dry run: <xml/>", str(exc))

    def test_read_empty_length(self):
        self.epp._ssl_socket = MagicMock()
        self.epp._ssl_socket.read.return_value = b''
        result = self.epp._read()
        self.assertIsNone(result)

    def test_execute_command_no_response(self):
        self.epp._write = MagicMock()
        self.epp._read = MagicMock(return_value=None)
        with self.assertRaises(EppCommunicatorException) as context:
            self.epp._execute_command("test")
        self.assertIn("Cannot connect to server. Please re-login!", str(context.exception))

    @patch('pyepp.epp.ssl.create_default_context')
    def test_connect_exception(self, mock_ssl):
        mock_ssl.side_effect = Exception("SSL Error")
        with self.assertRaises(EppCommunicatorException) as context:
            self.epp.connect()
        self.assertIn("Could not setup a secure connection", str(context.exception))

    def test_execute_not_connected(self):
        self.epp.greeting = None
        self.epp._dry_run = False
        with self.assertRaises(EppCommunicatorException) as context:
            self.epp.execute("<xml/>")
        self.assertIn("The connection to the server has not been established yet!", str(context.exception))

    @patch('pyepp.epp.BeautifulSoup')
    def test_execute_attribute_error_missing_code(self, mock_bs):
        self.epp.greeting = b'greeting'
        self.epp._execute_command = MagicMock(return_value='xml')
        mock_xml = MagicMock()
        mock_result = MagicMock()
        mock_result.get.side_effect = AttributeError("Mock attribute error")
        mock_xml.find.side_effect = lambda tag, *args, **kwargs: mock_result if tag == "result" else MagicMock()
        mock_bs.return_value = mock_xml
        with self.assertRaises(EppCommunicatorException) as context:
            self.epp.execute("<xml/>")
        self.assertIn("Could not get result code.", str(context.exception))

    def test_execute_generic_exception(self):
        self.epp.greeting = b'greeting'
        self.epp._execute_command = MagicMock(side_effect=ValueError("Some value error"))
        with self.assertRaises(EppCommunicatorException) as context:
            self.epp.execute("<xml/>")
        self.assertIn("Some value error", str(context.exception))

    @patch('pyepp.epp.EppCommunicator.execute')
    def test_login_no_extensions(self, mock_execute):
        mock_result = MagicMock()
        mock_result.code = 1000
        mock_execute.return_value = mock_result

        # Call without extensions to hit `if extensions is None: extensions = []`
        result = self.epp.login('user', 'pass')
        self.assertEqual(result.code, 1000)
        self.assertEqual(self.epp.user, 'user')
        sent_command = mock_execute.call_args[0][0]
        self.assertNotIn('<objURI>urn:ietf:params:xml:ns:epp-1.0</objURI>', sent_command)
        self.assertIn('<objURI>urn:ietf:params:xml:ns:domain-1.0</objURI>', sent_command)
        self.assertIn('<objURI>urn:ietf:params:xml:ns:contact-1.0</objURI>', sent_command)
        self.assertIn('<objURI>urn:ietf:params:xml:ns:host-1.0</objURI>', sent_command)

    @patch('pyepp.epp.EppCommunicator.execute')
    def test_login_with_extensions(self, mock_execute):
        mock_result = MagicMock()
        mock_result.code = 1000
        mock_execute.return_value = mock_result
        self.epp.login('user', 'pass', extensions=['urn:ietf:params:xml:ns:secDNS-1.1'])
        self.assertEqual(self.epp.user, 'user')
        sent_command = mock_execute.call_args[0][0]
        self.assertNotIn('<objURI>urn:ietf:params:xml:ns:epp-1.0</objURI>', sent_command)

    @patch('pyepp.epp.ssl.create_default_context')
    def test_connect_with_cert_and_key(self, mock_ssl):
        epp = EppCommunicator('localhost', '700', client_cert='cert.pem', client_key='key.pem', dry_run=False)
        mock_context = MagicMock()
        mock_ssl.return_value = mock_context
        epp._read = MagicMock(return_value=b'greeting')
        epp.connect()
        mock_context.load_cert_chain.assert_called_with(certfile='cert.pem', keyfile='key.pem')

    @patch('pyepp.epp.ssl.create_default_context')
    def test_connect_without_cert_and_key(self, mock_ssl):
        epp = EppCommunicator('localhost', '700', dry_run=False)
        mock_context = MagicMock()
        mock_ssl.return_value = mock_context
        epp._read = MagicMock(return_value=b'greeting')
        epp.connect()
        mock_context.load_cert_chain.assert_not_called()

    def test_read_empty_chunk(self):
        self.epp._ssl_socket = MagicMock()
        # Mock length to something that decodes to total_bytes > LENGTH_FIELD_SIZE (4)
        # Using format ">I" means big-endian unsigned int. 8 means length 8.
        self.epp._ssl_socket.read.return_value = struct.pack(">I", 8)
        self.epp._ssl_socket.recv.return_value = b''
        result = self.epp._read()
        self.assertIsNone(result)

    def test_read_logging_debug(self):
        self.epp._ssl_socket = MagicMock()
        self.epp._ssl_socket.read.return_value = struct.pack(">I", 8)
        self.epp._ssl_socket.recv.return_value = b'test'
        with self.assertLogs(level='DEBUG') as log:
            result = self.epp._read()
            self.assertEqual(result, b'test')
            self.assertTrue(any("DEBUG:root:Received 4/4 bytes" in msg for msg in log.output))
            self.assertFalse(any("INFO:root:Received" in msg for msg in log.output))

    def test_write_logging_debug(self):
        self.epp._ssl_socket = MagicMock()
        with self.assertLogs(level='DEBUG') as log:
            result = self.epp._write("<xml/>")
            self.assertEqual(result, 8)
            self.assertTrue(any("DEBUG:root:Sent 8 bytes" in msg for msg in log.output))
            self.assertFalse(any("INFO:root:Sent" in msg for msg in log.output))

    @patch('pyepp.epp.ssl.create_default_context')
    def test_connect_logging_debug(self, mock_ssl):
        epp = EppCommunicator('localhost', '700', dry_run=False)
        epp._read = MagicMock(return_value=b'greeting')
        with self.assertLogs(level='DEBUG') as log:
            epp.connect()
            self.assertTrue(any("DEBUG:root:Received greeting from server :\n" in msg for msg in log.output))

    def test_execute_command_masks_passwords_in_debug_logs(self):
        self.epp._write = MagicMock()
        self.epp._read = MagicMock(return_value=b"<domain:pw>respSecret</domain:pw>")
        with self.assertLogs(level='DEBUG') as log:
            result = self.epp._execute_command("<command><pw>reqSecret</pw></command>")
            self.assertEqual(result, b"<domain:pw>respSecret</domain:pw>")
            full_log = "\n".join(log.output)
            self.assertIn("<pw>***</pw>", full_log)
            self.assertIn("<domain:pw>***</domain:pw>", full_log)
            self.assertNotIn("reqSecret", full_log)
            self.assertNotIn("respSecret", full_log)


class MaskSensitiveXmlTest(unittest.TestCase):
    def test_mask_passwords_in_string(self):
        xml = "<login><clID>user</clID><pw>secret123</pw><newPW>new456</newPW></login>"
        masked = mask_sensitive_xml(xml)
        self.assertIn("<pw>***</pw>", masked)
        self.assertIn("<newPW>***</newPW>", masked)
        self.assertNotIn("secret123", masked)
        self.assertNotIn("new456", masked)

    def test_mask_domain_and_contact_passwords(self):
        xml = '<authInfo><domain:pw roid="1">domSecret</domain:pw><contact:pw>conSecret</contact:pw></authInfo>'
        masked = mask_sensitive_xml(xml)
        self.assertIn('<domain:pw roid="1">***</domain:pw>', masked)
        self.assertIn("<contact:pw>***</contact:pw>", masked)
        self.assertNotIn("domSecret", masked)
        self.assertNotIn("conSecret", masked)

    def test_mask_passwords_in_bytes(self):
        xml_bytes = b"<domain:pw>byteSecret</domain:pw>"
        masked = mask_sensitive_xml(xml_bytes)
        self.assertEqual(masked, "<domain:pw>***</domain:pw>")
        self.assertNotIn("byteSecret", masked)

    def test_no_sensitive_tags(self):
        xml = "<domain:name>example.com</domain:name>"
        self.assertEqual(mask_sensitive_xml(xml), xml)

    def test_mask_passwords_with_cdata(self):
        xml = "<login><pw><![CDATA[cdataSecret]]></pw></login>"
        masked = mask_sensitive_xml(xml)
        self.assertEqual(masked, "<login><pw>***</pw></login>")
        self.assertNotIn("cdataSecret", masked)

    def test_mask_passwords_multiline_cdata(self):
        xml = "<domain:pw>\n  <![CDATA[\n    multilineSecret\n  ]]>\n</domain:pw>"
        masked = mask_sensitive_xml(xml)
        self.assertEqual(masked, "<domain:pw>***</domain:pw>")
        self.assertNotIn("multilineSecret", masked)

    def test_mask_passwords_with_hyphen_and_dot_namespace_prefixes(self):
        xml = (
            "<secDNS-1.1:pw><![CDATA[secDnsSecret]]></secDNS-1.1:pw>"
            "<registry-ext:pw>regSecret</registry-ext:pw>"
            "<custom.ext:newPW>customSecret</custom.ext:newPW>"
        )
        masked = mask_sensitive_xml(xml)
        self.assertIn("<secDNS-1.1:pw>***</secDNS-1.1:pw>", masked)
        self.assertIn("<registry-ext:pw>***</registry-ext:pw>", masked)
        self.assertIn("<custom.ext:newPW>***</custom.ext:newPW>", masked)
        self.assertNotIn("secDnsSecret", masked)
        self.assertNotIn("regSecret", masked)
        self.assertNotIn("customSecret", masked)

    def test_mask_passwords_with_cdata_containing_closing_tag(self):
        xml = "<pw><![CDATA[first</pw>tailSecret]]></pw>"
        masked = mask_sensitive_xml(xml)
        self.assertEqual(masked, "<pw>***</pw>")
        self.assertNotIn("first", masked)
        self.assertNotIn("tailSecret", masked)

    def test_mask_passwords_with_comment_containing_closing_tag(self):
        xml = "<pw><!-- </pw> -->commentSecret<!-- comment --></pw>"
        masked = mask_sensitive_xml(xml)
        self.assertEqual(masked, "<pw>***</pw>")
        self.assertNotIn("commentSecret", masked)

    def test_mask_passwords_self_closing_tag(self):
        xml = "<domain:create><domain:pw/></domain:create>"
        masked = mask_sensitive_xml(xml)
        self.assertEqual(masked, xml)

    def test_mask_passwords_with_xml_declaration(self):
        xml = '<?xml version="1.0" encoding="UTF-8"?><epp><login><pw>declSecret</pw></login></epp>'
        masked = mask_sensitive_xml(xml)
        self.assertEqual(
            masked,
            '<?xml version="1.0" encoding="UTF-8"?><epp><login><pw>***</pw></login></epp>',
        )
        self.assertNotIn("declSecret", masked)

    def test_mask_passwords_malformed_xml_fallback(self):
        xml = "<login><pw>unclosed_secret"
        masked = mask_sensitive_xml(xml)
        self.assertEqual(masked, "<login><pw>***")
        self.assertNotIn("unclosed_secret", masked)

    def test_find_tag_end(self):
        self.assertEqual(_find_tag_end(b"<pw>", 0, 4), 4)
        self.assertEqual(_find_tag_end(b"<pw roid='1'>", 0, 13), 13)
        self.assertEqual(_find_tag_end(b"<pw", 0, 3), -1)





