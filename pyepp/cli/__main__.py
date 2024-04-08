"""
Executable cli module.
"""
import os
from configparser import RawConfigParser
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

APP_NAME = 'pyepp'


def load_config():
    """
    Loads the configuration file into context settings. It reads the config file
    from the below paths depends on the host OS.

    Mac OS X (POSIX) and Unix (POSIX):
      ~/.pyepp/config.ini
    Windows (not roaming):
      C:\\Users\\<user>\\AppData\\Local\\pyepp\\config.ini
    """
    cfg = os.path.join(click.get_app_dir(APP_NAME, roaming=False, force_posix=True), 'config.ini')
    parser = RawConfigParser()
    parser.read([cfg])
    config = {}
    for section in parser.sections():
        for key, value in parser.items(section):
            config[f"{section}_{key}".upper()] = value

    CONTEXT_SETTINGS['default_map'] = {
        'server': config.get('PYEPP_SERVER'),
        'port': config.get('PYEPP_PORT'),
        'client_cert': config.get('PYEPP_CLIENT_CERT'),
        'client_key': config.get('PYEPP_CLIENT_KEY'),
        'user': config.get('PYEPP_USER'),
        'password': config.get('PYEPP_PASSWORD')
    }


load_config()


@click.group(name='pyepp', context_settings=CONTEXT_SETTINGS)
@click.option('--server', envvar="PYEPP_SERVER", required=True)
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
def pyepp_cli(ctx, server, port, client_cert, client_key, user, password, output_format, no_pretty, dry_run,
              file, verbose, debug):
    """A command line interface to work with PyEpp library."""
    ctx.obj = cli.PyEppCli(server, port, client_cert, client_key, user, password, output_format, no_pretty, dry_run)

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
