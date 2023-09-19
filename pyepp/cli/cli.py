"""
PyEpp command line interface module.
"""
# pylint: skip-file
import functools
import pprint

import click

from pyepp.helper import xml_pretty
from pyepp.epp import EppResultData
from pyepp.host import Host
from pyepp.contact import Contact
from pyepp.domain import Domain
from pyepp import EppCommunicator


def login_logout(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        self.connect()
        self.login()
        result = func(self, *args, **kwargs)
        self.logout()

        return result

    return wrapper


class PyEppCli:
    def __init__(self, host, port, client_cert, client_key, user, password, output_format, no_pretty):
        self.epp = EppCommunicator(host, port, client_cert, client_key)

        self.user = user
        self.password = password

        self.output_format = output_format
        self.no_pretty = no_pretty

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


pass_pyepp_cli = click.make_pass_decorator(PyEppCli)





@click.group()
@click.pass_context
def domain(ctx):
    """To work with Domain objects in the registry."""
    ctx.obj.registry_object = Domain(ctx.obj.epp)


@click.group()
@click.pass_context
def host(ctx):
    """To work with Host objects in the registry."""
    ctx.obj.registry_object = Host(ctx.obj.epp)


@click.group()
@click.pass_context
def poll(ctx):
    """To request or acknowledge registry service messages."""
    pass


# @click.command(name='info')
# @click.argument('contact-id')
# @click.pass_context
# def contact_info(ctx, contact_id) -> None:
#     """Returns contact details."""
#     result = ctx.obj.info(contact_id)
#     click.echo(result)
#
#
# @click.command(name='check')
# @click.argument('contact-ids', nargs=-1)
# @click.pass_context
# def contact_check(ctx, contact_ids: tuple) -> None:
#     """"""
#     result = ctx.obj.check(list(contact_ids))
#     click.echo(result)
#
#
# @click.command(name='delete')
# @click.argument('contact-id')
# @click.pass_context
# def contact_delete(ctx, contact_id) -> None:
#     result = ctx.obj.delete(list(contact_id))
#     click.echo(result)
#
#
# @click.command()
# @click.pass_context
# def update(ctx) -> None:
#     pass
#
#
# @click.command()
# @click.pass_context
# def create(ctx) -> None:
#     pass
#
#
# @click.command()
# @click.pass_context
# def renew(ctx) -> None:
#     pass
#
#
# @click.command()
# @click.pass_context
# def transfer(ctx) -> None:
#     pass




# domain.add_command(check)
# domain.add_command(info)
# domain.add_command(delete)
# domain.add_command(update)
# domain.add_command(create)
# domain.add_command(renew)
# domain.add_command(transfer)
#
# host.add_command(check)
# host.add_command(info)
# host.add_command(delete)
# host.add_command(update)
# host.add_command(create)
