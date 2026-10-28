"""
Executable cli module.
"""

import os
import logging

import click

from pyepp.cli.host import host_group
from pyepp.cli import cli
from pyepp.cli.contact import contact_group
from pyepp.cli.domain import domain_group
from pyepp.cli.poll import poll_group
from pyepp.cli.profile import profile_group
from pyepp.cli import utils

logging.basicConfig(level=logging.ERROR)

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}

APP_NAME = "pyepp"

VALID_OUTPUT_FORMATS = ("XML", "OBJECT", "MIN", "TABLE")


def load_config(config_file=None, profile=None):
    """
    Loads configuration settings from config.ini into context settings.
    Supports AWS CLI style profiles: inherits from [default] (or legacy [pyepp]).

    :param config_file: Optional explicit path to configuration file (e.g. for testing).
    :param profile: Optional profile name to load.
    """
    from pyepp.profiles import (  # pylint: disable=import-outside-toplevel
        load_profile,
        get_default_config_path,
    )

    cfg = config_file or get_default_config_path()
    prof_name = profile or os.environ.get("PYEPP_PROFILE", "default")
    try:
        prof = load_profile(prof_name, config_file=cfg)
    except Exception:  # pylint: disable=broad-exception-caught
        prof = None

    if prof:
        # Sanitize output_format before placing into default_map. Click validates
        # default_map choices prior to command execution; an invalid choice here
        # would block commands like 'pyepp -c valid.ini' or 'pyepp profile list'.
        raw_fmt = getattr(prof, "output_format", None)
        fmt = str(raw_fmt).upper() if raw_fmt else "XML"
        if fmt not in VALID_OUTPUT_FORMATS:
            fmt = "XML"

        CONTEXT_SETTINGS["default_map"] = {
            "server": prof.server,
            "port": prof.port,
            "client_cert": prof.client_cert,
            "client_key": prof.client_key,
            "user": prof.user,
            "password": prof.password,
            "output_format": fmt,
            "no_pretty": prof.no_pretty,
            "dry_run": prof.dry_run,
        }
        if prof.extensions:
            CONTEXT_SETTINGS["default_map"]["extension"] = tuple(prof.extensions)
    else:
        CONTEXT_SETTINGS["default_map"] = {
            "output_format": "XML",
        }


load_config()


def _validate_profile_output_format(ctx, raw_fmt):
    """Validate profile output_format against allowed choices, raising BadParameter if invalid."""
    if raw_fmt is None:
        return "XML"
    fmt_upper = str(raw_fmt).upper()
    if fmt_upper not in VALID_OUTPUT_FORMATS:
        if ctx.invoked_subcommand != "profile":
            allowed = ", ".join(f"'{f.lower()}'" for f in VALID_OUTPUT_FORMATS)
            raise click.BadParameter(
                f"'{raw_fmt}' is not one of {allowed}.",
                ctx=ctx,
                param_hint="'-o' / '--output-format'",
            )
        return raw_fmt
    return fmt_upper


def _resolve_profile_options(ctx, active_profile, config_file, current_values):
    """Resolve configuration profile options and override default/unspecified parameters."""
    from pyepp.profiles import load_profile  # pylint: disable=import-outside-toplevel

    try:
        prof = load_profile(active_profile or "default", config_file=config_file)
    except Exception as ex:  # pylint: disable=broad-exception-caught
        if ctx.invoked_subcommand != "profile":
            raise click.ClickException(str(ex)) from ex
        return current_values

    updated = dict(current_values)

    # Profile settings must only override options whose parameter source is
    # DEFAULT, DEFAULT_MAP, or None. Explicit values from CLI flags (COMMANDLINE)
    # and environment variables (ENVIRONMENT) take precedence over profile values.
    # This prevents profiles from clobbering environment variables or wiping
    # credentials supplied via the environment when not specified in the profile.
    overridable_sources = (
        click.core.ParameterSource.DEFAULT,
        click.core.ParameterSource.DEFAULT_MAP,
        None,
    )

    for field_name in (
        "server",
        "port",
        "user",
        "password",
        "client_cert",
        "client_key",
    ):
        if ctx.get_parameter_source(field_name) in overridable_sources:
            val = getattr(prof, field_name, None)
            if val is not None or config_file is not None or active_profile is not None:
                updated[field_name] = val

    # Validate output_format from the loaded profile against allowed choices.
    # Click Choice validation occurs prior to pyepp_cli execution, so dynamically
    # resolved profile options must be explicitly validated here.
    if ctx.get_parameter_source("output_format") in overridable_sources:
        updated["output_format"] = _validate_profile_output_format(
            ctx, getattr(prof, "output_format", None)
        )

    if ctx.get_parameter_source("extension") in overridable_sources:
        updated["extension"] = (
            tuple(prof.extensions) if prof.extensions else None
        )

    if ctx.get_parameter_source("dry_run") in overridable_sources:
        if prof.dry_run:
            updated["dry_run"] = True

    if ctx.get_parameter_source("no_pretty") in overridable_sources:
        if prof.no_pretty:
            updated["no_pretty"] = True

    return updated


@click.group(name="pyepp", context_settings=CONTEXT_SETTINGS)
@click.option(
    "-p",
    "--profile",
    "profile",
    envvar="PYEPP_PROFILE",
    required=False,
    help="Configuration profile name from config.ini (e.g. ote, prod).",
)
@click.option(
    "-c",
    "--config-file",
    "config_file",
    type=click.Path(),
    envvar="PYEPP_CONFIG_FILE",
    required=False,
    help="Explicit path to config.ini file.",
)
@click.option("--server", envvar="PYEPP_SERVER", required=False)
@click.option("--port", envvar="PYEPP_PORT", required=False)
@click.option("--user", envvar="PYEPP_USER", required=False)
@click.option("--password", envvar="PYEPP_PASSWORD", required=False)
@click.option("--client-cert", envvar="PYEPP_CLIENT_CERT", required=False)
@click.option("--client-key", envvar="PYEPP_CLIENT_KEY", required=False)
@click.option(
    "--extension",
    envvar="PYEPP_EXTENSION",
    required=False,
    help="The extension to be loaded for the EPP command.",
    multiple=True,
)
@click.option(
    "-o",
    "--output-format",
    "output_format",
    envvar="PYEPP_OUTPUT_FORMAT",
    show_default=True,
    default="XML",
    type=click.Choice(list(VALID_OUTPUT_FORMATS), case_sensitive=False),
)
@click.option("--no-pretty", is_flag=True, show_default=True, default=False)
@click.option("--dry-run", is_flag=True, show_default=True, default=False)
@click.option(
    "-f",
    "--file",
    type=click.File("wb"),
    help="If provided, the output will be written in the file.",
    default=None,
)
@click.option("-v", "--verbose", is_flag=True, show_default=True, default=False)
@click.option("-d", "--debug", is_flag=True, show_default=True, default=False)
@click.version_option()
@click.pass_context
# pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
def pyepp_cli(
    ctx,
    profile,
    config_file,
    server,
    port,
    client_cert,
    client_key,
    user,
    password,
    extension,
    output_format,
    no_pretty,
    dry_run,
    file,
    verbose,
    debug,
):
    """A command line interface to work with PyEpp library."""
    active_profile = profile or os.environ.get("PYEPP_PROFILE")
    if active_profile or config_file:
        resolved = _resolve_profile_options(
            ctx,
            active_profile,
            config_file,
            {
                "server": server,
                "port": port,
                "user": user,
                "password": password,
                "client_cert": client_cert,
                "client_key": client_key,
                "extension": extension,
                "output_format": output_format,
                "dry_run": dry_run,
                "no_pretty": no_pretty,
            },
        )
        server = resolved["server"]
        port = resolved["port"]
        user = resolved["user"]
        password = resolved["password"]
        client_cert = resolved["client_cert"]
        client_key = resolved["client_key"]
        extension = resolved["extension"]
        output_format = resolved["output_format"]
        dry_run = resolved["dry_run"]
        no_pretty = resolved["no_pretty"]

    if ctx.invoked_subcommand != "profile":
        missing = []
        if not server:
            missing.append("--server")
        if not port:
            missing.append("--port")
        if not user:
            missing.append("--user")
        if not password:
            missing.append("--password")
        if missing:
            raise click.UsageError(
                f"Missing required parameter(s): {', '.join(missing)}. "
                f"Provide via CLI flags, environment variables, or a profile in config.ini."
            )

    ctx.obj = cli.PyEppCli(
        server,
        port,
        client_cert,
        client_key,
        user,
        password,
        extension,
        output_format,
        no_pretty,
        dry_run,
        profile_name=active_profile,
        config_file=config_file,
    )

    if verbose:
        logging.getLogger().setLevel(level=logging.INFO)
    if debug:
        logging.getLogger().setLevel(level=logging.DEBUG)

    utils.OUTPUT_FILE = file


@click.command("run")
@click.argument("xml", type=click.File("rb"))
@click.pass_context
def run_xml(ctx, xml):
    """Receive an XML file containing an EPP XML command and execute it.

    XML: path to an XML file
    """
    xml_command = xml.read()
    result = ctx.obj.execute(xml_command.decode("utf-8"))
    utils.echo(result)


@click.command("hello")
@click.pass_context
def hello(ctx):
    """Sends a hello command to the server and receives the Greeting response."""
    greeting = ctx.obj.hello()
    utils.echo(greeting)


pyepp_cli.add_command(run_xml)
pyepp_cli.add_command(contact_group)
pyepp_cli.add_command(domain_group)
pyepp_cli.add_command(host_group)
pyepp_cli.add_command(poll_group)
pyepp_cli.add_command(hello)
pyepp_cli.add_command(profile_group)
