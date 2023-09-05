"""
Executable cli module.
"""
import logging

import click

from pyepp import cli

logging.basicConfig(level=logging.CRITICAL)


@click.group(name='pyepp')
@click.option('--host', envvar="PYEPP_HOST")
@click.option('--port', envvar="PYEPP_PORT")
@click.option('--client-cert', envvar="PYEPP_CLIENT_CERT")
@click.option('--client-key', envvar="PYEPP_CLIENT_KET")
@click.option('--user', envvar="PYEPP_USER")
@click.option('--password', envvar="PYEPP_PASSWORD")
@click.option('-o', '--output-format', show_default=True, default='XML',
              type=click.Choice(['XML', 'OBJECT'], case_sensitive=False))
@click.option('--no-pretty', is_flag=True, show_default=True, default=False)
@click.option('-v', '--verbose', is_flag=True, show_default=True, default=False)
@click.option('-d', '--debug', is_flag=True, show_default=True, default=False)
@click.pass_context
# pylint: disable=too-many-arguments
def pyepp_cli(ctx, host, port, client_cert, client_key, user, password, output_format, no_pretty, verbose, debug):
    """A command line interface to work with PyEpp library."""
    ctx.obj = cli.PyEppCli(host, port, client_cert, client_key, user, password, output_format, no_pretty)

    if verbose:
        logging.basicConfig(level=logging.INFO)
    if debug:
        logging.basicConfig(level=logging.DEBUG)


pyepp_cli.add_command(cli.contact)
pyepp_cli.add_command(cli.domain)
pyepp_cli.add_command(cli.host)
pyepp_cli.add_command(cli.poll)
