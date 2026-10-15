"""
EPP Communicator unit tests
"""
import unittest
from unittest.mock import MagicMock, patch
import sys
import struct
import socket

from pyepp.command_templates import LOGIN_XML
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
        self.assertFalse(data.dry_run)
        self.assertEqual(d['message'], 'Success')

    def test_parsed_xml_equality_and_repr(self):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup('<root><a id="1">test</a></root>', 'xml')
        data_with_xml = EppResultData(
            code=1000,
            message='Success',
            raw_response='raw',
            result_data=None,
            parsed_xml=soup,
        )
        data_without_xml = EppResultData(
            code=1000,
            message='Success',
            raw_response='',
            result_data=None,
        )

        # compare=False ensures equality is unaffected by parsed_xml
        # (even when raw_response differs, here we test that parsed_xml does not affect equality)
        data_matching_fields = EppResultData(
            code=1000,
            message='Success',
            raw_response='raw',
            result_data=None,
            parsed_xml=soup,
        )
        data_matching_other = EppResultData(
            code=1000,
            message='Success',
            raw_response='raw',
            result_data=None,
        )
        self.assertEqual(data_matching_fields, data_matching_other)
        # repr=False ensures parsed_xml does not bloat string representations
        self.assertNotIn("parsed_xml", repr(data_with_xml))
        self.assertIs(data_with_xml.parsed_xml, soup)
        self.assertIsNone(data_without_xml.parsed_xml)

    def test_post_init_populates_parsed_xml(self):
        data = EppResultData(
            code=1000,
            message='Success',
            raw_response='<root><elem>val</elem></root>',
            result_data=None,
        )
        self.assertIsNotNone(data.parsed_xml)
        self.assertEqual(data.parsed_xml.find("elem").text, "val")

    def test_post_init_skips_when_dry_run(self):
        data = EppResultData(
            code=1000,
            message='Success',
            raw_response='<root><elem>val</elem></root>',
            result_data=None,
            dry_run=True,
        )
        self.assertIsNone(data.parsed_xml)

    def test_post_init_skips_when_empty_raw_response(self):
        data = EppResultData(
            code=1000,
            message='Success',
            raw_response='',
            result_data=None,
        )
        self.assertIsNone(data.parsed_xml)

    def test_post_init_preserves_explicit_parsed_xml(self):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup('<custom/>', 'xml')
        data = EppResultData(
            code=1000,
            message='Success',
            raw_response='<other/>',
            result_data=None,
            parsed_xml=soup,
        )
        self.assertIs(data.parsed_xml, soup)

    @patch('pyepp.epp.BeautifulSoup', side_effect=Exception('XML parse failure'))
    def test_post_init_exception_handling(self, _mock_bs):
        data = EppResultData(
            code=1000,
            message='Success',
            raw_response='<root/>',
            result_data=None,
        )
        self.assertIsNone(data.parsed_xml)


class EppCommunicatorTest(unittest.TestCase):
    def setUp(self):
        self.epp = EppCommunicator('localhost', '700', dry_run=False)

    def test_execute_success_populates_parsed_xml(self):
        self.epp.greeting = b'greeting'
        response_xml = (
            b'<?xml version="1.0" encoding="UTF-8"?>\n'
            b'<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">\n'
            b'  <response>\n'
            b'    <result code="1000">\n'
            b'      <msg>Command completed successfully</msg>\n'
            b'    </result>\n'
            b'    <trID>\n'
            b'      <clTRID>ABC-123</clTRID>\n'
            b'      <svTRID>SRV-456</svTRID>\n'
            b'    </trID>\n'
            b'  </response>\n'
            b'</epp>'
        )
        self.epp._execute_command = MagicMock(return_value=response_xml)
        result = self.epp.execute("<xml/>")
        self.assertEqual(result.code, 1000)
        self.assertEqual(result.client_transaction_id, "ABC-123")
        self.assertEqual(result.server_transaction_id, "SRV-456")
        self.assertIsNotNone(result.parsed_xml)
        self.assertEqual(result.parsed_xml.find("result").get("code"), "1000")

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
        self.assertTrue(result.dry_run)
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
        self.assertTrue(result.dry_run)
        self.assertEqual(result.raw_response, cmd)
        self.assertIsNone(result.client_transaction_id)

    def test_execute_dry_run_invalid_xml(self):
        self.epp._dry_run = True
        cmd = "invalid <xml"
        result = self.epp.execute(cmd)
        self.assertEqual(result.code, 1000)
        self.assertEqual(result.message, "Dry run")
        self.assertTrue(result.dry_run)
        self.assertEqual(result.raw_response, cmd)
        self.assertIsNone(result.client_transaction_id)

    @patch("pyepp.epp.BeautifulSoup", side_effect=Exception("Parsing failed"))
    def test_execute_dry_run_bs4_exception(self, _mock_bs4):
        self.epp._dry_run = True
        cmd = "<epp><command></command></epp>"
        result = self.epp.execute(cmd)
        self.assertEqual(result.code, 1000)
        self.assertEqual(result.message, "Dry run")
        self.assertTrue(result.dry_run)
        self.assertIsNone(result.client_transaction_id)

    def test_dry_run_hello(self):
        self.epp._dry_run = True
        res = self.epp.hello()
        self.assertIn(b"<hello/>", res)

    def test_dry_run_logout_without_socket(self):
        """Verify logout() works safely without an active socket connection in dry_run."""
        self.epp._dry_run = True
        self.epp._socket = None
        result = self.epp.logout()
        self.assertEqual(result.code, 1000)
        self.assertEqual(result.message, "Dry run")
        self.assertTrue(result.dry_run)

    @patch('pyepp.epp.socket.socket')
    @patch('pyepp.epp.ssl.create_default_context')
    def test_connect_dry_run_no_network(self, mock_ssl, mock_socket):
        """Verify connect() returns mock greeting without opening socket or TLS context in dry_run."""
        epp = EppCommunicator('localhost', '700', dry_run=True)
        greeting = epp.connect()
        mock_ssl.assert_not_called()
        mock_socket.assert_not_called()
        self.assertIsNotNone(greeting)
        self.assertEqual(greeting, epp.greeting)
        self.assertIn(b"<svID>DryRun</svID>", greeting)

    @patch('pyepp.epp.socket.socket')
    @patch('pyepp.epp.ssl.create_default_context')
    def test_offline_library_flow(self, mock_ssl, mock_socket):
        """Verify the full library flow (connect -> login -> logout) works offline in dry_run."""
        epp = EppCommunicator('example.com', '700', dry_run=True)
        greeting = epp.connect()
        self.assertIn(b"<svID>DryRun</svID>", greeting)

        login_res = epp.login('testuser', 'testpass')
        self.assertEqual(login_res.code, 1000)
        self.assertTrue(login_res.dry_run)

        logout_res = epp.logout()
        self.assertEqual(logout_res.code, 1000)
        self.assertTrue(logout_res.dry_run)

        mock_ssl.assert_not_called()
        mock_socket.assert_not_called()

    def test_dry_run_exception(self):
        mock_result = EppResultData(
            code=1000,
            message="Dry run",
            raw_response="<xml/>",
            result_data=None,
            dry_run=True,
        )
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

    @patch('pyepp.epp.get_compiled_template')
    @patch('pyepp.epp.EppCommunicator.execute')
    def test_login_uses_cached_template(self, mock_execute, mock_get_template):
        mock_result = MagicMock()
        mock_result.code = 1000
        mock_execute.return_value = mock_result
        mock_tmpl = MagicMock()
        mock_tmpl.render.return_value = "<mock_login/>"
        mock_get_template.return_value = mock_tmpl

        self.epp.login('user', 'pass')
        mock_get_template.assert_called_once_with(LOGIN_XML)
        mock_tmpl.render.assert_called_once_with(user='user', password='pass', extensions=[])

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





