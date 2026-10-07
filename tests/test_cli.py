"""
CLI base module and decorator unit tests.
"""
import logging
import unittest
from unittest.mock import MagicMock

from pyepp.cli.cli import login_logout
from pyepp.epp import EppCommunicatorException


class DummyCli:
    """Dummy CLI class to test the login_logout decorator."""

    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.connect = MagicMock()
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

    def test_login_logout_dry_run_success(self) -> None:
        """Verify connect, login, and logout are skipped in dry-run mode."""
        cli = DummyCli(dry_run=True)

        result = cli.execute_command()

        self.assertEqual(result, "command_result")
        cli.connect.assert_not_called()
        cli.login.assert_not_called()
        cli.logout.assert_not_called()

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
        """Verify that if connect fails, logout is not called and the exception propagates."""
        cli = DummyCli(dry_run=False)
        cli.connect.side_effect = EppCommunicatorException("Connection failed")

        with self.assertRaises(EppCommunicatorException) as context:
            cli.execute_command()

        self.assertEqual(str(context.exception), "Connection failed")
        cli.connect.assert_called_once()
        cli.login.assert_not_called()
        cli.logout.assert_not_called()

    def test_login_logout_login_fails(self) -> None:
        """Verify that if login fails, logout is not called and the exception propagates."""
        cli = DummyCli(dry_run=False)
        cli.login.side_effect = EppCommunicatorException("Authentication failed")

        with self.assertRaises(EppCommunicatorException) as context:
            cli.execute_command()

        self.assertEqual(str(context.exception), "Authentication failed")
        cli.connect.assert_called_once()
        cli.login.assert_called_once()
        cli.logout.assert_not_called()


if __name__ == "__main__":
    unittest.main()
