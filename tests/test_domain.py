"""
Domain unit tests
"""
import unittest
from unittest.mock import MagicMock

from pyepp.domain import Domain, DomainData
from pyepp.epp import EppCommunicator


class DomainTest(unittest.TestCase):
    """
    Domain name unit tests
    """

    def setUp(self) -> None:
        self.maxDiff = None

    def test_check_unsuccessful(self) -> None:
        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        expected_result = {'code': 2000}
        domain.execute = MagicMock(return_value=expected_result)

        result = domain.check(['internet.nz'])

        self.assertDictEqual(result, expected_result)

    def test_check(self) -> None:
        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        expected_result = {'client_transaction_id': '8d537a88-b18c-4f74-903e-aff9be1f902d',
                           'code': 1000,
                           'message': 'Command completed successfully',
                           'raw_response': '<response>\n'
                                           '<result code="1000">\n'
                                           '<msg>Command completed successfully</msg>\n'
                                           '</result>\n'
                                           '<resData>\n'
                                           '<domain:chkData>\n'
                                           '<domain:cd>\n'
                                           '<domain:name avail="false">inz1.nz</domain:name>\n'
                                           '<domain:reason>Registered</domain:reason>\n'
                                           '</domain:cd>\n'
                                           '<domain:cd>\n'
                                           '<domain:name avail="true">inz2.nz</domain:name>\n'
                                           '</domain:cd>\n'
                                           '<domain:cd>\n'
                                           '<domain:name avail="true">inz3.nz</domain:name>\n'
                                           '</domain:cd>\n'
                                           '</domain:chkData>\n'
                                           '</resData>\n'
                                           '<trID>\n'
                                           '<clTRID>8d537a88-b18c-4f74-903e-aff9be1f902d</clTRID>\n'
                                           '<svTRID>CIRA-000062431732-0000000003</svTRID>\n'
                                           '</trID>\n'
                                           '</response>',
                           'reason': None,
                           'repository_object_id': None,
                           'result_data': {'inz3.nz': {'avail': True, 'reason': None},
                                           'inz2.nz': {'avail': True, 'reason': None},
                                           'inz1.nz': {'avail': False, 'reason': 'Registered'}},
                           'server_transaction_id': 'CIRA-000062431732-0000000003'}

        domain.execute = MagicMock(return_value=expected_result)

        result = domain.check(['inz1.nz', 'inz2.nz', 'inz3.nz'])

        self.assertDictEqual(result, expected_result)

    def test_info_unsuccessful(self) -> None:
        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        expected_result = {'code': 2000}
        domain.execute = MagicMock(return_value=expected_result)

        result = domain.info('internet.nz')

        self.assertDictEqual(result, expected_result)

    def test_info(self) -> None:
        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        execute_result = {'client_transaction_id': None,
                          'code': 1000,
                          'message': 'Command completed successfully',
                          'raw_response': '<response>\n'
                                          '<result code="1000">\n'
                                          '<msg>Command completed successfully</msg>\n'
                                          '</result>\n'
                                          '<resData>\n'
                                          '<domain:infData>\n'
                                          '<domain:name>internet.nz</domain:name>\n'
                                          '<domain:roid>9204701-INZ</domain:roid>\n'
                                          '<domain:status s="inactive"/>\n'
                                          '<domain:registrant>inz-contact-1</domain:registrant>\n'
                                          '<domain:contact '
                                          'type="admin">inz-contact-1</domain:contact>\n'
                                          '<domain:contact '
                                          'type="tech">inz-contact-1</domain:contact>\n'
                                          '<domain:clID>933</domain:clID>\n'
                                          '<domain:crID>933</domain:crID>\n'
                                          '<domain:crDate>2023-02-23T21:56:22.713Z</domain:crDate>\n'
                                          '<domain:upID>CIRA_RAR_1</domain:upID>\n'
                                          '<domain:upDate>2023-02-24T21:59:27.901Z</domain:upDate>\n'
                                          '<domain:exDate>2024-02-23T21:56:22.713Z</domain:exDate>\n'
                                          '</domain:infData>\n'
                                          '</resData>\n'
                                          '<trID>\n'
                                          '<svTRID>CIRA-000063163743-0000000003</svTRID>\n'
                                          '</trID>\n'
                                          '</response>',
                          'reason': None,
                          'repository_object_id': '9204701-INZ',
                          'server_transaction_id': 'CIRA-000063163743-0000000003'}

        expected_result = {'client_transaction_id': None,
                           'code': 1000,
                           'message': 'Command completed successfully',
                           'raw_response': '<response>\n'
                                           '<result code="1000">\n'
                                           '<msg>Command completed successfully</msg>\n'
                                           '</result>\n'
                                           '<resData>\n'
                                           '<domain:infData>\n'
                                           '<domain:name>internet.nz</domain:name>\n'
                                           '<domain:roid>9204701-INZ</domain:roid>\n'
                                           '<domain:status s="inactive"/>\n'
                                           '<domain:registrant>inz-contact-1</domain:registrant>\n'
                                           '<domain:contact '
                                           'type="admin">inz-contact-1</domain:contact>\n'
                                           '<domain:contact '
                                           'type="tech">inz-contact-1</domain:contact>\n'
                                           '<domain:clID>933</domain:clID>\n'
                                           '<domain:crID>933</domain:crID>\n'
                                           '<domain:crDate>2023-02-23T21:56:22.713Z</domain:crDate>\n'
                                           '<domain:upID>CIRA_RAR_1</domain:upID>\n'
                                           '<domain:upDate>2023-02-24T21:59:27.901Z</domain:upDate>\n'
                                           '<domain:exDate>2024-02-23T21:56:22.713Z</domain:exDate>\n'
                                           '</domain:infData>\n'
                                           '</resData>\n'
                                           '<trID>\n'
                                           '<svTRID>CIRA-000063163743-0000000003</svTRID>\n'
                                           '</trID>\n'
                                           '</response>',
                           'reason': None,
                           'repository_object_id': '9204701-INZ',
                           'result_data': DomainData(domain_name='internet.nz',
                                                     sponsoring_client_id='933',
                                                     status=[''],
                                                     name_server=None,
                                                     host=[],
                                                     registrant='inz-contact-1',
                                                     create_date='2023-02-23T21:56:22.713Z',
                                                     creat_client_id='933',
                                                     update_client_id='CIRA_RAR_1',
                                                     update_date='2023-02-24T21:59:27.901Z',
                                                     expiry_date='2024-02-23T21:56:22.713Z',
                                                     transfer_date=None,
                                                     password=None),
                           'server_transaction_id': 'CIRA-000063163743-0000000003'}

        domain.execute = MagicMock(return_value=execute_result)

        result = domain.info('internet.nz')

        self.assertDictEqual(result, expected_result)
