"""
CLI Interactive Shell unit tests.
"""

import logging
import os
import stat
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import click
from click.testing import CliRunner

from pyepp import EppResultData, EppCommunicatorException
from pyepp.poll import ServiceMessageQueueData
from pyepp.cli.__main__ import pyepp_cli, load_config
from pyepp.cli.cli import PyEppCli
from pyepp.cli.shell import (
    ASCII_BANNER,
    ShellCompleter,
    execute_shell_line,
    format_divider_line,
    format_prompt,
    format_status_bar,
    get_default_history_path,
    switch_profile,
    _cleanup_unexpected_arg_history,
    _configure_readline,
    _exit_bottom_dock,
    _format_input_viewport,
    _format_last_result,
    _has_positional_or_extra_credentials,
    _is_sensitive_line,
    _load_persistent_history,
    _read_line_with_status_bar,
    _safe_close_session,
    _save_persistent_history,
    _scrub_last_readline_history_item,
    _supports_dock,
)


class CliShellTest(unittest.TestCase):
    """Test suite for interactive shell (USE-3), auto-completion, and mid-session profile switching."""

    def setUp(self) -> None:
        self.runner = CliRunner()
        self.ini_content = """[default]
port = 700
output_format = TABLE
no_pretty = false
dry_run = false

[profile ote]
server = epp.ote.registry.net.nz
user = ote_user
password = ote_secret_password
extensions = urn:ietf:params:xml:ns:secDNS-1.1

[profile prod]
server = epp.registry.net.nz
port = 701
user = prod_user
password = prod_secret_password
output_format = XML
no_pretty = true
timeout = 25.0

[profile incomplete]
server = epp.incomplete.net.nz
"""
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            tf.write(self.ini_content)
            self.cfg_path = tf.name
        self.tmp_history_dir = tempfile.mkdtemp()
        self.history_path = os.path.join(self.tmp_history_dir, "history")
        self._old_hist_env = os.environ.get("PYEPP_HISTORY_FILE")
        os.environ["PYEPP_HISTORY_FILE"] = self.history_path

    def tearDown(self) -> None:
        if os.path.exists(self.cfg_path):
            os.remove(self.cfg_path)
        if os.path.exists(self.history_path):
            os.remove(self.history_path)
        if os.path.exists(self.tmp_history_dir):
            os.rmdir(self.tmp_history_dir)
        if self._old_hist_env is None:
            os.environ.pop("PYEPP_HISTORY_FILE", None)
        else:
            os.environ["PYEPP_HISTORY_FILE"] = self._old_hist_env
        load_config()

    def _create_mock_cli(self, dry_run: bool = False) -> PyEppCli:
        """Create a PyEppCli instance with mocked EppCommunicator methods."""
        cli_obj = PyEppCli(
            server="epp.ote.registry.net.nz",
            port="700",
            client_cert=None,
            client_key=None,
            user="ote_user",
            password="ote_secret_password",
            extensions=("urn:ietf:params:xml:ns:secDNS-1.1",),
            output_format="XML",
            no_pretty=False,
            dry_run=dry_run,
            profile_name="ote",
            config_file=self.cfg_path,
            persistent_session=True,
        )
        cli_obj.epp.connect = MagicMock(return_value=b"<greeting/>")
        cli_obj.epp.login = MagicMock(
            return_value=EppResultData(
                code=1000,
                message="Command completed successfully",
                raw_response="<epp/>",
                result_data=None,
            )
        )
        cli_obj.epp.logout = MagicMock(
            return_value=EppResultData(
                code=1500,
                message="Command completed successfully; ending session",
                raw_response="<epp/>",
                result_data=None,
            )
        )
        cli_obj.epp.disconnect = MagicMock()
        return cli_obj

    def test_shell_startup_banner_and_persistent_session(self) -> None:
        """Verify shell displays ASCII banner, connects/logs in once, runs multiple commands, and logs out on exit."""
        check_result = EppResultData(
            code=1000,
            message="Command completed successfully",
            raw_response="<epp><response><result code='1000'><msg>OK</msg></result></response></epp>",
            result_data={"example.nz": {"avail": True, "reason": None}},
        )

        with patch("pyepp.epp.EppCommunicator.connect") as mock_connect, patch(
            "pyepp.epp.EppCommunicator.login"
        ) as mock_login, patch(
            "pyepp.epp.EppCommunicator.logout"
        ) as mock_logout, patch(
            "pyepp.epp.EppCommunicator.disconnect"
        ) as mock_disconnect, patch(
            "pyepp.epp.EppCommunicator.is_connected",
            new_callable=lambda: property(lambda self: True),
        ), patch(
            "pyepp.epp.EppCommunicator.is_logged_in",
            new_callable=lambda: property(lambda self: True),
        ), patch(
            "pyepp.domain.Domain.check", return_value=check_result
        ) as mock_domain_check, patch(
            "pyepp.contact.Contact.check", return_value=check_result
        ) as mock_contact_check, patch(
            "builtins.input",
            side_effect=[
                "domain check example.nz",
                "contact check c-123",
                "exit",
            ],
        ):
            result = self.runner.invoke(
                pyepp_cli,
                ["-c", self.cfg_path, "-p", "ote", "shell"],
            )

            self.assertEqual(result.exit_code, 0)
            self.assertIn(ASCII_BANNER.strip("\n"), result.output)
            self.assertIn("Interactive EPP Shell", result.output)
            self.assertIn(
                "Connected and logged in as ote_user@epp.ote.registry.net.nz:700",
                result.output,
            )
            self.assertIn("Exiting shell...", result.output)

            # Connect and login called only once for the entire session, not per command
            mock_connect.assert_called_once()
            mock_login.assert_called_once()
            mock_domain_check.assert_called_once_with(["example.nz"], None)
            mock_contact_check.assert_called_once_with(["c-123"], None)
            mock_logout.assert_called_once()
            mock_disconnect.assert_called()

    def test_shell_all_subcommands_dispatch(self) -> None:
        """Verify domain, contact, host, poll, profile, hello, and run commands work inside the shell."""
        cli_obj = self._create_mock_cli(dry_run=True)
        mock_res = EppResultData(
            code=1000,
            message="OK",
            raw_response="<epp><response><result code='1000'><msg>OK</msg></result></response></epp>",
            result_data={"item": {"avail": True, "reason": None}},
            dry_run=True,
        )

        with patch("pyepp.domain.Domain.info", return_value=mock_res) as m_dom_info, patch(
            "pyepp.contact.Contact.info", return_value=mock_res
        ) as m_con_info, patch(
            "pyepp.host.Host.info", return_value=mock_res
        ) as m_host_info, patch(
            "pyepp.poll.Poll.request", return_value=mock_res
        ) as m_poll_req, patch.object(
            cli_obj.epp, "hello", return_value=b"<greeting/>"
        ) as m_hello:
            self.assertTrue(execute_shell_line(cli_obj, "domain info example.nz"))
            m_dom_info.assert_called_once_with("example.nz", None)

            self.assertTrue(execute_shell_line(cli_obj, "contact info handle-1"))
            m_con_info.assert_called_once_with("handle-1", None)

            self.assertTrue(execute_shell_line(cli_obj, "host info ns1.example.nz"))
            m_host_info.assert_called_once_with("ns1.example.nz", None)

            self.assertTrue(execute_shell_line(cli_obj, "poll request"))
            m_poll_req.assert_called_once_with(client_transaction_id=None)

            self.assertTrue(execute_shell_line(cli_obj, "hello"))
            m_hello.assert_called_once()

            self.assertTrue(execute_shell_line(cli_obj, "profile list"))
            self.assertTrue(execute_shell_line(cli_obj, "profile show ote"))

        # Test 'run <xml>' command inside shell
        with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False) as xml_tf:
            xml_tf.write("<epp><hello/></epp>")
            xml_path = xml_tf.name

        try:
            with patch.object(cli_obj.epp, "execute", return_value=mock_res) as m_exec:
                self.assertTrue(execute_shell_line(cli_obj, f"run {xml_path}"))
                m_exec.assert_called_once_with("<epp><hello/></epp>")
        finally:
            if os.path.exists(xml_path):
                os.remove(xml_path)

    def test_shell_mid_session_profile_switch_via_use_and_profile_use(self) -> None:
        """Verify switching profile mid-session logs out old session and logs into new profile."""
        cli_obj = self._create_mock_cli(dry_run=False)
        cli_obj.epp._logged_in = True
        cli_obj.epp._ssl_socket = MagicMock()

        old_epp = cli_obj.epp

        with patch("pyepp.epp.EppCommunicator.connect") as new_connect, patch(
            "pyepp.epp.EppCommunicator.login"
        ) as new_login:
            # 1. Switch using 'use prod'
            self.assertTrue(execute_shell_line(cli_obj, "use prod"))

            # Old session logged out and disconnected
            old_epp.logout.assert_called_once()
            old_epp.disconnect.assert_called()

            # New communicator configured with 'prod' profile settings
            self.assertEqual(cli_obj.profile_name, "prod")
            self.assertEqual(cli_obj.user, "prod_user")
            self.assertEqual(cli_obj.password, "prod_secret_password")
            self.assertEqual(cli_obj.epp._server, "epp.registry.net.nz")
            self.assertEqual(cli_obj.epp._port, "701")
            self.assertEqual(cli_obj.epp.timeout, 25.0)
            self.assertEqual(cli_obj.output_format, "XML")
            self.assertTrue(cli_obj.no_pretty)
            new_connect.assert_called_once()
            new_login.assert_called_once_with(
                "prod_user", "prod_secret_password", extensions=None
            )

        # 2. Switch back using 'profile use ote'
        with patch("pyepp.epp.EppCommunicator.connect") as ote_connect, patch(
            "pyepp.epp.EppCommunicator.login"
        ) as ote_login:
            self.assertTrue(execute_shell_line(cli_obj, "profile use ote"))
            self.assertEqual(cli_obj.profile_name, "ote")
            self.assertEqual(cli_obj.user, "ote_user")
            self.assertEqual(cli_obj.epp._server, "epp.ote.registry.net.nz")
            self.assertEqual(cli_obj.output_format, "TABLE")
            self.assertFalse(cli_obj.no_pretty)
            ote_connect.assert_called_once()
            ote_login.assert_called_once_with(
                "ote_user",
                "ote_secret_password",
                extensions=("urn:ietf:params:xml:ns:secDNS-1.1",),
            )

    def test_shell_profile_switch_validation_preserves_existing_session(self) -> None:
        """Verify switching to a non-existent or incomplete profile preserves the active session."""
        cli_obj = self._create_mock_cli(dry_run=False)
        cli_obj.epp._logged_in = True
        cli_obj.epp._ssl_socket = MagicMock()

        # Non-existent profile
        self.assertFalse(switch_profile(cli_obj, "non_existent_profile"))
        cli_obj.epp.logout.assert_not_called()
        self.assertEqual(cli_obj.profile_name, "ote")

        # Incomplete profile (missing user/password)
        self.assertFalse(switch_profile(cli_obj, "incomplete"))
        cli_obj.epp.logout.assert_not_called()
        self.assertEqual(cli_obj.profile_name, "ote")

    def test_switch_profile_forwards_configured_timeout(self) -> None:
        """Verify switch_profile instantiates new EppCommunicator with profile's configured timeout."""
        cli_obj = self._create_mock_cli(dry_run=False)
        cli_obj.epp._logged_in = True
        cli_obj.epp._ssl_socket = MagicMock()

        with patch("pyepp.epp.EppCommunicator.connect"), patch("pyepp.epp.EppCommunicator.login"):
            self.assertTrue(switch_profile(cli_obj, "prod"))
            self.assertEqual(cli_obj.epp.timeout, 25.0)

    def test_shell_tab_autocompletion(self) -> None:
        """Verify ShellCompleter provides completions for commands, subcommands, profiles, and flags."""
        cli_obj = self._create_mock_cli(dry_run=True)
        completer = ShellCompleter(cli_obj)

        # Top-level command completion
        top_dom = completer.get_candidates("dom", "dom")
        self.assertEqual(top_dom, ["domain"])

        top_all = completer.get_candidates("", "")
        for expected in (
            "domain",
            "contact",
            "host",
            "poll",
            "profile",
            "hello",
            "run",
            "use",
            "set",
            "status",
            "exit",
        ):
            self.assertIn(expected, top_all)

        # Subcommand completion for domain, contact, host, poll, profile
        dom_subs = completer.get_candidates("domain ", "")
        self.assertIn("check", dom_subs)
        self.assertIn("create", dom_subs)
        self.assertIn("restore-report", dom_subs)

        dom_re = completer.get_candidates("domain re", "re")
        self.assertEqual(dom_re, ["renew", "restore", "restore-report"])

        prof_subs = completer.get_candidates("profile ", "")
        self.assertEqual(prof_subs, ["list", "show", "use"])

        # Profile name completion for 'use <TAB>', 'profile use <TAB>', and 'profile show <TAB>'
        use_profs = completer.get_candidates("use ", "")
        self.assertIn("ote", use_profs)
        self.assertIn("prod", use_profs)

        prof_use_profs = completer.get_candidates("profile use p", "p")
        self.assertEqual(prof_use_profs, ["prod"])

        prof_show_opts = completer.get_candidates("profile show --", "--")
        self.assertIn("--show-secrets", prof_show_opts)

        # Option flag completion on subcommands
        dom_create_opts = completer.get_candidates("domain create example.nz --", "--")
        self.assertIn("--registrant", dom_create_opts)
        self.assertIn("--ns-host", dom_create_opts)
        self.assertIn("--period", dom_create_opts)

        hello_opts = completer.get_candidates("hello --", "--")
        self.assertEqual(hello_opts, ["--help"])

        # Built-in 'set' and 'unset' completions
        set_keys = completer.get_candidates("set ", "")
        self.assertEqual(list(set_keys), ["output-format", "pretty", "dry-run", "debug"])

        set_fmt = completer.get_candidates("set output-format T", "T")
        self.assertEqual(set_fmt, ["TABLE"])

        set_pretty = completer.get_candidates("set pretty ", "")
        self.assertEqual(set_pretty, ["on", "off"])

        set_debug = completer.get_candidates("set debug ", "")
        self.assertEqual(set_debug, ["on", "off"])

        unset_keys = completer.get_candidates("unset ", "")
        self.assertEqual(unset_keys, ["debug", "dry-run", "pretty"])

        # Built-in 'help' completions
        help_cmds = completer.get_candidates("help c", "c")
        self.assertEqual(help_cmds, ["contact"])

        help_sub = completer.get_candidates("help contact ", "")
        self.assertIn("create", help_sub)

        # Readline complete(text, state) protocol
        with patch("pyepp.cli.shell._readline") as mock_rl:
            mock_rl.get_line_buffer.return_value = "domain ch"
            self.assertEqual(completer.complete("ch", 0), "check")
            self.assertIsNone(completer.complete("ch", 1))

    def test_shell_builtins_and_settings(self) -> None:
        """Verify built-in commands (status, set, help, reconnect, clear, comments, empty lines)."""
        root_logger = logging.getLogger()
        self.addCleanup(root_logger.setLevel, root_logger.level)
        cli_obj = self._create_mock_cli(dry_run=True)

        # Empty line and comment
        self.assertTrue(execute_shell_line(cli_obj, "   "))
        self.assertTrue(execute_shell_line(cli_obj, "# comment line"))

        # Unbalanced quotes parse error handled gracefully
        self.assertTrue(execute_shell_line(cli_obj, 'domain check "unclosed'))

        # Unknown command
        self.assertTrue(execute_shell_line(cli_obj, "unknowncmd"))

        # Status and help
        self.assertTrue(execute_shell_line(cli_obj, "status"))
        self.assertTrue(execute_shell_line(cli_obj, "help"))
        self.assertTrue(execute_shell_line(cli_obj, "help domain check"))

        # Set output-format, pretty, dry-run
        self.assertTrue(execute_shell_line(cli_obj, "set output-format TABLE"))
        self.assertEqual(cli_obj.output_format, "TABLE")

        self.assertTrue(execute_shell_line(cli_obj, "set output-format INVALID"))
        self.assertEqual(cli_obj.output_format, "TABLE")

        self.assertTrue(execute_shell_line(cli_obj, "set pretty off"))
        self.assertTrue(cli_obj.no_pretty)
        self.assertTrue(execute_shell_line(cli_obj, "set pretty on"))
        self.assertFalse(cli_obj.no_pretty)
        self.assertTrue(execute_shell_line(cli_obj, "set pretty invalid"))

        self.assertTrue(execute_shell_line(cli_obj, "set dry-run off"))
        self.assertFalse(cli_obj.dry_run)
        self.assertTrue(execute_shell_line(cli_obj, "set dry-run on"))
        self.assertTrue(cli_obj.dry_run)
        self.assertTrue(execute_shell_line(cli_obj, "set dry-run invalid"))

        self.assertTrue(execute_shell_line(cli_obj, "set unknown_key val"))
        self.assertTrue(execute_shell_line(cli_obj, "set only_one_arg"))

        # Set and unset debug mode
        self.assertTrue(execute_shell_line(cli_obj, "set debug on"))
        self.assertTrue(cli_obj.debug)
        self.assertEqual(logging.getLogger().level, logging.DEBUG)

        self.assertTrue(execute_shell_line(cli_obj, "set debug off"))
        self.assertFalse(cli_obj.debug)
        self.assertEqual(logging.getLogger().level, logging.ERROR)

        self.assertTrue(execute_shell_line(cli_obj, "set debug"))
        self.assertTrue(cli_obj.debug)
        self.assertEqual(logging.getLogger().level, logging.DEBUG)

        self.assertTrue(execute_shell_line(cli_obj, "unset debug"))
        self.assertFalse(cli_obj.debug)
        self.assertEqual(logging.getLogger().level, logging.ERROR)

        self.assertTrue(execute_shell_line(cli_obj, "set debug invalid"))
        self.assertTrue(execute_shell_line(cli_obj, "unset"))
        self.assertTrue(execute_shell_line(cli_obj, "unset invalid_key"))
        self.assertTrue(execute_shell_line(cli_obj, "unset dry-run"))
        self.assertFalse(cli_obj.dry_run)

        # Shorthand 1-arg 'set dry-run', 'unset pretty', 'set pretty'
        self.assertTrue(execute_shell_line(cli_obj, "set dry-run"))
        self.assertTrue(cli_obj.dry_run)
        self.assertTrue(execute_shell_line(cli_obj, "unset pretty"))
        self.assertTrue(cli_obj.no_pretty)
        self.assertTrue(execute_shell_line(cli_obj, "set pretty"))
        self.assertFalse(cli_obj.no_pretty)

        # Disabling dry-run when already disabled and logged in preserves active session
        cli_obj.dry_run = False
        cli_obj.epp._logged_in = True
        cli_obj.epp._ssl_socket = MagicMock()
        cli_obj.epp.logout.reset_mock()
        cli_obj.epp.connect.reset_mock()
        self.assertTrue(execute_shell_line(cli_obj, "unset dry-run"))
        cli_obj.epp.logout.assert_not_called()
        cli_obj.epp.connect.assert_not_called()
        cli_obj.dry_run = True

        # Reconnect and clear (clear only clears screen, preserving command history)
        with patch("click.clear") as mock_clear, patch(
            "pyepp.cli.shell._readline"
        ) as mock_rl, patch("pyepp.cli.shell._supports_ansi_tty", return_value=True), patch(
            "pyepp.cli.shell.sys.stdout"
        ) as mock_stdout:
            self.assertTrue(execute_shell_line(cli_obj, "clear"))
            mock_clear.assert_called_once()
            mock_rl.clear_history.assert_not_called()
            clear_writes = "".join(c.args[0] for c in mock_stdout.write.call_args_list)
            self.assertIn("\033[1;20r\033[20;1H", clear_writes)

        self.assertTrue(execute_shell_line(cli_obj, "reconnect"))

        # Quit returns False
        self.assertFalse(execute_shell_line(cli_obj, "quit"))

    def test_shell_prompt_formatting_and_interrupts(self) -> None:
        """Verify concise prompt, bottom status bar formatting, colors, and interrupt handling."""
        cli_obj = self._create_mock_cli(dry_run=True)
        self.assertEqual(format_prompt(cli_obj, color=False), "pyepp> ")
        colored_prompt = format_prompt(cli_obj, color=True)
        self.assertIn("pyepp", colored_prompt)
        self.assertIn("\x01", colored_prompt)
        self.assertIn("\x02", colored_prompt)

        self.assertEqual(
            format_status_bar(cli_obj, color=False),
            " ● dry-run | profile: ote | ote_user@epp.ote.registry.net.nz:700 | format: XML | pretty: on",
        )
        self.assertIn("● dry-run", format_status_bar(cli_obj, color=True))

        cli_obj.dry_run = False
        cli_obj.epp._logged_in = False
        self.assertEqual(
            format_status_bar(cli_obj, color=False),
            " ○ disconnected | profile: ote | ote_user@epp.ote.registry.net.nz:700 | format: XML | pretty: on",
        )
        self.assertIn("○ disconnected", format_status_bar(cli_obj, color=True))

        cli_obj.epp._logged_in = True
        cli_obj.no_pretty = True
        self.assertEqual(
            format_status_bar(cli_obj, color=False),
            " ● connected | profile: ote | ote_user@epp.ote.registry.net.nz:700 | format: XML | pretty: off",
        )
        self.assertIn("● connected", format_status_bar(cli_obj, color=True))
        self.assertIn("pyepp", format_prompt(cli_obj, color=True))

        # Test TTY divider lines and bottom status bar rendering around input()
        self.assertEqual(format_divider_line(10, color=False), "─" * 10)
        self.assertIn("─" * 10, format_divider_line(10, color=True))

        with patch("pyepp.cli.shell.sys.stdout") as mock_stdout, patch.dict(
            os.environ, {"TERM": "xterm-256color"}, clear=False
        ), patch("builtins.input", return_value="status"):
            mock_stdout.isatty.return_value = True
            line = _read_line_with_status_bar(cli_obj)
            self.assertEqual(line, "status")
            writes = "".join(c.args[0] for c in mock_stdout.write.call_args_list)
            self.assertIn("● connected", writes)
            self.assertIn("─", writes)
            self.assertIn("\033[1;20r", writes)
            self.assertIn("\033[22;1H", writes)
            self.assertIn("\033[24;1H\033[2K", writes)
            self.assertIn("status", writes)
            # Pressing Enter keeps the cursor on prompt_row (row 22) without inserting a blank
            # newline into scroll_bottom until _flush_pending_command() runs on output.
            self.assertNotIn("\033[20;1H\r\033[2K", writes)
            from pyepp.cli.shell import _flush_pending_command

            mock_stdout.reset_mock()
            _flush_pending_command()
            flush_writes = "".join(c.args[0] for c in mock_stdout.write.call_args_list)
            self.assertIn("\033[20;1H\r\033[2K", flush_writes)
            self.assertIn("status\n\r\033[2K", flush_writes)

        # Empty input clears the prompt row and anchors cursor at scroll_bottom without echoing command
        with patch("pyepp.cli.shell.sys.stdout") as mock_stdout, patch.dict(
            os.environ, {"TERM": "xterm-256color"}, clear=False
        ), patch("builtins.input", return_value="   "):
            mock_stdout.isatty.return_value = True
            self.assertEqual(_read_line_with_status_bar(cli_obj), "   ")
            writes = "".join(c.args[0] for c in mock_stdout.write.call_args_list)
            self.assertIn("\033[20;1H\r\033[2K", writes)

        # Test TTY status bar cleanup when KeyboardInterrupt occurs during input()
        with patch("pyepp.cli.shell.sys.stdout") as mock_stdout, patch.dict(
            os.environ, {"TERM": "xterm-256color"}, clear=False
        ), patch("builtins.input", side_effect=KeyboardInterrupt()):
            mock_stdout.isatty.return_value = True
            with self.assertRaises(KeyboardInterrupt):
                _read_line_with_status_bar(cli_obj)
            writes = "".join(c.args[0] for c in mock_stdout.write.call_args_list)
            self.assertIn("\033[20;1H\r\033[2K", writes)

        # Test _enter_bottom_dock and _exit_bottom_dock reserve and release the 4-row dock
        from pyepp.cli.shell import _enter_bottom_dock, _exit_bottom_dock

        with patch("pyepp.cli.shell.sys.stdout") as mock_stdout, patch.dict(
            os.environ, {"TERM": "xterm-256color"}, clear=False
        ):
            mock_stdout.isatty.return_value = True
            _enter_bottom_dock()
            _exit_bottom_dock()
            dock_writes = "".join(c.args[0] for c in mock_stdout.write.call_args_list)
            self.assertIn("\033[1;20r\033[20;1H", dock_writes)
            self.assertIn("\033[r", dock_writes)
            self.assertIn("\033[24;1H\033[2K", dock_writes)

        # Test status bar truncation to max_width so narrow terminals never wrap
        truncated_plain = format_status_bar(cli_obj, color=False, max_width=30)
        self.assertEqual(len(truncated_plain), 30)
        self.assertTrue(truncated_plain.endswith("…"))

        import click as _click

        truncated_color = format_status_bar(cli_obj, color=True, max_width=30)
        self.assertEqual(len(_click.unstyle(truncated_color)), 30)
        self.assertTrue(truncated_color.endswith("\x1b[0m"))

        # Test control character / escape sequence sanitization (CWE-150)
        cli_obj.user = "bad\x1b[31m\nuser\r"
        sanitized_bar = format_status_bar(cli_obj, color=False)
        self.assertNotIn("\n", sanitized_bar)
        self.assertNotIn("\r", sanitized_bar)
        self.assertIn("bad[31muser@", sanitized_bar)
        cli_obj.user = "ote_user"

        # Test TERM=dumb disables ANSI status bar cursor movement and NO_COLOR disables colors
        with patch("pyepp.cli.shell.sys.stdout") as mock_stdout, patch.dict(
            os.environ, {"TERM": "dumb"}, clear=False
        ), patch("builtins.input", return_value="exit"):
            mock_stdout.isatty.return_value = True
            self.assertEqual(_read_line_with_status_bar(cli_obj), "exit")
            mock_stdout.write.assert_not_called()

        with patch("pyepp.cli.shell.sys.stdout") as mock_stdout, patch.dict(
            os.environ, {"TERM": "xterm-256color", "NO_COLOR": "1"}, clear=False
        ), patch("builtins.input", return_value="exit") as mock_input:
            mock_stdout.isatty.return_value = True
            self.assertEqual(_read_line_with_status_bar(cli_obj), "exit")
            self.assertEqual(mock_input.call_args[0][0], "pyepp> ")

        # Test KeyboardInterrupt continues loop and EOFError exits cleanly
        with patch("builtins.input", side_effect=[KeyboardInterrupt(), EOFError()]):
            result = self.runner.invoke(
                pyepp_cli,
                ["-c", self.cfg_path, "-p", "ote", "--dry-run", "shell"],
            )
            self.assertEqual(result.exit_code, 0)
            self.assertIn("Interrupted. Type 'exit' or press Ctrl+D to quit.", result.output)
            self.assertIn("Exiting shell...", result.output)

    def test_shell_auto_reconnect_after_poisoned_transport_drop(self) -> None:
        """Verify persistent session automatically reconnects on next command if connection was dropped."""
        cli_obj = self._create_mock_cli(dry_run=False)
        # Simulate disconnected state after a transport failure
        cli_obj.epp._ssl_socket = None
        cli_obj.epp._logged_in = False

        check_result = EppResultData(
            code=1000,
            message="OK",
            raw_response="<epp/>",
            result_data={"example.nz": {"avail": True, "reason": None}},
        )

        with patch("pyepp.domain.Domain.check", return_value=check_result):
            execute_shell_line(cli_obj, "domain check example.nz")
            cli_obj.epp.connect.assert_called_once()
            cli_obj.epp.login.assert_called_once()
            cli_obj.epp.logout.assert_not_called()

    def test_shell_login_failure_disconnects_socket(self) -> None:
        """Verify that if login fails during shell connection, disconnect() is immediately invoked."""
        from pyepp.cli.shell import _connect_and_login

        cli_obj = self._create_mock_cli(dry_run=False)
        cli_obj.epp.login.side_effect = EppCommunicatorException("Auth failed")

        self.assertFalse(_connect_and_login(cli_obj))
        cli_obj.epp.connect.assert_called_once()
        cli_obj.epp.login.assert_called_once()
        cli_obj.epp.disconnect.assert_called_once()

    def test_shell_login_interrupt_disconnects_socket(self) -> None:
        """Verify KeyboardInterrupt during login immediately disconnects the open socket and re-raises."""
        from pyepp.cli.shell import _connect_and_login

        cli_obj = self._create_mock_cli(dry_run=False)
        cli_obj.epp.login.side_effect = KeyboardInterrupt()

        with self.assertRaises(KeyboardInterrupt):
            _connect_and_login(cli_obj)
        cli_obj.epp.connect.assert_called_once()
        cli_obj.epp.disconnect.assert_called_once()

    def test_shell_launches_without_default_profile_and_switches(self) -> None:
        """Verify 'pyepp -c config.ini shell' starts even when no [default] profile exists."""
        config_content = (
            "[ote]\n"
            "server = epp.ote.registry.nz\n"
            "port = 700\n"
            "user = ote-user\n"
            "password = ote-secret\n"
            "dry_run = true\n"
        )
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".ini", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(config_content)
            cfg_path = tmp.name

        try:
            runner = CliRunner()
            result = runner.invoke(
                pyepp_cli,
                ["-c", cfg_path, "shell"],
                input="use ote\nstatus\nexit\n",
                env={
                    "PYEPP_SERVER": "",
                    "PYEPP_PORT": "",
                    "PYEPP_USER": "",
                    "PYEPP_PASSWORD": "",
                },
            )
            self.assertEqual(result.exit_code, 0)
            self.assertIn("Switched to profile 'ote'.", result.output)
            self.assertIn("epp.ote.registry.nz:700", result.output)
        finally:
            os.remove(cfg_path)

    def test_configure_readline_bindings(self) -> None:
        """Verify _configure_readline handles both GNU readline and macOS libedit bindings."""
        cli_obj = self._create_mock_cli(dry_run=True)
        completer = ShellCompleter(cli_obj)

        with patch("pyepp.cli.shell._readline") as mock_rl:
            mock_rl.__doc__ = "Importing this module enables command line editing using libedit readline."
            mock_rl.get_completer_delims.return_value = " \t\n\"\\'`@$><=;|&{(-"
            _configure_readline(completer)
            mock_rl.parse_and_bind.assert_any_call("bind ^I rl_complete")
            mock_rl.parse_and_bind.assert_any_call("bind -k up ed-search-prev-history")
            mock_rl.parse_and_bind.assert_any_call("bind -k down ed-search-next-history")
            mock_rl.parse_and_bind.assert_any_call("bind ^[[A ed-search-prev-history")
            mock_rl.parse_and_bind.assert_any_call("bind ^[[B ed-search-next-history")
            mock_rl.parse_and_bind.assert_any_call("bind ^[OA ed-search-prev-history")
            mock_rl.parse_and_bind.assert_any_call("bind ^[OB ed-search-next-history")
            self.assertNotIn("-", mock_rl.set_completer_delims.call_args[0][0])

            mock_rl.__doc__ = "GNU readline"
            mock_rl.parse_and_bind.reset_mock()
            old_delims = _configure_readline(completer)
            mock_rl.parse_and_bind.assert_any_call("tab: complete")
            mock_rl.parse_and_bind.assert_any_call('"\\e[A": history-search-backward')
            mock_rl.parse_and_bind.assert_any_call('"\\e[B": history-search-forward')
            mock_rl.parse_and_bind.assert_any_call('"\\eOA": history-search-backward')
            mock_rl.parse_and_bind.assert_any_call('"\\eOB": history-search-forward')

            from pyepp.cli.shell import _cleanup_readline

            mock_rl.parse_and_bind.reset_mock()
            _cleanup_readline(old_delims)
            mock_rl.set_completer.assert_called_with(None)
            mock_rl.set_completer_delims.assert_called_with(old_delims)
            mock_rl.parse_and_bind.assert_any_call('"\\e[A": previous-history')
            mock_rl.parse_and_bind.assert_any_call('"\\e[B": next-history')
            mock_rl.parse_and_bind.assert_any_call('"\\eOA": previous-history')
            mock_rl.parse_and_bind.assert_any_call('"\\eOB": next-history')
            mock_rl.clear_history.assert_called_once()

    def test_sensitive_history_scrubbing(self) -> None:
        """Verify commands containing --password are removed from readline history."""
        cli_obj = self._create_mock_cli(dry_run=True)
        with patch("pyepp.cli.shell._readline") as mock_rl:
            mock_rl.get_current_history_length.return_value = 3
            with patch.object(cli_obj, "info", return_value="ok"):
                execute_shell_line(
                    cli_obj, "domain info example.nz --password SecretAuth123"
                )
            mock_rl.remove_history_item.assert_called_once_with(2)

            mock_rl.remove_history_item.reset_mock()
            with patch.object(cli_obj, "check", return_value="ok"):
                execute_shell_line(cli_obj, "domain check example.nz")
            mock_rl.remove_history_item.assert_not_called()

    def test_hello_disconnects_temporary_socket_when_not_logged_in(self) -> None:
        """Verify hello() disconnects temporary socket when session is not authenticated."""
        cli_obj = self._create_mock_cli(dry_run=False)
        cli_obj.epp._ssl_socket = None
        cli_obj.epp._logged_in = False

        with patch.object(cli_obj.epp, "hello", return_value=b"<greeting/>") as m_hello:
            execute_shell_line(cli_obj, "hello")
            m_hello.assert_called_once()
            cli_obj.epp.connect.assert_called_once()
            cli_obj.epp.disconnect.assert_called_once()

        # When already connected and logged in, hello() reuses the socket without disconnecting
        cli_obj.epp.connect.reset_mock()
        cli_obj.epp.disconnect.reset_mock()
        cli_obj.epp._ssl_socket = MagicMock()
        cli_obj.epp._logged_in = True

        with patch.object(cli_obj.epp, "hello", return_value=b"<greeting/>") as m_hello:
            execute_shell_line(cli_obj, "hello")
            m_hello.assert_called_once()
            cli_obj.epp.connect.assert_not_called()
            cli_obj.epp.disconnect.assert_not_called()

    def test_switch_profile_handles_corrupt_config_gracefully(self) -> None:
        """Verify malformed config.ini during switch_profile does not crash shell or drop session."""
        cli_obj = self._create_mock_cli(dry_run=False)
        cli_obj.epp._ssl_socket = MagicMock()
        cli_obj.epp._logged_in = True

        with patch("pyepp.cli.shell.load_profile", side_effect=RuntimeError("Parse error")):
            self.assertFalse(switch_profile(cli_obj, "prod"))
            self.assertTrue(cli_obj.epp.is_logged_in)
            cli_obj.epp.logout.assert_not_called()

    def test_set_dry_run_off_without_credentials_resets_logged_in_state(self) -> None:
        """Verify 'set dry-run off' without credentials resets _logged_in to False."""
        cli_obj = PyEppCli(
            server="epp.ote.registry.net.nz",
            port="700",
            client_cert=None,
            client_key=None,
            user=None,
            password=None,
            extensions=None,
            output_format="XML",
            no_pretty=False,
            dry_run=True,
            persistent_session=True,
        )
        cli_obj.epp._logged_in = True

        execute_shell_line(cli_obj, "set dry-run off")
        self.assertFalse(cli_obj.dry_run)
        self.assertFalse(cli_obj.epp.is_logged_in)

    def test_execute_syncs_cli_credentials_after_raw_login_xml(self) -> None:
        """Verify PyEppCli.execute syncs user/password/extensions when raw login XML succeeds."""
        cli_obj = self._create_mock_cli(dry_run=False)
        cli_obj.epp._ssl_socket = MagicMock()
        cli_obj.epp._logged_in = True

        def fake_execute(_cmd):
            cli_obj.epp._user = "new_xml_user"
            cli_obj.epp._password = "new_xml_password"
            cli_obj.epp._extensions = ["urn:custom:ext"]
            return EppResultData(
                code=1000,
                message="OK",
                raw_response="<epp/>",
                result_data=None,
            )

        with patch.object(cli_obj.epp, "execute", side_effect=fake_execute):
            cli_obj.execute("<epp><command><login/></command></epp>")

        self.assertEqual(cli_obj.user, "new_xml_user")
        self.assertEqual(cli_obj.password, "new_xml_password")
        self.assertEqual(cli_obj.extensions, ("urn:custom:ext",))

    def test_completer_case_insensitive_profile_and_sorted_help(self) -> None:
        """Verify case-insensitive profile completion and sorted help command completion."""
        cli_obj = self._create_mock_cli(dry_run=True)
        completer = ShellCompleter(cli_obj)

        self.assertEqual(completer.get_candidates("use O", "O"), ["ote"])
        self.assertEqual(completer.get_candidates("profile use P", "P"), ["prod"])
        help_cands = completer.get_candidates("help ", "")
        self.assertEqual(help_cands, sorted(help_cands))
        self.assertEqual(completer.get_candidates("? d", "d"), ["domain"])
        self.assertIn("create", completer.get_candidates("? domain ", ""))
        self.assertEqual(completer.get_candidates("last T", "T"), ["TABLE"])
        self.assertEqual(completer.get_candidates("save out.xml X", "X"), ["XML"])
        self.assertEqual(
            completer.get_candidates("domain check example.nz --output-format M", "M"),
            ["MIN"],
        )

    def test_command_latency_and_poll_badge_in_status_bar_and_status(self) -> None:
        """Verify command latency (ms) and poll queue count badge in status bar and 'status' output."""
        cli_obj = self._create_mock_cli(dry_run=True)
        poll_res = EppResultData(
            code=1301,
            message="Command completed successfully; ack to dequeue",
            raw_response="<epp/>",
            result_data=ServiceMessageQueueData(message_count=3, message_id="123"),
            dry_run=False,
        )

        with patch("pyepp.poll.Poll.request", return_value=poll_res):
            self.assertTrue(execute_shell_line(cli_obj, "poll request"))

        self.assertEqual(cli_obj.poll_queue_count, 3)
        self.assertIsNotNone(cli_obj.last_latency_ms)

        bar_plain = format_status_bar(cli_obj, color=False)
        self.assertIn("✉ poll: 3", bar_plain)
        self.assertIn(f"last: {cli_obj.last_latency_ms}ms", bar_plain)

        bar_color = format_status_bar(cli_obj, color=True)
        self.assertIn("✉ poll: ", bar_color)
        self.assertIn("last: ", bar_color)

        # Verify empty queue (code 1300) updates poll_queue_count to 0
        empty_poll_res = EppResultData(
            code=1300,
            message="Command completed successfully; no messages",
            raw_response="<epp/>",
            result_data=None,
            dry_run=False,
        )
        with patch("pyepp.poll.Poll.acknowledge", return_value=empty_poll_res):
            self.assertTrue(execute_shell_line(cli_obj, "poll acknowledge 123"))

        self.assertEqual(cli_obj.poll_queue_count, 0)
        self.assertNotIn("✉ poll:", format_status_bar(cli_obj, color=False))

        # Verify 'status' / 'st' prints Poll Queue and Last Latency
        with patch("pyepp.cli.utils.echo") as mock_echo:
            self.assertTrue(execute_shell_line(cli_obj, "st"))
            status_out = mock_echo.call_args[0][0]
            self.assertIn("Poll Queue:", status_out)
            self.assertIn("Last Latency:", status_out)

    def test_history_command_and_bang_expansion(self) -> None:
        """Verify 'history' / 'hist' built-in and '!!' / '!<N>' / '!<negative>' command expansion."""
        cli_obj = self._create_mock_cli(dry_run=True)

        # Empty history cases
        with patch("pyepp.cli.utils.echo") as mock_echo:
            self.assertTrue(execute_shell_line(cli_obj, "history"))
            self.assertIn("No commands in history.", mock_echo.call_args[0][0])
            self.assertTrue(execute_shell_line(cli_obj, "!!"))
            self.assertIn("No previous command in history.", mock_echo.call_args[0][0])

        check_res = EppResultData(
            code=1000,
            message="OK",
            raw_response="<epp/>",
            result_data={"example.nz": {"avail": True, "reason": None}},
            dry_run=True,
        )
        with patch("pyepp.domain.Domain.check", return_value=check_res) as mock_check:
            self.assertTrue(execute_shell_line(cli_obj, "domain check example.nz"))
            self.assertTrue(execute_shell_line(cli_obj, "set pretty off"))
            # Duplicate consecutive command is deduplicated
            self.assertTrue(execute_shell_line(cli_obj, "set pretty off"))
            self.assertEqual(
                cli_obj.session_history,
                ["domain check example.nz", "set pretty off"],
            )

            # Re-run command #1 via '!1'
            self.assertTrue(execute_shell_line(cli_obj, "!1"))
            self.assertEqual(mock_check.call_count, 2)

            # Re-run last command via '!!' and '!-1'
            self.assertTrue(execute_shell_line(cli_obj, "!!"))
            self.assertEqual(mock_check.call_count, 3)
            self.assertTrue(execute_shell_line(cli_obj, "!-1"))
            self.assertEqual(mock_check.call_count, 4)

        # Inspect history via 'hist 1' and error cases
        with patch("pyepp.cli.utils.echo") as mock_echo:
            self.assertTrue(execute_shell_line(cli_obj, "hist 1"))
            self.assertIn("domain check example.nz", mock_echo.call_args[0][0])

            self.assertTrue(execute_shell_line(cli_obj, "history -5"))
            self.assertIn("Usage: history [positive_count]", mock_echo.call_args[0][0])

            self.assertTrue(execute_shell_line(cli_obj, "history 1 2"))
            self.assertIn("Usage: history [count]", mock_echo.call_args[0][0])

            self.assertTrue(execute_shell_line(cli_obj, "!abc"))
            self.assertIn("Invalid history reference", mock_echo.call_args[0][0])

            self.assertTrue(execute_shell_line(cli_obj, "!999"))
            self.assertIn("History event '!999' not found.", mock_echo.call_args[0][0])

    def test_persistent_history_load_save_and_permissions(self) -> None:
        """Verify persistent history saves with 0600 permissions, scrubs --password, and reloads."""
        cli_obj = self._create_mock_cli(dry_run=True)
        cli_obj.session_history = [
            "domain check example.nz",
            "domain info secret.nz --password MySecretPassword",
            "contact check c-1",
        ]

        _save_persistent_history(cli_obj, self.history_path)
        self.assertTrue(os.path.isfile(self.history_path))
        file_mode = stat.S_IMODE(os.stat(self.history_path).st_mode)
        self.assertEqual(file_mode, 0o600)

        with open(self.history_path, "r", encoding="utf-8") as f_in:
            saved_text = f_in.read()
        self.assertIn("domain check example.nz", saved_text)
        self.assertIn("contact check c-1", saved_text)
        self.assertNotIn("MySecretPassword", saved_text)

        # Load into a fresh PyEppCli instance
        fresh_cli = self._create_mock_cli(dry_run=True)
        with patch("pyepp.cli.shell._readline") as mock_rl:
            _load_persistent_history(fresh_cli, self.history_path)
            self.assertEqual(
                fresh_cli.session_history,
                ["domain check example.nz", "contact check c-1"],
            )
            self.assertEqual(mock_rl.add_history.call_count, 2)

        self.assertEqual(get_default_history_path(), self.history_path)

    def test_last_and_save_commands(self) -> None:
        """Verify 'last [FORMAT]' and 'save <filepath> [FORMAT]' re-render and export last result."""
        cli_obj = self._create_mock_cli(dry_run=True)

        # When no command has executed yet
        with patch("pyepp.cli.utils.echo") as mock_echo:
            self.assertTrue(execute_shell_line(cli_obj, "last"))
            self.assertIn("No command result recorded", mock_echo.call_args[0][0])

        check_res = EppResultData(
            code=1000,
            message="OK",
            raw_response="<epp><response><result code='1000'><msg>OK</msg></result></response></epp>",
            result_data={"example.nz": {"avail": True, "reason": None}},
            dry_run=True,
        )
        with patch("pyepp.domain.Domain.check", return_value=check_res):
            self.assertTrue(execute_shell_line(cli_obj, "domain check example.nz"))

        # Re-display as MIN and TABLE without re-running the EPP command
        with patch("pyepp.cli.utils.echo") as mock_echo:
            self.assertTrue(execute_shell_line(cli_obj, "last MIN"))
            self.assertIn("example.nz", str(mock_echo.call_args[0][0]))
            self.assertEqual(cli_obj.output_format, "XML")

            self.assertTrue(execute_shell_line(cli_obj, "last INVALID"))
            self.assertIn("Invalid output format", mock_echo.call_args[0][0])

            self.assertTrue(execute_shell_line(cli_obj, "last XML EXTRA"))
            self.assertIn("Usage: last", mock_echo.call_args[0][0])

        # Save last result to disk in XML format
        out_file = os.path.join(self.tmp_history_dir, "saved_response.xml")
        try:
            self.assertTrue(execute_shell_line(cli_obj, f"save {out_file} XML"))
            self.assertTrue(os.path.isfile(out_file))
            with open(out_file, "r", encoding="utf-8") as f_in:
                content = f_in.read()
            self.assertIn("<result code=", content)
        finally:
            if os.path.exists(out_file):
                os.remove(out_file)

        with patch("pyepp.cli.utils.echo") as mock_echo:
            self.assertTrue(execute_shell_line(cli_obj, "save"))
            self.assertIn("Usage: save", mock_echo.call_args[0][0])

        # Verify 'q' alias exits shell
        self.assertFalse(execute_shell_line(cli_obj, "q"))

    def test_security_review_hardening(self) -> None:
        """Verify symlink rejection, control-char sanitization, --pass= scrubbing, and comment divider cleanup."""
        cli_obj = self._create_mock_cli(dry_run=True)

        # 1. Unclosed quote with --pass= or --show-secrets still scrubs readline history immediately
        with patch("pyepp.cli.shell._readline") as mock_rl:
            mock_rl.get_current_history_length.return_value = 2
            self.assertTrue(execute_shell_line(cli_obj, 'domain info example.nz --pass="unclosedSecret'))
            mock_rl.remove_history_item.assert_called_once_with(1)

        self.assertTrue(execute_shell_line(cli_obj, "profile show default --show-secrets"))
        self.assertEqual(cli_obj.session_history, [])

        # 2. Symlinked history file is refused on both save and load
        target_file = os.path.join(self.tmp_history_dir, "target.txt")
        symlink_file = os.path.join(self.tmp_history_dir, "symlink_history")
        try:
            with open(target_file, "w", encoding="utf-8") as f_out:
                f_out.write("original\n")
            os.symlink(target_file, symlink_file)

            cli_obj.session_history = ["domain check example.nz"]
            _save_persistent_history(cli_obj, symlink_file)
            with open(target_file, "r", encoding="utf-8") as f_in:
                self.assertEqual(f_in.read(), "original\n")

            fresh_cli = self._create_mock_cli(dry_run=True)
            _load_persistent_history(fresh_cli, symlink_file)
            self.assertEqual(fresh_cli.session_history, [])
        finally:
            if os.path.lexists(symlink_file):
                os.remove(symlink_file)
            if os.path.exists(target_file):
                os.remove(target_file)

        # 3. Control characters in persistent history file are stripped on load
        with open(self.history_path, "w", encoding="utf-8") as f_out:
            f_out.write("domain check \x1b[31mexample.nz\n")
        _load_persistent_history(fresh_cli, self.history_path)
        self.assertEqual(fresh_cli.session_history, ["domain check [31mexample.nz"])

        # 4. Comment lines clear the prompt row and return cursor to scroll_bottom without echoing
        with (
            patch("pyepp.cli.shell._supports_ansi_tty", return_value=True),
            patch("builtins.input", return_value="# just a comment"),
            patch("sys.stdout") as mock_stdout,
        ):
            self.assertEqual(_read_line_with_status_bar(cli_obj), "# just a comment")
            writes = "".join(call.args[0] for call in mock_stdout.write.call_args_list)
            self.assertIn("\033[20;1H\r\033[2K", writes)
            self.assertNotIn("# just a comment", writes)

    def test_debug_mode_lifecycle_and_status_display(self) -> None:
        """Verify setting and unsetting debug mode, status bar indicator, status output, and log levels."""
        cli_obj = self._create_mock_cli(dry_run=True)
        root_logger = logging.getLogger()
        self.addCleanup(root_logger.setLevel, root_logger.level)

        # Initially debug is False and not in status bar
        self.assertFalse(getattr(cli_obj, "debug", False))
        self.assertNotIn("debug: on", format_status_bar(cli_obj, color=False))

        # 'status' output displays Debug: False
        with patch("pyepp.cli.utils.echo") as mock_echo:
            self.assertTrue(execute_shell_line(cli_obj, "status"))
            status_output = mock_echo.call_args[0][0]
            self.assertIn("Debug:", status_output)
            self.assertIn("False", status_output)

        # Enable debug mode via 'set debug on'
        with patch("pyepp.cli.utils.echo") as mock_echo:
            self.assertTrue(execute_shell_line(cli_obj, "set debug on"))
            self.assertIn("Debug mode enabled.", mock_echo.call_args[0][0])
        self.assertTrue(cli_obj.debug)
        self.assertEqual(root_logger.level, logging.DEBUG)

        # Status bar reflects debug mode
        self.assertIn("debug: on", format_status_bar(cli_obj, color=False))
        self.assertIn("debug: on", format_status_bar(cli_obj, color=True))

        # 'status' output displays Debug: True
        with patch("pyepp.cli.utils.echo") as mock_echo:
            self.assertTrue(execute_shell_line(cli_obj, "status"))
            status_output = mock_echo.call_args[0][0]
            self.assertIn("Debug:", status_output)
            self.assertIn("True", status_output)

        # Unset debug mode via 'unset debug'
        with patch("pyepp.cli.utils.echo") as mock_echo:
            self.assertTrue(execute_shell_line(cli_obj, "unset debug"))
            self.assertIn("Debug mode disabled.", mock_echo.call_args[0][0])
        self.assertFalse(cli_obj.debug)
        self.assertEqual(root_logger.level, logging.ERROR)
        self.assertNotIn("debug: on", format_status_bar(cli_obj, color=False))

        # Test shorthand 'set debug' enables debug mode
        with patch("pyepp.cli.utils.echo") as mock_echo:
            self.assertTrue(execute_shell_line(cli_obj, "set debug"))
            self.assertIn("Debug mode enabled.", mock_echo.call_args[0][0])
        self.assertTrue(cli_obj.debug)

        # Test 'set debug off' disables debug mode
        with patch("pyepp.cli.utils.echo") as mock_echo:
            self.assertTrue(execute_shell_line(cli_obj, "set debug off"))
            self.assertIn("Debug mode disabled.", mock_echo.call_args[0][0])
        self.assertFalse(cli_obj.debug)

        # Test boolean string aliases: true, 1, yes
        for on_val in ("true", "1", "yes"):
            self.assertTrue(execute_shell_line(cli_obj, f"set debug {on_val}"))
            self.assertTrue(cli_obj.debug)

        # Test boolean string aliases: false, 0, no
        for off_val in ("false", "0", "no"):
            self.assertTrue(execute_shell_line(cli_obj, f"set debug {off_val}"))
            self.assertFalse(cli_obj.debug)

        # Test verbose restoration: when verbose is True, unsetting debug restores level to INFO
        cli_obj.verbose = True
        self.assertTrue(execute_shell_line(cli_obj, "set debug on"))
        self.assertEqual(root_logger.level, logging.DEBUG)
        self.assertTrue(execute_shell_line(cli_obj, "unset debug"))
        self.assertEqual(root_logger.level, logging.INFO)

        # Test handler initialization when root logger has no handlers
        with patch.object(root_logger, "handlers", []), patch("logging.basicConfig") as mock_basic:
            from pyepp.cli.shell import _set_debug_mode
            _set_debug_mode(cli_obj, True)
            mock_basic.assert_called_once_with(level=logging.DEBUG)

    def test_double_tab_completion_renders_above_status_bar(self) -> None:
        """Verify double-Tab completion (completion_type == ord('?')) renders matches above redrawn status bar."""
        cli_obj = self._create_mock_cli(dry_run=True)
        completer = ShellCompleter(cli_obj)

        with (
            patch("pyepp.cli.shell._readline") as mock_rl,
            patch("pyepp.cli.shell._supports_ansi_tty", return_value=True),
            patch("pyepp.cli.shell._use_color", return_value=True),
            patch("sys.stdout") as mock_stdout,
        ):
            mock_rl.get_line_buffer.return_value = "domain "
            mock_rl.get_completion_type.return_value = ord("?")
            mock_rl.get_endidx.return_value = 7

            # Double-Tab returns None so native readline/libedit does not overwrite the status bar
            self.assertIsNone(completer.complete("", 0))
            writes = "".join(call.args[0] for call in mock_stdout.write.call_args_list)
            # Completion candidates are rendered
            self.assertIn("check", writes)
            self.assertIn("restore-report", writes)
            # Status bar and prompt with current buffer are redrawn without \x01/\x02 markers
            self.assertIn("dry-run", writes)
            self.assertIn("domain ", writes)
            self.assertNotIn("\x01", writes)
            self.assertNotIn("\x02", writes)
            mock_stdout.flush.assert_called()

            # When cursor is in the middle of the buffer (get_endidx < len(line_buffer)),
            # cursor is repositioned backward with \033[<N>D
            mock_stdout.reset_mock()
            mock_rl.get_line_buffer.return_value = "domain  example.nz"
            mock_rl.get_endidx.return_value = 7
            self.assertIsNone(completer.complete("", 0))
            writes_mid = "".join(call.args[0] for call in mock_stdout.write.call_args_list)
            self.assertIn("\033[11D", writes_mid)

            # Typing 'domain update' (no trailing space) + double-Tab:
            # 1st Tab appends trailing space ('update ') and records expanded prefix;
            # 2nd Tab displays 'domain update' option flags cleanly above the status bar.
            mock_stdout.reset_mock()
            mock_rl.get_line_buffer.return_value = "domain update"
            mock_rl.get_endidx.return_value = 13
            mock_rl.get_completion_type.return_value = ord("\t")
            self.assertEqual(completer.complete("update", 0), "update ")
            mock_rl.get_line_buffer.return_value = "domain update "
            mock_rl.get_endidx.return_value = 14
            self.assertIsNone(completer.complete("", 0))
            writes_dom_upd = "".join(call.args[0] for call in mock_stdout.write.call_args_list)
            self.assertIn("--add-admin", writes_dom_upd)
            self.assertIn("--remove-tech", writes_dom_upd)

            # Direct '?' completion on 'domain update' (no trailing space) also resolves
            # next-token options and renders above the status bar.
            mock_stdout.reset_mock()
            mock_rl.get_line_buffer.return_value = "domain update"
            mock_rl.get_endidx.return_value = 13
            mock_rl.get_completion_type.return_value = ord("?")
            self.assertIsNone(completer.complete("update", 0))
            writes_direct_q = "".join(call.args[0] for call in mock_stdout.write.call_args_list)
            self.assertIn("--add-admin", writes_direct_q)

            # Typing 'domain update ' (with trailing space) + double-Tab:
            # 1st Tab expands common prefix '--'; 2nd Tab immediately displays all flags.
            mock_stdout.reset_mock()
            mock_rl.get_line_buffer.return_value = "domain update "
            mock_rl.get_endidx.return_value = 14
            mock_rl.get_completion_type.return_value = ord("\t")
            self.assertEqual(completer.complete("", 0), "--add-admin")
            mock_rl.get_line_buffer.return_value = "domain update --"
            mock_rl.get_endidx.return_value = 16
            self.assertIsNone(completer.complete("--", 0))
            writes_prefix_exp = "".join(call.args[0] for call in mock_stdout.write.call_args_list)
            self.assertIn("--add-admin", writes_prefix_exp)
            self.assertIn("--registrant", writes_prefix_exp)

            # Single-match command with no next-token candidates ('exit') on '?' still renders
            # above the status bar instead of letting readline overwrite the status bar.
            mock_stdout.reset_mock()
            mock_rl.get_line_buffer.return_value = "exit"
            mock_rl.get_endidx.return_value = 4
            mock_rl.get_completion_type.return_value = ord("?")
            self.assertIsNone(completer.complete("exit", 0))
            writes_single = "".join(call.args[0] for call in mock_stdout.write.call_args_list)
            self.assertIn("exit", writes_single)

            # display_matches_hook fallback renders above status bar
            mock_stdout.reset_mock()
            mock_rl.get_line_buffer.return_value = "domain update --"
            mock_rl.get_endidx.return_value = 16
            completer.display_matches_hook("--", ["--add-admin", "--help"], 11)
            writes_hook = "".join(call.args[0] for call in mock_stdout.write.call_args_list)
            self.assertIn("--add-admin", writes_hook)
            self.assertIn("--help", writes_hook)

    def test_sensitive_history_scrubbing_transfer_and_quoted_flags(self) -> None:
        """Verify positional transfer credentials, quoted password flags, and malformed input are scrubbed."""
        cli_obj = self._create_mock_cli(dry_run=True)

        # Positional domain transfer credentials are scrubbed
        with patch("pyepp.cli.shell._readline") as mock_rl:
            mock_rl.get_current_history_length.return_value = 2
            with patch.object(cli_obj, "transfer", return_value="ok"):
                execute_shell_line(cli_obj, "domain transfer example.nz SecretAuth123")
            mock_rl.remove_history_item.assert_called_once_with(1)

        # 'domain transfer --help' does not provide credentials and is NOT scrubbed
        with patch("pyepp.cli.shell._readline") as mock_rl:
            execute_shell_line(cli_obj, "domain transfer example.nz --help")
            mock_rl.remove_history_item.assert_not_called()

        # Quoted flags e.g. "--password" or '--pass=...' are scrubbed
        self.assertTrue(_is_sensitive_line('domain info example.nz "--password" Secret123'))
        self.assertTrue(_is_sensitive_line("domain info example.nz '--pass=Secret123'"))
        self.assertTrue(_is_sensitive_line('profile show default "--show-secrets"'))

        # Malformed / unbalanced quotes with auth/secret/pass keywords are conservatively scrubbed
        self.assertTrue(_is_sensitive_line("domain transfer 'unclosed auth secret"))
        self.assertTrue(_is_sensitive_line('domain info example.nz "unclosed pass'))

        # Normal commands without sensitive flags return False
        self.assertFalse(_is_sensitive_line("domain check example.nz"))
        self.assertFalse(_is_sensitive_line("domain info example.nz"))
        self.assertFalse(_is_sensitive_line(""))

        # Accidental positional credentials on password-capable commands are detected as sensitive
        self.assertTrue(_is_sensitive_line("domain update example.nz securepassword12"))
        self.assertFalse(_is_sensitive_line("domain update example.nz --registrant CONTACT-1"))
        self.assertTrue(_is_sensitive_line("domain update example.nz --add-admin CONTACT-1 securepassword12"))
        self.assertTrue(_is_sensitive_line("contact update contact-1 securepassword12"))
        self.assertFalse(_is_sensitive_line("contact update contact-1 --name John"))
        self.assertTrue(_is_sensitive_line("contact create contact-1 securepassword12"))
        self.assertFalse(_is_sensitive_line("contact info contact-1"))
        self.assertTrue(_is_sensitive_line("pyepp domain update example.nz securepassword12"))

    def test_accidental_positional_password_not_recorded_in_history(self) -> None:
        """Verify wrong commands with accidental positional password are not saved to history."""
        cli_obj = self._create_mock_cli(dry_run=True)
        cli_obj.session_history = ["domain check example.nz"]

        # 'domain update example.nz securepassword12' is rejected by Click (unexpected extra arg),
        # identified as sensitive by _is_sensitive_line, and never added to session history.
        with patch("pyepp.cli.shell._readline") as mock_rl:
            mock_rl.get_current_history_length.return_value = 2
            execute_shell_line(cli_obj, "domain update example.nz securepassword12")
            mock_rl.remove_history_item.assert_called_once_with(1)

        self.assertEqual(cli_obj.session_history, ["domain check example.nz"])

    def test_unexpected_extra_arguments_scrubbed_from_history(self) -> None:
        """Verify invalid extra arguments on commands are defensively scrubbed from history."""
        cli_obj = self._create_mock_cli(dry_run=True)
        cli_obj.session_history = ["domain check example.nz"]

        # If a non-sensitive command fails due to unexpected extra argument, the reactive
        # exception handler pops it from session history and scrubs readline.
        with patch("pyepp.cli.shell._readline") as mock_rl:
            mock_rl.get_current_history_length.return_value = 2
            execute_shell_line(cli_obj, "domain info example.nz unexpected_extra_arg")
            mock_rl.remove_history_item.assert_called_once_with(1)

        self.assertEqual(cli_obj.session_history, ["domain check example.nz"])

    def test_cleanup_unexpected_arg_history_helper(self) -> None:
        """Verify _cleanup_unexpected_arg_history pops matching session history and scrubs readline."""
        cli_obj = self._create_mock_cli(dry_run=True)
        cli_obj.session_history = ["domain check example.nz", "domain check example.nz badarg"]
        usage_err = click.UsageError("Got unexpected extra argument (badarg)")

        with patch("pyepp.cli.shell._readline") as mock_rl:
            mock_rl.get_current_history_length.return_value = 2
            _cleanup_unexpected_arg_history(cli_obj, "domain check example.nz badarg", usage_err)
            mock_rl.remove_history_item.assert_called_once_with(1)

        self.assertEqual(cli_obj.session_history, ["domain check example.nz"])

        # Non-matching error message does not pop or scrub
        other_err = click.UsageError("Missing parameter: domain_name")
        with patch("pyepp.cli.shell._readline") as mock_rl:
            _cleanup_unexpected_arg_history(cli_obj, "domain check", other_err)
            mock_rl.remove_history_item.assert_not_called()

        self.assertEqual(cli_obj.session_history, ["domain check example.nz"])

    def test_safe_close_session_records_last_logout_error_and_bifurcated_logging(self) -> None:
        """Verify _safe_close_session records logout error, bifurcates warning vs debug, and disconnects."""
        cli_obj = self._create_mock_cli(dry_run=False)
        cli_obj.epp._logged_in = True
        cli_obj.epp._last_logout_error = None
        cli_obj.last_logout_error = None
        cli_obj.disconnect = MagicMock()

        # 1. Normal cleanup (has_active_exception=False): logout failure is logged at WARNING
        logout_err = EppCommunicatorException("Logout failed with code 2000")
        with patch.object(cli_obj, "logout", side_effect=logout_err):
            with self.assertLogs(level=logging.WARNING) as log_capture:
                _safe_close_session(cli_obj, has_active_exception=False)

        self.assertEqual(cli_obj.last_logout_error, logout_err)
        self.assertEqual(cli_obj.epp._last_logout_error, logout_err)
        cli_obj.disconnect.assert_called_once()
        self.assertTrue(
            any("Logout failed during shell session cleanup" in msg for msg in log_capture.output)
        )

        # 2. Active exception cleanup (has_active_exception=True): logged at DEBUG
        cli_obj.disconnect.reset_mock()
        cli_obj.last_logout_error = None
        cli_obj.epp._last_logout_error = None
        with patch.object(cli_obj, "logout", side_effect=logout_err):
            with self.assertLogs(level=logging.DEBUG) as log_capture:
                _safe_close_session(cli_obj, has_active_exception=True)

        self.assertEqual(cli_obj.last_logout_error, logout_err)
        self.assertEqual(cli_obj.epp._last_logout_error, logout_err)
        cli_obj.disconnect.assert_called_once()
        self.assertTrue(
            any("Logout failed during shell session cleanup while handling exception" in msg
                for msg in log_capture.output)
        )

        # 3. Disconnect failure on normal cleanup logs warning
        cli_obj.disconnect.side_effect = RuntimeError("Disconnect socket drop")
        with patch.object(cli_obj, "logout", return_value=None):
            with self.assertLogs(level=logging.WARNING) as log_capture:
                _safe_close_session(cli_obj, has_active_exception=False)
        self.assertTrue(
            any("Disconnect failed during shell session cleanup" in msg for msg in log_capture.output)
        )

    def test_last_and_save_commands_with_no_pretty_bytes_response(self) -> None:
        """Verify 'last XML' and 'save <file> XML' decode raw bytes as UTF-8 string when pretty-printing is disabled."""
        cli_obj = self._create_mock_cli(dry_run=True)
        cli_obj.no_pretty = True

        raw_bytes = b"<epp><response><result code='1000'><msg>OK</msg></result></response></epp>"
        check_res = EppResultData(
            code=1000,
            message="OK",
            raw_response=raw_bytes,
            result_data={"example.nz": {"avail": True}},
            dry_run=True,
        )
        cli_obj.last_result = check_res

        # Test _format_last_result directly
        rendered = _format_last_result(cli_obj, fmt_override="XML")
        self.assertIsInstance(rendered, str)
        self.assertNotIn("b'", rendered)
        self.assertIn("<result code='1000'>", rendered)

        # Test 'last XML' shell command output
        with patch("pyepp.cli.utils.echo") as mock_echo:
            self.assertTrue(execute_shell_line(cli_obj, "last XML"))
            out = mock_echo.call_args[0][0]
            self.assertIsInstance(out, str)
            self.assertNotIn("b'", out)
            self.assertIn("<result code='1000'>", out)

        # Test 'save <filepath> XML' exports clean string
        out_file = os.path.join(self.tmp_history_dir, "saved_no_pretty.xml")
        try:
            self.assertTrue(execute_shell_line(cli_obj, f"save {out_file} XML"))
            with open(out_file, "r", encoding="utf-8") as f_in:
                saved_text = f_in.read()
            self.assertNotIn("b'", saved_text)
            self.assertIn("<result code='1000'>", saved_text)
        finally:
            if os.path.exists(out_file):
                os.remove(out_file)

    def test_format_input_viewport_scrolling_and_dock_protection(self) -> None:
        """Verify _format_input_viewport keeps long input on a single row without wrapping."""
        prompt = "pyepp [default]> "
        max_cols = 30

        # Short buffer fits within max_cols without scrolling
        short_buf = "domain check"
        rendered, shift = _format_input_viewport(prompt, short_buf, len(short_buf), max_cols)
        self.assertEqual(rendered, f"{prompt}{short_buf}")
        self.assertEqual(shift, 0)

        # Long buffer exceeds max_cols and truncates with '>' scroll indicator
        long_buf = "domain update example.nz --add-admin CONTACT-12345 --remove-tech CONTACT-99999"
        rendered_start, shift_start = _format_input_viewport(prompt, long_buf, 0, max_cols)
        self.assertTrue(rendered_start.endswith(">"))
        self.assertLessEqual(len(click.unstyle(rendered_start)), max_cols)

        # Cursor scrolled near the end shows '<' indicator
        rendered_end, shift_end = _format_input_viewport(prompt, long_buf, len(long_buf), max_cols)
        self.assertTrue("<" in rendered_end)
        self.assertEqual(shift_end, 0)
        self.assertLessEqual(len(click.unstyle(rendered_end)), max_cols)

        # Cursor in the middle shows both '<' and '>' indicators
        mid_pos = len(long_buf) // 2
        rendered_mid, shift_mid = _format_input_viewport(prompt, long_buf, mid_pos, max_cols)
        self.assertTrue("<" in rendered_mid and ">" in rendered_mid)
        self.assertLessEqual(len(click.unstyle(rendered_mid)), max_cols)

        # Verify readline configuration enables horizontal-scroll-mode
        completer = ShellCompleter(self._create_mock_cli(dry_run=True))
        with patch("pyepp.cli.shell._readline") as mock_rl:
            mock_rl.get_completer_delims.return_value = " \t\n\"\\'`@$><=;|&{("
            _configure_readline(completer)
            mock_rl.parse_and_bind.assert_any_call("set horizontal-scroll-mode on")

    def test_transfer_password_with_help_flag_scrubbed_from_history(self) -> None:
        """Verify that transfer commands containing passwords with --help are scrubbed, while clean help remains."""
        # Transfer with domain, password, and --help flag contains authInfo: must be scrubbed
        self.assertTrue(_is_sensitive_line("domain transfer example.nz Z8v2R9 --help"))
        self.assertTrue(_is_sensitive_line("pyepp domain transfer example.nz Z8v2R9 --help"))
        self.assertTrue(_is_sensitive_line("domain update example.nz MySecretPassword --help"))

        # Help on transfer or update without credentials is clean and not sensitive
        self.assertFalse(_is_sensitive_line("domain transfer example.nz --help"))
        self.assertFalse(_is_sensitive_line("domain transfer --help"))
        self.assertFalse(_is_sensitive_line("domain update --help"))
        self.assertFalse(_is_sensitive_line("domain update example.nz --help"))
        self.assertFalse(_is_sensitive_line("contact update --help"))

    def test_malformed_credential_commands_scrubbed_from_history(self) -> None:
        """Verify parser errors on password-capable commands are treated as sensitive to prevent leaks."""
        # Missing option argument or unknown option on transfer command with password
        self.assertTrue(_is_sensitive_line("domain transfer example.nz Z8v2R9 --period"))
        self.assertTrue(_is_sensitive_line("domain transfer example.nz Z8v2R9 --unknown-flag"))
        self.assertTrue(_is_sensitive_line("domain update example.nz secret123 --unknown-flag"))
        self.assertTrue(_is_sensitive_line("contact update contact-1 secret123 --unknown-flag"))

        # Non-password commands with parsing errors are not treated as sensitive
        self.assertFalse(_is_sensitive_line("domain check example.nz --period"))
        self.assertFalse(_is_sensitive_line("domain check example.nz --unknown-flag"))
        self.assertFalse(_is_sensitive_line("domain info example.nz --unknown-flag"))
        self.assertFalse(_is_sensitive_line("host info ns1.example.nz --unknown-flag"))

    def test_viewport_narrow_terminals_no_wrapping(self) -> None:
        """Verify _format_input_viewport bounds viewport to actual remaining columns in narrow terminals."""
        prompt = "pyepp> "  # length 7
        buf = "domain transfer example.nz Z8v2R9"

        # max_cols = 14: 7 cols for prompt, 7 cols for viewport, exactly 14 cols total (never 17)
        rendered_end, shift_end = _format_input_viewport(prompt, buf, len(buf), 14)
        self.assertLessEqual(len(click.unstyle(rendered_end)), 14)
        self.assertEqual(shift_end, 0)

        rendered_start, shift_start = _format_input_viewport(prompt, buf, 0, 14)
        self.assertLessEqual(len(click.unstyle(rendered_start)), 14)
        self.assertLessEqual(shift_start, 14)

        # Very narrow terminal (max_cols = 8): prompt is truncated, total <= 8
        rendered_narrow, _ = _format_input_viewport(prompt, buf, len(buf), 8)
        self.assertLessEqual(len(click.unstyle(rendered_narrow)), 8)

        # Zero or negative max_cols returns empty string even when prompt and buffer are empty
        self.assertEqual(_format_input_viewport("", "", 0, 0), ("", 0))
        self.assertEqual(_format_input_viewport("", "", 0, -5), ("", 0))

        # Check across all widths 1..35 and all cursor positions that visible width <= max_cols
        for w in range(1, 36):
            for c in (0, 5, len(buf) // 2, len(buf)):
                r, s = _format_input_viewport(prompt, buf, c, w)
                plain = click.unstyle(r)
                self.assertLessEqual(len(plain), w)
                self.assertGreaterEqual(s, 0)
                self.assertLessEqual(s, len(plain))

    def test_undocked_fallback_when_dimensions_insufficient(self) -> None:
        """Verify shell uses undocked fallback when terminal has insufficient dimensions or lacks ANSI."""
        cli_obj = self._create_mock_cli(dry_run=True)

        # Not an ANSI tty -> _supports_dock is False
        with patch("pyepp.cli.shell._supports_ansi_tty", return_value=False):
            self.assertFalse(_supports_dock())
            with patch("builtins.input", return_value="domain check example.nz") as mock_input:
                self.assertEqual(_read_line_with_status_bar(cli_obj), "domain check example.nz")
                mock_input.assert_called_once_with(format_prompt(cli_obj, color=False))

        # lines < 6 -> _supports_dock is False, and _exit_bottom_dock still resets DECSTBM (\033[r) on ANSI TTY
        with (
            patch("pyepp.cli.shell._supports_ansi_tty", return_value=True),
            patch("shutil.get_terminal_size", return_value=os.terminal_size((80, 5))),
        ):
            self.assertFalse(_supports_dock())
            with patch("builtins.input", return_value="status") as mock_input:
                self.assertEqual(_read_line_with_status_bar(cli_obj), "status")
                mock_input.assert_called_once_with(format_prompt(cli_obj, color=False))
            with patch("sys.stdout") as mock_stdout:
                _exit_bottom_dock()
                mock_stdout.write.assert_called_once_with("\033[r")

        # columns < 12 -> _supports_dock is False
        with (
            patch("pyepp.cli.shell._supports_ansi_tty", return_value=True),
            patch("shutil.get_terminal_size", return_value=os.terminal_size((10, 24))),
        ):
            self.assertFalse(_supports_dock())

        # lines >= 6 and columns >= 12 -> _supports_dock is True
        with (
            patch("pyepp.cli.shell._supports_ansi_tty", return_value=True),
            patch("shutil.get_terminal_size", return_value=os.terminal_size((80, 24))),
        ):
            self.assertTrue(_supports_dock())

    def test_readline_completion_dumb_terminal_fallback(self) -> None:
        """Verify custom completion hook is not installed on plain/dumb terminals and native rendering is preserved."""
        cli_obj = self._create_mock_cli(dry_run=True)
        completer = ShellCompleter(cli_obj)

        # On plain terminal / dumb terminal (_supports_dock is False):
        with (
            patch("pyepp.cli.shell._readline") as mock_rl,
            patch("pyepp.cli.shell._supports_dock", return_value=False),
        ):
            mock_rl.get_completer_delims.return_value = " \t\n\"\\'`@$><=;|&{("
            _configure_readline(completer)
            # Hook should NOT be set, letting readline use native match display
            mock_rl.set_completion_display_matches_hook.assert_not_called()

        # In complete() with _supports_dock False, double-Tab does not intercept or return None
        with (
            patch("pyepp.cli.shell._readline") as mock_rl,
            patch("pyepp.cli.shell._supports_dock", return_value=False),
        ):
            mock_rl.get_line_buffer.return_value = "domain "
            mock_rl.get_completion_type.return_value = ord("?")
            mock_rl.get_endidx.return_value = 7
            # Does not return None, returns matching candidate normally for native readline
            result = completer.complete("", 0)
            self.assertIsNotNone(result)

        # On ANSI terminal with dock (_supports_dock is True):
        with (
            patch("pyepp.cli.shell._readline") as mock_rl,
            patch("pyepp.cli.shell._supports_dock", return_value=True),
        ):
            mock_rl.get_completer_delims.return_value = " \t\n\"\\'`@$><=;|&{("
            _configure_readline(completer)
            mock_rl.set_completion_display_matches_hook.assert_called_once_with(completer.display_matches_hook)


if __name__ == "__main__":
    unittest.main()
