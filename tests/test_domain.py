"""
Domain unit tests
"""
import unittest
from datetime import date
from unittest.mock import MagicMock

from pyepp.domain import Domain, DomainData, DSRecordData, DNSSECAlgorithm, DigestTypeEnum
from pyepp.epp import EppCommunicator, EppResultData


class DomainTest(unittest.TestCase):
    """
    Domain name unit tests
    """

    def setUp(self) -> None:
        self.maxDiff = None

    def test_check_unsuccessful(self) -> None:
        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        expected_result = \
            EppResultData(**{'code': 2000, 'message': "Command completed unsuccessfully",
                             'reason': None, 'raw_response': "response", 'result_data': None})
        domain.execute = MagicMock(return_value=expected_result)

        result = domain.check(['internet.nz'])

        self.assertEqual(result, expected_result)

    def test_check(self) -> None:
        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        expected_result = (
            EppResultData(**{'client_transaction_id': '8d537a88-b18c-4f74-903e-aff9be1f902d',
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
                             'server_transaction_id': 'CIRA-000062431732-0000000003'}))

        domain.execute = MagicMock(return_value=expected_result)

        result = domain.check(['inz1.nz', 'inz2.nz', 'inz3.nz'])

        self.assertEqual(result, expected_result)

    def test_info_unsuccessful(self) -> None:
        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        expected_result = \
            EppResultData(**{'code': 2000, 'message': "Command completed unsuccessfully",
                             'reason': None, 'raw_response': "response", 'result_data': None})
        domain.execute = MagicMock(return_value=expected_result)

        result = domain.info('internet.nz')

        self.assertEqual(result, expected_result)

    def test_info(self) -> None:
        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        execute_result = (
            EppResultData(**{'client_transaction_id': None,
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
                                             '<extension>\n'
                                             '<secDNS:infData '
                                             'xmlns:secDNS="urn:ietf:params:xml:ns:secDNS-1.1">\n'
                                             '<secDNS:dsData>\n'
                                             '<secDNS:keyTag>17600</secDNS:keyTag>\n'
                                             '<secDNS:alg>13</secDNS:alg>\n'
                                             '<secDNS:digestType>1</secDNS:digestType>\n'
                                             '<secDNS:digest>4ffb0f3f0fb5edbaa0067d1cd94bb545249cfea2</secDNS:digest>\n'
                                             '<secDNS:keyData>\n'
                                             '<secDNS:flags>257</secDNS:flags>\n'
                                             '<secDNS:protocol>3</secDNS:protocol>\n'
                                             '<secDNS:alg>14</secDNS:alg>\n'
                                             '<secDNS:pubKey>1fHiagyGUIxsDmeYaaKOWceffQn7QTaCwM1y6Oy1zYRpndxu/6WAHM99p/X/dM7t+RcGahZ8+GlX5JHkbyaMllg==</secDNS:pubKey>\n'
                                             '</secDNS:keyData>\n'
                                             '</secDNS:dsData>\n'
                                             '<secDNS:dsData>\n'
                                             '<secDNS:keyTag>17600</secDNS:keyTag>\n'
                                             '<secDNS:alg>13</secDNS:alg>\n'
                                             '<secDNS:digestType>2</secDNS:digestType>\n'
                                             '<secDNS:digest>024c96b094aaad3892babb303e02587f7d6f8f749fef9ff642e3bb8bfc2e0dcf</secDNS:digest>\n'
                                             '<secDNS:keyData>\n'
                                             '<secDNS:flags>257</secDNS:flags>\n'
                                             '<secDNS:protocol>3</secDNS:protocol>\n'
                                             '<secDNS:alg>13</secDNS:alg>\n'
                                             '<secDNS:pubKey>2fHiagyGUIxsDmeYaaKOWceffQn7QTaCwM1y6Oy1zYRpndxu/6WAHM99p/X/dM7t+RcGahZ8+GlX5JHkbyaMllg==</secDNS:pubKey>\n'
                                             '</secDNS:keyData>\n'
                                             '</secDNS:dsData>\n'
                                             '<secDNS:dsData>\n'
                                             '<secDNS:keyTag>17600</secDNS:keyTag>\n'
                                             '<secDNS:alg>13</secDNS:alg>\n'
                                             '<secDNS:digestType>4</secDNS:digestType>\n'
                                             '<secDNS:digest>14d92f9f1e82c0906e2003b9e3401de4024f705724ef14d848fc2708d5714d5572db040faa3e317753e6577c7e70cbb8</secDNS:digest>\n'
                                             '<secDNS:keyData>\n'
                                             '<secDNS:flags>257</secDNS:flags>\n'
                                             '<secDNS:protocol>3</secDNS:protocol>\n'
                                             '<secDNS:alg>13</secDNS:alg>\n'
                                             '<secDNS:pubKey>3fHiagyGUIxsDmeYaaKOWceffQn7QTaCwM1y6Oy1zYRpndxu/6WAHM99p/X/dM7t+RcGahZ8+GlX5JHkbyaMllg==</secDNS:pubKey>\n'
                                             '</secDNS:keyData>\n'
                                             '</secDNS:dsData>\n'
                                             '</secDNS:infData>\n'
                                             '<rgp:infData xmlns:rgp="urn:ietf:params:xml:ns:rgp-1.0">\n'
                                             '<rgp:rgpStatus s="addPeriod"/>\n'
                                             '</rgp:infData>\n'
                                             '<regtype:infData '
                                             'xmlns:regtype="urn:ietf:params:xml:ns:regtype-0.1">\n'
                                             '<regtype:type>standard</regtype:type>\n'
                                             '</regtype:infData>\n'
                                             '</extension>\n'
                                             '<trID>\n'
                                             '<svTRID>CIRA-000063163743-0000000003</svTRID>\n'
                                             '</trID>\n'
                                             '</response>',
                             'reason': None,
                             'repository_object_id': '9204701-INZ',
                             'server_transaction_id': 'CIRA-000063163743-0000000003',
                             'result_data': None}))

        expected_result = \
            EppResultData(**{'client_transaction_id': None,
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
                                             '<extension>\n'
                                             '<secDNS:infData '
                                             'xmlns:secDNS="urn:ietf:params:xml:ns:secDNS-1.1">\n'
                                             '<secDNS:dsData>\n'
                                             '<secDNS:keyTag>17600</secDNS:keyTag>\n'
                                             '<secDNS:alg>13</secDNS:alg>\n'
                                             '<secDNS:digestType>1</secDNS:digestType>\n'
                                             '<secDNS:digest>4ffb0f3f0fb5edbaa0067d1cd94bb545249cfea2</secDNS:digest>\n'
                                             '<secDNS:keyData>\n'
                                             '<secDNS:flags>257</secDNS:flags>\n'
                                             '<secDNS:protocol>3</secDNS:protocol>\n'
                                             '<secDNS:alg>14</secDNS:alg>\n'
                                             '<secDNS:pubKey>1fHiagyGUIxsDmeYaaKOWceffQn7QTaCwM1y6Oy1zYRpndxu/6WAHM99p/X/dM7t+RcGahZ8+GlX5JHkbyaMllg==</secDNS:pubKey>\n'
                                             '</secDNS:keyData>\n'
                                             '</secDNS:dsData>\n'
                                             '<secDNS:dsData>\n'
                                             '<secDNS:keyTag>17600</secDNS:keyTag>\n'
                                             '<secDNS:alg>13</secDNS:alg>\n'
                                             '<secDNS:digestType>2</secDNS:digestType>\n'
                                             '<secDNS:digest>024c96b094aaad3892babb303e02587f7d6f8f749fef9ff642e3bb8bfc2e0dcf</secDNS:digest>\n'
                                             '<secDNS:keyData>\n'
                                             '<secDNS:flags>257</secDNS:flags>\n'
                                             '<secDNS:protocol>3</secDNS:protocol>\n'
                                             '<secDNS:alg>13</secDNS:alg>\n'
                                             '<secDNS:pubKey>2fHiagyGUIxsDmeYaaKOWceffQn7QTaCwM1y6Oy1zYRpndxu/6WAHM99p/X/dM7t+RcGahZ8+GlX5JHkbyaMllg==</secDNS:pubKey>\n'
                                             '</secDNS:keyData>\n'
                                             '</secDNS:dsData>\n'
                                             '<secDNS:dsData>\n'
                                             '<secDNS:keyTag>17600</secDNS:keyTag>\n'
                                             '<secDNS:alg>13</secDNS:alg>\n'
                                             '<secDNS:digestType>4</secDNS:digestType>\n'
                                             '<secDNS:digest>14d92f9f1e82c0906e2003b9e3401de4024f705724ef14d848fc2708d5714d5572db040faa3e317753e6577c7e70cbb8</secDNS:digest>\n'
                                             '<secDNS:keyData>\n'
                                             '<secDNS:flags>257</secDNS:flags>\n'
                                             '<secDNS:protocol>3</secDNS:protocol>\n'
                                             '<secDNS:alg>13</secDNS:alg>\n'
                                             '<secDNS:pubKey>3fHiagyGUIxsDmeYaaKOWceffQn7QTaCwM1y6Oy1zYRpndxu/6WAHM99p/X/dM7t+RcGahZ8+GlX5JHkbyaMllg==</secDNS:pubKey>\n'
                                             '</secDNS:keyData>\n'
                                             '</secDNS:dsData>\n'
                                             '</secDNS:infData>\n'
                                             '<rgp:infData xmlns:rgp="urn:ietf:params:xml:ns:rgp-1.0">\n'
                                             '<rgp:rgpStatus s="addPeriod"/>\n'
                                             '</rgp:infData>\n'
                                             '<regtype:infData '
                                             'xmlns:regtype="urn:ietf:params:xml:ns:regtype-0.1">\n'
                                             '<regtype:type>standard</regtype:type>\n'
                                             '</regtype:infData>\n'
                                             '</extension>\n'
                                             '<trID>\n'
                                             '<svTRID>CIRA-000063163743-0000000003</svTRID>\n'
                                             '</trID>\n'
                                             '</response>',
                             'repository_object_id': '9204701-INZ',
                             'result_data': DomainData(domain_name='internet.nz',
                                                       sponsoring_client_id='933',
                                                       status=['inactive'],
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
                                                       period=None,
                                                       dns_sec=[DSRecordData(key_tag='17600',
                                                                             algorithm='13',
                                                                             digest_type='1',
                                                                             digest='4ffb0f3f0fb5edbaa0067d1cd94bb545249cfea2',
                                                                             dns_key={'algorithm': '13',
                                                                                      'flag': '257',
                                                                                      'protocol': '3',
                                                                                      'public_key': '1fHiagyGUIxsDmeYaaKOWceffQn7QTaCwM1y6Oy1zYRpndxu/6WAHM99p/X/dM7t+RcGahZ8+GlX5JHkbyaMllg=='}),
                                                                DSRecordData(key_tag='17600',
                                                                             algorithm='13',
                                                                             digest_type='2',
                                                                             digest='024c96b094aaad3892babb303e02587f7d6f8f749fef9ff642e3bb8bfc2e0dcf',
                                                                             dns_key={'algorithm': '13',
                                                                                      'flag': '257',
                                                                                      'protocol': '3',
                                                                                      'public_key': '2fHiagyGUIxsDmeYaaKOWceffQn7QTaCwM1y6Oy1zYRpndxu/6WAHM99p/X/dM7t+RcGahZ8+GlX5JHkbyaMllg=='}),
                                                                DSRecordData(key_tag='17600',
                                                                             algorithm='13',
                                                                             digest_type='4',
                                                                             digest='14d92f9f1e82c0906e2003b9e3401de4024f705724ef14d848fc2708d5714d5572db040faa3e317753e6577c7e70cbb8',
                                                                             dns_key={'algorithm': '13',
                                                                                      'flag': '257',
                                                                                      'protocol': '3',
                                                                                      'public_key': '3fHiagyGUIxsDmeYaaKOWceffQn7QTaCwM1y6Oy1zYRpndxu/6WAHM99p/X/dM7t+RcGahZ8+GlX5JHkbyaMllg=='})]
                                                       ),
                             'server_transaction_id': 'CIRA-000063163743-0000000003'})

        domain.execute = MagicMock(return_value=execute_result)

        result = domain.info('internet.nz')
        self.assertEqual(result, expected_result)

    def test_create(self) -> None:
        expected_result = (
            EppResultData(**{'client_transaction_id': '96aaf073-5741-47bd-b1eb-b5abcf4206fa',
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
                             'server_transaction_id': 'CIRA-000064317159-0000000003',
                             'result_data': None}))

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

        self.assertEqual(result, expected_result)

    def test_delete(self) -> None:
        expected_result = EppResultData(**{'client_transaction_id': 'b9c0c77d-b2d9-47c7-9edb-b4d4988c2e7d',
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
                                           'server_transaction_id': 'CIRA-000064688525-0000000004',
                                           'result_data': None})

        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        domain.execute = MagicMock(return_value=expected_result)

        result = domain.delete('internet.nz')

        self.assertEqual(result, expected_result)

    def test_renew(self) -> None:
        expected_result = EppResultData(
            **{'client_transaction_id': '3fc04fc6-0b40-4979-99c0-fa91e9da573f',
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
               'server_transaction_id': 'CIRA-000065618145-0000000004',
               'result_data': None})

        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        domain.execute = MagicMock(return_value=expected_result)

        result = domain.renew(domain_name='internet.nz', expiry_date=date(2024, 1, 1), period=2)

        self.assertEqual(result, expected_result)

    def test_transfer(self) -> None:
        expected_result = EppResultData(
            **{'client_transaction_id': '3fc04fc6-0b40-4979-99c0-fa91e9da573f',
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
               'server_transaction_id': 'CIRA-000065618145-0000000004',
               'result_data': None})

        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        domain.execute = MagicMock(return_value=expected_result)

        result = domain.transfer(domain_name='internet.nz', password='PassWord', period=1)

        self.assertEqual(result, expected_result)

    def test_domain_update(self) -> None:
        expected_result = EppResultData(
            **{'client_transaction_id': 'd2066d60-fc5e-4b7a-9001-893ca2957857',
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
               'server_transaction_id': 'CIRA-000068457178-0000000004',
               'result_data': None})

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
                               add_admins=['contact-admin',],
                               add_techs=['contact-tech',])

        self.assertEqual(result, expected_result)
