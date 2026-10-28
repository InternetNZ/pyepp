"""
CLI Profile management module.
"""

from typing import Optional
import click

from pyepp.profiles import (
    load_all_profiles,
    load_profile,
    Profile,
    ProfileNotFoundError,
    get_default_config_path,
)
from pyepp.cli import utils


@click.group(name="profile")
def profile_group():
    """Manage and inspect EPP configuration profiles."""


def _format_profiles_table(profiles: dict[str, Profile]) -> str:
    """Format profiles dictionary into an aligned text table."""
    headers = ["Profile", "Server", "Port", "User", "Output Format"]
    rows = [
        [
            name,
            prof.server or "-",
            prof.port or "-",
            prof.user or "-",
            prof.output_format or "-",
        ]
        for name, prof in profiles.items()
    ]

    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            col_widths[i] = max(col_widths[i], len(val))

    header_line = "  ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    sep_line = "  ".join("-" * col_widths[i] for i in range(len(headers)))
    data_lines = [
        "  ".join(row[i].ljust(col_widths[i]) for i in range(len(row)))
        for row in rows
    ]
    return "\n".join([header_line, sep_line] + data_lines)


@profile_group.command("list")
@click.option(
    "-c",
    "--config-file",
    type=click.Path(exists=True),
    default=None,
    help="Path to configuration file.",
)
@click.pass_context
def list_profiles_cmd(ctx, config_file: Optional[str]):
    """List all configured profiles in the configuration file."""
    cfg = (
        config_file
        or getattr(ctx.obj, "config_file", None)
        or get_default_config_path()
    )
    profiles = load_all_profiles(cfg)
    utils.echo(_format_profiles_table(profiles))


@profile_group.command("show")
@click.argument("name", required=False, default=None)
@click.option(
    "-c",
    "--config-file",
    type=click.Path(exists=True),
    default=None,
    help="Path to configuration file.",
)
@click.option(
    "--show-secrets",
    is_flag=True,
    default=False,
    help="Display password unmasked.",
)
@click.pass_context
def show_profile_cmd(
    ctx, name: Optional[str], config_file: Optional[str], show_secrets: bool
):
    """Show details of a specific profile (defaults to active profile)."""
    cfg = (
        config_file
        or getattr(ctx.obj, "config_file", None)
        or get_default_config_path()
    )
    target_name = name or getattr(ctx.obj, "profile_name", None) or "default"

    try:
        prof = load_profile(target_name, config_file=cfg)
    except ProfileNotFoundError as err:
        raise click.ClickException(str(err)) from err

    pwd_display = (
        prof.password
        if show_secrets
        else ("********" if prof.password else "None")
    )
    ext_display = ", ".join(prof.extensions) if prof.extensions else "None"

    lines = [
        f"Profile: {prof.name}",
        f"  Server:        {prof.server or 'None'}",
        f"  Port:          {prof.port or 'None'}",
        f"  User:          {prof.user or 'None'}",
        f"  Password:      {pwd_display}",
        f"  Client Cert:   {prof.client_cert or 'None'}",
        f"  Client Key:    {prof.client_key or 'None'}",
        f"  Extensions:    {ext_display}",
        f"  Output Format: {prof.output_format}",
        f"  No Pretty:     {prof.no_pretty}",
        f"  Dry Run:       {prof.dry_run}",
    ]
    utils.echo("\n".join(lines))
