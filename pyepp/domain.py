"""
Domain Mapping Module
"""
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Optional
from datetime import date

from bs4 import BeautifulSoup

from pyepp.base_command import BaseCommand
from pyepp.command_templates import DOMAIN_CHECK_XML, DOMAIN_INFO_XML, DOMAIN_CREATE_XML, DOMAIN_DELETE_XML, \
    DOMAIN_RENEW_XML, TRANSFER_REQUEST_XML, DOMAIN_UPDATE_XML
from pyepp.epp import EppResultCode


class DNSSECAlgorithm(Enum):
    """DNSSEC algorithms"""
    DSA_SHA_1 = 3
    RSA_SHA_1 = 5
    DSA_NSEC3_SHA1 = 6
    RSASHA1_NSEC3_SHA1 = 7
    RSA_SHA_256 = 8
    RSA_SHA_512 = 10
    GOST_R_34_10_2001 = 12
    ECDSA_CURVE_P_256_WITH_SHA_256 = 13
    ECDSA_CURVE_P_384_WITH_SHA_384 = 14
    ED25519 = 15
    ED448 = 16
    PRIVATE_ALGORITHM = 253
    PRIVATE_ALGORITHM_OID = 255


class DigestTypeEnum(Enum):
    """Digest types"""
    SHA_1 = 1
    SHA_256 = 2
    GOST_R_34_11_94 = 3
    SHA_384 = 4


class DNSKeyFlagEnum(Enum):
    """DNS Key flags"""
    FLAG_256 = 256
    FLAG_257 = 257


@dataclass
class DSRecordKeyData:
    """DNSSEC Key data"""
    flag: str
    algorithm: DNSSECAlgorithm
    public_key: str
    protocol: str = 3


@dataclass
class DSRecordData:
    """DNSSEC data"""
    key_tag: int
    algorithm: DNSSECAlgorithm
    digest_type: DigestTypeEnum
    digest: str
    dns_key: Optional[DSRecordKeyData] = None


@dataclass
class DomainData:
    """Domain name data"""
    # pylint: disable=too-many-instance-attributes
    domain_name: str
    registrant: str
    admin: str
    tech: str
    period: int
    sponsoring_client_id: Optional[str] = ''
    billing: Optional[str] = ''
    status: Optional[list[str]] = None
    host: Optional[list[str]] = None
    create_date: Optional[str] = ''
    creat_client_id: Optional[str] = ''
    update_client_id: Optional[str] = ''
    update_date: Optional[str] = ''
    expiry_date: Optional[str] = ''
    transfer_date: Optional[str] = ''
    password: Optional[str] = ''
    dns_sec: Optional[DSRecordData] = None
    dns_key: Optional[DSRecordKeyData] = None


class Domain(BaseCommand):
    """
    Epp Domain
    """

    def _data_to_dict(self, data: DomainData) -> dict:
        """Convert dataclass to dictionary.

        :param DomainData data: Domain name details

        :return: Domain name details
        :rtype: dict
        """
        data_dict = asdict(data)

        return data_dict

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
            'sponsoring_client_id': raw_response.find('clID').text,
            'status': [status.text for status in raw_response.find_all('status')],
            'host': [host.text for host in raw_response.find_all('hostObj')] if raw_response.find('ns') else None,
            'registrant': raw_response.find('registrant').text,
            'admin': raw_response.find('contact', {'type': 'admin'}).text,
            'tech': raw_response.find('contact', {'type': 'tech'}).text,
            'billing': [billing.text for billing in raw_response.find_all('contact', {'type': 'billing'})]
            if raw_response.find('contact', {'type': 'billing'}) else None,
            'create_date': raw_response.find('crDate').text if raw_response.find('crDate') else None,
            'creat_client_id': raw_response.find('crID').text if raw_response.find('crID') else None,
            'expiry_date': raw_response.find('exDate').text if raw_response.find('exDate') else None,
            'update_client_id': raw_response.find('upID').text if raw_response.find('upID') else None,
            'update_date': raw_response.find('upDate').text if raw_response.find('upDate') else None,
            'transfer_date': raw_response.find('trDate').text if raw_response.find('trDate') else None,
            'password': raw_response.find('pw').text if raw_response.find('pw') else None,
            'period': None,
            'dns_sec': {
                'key_tag': raw_response.find('keyTag').text,
                'algorithm': raw_response.find('alg').text,
                'digest_type': raw_response.find('digestType').text,
                'digest': raw_response.find('digest').text,
                'dns_key': {
                    'flags': raw_response.find('flag').text,
                    'protocol': raw_response.find('protocol').text,
                    'alg': raw_response.find('algorithm').text,
                    'pubKey': raw_response.find('public_key').text,
                } if raw_response.find('keyData') else None
            } if raw_response.find('dsData') else None,
            'dns_key': {
                'flags': raw_response.find('flag').text,
                'protocol': raw_response.find('protocol').text,
                'alg': raw_response.find('algorithm').text,
                'pubKey': raw_response.find('public_key').text,
            } if raw_response.find('keyData') else None
        }

        result['result_data'] = DomainData(**result_data)

        return result

    def create(self, domain: DomainData) -> dict:
        """Create a domain object.

        :param DomainData domain: Contact

        :return: Response object
        :rtype: dict
        """
        params = self._data_to_dict(domain)

        result = self.execute(DOMAIN_CREATE_XML, **params)

        return result

    def delete(self, domain_name: str) -> dict:
        """Delete a domain object.

        :param str domain_name: Domain Name

        :return: Response object
        :rtype: dict
        """
        result = self.execute(DOMAIN_DELETE_XML, domain_name=domain_name)

        return result

    def renew(self, domain_name: str, expiry_date: date, period: Optional[int] = 1) -> dict:
        """Extends the registration period of a domain name. It also maintains existing status values.

        :param str domain_name: Domain Name
        :param date expiry_date: expiry date
        :param int period: period

        :return: Response object
        :rtype: dict
        """
        result = self.execute(DOMAIN_RENEW_XML,
                              domain_name=domain_name,
                              expiry_date=expiry_date.strftime("%Y-%m-%d"),
                              period=str(period))

        return result

    def transfer(self, domain_name: str, password: str, period: Optional[int] = None, ) -> dict:
        """transfers the sponsorship of a domain name from another Registrar to the Registrar
        submitting the request.

        :param str domain_name: Domain Name
        :param str password: The authorization password for the domain object
        :param int period: period

        :return: Response object
        :rtype: dict
        """
        result = self.execute(TRANSFER_REQUEST_XML,
                              domain_name=domain_name,
                              password=password,
                              period=str(period) if period else None)

        return result

    # pylint: disable=too-many-arguments,too-many-locals
    def update(self, domain_name: str,
               registrant: Optional[str] = None,
               admin: Optional[str] = None,
               tech:  Optional[str] = None,
               add_billings: Optional[list[str]] = None,
               remove_billings: Optional[list[str]] = None,
               add_statues: Optional[list[tuple]] = None,
               remove_statues: Optional[list[str]] = None,
               add_hosts: Optional[list[str]] = None,
               remove_hosts: Optional[list[str]] = None,
               password: Optional[str] = None
               ) -> dict:
        """

        :param str domain_name: Domain name to be updated
        :param str registrant: A contact id to replace the current registrant
        :param str admin: A contact id to replace the current admin
        :param str tech: A contact id to replace the current tech
        :param list[str] add_billings: A list of contact ids to add to the billing contacts
        :param list[str] remove_billings: A list of contact ids to remove from the billing contacts
        :param list[tuple] add_statues: List of statuses to be added tio the domain name. The tuple must contain two
            elements. The first one will be the Status Code and the second element will be Descriptions.
        :param list[str] remove_statues: A list of statues to be removed from the domain name.
        :param list[str] add_hosts: A list of host names to be added to the domain name.
        :param list[str] remove_hosts: A list of host names to be removed from the domain name.
        :param str password: A new password to replace the old password.

        :return: Response object
        :rtype: dict
        """
        remove_admin = None
        remove_tech = None

        if admin or tech:
            domain_info = self.info(domain_name=domain_name).get('result_data')
            remove_admin = domain_info.admin if admin else None
            remove_tech = domain_info.tech if tech else None

        add = bool(admin or tech or add_billings or add_statues or add_hosts)
        remove = bool(remove_admin or remove_tech or remove_billings or remove_statues or remove_hosts)
        change = bool(registrant or password)

        result = self.execute(DOMAIN_UPDATE_XML,
                              add=add,
                              remove=remove,
                              change=change,
                              domain_name=domain_name,
                              admin=admin,
                              remove_admin=remove_admin,
                              tech=tech,
                              remove_tech=remove_tech,
                              add_billings=add_billings,
                              remove_billings=remove_billings,
                              add_statues=add_statues,
                              remove_statues=remove_statues,
                              add_hosts=add_hosts,
                              remove_hosts=remove_hosts,
                              password=password,
                              registrant=registrant)

        return result
