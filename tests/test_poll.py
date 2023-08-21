"""
Host Name Mapping unit tests
"""
import unittest
from datetime import date
from unittest.mock import MagicMock

from pyepp.poll import Poll, ServiceMessageQueueData, ServiceMessageData
from pyepp.epp import EppCommunicator, EppResultData


class HostTest(unittest.TestCase):
    """
    Host mapping name unit tests
    """

    def setUp(self) -> None:
        self.maxDiff = None

    def test_poll_request_unsuccessful(self) -> None:
        epp_communicator = MagicMock(EppCommunicator)
        poll = Poll(epp_communicator)
        expected_result = \
            EppResultData(**{'code': 2000, 'message': "Command completed unsuccessfully",
                             'reason': None, 'raw_response': "response", 'result_data': None})
        poll.execute = MagicMock(return_value=expected_result)

        result = poll.request()

        self.assertEqual(result, expected_result)

    def test_poll_request(self) -> None:
        epp_communicator = MagicMock(EppCommunicator)
        poll = Poll(epp_communicator)
        expected_result = \
            EppResultData(**{'client_transaction_id': 'c6710aac-cbcf-48d0-9ec3-cfaad1cadc81',
                             'code': 1301,
                             'message': 'Command completed successfully; ack to dequeue',
                             'raw_response': '<response>\n'
                                             '<result code="1301">\n'
                                             '<msg>Command completed successfully; ack to dequeue</msg>\n'
                                             '</result>\n'
                                             '<msgQ count="1" id="27690316">\n'
                                             '<qDate>2023-07-26T00:21:31.246Z</qDate>\n'
                                             '<msg lang="en">Contact inz-contact-1 has been '
                                             'deleted.</msg>\n'
                                             '</msgQ>\n'
                                             '<trID>\n'
                                             '<clTRID>c6710aac-cbcf-48d0-9ec3-cfaad1cadc81</clTRID>\n'
                                             '<svTRID>CIRA-000097025501-0000000002</svTRID>\n'
                                             '</trID>\n'
                                             '</response>',
                             'reason': None,
                             'repository_object_id': None,
                             'result_data': ServiceMessageQueueData(message_count='1',
                                                                    message_id='27690316',
                                                                    queue_date='2023-07-26T00:21:31.246Z',
                                                                    messages=[ServiceMessageData(language='en',
                                                                                                 message='Contact '
                                                                                                         'inz-contact-1 '
                                                                                                         'has '
                                                                                                         'been '
                                                                                                         'deleted.')]),
                             'server_transaction_id': 'CIRA-000097025501-0000000002'})

        poll.execute = MagicMock(return_value=expected_result)

        result = poll.request()

        self.assertEqual(result, expected_result)

    def test_poll_ack_unsuccessful(self) -> None:
        epp_communicator = MagicMock(EppCommunicator)
        poll = Poll(epp_communicator)
        expected_result = \
            EppResultData(**{'code': 1500, 'message': "Command completed successfully",
                             'reason': None, 'raw_response': "response", 'result_data': None})
        poll.execute = MagicMock(return_value=expected_result)

        result = poll.acknowledge(121212)

        self.assertEqual(result, expected_result)

    def test_poll_ack(self) -> None:
        epp_communicator = MagicMock(EppCommunicator)
        poll = Poll(epp_communicator)
        expected_result = \
            EppResultData(**{'client_transaction_id': 'c6710aac-cbcf-48d0-9ec3-cfaad1cadc81',
                             'code': 1301,
                             'message': 'Command completed successfully',
                             'raw_response': '<response>\n'
                                             '<result code="1000">\n'
                                             '<msg>Command completed successfully</msg>\n'
                                             '</result>\n'
                                             '<msgQ count="1" id="27690316">\n'
                                             '</msgQ>\n'
                                             '<trID>\n'
                                             '<clTRID>c6710aac-cbcf-48d0-9ec3-cfaad1cadc81</clTRID>\n'
                                             '<svTRID>CIRA-000097025501-0000000002</svTRID>\n'
                                             '</trID>\n'
                                             '</response>',
                             'reason': None,
                             'repository_object_id': None,
                             'result_data': None,
                             'server_transaction_id': 'CIRA-000097025501-0000000002'})

        poll.execute = MagicMock(return_value=expected_result)

        result = poll.acknowledge(27690316)

        self.assertEqual(result, expected_result)
