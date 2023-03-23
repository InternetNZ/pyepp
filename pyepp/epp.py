"""
EPP Communicator Module
"""
import ssl
import socket
import struct
import logging

from bs4 import BeautifulSoup

from command_templates import LOGOUT_XML, LOGIN_XML, HELLO_XML
from helper import xml_pretty

LENGTH_FIELD_SIZE = 4
CRLF_SIZE = 2


class EppCommunicatorException(Exception):
    pass


class EppCommunicator:
    """
    An EPP client for connecting to EPP server.
    """

    def __init__(self, host, port, client_cert, client_key):
        self._host = host
        self._port = port
        self._user = None

        self._client_cert = client_cert
        self._client_key = client_key

        self._format_32 = self._format_32()

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.settimeout(10)
        self._socket.connect((self._host, int(self._port)))

        try:
            self._ssl = ssl.wrap_socket(
                self._socket,
                certfile=self._client_cert,
                keyfile=self._client_key)
            self.greeting = self._read()
            logging.debug(BeautifulSoup(self.greeting, 'xml'))
        except socket.error as ex:
            logging.error("Could not setup a sec sure connection. " + str(ex))

    def _format_32(self):
        """
        Get the size of C integers. We need 32 bits unsigned.

        From http://www.bortzmeyer.org/4934.html
        """
        format_32 = ">I"
        if struct.calcsize(format_32) < LENGTH_FIELD_SIZE:
            format_32 = ">L"
            if struct.calcsize(format_32) != LENGTH_FIELD_SIZE:
                logging.error("Could not setup a secure connection.")
        elif struct.calcsize(format_32) > LENGTH_FIELD_SIZE:
            format_32 = ">H"
            if struct.calcsize(format_32) != LENGTH_FIELD_SIZE:
                logging.error("Could not setup a secure connection.")

        return format_32

    def _unpack_data(self, data):
        """
        Unpack data.

        :param bytes data: data

        :return: unpacked data
        :rtype: str
        """
        return struct.unpack(self._format_32, data)[0]

    def _pack_data(self, data):
        """
        Pack the data.

        :param data: data

        :return: bytes
        """
        return struct.pack(self._format_32, data)

    def _read(self):
        """
        Read the response from the socket.

        :return: Response
        :rtype: bytes
        """
        length = self._ssl.read(LENGTH_FIELD_SIZE)
        buffer = bytes()

        if not length:
            return None

        total_bytes = self._unpack_data(length) - LENGTH_FIELD_SIZE
        while len(buffer) < total_bytes:
            total_bytes = total_bytes - len(buffer)
            buffer += self._ssl.recv(total_bytes)
            logging.info(f'Received {len(buffer)}/{total_bytes} bytes')
        return buffer

    def _write(self, xml):
        """
        Write the request into the socket.

        :param str xml: XML Command

        :return: Number of send bytes
        :rtype: int
        """
        # +4 for the length field itself (section 4 mandates that)
        # +2 for the CRLF at the end
        length = self._pack_data(len(xml) + LENGTH_FIELD_SIZE + CRLF_SIZE)

        self._ssl.send(length)
        xml += "\r\n"
        return self._ssl.send(xml.encode("utf-8"))

    def _execute_command(self, cmd):
        """
        Execute the command. Sending the request to the server and receive the response.

        :param str cmd: XML command

        :return: Response
        :rtype: bytes
        """
        logging.debug("Sending xml to server :\n{0}".format(cmd))

        self._write(cmd)

        response = self._read()
        if response is None:
            raise EppCommunicatorException("Cannot connect to server. Please re-login!")

        logging.debug("Received xml response from server :\n{0}".format(response))

        return response

    def execute(self, cmd):
        """
        Execute the command. Sending the request to the server and receive the response.

        :param str cmd: XML Command

        :return: XML Response
        :rtype: str
        """
        try:

            r = self._execute_command(cmd)
            xml_response = BeautifulSoup(r, 'xml')

            response = xml_response.find('response')
            result = xml_response.find('result')
            message = result.find('msg').string

            try:
                code = int(result.get('code'))
            except AttributeError:
                raise EppCommunicatorException("Could not get result code.")

            reason = None
            if code not in (1000, 1500):
                reason = result.find('reason').string if result.find('reason') else None

            logging.debug("Command executed:\n{}".format(xml_pretty(xml_response)))

            return {'code': code, 'message': message, 'reason': reason, 'response': response}
        except EppCommunicatorException as epp_ex:
            raise epp_ex
        except Exception as ex:
            raise EppCommunicatorException(ex) from ex

    def hello(self):
        """
        Send Hello command the server.

        :return: Greeting response
        :rtype: xml
        """
        logging.debug("Send Hello command to the server!")
        greeting = self._execute_command(HELLO_XML)
        return greeting

    def login(self, user, password):
        """
        Login the user to EPP server.

        :param str user: username
        :param str password: password
        :return:
        """
        self._user = user

        cmd = LOGIN_XML.format(user=user, password=password)
        result = self.execute(cmd)

        if result.get('code') == 1000:
            logging.info("User {0} logged in to {1}:{2}".format(self._user, self._host, self._port))
        elif result.get('code') == 2004:
            raise EppCommunicatorException('Incorrect user name or password. Please try again!')
        else:
            raise EppCommunicatorException('Something went wrong! Code: {} - Message: {} - Reason {}'.
                                           format(result.get('code'), result.get('message'), result.get('reason')))

        return result

    def logout(self):
        """
        Logout the user from EPP server.
        """

        self.execute(LOGOUT_XML)
        self._socket.close()
        logging.info("User {0} logged out from {1}:{2}".format(self._user, self._host, self._port))
