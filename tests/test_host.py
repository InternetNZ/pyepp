"""
Host Name Mapping unit tests
"""
import unittest
from datetime import date
from unittest.mock import MagicMock

from pyepp.host import Host
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
