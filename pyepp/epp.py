"""
EPP Communicator Module
"""

import ssl
import socket
import struct
import logging
import re
from xml.parsers import expat
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Optional, Any, Union

from bs4 import BeautifulSoup

from pyepp.command_templates import LOGOUT_XML, LOGIN_XML, HELLO_XML, template_engine

LENGTH_FIELD_SIZE = 4
CRLF_SIZE = 2

PASSWORD_TAG_FALLBACK_REGEX = re.compile(
    r"(?P<open><(?P<tag>(?:[\w.-]+:)?(?:pw|newPW))\b[^>]*>)(?:.*?(?P<close></(?P=tag)\s*>)|.*$)",
    re.IGNORECASE | re.DOTALL,
)
PASSWORD_TAG_REGEX = PASSWORD_TAG_FALLBACK_REGEX


def _is_sensitive_tag(name: str) -> bool:
    """
    Check if an XML element name corresponds to a sensitive password tag.

    :param str name: XML element tag name (with optional namespace prefix)
    :return: True if sensitive, False otherwise
    :rtype: bool
    """
    local_name = name.split(":")[-1]
    return local_name.lower() in ("pw", "newpw")


def _find_tag_end(data: bytes, start_idx: int, max_idx: int) -> int:
    """
    Find the index immediately following the closing '>' of an opening tag.

    :param bytes data: Raw XML payload bytes
    :param int start_idx: Starting index of the opening tag
    :param int max_idx: Upper bound index to search within
    :return: Offset immediately following '>', or -1 if not found
    :rtype: int
    """
    in_quote = None
    for idx in range(start_idx, max_idx):
        char = data[idx : idx + 1]
        if in_quote:
            if char == in_quote:
                in_quote = None
        elif char in (b'"', b"'"):
            in_quote = char
        elif char == b">":
            return idx + 1
    return -1


def _mask_with_expat(data: bytes) -> Optional[bytes]:
    """
    Mask sensitive tags in XML using expat parser element boundaries.

    :param bytes data: Raw XML bytes
    :return: Masked XML bytes, or None if parsing fails
    :rtype: Optional[bytes]
    """
    stripped = data.lstrip()
    is_wrapped = False
    to_parse = data
    if not stripped.startswith(b"<?xml"):
        to_parse = b"<root>" + data + b"</root>"
        is_wrapped = True

    parser = expat.ParserCreate()
    replacements = []
    stack = []

    def start_element(name, _attrs):
        if _is_sensitive_tag(name):
            stack.append((name, parser.CurrentByteIndex))

    def end_element(name):
        end_tag_start = parser.CurrentByteIndex
        if stack and stack[-1][0] == name:
            _, start_idx = stack.pop()
            tag_end = _find_tag_end(to_parse, start_idx, end_tag_start)
            if tag_end != -1 and not to_parse[start_idx:tag_end].rstrip().endswith(b"/>"):
                replacements.append((tag_end, end_tag_start))

    parser.StartElementHandler = start_element
    parser.EndElementHandler = end_element

    try:
        parser.Parse(to_parse, True)
    except (expat.ExpatError, ValueError):
        return None

    if not replacements:
        return data

    outermost_replacements = []
    for start, end in sorted(replacements):
        if not outermost_replacements or end > outermost_replacements[-1][1]:
            outermost_replacements.append((start, end))

    out = to_parse
    for start, end in reversed(outermost_replacements):
        out = out[:start] + b"***" + out[end:]

    if is_wrapped:
        out = out[len(b"<root>") : -len(b"</root>")]
    return out


def mask_sensitive_xml(xml_content: Union[str, bytes, Any]) -> str:
    """
    Mask sensitive XML elements like passwords prior to logging.

    :param xml_content: XML payload in string or bytes
    :return: XML string with masked sensitive fields
    :rtype: str
    """
    if isinstance(xml_content, bytes):
        raw_bytes = xml_content
    else:
        raw_bytes = str(xml_content).encode("utf-8", errors="replace")

    masked_bytes = _mask_with_expat(raw_bytes)
    if masked_bytes is not None:
        return masked_bytes.decode("utf-8", errors="replace")

    content_str = raw_bytes.decode("utf-8", errors="replace")

    def repl(match):
        close = match.group("close") or ""
        return match.group("open") + "***" + close

    return PASSWORD_TAG_FALLBACK_REGEX.sub(repl, content_str)


class EppCommunicatorException(Exception):
    """
    EPP communicator exception.
    """


class EppResultCode(Enum):
    """
    EPP result codes enumeration.
    """

    SUCCESS = 1000
    SUCCESS_ACTION_PENDING = 1001
    SUCCESS_NO_MESSAGE = 1300
    SUCCESS_ACK_TO_DEQUEUE = 1301
    SUCCESS_END_SESSION = 1500
    UNKNOWN_COMMAND = 2000
    COMMAND_SYNTAX_ERROR = 2001
    COMMAND_USE_ERROR = 2002
    REQUIRED_PARAMETER_MISSING = 2003
    PARAMETER_RANGE_ERROR = 2004
    PARAMETER_SYNTAX_ERROR = 2005
    UNIMPLEMENTED_PROTOCOL_VERSION = 2100
    UNIMPLEMENTED_COMMAND = 2101
    UNIMPLEMENTED_OPTION = 2102
    UNIMPLEMENTED_EXTENSION = 2103
    BILLING_FAILURE = 2104
    OBJECT_NOT_ELIGIBLE_FOR_RENEWAL = 2105
    OBJECT_NOT_ELIGIBLE_FOR_TRANSFER = 2106
    AUTHENTICATION_ERROR = 2200
    AUTHORIZATION_ERROR = 2201
    INVALID_AUTHORIZATION_INFORMATION = 2202
    OBJECT_PENDING_TRANSFER = 2300
    OBJECT_NOT_PENDING_TRANSFER = 2301
    OBJECT_EXISTS = 2302
    OBJECT_DOES_NOT_EXIST = 2303
    OBJECT_STATUS_PROHIBITS_OPERATION = 2304
    OBJECT_ASSOCIATION_PROHIBITS_OPERATION = 2305
    PARAMETER_VALUE_POLICY_ERROR = 2306
    UNIMPLEMENTED_OBJECT_SERVICE = 2307
    DATA_MANAGEMENT_POLICY_VIOLATION = 2308
    COMMAND_FAILED = 2400
    COMMAND_FAILED_CLOSING_CONNECTION = 2500
    AUTHENTICATION_ERROR_CLOSING_CONNECTION = 2501
    SESSION_LIMIT_EXCEEDED_CLOSING_CONNECTION = 2502


def get_format_32() -> str:
    """
    Get the size of C integers. We need 32 bits unsigned.

    From http://www.bortzmeyer.org/4934.html
    """
    return ">I"


# pylint: disable=too-many-instance-attributes
@dataclass
class EppResultData:
    """Epp result data structure."""

    code: int
    message: str
    raw_response: str
    result_data: Any
    reason: Optional[str] = None
    client_transaction_id: Optional[str] = None
    server_transaction_id: Optional[str] = None
    repository_object_id: Optional[str] = None
    dry_run: bool = False  # True if the command was executed offline in dry-run mode

    def __setitem__(self, key, value):
        self.__dict__[key] = value

    def __getitem__(self, key):
        return self.__dict__[key]

    def __len__(self):
        return len(self.__dict__)

    def to_dict(self) -> dict:
        """Convert an EppResultData object to a dictionary."""
        return asdict(self)


class EppDryRunException(EppCommunicatorException):
    """
    Exception raised or used to represent dry-run execution.
    """

    def __init__(self, cmd: str, result: Optional[EppResultData] = None) -> None:
        self.cmd = cmd
        self.result = result
        super().__init__(f"Dry run: {cmd}")


class EppCommunicator:
    """
    An EPP client for connecting to EPP server.
    """

    # pylint: disable=too-many-instance-attributes,too-many-arguments
    def __init__(
        self,
        server: str,
        port: str,
        client_cert: Optional[str] = None,
        client_key: Optional[str] = None,
        dry_run: Optional[bool] = False,
    ) -> None:
        """
        :param server: EPP server to connect to.
        :param port: EPP port to connect to.
        :param client_cert: Path to client certificate
        :param client_key: Path to client key
        :param dry_run: dry run the request
        """
        self._server = server
        self._port = port
        self._user = None
        self._client_cert = client_cert
        self._client_key = client_key

        self._dry_run = dry_run

        self._format_32 = get_format_32()

        self._context = None
        self._socket = None
        self._ssl_socket = None
        self.greeting = None

    @property
    def user(self):
        """User property"""
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
        :rtype: Optional[bytes]
        """
        length = self._ssl_socket.read(LENGTH_FIELD_SIZE)
        buffer = bytes()

        if not length:
            return None

        total_bytes = self._unpack_data(length) - LENGTH_FIELD_SIZE
        while len(buffer) < total_bytes:
            remaining = total_bytes - len(buffer)
            chunk = self._ssl_socket.recv(remaining)
            if not chunk:
                return None
            buffer += chunk
            logging.debug("Received %s/%s bytes", len(buffer), total_bytes)
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
        xml_bytes = xml.encode("utf-8")
        length = self._pack_data(len(xml_bytes) + LENGTH_FIELD_SIZE + CRLF_SIZE)

        self._ssl_socket.sendall(length)
        xml += "\r\n"
        data_to_send = xml.encode("utf-8")
        self._ssl_socket.sendall(data_to_send)
        logging.debug("Sent %s bytes", len(data_to_send))
        return len(data_to_send)

    def _execute_command(self, cmd: str) -> bytes:
        """
        Execute the command. Sending the request to the server and receive the response.

        :param str cmd: XML command

        :return: Response
        :rtype: bytes
        """

        # In dry-run mode, return the command bytes without transmitting over the network
        if self._dry_run:
            logging.debug(
                "Dry run - command not sent to server:\n%s", mask_sensitive_xml(cmd)
            )
            return cmd.encode("utf-8")

        logging.debug("Sending xml to server :\n%s", mask_sensitive_xml(cmd))

        self._write(cmd)

        response = self._read()
        if response is None:
            raise EppCommunicatorException("Cannot connect to server. Please re-login!")

        logging.debug(
            "Received xml response from server :\n%s", mask_sensitive_xml(response)
        )

        return response

    def connect(self) -> bytes:
        """
        Initial connect to the server.

        :return: Greeting message
        :rtype: bytes

        :raises EppCommunicatorException: When there is any errors
        """
        # In dry-run mode, bypass socket and TLS handshake and simulate a server greeting
        if self._dry_run:
            logging.debug("Dry run - skipping network connection")
            self.greeting = (
                b'<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">'
                b"<greeting><svID>DryRun</svID></greeting></epp>"
            )
            return self.greeting

        try:
            self._context = ssl.create_default_context()
            self._context.minimum_version = ssl.TLSVersion.TLSv1_2
            self._context.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1
            self._context.load_default_certs()
            if self._client_cert and self._client_key:
                self._context.load_cert_chain(
                    certfile=self._client_cert, keyfile=self._client_key
                )
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
            self._socket.settimeout(10)

            self._ssl_socket = self._context.wrap_socket(
                self._socket, server_hostname=self._server
            )
            self._ssl_socket.connect((self._server, int(self._port)))
            self.greeting = self._read()
            logging.debug("Received greeting from server :\n%s", self.greeting)
            return self.greeting
        except Exception as ex:
            self.disconnect()
            logging.error("Could not setup a secure connection. %s", str(ex))
            raise EppCommunicatorException(
                "Could not setup a secure connection"
            ) from ex

    def _execute_dry_run(self, cmd: str) -> EppResultData:
        """
        Execute command in dry-run mode without sending to server.

        :param str cmd: XML Command
        :return: Result object
        :rtype: EppResultData
        """
        raw_response = self._execute_command(cmd).decode("utf-8")
        client_transaction_id = None
        try:
            # Extract client transaction ID from the XML payload if present
            xml_cmd = BeautifulSoup(raw_response, "xml")
            cl_trid = xml_cmd.find("clTRID")
            if cl_trid:
                client_transaction_id = cl_trid.text
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logging.debug("Could not parse clTRID in dry run: %s", exc)

        # Return simulated success result with dry_run flag set to True
        return EppResultData(
            code=EppResultCode.SUCCESS.value,
            message="Dry run",
            reason=None,
            raw_response=raw_response,
            client_transaction_id=client_transaction_id,
            server_transaction_id=None,
            repository_object_id=None,
            result_data=None,
            dry_run=True,
        )

    def execute(self, cmd: str) -> EppResultData:
        """
        Execute the command. Sending the request to the server and receive the response.

        :param str cmd: XML Command

        :return: Result object
        :rtype: EppResultData

        :raises EppCommunicatorException: When there is any errors.
        """
        try:
            if not self.greeting and not self._dry_run:
                raise EppCommunicatorException(
                    "The connection to the server has not been established yet!"
                )

            # Route dry-run commands to offline execution handler
            if self._dry_run:
                return self._execute_dry_run(cmd)

            raw_response = self._execute_command(cmd)
            xml_response = BeautifulSoup(raw_response, "xml")

            response = xml_response.find("response")
            result = xml_response.find("result")
            message = result.find("msg").string

            try:
                code = int(result.get("code"))
            except AttributeError as exc:
                raise EppCommunicatorException("Could not get result code.") from exc

            reason = None
            if code not in (
                EppResultCode.SUCCESS.value,
                EppResultCode.SUCCESS_END_SESSION.value,
            ):
                reason = result.find("reason").string if result.find("reason") else None

            client_transaction_id = (
                response.find("clTRID").text if response.find("clTRID") else None
            )
            server_transaction_id = (
                response.find("svTRID").text if response.find("svTRID") else None
            )
            repository_object_id = (
                response.find("roid").text if response.find("roid") else None
            )

            logging.debug("Command executed:\n%s", mask_sensitive_xml(xml_response))

            return EppResultData(
                code=code,
                message=message,
                reason=reason,
                raw_response=raw_response,
                client_transaction_id=client_transaction_id,
                server_transaction_id=server_transaction_id,
                repository_object_id=repository_object_id,
                result_data=None,
            )
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

    def login(
        self, user: str, password: str, extensions: Optional[list[str]] = None
    ) -> EppResultData:
        """
        Login the user to EPP server.

        :param user: username
        :param password: password
        :param extensions: A list of supported extension URIs

        :return: Result object
        :rtype: EppResultData

        :raises EppCommunicatorException: When there are any errors.
        """
        if extensions is None:
            extensions = []

        self._user = user

        command_template = template_engine.from_string(LOGIN_XML)
        command = command_template.render(
            user=user, password=password, extensions=extensions
        )

        result = self.execute(command)

        if result.code == EppResultCode.SUCCESS.value:
            logging.info(
                "User %s logged in to %s:%s", self._user, self._server, self._port
            )
        elif result.code == EppResultCode.PARAMETER_RANGE_ERROR.value:
            raise EppCommunicatorException(
                "Incorrect user name or password. Please try again!"
            )
        else:
            raise EppCommunicatorException(
                f"Something went wrong! Code: {result.code} - Message: "
                f"{result.message} - Reason {result.reason}"
            )

        return result

    def disconnect(self) -> None:
        """
        Close and clean up socket connections without sending EPP commands.
        """
        if self._ssl_socket:
            try:
                self._ssl_socket.close()
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logging.debug("Error closing SSL socket: %s", exc)
            self._ssl_socket = None

        if self._socket:
            try:
                self._socket.close()
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logging.debug("Error closing socket: %s", exc)
            self._socket = None

        self.greeting = None

    def logout(self) -> EppResultData:
        """
        Logout the user from EPP server.

        :return: Result object
        :rtype: EppResultData
        """
        try:
            logout = self.execute(LOGOUT_XML)
            logging.info(
                "User %s logged out from %s:%s", self._user, self._server, self._port
            )
            return logout
        finally:
            self.disconnect()
