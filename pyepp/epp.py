"""
EPP Communicator Module
"""

import copy
import ssl
import socket
import struct
import logging
import re
from xml.parsers import expat
from dataclasses import dataclass, asdict, field, fields, is_dataclass
from enum import Enum
from typing import Optional, Any, Union

from bs4 import BeautifulSoup

from pyepp.command_templates import (
    LOGOUT_XML,
    LOGIN_XML,
    HELLO_XML,
    get_compiled_template,
)

LENGTH_FIELD_SIZE = 4
CRLF_SIZE = 2
DEFAULT_MAX_MESSAGE_SIZE = 10 * 1024 * 1024  # 10 MiB limit to prevent DoS via memory exhaustion
SOCKET_BUFFER_CHUNK_SIZE = 16384  # 16 KiB - matching standard TLS maximum record size

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


def _convert_dataclass_value(val: Any) -> Any:
    """
    Recursively convert dataclass instances to dictionaries.

    :param val: Value to convert
    :return: Converted value without dataclass instances
    """
    if is_dataclass(val) and not isinstance(val, type):
        return asdict(val)
    if isinstance(val, tuple) and hasattr(val, "_fields"):
        return type(val)(*(_convert_dataclass_value(v) for v in val))
    if isinstance(val, (list, tuple)):
        return type(val)(_convert_dataclass_value(v) for v in val)
    if isinstance(val, dict):
        return {k: _convert_dataclass_value(v) for k, v in val.items()}
    return copy.deepcopy(val)


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
    parsed_xml: Optional[BeautifulSoup] = field(
        default=None, compare=False, repr=False
    )

    def __post_init__(self):
        if self.parsed_xml is None and self.raw_response and not self.dry_run:
            try:
                self.parsed_xml = BeautifulSoup(self.raw_response, "xml")
            except Exception as exc:  # pylint: disable=broad-exception-caught
                logging.debug("Could not parse XML in EppResultData: %s", exc)

    def __setitem__(self, key, value):
        self.__dict__[key] = value

    def __getitem__(self, key):
        return self.__dict__[key]

    def __len__(self):
        return len(self.__dict__)

    def to_dict(self) -> dict:
        """Convert an EppResultData object to a dictionary."""
        return {
            f.name: _convert_dataclass_value(getattr(self, f.name))
            for f in fields(self)
            if f.name != "parsed_xml"
        }


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
        max_message_size: int = DEFAULT_MAX_MESSAGE_SIZE,
        user: Optional[str] = None,
        password: Optional[str] = None,
        extensions: Optional[list[str]] = None,
    ) -> None:
        """
        :param server: EPP server to connect to.
        :param port: EPP port to connect to.
        :param client_cert: Path to client certificate
        :param client_key: Path to client key
        :param dry_run: dry run the request
        :param max_message_size: Maximum allowed message size in bytes (DoS protection)
        :param user: Optional EPP username for automatic login in context manager
        :param password: Optional EPP password for automatic login in context manager
        :param extensions: Optional list of extension URIs for login
        """
        self._server = server
        self._port = port
        self._user = user
        self._password = password
        self._extensions = extensions or []
        self._client_cert = client_cert
        self._client_key = client_key

        self._dry_run = dry_run
        self._max_message_size = max_message_size

        self._format_32 = get_format_32()

        self._context = None
        self._socket = None
        self._ssl_socket = None
        self.greeting = None
        self._logged_in = False
        self._last_logout_error: Optional[Exception] = None

    def __repr__(self) -> str:
        """
        Safe string representation masking sensitive credentials.

        :return: Class representation string.
        :rtype: str
        """
        return (
            f"<{self.__class__.__name__} "
            f"server={self._server!r} port={self._port!r} "
            f"user={self._user!r} logged_in={self._logged_in} "
            f"dry_run={self._dry_run}>"
        )

    def __enter__(self) -> "EppCommunicator":
        """
        Enter runtime context, establishing connection and logging in if credentials exist.

        :return: Connected (and optionally authenticated) EppCommunicator instance.
        :rtype: EppCommunicator
        :raises EppCommunicatorException: If connection or authentication fails.
        """
        self._last_logout_error = None
        try:
            if not self.is_connected:
                self.connect()

            if self._user and self._password and not self._logged_in:
                self.login(self._user, self._password, self._extensions)
        except BaseException:
            self.disconnect()
            raise

        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> bool:
        """
        Exit runtime context, cleanly logging out and closing connection.

        :param exc_type: Exception class if raised within context.
        :param exc_val: Exception instance if raised within context.
        :param exc_tb: Traceback object if raised within context.
        :return: False to allow any exception raised within the context to propagate.
        :rtype: bool
        """
        try:
            if self._logged_in:
                self.logout()
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._last_logout_error = exc
            if exc_type is None:
                logging.warning(
                    "Logout failed during context exit cleanup: %s", exc
                )
            else:
                logging.debug(
                    "Error during EppCommunicator context exit cleanup while handling exception: %s",
                    exc,
                )
        finally:
            self.disconnect()

        return False

    @property
    def last_logout_error(self) -> Optional[Exception]:
        """
        Exception encountered during the most recent context manager logout, if any.

        :return: Exception instance if logout failed during __exit__, None otherwise.
        :rtype: Optional[Exception]
        """
        return self._last_logout_error

    @property
    def user(self) -> Optional[str]:
        """User property"""
        return self._user

    @property
    def extensions(self) -> list[str]:
        """Extensions property"""
        return list(getattr(self, "_extensions", []))

    @property
    def is_logged_in(self) -> bool:
        """
        Check if the client has an active authenticated session.

        :return: True if authenticated and logged in, False otherwise.
        :rtype: bool
        """
        return self._logged_in

    @property
    def is_connected(self) -> bool:
        """
        Check if the transport connection is established.

        :return: True if connected, False otherwise.
        :rtype: bool
        """
        if self._dry_run:
            return self.greeting is not None
        return self._ssl_socket is not None

    def _unpack_data(self, data: bytes) -> int:
        """
        Unpack data.

        :param bytes data: data

        :return: unpacked data
        :rtype: int
        """
        return struct.unpack(self._format_32, data)[0]

    def _pack_data(self, data: int) -> bytes:
        """
        Pack the data.

        :param int data: data

        :return: bytes
        :rtype: bytes
        """
        return struct.pack(self._format_32, data)

    def _read_from_socket(self, size: int, use_read: bool = False) -> bytes:
        """
        Read up to size bytes from the socket.

        :param int size: Maximum number of bytes to read
        :param bool use_read: If True, prefer socket.read over socket.recv
        :return: Bytes read from socket
        :rtype: bytes
        """
        if use_read:
            if hasattr(self._ssl_socket, "read"):
                return self._ssl_socket.read(size)
            if hasattr(self._ssl_socket, "recv"):
                return self._ssl_socket.recv(size)
        else:
            if hasattr(self._ssl_socket, "recv"):
                return self._ssl_socket.recv(size)
            if hasattr(self._ssl_socket, "read"):
                return self._ssl_socket.read(size)

        raise EppCommunicatorException("Socket has neither read nor recv method.")

    def _read_exact(self, num_bytes: int, use_read: bool = False) -> Optional[bytes]:
        """
        Read exactly num_bytes from the socket.

        :param int num_bytes: Number of bytes to read
        :param bool use_read: If True, prefer socket.read over socket.recv
        :return: Bytes read from socket, or None if connection closed before any bytes received
        :rtype: Optional[bytes]
        :raises EppCommunicatorException: If connection closes prematurely or socket error occurs
        """
        if self._ssl_socket is None:
            raise EppCommunicatorException("Socket connection is not established.")

        if num_bytes < 0:
            raise EppCommunicatorException(f"Invalid byte count requested: {num_bytes}")

        if num_bytes == 0:
            return b""

        buffer = bytearray()
        while len(buffer) < num_bytes:
            remaining = num_bytes - len(buffer)
            to_read = min(remaining, SOCKET_BUFFER_CHUNK_SIZE)
            try:
                chunk = self._read_from_socket(to_read, use_read=use_read)
            except (socket.timeout, TimeoutError) as exc:
                self.disconnect()
                raise EppCommunicatorException(
                    f"Socket timed out while receiving data: {exc}"
                ) from exc
            except ssl.SSLZeroReturnError:
                chunk = b""
            except ssl.SSLError as exc:
                self.disconnect()
                raise EppCommunicatorException(
                    f"SSL error while receiving data: {exc}"
                ) from exc
            except OSError as exc:
                self.disconnect()
                raise EppCommunicatorException(
                    f"Connection error while receiving data: {exc}"
                ) from exc

            if not chunk or len(chunk) == 0:
                if len(buffer) == 0:
                    return None
                self.disconnect()
                raise EppCommunicatorException(
                    f"Connection closed prematurely after {len(buffer)}/{num_bytes} bytes"
                )

            buffer.extend(chunk)
            logging.debug("Received %s/%s bytes", len(buffer), num_bytes)

        return bytes(buffer)

    def _read(self) -> Optional[bytes]:
        """
        Read the response from the socket.

        :return: Response
        :rtype: Optional[bytes]
        :raises EppCommunicatorException: If socket connection is invalid, header is malformed,
            or message size exceeds limit
        """
        if self._ssl_socket is None:
            raise EppCommunicatorException("Socket connection is not established.")

        length_header = self._read_exact(LENGTH_FIELD_SIZE, use_read=True)
        if length_header is None:
            return None

        total_length = self._unpack_data(length_header)
        if total_length < LENGTH_FIELD_SIZE:
            raise EppCommunicatorException(
                f"Invalid EPP message length header: {total_length} bytes "
                f"(minimum is {LENGTH_FIELD_SIZE} bytes)"
            )

        max_size = getattr(self, "_max_message_size", DEFAULT_MAX_MESSAGE_SIZE)
        if total_length > max_size:
            self.disconnect()
            raise EppCommunicatorException(
                f"EPP message length {total_length} exceeds maximum allowed size "
                f"({max_size} bytes)"
            )

        total_bytes = total_length - LENGTH_FIELD_SIZE
        return self._read_exact(total_bytes, use_read=False)

    def _write(self, xml: str) -> int:
        """
        Write the request into the socket.

        :param str xml: XML Command

        :return: Number of send bytes
        :rtype: int
        :raises EppCommunicatorException: If socket is not connected or send fails
        """
        if self._ssl_socket is None:
            raise EppCommunicatorException("Socket connection is not established.")

        # +4 for the length field itself (section 4 mandates that)
        # +2 for the CRLF at the end
        xml_bytes = xml.encode("utf-8")
        length = self._pack_data(len(xml_bytes) + LENGTH_FIELD_SIZE + CRLF_SIZE)

        try:
            self._ssl_socket.sendall(length)
            xml += "\r\n"
            data_to_send = xml.encode("utf-8")
            self._ssl_socket.sendall(data_to_send)
        except (socket.timeout, TimeoutError) as exc:
            self.disconnect()
            raise EppCommunicatorException(
                f"Socket timed out while sending data: {exc}"
            ) from exc
        except ssl.SSLError as exc:
            self.disconnect()
            raise EppCommunicatorException(
                f"SSL error while sending data: {exc}"
            ) from exc
        except OSError as exc:
            self.disconnect()
            raise EppCommunicatorException(
                f"Connection error while sending data: {exc}"
            ) from exc

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
            self.disconnect()
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
        except BaseException:
            self.disconnect()
            raise

    def _execute_dry_run(self, cmd: str) -> EppResultData:
        """
        Execute command in dry-run mode without sending to server.

        :param str cmd: XML Command
        :return: Result object
        :rtype: EppResultData
        """
        raw_response = self._execute_command(cmd).decode("utf-8")
        client_transaction_id = None
        xml_cmd = None
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
            parsed_xml=xml_cmd,
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

            if code in (
                EppResultCode.COMMAND_FAILED_CLOSING_CONNECTION.value,
                EppResultCode.AUTHENTICATION_ERROR_CLOSING_CONNECTION.value,
                EppResultCode.SESSION_LIMIT_EXCEEDED_CLOSING_CONNECTION.value,
            ):
                self.disconnect()

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
                parsed_xml=xml_response,
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
        active_extensions = (
            getattr(self, "_extensions", []) if extensions is None else extensions
        )

        command_template = get_compiled_template(LOGIN_XML)
        command = command_template.render(
            user=user, password=password, extensions=active_extensions
        )

        try:
            result = self.execute(command)
        except Exception:
            self._logged_in = False
            raise

        if result.code == EppResultCode.SUCCESS.value:
            self._logged_in = True
            self._user = user
            self._password = password
            self._extensions = active_extensions
            logging.info(
                "User %s logged in to %s:%s", self._user, self._server, self._port
            )
        elif result.code == EppResultCode.PARAMETER_RANGE_ERROR.value:
            self._logged_in = False
            raise EppCommunicatorException(
                "Incorrect user name or password. Please try again!"
            )
        else:
            self._logged_in = False
            raise EppCommunicatorException(
                f"Something went wrong! Code: {result.code} - Message: "
                f"{result.message} - Reason {result.reason}"
            )

        return result

    def disconnect(self) -> None:
        """
        Close and clean up socket connections without sending EPP commands.
        """
        self._logged_in = False
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
            self._logged_in = False
            self.disconnect()
