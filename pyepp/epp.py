"""
EPP Communicator Module
"""
import ssl
import socket
import struct
import logging
from enum import Enum

from bs4 import BeautifulSoup

from pyepp.command_templates import LOGOUT_XML, LOGIN_XML, HELLO_XML

LENGTH_FIELD_SIZE = 4
CRLF_SIZE = 2


class EppCommunicatorException(Exception):
    """
    EPP communicator exception
    """


class EppResultCode(Enum):
    """
    EPP result codes enum
    """
    SUCCESS = 1000
    SUCCESS_END_SESSION = 1500
    PARAMETER_RANGE_ERROR = 2004


def get_format_32() -> str:
    """
    Get the size of C integers. We need 32 bits unsigned.

    From http://www.bortzmeyer.org/4934.html
    """
    format_32 = ">I"
    if struct.calcsize(format_32) < LENGTH_FIELD_SIZE:
        format_32 = ">L"
        if struct.calcsize(format_32) != LENGTH_FIELD_SIZE:
            logging.error("Integer size does not match the length size!")
            raise EppCommunicatorException("Integer size does not match the length size!")
    elif struct.calcsize(format_32) > LENGTH_FIELD_SIZE:
        format_32 = ">H"
        if struct.calcsize(format_32) != LENGTH_FIELD_SIZE:
            logging.error("Integer size does not match the length size!")
            raise EppCommunicatorException("Integer size does not match the length size!")

    return format_32


class EppCommunicator:
    """
    An EPP client for connecting to EPP server.
    """

    # pylint: disable=too-many-instance-attributes
    def __init__(self, host: str, port: str, client_cert: str, client_key: str) -> None:
        """
        :param str host: Host name
        :param str port: Port number
        :param str client_cert: Path client certificate
        :param str client_key: Path to client key
        """
        self._host = host
        self._port = port
        self._user = None
        self._client_cert = client_cert
        self._client_key = client_key

        self._format_32 = get_format_32()

        self._context = None
        self._socket = None
        self._ssl_socket = None
        self.greeting = None

    @property
    def user(self):
        """User property
        """
        return self._user

    def _unpack_data(self, data: int) -> str:
        """
        Unpack data.

        :param bytes data: data

        :return: unpacked data
        :rtype: str
        """
        return struct.unpack(self._format_32, data)[0]

    def _pack_data(self, data: int) -> bytes:
        """
        Pack the data.

        :param data: data

        :return: bytes
        """
        return struct.pack(self._format_32, data)

    def _read(self) -> bytes:
        """
        Read the response from the socket.

        :return: Response
        :rtype: bytes
        """
        length = self._ssl_socket.read(LENGTH_FIELD_SIZE)
        buffer = bytes()

        if not length:
            return None

        total_bytes = self._unpack_data(length) - LENGTH_FIELD_SIZE
        while len(buffer) < total_bytes:
            total_bytes = total_bytes - len(buffer)
            buffer += self._ssl_socket.recv(total_bytes)
            logging.info('Received %s/%s bytes', len(buffer), total_bytes)
        return buffer

    def _write(self, xml: str) -> int:
        """
        Write the request into the socket.

        :param str xml: XML Command

        :return: Number of send bytes
        :rtype: int
        """
        # +4 for the length field itself (section 4 mandates that)
        # +2 for the CRLF at the end
        length = self._pack_data(len(xml) + LENGTH_FIELD_SIZE + CRLF_SIZE)

        self._ssl_socket.send(length)
        xml += "\r\n"
        return self._ssl_socket.send(xml.encode("utf-8"))

    def _execute_command(self, cmd: str) -> bytes:
        """
        Execute the command. Sending the request to the server and receive the response.

        :param str cmd: XML command

        :return: Response
        :rtype: bytes
        """
        logging.debug("Sending xml to server :\n%s", cmd)

        self._write(cmd)

        response = self._read()
        if response is None:
            raise EppCommunicatorException("Cannot connect to server. Please re-login!")

        logging.debug("Received xml response from server :\n%s", response)

        return response

    def connect(self) -> bytes:
        """
        Initial connect to the server.

        :return: Greeting message
        :rtype: bytes

        :raises EppCommunicatorException: When there is any errors
        """
        try:
            self._context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            self._context.load_default_certs()
            self._context.load_cert_chain(certfile=self._client_cert, keyfile=self._client_key)

            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
            self._socket.settimeout(10)

            self._ssl_socket = self._context.wrap_socket(self._socket, server_hostname=self._host)
            self._ssl_socket.connect((self._host, int(self._port)))
            self.greeting = self._read()
            logging.debug(BeautifulSoup(self.greeting, 'xml'))
            return self.greeting
        except Exception as ex:
            logging.error("Could not setup a sec sure connection. %s", str(ex))
            raise EppCommunicatorException("Could not setup a sec sure connection") from ex

    def execute(self, cmd: str) -> dict:
        """
        Execute the command. Sending the request to the server and receive the response.

        :param str cmd: XML Command

        :return: XML Response
        :rtype: dict

        :raises EppCommunicatorException: When there is any errors.
        """
        try:
            if not self.greeting:
                raise EppCommunicatorException("The connection to the server has not been established yet!")

            raw_response = self._execute_command(cmd)
            xml_response = BeautifulSoup(raw_response, 'xml')

            response = xml_response.find('response')
            result = xml_response.find('result')
            message = result.find('msg').string

            try:
                code = int(result.get('code'))
            except AttributeError as exc:
                raise EppCommunicatorException("Could not get result code.") from exc

            reason = None
            if code not in (EppResultCode.SUCCESS.value, EppResultCode.SUCCESS_END_SESSION.value):
                reason = result.find('reason').string if result.find('reason') else None

            client_transaction_id = response.find('clTRID').text if response.find('clTRID') else None
            server_transaction_id = response.find('svTRID').text if response.find('svTRID') else None
            repository_object_id = response.find('roid').text if response.find('roid') else None

            logging.debug("Command executed:\n%s", xml_response)

            return {
                'code': code,
                'message': message,
                'reason': reason,
                'raw_response': str(response),
                'client_transaction_id': client_transaction_id,
                'server_transaction_id': server_transaction_id,
                'repository_object_id': repository_object_id,
            }
        except EppCommunicatorException as epp_ex:
            raise epp_ex
        except Exception as ex:
            raise EppCommunicatorException(ex) from ex

    def hello(self) -> bytes:
        """
        Send Hello command the server.

        :return: Greeting response
        :rtype: bytes
        """
        logging.debug("Send Hello command to the server!")
        greeting = self._execute_command(HELLO_XML)
        return greeting

    def login(self, user: str, password: str) -> dict:
        """
        Login the user to EPP server.

        :param str user: username
        :param str password: password

        :return: login
        :rtype: dict

        :raises EppCommunicatorException: When there are any errors.
        """
        self._user = user

        cmd = LOGIN_XML.format(user=user, password=password)
        result = self.execute(cmd)

        if result.get('code') == EppResultCode.SUCCESS.value:
            logging.info("User %s logged in to %s:%s", self._user, self._host, self._port)
        elif result.get('code') == EppResultCode.PARAMETER_RANGE_ERROR.value:
            raise EppCommunicatorException("Incorrect user name or password. Please try again!")
        else:
            raise EppCommunicatorException(f"Something went wrong! Code: {result.get('code')} - Message: "
                                           f"{result.get('message')} - Reason {result.get('reason')}")

        return result

    def logout(self) -> dict:
        """
        Logout the user from EPP server.
        """

        logout = self.execute(LOGOUT_XML)
        self._socket.close()
        logging.info("User %s logged out from %s:%s", self._user, self._host, self._port)

        return logout
