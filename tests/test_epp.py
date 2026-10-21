"""
EPP Communicator unit tests
"""
import json
import unittest
from dataclasses import dataclass
from unittest.mock import MagicMock, patch
import sys
import struct
import socket
import ssl

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

    def test_to_dict_excludes_parsed_xml_and_is_json_serializable(self):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup('<root><item>test</item></root>', 'xml')
        data = EppResultData(
            code=1000,
            message='Success',
            raw_response='<root><item>test</item></root>',
            result_data=None,
            parsed_xml=soup,
        )
        d = data.to_dict()
        self.assertNotIn('parsed_xml', d)
        serialized = json.dumps(d)
        deserialized = json.loads(serialized)
        self.assertEqual(deserialized['code'], 1000)
        self.assertEqual(deserialized['message'], 'Success')
        self.assertNotIn('parsed_xml', deserialized)

    def test_to_dict_converts_nested_dataclasses_in_result_data(self):
        from bs4 import BeautifulSoup

        @dataclass
        class SubData:
            tag: str

        @dataclass
        class MainData:
            name: str
            sub: SubData
            sub_list: list[SubData]
            sub_map: dict[str, SubData]

        main_data = MainData(
            name='parent',
            sub=SubData(tag='child'),
            sub_list=[SubData(tag='list_item')],
            sub_map={'key': SubData(tag='map_item')},
        )
        soup = BeautifulSoup('<xml/>', 'xml')
        data = EppResultData(
            code=1000,
            message='Success',
            raw_response='<xml/>',
            result_data=main_data,
            parsed_xml=soup,
        )
        d = data.to_dict()
        self.assertNotIn('parsed_xml', d)
        self.assertEqual(d['result_data']['sub'], {'tag': 'child'})
        self.assertEqual(d['result_data']['sub_list'], [{'tag': 'list_item'}])
        self.assertEqual(d['result_data']['sub_map'], {'key': {'tag': 'map_item'}})

        serialized = json.dumps(d)
        deserialized = json.loads(serialized)
        self.assertEqual(deserialized['result_data']['name'], 'parent')

    def test_to_dict_converts_list_and_dict_result_data(self):
        @dataclass
        class Item:
            id: int

        # Test with dict containing dataclasses
        data_dict = EppResultData(
            code=1000,
            message='Success',
            raw_response='<xml/>',
            result_data={'item1': Item(id=1)},
        )
        d_dict = data_dict.to_dict()
        self.assertEqual(d_dict['result_data']['item1'], {'id': 1})
        self.assertIn('"id": 1', json.dumps(d_dict))

        # Test with list containing dataclasses
        data_list = EppResultData(
            code=1000,
            message='Success',
            raw_response='<xml/>',
            result_data=[Item(id=2)],
        )
        d_list = data_list.to_dict()
        self.assertEqual(d_list['result_data'], [{'id': 2}])
        self.assertIn('"id": 2', json.dumps(d_list))


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
        self.assertIsNotNone(result.parsed_xml)

        # Regression check: to_dict excludes parsed_xml and is JSON-serializable
        d = result.to_dict()
        self.assertNotIn("parsed_xml", d)
        serialized = json.dumps(d)
        self.assertIn('"message": "Dry run"', serialized)

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

    def test_read_fragmented_header_and_body(self):
        """Confirm that reading 1-byte chunks for header and body reassembles correctly."""
        self.epp._ssl_socket = MagicMock()
        # Message length = 12 bytes (4 bytes header + 8 bytes payload: b"<xml/>\r\n")
        header_bytes = struct.pack(">I", 12)
        body_bytes = b"<xml/>\r\n"

        # Header delivered in 1-byte chunks
        self.epp._ssl_socket.read.side_effect = [bytes([b]) for b in header_bytes]
        # Body delivered in 1-byte chunks
        self.epp._ssl_socket.recv.side_effect = [bytes([b]) for b in body_bytes]

        result = self.epp._read()
        self.assertEqual(result, body_bytes)

    def test_read_multi_byte_chunks_reassembly(self):
        """Confirm that reading irregular chunk sizes correctly reassembles the body."""
        self.epp._ssl_socket = MagicMock()
        payload = b"A" * 100
        total_length = len(payload) + 4
        self.epp._ssl_socket.read.return_value = struct.pack(">I", total_length)
        # Deliver payload in chunks of 30, 30, 30, 10
        self.epp._ssl_socket.recv.side_effect = [b"A" * 30, b"A" * 30, b"A" * 30, b"A" * 10]

        result = self.epp._read()
        self.assertEqual(result, payload)

    def test_read_exact_zero_bytes(self):
        """_read_exact with 0 bytes returns b'' immediately."""
        self.epp._ssl_socket = MagicMock()
        self.assertEqual(self.epp._read_exact(0), b"")

    def test_read_exact_negative_bytes(self):
        """_read_exact with negative byte count raises EppCommunicatorException."""
        self.epp._ssl_socket = MagicMock()
        with self.assertRaises(EppCommunicatorException) as ctx:
            self.epp._read_exact(-5)
        self.assertIn("Invalid byte count requested: -5", str(ctx.exception))

    def test_read_empty_body(self):
        """Message with total length equal to 4 has 0-byte body and returns b''."""
        self.epp._ssl_socket = MagicMock()
        self.epp._ssl_socket.read.return_value = struct.pack(">I", 4)
        result = self.epp._read()
        self.assertEqual(result, b"")

    def test_read_premature_close_during_header(self):
        """Premature closure after partial header bytes raises EppCommunicatorException."""
        self.epp._ssl_socket = MagicMock()
        self.epp._ssl_socket.read.side_effect = [b"\x00\x00", b""]
        with self.assertRaises(EppCommunicatorException) as ctx:
            self.epp._read()
        self.assertIn("Connection closed prematurely after 2/4 bytes", str(ctx.exception))

    def test_read_premature_close_during_body(self):
        """Premature closure after partial body bytes raises EppCommunicatorException."""
        self.epp._ssl_socket = MagicMock()
        self.epp._ssl_socket.read.return_value = struct.pack(">I", 14)  # 10 bytes body
        self.epp._ssl_socket.recv.side_effect = [b"hello", b""]  # 5 bytes received out of 10
        with self.assertRaises(EppCommunicatorException) as ctx:
            self.epp._read()
        self.assertIn("Connection closed prematurely after 5/10 bytes", str(ctx.exception))

    def test_read_invalid_length_header_too_small(self):
        """Header with length < 4 bytes raises EppCommunicatorException."""
        self.epp._ssl_socket = MagicMock()
        self.epp._ssl_socket.read.return_value = struct.pack(">I", 2)
        with self.assertRaises(EppCommunicatorException) as ctx:
            self.epp._read()
        self.assertIn("Invalid EPP message length header: 2 bytes (minimum is 4 bytes)", str(ctx.exception))

    def test_read_length_header_exceeds_max_message_size(self):
        """Header with length exceeding max_message_size raises EppCommunicatorException (DoS protection)."""
        self.epp._ssl_socket = MagicMock()
        self.epp._ssl_socket.read.return_value = struct.pack(">I", 10 * 1024 * 1024 + 1)
        with self.assertRaises(EppCommunicatorException) as ctx:
            self.epp._read()
        self.assertIn("exceeds maximum allowed size", str(ctx.exception))

    def test_configurable_max_message_size(self):
        """Custom max_message_size can be configured in EppCommunicator."""
        epp = EppCommunicator('localhost', '700', dry_run=False, max_message_size=100)
        epp._ssl_socket = MagicMock()
        epp._ssl_socket.read.return_value = struct.pack(">I", 101)
        with self.assertRaises(EppCommunicatorException) as ctx:
            epp._read()
        self.assertIn("exceeds maximum allowed size (100 bytes)", str(ctx.exception))

    def test_read_socket_timeout(self):
        """Socket timeout during read raises EppCommunicatorException."""
        self.epp._ssl_socket = MagicMock()
        self.epp._ssl_socket.read.side_effect = socket.timeout("timed out")
        with self.assertRaises(EppCommunicatorException) as ctx:
            self.epp._read()
        self.assertIn("Socket timed out while receiving data", str(ctx.exception))

    def test_read_ssl_zero_return_error(self):
        """Clean TLS shutdown (SSLZeroReturnError) before bytes returns None."""
        self.epp._ssl_socket = MagicMock()
        self.epp._ssl_socket.read.side_effect = ssl.SSLZeroReturnError("TLS closed")
        result = self.epp._read()
        self.assertIsNone(result)

    def test_read_ssl_zero_return_error_after_partial(self):
        """SSLZeroReturnError after partial bytes raises EppCommunicatorException."""
        self.epp._ssl_socket = MagicMock()
        self.epp._ssl_socket.read.side_effect = [b"\x00\x00", ssl.SSLZeroReturnError("TLS closed")]
        with self.assertRaises(EppCommunicatorException) as ctx:
            self.epp._read()
        self.assertIn("Connection closed prematurely after 2/4 bytes", str(ctx.exception))

    def test_read_ssl_error(self):
        """SSLError during read raises EppCommunicatorException."""
        self.epp._ssl_socket = MagicMock()
        self.epp._ssl_socket.read.side_effect = ssl.SSLError("bad mac")
        with self.assertRaises(EppCommunicatorException) as ctx:
            self.epp._read()
        self.assertIn("SSL error while receiving data", str(ctx.exception))

    def test_read_os_error(self):
        """OSError / ConnectionResetError raises EppCommunicatorException."""
        self.epp._ssl_socket = MagicMock()
        self.epp._ssl_socket.read.side_effect = OSError("Connection reset by peer")
        with self.assertRaises(EppCommunicatorException) as ctx:
            self.epp._read()
        self.assertIn("Connection error while receiving data", str(ctx.exception))

    def test_read_socket_not_connected(self):
        """Calling _read or _read_exact when _ssl_socket is None raises EppCommunicatorException."""
        self.epp._ssl_socket = None
        with self.assertRaises(EppCommunicatorException) as ctx:
            self.epp._read()
        self.assertIn("Socket connection is not established.", str(ctx.exception))
        with self.assertRaises(EppCommunicatorException) as ctx:
            self.epp._read_exact(4)
        self.assertIn("Socket connection is not established.", str(ctx.exception))

    def test_read_from_socket_neither_read_nor_recv(self):
        """Calling _read_from_socket on an object without read or recv raises EppCommunicatorException."""
        self.epp._ssl_socket = object()
        with self.assertRaises(EppCommunicatorException) as ctx:
            self.epp._read_from_socket(4)
        self.assertIn("Socket has neither read nor recv method.", str(ctx.exception))

    def test_write_socket_not_connected(self):
        """Calling _write when _ssl_socket is None raises EppCommunicatorException."""
        self.epp._ssl_socket = None
        with self.assertRaises(EppCommunicatorException) as ctx:
            self.epp._write("<xml/>")
        self.assertIn("Socket connection is not established.", str(ctx.exception))

    def test_write_socket_timeout(self):
        """Socket timeout during _write raises EppCommunicatorException."""
        self.epp._ssl_socket = MagicMock()
        self.epp._ssl_socket.sendall.side_effect = socket.timeout("write timed out")
        with self.assertRaises(EppCommunicatorException) as ctx:
            self.epp._write("<xml/>")
        self.assertIn("Socket timed out while sending data", str(ctx.exception))

    def test_write_ssl_error(self):
        """SSLError during _write raises EppCommunicatorException."""
        self.epp._ssl_socket = MagicMock()
        self.epp._ssl_socket.sendall.side_effect = ssl.SSLError("SSL write error")
        with self.assertRaises(EppCommunicatorException) as ctx:
            self.epp._write("<xml/>")
        self.assertIn("SSL error while sending data", str(ctx.exception))

    def test_write_os_error(self):
        """OSError during _write raises EppCommunicatorException."""
        self.epp._ssl_socket = MagicMock()
        self.epp._ssl_socket.sendall.side_effect = OSError("Broken pipe")
        with self.assertRaises(EppCommunicatorException) as ctx:
            self.epp._write("<xml/>")
        self.assertIn("Connection error while sending data", str(ctx.exception))


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


class EppContextManagerTest(unittest.TestCase):
    """
    Tests for EppCommunicator Pythonic context manager protocol (USE-1)
    and session lifecycle / state tracking.
    """

    def test_context_manager_auto_connect_and_login_success(self):
        """Context manager with credentials auto-connects, logs in, and logs out on exit."""
        epp = EppCommunicator('localhost', '700', user='test_user', password='test_password')

        def fake_connect():
            epp._ssl_socket = MagicMock()
            return b'greeting'

        def fake_login(user, password, extensions=None):
            epp._logged_in = True
            return MagicMock(code=1000)

        epp.connect = MagicMock(side_effect=fake_connect)
        epp.login = MagicMock(side_effect=fake_login)
        epp.logout = MagicMock(return_value=MagicMock())

        with epp as client:
            self.assertIs(client, epp)
            epp.connect.assert_called_once()
            epp.login.assert_called_once_with('test_user', 'test_password', [])
            self.assertTrue(client.is_connected)
            self.assertTrue(client.is_logged_in)

        epp.logout.assert_called_once()
        self.assertFalse(epp.is_logged_in)

    def test_context_manager_with_extensions(self):
        """Context manager forwards configured extensions to login."""
        extensions = ['urn:ietf:params:xml:ns:secDNS-1.1']
        epp = EppCommunicator('localhost', '700', user='u', password='p', extensions=extensions)
        self.assertEqual(epp.extensions, extensions)

        epp.connect = MagicMock(side_effect=lambda: setattr(epp, '_ssl_socket', MagicMock()))
        epp.login = MagicMock(side_effect=lambda *a, **k: setattr(epp, '_logged_in', True))
        epp.logout = MagicMock()

        with epp:
            epp.login.assert_called_once_with('u', 'p', extensions)

        epp.logout.assert_called_once()

    def test_context_manager_no_credentials_only_connects(self):
        """Context manager without credentials connects but does not auto-login, disconnects on exit."""
        epp = EppCommunicator('localhost', '700')
        epp.connect = MagicMock(side_effect=lambda: setattr(epp, '_ssl_socket', MagicMock()))
        epp.login = MagicMock()
        epp.logout = MagicMock()
        epp.disconnect = MagicMock()

        with epp as client:
            self.assertIs(client, epp)
            epp.connect.assert_called_once()
            epp.login.assert_not_called()
            self.assertTrue(epp.is_connected)
            self.assertFalse(epp.is_logged_in)

        epp.logout.assert_not_called()
        epp.disconnect.assert_called_once()

    def test_context_manager_manual_login_inside_block(self):
        """Manual login inside block marks is_logged_in and triggers logout on exit."""
        epp = EppCommunicator('localhost', '700')
        epp.connect = MagicMock(return_value=b'greeting')
        epp.logout = MagicMock()
        epp.execute = MagicMock(return_value=MagicMock(code=1000, message='OK'))
        epp._ssl_socket = MagicMock()

        with epp:
            self.assertFalse(epp.is_logged_in)
            epp.login('manual_user', 'manual_pass')
            self.assertTrue(epp.is_logged_in)

        epp.logout.assert_called_once()

    def test_context_manager_exception_in_block_propagates_and_cleans_up(self):
        """Exception raised within context block propagates and still triggers logout and disconnect."""
        epp = EppCommunicator('localhost', '700', user='u', password='p')
        epp.connect = MagicMock(return_value=b'greeting')
        epp.login = MagicMock(return_value=MagicMock(code=1000))
        epp.logout = MagicMock()
        epp._ssl_socket = MagicMock()
        # Simulate logged in
        epp._logged_in = True

        with self.assertRaises(RuntimeError) as ctx:
            with epp:
                raise RuntimeError("Custom failure inside context")

        self.assertEqual(str(ctx.exception), "Custom failure inside context")
        epp.logout.assert_called_once()

    def test_context_manager_logout_failure_does_not_mask_block_exception(self):
        """Logout error during context exit cleanup is logged at debug and does not mask original error."""
        epp = EppCommunicator('localhost', '700', user='u', password='p')
        epp.connect = MagicMock(return_value=b'greeting')
        epp.login = MagicMock(return_value=MagicMock(code=1000))
        logout_err = EppCommunicatorException("Logout network error")
        epp.logout = MagicMock(side_effect=logout_err)
        epp._ssl_socket = MagicMock()
        epp._logged_in = True

        with self.assertLogs(level='DEBUG') as log:
            with self.assertRaises(ValueError) as ctx:
                with epp:
                    raise ValueError("Original business error")

        self.assertEqual(str(ctx.exception), "Original business error")
        self.assertIs(epp.last_logout_error, logout_err)
        self.assertTrue(
            any("Error during EppCommunicator context exit cleanup while handling exception" in msg for msg in log.output)
        )

    def test_context_manager_logout_failure_normal_exit_logs_warning_and_records_state(self):
        """Logout failure on normal context exit logs at WARNING level and records last_logout_error."""
        epp = EppCommunicator('localhost', '700', user='u', password='p')
        epp.connect = MagicMock(return_value=b'greeting')
        epp.login = MagicMock(return_value=MagicMock(code=1000))
        logout_err = EppCommunicatorException("Clean logout timeout from server")
        epp.logout = MagicMock(side_effect=logout_err)
        epp._ssl_socket = MagicMock()
        epp._logged_in = True

        with self.assertLogs(level='WARNING') as log:
            with epp:
                pass  # block finishes normally

        self.assertIs(epp.last_logout_error, logout_err)
        self.assertTrue(
            any("Logout failed during context exit cleanup: Clean logout timeout from server" in msg
                for msg in log.output)
        )

    def test_last_logout_error_reset_on_enter(self):
        """Entering a new context resets last_logout_error to None."""
        epp = EppCommunicator('localhost', '700', dry_run=True, user='u', password='p')
        epp._last_logout_error = RuntimeError("Old error")
        self.assertIsNotNone(epp.last_logout_error)
        with epp:
            self.assertIsNone(epp.last_logout_error)
        self.assertIsNone(epp.last_logout_error)

    def test_context_manager_login_failure_in_enter_disconnects_socket(self):
        """If login fails during __enter__, socket is immediately closed to prevent descriptor leak."""
        epp = EppCommunicator('localhost', '700', user='u', password='bad_pass')
        epp.connect = MagicMock(side_effect=lambda: setattr(epp, '_ssl_socket', MagicMock()))
        epp.login = MagicMock(side_effect=EppCommunicatorException("Auth error 2200"))
        epp.disconnect = MagicMock()

        with self.assertRaises(EppCommunicatorException) as ctx:
            with epp:
                pass

        self.assertIn("Auth error 2200", str(ctx.exception))
        epp.connect.assert_called_once()
        epp.disconnect.assert_called_once()

    def test_context_manager_connect_failure_in_enter(self):
        """If connect fails in __enter__, exception propagates cleanly."""
        epp = EppCommunicator('localhost', '700')
        epp.connect = MagicMock(side_effect=EppCommunicatorException("Connection refused"))

        with self.assertRaises(EppCommunicatorException) as ctx:
            with epp:
                pass

        self.assertIn("Connection refused", str(ctx.exception))

    def test_context_manager_already_connected_does_not_reconnect(self):
        """If communicator is already connected, __enter__ skips reconnect."""
        epp = EppCommunicator('localhost', '700', user='u', password='p')
        epp._ssl_socket = MagicMock()  # makes is_connected True
        epp.connect = MagicMock()
        epp.login = MagicMock(return_value=MagicMock(code=1000))
        epp.logout = MagicMock()

        with epp:
            epp.connect.assert_not_called()
            epp.login.assert_called_once()

    def test_context_manager_explicit_logout_inside_block(self):
        """Calling logout explicitly inside block resets is_logged_in and avoids double-logout on exit."""
        epp = EppCommunicator('localhost', '700', user='u', password='p')
        epp.connect = MagicMock(return_value=b'greeting')
        epp.login = MagicMock(side_effect=lambda *a, **k: setattr(epp, '_logged_in', True))
        epp.logout = MagicMock(side_effect=lambda: setattr(epp, '_logged_in', False))
        epp._ssl_socket = MagicMock()

        with epp:
            self.assertTrue(epp.is_logged_in)
            epp.logout()
            self.assertFalse(epp.is_logged_in)

        # logout called once manually, NOT a second time on exit
        self.assertEqual(epp.logout.call_count, 1)

    def test_context_manager_dry_run_full_cycle(self):
        """Context manager with dry_run=True connects, logs in, executes, and cleans up offline."""
        epp = EppCommunicator('localhost', '700', dry_run=True, user='dry_user', password='dry_password')
        with epp as client:
            self.assertTrue(client.is_connected)
            self.assertTrue(client.is_logged_in)
            res = client.execute("<xml><command><clTRID>ABC</clTRID></command></xml>")
            self.assertTrue(res.dry_run)
            self.assertEqual(res.code, 1000)

        self.assertFalse(epp.is_connected)
        self.assertFalse(epp.is_logged_in)

    def test_context_manager_reusable(self):
        """EppCommunicator instance can be reused across multiple with statements."""
        epp = EppCommunicator('localhost', '700', dry_run=True, user='u', password='p')
        with epp:
            self.assertTrue(epp.is_logged_in)
        self.assertFalse(epp.is_logged_in)

        with epp:
            self.assertTrue(epp.is_logged_in)
        self.assertFalse(epp.is_logged_in)

    def test_repr_masks_password(self):
        """__repr__ must expose server, port, user, but NEVER secret password or keys."""
        epp = EppCommunicator(
            'registry.example.com',
            '700',
            user='admin_user',
            password='super_secret_password',
            client_cert='cert.pem',
            client_key='key.pem',
            dry_run=False,
        )
        repr_str = repr(epp)
        self.assertNotIn('super_secret_password', repr_str)
        self.assertIn('registry.example.com', repr_str)
        self.assertIn('admin_user', repr_str)
        self.assertIn('logged_in=False', repr_str)
        self.assertIn('dry_run=False', repr_str)

    def test_login_execute_exception_resets_logged_in(self):
        """If execute() throws an unexpected exception during login(), _logged_in remains False."""
        epp = EppCommunicator('localhost', '700')
        epp.execute = MagicMock(side_effect=EppCommunicatorException("Connection aborted"))

        with self.assertRaises(EppCommunicatorException):
            epp.login('user', 'pass')

        self.assertFalse(epp.is_logged_in)

    def test_login_failure_resets_logged_in(self):
        """Login returning non-success result code sets _logged_in to False and raises."""
        epp = EppCommunicator('localhost', '700')
        mock_result = MagicMock()
        mock_result.code = 2200
        mock_result.message = "Authentication error"
        mock_result.reason = "Bad credentials"
        epp.execute = MagicMock(return_value=mock_result)

        with self.assertRaises(EppCommunicatorException) as ctx:
            epp.login('user', 'pass')

        self.assertIn("Auth", str(ctx.exception))
        self.assertFalse(epp.is_logged_in)

    def test_login_parameter_range_error_resets_logged_in(self):
        """Login returning PARAMETER_RANGE_ERROR sets _logged_in to False and raises."""
        epp = EppCommunicator('localhost', '700')
        mock_result = MagicMock()
        mock_result.code = 2004
        mock_result.message = "Parameter range error"
        mock_result.reason = "Invalid"
        epp.execute = MagicMock(return_value=mock_result)

        with self.assertRaises(EppCommunicatorException) as ctx:
            epp.login('user', 'pass')

        self.assertIn("Incorrect user name or password", str(ctx.exception))
        self.assertFalse(epp.is_logged_in)

    def test_properties_state_flow(self):
        """Verify user, extensions, is_connected, and is_logged_in properties."""
        epp = EppCommunicator('localhost', '700', user='my_user')
        self.assertEqual(epp.user, 'my_user')
        self.assertEqual(epp.extensions, [])
        self.assertFalse(epp.is_connected)
        self.assertFalse(epp.is_logged_in)

        # After connecting in dry run
        epp._dry_run = True
        epp.connect()
        self.assertTrue(epp.is_connected)
        self.assertFalse(epp.is_logged_in)

        # After disconnecting
        epp.disconnect()
        self.assertFalse(epp.is_connected)
        self.assertFalse(epp.is_logged_in)





