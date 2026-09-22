"""
EPP Communicator unit tests
"""
import unittest
from unittest.mock import MagicMock, patch
import sys
import struct
import socket

from pyepp.epp import EppCommunicator, EppResultData, EppCommunicatorException

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

    @patch('pyepp.epp.sys.exit')
    def test_execute_command_dry_run(self, mock_exit):
        mock_exit.side_effect = SystemExit
        self.epp._dry_run = True
        with self.assertRaises(SystemExit):
            self.epp._execute_command("test")
        mock_exit.assert_called_once()

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
        self.assertIn("Could not setup a sec sure connection", str(context.exception))

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

    @patch('pyepp.epp.EppCommunicator.execute')
    def test_login_with_extensions(self, mock_execute):
        mock_result = MagicMock()
        mock_result.code = 1000
        mock_execute.return_value = mock_result
        self.epp.login('user', 'pass', extensions=['urn:ietf:params:xml:ns:secDNS-1.1'])
        self.assertEqual(self.epp.user, 'user')

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
