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

    def test_contact_update_address_with_omitted_and_empty_streets(self) -> None:
        """Verify contact update CLI sets street fields appropriately when omitted or empty."""
        mock_obj = MagicMock()
        mock_obj.update.return_value = "Success"

        # Case 1: omitted street-2 and street-3
        result = self.runner.invoke(
            contact_update,
            [
                "test-contact-1",
                "--street-1",
                "123 Main St",
                "--city",
                "Wellington",
                "--country-code",
                "NZ",
            ],
            obj=mock_obj,
        )
        self.assertEqual(result.exit_code, 0)
        contact_arg = mock_obj.update.call_args[0][0]
        self.assertEqual(contact_arg.postal_info.address.street_1, "123 Main St")
        self.assertIsNone(contact_arg.postal_info.address.street_2)
        self.assertIsNone(contact_arg.postal_info.address.street_3)

        mock_obj.reset_mock()

        # Case 2: explicitly empty street-2 to clear secondary line
        result = self.runner.invoke(
            contact_update,
            [
                "test-contact-1",
                "--street-1",
                "123 Main St",
                "--street-2",
                "",
                "--city",
                "Wellington",
                "--country-code",
                "NZ",
            ],
            obj=mock_obj,
        )
        self.assertEqual(result.exit_code, 0)
        contact_arg = mock_obj.update.call_args[0][0]
        self.assertEqual(contact_arg.postal_info.address.street_1, "123 Main St")
        self.assertEqual(contact_arg.postal_info.address.street_2, "")
        self.assertIsNone(contact_arg.postal_info.address.street_3)

    def test_contact_update_address_sparse_streets_raises_usage_error(self) -> None:
        """Verify contact update CLI rejects sparse street arguments with UsageError."""
        mock_obj = MagicMock()

        # Omitted street-1 but provided street-2
        result = self.runner.invoke(
            contact_update,
            [
                "test-contact-1",
                "--street-2",
                "Suite 2",
                "--city",
                "Wellington",
                "--country-code",
                "NZ",
            ],
            obj=mock_obj,
        )
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn(
            "Cannot specify --street-2 or --street-3 when preceding street lines are omitted.",
            result.output,
        )

        # Gap: street-1 and street-3 but omitted street-2
        result = self.runner.invoke(
            contact_update,
            [
                "test-contact-1",
                "--street-1",
                "123 Main St",
                "--street-3",
                "",
                "--city",
                "Wellington",
                "--country-code",
                "NZ",
            ],
            obj=mock_obj,
        )
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn(
            "Cannot specify --street-3 when --street-2 is omitted.",
            result.output,
        )

    def test_contact_create_address_empty_street_preceding_populated_raises_usage_error(
        self,
    ) -> None:
        """Verify contact create CLI rejects empty street options preceding populated ones."""
        mock_obj = MagicMock()

        result = self.runner.invoke(
            contact_create,
            [
                "test-contact-1",
                "--name",
                "Test",
                "--email",
                "test@example.com",
                "--street-1",
                "",
                "--street-2",
                "Suite 2",
                "--city",
                "Wellington",
                "--country-code",
                "NZ",
            ],
            obj=mock_obj,
        )
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn(
            "Cannot specify --street-2 or --street-3 when --street-1 is empty.",
            result.output,
        )

    def test_contact_create_address_sparse_streets_raises_usage_error(
        self,
    ) -> None:
        """Verify contact create CLI rejects sparse street arguments with UsageError."""
        mock_obj = MagicMock()

        # Omitted street-1 but provided street-2
        result = self.runner.invoke(
            contact_create,
            [
                "test-contact-1",
                "--name",
                "Test",
                "--email",
                "test@example.com",
                "--street-2",
                "Suite 2",
                "--city",
                "Wellington",
                "--country-code",
                "NZ",
            ],
            obj=mock_obj,
        )
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn(
            "Cannot specify --street-2 or --street-3 when preceding street lines are omitted.",
            result.output,
        )

        # Gap: street-1 and street-3 but omitted street-2
        result = self.runner.invoke(
            contact_create,
            [
                "test-contact-1",
                "--name",
                "Test",
                "--email",
                "test@example.com",
                "--street-1",
                "123 Main St",
                "--street-3",
                "Suite 3",
                "--city",
                "Wellington",
                "--country-code",
                "NZ",
            ],
            obj=mock_obj,
        )
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn(
            "Cannot specify --street-3 when --street-2 is omitted.",
            result.output,
        )

    def test_contact_create_address_empty_street_2_preceding_populated_street_3_raises_usage_error(
        self,
    ) -> None:
        """Verify contact create CLI rejects empty street_2 option preceding populated street_3."""
        mock_obj = MagicMock()

        result = self.runner.invoke(
            contact_create,
            [
                "test-contact-1",
                "--name",
                "Test",
                "--email",
                "test@example.com",
                "--street-1",
                "123 Main St",
                "--street-2",
                "",
                "--street-3",
                "Building B",
                "--city",
                "Wellington",
                "--country-code",
                "NZ",
            ],
            obj=mock_obj,
        )
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn(
            "Cannot specify --street-3 when --street-2 is empty.",
            result.output,
        )

    def test_contact_create_with_privacy(self) -> None:
        """Verify contact create passes privacy elements to ContactData."""
        mock_obj = MagicMock()
        mock_obj.create.return_value = "Success"

        result = self.runner.invoke(
            contact_create,
            [
                "test-contact-1",
                "--name",
                "Test",
                "--email",
                "test@example.com",
                "--city",
                "Wellington",
                "--country-code",
                "NZ",
                "--privacy",
                "voice",
                "--privacy",
                "email",
            ],
            obj=mock_obj,
        )
        self.assertEqual(result.exit_code, 0)
        mock_obj.create.assert_called_once()
        contact_arg = mock_obj.create.call_args[0][0]
        self.assertEqual(contact_arg.privacy, ["voice", "email"])

    def test_contact_update_with_privacy(self) -> None:
        """Verify contact update passes privacy elements to ContactData."""
        mock_obj = MagicMock()
        mock_obj.update.return_value = "Success"

        result = self.runner.invoke(
            contact_update,
            [
                "test-contact-1",
                "--privacy",
                "voice",
                "--privacy",
                "addr",
            ],
            obj=mock_obj,
        )
        self.assertEqual(result.exit_code, 0)
        mock_obj.update.assert_called_once()
        contact_arg = mock_obj.update.call_args[0][0]
        self.assertEqual(contact_arg.privacy, ["voice", "addr"])

    def test_contact_create_help_shows_privacy_options(self) -> None:
        """Verify contact create --help displays --privacy and valid options."""
        result = self.runner.invoke(contact_create, ["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("--privacy", result.output)
        self.assertIn("name", result.output)
        self.assertIn("org", result.output)
        self.assertIn("addr", result.output)
        self.assertIn("voice", result.output)
        self.assertIn("fax", result.output)
        self.assertIn("email", result.output)

    def test_contact_update_help_shows_privacy_options(self) -> None:
        """Verify contact update --help displays --privacy and valid options."""
        result = self.runner.invoke(contact_update, ["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("--privacy", result.output)
        self.assertIn("name", result.output)
        self.assertIn("org", result.output)
        self.assertIn("addr", result.output)
        self.assertIn("voice", result.output)
        self.assertIn("fax", result.output)
        self.assertIn("email", result.output)


if __name__ == "__main__":
    unittest.main()
