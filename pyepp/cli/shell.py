"""
Interactive CLI Shell / REPL session module for PyEPP.

Provides a persistent EPP session (`pyepp shell`) with ASCII startup banner,
readline tab auto-completion, command history, and mid-session profile switching.
"""

import logging
import shlex
from typing import Optional

import click

from pyepp import __version__, EppCommunicator, EppCommunicatorException
from pyepp.cli import utils
from pyepp.cli.contact import contact_group
from pyepp.cli.domain import domain_group
from pyepp.cli.host import host_group
from pyepp.cli.poll import poll_group
from pyepp.cli.profile import profile_group
from pyepp.profiles import (
    list_profiles,
    load_profile,
    ProfileNotFoundError,
)

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
    "use",
    "set",
    "status",
    "reconnect",
    "clear",
    "help",
    "exit",
    "quit",
)

SET_KEYS = ("output-format", "pretty", "dry-run")

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
  status                           Display current session and connection status
  reconnect                        Reconnect and re-authenticate the active session
  clear                            Clear the terminal screen
  help [command]                   Show this help or command-specific help (e.g. 'help domain check')
  exit / quit                      Log out and exit the interactive shell
""".strip()


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
        utils.echo(
            f"Dry-run mode active (profile: {cli_obj.profile_name or 'default'})."
        )
        return True

    if not getattr(cli_obj.epp, "_server", None) or not cli_obj.user or not cli_obj.password:
        # Ensure _logged_in and _ssl_socket are reset so disconnected sessions never
        # report is_logged_in=True (e.g. after transitioning out of dry-run mode).
        _safe_close_session(cli_obj)
        utils.echo(
            "No complete credentials configured. Use 'use <profile>' to connect to a profile.",
            err=True,
        )
        return False

    connected = False
    try:
        cli_obj.connect()
        connected = True
        cli_obj.login()
        server = getattr(cli_obj.epp, "_server", "unknown")
        port = getattr(cli_obj.epp, "_port", "700")
        utils.echo(f"Connected and logged in as {cli_obj.user}@{server}:{port}")
        return True
    except BaseException as exc:
        if connected:
            try:
                cli_obj.disconnect()
            except Exception as disc_exc:  # pylint: disable=broad-exception-caught
                logging.debug("Disconnect failed after login error: %s", disc_exc)
        if isinstance(exc, Exception):
            utils.echo(f"Error connecting to EPP server: {exc}", err=True)
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
        utils.echo(f"Error: {exc}", err=True)
        return False
    except Exception as exc:  # pylint: disable=broad-exception-caught
        utils.echo(f"Error loading profile '{profile_name}': {exc}", err=True)
        return False

    missing = []
    if not prof.server:
        missing.append("server")
    if not prof.port:
        missing.append("port")
    if not prof.user:
        missing.append("user")
    if not prof.password:
        missing.append("password")

    if missing and not prof.dry_run:
        utils.echo(
            f"Error: Profile '{prof.name}' is missing required setting(s): {', '.join(missing)}.",
            err=True,
        )
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
    )
    cli_obj.user = prof.user
    cli_obj.password = prof.password
    cli_obj.extensions = tuple(prof.extensions) if prof.extensions else None
    cli_obj.output_format = fmt
    cli_obj.no_pretty = bool(prof.no_pretty)
    cli_obj.dry_run = bool(prof.dry_run)
    cli_obj.profile_name = prof.name
    cli_obj.registry_object = None
    cli_obj.persistent_session = True

    utils.echo(f"Switched to profile '{prof.name}'.")
    return _connect_and_login(cli_obj)


def format_prompt(cli_obj) -> str:
    """Build dynamic prompt showing current profile, user, server, and connection state."""
    prof_label = cli_obj.profile_name or "default"
    server = getattr(cli_obj.epp, "_server", None) or "unconnected"
    user = cli_obj.user or "anonymous"

    if cli_obj.dry_run:
        state = f"{prof_label}:dry-run"
    elif getattr(cli_obj.epp, "is_logged_in", False):
        state = prof_label
    else:
        state = f"{prof_label}:disconnected"

    return f"pyepp [{state}] ({user}@{server})> "


def _print_status(cli_obj) -> None:
    """Display current session and connection parameters."""
    server = getattr(cli_obj.epp, "_server", None) or "None"
    port = getattr(cli_obj.epp, "_port", None) or "None"
    connected = getattr(cli_obj.epp, "is_connected", False)
    logged_in = getattr(cli_obj.epp, "is_logged_in", False)
    exts = ", ".join(cli_obj.extensions) if cli_obj.extensions else "None"
    lines = [
        f"Profile:       {cli_obj.profile_name or 'default'}",
        f"Server:        {server}:{port}",
        f"User:          {cli_obj.user or 'None'}",
        f"Connected:     {connected}",
        f"Logged In:     {logged_in}",
        f"Extensions:    {exts}",
        f"Output Format: {cli_obj.output_format}",
        f"Pretty Print:  {not cli_obj.no_pretty}",
        f"Dry Run:       {cli_obj.dry_run}",
    ]
    utils.echo("\n".join(lines))


def _handle_set_command(cli_obj, args: list[str]) -> None:
    """Handle 'set <key> <value>' shell command to modify session settings on the fly."""
    if len(args) != 2:
        utils.echo(
            "Usage: set <output-format|pretty|dry-run> <value>",
            err=True,
        )
        return

    key, val = args[0].lower(), args[1].strip()
    if key in ("output-format", "output_format", "format"):
        fmt = val.upper()
        if fmt not in VALID_OUTPUT_FORMATS:
            allowed = ", ".join(VALID_OUTPUT_FORMATS)
            utils.echo(f"Invalid output format '{val}'. Choose from: {allowed}", err=True)
            return
        cli_obj.output_format = fmt
        utils.echo(f"Output format set to {fmt}.")
    elif key == "pretty":
        if val.lower() in ("on", "true", "1", "yes"):
            cli_obj.no_pretty = False
            utils.echo("Pretty output enabled.")
        elif val.lower() in ("off", "false", "0", "no"):
            cli_obj.no_pretty = True
            utils.echo("Pretty output disabled.")
        else:
            utils.echo("Usage: set pretty <on|off>", err=True)
    elif key in ("dry-run", "dry_run"):
        if val.lower() in ("on", "true", "1", "yes"):
            _safe_close_session(cli_obj)
            cli_obj.dry_run = True
            cli_obj.epp._dry_run = True  # pylint: disable=protected-access
            utils.echo("Dry-run mode enabled.")
        elif val.lower() in ("off", "false", "0", "no"):
            _safe_close_session(cli_obj)
            cli_obj.dry_run = False
            cli_obj.epp._dry_run = False  # pylint: disable=protected-access
            utils.echo("Dry-run mode disabled.")
            _connect_and_login(cli_obj)
        else:
            utils.echo("Usage: set dry-run <on|off>", err=True)
    else:
        utils.echo(
            f"Unknown setting '{key}'. Available settings: {', '.join(SET_KEYS)}",
            err=True,
        )


def _dispatch_click_command(cli_obj, tokens: list[str]) -> None:
    """Invoke a registered Click command or group within the persistent shell session."""
    cmd_groups = _get_command_groups()
    cmd_name = tokens[0].lower()
    sub_args = tokens[1:]

    # Intercept 'profile use <name>' so it mutates the active shell session
    if cmd_name == "profile" and sub_args and sub_args[0].lower() == "use":
        if len(sub_args) != 2:
            utils.echo("Usage: profile use <profile_name>", err=True)
            return
        switch_profile(cli_obj, sub_args[1])
        return

    cmd_obj = cmd_groups.get(cmd_name)
    if cmd_obj is None:
        utils.echo(
            f"Unknown command '{tokens[0]}'. Type 'help' for available commands.",
            err=True,
        )
        return

    try:
        cmd_obj.main(
            args=sub_args,
            prog_name=cmd_name,
            obj=cli_obj,
            standalone_mode=False,
        )
    except click.ClickException as exc:
        exc.show()
    except click.Abort:
        utils.echo("Aborted!", err=True)
    except EppCommunicatorException as exc:
        utils.echo(f"EPP Error: {exc}", err=True)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        utils.echo(f"Error: {exc}", err=True)


def _handle_builtin_command(cli_obj, cmd: str, args: list[str]) -> None:
    """Execute a built-in shell control command."""
    if cmd == "help":
        if not args:
            utils.echo(HELP_TEXT)
        else:
            _dispatch_click_command(cli_obj, args + ["--help"])
    elif cmd == "clear":
        click.clear()
    elif cmd == "status":
        _print_status(cli_obj)
    elif cmd == "reconnect":
        _safe_close_session(cli_obj)
        _connect_and_login(cli_obj)
    elif cmd == "use":
        if len(args) != 1:
            utils.echo("Usage: use <profile_name>", err=True)
        else:
            switch_profile(cli_obj, args[0])
    elif cmd == "set":
        _handle_set_command(cli_obj, args)


def execute_shell_line(cli_obj, line: str) -> bool:
    """
    Parse and execute a single command line in the interactive shell.

    :return: True to continue the REPL loop, False if the user requested exit.
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return True

    try:
        tokens = shlex.split(stripped)
    except ValueError as exc:
        utils.echo(f"Parse error: {exc}", err=True)
        return True

    if not tokens:
        return True

    cmd = tokens[0].lower()
    if cmd in ("exit", "quit"):
        return False

    if cmd in SHELL_BUILTIN_COMMANDS:
        try:
            _handle_builtin_command(cli_obj, cmd, tokens[1:])
        except Exception as exc:  # pylint: disable=broad-exception-caught
            utils.echo(f"Error: {exc}", err=True)
    else:
        _dispatch_click_command(cli_obj, tokens)

    # Scrub commands containing --password from readline history to prevent
    # auth-info secrets from lingering in history buffers.
    _scrub_sensitive_history(stripped)
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
            candidates = [
                p for p in self._get_profile_names() if p.lower().startswith(text.lower())
            ]
        elif first == "set":
            candidates = [k for k in SET_KEYS if k.startswith(text.lower())]
        elif first == "help":
            candidates = [c for c in sorted(cmd_groups.keys()) if c.startswith(text.lower())]
        elif first == "profile":
            sub_names = sorted(list(profile_group.commands.keys()) + ["use"])
            candidates = [s for s in sub_names if s.startswith(text.lower())]
        elif first in cmd_groups:
            grp = cmd_groups[first]
            if isinstance(grp, click.Group):
                candidates = [
                    s for s in sorted(grp.commands.keys()) if s.startswith(text.lower())
                ]
            else:
                candidates = [
                    o for o in self._extract_command_options(grp) if o.startswith(text)
                ]
        return candidates

    def _complete_subsequent_tokens(
        self,
        tokens: list[str],
        text: str,
        cmd_groups: dict[str, click.Command],
    ) -> list[str]:
        """Return completion candidates when completing the third or later token."""
        first = tokens[0].lower()
        second = tokens[1].lower()
        candidates: list[str] = []

        if first == "set" and len(tokens) == 2:
            if second == "output-format":
                candidates = [
                    f for f in VALID_OUTPUT_FORMATS if f.startswith(text.upper())
                ]
            elif second in ("pretty", "dry-run"):
                candidates = [v for v in ("on", "off") if v.startswith(text.lower())]
        elif first == "profile" and second in ("use", "show") and len(tokens) == 2:
            sub_cmd = profile_group.commands.get(second)
            if text.startswith("-") and sub_cmd:
                candidates = [
                    o
                    for o in self._extract_command_options(sub_cmd)
                    if o.startswith(text)
                ]
            else:
                candidates = [
                    p for p in self._get_profile_names() if p.lower().startswith(text.lower())
                ]
        elif first == "help" and len(tokens) == 2 and second in cmd_groups:
            grp = cmd_groups[second]
            if isinstance(grp, click.Group):
                candidates = [
                    s
                    for s in sorted(grp.commands.keys())
                    if s.startswith(text.lower())
                ]
        elif first in cmd_groups:
            grp = cmd_groups[first]
            target_cmd = (
                grp.commands.get(second) if isinstance(grp, click.Group) else grp
            )
            if target_cmd:
                candidates = [
                    o
                    for o in self._extract_command_options(target_cmd)
                    if o.startswith(text)
                ]

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
            line_buffer = (
                _readline.get_line_buffer() if _readline is not None else text
            )
            self._matches = self.get_candidates(line_buffer, text)
        if state < len(self._matches):
            return self._matches[state]
        return None


def _scrub_sensitive_history(line: str) -> None:
    """Remove the most recent readline history entry if the line contains a password flag."""
    if _readline is None or "--password" not in line.lower():
        return
    try:
        if hasattr(_readline, "get_current_history_length") and hasattr(
            _readline, "remove_history_item"
        ):
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

    utils.echo(ASCII_BANNER.strip("\n"))
    utils.echo(
        f"Interactive EPP Shell (v{__version__}) - Type 'help' for commands, 'exit' to quit.\n"
    )

    completer = ShellCompleter(cli_obj)
    old_delims = _configure_readline(completer)

    try:
        _connect_and_login(cli_obj)
        while True:
            try:
                line = input(format_prompt(cli_obj))
            except KeyboardInterrupt:
                utils.echo("\nInterrupted. Type 'exit' or press Ctrl+D to quit.")
                continue
            except EOFError:
                utils.echo("\nExiting shell...")
                break

            if not execute_shell_line(cli_obj, line):
                utils.echo("Exiting shell...")
                break
    finally:
        _cleanup_readline(old_delims)
        _safe_close_session(cli_obj)
