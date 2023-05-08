"""
Host Mapping Module
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class IPAddressData:
    """IP Address"""
    address: str
    # pylint: disable=invalid-name
    ip: str


@dataclass
class HostData:
    """Host data"""
    name: str
    address: Optional[list[IPAddressData]] = None
