"""
Executable cli module.
"""
import logging

import click

from pyepp.cli import cli
from pyepp.cli.contact import contact_group

logging.basicConfig(level=logging.ERROR)


@click.group(name='pyepp')
@click.option('--host', envvar="PYEPP_HOST", required=True)
@click.option('--port', envvar="PYEPP_PORT", required=True)
@click.option('--client-cert', envvar="PYEPP_CLIENT_CERT", required=True)
@click.option('--client-key', envvar="PYEPP_CLIENT_KEY", required=True)
@click.option('--user', envvar="PYEPP_USER", required=True)
@click.option('--password', envvar="PYEPP_PASSWORD", required=True)
@click.option('-o', '--output-format', show_default=True, default='XML',
              type=click.Choice(['XML', 'OBJECT', 'MIN'], case_sensitive=False))
@click.option('--no-pretty', is_flag=True, show_default=True, default=False)
@click.option('-v', '--verbose', is_flag=True, show_default=True, default=False)
@click.option('-d', '--debug', is_flag=True, show_default=True, default=False)
@click.version_option()
@click.pass_context
# pylint: disable=too-many-arguments
def pyepp_cli(ctx, host, port, client_cert, client_key, user, password, output_format, no_pretty, verbose, debug):
    """A command line interface to work with PyEpp library."""
    ctx.obj = cli.PyEppCli(host, port, client_cert, client_key, user, password, output_format, no_pretty)

    if verbose:
        logging.basicConfig(level=logging.INFO)
    if debug:
        logging.basicConfig(level=logging.DEBUG)


pyepp_cli.add_command(contact_group)
pyepp_cli.add_command(cli.domain)
pyepp_cli.add_command(cli.host)
pyepp_cli.add_command(cli.poll)