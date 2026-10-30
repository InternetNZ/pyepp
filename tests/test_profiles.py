"""
Unit tests for pyepp.profiles module.
"""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from pyepp import (
    EppCommunicator,
    EppCommunicatorException,
    Profile,
    ProfileNotFoundError,
    load_profile,
    list_profiles,
    load_all_profiles,
    get_default_config_path,
)


class ProfilesModuleTest(unittest.TestCase):
    """Test suite for Profile class and profile resolution functions."""

    def test_profile_dataclass_defaults(self) -> None:
        """Verify default values on a fresh Profile instance."""
        prof = Profile(name="test")
        self.assertEqual(prof.name, "test")
        self.assertIsNone(prof.server)
        self.assertEqual(prof.port, "700")
        self.assertIsNone(prof.user)
        self.assertIsNone(prof.password)
        self.assertIsNone(prof.client_cert)
        self.assertIsNone(prof.client_key)
        self.assertEqual(prof.extensions, [])
        self.assertEqual(prof.output_format, "XML")
        self.assertFalse(prof.no_pretty)
        self.assertFalse(prof.dry_run)
        self.assertEqual(prof.raw_config, {})

    def test_profile_repr_masks_password_and_raw_config(self) -> None:
        """Verify Profile.__repr__ does not expose plaintext password or raw_config."""
        prof = Profile(
            name="test_repr",
            server="epp.test",
            user="test_user",
            password="super_secret_epp_password",
            raw_config={"password": "super_secret_epp_password", "token": "sensitive_tok"},
        )
        repr_str = repr(prof)
        self.assertNotIn("super_secret_epp_password", repr_str)
        self.assertNotIn("sensitive_tok", repr_str)
        self.assertNotIn("raw_config", repr_str)
        # Ensure credentials remain accessible on the instance
        self.assertEqual(prof.password, "super_secret_epp_password")
        self.assertEqual(prof.raw_config["password"], "super_secret_epp_password")

    def test_profile_mapping_protocol_and_unpacking(self) -> None:
        """Verify Profile behaves as a Mapping and can be unpacked into EppCommunicator."""
        prof = Profile(
            name="ote",
            server="epp.ote.registry.net.nz",
            port="700",
            user="user123",
            password="pwd",
            extensions=["urn:ietf:params:xml:ns:secDNS-1.1"],
            raw_config={"custom_key": "custom_val"},
        )

        # Mapping access
        self.assertEqual(prof["server"], "epp.ote.registry.net.nz")
        self.assertEqual(prof["port"], "700")
        self.assertEqual(prof["user"], "user123")
        self.assertEqual(prof["password"], "pwd")
        self.assertEqual(prof["extensions"], ["urn:ietf:params:xml:ns:secDNS-1.1"])
        self.assertEqual(prof["custom_key"], "custom_val")
        self.assertIn("server", prof)
        self.assertIn("custom_key", prof)
        self.assertNotIn("non_existent_key", prof)

        # Keys in iter are only valid communicator keys with non-None values
        keys = list(iter(prof))
        self.assertIn("server", keys)
        self.assertIn("port", keys)
        self.assertIn("user", keys)
        self.assertIn("password", keys)
        self.assertIn("extensions", keys)
        self.assertNotIn("client_cert", keys)  # Was None, so excluded from unpacking

        # Directly unpack into EppCommunicator
        epp = EppCommunicator(**prof)
        self.assertEqual(epp._server, "epp.ote.registry.net.nz")
        self.assertEqual(epp._port, "700")
        self.assertEqual(epp._user, "user123")
        self.assertEqual(epp._password, "pwd")
        self.assertEqual(epp._extensions, ["urn:ietf:params:xml:ns:secDNS-1.1"])

    def test_profile_to_communicator_kwargs_with_overrides(self) -> None:
        """Verify to_communicator_kwargs applies overrides correctly."""
        prof = Profile(
            name="prod",
            server="epp.registry.net.nz",
            port="700",
            user="prod_user",
        )
        kwargs = prof.to_communicator_kwargs(user="override_user", dry_run=True)
        self.assertEqual(kwargs["server"], "epp.registry.net.nz")
        self.assertEqual(kwargs["port"], "700")
        self.assertEqual(kwargs["user"], "override_user")
        self.assertEqual(kwargs["extensions"], [])
        self.assertTrue(kwargs["dry_run"])

    def test_epp_communicator_dry_run_and_extensions_overrides(self) -> None:
        """Verify overriding dry_run=False and extensions=[] when profile sets them to truthy."""
        prof = Profile(
            name="test_overrides",
            server="127.0.0.1",
            port="700",
            user="admin",
            password="secret",
            dry_run=True,
            extensions=["urn:ietf:params:xml:ns:secDNS-1.1"],
        )

        # Omitted arguments inherit truthy values from profile
        epp_default = EppCommunicator(profile=prof)
        self.assertTrue(epp_default._dry_run)
        self.assertEqual(epp_default._extensions, ["urn:ietf:params:xml:ns:secDNS-1.1"])

        # Explicit dry_run=False and extensions=[] override profile truthy values
        epp_override = EppCommunicator(profile=prof, dry_run=False, extensions=[])
        self.assertFalse(epp_override._dry_run)
        self.assertEqual(epp_override._extensions, [])

    def test_profile_create_communicator(self) -> None:
        """Verify create_communicator creates a properly configured EppCommunicator."""
        prof = Profile(
            name="test",
            server="127.0.0.1",
            port="700",
            user="admin",
            password="secret",
            dry_run=True,
        )
        epp = prof.create_communicator()
        self.assertIsInstance(epp, EppCommunicator)
        self.assertEqual(epp._server, "127.0.0.1")
        self.assertEqual(epp._user, "admin")
        self.assertTrue(epp._dry_run)

    def test_profile_to_dict_and_copy(self) -> None:
        """Verify to_dict and copy methods on Profile."""
        prof = Profile(
            name="test",
            server="127.0.0.1",
            port="700",
            user="admin",
            output_format="TABLE",
        )
        d = prof.to_dict()
        self.assertEqual(d["name"], "test")
        self.assertEqual(d["output_format"], "TABLE")

        copied = prof.copy(output_format="JSON", user="admin2")
        self.assertEqual(copied.output_format, "JSON")
        self.assertEqual(copied.user, "admin2")
        self.assertEqual(copied.server, "127.0.0.1")

    def test_load_profile_when_config_file_does_not_exist(self) -> None:
        """Verify load_profile returns default Profile if config file is missing."""
        missing_path = "/tmp/non_existent_pyepp_config_file_12345.ini"
        prof = load_profile("default", config_file=missing_path)
        self.assertEqual(prof.name, "default")
        self.assertEqual(prof.port, "700")
        self.assertEqual(prof.output_format, "XML")

        # Requesting a specific non-existent profile should raise ProfileNotFoundError
        with self.assertRaises(ProfileNotFoundError):
            load_profile("custom_profile", config_file=missing_path)

    def test_aws_style_profile_inheritance_and_overrides(self) -> None:
        """Verify [default] settings are inherited by named profiles and overridden as needed."""
        ini_content = """[default]
port = 700
output_format = TABLE
no_pretty = true
dry_run = false

[profile ote]
server = epp.ote.registry.net.nz
user = ote_user
password = ote_pwd
extensions = urn:ietf:params:xml:ns:secDNS-1.1, urn:ietf:params:xml:ns:rgp-1.0

[profile prod]
server = epp.registry.net.nz
port = 701
user = prod_user
password = prod_pwd
output_format = XML
client_cert = /certs/prod.crt
client_key = /certs/prod.key

[custom]
server = epp.custom.net
"""
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            tf.write(ini_content)
            cfg_path = tf.name

        try:
            profiles = load_all_profiles(cfg_path)
            self.assertIn("default", profiles)
            self.assertIn("ote", profiles)
            self.assertIn("prod", profiles)
            self.assertIn("custom", profiles)

            # Check ote profile
            ote = load_profile("ote", config_file=cfg_path)
            self.assertEqual(ote.name, "ote")
            self.assertEqual(ote.server, "epp.ote.registry.net.nz")
            self.assertEqual(ote.port, "700")  # Inherited from [default]
            self.assertEqual(ote.output_format, "TABLE")  # Inherited from [default]
            self.assertTrue(ote.no_pretty)  # Inherited from [default]
            self.assertFalse(ote.dry_run)
            self.assertEqual(
                ote.extensions,
                [
                    "urn:ietf:params:xml:ns:secDNS-1.1",
                    "urn:ietf:params:xml:ns:rgp-1.0",
                ],
            )

            # Check prod profile (with overrides)
            prod = load_profile("prod", config_file=cfg_path)
            self.assertEqual(prod.server, "epp.registry.net.nz")
            self.assertEqual(prod.port, "701")  # Overridden
            self.assertEqual(prod.output_format, "XML")  # Overridden
            self.assertEqual(prod.client_cert, "/certs/prod.crt")
            self.assertEqual(prod.client_key, "/certs/prod.key")

            # Check custom profile without 'profile ' prefix in section header
            custom = load_profile("custom", config_file=cfg_path)
            self.assertEqual(custom.server, "epp.custom.net")
            self.assertEqual(custom.port, "700")  # Inherited from default

            # Check list_profiles ordering
            names = list_profiles(cfg_path)
            self.assertEqual(names[0], "default")
            self.assertIn("ote", names)
            self.assertIn("prod", names)
            self.assertIn("custom", names)

            # Case insensitivity and prefix resolution
            self.assertEqual(load_profile("OTE", config_file=cfg_path).name, "ote")
            self.assertEqual(
                load_profile("profile ote", config_file=cfg_path).name, "ote"
            )
        finally:
            if os.path.exists(cfg_path):
                os.remove(cfg_path)

    def test_legacy_pyepp_section_support(self) -> None:
        """Verify legacy [pyepp] section acts as default profile."""
        ini_content = """[pyepp]
server = localhost
port = 700
user = legacy_user
password = legacy_pass
output_format = TABLE
"""
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            tf.write(ini_content)
            cfg_path = tf.name

        try:
            prof_default = load_profile("default", config_file=cfg_path)
            self.assertEqual(prof_default.server, "localhost")
            self.assertEqual(prof_default.user, "legacy_user")
            self.assertEqual(prof_default.output_format, "TABLE")

            prof_pyepp = load_profile("pyepp", config_file=cfg_path)
            self.assertEqual(prof_pyepp.server, "localhost")
        finally:
            if os.path.exists(cfg_path):
                os.remove(cfg_path)

    def test_default_section_precedence_over_legacy_pyepp(self) -> None:
        """Verify [default] takes precedence over [pyepp] even when [pyepp] appears second."""
        ini_content = """[default]
server = modern.server.net
port = 700
user = modern_user

[pyepp]
server = legacy.server.net
user = legacy_user
"""
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            tf.write(ini_content)
            cfg_path = tf.name

        try:
            prof = load_profile("default", config_file=cfg_path)
            self.assertEqual(prof.server, "modern.server.net")
            self.assertEqual(prof.user, "modern_user")
        finally:
            if os.path.exists(cfg_path):
                os.remove(cfg_path)

    def test_profile_default_section_support(self) -> None:
        """Verify [profile default] acts as base default and is inherited by other profiles."""
        ini_content = """[profile default]
server = base.default.net
port = 700
output_format = TABLE

[profile ote]
user = ote_user
"""
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            tf.write(ini_content)
            cfg_path = tf.name

        try:
            prof_default = load_profile("default", config_file=cfg_path)
            self.assertEqual(prof_default.server, "base.default.net")
            self.assertEqual(prof_default.output_format, "TABLE")

            prof_ote = load_profile("ote", config_file=cfg_path)
            self.assertEqual(prof_ote.server, "base.default.net")
            self.assertEqual(prof_ote.output_format, "TABLE")
            self.assertEqual(prof_ote.user, "ote_user")
        finally:
            if os.path.exists(cfg_path):
                os.remove(cfg_path)

    def test_profile_case_collision_and_alias_merging(self) -> None:
        """Verify sections differing only by case or prefix merge into a single canonical profile."""
        ini_content = """[OTE]
server = epp.ote.net
user = ote_user

[profile ote]
password = ote_secret
"""
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            tf.write(ini_content)
            cfg_path = tf.name

        try:
            profiles = load_all_profiles(cfg_path)
            # Only one canonical 'ote' profile key should exist
            self.assertIn("ote", profiles)
            self.assertNotIn("OTE", profiles)
            self.assertNotIn("profile ote", profiles)

            ote = profiles["ote"]
            self.assertEqual(ote.server, "epp.ote.net")
            self.assertEqual(ote.user, "ote_user")
            self.assertEqual(ote.password, "ote_secret")

            # list_profiles should only have unique entries
            names = list_profiles(cfg_path)
            self.assertEqual(names.count("ote"), 1)
        finally:
            if os.path.exists(cfg_path):
                os.remove(cfg_path)

    def test_epp_communicator_from_profile(self) -> None:
        """Verify EppCommunicator.from_profile instantiates correctly."""
        ini_content = """[profile ote]
server = epp.ote.test
port = 700
user = test_user
password = test_pass
"""
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            tf.write(ini_content)
            cfg_path = tf.name

        try:
            epp = EppCommunicator.from_profile(
                "ote", config_file=cfg_path, dry_run=True
            )
            self.assertEqual(epp._server, "epp.ote.test")
            self.assertEqual(epp._port, "700")
            self.assertEqual(epp._user, "test_user")
            self.assertEqual(epp._password, "test_pass")
            self.assertTrue(epp._dry_run)
        finally:
            if os.path.exists(cfg_path):
                os.remove(cfg_path)

    @patch("pyepp.epp.ssl.create_default_context")
    def test_epp_communicator_from_profile_with_cert_and_key_expanded(
        self, mock_ssl: MagicMock
    ) -> None:
        """Verify EppCommunicator.from_profile uses expanded cert/key when connecting."""
        ini_content = """[profile tls_test]
server = epp.tls.test
client_cert = ~/.pyepp/certs/client.crt
client_key = ~/.pyepp/certs/client.key
"""
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            tf.write(ini_content)
            cfg_path = tf.name

        try:
            epp = EppCommunicator.from_profile(
                "tls_test", config_file=cfg_path, dry_run=False
            )
            expected_cert = os.path.expanduser("~/.pyepp/certs/client.crt")
            expected_key = os.path.expanduser("~/.pyepp/certs/client.key")
            self.assertEqual(epp._client_cert, expected_cert)
            self.assertEqual(epp._client_key, expected_key)

            mock_context = MagicMock()
            mock_ssl.return_value = mock_context
            epp._read = MagicMock(return_value=b"greeting")
            epp.connect()
            mock_context.load_cert_chain.assert_called_with(
                certfile=expected_cert, keyfile=expected_key
            )
        finally:
            if os.path.exists(cfg_path):
                os.remove(cfg_path)

    def test_epp_communicator_init_with_profile_param(self) -> None:
        """Verify EppCommunicator.__init__ accepts profile argument."""
        ini_content = """[profile prod]
server = epp.prod.test
port = 700
user = prod_u
password = prod_p
"""
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            tf.write(ini_content)
            cfg_path = tf.name

        try:
            # By profile name string
            epp = EppCommunicator(profile="prod", config_file=cfg_path)
            self.assertEqual(epp._server, "epp.prod.test")
            self.assertEqual(epp._user, "prod_u")

            # By Profile instance
            prof = load_profile("prod", config_file=cfg_path)
            epp2 = EppCommunicator(profile=prof)
            self.assertEqual(epp2._server, "epp.prod.test")
            self.assertEqual(epp2._user, "prod_u")
        finally:
            if os.path.exists(cfg_path):
                os.remove(cfg_path)

    def test_epp_communicator_port_override_to_700(self) -> None:
        """Verify overriding port to '700' when profile specifies a non-700 port."""
        ini_content = """[profile custom_port]
server = epp.custom.test
port = 701
user = u
password = p
"""
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            tf.write(ini_content)
            cfg_path = tf.name

        try:
            # When port is omitted, profile port (701) is used
            epp_default = EppCommunicator(profile="custom_port", config_file=cfg_path)
            self.assertEqual(epp_default._port, "701")

            # When port="700" is explicitly provided as str, it overrides profile port 701
            epp_str = EppCommunicator(
                profile="custom_port", config_file=cfg_path, port="700"
            )
            self.assertEqual(epp_str._port, "700")

            # When port=700 is explicitly provided as int, it overrides profile port 701
            epp_int = EppCommunicator(
                profile="custom_port", config_file=cfg_path, port=700
            )
            self.assertEqual(epp_int._port, "700")
        finally:
            if os.path.exists(cfg_path):
                os.remove(cfg_path)

    def test_connect_raises_when_no_server_is_configured(self) -> None:
        """Verify connect() raises EppCommunicatorException when server is missing."""
        epp = EppCommunicator()
        with self.assertRaises(EppCommunicatorException) as ctx:
            epp.connect()
        self.assertIn("server hostname is required", str(ctx.exception))

    def test_load_profiles_utf8_encoding(self) -> None:
        """Verify load_all_profiles correctly parses non-ASCII UTF-8 characters."""
        ini_content = """[profile utf8_test]
server = epp.māori.test
user = Māori_user
password = Pāsswørd_€_123
"""
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as tf:
            tf.write(ini_content)
            cfg_path = tf.name

        try:
            prof = load_profile("utf8_test", config_file=cfg_path)
            self.assertEqual(prof.server, "epp.māori.test")
            self.assertEqual(prof.user, "Māori_user")
            self.assertEqual(prof.password, "Pāsswørd_€_123")
        finally:
            if os.path.exists(cfg_path):
                os.remove(cfg_path)

    def test_check_config_file_permissions_warning(self) -> None:
        """Verify security warning is emitted on POSIX when file permissions are too open."""
        if os.name != "posix":
            self.skipTest("Permission test only applies to POSIX systems")

        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            tf.write("[default]\nserver=test\n")
            cfg_path = tf.name

        try:
            # Set open permissions 0644 (world-readable)
            os.chmod(cfg_path, 0o644)
            with patch("logging.warning") as mock_warn:
                load_all_profiles(cfg_path)
                mock_warn.assert_called_once()
                self.assertIn("accessible by other users", mock_warn.call_args[0][0])

            # Set secure permissions 0600 (owner only)
            os.chmod(cfg_path, 0o600)
            with patch("logging.warning") as mock_warn_secure:
                load_all_profiles(cfg_path)
                mock_warn_secure.assert_not_called()
        finally:
            if os.path.exists(cfg_path):
                os.remove(cfg_path)

    def test_client_cert_and_key_path_expansion(self) -> None:
        """Verify ~ is expanded in client_cert and client_key paths."""
        ini_content = """[profile cert_test]
server = epp.test.net
client_cert = ~/.pyepp/certs/client.crt
client_key = ~/.pyepp/certs/client.key
"""
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            tf.write(ini_content)
            cfg_path = tf.name

        try:
            prof = load_profile("cert_test", config_file=cfg_path)
            expected_cert = os.path.expanduser("~/.pyepp/certs/client.crt")
            expected_key = os.path.expanduser("~/.pyepp/certs/client.key")
            self.assertEqual(prof.client_cert, expected_cert)
            self.assertEqual(prof.client_key, expected_key)
            self.assertEqual(prof["client_cert"], expected_cert)
            self.assertEqual(prof["client_key"], expected_key)
            kwargs = prof.to_communicator_kwargs()
            self.assertEqual(kwargs["client_cert"], expected_cert)
            self.assertEqual(kwargs["client_key"], expected_key)
        finally:
            if os.path.exists(cfg_path):
                os.remove(cfg_path)

    def test_client_cert_and_key_hyphenated_keys_expansion(self) -> None:
        """Verify ~ is expanded when using hyphenated client-cert and client-key."""
        ini_content = """[profile hyphen_test]
server = epp.test.net
client-cert = ~/certs/my_client.crt
client-key = ~/certs/my_client.key
"""
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            tf.write(ini_content)
            cfg_path = tf.name

        try:
            prof = load_profile("hyphen_test", config_file=cfg_path)
            expected_cert = os.path.expanduser("~/certs/my_client.crt")
            expected_key = os.path.expanduser("~/certs/my_client.key")
            self.assertEqual(prof.client_cert, expected_cert)
            self.assertEqual(prof.client_key, expected_key)
        finally:
            if os.path.exists(cfg_path):
                os.remove(cfg_path)

    def test_client_cert_and_key_empty_or_whitespace_resolves_to_none(self) -> None:
        """Verify empty or whitespace strings for cert/key resolve to None."""
        ini_content = """[profile empty_test]
server = epp.test.net
client_cert = 
client_key =    
"""
        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            tf.write(ini_content)
            cfg_path = tf.name

        try:
            prof = load_profile("empty_test", config_file=cfg_path)
            self.assertIsNone(prof.client_cert)
            self.assertIsNone(prof.client_key)
        finally:
            if os.path.exists(cfg_path):
                os.remove(cfg_path)

    def test_check_client_key_permissions_warning(self) -> None:
        """Verify security warning is emitted on POSIX when client_key has open permissions."""
        if os.name != "posix":
            self.skipTest("Permission test only applies to POSIX systems")

        with tempfile.NamedTemporaryFile("w", delete=False) as tf_key:
            tf_key.write("FAKE KEY DATA")
            key_path = tf_key.name

        with tempfile.NamedTemporaryFile("w", delete=False) as tf_cfg:
            tf_cfg.write(f"[default]\nserver=test\nclient_key={key_path}\n")
            cfg_path = tf_cfg.name

        try:
            # Set secure permissions on config file to isolate key warning
            os.chmod(cfg_path, 0o600)
            # Set open permissions 0644 on key file
            os.chmod(key_path, 0o644)
            with patch("logging.warning") as mock_warn:
                load_all_profiles(cfg_path)
                mock_warn.assert_called_once()
                self.assertIn("contains private key material but is accessible by other users", mock_warn.call_args[0][0])
                self.assertEqual(mock_warn.call_args[0][1], key_path)

            # Set secure permissions 0600 on key file
            os.chmod(key_path, 0o600)
            with patch("logging.warning") as mock_warn_secure:
                load_all_profiles(cfg_path)
                mock_warn_secure.assert_not_called()
        finally:
            if os.path.exists(cfg_path):
                os.remove(cfg_path)
            if os.path.exists(key_path):
                os.remove(key_path)

    def test_check_client_key_permissions_deduplication(self) -> None:
        """Verify duplicate warnings are not emitted when multiple profiles inherit the same key."""
        if os.name != "posix":
            self.skipTest("Permission test only applies to POSIX systems")

        with tempfile.NamedTemporaryFile("w", delete=False) as tf_key:
            tf_key.write("FAKE KEY DATA")
            key_path = tf_key.name

        with tempfile.NamedTemporaryFile("w", delete=False) as tf_cfg:
            tf_cfg.write(
                f"[default]\nserver=test\nclient_key={key_path}\n\n"
                f"[profile ote]\nserver=ote.test\n\n"
                f"[profile prod]\nserver=prod.test\n"
            )
            cfg_path = tf_cfg.name

        try:
            os.chmod(cfg_path, 0o600)
            os.chmod(key_path, 0o644)
            with patch("logging.warning") as mock_warn:
                load_all_profiles(cfg_path)
                # Should be called exactly once despite 3 profile sections using the same key
                mock_warn.assert_called_once()
                self.assertIn("contains private key material", mock_warn.call_args[0][0])
        finally:
            if os.path.exists(cfg_path):
                os.remove(cfg_path)
            if os.path.exists(key_path):
                os.remove(key_path)

    def test_check_client_key_permissions_nonexistent_or_oserror(self) -> None:
        """Verify nonexistent file and OSError during stat are handled gracefully."""
        from pyepp.profiles import _check_client_key_permissions  # pylint: disable=import-outside-toplevel

        # Non-existent file
        with patch("logging.warning") as mock_warn:
            _check_client_key_permissions("/nonexistent/path/to/key.pem")
            mock_warn.assert_not_called()

        # OSError during os.stat inside try-block
        with tempfile.NamedTemporaryFile("w", delete=False) as tf_key:
            tf_key.write("KEY")
            key_path = tf_key.name

        try:
            with patch("os.path.isfile", return_value=True), patch(
                "os.stat", side_effect=OSError("Disk error")
            ):
                with patch("logging.warning") as mock_warn:
                    _check_client_key_permissions(key_path)
                    mock_warn.assert_not_called()
        finally:
            if os.path.exists(key_path):
                os.remove(key_path)

    def test_build_profile_from_config_standalone_checked_keys_none(self) -> None:
        """Verify _build_profile_from_config works with default checked_keys=None."""
        from pyepp.profiles import _build_profile_from_config  # pylint: disable=import-outside-toplevel

        with tempfile.NamedTemporaryFile("w", delete=False) as tf_key:
            tf_key.write("KEY")
            key_path = tf_key.name

        try:
            os.chmod(key_path, 0o600)
            prof = _build_profile_from_config(
                "standalone",
                {
                    "server": "epp.example.com",
                    "client_cert": "~/cert.pem",
                    "client_key": key_path,
                },
            )
            self.assertEqual(prof.name, "standalone")
            self.assertEqual(prof.client_cert, os.path.expanduser("~/cert.pem"))
            self.assertEqual(prof.client_key, key_path)
        finally:
            if os.path.exists(key_path):
                os.remove(key_path)


if __name__ == "__main__":
    unittest.main()
