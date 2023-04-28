"""
Domain Mapping Module
"""
from bs4 import BeautifulSoup

from pyepp.base_command import BaseCommand
from pyepp.command_templates import DOMAIN_CHECK_XML
from pyepp.epp import EppResultCode


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
        for contact_cd in domains_check_data:
            contact = contact_cd.find('name')
            available = contact.get('avail') in ('true', '1')
            reason = contact_cd.find('reason').text if not available else None
            result_data[contact.text] = {
                'avail': available,
                'reason': reason,
            }

        result['result_data'] = result_data

        return result
