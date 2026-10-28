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


if __name__ == "__main__":
    unittest.main()
