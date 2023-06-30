"""
Host Mapping Module
"""
from dataclasses import dataclass, asdict
from typing import Optional

from bs4 import BeautifulSoup

from pyepp.base_command import BaseCommand
from pyepp.command_templates import HOST_CHECK_XML, HOST_INFO_XML, HOST_CREAT_XML, HOST_DELETE_XML, HOST_UPDATE_XML
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
    host_name: str
    address: Optional[list[IPAddressData]] = None
    status: Optional[list[str]] = None
    create_date: Optional[str] = ''
    creat_client_id: Optional[str] = ''
    update_client_id: Optional[str] = ''
    update_date: Optional[str] = ''


class Host(BaseCommand):
    """
    Epp Host Mapping
    """

    def _data_to_dict(self, data: HostData) -> dict:
        """Convert dataclass to dictionary.

        :param HostData data: Host name details

        :return: Host name details
        :rtype: dict
        """
        data_dict = asdict(data)

        return data_dict

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

    def info(self, host_name: str) -> dict:
        """This is used to retrieve information associated with a host object.

        :param str host_name: Host name

        :return: Host name details
        :rtype: dict
        """
        result = self.execute(HOST_INFO_XML, host_name=host_name)

        if int(result.get('code')) != int(EppResultCode.SUCCESS.value):
            return result

        raw_response = BeautifulSoup(result.get('raw_response'), 'xml')

        result_data = {
            'host_name': raw_response.find('name').text,
            'status': [status.get('s') for status in raw_response.find_all('status')],
            'address': [IPAddressData(address=addr.text, ip=addr.get('ip')) for addr in raw_response.find_all('addr')]
            if raw_response.find('addr') else None,
            'create_date': raw_response.find('crDate').text if raw_response.find('crDate') else None,
            'creat_client_id': raw_response.find('crID').text if raw_response.find('crID') else None,
            'update_client_id': raw_response.find('upID').text if raw_response.find('upID') else None,
            'update_date': raw_response.find('upDate').text if raw_response.find('upDate') else None,
        }

        result['result_data'] = HostData(**result_data)

        return result

    def create(self, host: HostData) -> dict:
        """Create a host object.

        :param HostData host: Contact

        :return: Response object
        :rtype: dict
        """
        params = self._data_to_dict(host)

        result = self.execute(HOST_CREAT_XML, **params)

        return result

    def delete(self, host_name: str) -> dict:
        """Delete a host object.

        :param str host_name: Host Name

        :return: Response object
        :rtype: dict
        """
        result = self.execute(HOST_DELETE_XML, host_name=host_name)

        return result

    # pylint: disable=too-many-arguments
    def update(self, host_name: str,
               add_ip_address: Optional[list[IPAddressData]] = None,
               remove_ip_address: Optional[list[IPAddressData]] = None,
               add_statue: Optional[list[str]] = None,
               remove_statue: Optional[list[str]] = None,
               new_host_name: Optional[str] = None
               ) -> dict:
        """Update a host object.

        :param host_name: Host Name
        :param add_ip_address: A list of IP addressed to be added to the host
        :param remove_ip_address: A list of IP addressed to be removed from the host
        :param add_statue: A list of statues to be added to the host
        :param remove_statue: A list of statues to be removed from the host
        :param new_host_name: The host name will be changed to this new host name

        :return: Response object
        :rtype: dict
        """

        add = bool(add_ip_address or add_statue)
        remove = bool(remove_ip_address or remove_statue)
        change = bool(new_host_name)

        result = self.execute(HOST_UPDATE_XML,
                              host_name=host_name,
                              add=add,
                              remove=remove,
                              change=change,
                              add_ip_address=add_ip_address,
                              remove_ip_address=remove_ip_address,
                              add_statue=add_statue,
                              remove_statue=remove_statue,
                              new_host_name=new_host_name)

        return result
