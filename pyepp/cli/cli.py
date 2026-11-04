"""
PyEpp command line interface module.
"""

# pylint: skip-file
import functools
import logging
import pprint

import click

from pyepp.helper import xml_pretty
from pyepp import EppCommunicator, EppResultData
from pyepp.cli.utils import format_table, format_tsv


def login_logout(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        if self.dry_run:
            return func(self, *args, **kwargs)

        # In persistent session mode (e.g. interactive shell), reuse an already
        # connected and authenticated EPP session without logging out after each command.
        if getattr(self, "persistent_session", False):
            epp_client = getattr(self, "epp", None)
            if epp_client and epp_client.is_connected and epp_client.is_logged_in:
                return func(self, *args, **kwargs)

            connected = False
            try:
                self.connect()
                connected = True
                self.login()
            except BaseException:
                if connected:
                    try:
                        self.disconnect()
                    except Exception as ex:
                        logging.debug("Disconnect failed during cleanup: %s", ex)
                raise
            return func(self, *args, **kwargs)

        connected = False
        logged_in = False
        try:
            self.connect()
            connected = True
            self.login()
            logged_in = True
            return func(self, *args, **kwargs)
        finally:
            if logged_in:
                try:
                    self.logout()
                except Exception as ex:
                    logging.debug("Logout failed during cleanup: %s", ex)
            elif connected:
                try:
                    self.disconnect()
                except Exception as ex:
                    logging.debug("Disconnect failed during cleanup: %s", ex)

    return wrapper


class PyEppCli:
    def __init__(
        self,
        server,
        port,
        client_cert,
        client_key,
        user,
        password,
        extensions,
        output_format,
        no_pretty,
        dry_run=False,
        profile_name=None,
        config_file=None,
        persistent_session=False,
        debug=False,
        verbose=False,
    ):
        self.epp = EppCommunicator(server, port, client_cert, client_key, dry_run)

        self.user = user
        self.password = password

        self.extensions = extensions

        self.output_format = output_format.upper() if output_format else "XML"
        self.no_pretty = no_pretty
        self.dry_run = dry_run
        self.profile_name = profile_name
        self.config_file = config_file
        self.persistent_session = persistent_session
        self.debug = debug
        self.verbose = verbose

        self.registry_object = None
        self.last_result = None
        self.last_latency_ms = None
        self.poll_queue_count = None
        self.session_history = []

    def connect(self):
        self.epp.connect()

    def disconnect(self):
        self.epp.disconnect()

    def login(self):
        self.epp.login(self.user, self.password, extensions=self.extensions)

    def logout(self):
        self.epp.logout()

    def hello(self):
        if self.dry_run:
            return self.epp.hello()

        # In a persistent session, reuse the open socket if already connected and
        # authenticated so that the active session is not torn down.
        if (
            getattr(self, "persistent_session", False)
            and self.epp.is_connected
            and self.epp.is_logged_in
        ):
            return self.epp.hello()

        connected = False
        try:
            self.connect()
            connected = True
            return self.epp.hello()
        finally:
            # Always disconnect temporary unauthenticated connections opened solely for hello
            if connected and not getattr(self.epp, "is_logged_in", False):
                try:
                    self.disconnect()
                except Exception as ex:
                    logging.debug("Disconnect failed during hello cleanup: %s", ex)

    def format_output(self, result: EppResultData):
        self.last_result = result
        fmt = self.output_format.upper() if self.output_format else "XML"
        if fmt == "XML":
            output = getattr(result, "raw_response", result)
            if not self.no_pretty and output:
                output = xml_pretty(output)
        elif fmt == "MIN":
            output = getattr(result, "result_data", result)
            if not self.no_pretty and output is not None:
                output = pprint.pformat(output)
        elif fmt == "TABLE":
            # TABLE format: Displays all EppResultData fields except raw_response and parsed_xml.
            # When --no-pretty is supplied, plain tab-separated (TSV) format is emitted.
            # If the response is not an EppResultData instance (e.g. raw greeting or unexpected response),
            # or if table generation encounters an unexpected error, safely fall back to XML output.
            if isinstance(result, EppResultData) and not result.dry_run:
                try:
                    if self.no_pretty:
                        output = format_tsv(result)
                    else:
                        output = format_table(result)

                    if output is None:
                        # Fallback to XML when response payload cannot be represented in tabular form
                        output = getattr(result, "raw_response", result)
                        if not self.no_pretty and output:
                            output = xml_pretty(output)
                except Exception:  # pylint: disable=broad-exception-caught
                    # Fallback to XML when table formatting encounters an unexpected failure
                    output = getattr(result, "raw_response", result)
                    if not self.no_pretty and output:
                        output = xml_pretty(output)
            else:
                # Fallback to XML when result is not an EppResultData instance
                output = getattr(result, "raw_response", result)
                if not self.no_pretty and output:
                    output = xml_pretty(output)
        else:
            output = result
            if not self.no_pretty:
                output = pprint.pformat(output)

        return output

    @login_logout
    def execute(self, *args, **kwargs):
        result = self.epp.execute(*args, **kwargs)
        # If a raw <login> command was executed via 'run', synchronize PyEppCli
        # credentials with the updated EppCommunicator session state so prompt,
        # status, and subsequent auto-reconnects reflect the authenticated user.
        if getattr(self.epp, "is_logged_in", False):
            if getattr(self.epp, "_user", None) is not None:
                self.user = self.epp._user
            if getattr(self.epp, "_password", None) is not None:
                self.password = self.epp._password
            if getattr(self.epp, "_extensions", None) is not None:
                self.extensions = (
                    tuple(self.epp._extensions) if self.epp._extensions else None
                )
        return self.format_output(result)

    @login_logout
    def check(self, *args, **kwargs):
        result = self.registry_object.check(*args, **kwargs)
        return self.format_output(result)

    @login_logout
    def info(self, *args, **kwargs):
        result = self.registry_object.info(*args, **kwargs)
        return self.format_output(result)

    @login_logout
    def delete(self, *args, **kwargs):
        result = self.registry_object.delete(*args, **kwargs)
        return self.format_output(result)

    @login_logout
    def update(self, *args, **kwargs):
        result = self.registry_object.update(*args, **kwargs)
        return self.format_output(result)

    @login_logout
    def create(self, *args, **kwargs):
        result = self.registry_object.create(*args, **kwargs)
        return self.format_output(result)

    @login_logout
    def renew(self, *args, **kwargs):
        result = self.registry_object.renew(*args, **kwargs)
        return self.format_output(result)

    @login_logout
    def transfer(self, *args, **kwargs):
        result = self.registry_object.transfer(*args, **kwargs)
        return self.format_output(result)

    def _update_poll_queue_count(self, result):
        """Update cached poll queue count from a Poll request/acknowledge result."""
        if not isinstance(result, EppResultData) or result.dry_run:
            return
        data = getattr(result, "result_data", None)
        if data is not None and hasattr(data, "message_count"):
            try:
                self.poll_queue_count = int(data.message_count)
            except (TypeError, ValueError):
                pass
        elif str(getattr(result, "code", "")) == "1300":
            # RFC 5730 code 1300: Command completed successfully; no messages
            self.poll_queue_count = 0

    @login_logout
    def request(self, *args, **kwargs):
        result = self.registry_object.request(*args, **kwargs)
        self._update_poll_queue_count(result)
        return self.format_output(result)

    @login_logout
    def acknowledge(self, *args, **kwargs):
        result = self.registry_object.acknowledge(*args, **kwargs)
        self._update_poll_queue_count(result)
        return self.format_output(result)

    @login_logout
    def restore(self, *args, **kwargs):
        result = self.registry_object.restore(*args, **kwargs)
        return self.format_output(result)

    @login_logout
    def restore_report(self, *args, **kwargs):
        result = self.registry_object.restore_report(*args, **kwargs)
        return self.format_output(result)


pass_pyepp_cli = click.make_pass_decorator(PyEppCli)
