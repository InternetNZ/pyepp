"""
CLI Domain command unit tests
"""
import unittest
from unittest.mock import MagicMock
from click.testing import CliRunner

from pyepp.cli.domain import domain_create, domain_update
from pyepp.cli.__main__ import pyepp_cli


class CliDomainTest(unittest.TestCase):
    """
    Test suite for domain CLI commands.
    """

    def setUp(self) -> None:
        self.runner = CliRunner()

    def test_domain_update_statuses(self) -> None:
        """Verify domain_update passes add_statuses and remove_statuses."""
        mock_obj = MagicMock()

        result = self.runner.invoke(
            domain_update,
            [
                "example.com",
                "--add-status",
                "clientHold",
                "Reason",
                "--remove-status",
                "clientUpdateProhibited",
            ],
            obj=mock_obj,
        )

        self.assertEqual(result.exit_code, 0)
        mock_obj.update.assert_called_once()
        call_kwargs = mock_obj.update.call_args.kwargs
        self.assertEqual(call_kwargs["add_statuses"], (("clientHold", "Reason"),))
        self.assertEqual(call_kwargs["remove_statuses"], ("clientUpdateProhibited",))

    def test_cli_extension_envvar(self) -> None:
        """Verify CLI loads extension from PYEPP_EXTENSION."""
        param = next(p for p in pyepp_cli.params if p.name == "extension")
        self.assertEqual(param.envvar, "PYEPP_EXTENSION")

    def test_cli_dry_run_domain_info(self) -> None:
        """Verify CLI with --dry-run returns XML command without connecting to server."""
        result = self.runner.invoke(
            pyepp_cli,
            [
                "--server",
                "localhost",
                "--port",
                "700",
                "--user",
                "testuser",
                "--password",
                "testpass",
                "-o",
                "XML",
                "--dry-run",
                "domain",
                "info",
                "example.com",
            ],
        )
        self.assertEqual(result.exit_code, 0)
        self.assertIn("<domain:info", result.output)
        self.assertIn("example.com", result.output)

    def test_cli_dry_run_hello(self) -> None:
        """Verify CLI with --dry-run hello returns hello XML without connecting."""
        result = self.runner.invoke(
            pyepp_cli,
            [
                "--server",
                "localhost",
                "--port",
                "700",
                "--user",
                "testuser",
                "--password",
                "testpass",
                "--dry-run",
                "hello",
            ],
        )
        self.assertEqual(result.exit_code, 0)
        self.assertIn("<hello/>", result.output)

    def test_domain_create_multiple_contacts(self) -> None:
        """Verify domain_create passes repeatable admin, tech, billing, and ns-host options."""
        mock_obj = MagicMock()

        result = self.runner.invoke(
            domain_create,
            [
                "example.nz",
                "--registrant",
                "reg-1",
                "--admin",
                "adm-1",
                "--admin",
                "adm-2",
                "--tech",
                "tech-1",
                "--tech",
                "tech-2",
                "--billing",
                "bill-1",
                "--billing",
                "bill-2",
                "--ns-host",
                "ns1.example.nz",
                "--ns-host",
                "ns2.example.nz",
            ],
            obj=mock_obj,
        )

        self.assertEqual(result.exit_code, 0)
        mock_obj.create.assert_called_once()
        domain_data = mock_obj.create.call_args[0][0]
        self.assertEqual(domain_data.domain_name, "example.nz")
        self.assertEqual(domain_data.registrant, "reg-1")
        self.assertEqual(domain_data.admin, ["adm-1", "adm-2"])
        self.assertEqual(domain_data.tech, ["tech-1", "tech-2"])
        self.assertEqual(domain_data.billing, ["bill-1", "bill-2"])
        self.assertEqual(domain_data.host, ["ns1.example.nz", "ns2.example.nz"])

    def test_cli_dry_run_domain_create_multiple_contacts(self) -> None:
        """Verify CLI domain create with --dry-run outputs multiple contacts cleanly."""
        result = self.runner.invoke(
            pyepp_cli,
            [
                "--server",
                "localhost",
                "--port",
                "700",
                "--user",
                "testuser",
                "--password",
                "testpass",
                "-o",
                "XML",
                "--no-pretty",
                "--dry-run",
                "domain",
                "create",
                "example.nz",
                "--registrant",
                "reg-1",
                "--admin",
                "adm-1",
                "--admin",
                "adm-2",
                "--tech",
                "tech-1",
                "--billing",
                "bill-1",
            ],
        )
        self.assertEqual(result.exit_code, 0)
        self.assertIn('<domain:contact type="admin">adm-1</domain:contact>', result.output)
        self.assertIn('<domain:contact type="admin">adm-2</domain:contact>', result.output)
        self.assertIn('<domain:contact type="tech">tech-1</domain:contact>', result.output)
        self.assertIn('<domain:contact type="billing">bill-1</domain:contact>', result.output)
        self.assertNotIn("['adm-1'", result.output)
