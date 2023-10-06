"""
Contact unit tests
"""
import unittest
from unittest.mock import MagicMock

from pyepp.contact import ContactData, PostalInfoData, AddressData, Contact
from pyepp.epp import EppCommunicator, EppResultData


class ContactTest(unittest.TestCase):
    """
    Contact unit tests
    """

    def setUp(self) -> None:
        self.maxDiff = None

    def test_data_to_dict(self) -> None:
        data = ContactData(
            id='id',
            status=['status1', 'status2'],
            create_date='create_date',
            creat_client_id='creat_client_id',
            sponsoring_client_id='sponsoring_client_id',
            update_client_id='update_client_id',
            update_date='update_date',
            postal_info=PostalInfoData(
                name='name',
                organization='organization',
                address=AddressData(
                    street_1='street_1',
                    street_2='street_2',
                    street_3='street_3',
                    city='city',
                    province='province',
                    postal_code='postal_code',
                    country_code='country_code',
                ),
            ),
            phone='phone',
            fax='fax',
            email='email',
            password='',
        )

        expected_result = {
            'id': 'id',
            'status': ['status1', 'status2'],
            'create_date': 'create_date',
            'creat_client_id': 'creat_client_id',
            'sponsoring_client_id': 'sponsoring_client_id',
            'update_client_id': 'update_client_id',
            'update_date': 'update_date',
            'name': 'name',
            'organization': 'organization',
            'street_1': 'street_1',
            'street_2': 'street_2',
            'street_3': 'street_3',
            'city': 'city',
            'province': 'province',
            'postal_code': 'postal_code',
            'country_code': 'country_code',
            'phone': 'phone',
            'fax': 'fax',
            'email': 'email',
            'password': '',
        }

        epp_communicator = MagicMock(EppCommunicator)
        contact = Contact(epp_communicator)

        result = contact._data_to_dict(data)
        self.assertDictEqual(result, expected_result)

    def test_check_unsuccessful(self) -> None:
        epp_communicator = MagicMock(EppCommunicator)
        contact = Contact(epp_communicator)
        expected_result = \
            EppResultData(**{'code': 2000, 'message': "Command completed unsuccessfully",
                             'reason': None, 'raw_response': "response", 'result_data': None})
        contact.execute = MagicMock(return_value=expected_result)

        result = contact.check(['contact1'])

        self.assertEqual(result, expected_result)

    def test_check(self) -> None:
        epp_communicator = MagicMock(EppCommunicator)
        contact = Contact(epp_communicator)
        expected_result = EppResultData(**{
            'client_transaction_id': 'eccb044f-a80f-4db3-a918-988f1ac918e3',
            'code': 1000,
            'message': 'Command completed successfully',
            'raw_response': '<response>\n'
                            '<result code="1000">\n'
                            '<msg>Command completed successfully</msg>\n'
                            '</result>\n'
                            '<resData>\n'
                            '<contact:chkData>\n'
                            '<contact:cd>\n'
                            '<contact:id avail="true">contact1</contact:id>\n'
                            '</contact:cd>\n'
                            '</contact:chkData>\n'
                            '</resData>\n'
                            '<trID>\n'
                            '<clTRID>eccb044f-a80f-4db3-a918-988f1ac918e3</clTRID>\n'
                            '<svTRID>CIRA-000062206323-0000000003</svTRID>\n'
                            '</trID>\n'
                            '</response>',
            'reason': None,
            'repository_object_id': None,
            'result_data': {'contact1': {'avail': True, 'reason': None},
                            'contact2': {'avail': False,
                                         'reason': 'Selected contact ID is not '
                                                   'available'}},
            'server_transaction_id': 'CIRA-000062206323-0000000003'
        })

        contact.execute = MagicMock(return_value=expected_result)

        result = contact.check(['contact1', 'contact2'])

        self.assertEqual(result, expected_result)

    def test_info_unsuccessful(self) -> None:
        epp_communicator = MagicMock(EppCommunicator)
        contact = Contact(epp_communicator)
        expected_result = \
            EppResultData(**{'code': 2000, 'message': "Command completed unsuccessfully",
                             'reason': None, 'raw_response': "response", 'result_data': None})
        contact.execute = MagicMock(return_value=expected_result)

        result = contact.info('contact1')

        self.assertEqual(result, expected_result)

    def test_info(self) -> None:
        epp_communicator = MagicMock(EppCommunicator)
        contact = Contact(epp_communicator)
        execute_result = EppResultData(**{
            'client_transaction_id': '5123c3d4-79ce-4d87-ad7b-d234eb992474',
            'code': 1000,
            'message': 'Command completed successfully',
            'raw_response': '<response>\n'
                            '<result code="1000">\n'
                            '<msg>Command completed successfully</msg>\n'
                            '</result>\n'
                            '<resData>\n'
                            '<contact:infData>\n'
                            '<contact:id>inz-contact-1</contact:id>\n'
                            '<contact:roid>9175701-INZ</contact:roid>\n'
                            '<contact:status s="linked"/>\n'
                            '<contact:postalInfo type="loc">\n'
                            '<contact:name>inz</contact:name>\n'
                            '<contact:addr>\n'
                            '<contact:street>18 portmore place</contact:street>\n'
                            '<contact:city>Wellington</contact:city>\n'
                            '<contact:cc>NZ</contact:cc>\n'
                            '</contact:addr>\n'
                            '</contact:postalInfo>\n'
                            '<contact:email>inz@internet.net.nz</contact:email>\n'
                            '<contact:clID>933</contact:clID>\n'
                            '<contact:crID>933</contact:crID>\n'
                            '<contact:crDate>2023-02-23T02:59:16.784Z</contact:crDate>\n'
                            '<contact:upID>CIRA_RAR_1</contact:upID>\n'
                            '<contact:upDate>2023-02-23T21:59:01.021Z</contact:upDate>\n'
                            '<contact:authInfo>\n'
                            '<contact:pw>PassWord</contact:pw>\n'
                            '</contact:authInfo>\n'
                            '</contact:infData>\n'
                            '</resData>\n'
                            '<trID>\n'
                            '<clTRID>5123c3d4-79ce-4d87-ad7b-d234eb992474</clTRID>\n'
                            '<svTRID>CIRA-000062211375-0000000003</svTRID>\n'
                            '</trID>\n'
                            '</response>',
            'reason': None,
            'repository_object_id': '9175701-INZ',
            'server_transaction_id': 'CIRA-000062211375-0000000003',
            'result_data': None
        })

        expected_result = EppResultData(**{
            'client_transaction_id': '5123c3d4-79ce-4d87-ad7b-d234eb992474',
            'code': 1000,
            'message': 'Command completed successfully',
            'raw_response': '<response>\n'
                            '<result code="1000">\n'
                            '<msg>Command completed successfully</msg>\n'
                            '</result>\n'
                            '<resData>\n'
                            '<contact:infData>\n'
                            '<contact:id>inz-contact-1</contact:id>\n'
                            '<contact:roid>9175701-INZ</contact:roid>\n'
                            '<contact:status s="linked"/>\n'
                            '<contact:postalInfo type="loc">\n'
                            '<contact:name>inz</contact:name>\n'
                            '<contact:addr>\n'
                            '<contact:street>18 portmore place</contact:street>\n'
                            '<contact:city>Wellington</contact:city>\n'
                            '<contact:cc>NZ</contact:cc>\n'
                            '</contact:addr>\n'
                            '</contact:postalInfo>\n'
                            '<contact:email>inz@internet.net.nz</contact:email>\n'
                            '<contact:clID>933</contact:clID>\n'
                            '<contact:crID>933</contact:crID>\n'
                            '<contact:crDate>2023-02-23T02:59:16.784Z</contact:crDate>\n'
                            '<contact:upID>CIRA_RAR_1</contact:upID>\n'
                            '<contact:upDate>2023-02-23T21:59:01.021Z</contact:upDate>\n'
                            '<contact:authInfo>\n'
                            '<contact:pw>PassWord</contact:pw>\n'
                            '</contact:authInfo>\n'
                            '</contact:infData>\n'
                            '</resData>\n'
                            '<trID>\n'
                            '<clTRID>5123c3d4-79ce-4d87-ad7b-d234eb992474</clTRID>\n'
                            '<svTRID>CIRA-000062211375-0000000003</svTRID>\n'
                            '</trID>\n'
                            '</response>',
            'reason': None,
            'repository_object_id': '9175701-INZ',
            'result_data': ContactData(id='inz-contact-1',
                                       email='inz@internet.net.nz',
                                       postal_info=PostalInfoData(**{'address': AddressData(**{'city': 'Wellington',
                                                                                               'country_code': 'NZ',
                                                                                               'postal_code': None,
                                                                                               'province': None,
                                                                                               'street_1': '18 portmore '
                                                                                                           'place',
                                                                                               'street_2': None,
                                                                                               'street_3': None}),
                                                                     'name': 'inz',
                                                                     'organization': None}),
                                       status=[''],
                                       phone=None,
                                       fax=None,
                                       password='PassWord',
                                       create_date='2023-02-23T02:59:16.784Z',
                                       creat_client_id='933',
                                       sponsoring_client_id='933',
                                       update_client_id='CIRA_RAR_1',
                                       update_date='2023-02-23T21:59:01.021Z'
                                       ),
            'server_transaction_id': 'CIRA-000062211375-0000000003'
        })

        contact.execute = MagicMock(return_value=execute_result)

        result = contact.info('inz-contact-1')

        self.assertEqual(result, expected_result)

    def test_create(self) -> None:
        expected_result = EppResultData(**{'client_transaction_id': 'caae2895-fe01-4f1c-a892-115b17315acc',
                                           'code': 1000,
                                           'message': 'Command completed successfully',
                                           'raw_response': '<response>\n'
                                                           '<result code="1000">\n'
                                                           '<msg>Command completed successfully</msg>\n'
                                                           '</result>\n'
                                                           '<resData>\n'
                                                           '<contact:creData>\n'
                                                           '<contact:id>inz-contact-1</contact:id>\n'
                                                           '<contact:crDate>2023-04-26T23:06:11.894Z</contact:crDate>\n'
                                                           '</contact:creData>\n'
                                                           '</resData>\n'
                                                           '<trID>\n'
                                                           '<clTRID>caae2895-fe01-4f1c-a892-115b17315acc</clTRID>\n'
                                                           '<svTRID>CIRA-000062214171-0000000003</svTRID>\n'
                                                           '</trID>\n'
                                                           '</response>',
                                           'reason': None,
                                           'repository_object_id': None,
                                           'server_transaction_id': 'CIRA-000062214171-0000000003',
                                           'result_data': None})

        create_params = ContactData(
            id='inz-contact-1',
            email='epp@internetnz.net.nz',
            postal_info=PostalInfoData(
                name='IRS EPP',
                organization='INZ',
                address=AddressData(
                    street_1='18 Willis Street',
                    street_2='Wellington CBD',
                    city='Wellington',
                    country_code='NZ',
                    province='Wellington',
                    postal_code='6011'
                ),
            ),
            phone='+64.111111111'
        )

        epp_communicator = MagicMock(EppCommunicator)
        contact = Contact(epp_communicator)
        contact.execute = MagicMock(return_value=expected_result)

        result = contact.create(create_params)

        self.assertEqual(result, expected_result)

    def test_delete(self) -> None:
        expected_result = EppResultData(**{'client_transaction_id': 'a21a659d-5040-4848-9f5f-0cffa0ff62d1',
                                           'code': 1000,
                                           'message': 'Command completed successfully',
                                           'raw_response': '<response>\n'
                                                           '<result code="1000">\n'
                                                           '<msg>Command completed successfully</msg>\n'
                                                           '</result>\n'
                                                           '<trID>\n'
                                                           '<clTRID>a21a659d-5040-4848-9f5f-0cffa0ff62d1</clTRID>\n'
                                                           '<svTRID>CIRA-000062220522-0000000004</svTRID>\n'
                                                           '</trID>\n'
                                                           '</response>',
                                           'reason': None,
                                           'repository_object_id': None,
                                           'server_transaction_id': 'CIRA-000062220522-0000000004',
                                           'result_data': None})

        epp_communicator = MagicMock(EppCommunicator)
        contact = Contact(epp_communicator)
        contact.execute = MagicMock(return_value=expected_result)

        result = contact.delete('inz-contact-1')

        self.assertEqual(result, expected_result)

    def test_update(self) -> None:
        update_params = ContactData(
            id='inz-contact-1',
            email='ehsan@internetnz.net.nz',
            postal_info=PostalInfoData(name='IRS EPP2')
        )

        expected_result = EppResultData(**{'client_transaction_id': '0e872842-b77b-4800-9572-c72e46e068de',
                                           'code': 1000,
                                           'message': 'Command completed successfully',
                                           'raw_response': '<response>\n'
                                                           '<result code="1000">\n'
                                                           '<msg>Command completed successfully</msg>\n'
                                                           '</result>\n'
                                                           '<trID>\n'
                                                           '<clTRID>0e872842-b77b-4800-9572-c72e46e068de</clTRID>\n'
                                                           '<svTRID>CIRA-000062223355-0000000004</svTRID>\n'
                                                           '</trID>\n'
                                                           '</response>',
                                           'reason': None,
                                           'repository_object_id': None,
                                           'server_transaction_id': 'CIRA-000062223355-0000000004',
                                           'result_data': None})

        epp_communicator = MagicMock(EppCommunicator)
        contact = Contact(epp_communicator)
        contact.execute = MagicMock(return_value=expected_result)

        result = contact.update(update_params)

        self.assertEqual(result, expected_result)
