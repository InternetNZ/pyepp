"""
Host Mapping Module
"""
from dataclasses import dataclass
from typing import Optional

from bs4 import BeautifulSoup

from pyepp.base_command import BaseCommand
from pyepp.command_templates import HOST_CHECK_XML
from pyepp.epp import EppResultCode


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


class Host(BaseCommand):
    """
    Epp Host Mapping
    """

    def check(self, host_names: list[str]) -> dict:
        """This command is used to determine if a host object can be provisioned.

        :param list host_names: List of domain names

        :return: host name check result
        :rtype: dict
        """
        result = self.execute(HOST_CHECK_XML, host_names=host_names)

        if int(result.get('code')) != int(EppResultCode.SUCCESS.value):
            return result

        raw_response = BeautifulSoup(result.get('raw_response'), 'xml')
        domains_check_data = raw_response.find_all('cd')

        result_data = {}
        for domain_cd in domains_check_data:
            domain = domain_cd.find('name')
            available = domain.get('avail') in ('true', '1')
            reason = domain_cd.find('reason').text if not available else None
            result_data[domain.text] = {
                'avail': available,
                'reason': reason,
            }

        result['result_data'] = result_data

        return result
