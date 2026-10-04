"""
CLI Contact command unit tests
"""
import unittest
from unittest.mock import MagicMock
from click.testing import CliRunner

from pyepp.cli.contact import contact_create, contact_update


class CliContactTest(unittest.TestCase):
    """
    Test suite for contact CLI commands.
    """

    def setUp(self) -> None:
        self.runner = CliRunner()

    def test_contact_create_default_type(self) -> None:
        """Verify contact create defaults postal_info.type to 'loc'."""
        mock_obj = MagicMock()
        mock_obj.create.return_value = "Success"

        result = self.runner.invoke(
            contact_create,
            [
                "test-contact-1",
                "--name",
                "John Doe",
                "--email",
                "john@example.com",
                "--city",
                "Auckland",
                "--country-code",
                "NZ",
            ],
            obj=mock_obj,
        )

        self.assertEqual(result.exit_code, 0)
        mock_obj.create.assert_called_once()
        contact_arg = mock_obj.create.call_args[0][0]
        self.assertEqual(contact_arg.postal_info.type, "loc")

    def test_contact_create_int_type(self) -> None:
        """Verify contact create accepts --type int."""
        mock_obj = MagicMock()
        mock_obj.create.return_value = "Success"

        result = self.runner.invoke(
            contact_create,
            [
                "test-contact-2",
                "--name",
                "John Doe",
                "--email",
                "john@example.com",
                "--city",
                "Tokyo",
                "--country-code",
                "JP",
                "--type",
                "int",
            ],
            obj=mock_obj,
        )

        self.assertEqual(result.exit_code, 0)
        mock_obj.create.assert_called_once()
        contact_arg = mock_obj.create.call_args[0][0]
        self.assertEqual(contact_arg.postal_info.type, "int")

    def test_contact_update_int_type(self) -> None:
        """Verify contact update accepts --type int."""
        mock_obj = MagicMock()
        mock_obj.update.return_value = "Success"

        result = self.runner.invoke(
            contact_update,
            [
                "test-contact-2",
                "--type",
                "int",
                "--name",
                "Updated Name",
            ],
            obj=mock_obj,
        )

        self.assertEqual(result.exit_code, 0)
        mock_obj.update.assert_called_once()
        contact_arg = mock_obj.update.call_args[0][0]
        self.assertEqual(contact_arg.postal_info.type, "int")


if __name__ == "__main__":
    unittest.main()
