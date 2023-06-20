"""
Host Name Mapping unit tests
"""
import unittest
from datetime import date
from unittest.mock import MagicMock

from pyepp.host import Host, HostData, IPAddressData
from pyepp.epp import EppCommunicator


class HostTest(unittest.TestCase):
    """
    Host mapping name unit tests
    """

    def setUp(self) -> None:
        self.maxDiff = None

    def test_check_unsuccessful(self) -> None:
        epp_communicator = MagicMock(EppCommunicator)
        host = Host(epp_communicator)
        expected_result = {'code': 2000}
        host.execute = MagicMock(return_value=expected_result)

        result = host.check(['test.host.nz'])

        self.assertDictEqual(result, expected_result)

    def test_check(self) -> None:
        epp_communicator = MagicMock(EppCommunicator)
        host = Host(epp_communicator)
        expected_result = {'client_transaction_id': 'cc7d1dba-2c89-4934-9cd2-688f14aafc8c',
                           'code': 1000,
                           'message': 'Command completed successfully',
                           'raw_response': '<response>\n'
                                           '<result code="1000">\n'
                                           '<msg>Command completed successfully</msg>\n'
                                           '</result>\n'
                                           '<resData>\n'
                                           '<host:chkData>\n'
                                           '<host:cd>\n'
                                           '<host:name avail="true">test1.ehsan.nz</host:name>\n'
                                           '</host:cd>\n'
                                           '<host:cd>\n'
                                           '<host:name '
                                           'avail="false">0qx.test-3gudmj2badfgwhaubrm8douuldtkz4.co.nz</host:name>\n'
                                           '<host:reason>Selected host is not available</host:reason>\n'
                                           '</host:cd>\n'
                                           '</host:chkData>\n'
                                           '</resData>\n'
                                           '<trID>\n'
                                           '<clTRID>cc7d1dba-2c89-4934-9cd2-688f14aafc8c</clTRID>\n'
                                           '<svTRID>CIRA-000071511943-0000000003</svTRID>\n'
                                           '</trID>\n'
                                           '</response>',
                           'reason': None,
                           'repository_object_id': None,
                           'result_data': {'0qx.test-3gudmj2badfgwhaubrm8douuldtkz4.co.nz': {'avail': False,
                                                                                             'reason': 'Selected '
                                                                                                       'host '
                                                                                                       'is '
                                                                                                       'not '
                                                                                                       'available'},
                                           'test1.host.nz': {'avail': True, 'reason': None}},
                           'server_transaction_id': 'CIRA-000071511943-0000000003'}
        host.execute = MagicMock(return_value=expected_result)

        result = host.check(['0qx.test-3gudmj2badfgwhaubrm8douuldtkz4.co.nz', 'itest1.host.nz'])

        self.assertDictEqual(result, expected_result)

    def test_info_unsuccessful(self) -> None:
        epp_communicator = MagicMock(EppCommunicator)
        host = Host(epp_communicator)
        expected_result = {'code': 2000}
        host.execute = MagicMock(return_value=expected_result)

        result = host.info('host.internet.nz')

        self.assertDictEqual(result, expected_result)

    def test_info(self) -> None:
        epp_communicator = MagicMock(EppCommunicator)
        host = Host(epp_communicator)
        execute_result = {'client_transaction_id': 'fecb12df-bc07-4acf-bbc8-e2c5326f63e8',
                          'code': 1000,
                          'message': 'Command completed successfully',
                          'raw_response': '<response>\n'
                                          '<result code="1000">\n'
                                          '<msg>Command completed successfully</msg>\n'
                                          '</result>\n'
                                          '<resData>\n'
                                          '<host:infData>\n'
                                          '<host:name>0qx.test-3gudmj2badfgwhaubrm8douuldtkz4.co.nz</host:name>\n'
                                          '<host:roid>12313305-INZ</host:roid>\n'
                                          '<host:status s="linked"/>\n'
                                          '<host:addr ip="v4">192.1.2.3</host:addr>\n'
                                          '<host:addr '
                                          'ip="v6">2620:0:1009:3:7426:52dc:b8c1:51b2</host:addr>\n'
                                          '<host:clID>163</host:clID>\n'
                                          '<host:crID>163</host:crID>\n'
                                          '<host:crDate>2023-05-27T08:06:36.407Z</host:crDate>\n'
                                          '<host:upID>CIRA_RAR_1</host:upID>\n'
                                          '<host:upDate>2023-05-27T08:09:49.271Z</host:upDate>\n'
                                          '</host:infData>\n'
                                          '</resData>\n'
                                          '<trID>\n'
                                          '<clTRID>fecb12df-bc07-4acf-bbc8-e2c5326f63e8</clTRID>\n'
                                          '<svTRID>CIRA-000073271502-0000000003</svTRID>\n'
                                          '</trID>\n'
                                          '</response>',
                          'reason': None,
                          'repository_object_id': '12313305-INZ',
                          'server_transaction_id': 'CIRA-000073271502-0000000003'}

        expected_result = {'client_transaction_id': 'fecb12df-bc07-4acf-bbc8-e2c5326f63e8',
                           'code': 1000,
                           'message': 'Command completed successfully',
                           'raw_response': '<response>\n'
                                           '<result code="1000">\n'
                                           '<msg>Command completed successfully</msg>\n'
                                           '</result>\n'
                                           '<resData>\n'
                                           '<host:infData>\n'
                                           '<host:name>0qx.test-3gudmj2badfgwhaubrm8douuldtkz4.co.nz</host:name>\n'
                                           '<host:roid>12313305-INZ</host:roid>\n'
                                           '<host:status s="linked"/>\n'
                                           '<host:addr ip="v4">192.1.2.3</host:addr>\n'
                                           '<host:addr '
                                           'ip="v6">2620:0:1009:3:7426:52dc:b8c1:51b2</host:addr>\n'
                                           '<host:clID>163</host:clID>\n'
                                           '<host:crID>163</host:crID>\n'
                                           '<host:crDate>2023-05-27T08:06:36.407Z</host:crDate>\n'
                                           '<host:upID>CIRA_RAR_1</host:upID>\n'
                                           '<host:upDate>2023-05-27T08:09:49.271Z</host:upDate>\n'
                                           '</host:infData>\n'
                                           '</resData>\n'
                                           '<trID>\n'
                                           '<clTRID>fecb12df-bc07-4acf-bbc8-e2c5326f63e8</clTRID>\n'
                                           '<svTRID>CIRA-000073271502-0000000003</svTRID>\n'
                                           '</trID>\n'
                                           '</response>',
                           'reason': None,
                           'repository_object_id': '12313305-INZ',
                           'result_data': HostData(host_name='0qx.test-3gudmj2badfgwhaubrm8douuldtkz4.co.nz',
                                                   status=['linked'],
                                                   address=[IPAddressData(address='192.1.2.3', ip='v4'),
                                                            IPAddressData(address='2620:0:1009:3:7426:52dc:b8c1:51b2',
                                                                          ip='v6')],
                                                   create_date='2023-05-27T08:06:36.407Z',
                                                   creat_client_id='163',
                                                   update_client_id='CIRA_RAR_1',
                                                   update_date='2023-05-27T08:09:49.271Z'),
                           'server_transaction_id': 'CIRA-000073271502-0000000003'}

        host.execute = MagicMock(return_value=execute_result)

        result = host.info('0qx.test-3gudmj2badfgwhaubrm8douuldtkz4.co.nz')

        self.assertDictEqual(result, expected_result)
