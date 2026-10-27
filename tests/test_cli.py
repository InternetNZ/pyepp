"""
CLI base module and decorator unit tests.
"""
import logging
import os
import pprint
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from pyepp import (
    EppResultData,
    DomainData,
    ContactData,
    PostalInfoData,
    AddressData,
)
from pyepp.host import HostData, IPAddressData
from pyepp.cli.cli import PyEppCli, login_logout
from pyepp.cli.utils import format_table, format_tsv
from pyepp.cli.__main__ import pyepp_cli, load_config, CONTEXT_SETTINGS
from pyepp.epp import EppCommunicatorException


class DummyCli:
    """Dummy CLI class to test the login_logout decorator."""

    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.connect = MagicMock()
        self.disconnect = MagicMock()
        self.login = MagicMock()
        self.logout = MagicMock()

    @login_logout
    def execute_command(self, *args, **kwargs):
        """Dummy command method."""
        return "command_result"


class CliDecoratorTest(unittest.TestCase):
    """
    Test suite for the login_logout decorator and its edge cases.
    """

    def test_login_logout_success(self) -> None:
        """Verify normal execution connects, logs in, executes, and logs out."""
        cli = DummyCli(dry_run=False)
        order = []
        cli.connect.side_effect = lambda: order.append("connect")
        cli.login.side_effect = lambda: order.append("login")
        cli.logout.side_effect = lambda: order.append("logout")

        result = cli.execute_command("arg1", key="val")

        self.assertEqual(result, "command_result")
        self.assertEqual(order, ["connect", "login", "logout"])
        cli.connect.assert_called_once()
        cli.login.assert_called_once()
        cli.logout.assert_called_once()
        cli.disconnect.assert_not_called()

    def test_login_logout_func_raises_exception(self) -> None:
        """Verify logout is still invoked when the decorated function raises an exception."""
        cli = DummyCli(dry_run=False)

        class FailingCli(DummyCli):
            @login_logout
            def execute_command(self, *args, **kwargs):
                raise EppCommunicatorException("EPP Command failed")

        failing_cli = FailingCli(dry_run=False)

        with self.assertRaises(EppCommunicatorException) as context:
            failing_cli.execute_command()

        self.assertEqual(str(context.exception), "EPP Command failed")
        failing_cli.connect.assert_called_once()
        failing_cli.login.assert_called_once()
        failing_cli.logout.assert_called_once()
        failing_cli.disconnect.assert_not_called()

    def test_login_logout_dry_run_success(self) -> None:
        """Verify connect, login, and logout are skipped in dry-run mode."""
        cli = DummyCli(dry_run=True)

        result = cli.execute_command()

        self.assertEqual(result, "command_result")
        cli.connect.assert_not_called()
        cli.login.assert_not_called()
        cli.logout.assert_not_called()
        cli.disconnect.assert_not_called()

    def test_login_logout_dry_run_exception(self) -> None:
        """Verify logout is skipped in dry-run mode even when an exception is raised."""
        class FailingCli(DummyCli):
            @login_logout
            def execute_command(self, *args, **kwargs):
                raise ValueError("Dry run error")

        failing_cli = FailingCli(dry_run=True)

        with self.assertRaises(ValueError) as context:
            failing_cli.execute_command()

        self.assertEqual(str(context.exception), "Dry run error")
        failing_cli.connect.assert_not_called()
        failing_cli.login.assert_not_called()
        failing_cli.logout.assert_not_called()
        failing_cli.disconnect.assert_not_called()

    def test_login_logout_cleanup_logout_exception_on_func_error(self) -> None:
        """Verify that a logout error during cleanup does not mask the original exception."""
        class FailingCli(DummyCli):
            @login_logout
            def execute_command(self, *args, **kwargs):
                raise EppCommunicatorException("Original command failure")

        failing_cli = FailingCli(dry_run=False)
        failing_cli.logout.side_effect = RuntimeError("Network error during logout")

        with self.assertLogs(level=logging.DEBUG) as log_capture:
            with self.assertRaises(EppCommunicatorException) as context:
                failing_cli.execute_command()

        self.assertEqual(str(context.exception), "Original command failure")
        failing_cli.logout.assert_called_once()
        self.assertTrue(
            any("Logout failed during cleanup: Network error during logout" in msg
                for msg in log_capture.output)
        )

    def test_login_logout_cleanup_logout_exception_on_func_success(self) -> None:
        """Verify that a logout error during cleanup is suppressed and command result returned."""
        cli = DummyCli(dry_run=False)
        cli.logout.side_effect = RuntimeError("Network error during logout")

        with self.assertLogs(level=logging.DEBUG) as log_capture:
            result = cli.execute_command()

        self.assertEqual(result, "command_result")
        cli.logout.assert_called_once()
        self.assertTrue(
            any("Logout failed during cleanup: Network error during logout" in msg
                for msg in log_capture.output)
        )

    def test_login_logout_connect_fails(self) -> None:
        """Verify that if connect fails, logout and disconnect are not called and exception propagates."""
        cli = DummyCli(dry_run=False)
        cli.connect.side_effect = EppCommunicatorException("Connection failed")

        with self.assertRaises(EppCommunicatorException) as context:
            cli.execute_command()

        self.assertEqual(str(context.exception), "Connection failed")
        cli.connect.assert_called_once()
        cli.login.assert_not_called()
        cli.logout.assert_not_called()
        cli.disconnect.assert_not_called()

    def test_login_logout_login_fails(self) -> None:
        """Verify that if login fails after connect, disconnect is called and logout is not called."""
        cli = DummyCli(dry_run=False)
        cli.login.side_effect = EppCommunicatorException("Authentication failed")

        with self.assertRaises(EppCommunicatorException) as context:
            cli.execute_command()

        self.assertEqual(str(context.exception), "Authentication failed")
        cli.connect.assert_called_once()
        cli.login.assert_called_once()
        cli.disconnect.assert_called_once()
        cli.logout.assert_not_called()

    def test_login_logout_cleanup_disconnect_exception_on_login_fails(self) -> None:
        """Verify that a disconnect error during cleanup does not mask the login exception."""
        cli = DummyCli(dry_run=False)
        cli.login.side_effect = EppCommunicatorException("Authentication failed")
        cli.disconnect.side_effect = RuntimeError("Socket error during disconnect")

        with self.assertLogs(level=logging.DEBUG) as log_capture:
            with self.assertRaises(EppCommunicatorException) as context:
                cli.execute_command()

        self.assertEqual(str(context.exception), "Authentication failed")
        cli.connect.assert_called_once()
        cli.login.assert_called_once()
        cli.disconnect.assert_called_once()
        cli.logout.assert_not_called()
        self.assertTrue(
            any("Disconnect failed during cleanup: Socket error during disconnect" in msg
                for msg in log_capture.output)
        )


class CliFormatOutputTest(unittest.TestCase):
    """
    Test suite for PyEppCli.format_output and MIN output formatting.
    """

    def setUp(self) -> None:
        self.cli_min = PyEppCli(
            "localhost",
            "700",
            None,
            None,
            "user",
            "pass",
            [],
            output_format="MIN",
            no_pretty=False,
        )
        self.cli_min_raw = PyEppCli(
            "localhost",
            "700",
            None,
            None,
            "user",
            "pass",
            [],
            output_format="MIN",
            no_pretty=True,
        )
        self.cli_table = PyEppCli(
            "localhost",
            "700",
            None,
            None,
            "user",
            "pass",
            [],
            output_format="TABLE",
            no_pretty=False,
        )
        self.cli_table_raw = PyEppCli(
            "localhost",
            "700",
            None,
            None,
            "user",
            "pass",
            [],
            output_format="TABLE",
            no_pretty=True,
        )

    def test_min_format_pretty_dict(self) -> None:
        """Verify MIN output format pretty-prints dictionary result_data with pprint."""
        check_data = {
            "example1.nz": {"avail": False, "reason": "Registered"},
            "example2.nz": {"avail": True, "reason": None},
        }
        result = EppResultData(
            code=1000,
            message="Command completed successfully",
            raw_response="<raw/>",
            result_data=check_data,
        )
        output = self.cli_min.format_output(result)
        self.assertIsInstance(output, str)
        self.assertEqual(output, pprint.pformat(check_data))
        self.assertIn("\n", output)

    def test_min_format_pretty_dataclass(self) -> None:
        """Verify MIN output format pretty-prints dataclass result_data with pprint."""
        domain_data = DomainData(
            domain_name="example.nz",
            registrant="reg-1",
            admin="adm-1",
            status=["ok"],
            host=["ns1.example.nz"],
        )
        result = EppResultData(
            code=1000,
            message="Command completed successfully",
            raw_response="<raw/>",
            result_data=domain_data,
        )
        output = self.cli_min.format_output(result)
        self.assertIsInstance(output, str)
        self.assertEqual(output, pprint.pformat(domain_data))
        self.assertIn("\n", output)
        self.assertIn("DomainData(", output)
        self.assertIn("domain_name='example.nz'", output)

    def test_min_format_none_result_data(self) -> None:
        """Verify MIN output format returns None when result_data is None."""
        result = EppResultData(
            code=1000,
            message="Command completed successfully",
            raw_response="<raw/>",
            result_data=None,
        )
        output = self.cli_min.format_output(result)
        self.assertIsNone(output)

    def test_min_format_no_pretty(self) -> None:
        """Verify MIN output format returns raw result_data when no_pretty is True."""
        check_data = {"example.nz": {"avail": True, "reason": None}}
        result = EppResultData(
            code=1000,
            message="Command completed successfully",
            raw_response="<raw/>",
            result_data=check_data,
        )
        output = self.cli_min_raw.format_output(result)
        self.assertEqual(output, check_data)

    def test_output_format_case_insensitivity(self) -> None:
        """Verify output_format lowercase 'min' is normalized and formatted."""
        cli = PyEppCli(
            "localhost",
            "700",
            None,
            None,
            "user",
            "pass",
            [],
            output_format="min",
            no_pretty=False,
        )
        self.assertEqual(cli.output_format, "MIN")
        result = EppResultData(
            code=1000,
            message="Command completed successfully",
            raw_response="<raw/>",
            result_data={"test.nz": {"avail": True, "reason": None}},
        )
        output = cli.format_output(result)
        self.assertEqual(
            output, pprint.pformat({"test.nz": {"avail": True, "reason": None}})
        )

    def test_cli_runner_min_flags_and_output(self) -> None:
        """Verify CLI runner accepts -o min, --o min, --output-format min and displays pretty result_data."""
        runner = CliRunner()
        check_data = {
            "domain1.nz": {"avail": False, "reason": "Registered"},
            "domain2.nz": {"avail": True, "reason": None},
        }
        mock_result = EppResultData(
            code=1000,
            message="Command completed successfully",
            raw_response="<raw/>",
            result_data=check_data,
        )

        for flag in ["-o", "--o", "--output-format"]:
            with patch("pyepp.domain.Domain.check", return_value=mock_result):
                result = runner.invoke(
                    pyepp_cli,
                    [
                        "--server",
                        "localhost",
                        "--port",
                        "700",
                        "--user",
                        "user",
                        "--password",
                        "pass",
                        flag,
                        "min",
                        "--dry-run",
                        "domain",
                        "check",
                        "domain1.nz",
                        "domain2.nz",
                    ],
                )
                self.assertEqual(result.exit_code, 0)
                expected_pretty = pprint.pformat(check_data)
                self.assertIn(expected_pretty, result.output)

    def test_cli_runner_min_no_pretty(self) -> None:
        """Verify CLI runner with --no-pretty outputs raw single-line dictionary."""
        runner = CliRunner()
        check_data = {
            "domain1.nz": {"avail": False, "reason": "Registered"},
            "domain2.nz": {"avail": True, "reason": None},
        }
        mock_result = EppResultData(
            code=1000,
            message="Command completed successfully",
            raw_response="<raw/>",
            result_data=check_data,
        )

        with patch("pyepp.domain.Domain.check", return_value=mock_result):
            result = runner.invoke(
                pyepp_cli,
                [
                    "--server",
                    "localhost",
                    "--port",
                    "700",
                    "--user",
                    "user",
                    "--password",
                    "pass",
                    "-o",
                    "min",
                    "--no-pretty",
                    "--dry-run",
                    "domain",
                    "check",
                    "domain1.nz",
                    "domain2.nz",
                ],
            )
            self.assertEqual(result.exit_code, 0)
            self.assertIn(str(check_data), result.output)

    def test_cli_runner_min_file_output(self) -> None:
        """Verify CLI runner with -f / --file writes MIN pretty output to file successfully."""
        runner = CliRunner()
        domain_data = DomainData(
            domain_name="example.nz",
            registrant="reg-1",
            status=["ok"],
        )
        mock_result = EppResultData(
            code=1000,
            message="Command completed successfully",
            raw_response="<raw/>",
            result_data=domain_data,
        )

        with tempfile.NamedTemporaryFile(delete=False) as tf:
            out_path = tf.name

        try:
            with patch("pyepp.domain.Domain.info", return_value=mock_result):
                result = runner.invoke(
                    pyepp_cli,
                    [
                        "--server",
                        "localhost",
                        "--port",
                        "700",
                        "--user",
                        "user",
                        "--password",
                        "pass",
                        "--o",
                        "min",
                        "-f",
                        out_path,
                        "--dry-run",
                        "domain",
                        "info",
                        "example.nz",
                    ],
                )
                self.assertEqual(result.exit_code, 0)
                with open(out_path, "r", encoding="utf-8") as f:
                    file_content = f.read()
                self.assertIn("DomainData(", file_content)
                self.assertIn("domain_name='example.nz'", file_content)
                self.assertIn("\n", file_content)
        finally:
            if os.path.exists(out_path):
                os.remove(out_path)

    def test_table_format_pretty_dict(self) -> None:
        """Verify TABLE output format renders Master EPP Response table and Check Results sub-table."""
        check_data = {
            "example1.nz": {"avail": False, "reason": "Registered"},
            "example2.nz": {"avail": True, "reason": None},
        }
        result = EppResultData(
            code=1000,
            message="Command completed successfully",
            raw_response="<raw_xml_payload/>",
            result_data=check_data,
            client_transaction_id="cl-trid-123",
            server_transaction_id="sv-trid-456",
        )
        output = self.cli_table.format_output(result)
        self.assertIsInstance(output, str)
        # Master envelope section
        self.assertIn("[ EPP Response ]", output)
        self.assertIn("| Field", output)
        self.assertIn("| Value", output)
        self.assertIn("1000", output)
        self.assertIn("Command completed successfully", output)
        self.assertIn("cl-trid-123", output)
        self.assertIn("sv-trid-456", output)
        # Dedicated check sub-table section
        self.assertIn("[ Check Results ]", output)
        self.assertIn("| Entity", output)
        self.assertIn("| Available", output)
        self.assertIn("| Reason", output)
        self.assertIn("example1.nz", output)
        self.assertIn("No", output)
        self.assertIn("Registered", output)
        self.assertIn("example2.nz", output)
        self.assertIn("Yes", output)
        # raw_response and parsed_xml must be strictly omitted
        self.assertNotIn("raw_response", output)
        self.assertNotIn("<raw_xml_payload/>", output)
        self.assertNotIn("parsed_xml", output)

    def test_table_format_pretty_dataclass(self) -> None:
        """Verify TABLE output format renders Master EPP table and Domain Information sub-table."""
        domain_data = DomainData(
            domain_name="example.nz",
            registrant="reg-1",
            admin="adm-1",
            status=["ok"],
            host=["ns1.example.nz"],
        )
        result = EppResultData(
            code=1000,
            message="Command completed successfully",
            raw_response="<raw/>",
            result_data=domain_data,
        )
        output = self.cli_table.format_output(result)
        self.assertIn("[ EPP Response ]", output)
        self.assertIn("[ Domain Information: example.nz ]", output)
        self.assertIn("| Property", output)
        self.assertIn("| Value", output)
        self.assertIn("domain_name", output)
        self.assertIn("example.nz", output)
        self.assertIn("registrant", output)
        self.assertIn("reg-1", output)
        self.assertIn("nameservers", output)
        self.assertIn("ns1.example.nz", output)
        self.assertNotIn("raw_response", output)

    def test_table_format_contact_data(self) -> None:
        """Verify TABLE output format renders Contact Information sub-table with postal details."""
        postal = PostalInfoData(
            name="John Doe",
            organization="ACME Corp",
            address=AddressData(
                street_1="123 Main St",
                street_2="Suite 400",
                city="Wellington",
                country_code="NZ",
            ),
        )
        contact = ContactData(
            id="sh8013",
            email="jdoe@example.nz",
            postal_info=postal,
            phone="+64.41234567",
            status=["ok"],
            privacy=["email"],
        )
        result = EppResultData(
            code=1000,
            message="Command completed successfully",
            raw_response="<raw/>",
            result_data=contact,
        )
        output = self.cli_table.format_output(result)
        self.assertIn("[ EPP Response ]", output)
        self.assertIn("[ Contact Information: sh8013 ]", output)
        self.assertIn("jdoe@example.nz", output)
        self.assertIn("John Doe", output)
        self.assertIn("ACME Corp", output)
        self.assertIn("123 Main St", output)
        self.assertIn("+64.41234567", output)
        self.assertIn("email", output)

    def test_table_format_host_data(self) -> None:
        """Verify TABLE output format renders Host Information sub-table with IP addresses."""
        host_data = HostData(
            host_name="ns1.example.nz",
            address=[
                IPAddressData(address="192.0.2.1", ip="v4"),
                IPAddressData(address="2001:db8::1", ip="v6"),
            ],
            status=["ok"],
        )
        result = EppResultData(
            code=1000,
            message="Command completed successfully",
            raw_response="<raw/>",
            result_data=host_data,
        )
        output = self.cli_table.format_output(result)
        self.assertIn("[ EPP Response ]", output)
        self.assertIn("[ Host Information: ns1.example.nz ]", output)
        self.assertIn("192.0.2.1 (v4)", output)
        self.assertIn("2001:db8::1 (v6)", output)
        self.assertIn("ok", output)

    def test_table_format_none_result_data(self) -> None:
        """Verify TABLE output format renders only Master EPP table when result_data is None."""
        result = EppResultData(
            code=1000,
            message="Command completed successfully",
            raw_response="<raw/>",
            result_data=None,
        )
        output = self.cli_table.format_output(result)
        self.assertIn("[ EPP Response ]", output)
        self.assertIn("1000", output)
        # No payload sub-table should be present
        self.assertNotIn("[ Check Results ]", output)
        self.assertNotIn("[ Domain Information", output)
        self.assertNotIn("[ Result Data ]", output)

    def test_table_format_no_pretty_tsv(self) -> None:
        """Verify TABLE output format with --no-pretty emits plain tab-separated (TSV) format."""
        check_data = {"example.nz": {"avail": True, "reason": None}}
        result = EppResultData(
            code=1000,
            message="Command completed successfully",
            raw_response="<raw_response_secret/>",
            result_data=check_data,
            client_transaction_id="cl-001",
        )
        output = self.cli_table_raw.format_output(result)
        self.assertIsInstance(output, str)
        # Verify TSV structure for master and sub-table sections
        lines = output.splitlines()
        self.assertIn("Field\tValue", lines)
        self.assertIn("code\t1000", lines)
        self.assertIn("client_transaction_id\tcl-001", lines)
        self.assertIn("Entity\tAvailable\tReason", lines)
        self.assertIn("example.nz\tYes\tNone", lines)
        # Omission of raw_response
        self.assertNotIn("raw_response", output)
        self.assertNotIn("<raw_response_secret/>", output)
        # No ASCII box decorations in TSV
        self.assertNotIn("+--", output)
        self.assertNotIn("| Field", output)

    def test_table_format_cell_wrapping(self) -> None:
        """Verify format_table wraps cells and preserves content when max_width is constrained."""
        long_message = "This is a very long error message that exceeds standard narrow column limits."
        result = EppResultData(
            code=2000,
            message=long_message,
            raw_response="<raw/>",
            result_data={"key": "value"},
        )
        # Force table formatting with narrow max_width
        output = format_table(result, max_width=50)
        self.assertIn("Field", output)
        self.assertIn("Value", output)
        # Content should still be present despite cell wrapping across lines
        self.assertIn("This is a very long", output)
        self.assertIn("exceeds standard", output)
        # Grid border and row lines must not exceed the max width
        for line in output.splitlines():
            if line.startswith(("+", "|")):
                self.assertLessEqual(len(line), 50)

    def test_table_format_fallback_to_xml(self) -> None:
        """Verify TABLE output format falls back to XML when input is not an EppResultData instance."""
        raw_xml = '<?xml version="1.0"?><greeting><svID>TestRegistry</svID></greeting>'
        output = self.cli_table.format_output(raw_xml)
        self.assertIn("<greeting>", output)
        self.assertIn("<svID>", output)
        self.assertIn("TestRegistry", output)

    def test_table_format_fallback_on_exception(self) -> None:
        """Verify TABLE output format falls back to XML if table formatting raises an unexpected error."""
        result = EppResultData(
            code=1000,
            message="Success",
            raw_response="<fallback_xml/>",
            result_data=None,
        )
        with patch("pyepp.cli.cli.format_table", side_effect=RuntimeError("formatting crash")):
            output = self.cli_table.format_output(result)
            self.assertIn("<fallback_xml/>", output)

    def test_table_format_case_insensitivity(self) -> None:
        """Verify output_format lowercase 'table' is normalized to 'TABLE'."""
        cli = PyEppCli(
            "localhost",
            "700",
            None,
            None,
            "user",
            "pass",
            [],
            output_format="table",
            no_pretty=False,
        )
        self.assertEqual(cli.output_format, "TABLE")
        result = EppResultData(
            code=1000,
            message="Success",
            raw_response="<raw/>",
            result_data=None,
        )
        output = cli.format_output(result)
        self.assertIn("| Field", output)
        self.assertIn("1000", output)

    def test_cli_runner_table_flags_and_output(self) -> None:
        """Verify CLI runner accepts -o table, --o table, --output-format table and outputs ASCII table."""
        runner = CliRunner()
        check_data = {
            "domain1.nz": {"avail": False, "reason": "Registered"},
        }
        mock_result = EppResultData(
            code=1000,
            message="Command completed successfully",
            raw_response="<raw/>",
            result_data=check_data,
        )

        for flag in ["-o", "--o", "--output-format"]:
            with patch("pyepp.domain.Domain.check", return_value=mock_result):
                result = runner.invoke(
                    pyepp_cli,
                    [
                        "--server",
                        "localhost",
                        "--port",
                        "700",
                        "--user",
                        "user",
                        "--password",
                        "pass",
                        flag,
                        "table",
                        "--dry-run",
                        "domain",
                        "check",
                        "domain1.nz",
                    ],
                )
                self.assertEqual(result.exit_code, 0)
                self.assertIn("| Field", result.output)
                self.assertIn("| Value", result.output)
                self.assertIn("1000", result.output)

    def test_cli_runner_table_no_pretty(self) -> None:
        """Verify CLI runner with -o table --no-pretty outputs TSV format."""
        runner = CliRunner()
        check_data = {
            "domain1.nz": {"avail": True, "reason": None},
        }
        mock_result = EppResultData(
            code=1000,
            message="Command completed successfully",
            raw_response="<raw/>",
            result_data=check_data,
        )

        with patch("pyepp.domain.Domain.check", return_value=mock_result):
            result = runner.invoke(
                pyepp_cli,
                [
                    "--server",
                    "localhost",
                    "--port",
                    "700",
                    "--user",
                    "user",
                    "--password",
                    "pass",
                    "-o",
                    "table",
                    "--no-pretty",
                    "--dry-run",
                    "domain",
                    "check",
                    "domain1.nz",
                ],
            )
            self.assertEqual(result.exit_code, 0)
            self.assertIn("Field\tValue", result.output)
            self.assertIn("code\t1000", result.output)


class CliConfigTest(unittest.TestCase):
    """
    Test suite for reading CLI configuration and default output format.
    """

    def tearDown(self) -> None:
        # Reset config to defaults
        load_config()

    def test_load_config_default_output_format_is_xml(self) -> None:
        """Verify load_config defaults output_format to XML when not present in config."""
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            tf.write("[pyepp]\nserver=localhost\nport=700\nuser=u\npassword=p\n")
            cfg_path = tf.name

        try:
            load_config(cfg_path)
            self.assertEqual(CONTEXT_SETTINGS["default_map"]["output_format"], "XML")
        finally:
            if os.path.exists(cfg_path):
                os.remove(cfg_path)

    def test_load_config_reads_output_format(self) -> None:
        """Verify load_config sets output_format from configuration file and applies to CLI."""
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            tf.write("[pyepp]\nserver=localhost\nport=700\nuser=u\npassword=p\noutput_format=TABLE\n")
            cfg_path = tf.name

        try:
            load_config(cfg_path)
            self.assertEqual(CONTEXT_SETTINGS["default_map"]["output_format"], "TABLE")

            runner = CliRunner()
            check_data = {"test.nz": {"avail": True, "reason": None}}
            mock_result = EppResultData(
                code=1000,
                message="Command completed successfully",
                raw_response="<raw/>",
                result_data=check_data,
            )
            with patch("pyepp.domain.Domain.check", return_value=mock_result):
                # Run WITHOUT specifying -o flag; should pick up TABLE from config.ini
                result = runner.invoke(
                    pyepp_cli,
                    [
                        "--dry-run",
                        "domain",
                        "check",
                        "test.nz",
                    ],
                )
                self.assertEqual(result.exit_code, 0)
                self.assertIn("[ EPP Response ]", result.output)
                self.assertIn("[ Check Results ]", result.output)
                self.assertIn("test.nz", result.output)
        finally:
            if os.path.exists(cfg_path):
                os.remove(cfg_path)

    def test_load_config_cli_flag_overrides_config_file(self) -> None:
        """Verify explicit CLI -o flag overrides output_format in configuration file."""
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            tf.write("[pyepp]\nserver=localhost\nport=700\nuser=u\npassword=p\noutput_format=TABLE\n")
            cfg_path = tf.name

        try:
            load_config(cfg_path)
            runner = CliRunner()
            check_data = {"test.nz": {"avail": True, "reason": None}}
            mock_result = EppResultData(
                code=1000,
                message="Command completed successfully",
                raw_response="<raw/>",
                result_data=check_data,
            )
            with patch("pyepp.domain.Domain.check", return_value=mock_result):
                # Pass -o MIN to override TABLE config
                result = runner.invoke(
                    pyepp_cli,
                    [
                        "-o",
                        "MIN",
                        "--dry-run",
                        "domain",
                        "check",
                        "test.nz",
                    ],
                )
                self.assertEqual(result.exit_code, 0)
                self.assertNotIn("[ EPP Response ]", result.output)
                self.assertIn(pprint.pformat(check_data), result.output)
        finally:
            if os.path.exists(cfg_path):
                os.remove(cfg_path)


if __name__ == "__main__":
    unittest.main()
