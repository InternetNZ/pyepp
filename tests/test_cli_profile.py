"""
CLI Profile command unit tests.
"""

import os
import tempfile
import unittest
from unittest.mock import patch
from click.testing import CliRunner

from pyepp import EppResultData
from pyepp.cli.__main__ import pyepp_cli, load_config


class CliProfileTest(unittest.TestCase):
    """Test suite for CLI profile subcommands and CLI profile flag integration."""

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
client_cert = /path/to/cert.pem
client_key = /path/to/key.pem
"""
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            tf.write(self.ini_content)
            self.cfg_path = tf.name

    def tearDown(self) -> None:
        if os.path.exists(self.cfg_path):
            os.remove(self.cfg_path)
        load_config()

    def test_cli_profile_list(self) -> None:
        """Verify 'pyepp profile list' outputs a formatted table of configured profiles."""
        result = self.runner.invoke(
            pyepp_cli,
            ["-c", self.cfg_path, "profile", "list"],
        )
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Profile", result.output)
        self.assertIn("Server", result.output)
        self.assertIn("default", result.output)
        self.assertIn("ote", result.output)
        self.assertIn("prod", result.output)
        self.assertIn("epp.ote.registry.net.nz", result.output)
        self.assertIn("epp.registry.net.nz", result.output)

    def test_cli_profile_show_default(self) -> None:
        """Verify 'pyepp profile show' without arguments displays default profile."""
        result = self.runner.invoke(
            pyepp_cli,
            ["-c", self.cfg_path, "profile", "show"],
        )
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Profile: default", result.output)
        self.assertIn("Port:          700", result.output)
        self.assertIn("Output Format: TABLE", result.output)

    def test_cli_profile_show_named_profile_masks_password(self) -> None:
        """Verify 'pyepp profile show <name>' displays profile details with masked password."""
        result = self.runner.invoke(
            pyepp_cli,
            ["-c", self.cfg_path, "profile", "show", "ote"],
        )
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Profile: ote", result.output)
        self.assertIn("Server:        epp.ote.registry.net.nz", result.output)
        self.assertIn("User:          ote_user", result.output)
        self.assertIn("Password:      ********", result.output)
        self.assertNotIn("ote_secret_password", result.output)
        self.assertIn("urn:ietf:params:xml:ns:secDNS-1.1", result.output)

    def test_cli_profile_show_secrets_unmasks_password(self) -> None:
        """Verify '--show-secrets' displays unmasked password."""
        result = self.runner.invoke(
            pyepp_cli,
            ["-c", self.cfg_path, "profile", "show", "ote", "--show-secrets"],
        )
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Password:      ote_secret_password", result.output)

    def test_cli_profile_show_non_existent_profile(self) -> None:
        """Verify 'pyepp profile show non_existent' reports an error."""
        result = self.runner.invoke(
            pyepp_cli,
            ["-c", self.cfg_path, "profile", "show", "unknown_profile"],
        )
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Profile 'unknown_profile' not found", result.output)

    def test_cli_execution_with_profile_flag(self) -> None:
        """Verify CLI commands run with -p <profile> pick up credentials and connection settings."""
        mock_result = EppResultData(
            code=1000,
            message="Command completed successfully",
            raw_response="<raw/>",
            result_data={"test.nz": {"avail": True, "reason": None}},
        )

        with patch("pyepp.domain.Domain.check", return_value=mock_result):
            result = self.runner.invoke(
                pyepp_cli,
                [
                    "-c",
                    self.cfg_path,
                    "-p",
                    "ote",
                    "--dry-run",
                    "domain",
                    "check",
                    "test.nz",
                ],
            )
            self.assertEqual(result.exit_code, 0)
            self.assertIn("test.nz", result.output)

    def test_cli_flag_overrides_profile_setting(self) -> None:
        """Verify explicit CLI option overrides the value configured in the profile."""
        mock_result = EppResultData(
            code=1000,
            message="Command completed successfully",
            raw_response="<raw/>",
            result_data={"test.nz": {"avail": True, "reason": None}},
        )

        with patch("pyepp.cli.cli.PyEppCli") as mock_cli_cls:
            instance = mock_cli_cls.return_value
            instance.execute = lambda *args, **kwargs: "<raw/>"

            result = self.runner.invoke(
                pyepp_cli,
                [
                    "-c",
                    self.cfg_path,
                    "-p",
                    "ote",
                    "--user",
                    "cli_override_user",
                    "--dry-run",
                    "domain",
                    "check",
                    "test.nz",
                ],
            )
            self.assertEqual(result.exit_code, 0)
            # Check user was overridden in PyEppCli instantiation
            called_args = mock_cli_cls.call_args[0]
            # server=args[0], port=args[1], client_cert=args[2], client_key=args[3], user=args[4]
            self.assertEqual(called_args[0], "epp.ote.registry.net.nz")
            self.assertEqual(called_args[4], "cli_override_user")

    def test_cli_env_var_overrides_profile_setting(self) -> None:
        """Verify environment variables take precedence over profile values."""
        with patch("pyepp.cli.cli.PyEppCli") as mock_cli_cls:
            instance = mock_cli_cls.return_value
            instance.execute = lambda *args, **kwargs: "<raw/>"

            result = self.runner.invoke(
                pyepp_cli,
                [
                    "-c",
                    self.cfg_path,
                    "-p",
                    "ote",
                    "--dry-run",
                    "domain",
                    "check",
                    "test.nz",
                ],
                env={"PYEPP_SERVER": "env.override.example.com"},
            )
            self.assertEqual(result.exit_code, 0)
            called_args = mock_cli_cls.call_args[0]
            # server=args[0], user=args[4], password=args[5]
            self.assertEqual(called_args[0], "env.override.example.com")
            self.assertEqual(called_args[4], "ote_user")
            self.assertEqual(called_args[5], "ote_secret_password")

    def test_cli_env_var_preserved_when_profile_omits_field(self) -> None:
        """Verify environment variable is preserved when selected profile omits the field."""
        # Create a profile that omits password
        no_pwd_ini = """[no_pwd]
server = epp.no-pwd.registry.net.nz
user = no_pwd_user
port = 700
"""
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            tf.write(no_pwd_ini)
            no_pwd_cfg = tf.name

        try:
            with patch("pyepp.cli.cli.PyEppCli") as mock_cli_cls:
                instance = mock_cli_cls.return_value
                instance.execute = lambda *args, **kwargs: "<raw/>"

                result = self.runner.invoke(
                    pyepp_cli,
                    [
                        "-c",
                        no_pwd_cfg,
                        "-p",
                        "no_pwd",
                        "--dry-run",
                        "domain",
                        "check",
                        "test.nz",
                    ],
                    env={"PYEPP_PASSWORD": "env_secret_password"},
                )
                self.assertEqual(result.exit_code, 0)
                called_args = mock_cli_cls.call_args[0]
                self.assertEqual(called_args[0], "epp.no-pwd.registry.net.nz")
                self.assertEqual(called_args[4], "no_pwd_user")
                self.assertEqual(called_args[5], "env_secret_password")
        finally:
            if os.path.exists(no_pwd_cfg):
                os.remove(no_pwd_cfg)

    def test_cli_flag_overrides_env_var_and_profile(self) -> None:
        """Verify CLI flag takes highest precedence over both env var and profile."""
        with patch("pyepp.cli.cli.PyEppCli") as mock_cli_cls:
            instance = mock_cli_cls.return_value
            instance.execute = lambda *args, **kwargs: "<raw/>"

            result = self.runner.invoke(
                pyepp_cli,
                [
                    "-c",
                    self.cfg_path,
                    "-p",
                    "ote",
                    "--server",
                    "flag.override.example.com",
                    "--dry-run",
                    "domain",
                    "check",
                    "test.nz",
                ],
                env={"PYEPP_SERVER": "env.override.example.com"},
            )
            self.assertEqual(result.exit_code, 0)
            called_args = mock_cli_cls.call_args[0]
            self.assertEqual(called_args[0], "flag.override.example.com")

    def test_cli_missing_required_params_error(self) -> None:
        """Verify error message when no profile and no server flags are provided."""
        # Use an empty temp config file
        with tempfile.NamedTemporaryFile("w", delete=False) as empty_tf:
            empty_cfg = empty_tf.name

        try:
            result = self.runner.invoke(
                pyepp_cli,
                ["-c", empty_cfg, "--dry-run", "domain", "check", "test.nz"],
            )
            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("Missing required parameter(s)", result.output)
            self.assertIn("--server", result.output)
        finally:
            if os.path.exists(empty_cfg):
                os.remove(empty_cfg)

    def test_cli_load_config_sanitizes_invalid_output_format(self) -> None:
        """Verify load_config sanitizes invalid output_format to XML so Click does not crash."""
        bad_format_ini = """[default]
server = epp.registry.net.nz
output_format = INVALID_FORMAT
"""
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            tf.write(bad_format_ini)
            bad_cfg = tf.name

        try:
            load_config(bad_cfg)
            # Invoking profile list with valid cfg must not fail with Click choice error
            result = self.runner.invoke(
                pyepp_cli,
                ["-c", self.cfg_path, "profile", "list"],
            )
            self.assertEqual(result.exit_code, 0)
            self.assertIn("Profile", result.output)
        finally:
            if os.path.exists(bad_cfg):
                os.remove(bad_cfg)
            load_config()

    def test_cli_profile_with_invalid_output_format_rejected(self) -> None:
        """Verify selecting a profile with invalid output_format raises a Click BadParameter error."""
        bad_format_ini = """[bad_fmt]
server = epp.registry.net.nz
user = test_user
password = test_pass
port = 700
output_format = INVALID_FORMAT
"""
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            tf.write(bad_format_ini)
            bad_cfg = tf.name

        try:
            result = self.runner.invoke(
                pyepp_cli,
                [
                    "-c",
                    bad_cfg,
                    "-p",
                    "bad_fmt",
                    "--dry-run",
                    "domain",
                    "check",
                    "test.nz",
                ],
            )
            self.assertEqual(result.exit_code, 2)
            self.assertIn("Invalid value for '-o' / '--output-format'", result.output)
            self.assertIn("INVALID_FORMAT", result.output)
        finally:
            if os.path.exists(bad_cfg):
                os.remove(bad_cfg)

    def test_cli_profile_list_allowed_with_invalid_output_format(self) -> None:
        """Verify profile list command succeeds even if a profile has an invalid output_format."""
        bad_format_ini = """[bad_fmt]
server = epp.registry.net.nz
output_format = NOT_A_FORMAT
"""
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            tf.write(bad_format_ini)
            bad_cfg = tf.name

        try:
            result = self.runner.invoke(
                pyepp_cli,
                ["-c", bad_cfg, "profile", "list"],
            )
            self.assertEqual(result.exit_code, 0)
            self.assertIn("bad_fmt", result.output)
        finally:
            if os.path.exists(bad_cfg):
                os.remove(bad_cfg)

    def test_cli_profile_overrides_default_truthy_booleans(self) -> None:
        """Verify named profile with falsy booleans overrides [default] profile's truthy booleans."""
        ini_content = """[default]
server = epp.default.net.nz
user = default_user
password = default_pass
port = 700
dry_run = true
no_pretty = true

[prod]
server = epp.prod.net.nz
user = prod_user
password = prod_pass
port = 700
dry_run = false
no_pretty = false
"""
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            tf.write(ini_content)
            cfg_path = tf.name

        try:
            load_config(cfg_path)
            with patch("pyepp.cli.cli.PyEppCli") as mock_cli_cls:
                instance = mock_cli_cls.return_value
                instance.execute = lambda *args, **kwargs: "<raw/>"

                result = self.runner.invoke(
                    pyepp_cli,
                    ["-c", cfg_path, "-p", "prod", "domain", "check", "test.nz"],
                )
                self.assertEqual(result.exit_code, 0)
                called_args = mock_cli_cls.call_args[0]
                # no_pretty=args[8], dry_run=args[9]
                self.assertFalse(called_args[8])
                self.assertFalse(called_args[9])
        finally:
            if os.path.exists(cfg_path):
                os.remove(cfg_path)
            load_config()


if __name__ == "__main__":
    unittest.main()
