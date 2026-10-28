"""
Profile configuration module for PyEPP.

Provides support for user-defined configuration profiles in config.ini (AWS CLI style):
- A [default] section holds shared/general application configurations.
- Named profiles are defined via [profile <name>] or [<name>].
- Profiles inherit default values from [default].
- Legacy [pyepp] section is supported as a fallback for backward compatibility.
"""

from collections.abc import Iterator, Mapping
from configparser import RawConfigParser
from dataclasses import dataclass, field
import os
from typing import Any, Optional, TYPE_CHECKING
import click

if TYPE_CHECKING:
    from pyepp.epp import EppCommunicator


APP_NAME = "pyepp"


class ProfileNotFoundError(Exception):
    """Raised when a requested configuration profile is not found."""


def _parse_bool(val: Optional[str], default: bool = False) -> bool:
    """Parse a boolean value from configuration string."""
    if val is None:
        return default
    return val.strip().lower() in ("true", "1", "yes", "on")


def _parse_extensions(raw: Optional[str]) -> list[str]:
    """Parse extension URIs from comma-, newline-, or space-separated string."""
    if not raw:
        return []
    cleaned = raw.replace(",", " ").replace("\n", " ").replace("\r", " ")
    return [ext.strip() for ext in cleaned.split() if ext.strip()]


def get_default_config_path() -> str:
    """Return OS-dependent default path for config.ini."""
    return os.path.join(
        click.get_app_dir(APP_NAME, roaming=False, force_posix=True), "config.ini"
    )


def normalize_profile_name(section_name: str) -> str:
    """
    Normalize section name to profile name.

    E.g. 'profile ote' -> 'ote', 'Profile PROD' -> 'PROD', 'default' -> 'default'.
    """
    s = section_name.strip()
    if s.lower().startswith("profile "):
        return s[8:].strip()
    return s


# pylint: disable=too-many-instance-attributes
@dataclass
class Profile(Mapping[str, Any]):
    """
    Represents an EPP configuration profile.

    Implements the Mapping protocol so it can be unpacked directly into
    EppCommunicator(**profile).
    """

    name: str
    server: Optional[str] = None
    port: Optional[str] = "700"
    user: Optional[str] = None
    password: Optional[str] = None
    client_cert: Optional[str] = None
    client_key: Optional[str] = None
    extensions: list[str] = field(default_factory=list)
    output_format: str = "XML"
    no_pretty: bool = False
    dry_run: bool = False
    raw_config: dict[str, str] = field(default_factory=dict)

    _COMMUNICATOR_KEYS = (
        "server",
        "port",
        "client_cert",
        "client_key",
        "dry_run",
        "user",
        "password",
        "extensions",
    )

    def __getitem__(self, key: str) -> Any:
        if key in self._COMMUNICATOR_KEYS:
            val = getattr(self, key, None)
            if val is not None:
                return val
        if key in self.raw_config:
            return self.raw_config[key]
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        for key in self._COMMUNICATOR_KEYS:
            val = getattr(self, key, None)
            if val is not None:
                yield key

    def __len__(self) -> int:
        return sum(1 for _ in self)

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        if key in self._COMMUNICATOR_KEYS and getattr(self, key, None) is not None:
            return True
        return key in self.raw_config

    def to_communicator_kwargs(self, **overrides: Any) -> dict[str, Any]:
        """Return dictionary of parameters suitable for EppCommunicator(**kwargs)."""
        # Ensure extensions is consistently included as a list (matching Profile.__getitem__
        # and the Mapping protocol) rather than being stripped when empty.
        kwargs: dict[str, Any] = {
            "server": self.server,
            "port": self.port,
            "client_cert": self.client_cert,
            "client_key": self.client_key,
            "dry_run": self.dry_run,
            "user": self.user,
            "password": self.password,
            "extensions": list(self.extensions) if self.extensions is not None else [],
        }
        result = {k: v for k, v in kwargs.items() if v is not None}
        result.update(overrides)
        return result

    def create_communicator(self, **overrides: Any) -> "EppCommunicator":
        """Instantiate an EppCommunicator initialized with this profile's configuration."""
        from pyepp.epp import EppCommunicator  # pylint: disable=import-outside-toplevel

        kwargs = self.to_communicator_kwargs(**overrides)
        return EppCommunicator(**kwargs)

    def to_dict(self, communicator_only: bool = False) -> dict[str, Any]:
        """Return dictionary representation of the profile."""
        if communicator_only:
            return self.to_communicator_kwargs()
        return {
            "name": self.name,
            "server": self.server,
            "port": self.port,
            "user": self.user,
            "password": self.password,
            "client_cert": self.client_cert,
            "client_key": self.client_key,
            "extensions": list(self.extensions),
            "output_format": self.output_format,
            "no_pretty": self.no_pretty,
            "dry_run": self.dry_run,
            "raw_config": dict(self.raw_config),
        }

    def copy(self, **overrides: Any) -> "Profile":
        """Create a shallow copy of the profile with optional overrides."""
        data = self.to_dict(communicator_only=False)
        data.update(overrides)
        return Profile(**data)


def _build_profile_from_config(name: str, config: dict[str, str]) -> Profile:
    """Construct a Profile instance from a merged configuration dictionary."""
    fmt = (
        config.get("output_format")
        or config.get("output-format")
        or config.get("format")
        or "XML"
    )
    ext_raw = config.get("extensions") or config.get("extension")
    return Profile(
        name=name,
        server=config.get("server"),
        port=config.get("port", "700"),
        user=config.get("user"),
        password=config.get("password"),
        client_cert=config.get("client_cert") or config.get("client-cert"),
        client_key=config.get("client_key") or config.get("client-key"),
        extensions=_parse_extensions(ext_raw),
        output_format=fmt.strip().upper(),
        no_pretty=_parse_bool(config.get("no_pretty") or config.get("no-pretty")),
        dry_run=_parse_bool(config.get("dry_run") or config.get("dry-run")),
        raw_config=dict(config),
    )


def load_all_profiles(config_file: Optional[str] = None) -> dict[str, Profile]:
    """
    Load all configuration profiles defined in the config.ini file.

    Inherits base settings from [default] (or legacy [pyepp]).

    :param config_file: Optional path to config file. Defaults to ~/.pyepp/config.ini.
    :return: Dictionary mapping profile names to Profile instances.
    """
    cfg_path = config_file or get_default_config_path()
    parser = RawConfigParser()
    if os.path.exists(cfg_path):
        parser.read([cfg_path])

    # 1. Gather base defaults from parser defaults, [default], or legacy [pyepp]
    default_config: dict[str, str] = {}
    for k, v in parser.defaults().items():
        default_config[k.lower()] = v

    for sec in parser.sections():
        if sec.lower() in ("default", "pyepp"):
            for k, v in parser.items(sec):
                default_config[k.lower()] = v

    if "port" not in default_config:
        default_config["port"] = "700"
    if "output_format" not in default_config and "format" not in default_config:
        default_config["output_format"] = "XML"

    profiles: dict[str, Profile] = {}

    # 2. Build default profile
    profiles["default"] = _build_profile_from_config("default", default_config)

    # 3. Build specific named profiles
    for sec in parser.sections():
        sec_lower = sec.lower()
        if sec_lower in ("default", "pyepp"):
            # Also register 'pyepp' as a profile name if explicitly present
            if sec_lower == "pyepp":
                profiles["pyepp"] = _build_profile_from_config("pyepp", default_config)
            continue

        prof_name = normalize_profile_name(sec)
        merged = dict(default_config)
        for k, v in parser.items(sec):
            merged[k.lower()] = v

        profiles[prof_name] = _build_profile_from_config(prof_name, merged)

    return profiles


def list_profiles(config_file: Optional[str] = None) -> list[str]:
    """
    List all available profile names in the configuration file.

    :param config_file: Optional path to config file.
    :return: Sorted list of profile names with 'default' first.
    """
    profiles = load_all_profiles(config_file)
    names = sorted(list(profiles.keys()))
    if "default" in names:
        names.remove("default")
        names.insert(0, "default")
    return names


def load_profile(
    name: str = "default", config_file: Optional[str] = None
) -> Profile:
    """
    Load a specific configuration profile by name.

    :param name: Profile name (e.g. 'default', 'ote', 'prod'). Case-insensitive.
    :param config_file: Optional path to config file.
    :return: The resolved Profile instance.
    :raises ProfileNotFoundError: If profile does not exist.
    """
    profiles = load_all_profiles(config_file)
    target = normalize_profile_name(name).lower()

    # Exact or case-insensitive match
    for prof_name, prof in profiles.items():
        if prof_name.lower() == target:
            return prof

    available = ", ".join(list_profiles(config_file))
    raise ProfileNotFoundError(
        f"Profile '{name}' not found. Available profiles: {available}"
    )
