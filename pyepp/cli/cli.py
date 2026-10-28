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
    ):
        self.epp = EppCommunicator(server, port, client_cert, client_key, dry_run)

        self.user = user
        self.password = password

        self.extensions = extensions

        self.output_format = output_format.upper() if output_format else "XML"
        self.no_pretty = no_pretty
        self.dry_run = dry_run

        self.registry_object = None

    def connect(self):
        self.epp.connect()

    def disconnect(self):
        self.epp.disconnect()

    def login(self):
        self.epp.login(self.user, self.password, extensions=self.extensions)

    def logout(self):
        self.epp.logout()

    def hello(self):
        # In dry-run mode, avoid establishing a live socket connection before hello
        if not self.dry_run:
            self.connect()
        result = self.epp.hello()
        return result

    def format_output(self, result: EppResultData):
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

    @login_logout
    def request(self, *args, **kwargs):
        result = self.registry_object.request(*args, **kwargs)
        return self.format_output(result)

    @login_logout
    def acknowledge(self, *args, **kwargs):
        result = self.registry_object.acknowledge(*args, **kwargs)
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
