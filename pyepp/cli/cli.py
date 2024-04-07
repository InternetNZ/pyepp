"""
PyEpp command line interface module.
"""
# pylint: skip-file
import functools
import pprint

import click

from pyepp.helper import xml_pretty
from pyepp.epp import EppResultData
from pyepp import EppCommunicator


def login_logout(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.dry_run:
            self.connect()
            self.login()

        result = func(self, *args, **kwargs)

        if not self.dry_run:
            self.logout()

        return result

    return wrapper


class PyEppCli:
    def __init__(self, server, port, client_cert, client_key, user, password, output_format, no_pretty, dry_run=False):
        self.epp = EppCommunicator(server, port, client_cert, client_key, dry_run)

        self.user = user
        self.password = password

        self.output_format = output_format
        self.no_pretty = no_pretty
        self.dry_run = dry_run

        self.registry_object = None

    def connect(self):
        self.epp.connect()

    def login(self):
        self.epp.login(self.user, self.password)

    def logout(self):
        self.epp.logout()

    def format_output(self, result: EppResultData):
        output = result
        if self.output_format == 'XML':
            output = result.raw_response
            if not self.no_pretty:
                output = xml_pretty(result.raw_response)
        elif self.output_format == 'MIN':
            return result.result_data
        else:
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


pass_pyepp_cli = click.make_pass_decorator(PyEppCli)
