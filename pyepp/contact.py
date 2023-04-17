"""
Contact Mapping Module
"""
# from dataclasses import dataclass

from pyepp.base_command import BaseCommand
from pyepp.command_templates import CONTACT_CHECK_XML, CONTACT_INFO_XML, CONTACT_CREAT_XML, CONTACT_DELETE_XML, \
    CONTACT_UPDATE_XML
from pyepp.epp import EppResultCode


# @dataclass
# class AddressData:
#     street_1: str
#     street_2: str
#     street_3: str
#     city: str
#     province: str
#     postal_code: str
#     country_code: str
#
#
# @dataclass
# class PostalInfoData:
#     name: str
#     organization: str
#     address: AddressData
#
#
# @dataclass
# class ContactData:
#     id: str
#     postal_info: PostalInfoData
#     phone: str
#     fax: str
#     email: str
#     password: str
#     client_transaction_id: str
#     server_transaction_id: str
#     registry_object_id: str

class Contact(BaseCommand):
    """
    Epp Contact
    """

    def __init__(self, epp_communicator):
        super(Contact).__init__(epp_communicator)

    def check(self, ids):
        """
        This command is used to determine if an object can be provisioned.

        :param list ids: List of contact ids

        :return: contact check result
        :rtype: dict
        """
        result = self.execute(CONTACT_CHECK_XML, contact_ids=ids)

        if result.get('code') != EppResultCode.SUCCESS.value:
            return result

        raw_response = result.get('raw_response')
        contacts_check_data = raw_response.find_all('contact:cd')

        result_data = {}
        for contact_cd in contacts_check_data:
            contact = contact_cd.find('contact:id')
            available = contact.get('avail') in ('true', '1')
            reason = contact_cd.find('contact:reason').text if not available else None
            result_data[contact.text] = {
                'avail': available,
                'reason': reason,
            }

        result['result_data'] = result_data

        return result

    def info(self, contact_id):
        """
        Retrieve contact details.

        :param str contact_id: Contact ID

        :return: Contact details
        :rtype: dict
        """
        result = self.execute(CONTACT_INFO_XML, contact_id=contact_id)

        raw_response = result.get('raw_response')

        result_data = {
            'id': raw_response.find('contact:id').text,
            'repository_id': raw_response.find('contact:roid').text,
            'status': raw_response.find_all('contact:status'),
            'create_date': raw_response.find('contact:crDate').text,
            'creat_client_id': raw_response.find('contact:crDate').text,
            'sponsoring_client_id': raw_response.find('contact:clID').text,
            'update_client_id': raw_response.find('contact:upID').text,
            'update_date': raw_response.find('contact:upDate').text,
            'name': raw_response.find('contact:name').text,
            'address': {
                'street_1': raw_response.find_all('contact:street')[0].text,
                'street_2': raw_response.find_all('contact:street')[1].text
                if len(raw_response.find_all('contact:street')) > 1 else None,
                'street_3': raw_response.find_all('contact:street')[2].text
                if len(raw_response.find_all('contact:street')) > 2 else None,
                'city': raw_response.find('contact:city').text,
                'province': raw_response.find('contact:sp').text if raw_response.find('contact:sp') else None,
                'postal_code': raw_response.find('contact:pc').text if raw_response.find(
                    'contact:pc') else None,
                'country_code': raw_response.find('contact:cc').text,
            },
            'phone': raw_response.find('contact:voice').text if raw_response.find('contact:fax') else None,
            'fax': raw_response.find('contact:fax').text if raw_response.find('contact:fax') else None,
            'email': raw_response.find('contact:email').text,
        }

        if raw_response.find('contact:pw'):
            result_data['password'] = raw_response.find('contact:pw').text

        result['result_data'] = result_data

        return result

    # pylint: disable=too-many-arguments,too-many-locals
    def create(self,
               contact_id,
               name,
               street_1,
               city,
               country_code,
               email,
               organization=None,
               street_2=None,
               street_3=None,
               province=None,
               postal_code=None,
               phone='',
               fax='',
               password=None,
               ):
        """
        Create a contact object.

        :param str contact_id: Contact ID
        :param str name: Contact Name
        :param str street_1: Street address line 1
        :param str street_2: Street address line 2 (OPTIONAL)
        :param str street_3: Street address line 3 (OPTIONAL)
        :param str city: City name
        :param str country_code: Country code
        :param str email: Email address
        :param str organization: Organization name (OPTIONAL)
        :param str province: Province (OPTIONAL)
        :param str postal_code: Postal code (OPTIONAL)
        :param str phone: Phone number (OPTIONAL)
        :param str fax: Fax Number (OPTIONAL)
        :param str password: Password (OPTIONAL)

        :return: Response object
        :rtype: dict
        """
        params = {
            'id': contact_id,
            'name': name,
            'street_1': street_1,
            'city': city,
            'country_code': country_code,
            'organization': organization,
            'email': email,
            'street_2': street_2,
            'street_3': street_3,
            'province': province,
            'postal_code': postal_code,
            'phone': phone,
            'fax': fax,
            'password': password,
        }

        result = self.execute(CONTACT_CREAT_XML, **params)

        return result

    def delete(self, contact_id):
        """
        Delete a contact object.

        :param str contact_id: Contact ID

        :return: Response object
        :rtype: dict
        """
        result = self.execute(CONTACT_DELETE_XML, id=contact_id)

        return result

    # pylint: disable=too-many-arguments,too-many-locals
    def update(self,
               contact_id,
               name=None,
               add_status=None,
               remove_status=None,
               street_1=None,
               street_2=None,
               street_3=None,
               city=None,
               country_code=None,
               email=None,
               organization=None,
               province=None,
               postal_code=None,
               phone='',
               fax='',
               password=None,
               ):
        """
        Update the contact.

        :param str contact_id: Contact ID
        :param str name: Contact Name
        :param str add_status: Status to be added
        :param str remove_status: Status to be removed
        :param str street_1: Street address line 1
        :param str street_2: Street address line 2
        :param str street_3: Street address line 3
        :param str city: City name
        :param str country_code: Country code
        :param str email: Email address
        :param str organization: Organization name
        :param str province: Province
        :param str postal_code: Postal code
        :param str phone: Phone number
        :param str fax: Fax Number
        :param str password: Password

        :return: Response object
        :rtype: dict
        """

        params = {
            'id': contact_id,
            'name': name,
            'add_status': add_status,
            'remove_status': remove_status,
            'street_1': street_1,
            'city': city,
            'country_code': country_code,
            'organization': organization,
            'email': email,
            'street_2': street_2,
            'street_3': street_3,
            'province': province,
            'postal_code': postal_code,
            'phone': phone,
            'fax': fax,
            'password': password,
        }

        # pylint: disable=too-many-boolean-expressions
        if street_1 or street_2 or street_3 or city or province or country_code or postal_code:
            params['address_change'] = True

        if params.get('address_change') or name or organization:
            params['postalinfo_change'] = True

        result = self.execute(CONTACT_UPDATE_XML, **params)

        return result
