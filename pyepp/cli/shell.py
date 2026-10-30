"""
Interactive CLI Shell / REPL session module for PyEPP.

Provides a persistent EPP session (`pyepp shell`) with ASCII startup banner,
readline tab auto-completion, command history, and mid-session profile switching.
"""

import logging
import os
import re
import shlex
import shutil
import sys
import time
from typing import Optional

import click

from pyepp import __version__, EppCommunicator, EppCommunicatorException
from pyepp.cli import utils
from pyepp.cli.contact import contact_group
from pyepp.cli.domain import domain_group
from pyepp.cli.host import host_group
from pyepp.cli.poll import poll_group
from pyepp.cli.profile import profile_group
from pyepp.profiles import list_profiles, load_profile, ProfileNotFoundError

try:
    import readline as _readline
except ImportError:  # pragma: no cover
    _readline = None

ASCII_BANNER = r"""
  ____        _____ ____  ____
 |  _ \ _   _| ____|  _ \|  _ \
 | |_) | | | |  _| | |_) | |_) |
 |  __/| |_| | |___|  __/|  __/
 |_|    \__, |_____|_|   |_|
        |___/
"""

VALID_OUTPUT_FORMATS = ("XML", "OBJECT", "MIN", "TABLE")
SHELL_BUILTIN_COMMANDS = (
    "use", "set", "status", "reconnect", "clear", "history", "last", "save", "help", "exit", "quit"
)
SHELL_ALIASES = {"?": "help", "q": "exit", "st": "status", "hist": "history"}
MAX_HISTORY_ENTRIES = 500
SET_KEYS = ("output-format", "pretty", "dry-run")

# Regex matching ANSI SGR escape sequences so readline prompt ignore markers (\x01/\x02) wrap color codes.
_ANSI_ESCAPE_RE = re.compile(r"(\x1b\[[0-9;]*m)")
# Regex matching ASCII/C1 control characters to prevent terminal escape injection (CWE-150).
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")
# Regex matching sensitive CLI flags (--password, --pass prefix, --show-secrets) to scrub from history.
_SENSITIVE_LINE_RE = re.compile(r"(?:^|\s)(?:--pass(?:word)?|--show-secrets)(?:\s|=|$)", re.IGNORECASE)

HELP_TEXT = """
Available Commands:
  domain      Manage domain objects (check, info, create, delete, renew, transfer, update, restore, restore-report)
  contact     Manage contact objects (check, info, create, delete, update)
  host        Manage host objects (check, info, create, delete, update)
  poll        Manage service message queue (request, acknowledge)
  profile     Inspect or switch configuration profiles (list, show, use <name>)
  hello       Send a hello command and display server greeting
  run         Execute a raw XML command file (run <file.xml>)

Session & Shell Commands:
  use <profile>                    Switch to another configuration profile mid-session
  set output-format <FORMAT>       Set output format (XML, OBJECT, MIN, TABLE)
  set pretty <on|off>              Enable or disable pretty-printed output
  set dry-run <on|off>             Enable or disable dry-run mode
  last [FORMAT]                    Re-display the last command response in XML, TABLE, MIN, or OBJECT
  save <file> [FORMAT]             Save the last command response to a file
  history [count] / hist           Show command history (use !! or !<N> to re-run a command)
  status / st                      Display current session and connection status
  reconnect                        Reconnect and re-authenticate the active session
  clear                            Clear the terminal screen (keeps command history)
  help [command] / ?               Show this help or command-specific help (e.g. 'help domain check')
  exit / quit / q                  Log out and exit the interactive shell
""".strip()


def _rl_style(text: str, **kwargs) -> str:
    """Style text with Click ANSI colors and wrap escape sequences in readline ignore markers."""
    styled = click.style(text, **kwargs)
    return _ANSI_ESCAPE_RE.sub("\x01\\1\x02", styled)


def _format_help_text() -> str:
    """Return colorized help text for the interactive shell."""
    lines = []
    for line in HELP_TEXT.splitlines():
        if line.endswith(":") and not line.startswith(" "):
            lines.append(click.style(line, fg="yellow", bold=True))
        elif line.startswith("  ") and len(line) > 2:
            stripped = line.lstrip(" ")
            parts = stripped.split("  ", 1)
            if len(parts) == 2:
                cmd_part, desc_part = parts[0], parts[1]
                padding = " " * (len(line) - len(stripped))
                lines.append(f"{padding}{click.style(cmd_part, fg='cyan', bold=True)}  {desc_part}")
            else:
                lines.append(line)
        else:
            lines.append(line)
    return "\n".join(lines)


def _get_command_groups() -> dict[str, click.Command]:
    """Return mapping of Click commands supported inside the interactive shell."""
    from pyepp.cli.__main__ import hello, run_xml  # pylint: disable=import-outside-toplevel

    return {
        "domain": domain_group,
        "contact": contact_group,
        "host": host_group,
        "poll": poll_group,
        "profile": profile_group,
        "hello": hello,
        "run": run_xml,
    }


def _safe_close_session(cli_obj) -> None:
    """Safely log out and disconnect an active session without raising exceptions."""
    epp = getattr(cli_obj, "epp", None)
    if epp is None:
        return
    try:
        if getattr(epp, "is_logged_in", False) and not getattr(cli_obj, "dry_run", False):
            cli_obj.logout()
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logging.debug("Logout failed during shell session cleanup: %s", exc)
    finally:
        try:
            cli_obj.disconnect()
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logging.debug("Disconnect failed during shell session cleanup: %s", exc)


def _connect_and_login(cli_obj) -> bool:
    """
    Establish connection and authenticate the CLI session if not in dry-run mode.

    Follows the Poisoned Transport and Resource Manager guidelines: if login or
    connection fails, disconnect() is invoked immediately so dead descriptors are
    never retained.
    """
    cli_obj.persistent_session = True
    if cli_obj.dry_run:
        msg = f"Dry-run mode active (profile: {cli_obj.profile_name or 'default'})."
        utils.echo(click.style(msg, fg="yellow"))
        return True

    if not getattr(cli_obj.epp, "_server", None) or not cli_obj.user or not cli_obj.password:
        # Ensure _logged_in and _ssl_socket are reset so disconnected sessions never
        # report is_logged_in=True (e.g. after transitioning out of dry-run mode).
        _safe_close_session(cli_obj)
        msg = "No complete credentials configured. Use 'use <profile>' to connect to a profile."
        utils.echo(click.style(msg, fg="yellow"), err=True)
        return False

    connected = False
    try:
        cli_obj.connect()
        connected = True
        cli_obj.login()
        server = getattr(cli_obj.epp, "_server", "unknown")
        port = getattr(cli_obj.epp, "_port", "700")
        msg = f"Connected and logged in as {cli_obj.user}@{server}:{port}"
        utils.echo(click.style(msg, fg="green"))
        return True
    except BaseException as exc:
        if connected:
            try:
                cli_obj.disconnect()
            except Exception as disc_exc:  # pylint: disable=broad-exception-caught
                logging.debug("Disconnect failed after login error: %s", disc_exc)
        if isinstance(exc, Exception):
            utils.echo(click.style(f"Error connecting to EPP server: {exc}", fg="red"), err=True)
            return False
        raise


def switch_profile(cli_obj, profile_name: str) -> bool:
    """
    Switch the active session to a new configuration profile mid-session.

    Validates the target profile before tearing down the existing connection so
    a typo or invalid profile name does not disrupt the current active session.
    """
    try:
        prof = load_profile(profile_name, config_file=cli_obj.config_file)
    except ProfileNotFoundError as exc:
        utils.echo(click.style(f"Error: {exc}", fg="red"), err=True)
        return False
    except Exception as exc:  # pylint: disable=broad-exception-caught
        utils.echo(click.style(f"Error loading profile '{profile_name}': {exc}", fg="red"), err=True)
        return False

    missing = [k for k in ("server", "port", "user", "password") if not getattr(prof, k, None)]
    if missing and not prof.dry_run:
        msg = f"Error: Profile '{prof.name}' is missing required setting(s): {', '.join(missing)}."
        utils.echo(click.style(msg, fg="red"), err=True)
        return False

    fmt = (prof.output_format or "XML").upper()
    if fmt not in VALID_OUTPUT_FORMATS:
        fmt = "XML"

    # Tear down existing session cleanly before applying new profile credentials
    _safe_close_session(cli_obj)

    cli_obj.epp = EppCommunicator(
        prof.server, prof.port, prof.client_cert, prof.client_key, prof.dry_run
    )
    cli_obj.user = prof.user
    cli_obj.password = prof.password
    cli_obj.extensions = tuple(prof.extensions) if prof.extensions else None
    cli_obj.output_format = fmt
    cli_obj.no_pretty = bool(prof.no_pretty)
    cli_obj.dry_run = bool(prof.dry_run)
    cli_obj.profile_name = prof.name
    cli_obj.registry_object = None
    cli_obj.last_result = None
    cli_obj.last_latency_ms = None
    cli_obj.poll_queue_count = None
    cli_obj.persistent_session = True

    utils.echo(click.style(f"Switched to profile '{prof.name}'.", fg="cyan"))
    return _connect_and_login(cli_obj)


def _sanitize_display(value: Optional[str], fallback: str = "") -> str:
    """Strip ASCII/C1 control characters from display values to prevent escape injection."""
    if not value:
        return fallback
    cleaned = _CONTROL_CHARS_RE.sub("", str(value))
    return cleaned or fallback


def _supports_ansi_tty() -> bool:
    """Return True if stdout is an interactive terminal supporting ANSI cursor movement."""
    is_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    term = os.environ.get("TERM", "").lower()
    return bool(is_tty and term != "dumb")


def _use_color() -> bool:
    """Return True if ANSI colors should be emitted (respects NO_COLOR and TERM=dumb)."""
    return _supports_ansi_tty() and not bool(os.environ.get("NO_COLOR"))


def _truncate_ansi(text: str, max_width: int) -> str:
    """
    Truncate a string (which may contain ANSI SGR sequences) to at most `max_width`
    visible characters so it never wraps onto a second physical terminal row.
    """
    if max_width <= 0:
        return ""
    plain = click.unstyle(text)
    if len(plain) <= max_width:
        return text
    if max_width == 1:
        return "…"

    limit = max_width - 1
    visible_count = 0
    has_ansi = False
    out: list[str] = []
    for idx, part in enumerate(_ANSI_ESCAPE_RE.split(text)):
        if idx % 2 == 1:
            has_ansi = True
            out.append(part)
        elif part:
            remaining = limit - visible_count
            if remaining <= 0:
                break
            chunk = part[:remaining]
            out.append(chunk)
            visible_count += len(chunk)
    out.append("…")
    if has_ansi:
        out.append("\x1b[0m")
    return "".join(out)


def format_prompt(cli_obj, color: bool = False) -> str:
    """
    Build concise input prompt (`pyepp> `).

    Session details (profile, username, server, connection state, and output settings)
    are displayed in the bottom status bar via `format_status_bar`.
    """
    if not color:
        return "pyepp> "

    if cli_obj.dry_run:
        prompt_color = "yellow"
    elif getattr(cli_obj.epp, "is_logged_in", False):
        prompt_color = "green"
    else:
        prompt_color = "cyan"

    return _rl_style("pyepp", fg=prompt_color, bold=True) + _rl_style("> ", fg="bright_white", bold=True)


def _append_telemetry_segments(cli_obj, segments: list[str], color: bool) -> None:
    """Append optional poll queue badge and last command latency to status bar segments."""
    poll_count = getattr(cli_obj, "poll_queue_count", None)
    if isinstance(poll_count, int) and poll_count > 0:
        badge = f"✉ poll: {poll_count}"
        segments.append(click.style(badge, fg="yellow", bold=True) if color else badge)

    latency_ms = getattr(cli_obj, "last_latency_ms", None)
    if latency_ms is not None:
        if color:
            segments.append(
                click.style("last: ", fg="bright_black") + click.style(f"{latency_ms}ms", fg="cyan")
            )
        else:
            segments.append(f"last: {latency_ms}ms")


def format_status_bar(cli_obj, color: bool = False, max_width: Optional[int] = None) -> str:
    """Build the bottom status bar displaying session state, telemetry, and formatting options."""
    prof_label = _sanitize_display(cli_obj.profile_name, "default")
    server = _sanitize_display(getattr(cli_obj.epp, "_server", None), "unconnected")
    port = _sanitize_display(getattr(cli_obj.epp, "_port", None))
    target = f"{server}:{port}" if server != "unconnected" and port else server
    user = _sanitize_display(cli_obj.user, "anonymous")
    fmt = _sanitize_display(cli_obj.output_format, "XML")
    pretty_state = "off" if cli_obj.no_pretty else "on"

    if cli_obj.dry_run:
        state_text, state_color = "● dry-run", "yellow"
    elif getattr(cli_obj.epp, "is_logged_in", False):
        state_text, state_color = "● connected", "green"
    else:
        state_text, state_color = "○ disconnected", "red"

    if not color:
        segments = [
            state_text, f"profile: {prof_label}", f"{user}@{target}",
            f"format: {fmt}", f"pretty: {pretty_state}",
        ]
        _append_telemetry_segments(cli_obj, segments, color=False)
        status_bar = f" {' | '.join(segments)}"
        return _truncate_ansi(status_bar, max_width) if max_width is not None else status_bar

    segments = [
        click.style(state_text, fg=state_color, bold=True),
        click.style("profile: ", fg="bright_black") + click.style(prof_label, fg="cyan", bold=True),
        click.style(user, fg="bright_white", bold=True)
        + click.style("@", fg="bright_black") + click.style(target, fg="white"),
        click.style("format: ", fg="bright_black") + click.style(fmt, fg="magenta", bold=True),
        click.style("pretty: ", fg="bright_black")
        + click.style(pretty_state, fg="green" if pretty_state == "on" else "bright_black"),
    ]
    _append_telemetry_segments(cli_obj, segments, color=True)
    status_bar = f" {click.style(' │ ', fg='bright_black').join(segments)}"
    return _truncate_ansi(status_bar, max_width) if max_width is not None else status_bar


def format_divider_line(width: int, color: bool = False) -> str:
    """Build a horizontal divider line across the terminal width."""
    rule = "─" * max(1, width)
    return click.style(rule, fg="bright_black") if color else rule


def _read_line_with_status_bar(cli_obj) -> str:
    """Render divider lines around the prompt and status bar below it, then read a command line."""
    if not _supports_ansi_tty():
        return input(format_prompt(cli_obj, color=False))

    color = _use_color()
    width = max(1, shutil.get_terminal_size((80, 24)).columns - 1)
    divider = format_divider_line(width, color=color)
    # Truncate status bar to (columns - 1) so it never wraps onto a second row
    # and corrupts the \r\033[2A vertical cursor return.
    status_line = format_status_bar(cli_obj, color=color, max_width=width)
    # Row 1: top divider (between previous result section and prompt)
    # Row 2: prompt row (cursor returned here via \033[2A)
    # Row 3: bottom divider (between prompt and status bar / upcoming result)
    # Row 4: status bar
    sys.stdout.write(f"\r\033[2K{divider}\n\033[2K\n\033[2K{divider}\n\033[2K{status_line}\r\033[2A")
    sys.stdout.flush()

    try:
        line = input(format_prompt(cli_obj, color=color))
    except BaseException:
        # Cursor is on Row 2 (prompt); clear Row 3 (divider) and Row 4 (status bar) below it.
        sys.stdout.write("\n\r\033[2K\n\r\033[2K\033[A")
        sys.stdout.flush()
        raise

    # Pressing Enter moved the cursor onto Row 3 (bottom divider).
    # For executable commands, keep Row 3 as the divider between prompt and result and clear Row 4.
    # For empty or comment lines, clear both Row 3 and Row 4 to avoid stacking duplicate dividers.
    stripped = line.strip()
    has_output = bool(stripped and not stripped.startswith("#"))
    sys.stdout.write("\n\r\033[2K" if has_output else "\r\033[2K\n\r\033[2K\033[A")
    sys.stdout.flush()
    return line


def _style_bool(value: bool, true_color: str = "green", false_color: str = "red") -> str:
    """Format a boolean value with color."""
    return click.style(str(value), fg=true_color if value else false_color, bold=True)


def _print_status(cli_obj) -> None:
    """Display current session and connection parameters with color formatting."""
    endpoint = (
        f"{_sanitize_display(getattr(cli_obj.epp, '_server', None), 'None')}:"
        f"{_sanitize_display(getattr(cli_obj.epp, '_port', None), 'None')}"
    )
    connected = _style_bool(getattr(cli_obj.epp, "is_connected", False))
    logged_in = _style_bool(getattr(cli_obj.epp, "is_logged_in", False))
    exts = ", ".join(_sanitize_display(e) for e in cli_obj.extensions) if cli_obj.extensions else "None"
    prof_str = click.style(_sanitize_display(cli_obj.profile_name, "default"), fg="bright_white", bold=True)
    fmt_label = click.style(_sanitize_display(cli_obj.output_format, "XML"), fg="magenta", bold=True)
    pretty_str = _style_bool(not cli_obj.no_pretty, false_color="yellow")
    dry_run_str = _style_bool(cli_obj.dry_run, true_color="yellow", false_color="green")
    lines = [
        f"{click.style('Profile:', fg='cyan', bold=True)}       {prof_str}",
        f"{click.style('Server:', fg='cyan', bold=True)}        {endpoint}",
        f"{click.style('User:', fg='cyan', bold=True)}          {_sanitize_display(cli_obj.user, 'None')}",
        f"{click.style('Connected:', fg='cyan', bold=True)}     {connected}",
        f"{click.style('Logged In:', fg='cyan', bold=True)}     {logged_in}",
        f"{click.style('Extensions:', fg='cyan', bold=True)}    {exts}",
        f"{click.style('Output Format:', fg='cyan', bold=True)} {fmt_label}",
        f"{click.style('Pretty Print:', fg='cyan', bold=True)}  {pretty_str}",
        f"{click.style('Dry Run:', fg='cyan', bold=True)}       {dry_run_str}",
    ]
    poll_count = getattr(cli_obj, "poll_queue_count", None)
    if isinstance(poll_count, int):
        p_val = click.style(str(poll_count), fg="yellow" if poll_count > 0 else "green", bold=True)
        lines.append(f"{click.style('Poll Queue:', fg='cyan', bold=True)}    {p_val}")
    latency_ms = getattr(cli_obj, "last_latency_ms", None)
    if latency_ms is not None:
        lines.append(f"{click.style('Last Latency:', fg='cyan', bold=True)}  {latency_ms}ms")
    utils.echo("\n".join(lines))


def _handle_set_command(cli_obj, args: list[str]) -> None:
    """Handle 'set <key> <value>' shell command to modify session settings on the fly."""
    if len(args) != 2:
        utils.echo(
            click.style("Usage: set <output-format|pretty|dry-run> <value>", fg="yellow"),
            err=True,
        )
        return

    key, val = args[0].lower(), args[1].strip()
    if key in ("output-format", "output_format", "format"):
        fmt = val.upper()
        if fmt not in VALID_OUTPUT_FORMATS:
            allowed = ", ".join(VALID_OUTPUT_FORMATS)
            msg = f"Invalid output format '{val}'. Choose from: {allowed}"
            utils.echo(click.style(msg, fg="red"), err=True)
            return
        cli_obj.output_format = fmt
        utils.echo(click.style(f"Output format set to {fmt}.", fg="green"))
    elif key == "pretty":
        if val.lower() in ("on", "true", "1", "yes"):
            cli_obj.no_pretty = False
            utils.echo(click.style("Pretty output enabled.", fg="green"))
        elif val.lower() in ("off", "false", "0", "no"):
            cli_obj.no_pretty = True
            utils.echo(click.style("Pretty output disabled.", fg="yellow"))
        else:
            utils.echo(click.style("Usage: set pretty <on|off>", fg="yellow"), err=True)
    elif key in ("dry-run", "dry_run"):
        if val.lower() in ("on", "true", "1", "yes"):
            _safe_close_session(cli_obj)
            cli_obj.dry_run = True
            cli_obj.epp._dry_run = True  # pylint: disable=protected-access
            utils.echo(click.style("Dry-run mode enabled.", fg="yellow"))
        elif val.lower() in ("off", "false", "0", "no"):
            _safe_close_session(cli_obj)
            cli_obj.dry_run = False
            cli_obj.epp._dry_run = False  # pylint: disable=protected-access
            utils.echo(click.style("Dry-run mode disabled.", fg="green"))
            _connect_and_login(cli_obj)
        else:
            utils.echo(click.style("Usage: set dry-run <on|off>", fg="yellow"), err=True)
    else:
        msg = f"Unknown setting '{key}'. Available settings: {', '.join(SET_KEYS)}"
        utils.echo(click.style(msg, fg="red"), err=True)


def _format_last_result(cli_obj, fmt_override: Optional[str] = None) -> Optional[str]:
    """
    Format the most recent `EppResultData` stored on `cli_obj.last_result` using either
    the current session output format or an explicit format override.
    """
    last_res = getattr(cli_obj, "last_result", None)
    if last_res is None:
        msg = "No command result recorded in this session yet."
        utils.echo(click.style(msg, fg="yellow"), err=True)
        return None

    target_fmt = (fmt_override or cli_obj.output_format or "XML").upper()
    if target_fmt not in VALID_OUTPUT_FORMATS:
        allowed = ", ".join(VALID_OUTPUT_FORMATS)
        msg = f"Invalid output format '{fmt_override}'. Choose from: {allowed}"
        utils.echo(click.style(msg, fg="red"), err=True)
        return None

    orig_fmt = cli_obj.output_format
    try:
        cli_obj.output_format = target_fmt
        rendered = cli_obj.format_output(last_res)
        return "" if rendered is None else str(rendered)
    finally:
        cli_obj.output_format = orig_fmt


def _handle_last_command(cli_obj, args: list[str]) -> None:
    """Handle 'last [XML|OBJECT|MIN|TABLE]' to re-display the last command response."""
    if len(args) > 1:
        utils.echo(click.style("Usage: last [XML|OBJECT|MIN|TABLE]", fg="yellow"), err=True)
        return
    rendered = _format_last_result(cli_obj, args[0] if args else None)
    if rendered is not None:
        utils.echo(rendered)


def _handle_save_command(cli_obj, args: list[str]) -> None:
    """Handle 'save <filepath> [XML|OBJECT|MIN|TABLE]' to write the last response to disk."""
    if len(args) not in (1, 2):
        msg = "Usage: save <filepath> [XML|OBJECT|MIN|TABLE]"
        utils.echo(click.style(msg, fg="yellow"), err=True)
        return
    rendered = _format_last_result(cli_obj, args[1] if len(args) == 2 else None)
    if rendered is None:
        return

    filepath = os.path.expanduser(args[0])
    plain_text = click.unstyle(rendered)
    try:
        with open(filepath, "w", encoding="utf-8") as file_obj:
            file_obj.write(plain_text if plain_text.endswith("\n") else f"{plain_text}\n")
        utils.echo(click.style(f"Saved last response to {filepath}.", fg="green"))
    except OSError as exc:
        utils.echo(click.style(f"Error saving to '{filepath}': {exc}", fg="red"), err=True)


def _handle_history_command(cli_obj, args: list[str]) -> None:
    """Handle 'history [count]' to display numbered session command history."""
    if len(args) > 1:
        utils.echo(click.style("Usage: history [count]", fg="yellow"), err=True)
        return

    history_list: list[str] = getattr(cli_obj, "session_history", None) or []
    count = len(history_list)
    if args:
        try:
            count = int(args[0])
            if count <= 0:
                raise ValueError
        except ValueError:
            utils.echo(click.style("Usage: history [positive_count]", fg="yellow"), err=True)
            return

    if not history_list:
        utils.echo(click.style("No commands in history.", fg="bright_black"))
        return

    start_idx = max(0, len(history_list) - count)
    out_lines = [
        f"  {click.style(f'{idx + 1:4d}', fg='cyan')}  {_sanitize_display(history_list[idx])}"
        for idx in range(start_idx, len(history_list))
    ]
    utils.echo("\n".join(out_lines))


def _dispatch_click_command(cli_obj, tokens: list[str]) -> None:
    """Invoke a registered Click command or group within the persistent shell session."""
    cmd_groups = _get_command_groups()
    cmd_name = tokens[0].lower()
    sub_args = tokens[1:]

    # Intercept 'profile use <name>' so it mutates the active shell session
    if cmd_name == "profile" and sub_args and sub_args[0].lower() == "use":
        if len(sub_args) != 2:
            utils.echo(click.style("Usage: profile use <profile_name>", fg="yellow"), err=True)
            return
        switch_profile(cli_obj, sub_args[1])
        return

    cmd_obj = cmd_groups.get(cmd_name)
    if cmd_obj is None:
        msg = f"Unknown command '{tokens[0]}'. Type 'help' for available commands."
        utils.echo(click.style(msg, fg="red"), err=True)
        return

    record_latency = "--help" not in sub_args and "-h" not in sub_args
    start_t = time.perf_counter()
    try:
        cmd_obj.main(args=sub_args, prog_name=cmd_name, obj=cli_obj, standalone_mode=False)
    except click.ClickException as exc:
        record_latency = False
        exc.show()
    except click.Abort:
        record_latency = False
        utils.echo(click.style("Aborted!", fg="yellow"), err=True)
    except EppCommunicatorException as exc:
        utils.echo(click.style(f"EPP Error: {exc}", fg="red"), err=True)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        utils.echo(click.style(f"Error: {exc}", fg="red"), err=True)
    finally:
        # Record round-trip command execution time for the status bar and 'status' output
        if record_latency:
            cli_obj.last_latency_ms = int(round((time.perf_counter() - start_t) * 1000))


def _handle_use_command(cli_obj, args: list[str]) -> None:
    """Handle 'use <profile_name>' command."""
    if len(args) != 1:
        utils.echo(click.style("Usage: use <profile_name>", fg="yellow"), err=True)
    else:
        switch_profile(cli_obj, args[0])


def _handle_builtin_command(cli_obj, cmd: str, args: list[str]) -> None:
    """Execute a built-in shell control command."""
    if cmd == "help":
        if not args:
            utils.echo(_format_help_text())
        else:
            _dispatch_click_command(cli_obj, args + ["--help"])
        return

    if cmd == "clear":
        click.clear()
        return

    if cmd == "reconnect":
        _safe_close_session(cli_obj)
        _connect_and_login(cli_obj)
        return

    handlers = {
        "status": lambda: _print_status(cli_obj),
        "use": lambda: _handle_use_command(cli_obj, args),
        "set": lambda: _handle_set_command(cli_obj, args),
        "history": lambda: _handle_history_command(cli_obj, args),
        "last": lambda: _handle_last_command(cli_obj, args),
        "save": lambda: _handle_save_command(cli_obj, args),
    }
    handler = handlers.get(cmd)
    if handler is not None:
        handler()


def _is_sensitive_line(line: str) -> bool:
    """Return True if a command line contains password/secret flags that must not be stored in history."""
    return bool(_SENSITIVE_LINE_RE.search(line))


def _expand_history_reference(cli_obj, stripped: str) -> Optional[str]:
    """Expand '!!' (last command) or '!<N>' (1-based or negative relative history index)."""
    if not stripped.startswith("!"):
        return stripped

    history_list: list[str] = getattr(cli_obj, "session_history", None) or []
    if stripped == "!!":
        if not history_list:
            utils.echo(click.style("No previous command in history.", fg="yellow"), err=True)
            return None
        expanded = _sanitize_display(history_list[-1])
        utils.echo(click.style(expanded, fg="cyan"))
        return expanded

    try:
        idx = int(stripped[1:].strip())
    except ValueError:
        msg = f"Invalid history reference '{stripped}'. Use '!!' or '!<number>'."
        utils.echo(click.style(msg, fg="red"), err=True)
        return None

    if 0 < idx <= len(history_list):
        expanded = _sanitize_display(history_list[idx - 1])
    elif idx < 0 and abs(idx) <= len(history_list):
        expanded = _sanitize_display(history_list[idx])
    else:
        utils.echo(click.style(f"History event '{stripped}' not found.", fg="red"), err=True)
        return None

    utils.echo(click.style(expanded, fg="cyan"))
    return expanded


def _record_session_history(cli_obj, stripped: str, cmd: str) -> None:
    """Append a non-sensitive command line to `cli_obj.session_history`."""
    if _is_sensitive_line(stripped) or cmd in ("history", "exit", "quit"):
        return
    if not hasattr(cli_obj, "session_history") or cli_obj.session_history is None:
        cli_obj.session_history = []
    # Avoid duplicating consecutive identical commands
    if not cli_obj.session_history or cli_obj.session_history[-1] != stripped:
        cli_obj.session_history.append(stripped)
        if len(cli_obj.session_history) > MAX_HISTORY_ENTRIES:
            cli_obj.session_history = cli_obj.session_history[-MAX_HISTORY_ENTRIES:]


def execute_shell_line(cli_obj, line: str) -> bool:
    """Parse and execute a command line in the shell (returns False if user requested exit)."""
    # Scrub raw input containing sensitive flags immediately before any early return (e.g. parse error)
    _scrub_sensitive_history(line)
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return True

    expanded = _expand_history_reference(cli_obj, stripped)
    if expanded is None:
        return True
    stripped = expanded

    try:
        tokens = shlex.split(stripped)
    except ValueError as exc:
        utils.echo(click.style(f"Parse error: {exc}", fg="red"), err=True)
        return True

    if not tokens:
        return True

    raw_cmd = tokens[0].lower()
    cmd = SHELL_ALIASES.get(raw_cmd, raw_cmd)
    if cmd in ("exit", "quit"):
        return False

    _record_session_history(cli_obj, stripped, cmd)

    if cmd in SHELL_BUILTIN_COMMANDS:
        try:
            _handle_builtin_command(cli_obj, cmd, tokens[1:])
        except Exception as exc:  # pylint: disable=broad-exception-caught
            utils.echo(click.style(f"Error: {exc}", fg="red"), err=True)
    else:
        _dispatch_click_command(cli_obj, tokens)

    return True


class ShellCompleter:
    """Readline tab auto-completer for PyEPP interactive shell commands, subcommands, and options."""

    def __init__(self, cli_obj) -> None:
        self.cli_obj = cli_obj
        self._matches: list[str] = []

    def _get_profile_names(self) -> list[str]:
        """Return available profile names from configuration file."""
        try:
            return list_profiles(self.cli_obj.config_file)
        except Exception:  # pylint: disable=broad-exception-caught
            return ["default"]

    @staticmethod
    def _extract_command_options(cmd: click.Command) -> list[str]:
        """Extract long option flags from a Click command."""
        opts = ["--help"]
        for param in getattr(cmd, "params", []):
            if isinstance(param, click.Option):
                for opt in param.opts + param.secondary_opts:
                    if opt.startswith("--"):
                        opts.append(opt)
        return sorted(set(opts))

    def _complete_second_token(
        self, first: str, text: str, cmd_groups: dict[str, click.Command]
    ) -> list[str]:
        """Return completion candidates when completing the second token on the line."""
        candidates: list[str] = []
        if first == "use":
            candidates = [p for p in self._get_profile_names() if p.lower().startswith(text.lower())]
        elif first == "set":
            candidates = [k for k in SET_KEYS if k.startswith(text.lower())]
        elif first == "last":
            candidates = [f for f in VALID_OUTPUT_FORMATS if f.startswith(text.upper())]
        elif first in ("help", "?"):
            candidates = [c for c in sorted(cmd_groups.keys()) if c.startswith(text.lower())]
        elif first == "profile":
            sub_names = sorted(list(profile_group.commands.keys()) + ["use"])
            candidates = [s for s in sub_names if s.startswith(text.lower())]
        elif first in cmd_groups:
            grp = cmd_groups[first]
            if isinstance(grp, click.Group):
                candidates = [s for s in sorted(grp.commands.keys()) if s.startswith(text.lower())]
            else:
                candidates = [o for o in self._extract_command_options(grp) if o.startswith(text)]
        return candidates

    def _complete_subsequent_tokens(
        self, tokens: list[str], text: str, cmd_groups: dict[str, click.Command]
    ) -> list[str]:
        """Return completion candidates when completing the third or later token."""
        first = tokens[0].lower()
        second = tokens[1].lower()
        candidates: list[str] = []

        if tokens[-1] in ("--output-format", "-o"):
            return [f for f in VALID_OUTPUT_FORMATS if f.startswith(text.upper())]

        if first == "set" and len(tokens) == 2:
            if second == "output-format":
                candidates = [f for f in VALID_OUTPUT_FORMATS if f.startswith(text.upper())]
            elif second in ("pretty", "dry-run"):
                candidates = [v for v in ("on", "off") if v.startswith(text.lower())]
        elif first == "save" and len(tokens) == 2:
            candidates = [f for f in VALID_OUTPUT_FORMATS if f.startswith(text.upper())]
        elif first == "profile" and second in ("use", "show") and len(tokens) == 2:
            sub_cmd = profile_group.commands.get(second)
            if text.startswith("-") and sub_cmd:
                candidates = [o for o in self._extract_command_options(sub_cmd) if o.startswith(text)]
            else:
                candidates = [p for p in self._get_profile_names() if p.lower().startswith(text.lower())]
        elif first in ("help", "?") and len(tokens) == 2 and second in cmd_groups:
            grp = cmd_groups[second]
            if isinstance(grp, click.Group):
                candidates = [s for s in sorted(grp.commands.keys()) if s.startswith(text.lower())]
        elif first in cmd_groups:
            grp = cmd_groups[first]
            target_cmd = grp.commands.get(second) if isinstance(grp, click.Group) else grp
            if target_cmd:
                candidates = [o for o in self._extract_command_options(target_cmd) if o.startswith(text)]

        return candidates

    def get_candidates(self, line_buffer: str, text: str) -> list[str]:
        """Compute completion candidates for the current readline line buffer and token prefix."""
        cmd_groups = _get_command_groups()
        top_commands = sorted(list(cmd_groups.keys()) + list(SHELL_BUILTIN_COMMANDS))

        # Split buffer up to the current word being completed
        prefix_buffer = line_buffer[: len(line_buffer) - len(text)]
        try:
            tokens = shlex.split(prefix_buffer)
        except ValueError:
            tokens = prefix_buffer.split()

        if not tokens:
            return [c for c in top_commands if c.startswith(text.lower())]

        if len(tokens) == 1:
            return self._complete_second_token(tokens[0].lower(), text, cmd_groups)

        return self._complete_subsequent_tokens(tokens, text, cmd_groups)

    def complete(self, text: str, state: int) -> Optional[str]:
        """Readline completer callback."""
        if state == 0:
            line_buffer = _readline.get_line_buffer() if _readline is not None else text
            self._matches = self.get_candidates(line_buffer, text)
        if state < len(self._matches):
            return self._matches[state]
        return None


def get_default_history_path() -> str:
    """Return path to the persistent shell history file (`~/.pyepp/history`)."""
    env_path = os.environ.get("PYEPP_HISTORY_FILE")
    if env_path:
        return os.path.expanduser(env_path)
    return os.path.expanduser("~/.pyepp/history")


def _load_persistent_history(cli_obj, history_file: Optional[str] = None) -> None:
    """Load non-sensitive command history from disk into `cli_obj.session_history` and readline."""
    path = history_file or get_default_history_path()
    # Refuse symlinked history files and strip control characters to prevent CWE-150 injection
    if not path or os.path.islink(path) or not os.path.isfile(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as file_obj:
            lines = [
                _sanitize_display(ln.strip())
                for ln in file_obj
                if _sanitize_display(ln.strip()) and not _is_sensitive_line(ln)
            ]
        recent = lines[-MAX_HISTORY_ENTRIES:]
        cli_obj.session_history = list(recent)
        if _readline is not None and hasattr(_readline, "add_history"):
            for item in recent:
                _readline.add_history(item)
    except OSError as exc:
        logging.debug("Could not load persistent shell history: %s", exc)


def _save_persistent_history(cli_obj, history_file: Optional[str] = None) -> None:
    """Save non-sensitive command history to `~/.pyepp/history` with owner-only (`0600`) mode."""
    history_list: list[str] = getattr(cli_obj, "session_history", None) or []
    safe = [e for e in history_list if e and not _is_sensitive_line(e)][-MAX_HISTORY_ENTRIES:]
    path = history_file or get_default_history_path()
    if not safe or not path or os.path.islink(path):
        return
    try:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, mode=0o700, exist_ok=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(path, flags, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as file_obj:
            file_obj.write("\n".join(safe) + "\n")
        os.chmod(path, 0o600)
    except OSError as exc:
        logging.debug("Could not save persistent shell history: %s", exc)


def _scrub_sensitive_history(line: str) -> None:
    """Remove the most recent readline history entry if the line contains a password flag."""
    if _readline is None or not _is_sensitive_line(line):
        return
    try:
        if hasattr(_readline, "get_current_history_length") and hasattr(_readline, "remove_history_item"):
            length = _readline.get_current_history_length()
            if length > 0:
                _readline.remove_history_item(length - 1)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logging.debug("Could not scrub sensitive history item: %s", exc)


def _configure_readline(completer: ShellCompleter) -> Optional[str]:
    """Configure readline tab auto-completion and word delimiters if available."""
    if _readline is None:  # pragma: no cover
        return None
    old_delims = _readline.get_completer_delims()
    _readline.set_completer(completer.complete)
    # Remove '-' from completer_delims so options like '--client-transaction-id'
    # and subcommands like 'restore-report' complete as a single token.
    delims = old_delims.replace("-", "")
    _readline.set_completer_delims(delims)
    doc = getattr(_readline, "__doc__", "") or ""
    if "libedit" in doc:
        _readline.parse_and_bind("bind ^I rl_complete")
    else:
        _readline.parse_and_bind("tab: complete")
    return old_delims


def _cleanup_readline(old_delims: Optional[str] = None) -> None:
    """Release readline completer references, restore delimiters, and clear session history."""
    if _readline is None:  # pragma: no cover
        return
    try:
        _readline.set_completer(None)
        if old_delims is not None:
            _readline.set_completer_delims(old_delims)
        if hasattr(_readline, "clear_history"):
            _readline.clear_history()
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logging.debug("Readline cleanup failed: %s", exc)


@click.command(name="shell")
@click.pass_context
def shell_command(ctx) -> None:
    """Start an interactive PyEPP shell session with persistent connection and auto-completion."""
    cli_obj = ctx.obj
    cli_obj.persistent_session = True

    utils.echo(click.style(ASCII_BANNER.strip("\n"), fg="bright_cyan", bold=True))
    welcome_msg = (
        f"{click.style(f'Interactive EPP Shell (v{__version__})', fg='cyan', bold=True)} - "
        f"Type {click.style('help', fg='yellow', bold=True)} for commands, "
        f"{click.style('exit', fg='yellow', bold=True)} to quit.\n"
    )
    utils.echo(welcome_msg)

    completer = ShellCompleter(cli_obj)
    old_delims = _configure_readline(completer)
    _load_persistent_history(cli_obj)

    try:
        _connect_and_login(cli_obj)
        while True:
            try:
                line = _read_line_with_status_bar(cli_obj)
            except KeyboardInterrupt:
                prefix = "" if _supports_ansi_tty() else "\n"
                msg = f"{prefix}Interrupted. Type 'exit' or press Ctrl+D to quit."
                utils.echo(click.style(msg, fg="yellow"))
                continue
            except EOFError:
                prefix = "" if _supports_ansi_tty() else "\n"
                utils.echo(click.style(f"{prefix}Exiting shell...", fg="cyan"))
                break

            if not execute_shell_line(cli_obj, line):
                utils.echo(click.style("Exiting shell...", fg="cyan"))
                break
    finally:
        _save_persistent_history(cli_obj)
        _cleanup_readline(old_delims)
        _safe_close_session(cli_obj)
