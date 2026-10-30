"""
CLI Interactive Shell unit tests.
"""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from pyepp import EppResultData, EppCommunicatorException
from pyepp.cli.__main__ import pyepp_cli, load_config
from pyepp.cli.cli import PyEppCli
from pyepp.cli.shell import (
    ASCII_BANNER,
    ShellCompleter,
    execute_shell_line,
    format_prompt,
    switch_profile,
    _configure_readline,
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

[profile incomplete]
server = epp.incomplete.net.nz
"""
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            tf.write(self.ini_content)
            self.cfg_path = tf.name

    def tearDown(self) -> None:
        if os.path.exists(self.cfg_path):
            os.remove(self.cfg_path)
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

        # Built-in 'set' completions
        set_keys = completer.get_candidates("set ", "")
        self.assertEqual(list(set_keys), ["output-format", "pretty", "dry-run"])

        set_fmt = completer.get_candidates("set output-format T", "T")
        self.assertEqual(set_fmt, ["TABLE"])

        set_pretty = completer.get_candidates("set pretty ", "")
        self.assertEqual(set_pretty, ["on", "off"])

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

        # Reconnect and clear (clear only clears screen, preserving command history)
        with patch("click.clear") as mock_clear, patch(
            "pyepp.cli.shell._readline"
        ) as mock_rl:
            self.assertTrue(execute_shell_line(cli_obj, "clear"))
            mock_clear.assert_called_once()
            mock_rl.clear_history.assert_not_called()

        self.assertTrue(execute_shell_line(cli_obj, "reconnect"))

        # Quit returns False
        self.assertFalse(execute_shell_line(cli_obj, "quit"))

    def test_shell_prompt_formatting_and_interrupts(self) -> None:
        """Verify dynamic prompt formatting and handling of KeyboardInterrupt / EOFError."""
        cli_obj = self._create_mock_cli(dry_run=True)
        self.assertEqual(
            format_prompt(cli_obj),
            "pyepp [ote:dry-run] (ote_user@epp.ote.registry.net.nz)> ",
        )

        cli_obj.dry_run = False
        cli_obj.epp._logged_in = False
        self.assertEqual(
            format_prompt(cli_obj),
            "pyepp [ote:disconnected] (ote_user@epp.ote.registry.net.nz)> ",
        )

        cli_obj.epp._logged_in = True
        self.assertEqual(
            format_prompt(cli_obj),
            "pyepp [ote] (ote_user@epp.ote.registry.net.nz)> ",
        )

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
            mock_rl.parse_and_bind.assert_called_with("bind ^I rl_complete")
            self.assertNotIn("-", mock_rl.set_completer_delims.call_args[0][0])

            mock_rl.__doc__ = "GNU readline"
            old_delims = _configure_readline(completer)
            mock_rl.parse_and_bind.assert_called_with("tab: complete")

            from pyepp.cli.shell import _cleanup_readline

            _cleanup_readline(old_delims)
            mock_rl.set_completer.assert_called_with(None)
            mock_rl.set_completer_delims.assert_called_with(old_delims)
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


if __name__ == "__main__":
    unittest.main()
