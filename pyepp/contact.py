"""
Contact Mapping Module
"""
from typing import Optional
from dataclasses import dataclass, asdict
from bs4 import BeautifulSoup

from pyepp.base_command import BaseCommand
from pyepp.command_templates import CONTACT_CHECK_XML, CONTACT_INFO_XML, CONTACT_CREAT_XML, CONTACT_DELETE_XML, \
    CONTACT_UPDATE_XML
from pyepp.epp import EppResultCode


@dataclass
class AddressData:
    """Address data class"""
    street_1: str
    city: str
    country_code: str
    street_2: Optional[str] = ''
    street_3: Optional[str] = ''
    province: Optional[str] = ''
    postal_code: Optional[str] = ''


@dataclass
class PostalInfoData:
    """Postal Info data class"""
    name: str
    organization: Optional[str] = ''
    address: Optional[AddressData] = None


@dataclass
class ContactData:
    """Contact data class"""
    # pylint: disable=invalid-name,too-many-instance-attributes
    id: str
    email: str
    postal_info: Optional[PostalInfoData] = None
    status: Optional[list[str]] = None
    phone: Optional[str] = ''
    fax: Optional[str] = ''
    password: Optional[str] = ''
    client_transaction_id: Optional[str] = ''
    server_transaction_id: Optional[str] = ''
    repository_object_id: Optional[str] = ''
    create_date: Optional[str] = ''
    creat_client_id: Optional[str] = ''
    sponsoring_client_id: Optional[str] = ''
    update_client_id: Optional[str] = ''
    update_date: Optional[str] = ''


class Contact(BaseCommand):
    """
    Epp Contact
    """

    def _data_to_dict(self, data: ContactData) -> dict:
        """Convert dataclass to dictionary.

        :param ContactData data: Contact details

        :return: Contact details
        :rtype: dict
        """
        data_dict = asdict(data)
        postal_info = data_dict.pop('postal_info', {})
        address = postal_info.pop('address', {})

        if address:
            data_dict.update(address)
        if postal_info:
            data_dict.update(postal_info)

        return data_dict

    def check(self, contact_ids: list[str]) -> dict:
        """This command is used to determine if an object can be provisioned.

        :param list contact_ids: List of contact ids

        :return: contact check result
        :rtype: dict
        """
        result = self.execute(CONTACT_CHECK_XML, ids=contact_ids)

        if int(result.get('code')) != int(EppResultCode.SUCCESS.value):
            return result

        raw_response = BeautifulSoup(result.get('raw_response'), 'xml')
        contacts_check_data = raw_response.find_all('cd')

        result_data = {}
        for contact_cd in contacts_check_data:
            contact = contact_cd.find('id')
            available = contact.get('avail') in ('true', '1')
            reason = contact_cd.find('reason').text if not available else None
            result_data[contact.text] = {
                'avail': available,
                'reason': reason,
            }

        result['result_data'] = result_data

        return result

    def info(self, contact_id: str) -> dict:
        """
        Retrieve contact details.

        :param str contact_id: Contact ID

        :return: Contact details
        :rtype: dict
        """
        result = self.execute(CONTACT_INFO_XML, id=contact_id)

        if int(result.get('code')) != int(EppResultCode.SUCCESS.value):
            return result

        raw_response = BeautifulSoup(result.get('raw_response'), 'xml')

        result_data = {
            'id': raw_response.find('id').text,
            'repository_object_id': raw_response.find('roid').text,
            'status': [status.text for status in raw_response.find_all('status')],
            'create_date': raw_response.find('crDate').text,
            'creat_client_id': raw_response.find('crID').text,
            'sponsoring_client_id': raw_response.find('clID').text,
            'update_client_id': raw_response.find('upID').text,
            'update_date': raw_response.find('upDate').text,
            'postal_info': {
                'name': raw_response.find('name').text,
                'organization': raw_response.find('org').text if raw_response.find('org') else None,
                'address': {
                    'street_1': raw_response.find_all('street')[0].text,
                    'street_2': raw_response.find_all('street')[1].text
                    if len(raw_response.find_all('street')) > 1 else None,
                    'street_3': raw_response.find_all('street')[2].text
                    if len(raw_response.find_all('street')) > 2 else None,
                    'city': raw_response.find('city').text,
                    'province': raw_response.find('sp').text if raw_response.find('sp') else None,
                    'postal_code': raw_response.find('pc').text if raw_response.find(
                        'pc') else None,
                    'country_code': raw_response.find('cc').text,
                },
            },
            'phone': raw_response.find('voice').text if raw_response.find('voice') else None,
            'fax': raw_response.find('fax').text if raw_response.find('fax') else None,
            'email': raw_response.find('email').text,
        }

        if raw_response.find('pw'):
            result_data['password'] = raw_response.find('pw').text

        result['result_data'] = ContactData(**result_data)

        return result

    def create(self, contact: ContactData) -> dict:
        """Create a contact object.

        :param ContactData contact: Contact

        :return: Response object
        :rtype: dict
        """
        params = self._data_to_dict(contact)

        result = self.execute(CONTACT_CREAT_XML, **params)

        return result

    def delete(self, contact_id: str) -> dict:
        """Delete a contact object.

        :param str contact_id: Contact ID

        :return: Response object
        :rtype: dict
        """
        result = self.execute(CONTACT_DELETE_XML, id=contact_id)

        return result

    def update(self,
               contact: ContactData,
               add_status: Optional[str] = '',
               remove_status: Optional[str] = '',
               ) -> dict:
        """Update contact details.

        :param ContactData contact: Contact details to be updated
        :param str add_status: Status to be added
        :param str remove_status: Status to be removed

        :return: Response object
        :rtype: dict
        """

        params = self._data_to_dict(contact)

        params['add_status'] = add_status
        params['remove_status'] = remove_status

        params['postalinfo_change'] = bool(contact.postal_info)
        params['address_change'] = bool(contact.postal_info.address)

        result = self.execute(CONTACT_UPDATE_XML, **params)

        return result
