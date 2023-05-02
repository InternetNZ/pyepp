"""
Domain Mapping Module
"""
from dataclasses import dataclass
from typing import Optional

from bs4 import BeautifulSoup

from pyepp.base_command import BaseCommand
from pyepp.command_templates import DOMAIN_CHECK_XML, DOMAIN_INFO_XML
from pyepp.epp import EppResultCode


@dataclass
class DomainData:
    """Domain name data"""
    # pylint: disable=too-many-instance-attributes
    domain_name: str
    sponsoring_client_id: str
    status: Optional[list[str]] = None
    name_server: Optional[list[str]] = None
    host: Optional[list[str]] = None
    registrant: Optional[str] = ''
    create_date: Optional[str] = ''
    creat_client_id: Optional[str] = ''
    update_client_id: Optional[str] = ''
    update_date: Optional[str] = ''
    expiry_date: Optional[str] = ''
    transfer_date: Optional[str] = ''
    password: Optional[str] = ''


class Domain(BaseCommand):
    """
    Epp Domain
    """

    # pylint: disable=R0801
    def check(self, domain_names: list[str]) -> dict:
        """This command is used to determine if a domain object can be provisioned.

        :param list domain_names: List of domain names

        :return: domain name check result
        :rtype: dict
        """
        result = self.execute(DOMAIN_CHECK_XML, domain_names=domain_names)

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

    def info(self, domain_name: str) -> dict:
        """This is used to retrieve information associated with a domain object.

        :param str domain_name: Domain name

        :return: Domain name details
        :rtype: dict
        """
        result = self.execute(DOMAIN_INFO_XML, domain_name=domain_name)

        if int(result.get('code')) != int(EppResultCode.SUCCESS.value):
            return result

        raw_response = BeautifulSoup(result.get('raw_response'), 'xml')

        result_data = {
            'domain_name': raw_response.find('name').text,
            # 'repository_object_id': raw_response.find('roid').text,
            'sponsoring_client_id': raw_response.find('clID').text,
            'status': [status.text for status in raw_response.find_all('status')],
            'name_server':
                raw_response.find('ns').text if [ns.text for ns in raw_response.find_all('hostObj')] else None,
            'host': [host.text for host in raw_response.find_all('host')],
            'registrant': raw_response.find('registrant').text if raw_response.find('registrant') else None,
            'create_date': raw_response.find('crDate').text if raw_response.find('crDate') else None,
            'creat_client_id': raw_response.find('crID').text if raw_response.find('crID') else None,
            'expiry_date': raw_response.find('exDate').text if raw_response.find('exDate') else None,
            'update_client_id': raw_response.find('upID').text if raw_response.find('upID') else None,
            'update_date': raw_response.find('upDate').text if raw_response.find('upDate') else None,
            'transfer_date': raw_response.find('trDate').text if raw_response.find('trDate') else None,
            'password': raw_response.find('pw').text if raw_response.find('pw') else None,
        }

        result['result_data'] = DomainData(**result_data)

        return result
