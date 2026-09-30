"""
CLI Host command unit tests
"""
import unittest
from unittest.mock import MagicMock
from click.testing import CliRunner

from pyepp.cli.host import host_update
from pyepp.host import IPAddressData


class CliHostTest(unittest.TestCase):
    """
    Test suite for host CLI commands.
    """

    def setUp(self) -> None:
        self.runner = CliRunner()

    def test_host_update_remove_ip_only(self) -> None:
        """Verify --remove-ip works without --add-ip."""
        mock_obj = MagicMock()
        mock_obj.update.return_value = "Success"

        result = self.runner.invoke(
            host_update,
            ["ns1.example.com", "--remove-ip", "192.0.2.1", "v4"],
            obj=mock_obj,
        )

        self.assertEqual(result.exit_code, 0)
        mock_obj.update.assert_called_once_with(
            "ns1.example.com",
            add_ip_address=None,
            remove_ip_address=[IPAddressData("192.0.2.1", "v4")],
            add_status=None,
            remove_status=None,
            new_host_name=None,
            client_transaction_id=None,
        )

    def test_host_update_remove_status_only(self) -> None:
        """Verify --remove-status works without --add-status."""
        mock_obj = MagicMock()
        mock_obj.update.return_value = "Success"

        result = self.runner.invoke(
            host_update,
            ["ns1.example.com", "--remove-status", "clientHold"],
            obj=mock_obj,
        )

        self.assertEqual(result.exit_code, 0)
        mock_obj.update.assert_called_once_with(
            "ns1.example.com",
            add_ip_address=None,
            remove_ip_address=None,
            add_status=None,
            remove_status=["clientHold"],
            new_host_name=None,
            client_transaction_id=None,
        )

    def test_host_update_add_and_remove(self) -> None:
        """Verify --add-ip, --remove-ip, --add-status, --remove-status together."""
        mock_obj = MagicMock()
        mock_obj.update.return_value = "Success"

        result = self.runner.invoke(
            host_update,
            [
                "ns1.example.com",
                "--add-ip",
                "192.0.2.2",
                "v4",
                "--remove-ip",
                "192.0.2.1",
                "v4",
                "--add-status",
                "clientUpdateProhibited",
                "--remove-status",
                "clientHold",
                "--new-host-name",
                "ns2.example.com",
                "--client-transaction-id",
                "test-trid-123",
            ],
            obj=mock_obj,
        )

        self.assertEqual(result.exit_code, 0)
        mock_obj.update.assert_called_once_with(
            "ns1.example.com",
            add_ip_address=[IPAddressData("192.0.2.2", "v4")],
            remove_ip_address=[IPAddressData("192.0.2.1", "v4")],
            add_status=["clientUpdateProhibited"],
            remove_status=["clientHold"],
            new_host_name="ns2.example.com",
            client_transaction_id="test-trid-123",
        )
