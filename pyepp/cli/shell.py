"""
Interactive CLI Shell / REPL session module for PyEPP.

Provides a persistent EPP session (`pyepp shell`) with ASCII startup banner,
readline tab auto-completion, command history, and mid-session profile switching.
"""
# pylint: disable=too-many-lines

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
    "use", "set", "unset", "status", "reconnect", "clear", "history", "last", "save", "help", "exit", "quit"
)
SHELL_ALIASES = {"?": "help", "q": "exit", "st": "status", "hist": "history"}
MAX_HISTORY_ENTRIES = 500
SET_KEYS = ("output-format", "pretty", "dry-run", "debug")
UNSET_KEYS = ("debug", "dry-run", "pretty")

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
  set debug <on|off>               Enable or disable debug logging
  unset <debug|dry-run|pretty>     Disable debug logging, dry-run, or pretty output
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


def _safe_close_session(cli_obj, has_active_exception: Optional[bool] = None) -> None:
    """
    Safely log out and disconnect an active session without raising exceptions.

    Preserves the teardown contract from EppCommunicator.__exit__:
    - Validates logout response code via cli_obj.logout().
    - Records any logout exception in cli_obj.last_logout_error and cli_obj.epp._last_logout_error.
    - Warns during normal cleanup (exc_type is None) and logs at DEBUG when handling an active exception.
    - Always disconnects the transport afterward.
    """
    epp = getattr(cli_obj, "epp", None)
    if epp is None:
        return
    if has_active_exception is None:
        has_active_exception = sys.exc_info()[0] is not None

    try:
        if getattr(epp, "is_logged_in", False) and not getattr(cli_obj, "dry_run", False):
            cli_obj.logout()
    except Exception as exc:  # pylint: disable=broad-exception-caught
        cli_obj.last_logout_error = exc
        if hasattr(epp, "_last_logout_error"):
            epp._last_logout_error = exc  # pylint: disable=protected-access
        if not has_active_exception:
            logging.warning("Logout failed during shell session cleanup: %s", exc)
        else:
            logging.debug("Logout failed during shell session cleanup while handling exception: %s", exc)
    finally:
        try:
            cli_obj.disconnect()
        except Exception as exc:  # pylint: disable=broad-exception-caught
            if not has_active_exception:
                logging.warning("Disconnect failed during shell session cleanup: %s", exc)
            else:
                logging.debug("Disconnect failed during shell session cleanup while handling exception: %s", exc)


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
        prof.server,
        prof.port,
        prof.client_cert,
        prof.client_key,
        prof.dry_run,
        timeout=getattr(prof, "timeout", None),
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


def _supports_dock() -> bool:
    """Return True if stdout supports ANSI sequences and has sufficient dimensions for the 4-row dock."""
    if not _supports_ansi_tty():
        return False
    size = shutil.get_terminal_size((80, 24))
    return size.lines >= 6 and size.columns >= 12


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
    """Append optional poll queue badge, debug indicator, and last command latency to status bar segments."""
    # Display 'debug: on' badge in yellow when debug mode is enabled in the active session
    if getattr(cli_obj, "debug", False):
        dbg_text = "debug: on"
        segments.append(click.style(dbg_text, fg="yellow", bold=True) if color else dbg_text)

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


def _get_dock_geometry() -> tuple[int, int, int, int, int, int]:
    """
    Compute terminal width and 1-based row coordinates for the scrollable output
    region (`1..scroll_bottom`) and the pinned 4-row bottom dock (`H-3..H`).

    Returns:
        Tuple of (width, scroll_bottom, top_div_row, prompt_row, bot_div_row, status_row).
    """
    size = shutil.get_terminal_size((80, 24))
    width = max(1, size.columns - 1)
    lines = max(6, size.lines)
    scroll_bottom = lines - 4
    return width, scroll_bottom, lines - 3, lines - 2, lines - 1, lines


class _ShellLoggingFilter(logging.Filter):  # pylint: disable=too-few-public-methods
    """Flush pending shell command into the scrollable output region before emitting log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        _flush_pending_command()
        return True


def _enter_bottom_dock() -> None:
    """Reserve the bottom 4 terminal rows for the prompt dock and activate the scroll region."""
    if not _supports_dock():
        return
    _, scroll_bottom, _, _, _, _ = _get_dock_geometry()
    # Push existing terminal lines up by 4 rows so the dock never overwrites prior content,
    # then set DECSTBM (\033[1;<scroll_bottom>r) and anchor the cursor at scroll_bottom.
    sys.stdout.write("\n" * 4 + f"\033[1;{scroll_bottom}r\033[{scroll_bottom};1H")
    sys.stdout.flush()


def _exit_bottom_dock() -> None:
    """Reset the terminal scroll region to full screen and erase the 4-row bottom dock on exit."""
    if not _supports_ansi_tty():
        return
    if not _supports_dock():
        # Even if the terminal was resized smaller than the dock threshold during the session,
        # always reset DECSTBM (\033[r) on an ANSI TTY so the scroll region is never left stranded.
        sys.stdout.write("\033[r")
        sys.stdout.flush()
        return
    _, scroll_bottom, top_div_row, prompt_row, bot_div_row, status_row = _get_dock_geometry()
    sys.stdout.write(
        "\033[r"
        f"\033[{top_div_row};1H\033[2K"
        f"\033[{prompt_row};1H\033[2K"
        f"\033[{bot_div_row};1H\033[2K"
        f"\033[{status_row};1H\033[2K"
        f"\033[{scroll_bottom};1H\r\033[2K"
    )
    sys.stdout.flush()


def _flush_pending_command() -> None:
    """
    Transition a submitted command from the pinned bottom dock into the scrollable output
    region right before the first line of command output is written (or after a silent command
    completes).

    Keeping the user's submitted command in place inside the bottom dock while a network
    request is in flight prevents pressing Enter from inserting a visible blank line or
    making the prompt dock jump before the response arrives.
    """
    pending_cmd = getattr(_flush_pending_command, "pending_command", None)
    if pending_cmd is None:
        return
    _flush_pending_command.pending_command = None
    if not _supports_dock():
        return
    width, scroll_bottom, top_div_row, prompt_row, bot_div_row, _ = _get_dock_geometry()
    color = _use_color()
    divider = format_divider_line(width, color=color)
    sys.stdout.write(
        f"\033[1;{scroll_bottom}r"
        f"\033[{top_div_row};1H\033[2K{divider}"
        f"\033[{prompt_row};1H\033[2K"
        f"\033[{bot_div_row};1H\033[2K{divider}"
        f"\033[{scroll_bottom};1H\r\033[2K{divider}\n\r\033[2K{pending_cmd}\n\r\033[2K"
    )
    sys.stdout.flush()


def _format_input_viewport(
    prompt: str, buffer: str, cursor_pos: int, max_cols: int
) -> tuple[str, int]:
    """
    Format prompt and command buffer to strictly fit within a single terminal row.

    When the combined length exceeds `max_cols`, computes a horizontally scrolled viewport
    window containing `cursor_pos` with '<' and/or '>' scroll markers. This prevents long
    commands from wrapping onto subsequent rows and corrupting the bottom divider or status bar.

    Args:
        prompt: Prompt string (may contain ANSI color styling).
        buffer: Full unformatted input buffer.
        cursor_pos: Zero-based cursor character offset in buffer.
        max_cols: Maximum terminal columns available on the prompt row (width - 1).

    Returns:
        tuple of (rendered_prompt_row_text, backward_cursor_offset)
        where `backward_cursor_offset` is the number of columns to move left from the
        end of `rendered_prompt_row_text` to reach `cursor_pos` (for `\033[<N>D`).
    """
    if max_cols <= 0:
        return "", 0

    cursor_pos = max(0, min(cursor_pos, len(buffer)))
    plain_prompt = click.unstyle(prompt)
    if len(plain_prompt) + len(buffer) <= max_cols:
        return f"{prompt}{buffer}", len(buffer) - cursor_pos

    # In narrow viewports, truncate the prompt if it leaves fewer than 3 columns for the buffer
    if len(plain_prompt) >= max_cols - 2 and max_cols > 3:
        prompt = _truncate_ansi(prompt, max_cols - 3)
        plain_prompt = click.unstyle(prompt)
    elif max_cols <= 3:
        prompt = ""
        plain_prompt = ""

    # Available character width strictly bounded by actual remaining columns
    avail = max(1, max_cols - len(plain_prompt))
    if not buffer:
        slice_text = ""
        shift = 0
    elif avail == 1:
        slice_text = ">" if cursor_pos < len(buffer) else "<"
        shift = 0
    elif cursor_pos < avail - 1:
        # Cursor is near the start; show head of buffer with trailing '>' indicator
        slice_text = buffer[: avail - 1] + ">"
        shift = len(slice_text) - cursor_pos
    else:
        # Cursor is scrolled right; show window containing cursor with '<' / '>' markers
        prefix = "<"
        suffix = ">" if cursor_pos + 1 < len(buffer) else ""
        span = max(1, avail - len(prefix) - len(suffix))
        end = min(len(buffer), cursor_pos + 1)
        start = max(0, end - span)
        slice_text = prefix + buffer[start:end] + suffix
        if len(slice_text) > avail:
            slice_text = slice_text[:avail]
        shift = len(slice_text) - (len(prefix) + cursor_pos - start)

    rendered = f"{prompt}{slice_text}"
    return rendered, max(0, min(len(slice_text), shift))


def _read_line_with_status_bar(cli_obj) -> str:
    """Render the pinned 4-row bottom dock (dividers, prompt, status bar) and read a command line."""
    if not _supports_dock():
        return input(format_prompt(cli_obj, color=False))

    _flush_pending_command()
    color = _use_color()
    width, scroll_bottom, top_div_row, prompt_row, bot_div_row, status_row = _get_dock_geometry()
    divider = format_divider_line(width, color=color)
    # Truncate status bar to (columns - 1) so it never wraps onto a second row.
    status_line = format_status_bar(cli_obj, color=color, max_width=width)
    # Lock scroll region to rows 1..scroll_bottom and render the 4-row dock at the bottom:
    #   top_div_row (H-3): top divider
    #   prompt_row  (H-2): input prompt
    #   bot_div_row (H-1): bottom divider
    #   status_row  (H):   status bar
    sys.stdout.write(
        f"\033[1;{scroll_bottom}r"
        f"\033[{top_div_row};1H\033[2K{divider}"
        f"\033[{prompt_row};1H\033[2K"
        f"\033[{bot_div_row};1H\033[2K{divider}"
        f"\033[{status_row};1H\033[2K{status_line}"
        f"\033[{prompt_row};1H"
    )
    sys.stdout.flush()

    try:
        line = input(format_prompt(cli_obj, color=color))
    except BaseException:
        _flush_pending_command.pending_command = None
        # Clear prompt row, restore bottom divider/status bar, and move cursor back into
        # the bottom of the scrollable output region (scroll_bottom) for interrupt/exit messages.
        sys.stdout.write(
            f"\033[{top_div_row};1H\033[2K{divider}"
            f"\033[{prompt_row};1H\033[2K"
            f"\033[{bot_div_row};1H\033[2K{divider}"
            f"\033[{status_row};1H\033[2K{status_line}"
            f"\033[{scroll_bottom};1H\r\033[2K"
        )
        sys.stdout.flush()
        raise

    # Immediately restore bot_div_row (which readline's Enter newline moved onto) and keep the
    # cursor at the end of the submitted command on prompt_row while the command executes.
    # The command is scrolled into the output region only when output is emitted (or after
    # execution completes), preventing any blank-line jump when pressing Enter.
    stripped = line.strip()
    has_output = bool(stripped and not stripped.startswith("#"))
    prompt_str = format_prompt(cli_obj, color=color).replace("\x01", "").replace("\x02", "")
    if has_output:
        _flush_pending_command.pending_command = f"{prompt_str}{line}"
        disp_cmd, _ = _format_input_viewport(prompt_str, line, len(line), width - 1)
        sys.stdout.write(
            f"\033[{top_div_row};1H\033[2K{divider}"
            f"\033[{bot_div_row};1H\033[2K{divider}"
            f"\033[{status_row};1H\033[2K{status_line}"
            f"\033[{prompt_row};1H\033[2K{disp_cmd}"
        )
    else:
        _flush_pending_command.pending_command = None
        sys.stdout.write(
            f"\033[{top_div_row};1H\033[2K{divider}"
            f"\033[{prompt_row};1H\033[2K"
            f"\033[{bot_div_row};1H\033[2K{divider}"
            f"\033[{status_row};1H\033[2K{status_line}"
            f"\033[{scroll_bottom};1H\r\033[2K"
        )
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
    debug_str = _style_bool(getattr(cli_obj, "debug", False), true_color="yellow", false_color="green")
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
        f"{click.style('Debug:', fg='cyan', bold=True)}         {debug_str}",
    ]
    poll_count = getattr(cli_obj, "poll_queue_count", None)
    if isinstance(poll_count, int):
        p_val = click.style(str(poll_count), fg="yellow" if poll_count > 0 else "green", bold=True)
        lines.append(f"{click.style('Poll Queue:', fg='cyan', bold=True)}    {p_val}")
    latency_ms = getattr(cli_obj, "last_latency_ms", None)
    if latency_ms is not None:
        lines.append(f"{click.style('Last Latency:', fg='cyan', bold=True)}  {latency_ms}ms")
    utils.echo("\n".join(lines))


def _set_debug_mode(cli_obj, enabled: bool) -> None:
    """
    Enable or disable debug logging mode on the active CLI session and root logger.

    When enabled, the root logger level is set to DEBUG to emit raw XML payloads
    and transport diagnostics. When disabled, the logger level is restored to INFO
    (if verbose mode was specified at startup) or ERROR.
    """
    cli_obj.debug = enabled
    root_logger = logging.getLogger()
    if enabled:
        # If no logging handler exists (e.g. standalone test execution), ensure basicConfig is initialized
        if not root_logger.handlers:
            logging.basicConfig(level=logging.DEBUG)
        else:
            root_logger.setLevel(logging.DEBUG)
    else:
        log_level = logging.INFO if getattr(cli_obj, "verbose", False) else logging.ERROR
        root_logger.setLevel(log_level)


def _set_output_format(cli_obj, val: str) -> None:
    """Apply output-format setting."""
    fmt = val.upper()
    if fmt not in VALID_OUTPUT_FORMATS:
        allowed = ", ".join(VALID_OUTPUT_FORMATS)
        msg = f"Invalid output format '{val}'. Choose from: {allowed}"
        utils.echo(click.style(msg, fg="red"), err=True)
        return
    cli_obj.output_format = fmt
    utils.echo(click.style(f"Output format set to {fmt}.", fg="green"))


def _set_pretty(cli_obj, val: str) -> None:
    """Apply pretty-printing setting."""
    if val.lower() in ("on", "true", "1", "yes"):
        cli_obj.no_pretty = False
        utils.echo(click.style("Pretty output enabled.", fg="green"))
    elif val.lower() in ("off", "false", "0", "no"):
        cli_obj.no_pretty = True
        utils.echo(click.style("Pretty output disabled.", fg="yellow"))
    else:
        utils.echo(click.style("Usage: set pretty <on|off>", fg="yellow"), err=True)


def _set_dry_run(cli_obj, val: str) -> None:
    """Apply dry-run mode setting."""
    if val.lower() in ("on", "true", "1", "yes"):
        if not cli_obj.dry_run:
            _safe_close_session(cli_obj)
            cli_obj.dry_run = True
            cli_obj.epp._dry_run = True  # pylint: disable=protected-access
        utils.echo(click.style("Dry-run mode enabled.", fg="yellow"))
    elif val.lower() in ("off", "false", "0", "no"):
        # Only tear down and reconnect when transitioning out of dry-run mode or when disconnected,
        # so disabling an already-disabled dry-run does not drop an active live EPP session.
        was_dry_run = bool(cli_obj.dry_run)
        cli_obj.dry_run = False
        cli_obj.epp._dry_run = False  # pylint: disable=protected-access
        utils.echo(click.style("Dry-run mode disabled.", fg="green"))
        if was_dry_run or not getattr(cli_obj.epp, "is_logged_in", False):
            _safe_close_session(cli_obj)
            _connect_and_login(cli_obj)
    else:
        utils.echo(click.style("Usage: set dry-run <on|off>", fg="yellow"), err=True)


def _set_debug(cli_obj, val: str) -> None:
    """Apply debug logging mode setting."""
    if val.lower() in ("on", "true", "1", "yes"):
        _set_debug_mode(cli_obj, True)
        utils.echo(click.style("Debug mode enabled.", fg="yellow"))
    elif val.lower() in ("off", "false", "0", "no"):
        _set_debug_mode(cli_obj, False)
        utils.echo(click.style("Debug mode disabled.", fg="green"))
    else:
        utils.echo(click.style("Usage: set debug <on|off>", fg="yellow"), err=True)


def _handle_set_command(cli_obj, args: list[str]) -> None:
    """Handle 'set <key> <value>' shell command to modify session settings on the fly."""
    # Allow 'set <boolean-key>' without an explicit value as a natural shorthand to enable it
    if len(args) == 1:
        single_key = args[0].lower()
        if single_key == "debug":
            _set_debug(cli_obj, "on")
            return
        if single_key in ("dry-run", "dry_run"):
            _set_dry_run(cli_obj, "on")
            return
        if single_key == "pretty":
            _set_pretty(cli_obj, "on")
            return

    if len(args) != 2:
        utils.echo(
            click.style("Usage: set <output-format|pretty|dry-run|debug> <value>", fg="yellow"),
            err=True,
        )
        return

    key, val = args[0].lower(), args[1].strip()
    if key in ("output-format", "output_format", "format"):
        _set_output_format(cli_obj, val)
    elif key == "pretty":
        _set_pretty(cli_obj, val)
    elif key in ("dry-run", "dry_run"):
        _set_dry_run(cli_obj, val)
    elif key == "debug":
        _set_debug(cli_obj, val)
    else:
        msg = f"Unknown setting '{key}'. Available settings: {', '.join(SET_KEYS)}"
        utils.echo(click.style(msg, fg="red"), err=True)


def _handle_unset_command(cli_obj, args: list[str]) -> None:
    """Handle 'unset <key>' shell command to disable boolean settings (debug, dry-run, pretty)."""
    if len(args) != 1:
        utils.echo(click.style("Usage: unset <debug|dry-run|pretty>", fg="yellow"), err=True)
        return

    key = args[0].lower()
    if key == "debug":
        _set_debug(cli_obj, "off")
    elif key in ("dry-run", "dry_run"):
        _set_dry_run(cli_obj, "off")
    elif key == "pretty":
        _set_pretty(cli_obj, "off")
    else:
        msg = f"Unknown setting '{key}'. Available settings to unset: {', '.join(UNSET_KEYS)}"
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
        if rendered is None:
            return ""
        # When pretty-printing is disabled, format_output returns raw XML as bytes.
        # Decode bytes as UTF-8 so the shell displays and saves clean XML text
        # rather than Python's b'...' string representation.
        if isinstance(rendered, (bytes, bytearray)):
            return rendered.decode("utf-8", errors="replace")
        return str(rendered)
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


def _cleanup_unexpected_arg_history(cli_obj, raw_line: str, exc: click.UsageError) -> None:
    """Defensively scrub command from session and readline history if rejected due to extra arguments."""
    if "unexpected extra argument" in str(exc).lower() and not _is_sensitive_line(raw_line):
        history = getattr(cli_obj, "session_history", None)
        if raw_line and history and history[-1] == raw_line:
            history.pop()
        _scrub_last_readline_history_item()


def _dispatch_click_command(cli_obj, tokens: list[str], raw_line: str = "") -> None:
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
    if not record_latency:
        _flush_pending_command()
    start_t = time.perf_counter()
    try:
        cmd_obj.main(args=sub_args, prog_name=cmd_name, obj=cli_obj, standalone_mode=False)
    except click.UsageError as exc:
        record_latency = False
        _flush_pending_command()
        _cleanup_unexpected_arg_history(cli_obj, raw_line, exc)
        exc.show()
    except click.ClickException as exc:
        record_latency = False
        _flush_pending_command()
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
        _flush_pending_command.pending_command = None
        click.clear()
        if _supports_dock():
            _, scroll_bottom, _, _, _, _ = _get_dock_geometry()
            sys.stdout.write(f"\033[1;{scroll_bottom}r\033[{scroll_bottom};1H")
            sys.stdout.flush()
        return

    if cmd == "reconnect":
        _safe_close_session(cli_obj)
        _connect_and_login(cli_obj)
        return

    handlers = {
        "status": lambda: _print_status(cli_obj),
        "use": lambda: _handle_use_command(cli_obj, args),
        "set": lambda: _handle_set_command(cli_obj, args),
        "unset": lambda: _handle_unset_command(cli_obj, args),
        "history": lambda: _handle_history_command(cli_obj, args),
        "last": lambda: _handle_last_command(cli_obj, args),
        "save": lambda: _handle_save_command(cli_obj, args),
    }
    handler = handlers.get(cmd)
    if handler is not None:
        handler()


def _has_positional_or_extra_credentials(tokens: list[str]) -> bool:
    """Return True if tokens contain a positional password or extra arguments on a password-capable command.

    In EPP, passwords/authInfo can be provided positionally (e.g. `domain transfer <domain> <password>`)
    or mistakenly typed positionally without the `--password` flag (e.g. `domain update example.nz <password>`).
    We parse arguments using Click's command parser to accurately identify positional credentials and
    accidental extra positional arguments on password-accepting commands, preventing credential leakage
    into shell history even when syntax errors occur or when `--help` is requested with arguments.
    """
    cmd_tokens = list(tokens)
    if cmd_tokens and cmd_tokens[0].lower() == "pyepp":
        cmd_tokens = cmd_tokens[1:]
    if len(cmd_tokens) < 2:
        return False

    grp_name = cmd_tokens[0].lower()
    sub_name = cmd_tokens[1].lower()
    grp = _get_command_groups().get(grp_name)
    sub_cmd = grp.commands.get(sub_name) if isinstance(grp, click.Group) else None
    if sub_cmd is None:
        return False

    # Check whether the subcommand accepts a password or auth-info argument/option
    has_pwd_param = any(
        getattr(p, "name", "").lower() in ("password", "auth_info", "authinfo", "auth")
        for p in getattr(sub_cmd, "params", [])
    )

    try:
        parser = sub_cmd.make_parser(click.Context(sub_cmd))
        opts, extra_args, _ = parser.parse_args(cmd_tokens[2:])
    except Exception:  # pylint: disable=broad-exception-caught
        # On option parsing errors (e.g. missing option value like '--period', or unknown options),
        # treat lines on password-capable commands as sensitive to prevent leaking positional credentials.
        return bool(has_pwd_param)

    # Check 1: positional password argument (e.g. domain transfer <domain> <password> [--help])
    pwd = opts.get("password")
    if isinstance(pwd, str) and pwd.strip():
        return True

    # Check 2: extra positional arguments on any command accepting a password parameter
    # (e.g. accidental omission of '--password' in 'domain update <domain> <password>')
    return bool(extra_args and has_pwd_param)


def _is_sensitive_line(line: str) -> bool:
    """Return True if a command line contains passwords, secrets, or auth-info that
    must not be stored in readline/session history or persisted to disk.

    Handles quoted password flags (e.g. `"--password"`), positional transfer passwords
    (`domain transfer <domain> <password>`), accidental positional credentials on
    password-capable commands (`domain update <domain> <password>`), and malformed/unbalanced input.
    """
    if not line or not line.strip():
        return False

    # Fast-path regex check for unquoted password/secrets flags
    if _SENSITIVE_LINE_RE.search(line):
        return True

    # Parse tokens to handle quoted flags (e.g. "--password") and positional credentials
    try:
        tokens = shlex.split(line)
    except ValueError:
        # On malformed/unbalanced input (e.g. unclosed quotes), conservatively scrub if
        # any sensitive keyword or auth pattern appears in the input.
        lower = line.lower()
        return any(kw in lower for kw in ("pass", "secret", "auth", "transfer"))

    # Check for sensitive flags in parsed tokens (handles quotes like "--password" or '--show-secrets')
    if any(tok.lower().startswith(("--pass", "--show-secrets")) for tok in tokens):
        return True

    # Check for positional credentials or accidental extra positional arguments on password-capable commands
    return _has_positional_or_extra_credentials(tokens)


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
        _dispatch_click_command(cli_obj, tokens, raw_line=stripped)

    return True


class ShellCompleter:
    """Readline tab auto-completer for PyEPP interactive shell commands, subcommands, and options."""

    def __init__(self, cli_obj) -> None:
        self.cli_obj = cli_obj
        self._matches: list[str] = []
        self._last_prefix_expanded: Optional[str] = None

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
        elif first == "unset":
            candidates = [k for k in UNSET_KEYS if k.startswith(text.lower())]
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
            elif second in ("pretty", "dry-run", "debug"):
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

    def _format_completion_columns(self, matches: list[str], width: int) -> str:
        """Format completion candidates into aligned multi-column rows that fit within `width`."""
        col_width = min(max(1, width), max(len(m) for m in matches) + 4)
        cols = max(1, width // col_width)
        rows = (len(matches) + cols - 1) // cols
        lines: list[str] = []
        for row_idx in range(rows):
            row_items: list[str] = []
            for col_idx in range(cols):
                idx = row_idx + col_idx * rows
                if idx < len(matches):
                    row_items.append(matches[idx].ljust(col_width))
            lines.append("\r\033[2K" + "".join(row_items).rstrip())
        return "\n".join(lines)

    def _display_matches_with_status_bar(self, matches: list[str], line_buffer: str) -> None:
        """
        Render completion candidates inside the scrollable output region above the pinned
        4-row bottom dock, then restore the prompt, current line buffer, and cursor position.
        """
        color = _use_color()
        geom = _get_dock_geometry()
        width = geom[0]
        divider = format_divider_line(width, color=color)
        status_line = format_status_bar(self.cli_obj, color=color, max_width=width)
        grid = self._format_completion_columns(matches, width)
        # Strip readline prompt ignore markers (\x01 / \x02) when writing directly to stdout
        prompt_str = format_prompt(self.cli_obj, color=color).replace("\x01", "").replace("\x02", "")
        endidx = (
            _readline.get_endidx()
            if _readline is not None and hasattr(_readline, "get_endidx")
            else len(line_buffer)
        )

        disp_cmd, shift = _format_input_viewport(prompt_str, line_buffer, endidx, width - 1)
        # Print the current prompt line and completion grid at scroll_bottom (so they scroll
        # upward in the scrollable region 1..scroll_bottom), then redraw the pinned 4-row dock
        # at rows (H-3)..H and restore the active prompt + cursor offset on prompt_row (H-2).
        sys.stdout.write(
            f"\033[1;{geom[1]}r"
            f"\033[{geom[1]};1H\r\033[2K{prompt_str}{line_buffer}\n{grid}\n\r\033[2K"
            f"\033[{geom[2]};1H\033[2K{divider}"
            f"\033[{geom[4]};1H\033[2K{divider}"
            f"\033[{geom[5]};1H\033[2K{status_line}"
            f"\033[{geom[3]};1H\033[2K{disp_cmd}"
        )
        if shift > 0:
            sys.stdout.write(f"\033[{shift}D")
        sys.stdout.flush()

    def display_matches_hook(
        self, _substitution: str, matches: list[str], _longest_match_length: int
    ) -> None:
        """Readline match-display hook ensuring native match lists never overwrite the status bar."""
        if matches and _supports_dock():
            full_buffer = _readline.get_line_buffer() if _readline is not None else ""
            self._display_matches_with_status_bar(list(matches), full_buffer)

    def _resolve_display_candidates(self, active_buffer: str, text: str) -> list[str]:
        """Return candidates to display on double-Tab, advancing to next-token options if `text` is complete."""
        if self._matches == [text]:
            next_matches = self.get_candidates(active_buffer + " ", "")
            if next_matches:
                return next_matches
        return self._matches

    def complete(self, text: str, state: int) -> Optional[str]:
        """Readline completer callback."""
        if state == 0:
            full_buffer = _readline.get_line_buffer() if _readline is not None else text
            endidx = (
                _readline.get_endidx()
                if _readline is not None and hasattr(_readline, "get_endidx")
                else None
            )
            active_buffer = full_buffer[:endidx] if isinstance(endidx, int) else full_buffer
            self._matches = self.get_candidates(active_buffer, text)
            completion_type = (
                _readline.get_completion_type()
                if _readline is not None and hasattr(_readline, "get_completion_type")
                else 0
            )
            # Detect when the second Tab of a double-Tab immediately follows an automatic
            # common-prefix or trailing-space expansion from the first Tab (e.g. 'domain update'
            # -> 'domain update ' or 'domain update ' -> 'domain update --').
            is_second_tab_after_expand = (
                self._last_prefix_expanded is not None
                and active_buffer == self._last_prefix_expanded
            )
            self._last_prefix_expanded = None

            # When readline requests a completion listing (double-Tab '?', or show-all '!'/'@')
            # or on the second Tab immediately after prefix expansion in an interactive ANSI TTY with dock,
            # render the candidate list (including single-match or next-token candidates) above
            # the redrawn prompt frame and status bar so readline never writes onto the status bar.
            if (
                completion_type in (ord("?"), ord("!"), ord("@")) or is_second_tab_after_expand
            ) and _supports_dock():
                display_list = self._resolve_display_candidates(active_buffer, text)
                if display_list:
                    self._display_matches_with_status_bar(display_list, full_buffer)
                    self._matches = []
                    return None

            # When the token under cursor is already a complete match (e.g. 'domain' or
            # 'domain update') and has next-token completions, append a space on the first Tab
            # and record the expanded prefix so the second Tab lists next-token completions.
            if self._matches == [text] and _supports_dock():
                next_matches = self.get_candidates(active_buffer + " ", "")
                if next_matches:
                    self._matches = [text + " "]
                    self._last_prefix_expanded = active_buffer + " "
            elif len(self._matches) > 1 and _supports_dock():
                common = os.path.commonprefix(self._matches)
                if len(common) > len(text):
                    prefix_len = len(active_buffer) - len(text)
                    self._last_prefix_expanded = active_buffer[:prefix_len] + common
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


def _scrub_last_readline_history_item() -> None:
    """Unconditionally remove the most recent readline history entry."""
    if _readline is None:
        return
    try:
        if hasattr(_readline, "get_current_history_length") and hasattr(_readline, "remove_history_item"):
            length = _readline.get_current_history_length()
            if length > 0:
                _readline.remove_history_item(length - 1)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logging.debug("Could not scrub last readline history item: %s", exc)


def _scrub_sensitive_history(line: str) -> None:
    """Remove the most recent readline history entry if the line contains sensitive credentials."""
    if _is_sensitive_line(line):
        _scrub_last_readline_history_item()


def _configure_readline(completer: ShellCompleter) -> Optional[str]:
    """Configure readline tab auto-completion, prefix history search, and word delimiters."""
    if _readline is None:  # pragma: no cover
        return None
    old_delims = _readline.get_completer_delims()
    _readline.set_completer(completer.complete)
    # Install custom display hook only when the ANSI bottom dock is supported.
    # On plain/dumb terminals, leaving this unset lets readline fall back to its native completion listing.
    if hasattr(_readline, "set_completion_display_matches_hook") and _supports_dock():
        _readline.set_completion_display_matches_hook(completer.display_matches_hook)
    # Remove '-' from completer_delims so options like '--client-transaction-id'
    # and subcommands like 'restore-report' complete as a single token.
    delims = old_delims.replace("-", "")
    _readline.set_completer_delims(delims)
    # Enable horizontal scrolling so input editing stays strictly on the prompt row
    # and does not wrap over the bottom divider or status bar when commands exceed screen width.
    try:
        _readline.parse_and_bind("set horizontal-scroll-mode on")
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logging.debug("Could not enable horizontal-scroll-mode in readline: %s", exc)
    doc = getattr(_readline, "__doc__", "") or ""
    if "libedit" in doc:
        _readline.parse_and_bind("bind ^I rl_complete")
        # macOS / BSD libedit: bind Up and Down arrow keys (symbolic -k and escape sequences)
        # to prefix history search (ed-search-prev-history / ed-search-next-history).
        _readline.parse_and_bind("bind -k up ed-search-prev-history")
        _readline.parse_and_bind("bind -k down ed-search-next-history")
        _readline.parse_and_bind("bind ^[[A ed-search-prev-history")
        _readline.parse_and_bind("bind ^[[B ed-search-next-history")
        _readline.parse_and_bind("bind ^[OA ed-search-prev-history")
        _readline.parse_and_bind("bind ^[OB ed-search-next-history")
    else:
        _readline.parse_and_bind("tab: complete")
        # GNU Readline: bind Up and Down arrow keys (standard ANSI and application cursor sequences)
        # to prefix history search (history-search-backward / history-search-forward).
        # When text is already typed (e.g. 'domain update'), pressing Up filters history entries
        # matching that prefix; on an empty line, it steps sequentially through all history.
        _readline.parse_and_bind('"\\e[A": history-search-backward')
        _readline.parse_and_bind('"\\e[B": history-search-forward')
        _readline.parse_and_bind('"\\eOA": history-search-backward')
        _readline.parse_and_bind('"\\eOB": history-search-forward')
    return old_delims


def _cleanup_readline(old_delims: Optional[str] = None) -> None:
    """Release readline completer references, restore delimiters, and clear session history."""
    if _readline is None:  # pragma: no cover
        return
    try:
        _readline.set_completer(None)
        if hasattr(_readline, "set_completion_display_matches_hook"):
            _readline.set_completion_display_matches_hook(None)
        if old_delims is not None:
            _readline.set_completer_delims(old_delims)
        doc = getattr(_readline, "__doc__", "") or ""
        if "libedit" in doc:
            _readline.parse_and_bind("bind -k up ed-prev-history")
            _readline.parse_and_bind("bind -k down ed-next-history")
            _readline.parse_and_bind("bind ^[[A ed-prev-history")
            _readline.parse_and_bind("bind ^[[B ed-next-history")
            _readline.parse_and_bind("bind ^[OA ed-prev-history")
            _readline.parse_and_bind("bind ^[OB ed-next-history")
        else:
            _readline.parse_and_bind('"\\e[A": previous-history')
            _readline.parse_and_bind('"\\e[B": next-history')
            _readline.parse_and_bind('"\\eOA": previous-history')
            _readline.parse_and_bind('"\\eOB": next-history')
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

    _enter_bottom_dock()
    utils.PRE_ECHO_HOOK = _flush_pending_command
    log_filter = _ShellLoggingFilter()
    logging.getLogger().addFilter(log_filter)
    for handler in logging.getLogger().handlers:
        handler.addFilter(log_filter)
    try:
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
                    prefix = "" if _supports_dock() else "\n"
                    msg = f"{prefix}Interrupted. Type 'exit' or press Ctrl+D to quit."
                    utils.echo(click.style(msg, fg="yellow"))
                    continue
                except EOFError:
                    prefix = "" if _supports_dock() else "\n"
                    utils.echo(click.style(f"{prefix}Exiting shell...", fg="cyan"))
                    break

                if not execute_shell_line(cli_obj, line):
                    utils.echo(click.style("Exiting shell...", fg="cyan"))
                    break
        finally:
            _save_persistent_history(cli_obj)
            _cleanup_readline(old_delims)
            _safe_close_session(cli_obj)
    finally:
        logging.getLogger().removeFilter(log_filter)
        for handler in logging.getLogger().handlers:
            handler.removeFilter(log_filter)
        utils.PRE_ECHO_HOOK = None
        _flush_pending_command.pending_command = None
        _exit_bottom_dock()
