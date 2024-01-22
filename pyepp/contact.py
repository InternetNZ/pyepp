"""
Contact Mapping Module. This module is used to manage contact objects in Registry.
"""
from typing import Optional
from dataclasses import dataclass, asdict
from bs4 import BeautifulSoup

from pyepp.base_command import BaseCommand
from pyepp.command_templates import CONTACT_CHECK_XML, CONTACT_INFO_XML, CONTACT_CREAT_XML, CONTACT_DELETE_XML, \
    CONTACT_UPDATE_XML
from pyepp.epp import EppResultCode, EppResultData


@dataclass
class AddressData:
    """Contact address data class.
    """
    street_1: Optional[str] = ''
    city: Optional[str] = ''
    country_code: Optional[str] = ''
    street_2: Optional[str] = ''
    street_3: Optional[str] = ''
    province: Optional[str] = ''
    postal_code: Optional[str] = ''


@dataclass
class PostalInfoData:
    """Contact postal info data class.
    """
    name: Optional[str]
    organization: Optional[str] = ''
    address: Optional[AddressData] = None


@dataclass
class ContactData:
    """Contact data class. Contains the properties of the contacts associated with the domain name.
    """
    # pylint: disable=invalid-name,too-many-instance-attributes
    id: str
    email: Optional[str] = ''
    postal_info: Optional[PostalInfoData] = None
    status: Optional[list[str]] = None
    phone: Optional[str] = ''
    fax: Optional[str] = ''
    password: Optional[str] = ''
    create_date: Optional[str] = ''
    creat_client_id: Optional[str] = ''
    sponsoring_client_id: Optional[str] = ''
    update_client_id: Optional[str] = ''
    update_date: Optional[str] = ''


class Contact(BaseCommand):
    """Epp Contact object class. This class is used to create and manage the contacts within the Registry.

    Contacts are individuals or organizations that are associated with domain names. There are different types of
    contacts including:

    * Registrant - The entity that has the authority to use and manage the domain name.
    * Administrative Contact - Either the Registrant or someone authorized to act on behalf of the Registrant.
    * Technical Contact - A technical contact is an individual identified as a contact for technical information-related
      administration of a registered domain name.
    * Billing Contact - Also known as the Finance Contact, this is the individual or organization responsible for
    payment of fees related to the domain name and will monitor period activity, account balances, and account
    status.
    """

    def _data_to_dict(self, data: ContactData) -> dict:
        """Convert a contact dataclass to a dictionary.

        :param data: Contact details

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

    def check(self, contact_ids: list[str], client_transaction_id: Optional[str] = None) -> EppResultData:
        """A successful Contact Check request determines whether a Contact ID is available for use and whether a contact
        can be created in the Registry. When creating a new contact, the Registrar must generate a Registry-unique
        contact ID. A Registry Contact Check request can determine whether an ID is already in use.

        :param contact_ids: List of contact ids
        :param client_transaction_id: Client transaction id

        :return: contact check result
        :rtype: EppResultData
        """
        result = self.execute(CONTACT_CHECK_XML, ids=contact_ids, client_transaction_id=client_transaction_id)

        if result.code != int(EppResultCode.SUCCESS.value):
            return result

        raw_response = BeautifulSoup(result.raw_response, 'xml')
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

        result.result_data = result_data

        return result

    def info(self, contact_id: str, client_transaction_id: Optional[str] = None) -> EppResultData:
        """
        A successful Contact Info request retrieves information associated with an existing contact.
        All available information is returned if the querying Registrar is the contact’s sponsor. For a non-sponsoring
        Registrar, all contact information is returned if the correct authorization code is entered. As well, if the
        Authorization Code Expiry has been configured, the authorization code must not be expired. Otherwise,
        the <contact:info> will fail.

        :param contact_id: Contact ID
        :param client_transaction_id: Client transaction id

        :return: Contact details
        :rtype: EppResultData
        """
        result = self.execute(CONTACT_INFO_XML, id=contact_id, client_transaction_id=client_transaction_id)

        if result.code != int(EppResultCode.SUCCESS.value):
            return result

        raw_response = BeautifulSoup(result.raw_response, 'xml')

        result_data = {
            'id': raw_response.find('id').text,
            'status': [status.text for status in raw_response.find_all('status')],
            'create_date': raw_response.find('crDate').text,
            'creat_client_id': raw_response.find('crID').text,
            'sponsoring_client_id': raw_response.find('clID').text,
            'update_client_id': raw_response.find('upID').text,
            'update_date': raw_response.find('upDate').text,
            'postal_info': PostalInfoData(**{
                'name': raw_response.find('name').text,
                'organization': raw_response.find('org').text if raw_response.find('org') else None,
                'address': AddressData(**{
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
                }),
            }),
            'phone': raw_response.find('voice').text if raw_response.find('voice') else None,
            'fax': raw_response.find('fax').text if raw_response.find('fax') else None,
            'email': raw_response.find('email').text,
        }

        if raw_response.find('pw'):
            result_data['password'] = raw_response.find('pw').text

        result.result_data = ContactData(**result_data)

        return result

    def create(self, contact: ContactData, client_transaction_id: Optional[str] = None) -> EppResultData:
        """A successful Contact Create request creates a contact object in the Registry. To create a domain name
        successfully, a Registrar does not need to be the sponsor of the related hosts but must be the sponsor of all
        assigned contacts.

        :param contact: Contact
        :param client_transaction_id: Client transaction id

        :return: Result object
        :rtype: EppResultData
        """
        params = self._data_to_dict(contact)
        params['client_transaction_id'] = client_transaction_id

        result = self.execute(CONTACT_CREAT_XML, **params)

        return result

    def delete(self, contact_id: str, client_transaction_id: Optional[str] = None) -> EppResultData:
        """A successful Contact Delete request deletes a contact object from the Registry

        :param contact_id: Contact ID
        :param client_transaction_id: Client transaction id

        :return: Result object
        """
        result = self.execute(CONTACT_DELETE_XML, id=contact_id, client_transaction_id=client_transaction_id)

        return result

    def update(self,
               contact: ContactData,
               add_status: Optional[str] = '',
               remove_status: Optional[str] = '',
               client_transaction_id: Optional[str] = None
               ) -> EppResultData:
        """A successful Contact Update request modifies a contact object in the Registry. Updates to Registrant contacts
        must be valid and must be complete.

        :param contact: Contact details to be updated
        :param add_status: Status to be added
        :param remove_status: Status to be removed
        :param client_transaction_id: Client transaction id

        :return: Result object
        :rtype: EppResultData
        """

        params = self._data_to_dict(contact)

        params['add_status'] = add_status
        params['remove_status'] = remove_status

        params['postalinfo_change'] = bool(contact.postal_info)
        params['address_change'] = bool(contact.postal_info.address)
        params['client_transaction_id'] = client_transaction_id

        result = self.execute(CONTACT_UPDATE_XML, **params)

        return result
