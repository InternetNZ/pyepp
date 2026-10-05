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
        """Verify contact update accepts --type int with complete postal info."""
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
                "--city",
                "Tokyo",
                "--country-code",
                "JP",
            ],
            obj=mock_obj,
        )

        self.assertEqual(result.exit_code, 0)
        mock_obj.update.assert_called_once()
        contact_arg = mock_obj.update.call_args[0][0]
        self.assertEqual(contact_arg.postal_info.type, "int")
        self.assertEqual(contact_arg.postal_info.name, "Updated Name")
        self.assertEqual(contact_arg.postal_info.address.city, "Tokyo")
        self.assertEqual(contact_arg.postal_info.address.country_code, "JP")

    def test_contact_update_int_type_missing_postal_fields_raises_error(self) -> None:
        """Verify contact update errors when int postal update is missing name, city, or country-code."""
        mock_obj = MagicMock()

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

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn(
            "Updating postal info with type 'int' requires --name, --city, and --country-code.",
            result.output,
        )
        mock_obj.update.assert_not_called()

    def test_contact_update_name_only_allowed(self) -> None:
        """Verify contact update allows updating name without requiring address fields."""
        mock_obj = MagicMock()
        mock_obj.update.return_value = "Success"

        result = self.runner.invoke(
            contact_update,
            [
                "test-contact-2",
                "--name",
                "Updated Name",
            ],
            obj=mock_obj,
        )

        self.assertEqual(result.exit_code, 0)
        mock_obj.update.assert_called_once()
        contact_arg = mock_obj.update.call_args[0][0]
        self.assertEqual(contact_arg.postal_info.name, "Updated Name")
        self.assertIsNone(contact_arg.postal_info.address)

    def test_contact_update_address_missing_city_or_cc_raises_error(self) -> None:
        """Verify contact update errors when updating address without city or country-code."""
        mock_obj = MagicMock()

        result = self.runner.invoke(
            contact_update,
            [
                "test-contact-2",
                "--street-1",
                "123 Main St",
            ],
            obj=mock_obj,
        )

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn(
            "Updating contact address requires --city and --country-code.",
            result.output,
        )
        mock_obj.update.assert_not_called()

    def test_contact_update_without_postal_info(self) -> None:
        """Verify contact update without postal fields leaves postal_info as None."""
        mock_obj = MagicMock()
        mock_obj.update.return_value = "Success"

        result = self.runner.invoke(
            contact_update,
            [
                "test-contact-2",
                "--phone",
                "+64.12345678",
            ],
            obj=mock_obj,
        )

        self.assertEqual(result.exit_code, 0)
        mock_obj.update.assert_called_once()
        contact_arg = mock_obj.update.call_args[0][0]
        self.assertIsNone(contact_arg.postal_info)
        self.assertEqual(contact_arg.phone, "+64.12345678")


if __name__ == "__main__":
    unittest.main()
