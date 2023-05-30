"""
Domain unit tests
"""
import unittest
from datetime import date
from unittest.mock import MagicMock

from pyepp.domain import Domain, DomainData, DSRecordData, DNSSECAlgorithm, DigestTypeEnum
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
                                                     host=None,
                                                     registrant='inz-contact-1',
                                                     admin='inz-contact-1',
                                                     tech='inz-contact-1',
                                                     billing=None,
                                                     create_date='2023-02-23T21:56:22.713Z',
                                                     creat_client_id='933',
                                                     update_client_id='CIRA_RAR_1',
                                                     update_date='2023-02-24T21:59:27.901Z',
                                                     expiry_date='2024-02-23T21:56:22.713Z',
                                                     transfer_date=None,
                                                     password=None,
                                                     period=None),
                           'server_transaction_id': 'CIRA-000063163743-0000000003'}

        domain.execute = MagicMock(return_value=execute_result)

        result = domain.info('internet.nz')

        self.assertDictEqual(result, expected_result)

    def test_create(self) -> None:
        expected_result = {'client_transaction_id': '96aaf073-5741-47bd-b1eb-b5abcf4206fa',
                           'code': 1000,
                           'message': 'Command completed successfully',
                           'raw_response': '<response>\n'
                                           '<result code="1000">\n'
                                           '<msg>Command completed successfully</msg>\n'
                                           '</result>\n'
                                           '<resData>\n'
                                           '<domain:creData>\n'
                                           '<domain:name>internet.nz</domain:name>\n'
                                           '<domain:crDate>2023-05-07T23:36:25.681Z</domain:crDate>\n'
                                           '<domain:exDate>2026-05-07T23:36:25.681Z</domain:exDate>\n'
                                           '</domain:creData>\n'
                                           '</resData>\n'
                                           '<trID>\n'
                                           '<clTRID>96aaf073-5741-47bd-b1eb-b5abcf4206fa</clTRID>\n'
                                           '<svTRID>CIRA-000064317159-0000000003</svTRID>\n'
                                           '</trID>\n'
                                           '</response>',
                           'reason': None,
                           'repository_object_id': None,
                           'server_transaction_id': 'CIRA-000064317159-0000000003'}

        create_params = DomainData(
            domain_name='internet.nz',
            registrant='inz-contact-3',
            admin='inz-contact-1',
            tech='inz-contact-1',
            billing='inz-contact-3',
            period=3,
            host=['01y.test-indwrx2vkicn2otgm3otav5wpnzvjd.co.nz', '0d9x6239.drdomain.co.nz'],
            dns_sec=DSRecordData(
                key_tag=1235,
                algorithm=DNSSECAlgorithm.DSA_SHA_1.value,
                digest_type=DigestTypeEnum.SHA_1.value,
                digest='8cdb09364147aed879d12c68d615f98af5900b73'
            ),
        )
        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        domain.execute = MagicMock(return_value=expected_result)

        result = domain.create(create_params)

        self.assertDictEqual(result, expected_result)

    def test_delete(self) -> None:
        expected_result = {'client_transaction_id': 'b9c0c77d-b2d9-47c7-9edb-b4d4988c2e7d',
                           'code': 1000,
                           'message': 'Command completed successfully',
                           'raw_response': '<response>\n'
                                           '<result code="1000">\n'
                                           '<msg>Command completed successfully</msg>\n'
                                           '</result>\n'
                                           '<trID>\n'
                                           '<clTRID>b9c0c77d-b2d9-47c7-9edb-b4d4988c2e7d</clTRID>\n'
                                           '<svTRID>CIRA-000064688525-0000000004</svTRID>\n'
                                           '</trID>\n'
                                           '</response>',
                           'reason': None,
                           'repository_object_id': None,
                           'server_transaction_id': 'CIRA-000064688525-0000000004'}

        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        domain.execute = MagicMock(return_value=expected_result)

        result = domain.delete('internet.nz')

        self.assertDictEqual(result, expected_result)

    def test_renew(self) -> None:
        expected_result = {'client_transaction_id': '3fc04fc6-0b40-4979-99c0-fa91e9da573f',
                           'code': 1000,
                           'message': 'Command completed successfully',
                           'raw_response': '<response>\n'
                                           '<result code="1000">\n'
                                           '<msg>Command completed successfully</msg>\n'
                                           '</result>\n'
                                           '<resData>\n'
                                           '<domain:renData>\n'
                                           '<domain:name>internet.nz</domain:name>\n'
                                           '<domain:exDate>2026-01-21T21:56:22.713Z</domain:exDate>\n'
                                           '</domain:renData>\n'
                                           '</resData>\n'
                                           '<trID>\n'
                                           '<clTRID>3fc04fc6-0b40-4979-99c0-fa91e9da573f</clTRID>\n'
                                           '<svTRID>CIRA-000065618145-0000000004</svTRID>\n'
                                           '</trID>\n'
                                           '</response>',
                           'reason': None,
                           'repository_object_id': None,
                           'server_transaction_id': 'CIRA-000065618145-0000000004'}

        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        domain.execute = MagicMock(return_value=expected_result)

        result = domain.renew(domain_name='internet.nz', expiry_date=date(2024, 1, 1), period=2)

        self.assertDictEqual(result, expected_result)

    def test_transfer(self) -> None:
        expected_result = {'client_transaction_id': '3fc04fc6-0b40-4979-99c0-fa91e9da573f',
                           'code': 1000,
                           'message': 'Command completed successfully',
                           'raw_response': '<response>\n'
                                           '<result code="1000">\n'
                                           '<msg>Command completed successfully</msg>\n'
                                           '</result>\n'
                                           '<resData>\n'
                                           '<domain:renData>\n'
                                           '<domain:name>internet.nz</domain:name>\n'
                                           '<domain:reID>ClientX</domain:reID>\n'
                                           '<domain:reDate>2000-06-08T22:00:00.0Z</domain:reDate>\n'
                                           '<domain:acID>ClientY</domain:acID>\n'
                                           '<domain:acDate>2000-06-13T22:00:00.0Z</domain:acDate>\n'
                                           '<domain:exDate>2002-09-08T22:00:00.0Z</domain:exDate>\n'
                                           '</domain:renData>\n'
                                           '</resData>\n'
                                           '<trID>\n'
                                           '<clTRID>3fc04fc6-0b40-4979-99c0-fa91e9da573f</clTRID>\n'
                                           '<svTRID>CIRA-000065618145-0000000004</svTRID>\n'
                                           '</trID>\n'
                                           '</response>',
                           'reason': None,
                           'repository_object_id': None,
                           'server_transaction_id': 'CIRA-000065618145-0000000004'}

        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        domain.execute = MagicMock(return_value=expected_result)

        result = domain.transfer(domain_name='internet.nz', password='PassWord', period=1)

        self.assertDictEqual(result, expected_result)

    def test_domain_update(self) -> None:
        expected_result = {'client_transaction_id': 'd2066d60-fc5e-4b7a-9001-893ca2957857',
                           'code': 1000,
                           'message': 'Command completed successfully',
                           'raw_response': '<response>\n'
                                           '<result code="1000">\n'
                                           '<msg>Command completed successfully</msg>\n'
                                           '</result>\n'
                                           '<trID>\n'
                                           '<clTRID>d2066d60-fc5e-4b7a-9001-893ca2957857</clTRID>\n'
                                           '<svTRID>CIRA-000068457178-0000000004</svTRID>\n'
                                           '</trID>\n'
                                           '</response>',
                           'reason': None,
                           'repository_object_id': None,
                           'server_transaction_id': 'CIRA-000068457178-0000000004'}

        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        domain.execute = MagicMock(return_value=expected_result)
        domain.info = MagicMock(return_value={
            'result_data': DomainData(
                domain_name='internet.nz',
                registrant='registrant1',
                admin='old-admin',
                tech='old-tech',
                period=1
            )
        })

        result = domain.update(domain_name='internet.nz',
                               password='PassWord',
                               admin='contact-admin',
                               tech='contact-tech')

        self.assertDictEqual(result, expected_result)
