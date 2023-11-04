"""
Executable cli module.
"""
import logging

import click

from pyepp.cli.host import host_group
from pyepp.cli import cli
from pyepp.cli.contact import contact_group
from pyepp.cli.domain import domain_group
from pyepp.cli.poll import poll_group
from pyepp.cli import utils


logging.basicConfig(level=logging.ERROR)

CONTEXT_SETTINGS = {'help_option_names': ['-h', '--help']}


@click.group(name='pyepp', context_settings=CONTEXT_SETTINGS)
@click.option('--host', envvar="PYEPP_HOST", required=True)
@click.option('--port', envvar="PYEPP_PORT", required=True)
@click.option('--client-cert', envvar="PYEPP_CLIENT_CERT", required=True)
@click.option('--client-key', envvar="PYEPP_CLIENT_KEY", required=True)
@click.option('--user', envvar="PYEPP_USER", required=True)
@click.option('--password', envvar="PYEPP_PASSWORD", required=True)
@click.option('-o', '--output-format', show_default=True, default='XML',
              type=click.Choice(['XML', 'OBJECT', 'MIN'], case_sensitive=False))
@click.option('--no-pretty', is_flag=True, show_default=True, default=False)
@click.option('--dry-run', is_flag=True, show_default=True, default=False)
@click.option('-f', '--file', type=click.File('wb'),
              help='If provided, the output will be written in the file.', default=None)
@click.option('-v', '--verbose', is_flag=True, show_default=True, default=False)
@click.option('-d', '--debug', is_flag=True, show_default=True, default=False)
@click.version_option()
@click.pass_context
# pylint: disable=too-many-arguments
def pyepp_cli(ctx, host, port, client_cert, client_key, user, password, output_format, no_pretty, dry_run,
              file, verbose, debug):
    """A command line interface to work with PyEpp library."""
    ctx.obj = cli.PyEppCli(host, port, client_cert, client_key, user, password, output_format, no_pretty, dry_run)

    if verbose:
        logging.basicConfig(level=logging.INFO)
    if debug:
        logging.basicConfig(level=logging.DEBUG)

    utils.OUTPUT_FILE = file


@click.command('run')
@click.argument('xml', type=click.File('rb'))
@click.pass_context
def run_xml(ctx, xml):
    """Receive an XML file containing an EPP XML command and execute it.

    XML: path to an XML file
    """
    xml_command = xml.read()
    result = ctx.obj.execute(xml_command.decode('utf-8'))
    utils.echo(result)


pyepp_cli.add_command(run_xml)
pyepp_cli.add_command(contact_group)
pyepp_cli.add_command(domain_group)
pyepp_cli.add_command(host_group)
pyepp_cli.add_command(poll_group)
