"""
Domain unit tests
"""
import unittest
from unittest.mock import MagicMock

from pyepp.domain import Domain
from pyepp.epp import EppCommunicator


class ContactTest(unittest.TestCase):
    """
    Contact unit tests
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
                           'registry_object_id': None,
                           'result_data': {'inz3.nz': {'avail': True, 'reason': None},
                                           'inz2.nz': {'avail': True, 'reason': None},
                                           'inz1.nz': {'avail': False, 'reason': 'Registered'}},
                           'server_transaction_id': 'CIRA-000062431732-0000000003'}

        domain.execute = MagicMock(return_value=expected_result)

        result = domain.check(['inz1.nz', 'inz2.nz', 'inz3.nz'])

        self.assertDictEqual(result, expected_result)
