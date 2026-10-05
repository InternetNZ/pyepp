"""
CLI Domain command unit tests
"""
import unittest
from unittest.mock import MagicMock
from click.testing import CliRunner

from pyepp.cli.domain import domain_update
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
