"""
Host Name Mapping unit tests
"""

import unittest
from datetime import date
from unittest.mock import MagicMock, patch

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
        expected_result = EppResultData(
            **{
                "code": 2000,
                "message": "Command completed unsuccessfully",
                "reason": None,
                "raw_response": "response",
                "result_data": None,
            }
        )
        poll.execute = MagicMock(return_value=expected_result)

        result = poll.request()

        self.assertEqual(result, expected_result)

    def test_poll_request_dry_run(self) -> None:
        epp_communicator = MagicMock(EppCommunicator)
        poll = Poll(epp_communicator)
        expected_result = EppResultData(
            code=1000,
            message="Dry run",
            reason=None,
            raw_response="<poll:request/>",
            result_data=None,
            dry_run=True,
        )
        poll.execute = MagicMock(return_value=expected_result)
        result = poll.request()
        self.assertEqual(result, expected_result)

    def test_poll_request_uses_parsed_xml_directly(self) -> None:
        """Verify poll.request re-uses result.parsed_xml directly."""
        epp_communicator = MagicMock(EppCommunicator)
        poll = Poll(epp_communicator)
        mock_parsed = MagicMock()
        mock_msgq = MagicMock()
        mock_msgq.get.side_effect = lambda attr: "5" if attr == "count" else "12345"
        mock_qdate = MagicMock(text="2023-01-01T00:00:00Z")
        mock_msg = MagicMock(text="Domain renewed")
        mock_msg.get.return_value = "en"

        mock_parsed.find.side_effect = lambda tag, *args, **kwargs: {
            "msgQ": mock_msgq,
            "qDate": mock_qdate,
            "msg": mock_msg,
        }.get(tag, None)
        mock_parsed.find_all.side_effect = lambda tag, *args, **kwargs: {
            "msg": [MagicMock(), mock_msg],
        }.get(tag, [])

        execute_result = EppResultData(
            code=1301,
            message="Command completed successfully; ack to dequeue",
            reason=None,
            raw_response="<dummy/>",
            result_data=None,
            dry_run=False,
            parsed_xml=mock_parsed,
        )
        poll.execute = MagicMock(return_value=execute_result)
        result = poll.request()
        self.assertEqual(result.result_data.message_id, 12345)
        self.assertEqual(result.result_data.message_count, 5)

    def test_poll_ack_uses_parsed_xml_directly(self) -> None:
        """Verify poll.acknowledge re-uses result.parsed_xml directly."""
        epp_communicator = MagicMock(EppCommunicator)
        poll = Poll(epp_communicator)
        mock_parsed = MagicMock()
        mock_msgq = MagicMock()
        mock_msgq.get.side_effect = lambda attr: "4" if attr == "count" else "12345"
        mock_parsed.find.side_effect = lambda tag, *args, **kwargs: {
            "msgQ": mock_msgq,
        }.get(tag, None)

        execute_result = EppResultData(
            code=1000,
            message="Command completed successfully",
            reason=None,
            raw_response="<dummy/>",
            result_data=None,
            dry_run=False,
            parsed_xml=mock_parsed,
        )
        poll.execute = MagicMock(return_value=execute_result)
        result = poll.acknowledge(12345)
        self.assertEqual(result.result_data.message_id, 12345)
        self.assertEqual(result.result_data.message_count, 4)

    def test_poll_request(self) -> None:
        epp_communicator = MagicMock(EppCommunicator)
        poll = Poll(epp_communicator)
        expected_result = EppResultData(
            **{
                "client_transaction_id": "c6710aac-cbcf-48d0-9ec3-cfaad1cadc81",
                "code": 1301,
                "message": "Command completed successfully; ack to dequeue",
                "raw_response": "<response>\n"
                '<result code="1301">\n'
                "<msg>Command completed successfully; ack to dequeue</msg>\n"
                "</result>\n"
                '<msgQ count="1" id="27690316">\n'
                "<qDate>2023-07-26T00:21:31.246Z</qDate>\n"
                '<msg lang="en">Contact inz-contact-1 has been '
                "deleted.</msg>\n"
                "</msgQ>\n"
                "<trID>\n"
                "<clTRID>c6710aac-cbcf-48d0-9ec3-cfaad1cadc81</clTRID>\n"
                "<svTRID>CIRA-000097025501-0000000002</svTRID>\n"
                "</trID>\n"
                "</response>",
                "reason": None,
                "repository_object_id": None,
                "result_data": ServiceMessageQueueData(
                    message_count="1",
                    message_id="27690316",
                    queue_date="2023-07-26T00:21:31.246Z",
                    messages=[
                        ServiceMessageData(
                            language="en",
                            message="Contact "
                            "inz-contact-1 "
                            "has "
                            "been "
                            "deleted.",
                        )
                    ],
                ),
                "server_transaction_id": "CIRA-000097025501-0000000002",
            }
        )

        poll.execute = MagicMock(return_value=expected_result)

        result = poll.request()

        self.assertEqual(result, expected_result)

    def test_poll_ack_unsuccessful(self) -> None:
        epp_communicator = MagicMock(EppCommunicator)
        poll = Poll(epp_communicator)
        expected_result = EppResultData(
            **{
                "code": 1500,
                "message": "Command completed successfully",
                "reason": None,
                "raw_response": "response",
                "result_data": None,
            }
        )
        poll.execute = MagicMock(return_value=expected_result)

        result = poll.acknowledge(121212)

        self.assertEqual(result, expected_result)

    def test_poll_ack_dry_run(self) -> None:
        epp_communicator = MagicMock(EppCommunicator)
        poll = Poll(epp_communicator)
        expected_result = EppResultData(
            code=1000,
            message="Dry run",
            reason=None,
            raw_response="<poll:ack/>",
            result_data=None,
            dry_run=True,
        )
        poll.execute = MagicMock(return_value=expected_result)
        result = poll.acknowledge(121212)
        self.assertEqual(result, expected_result)

    def test_poll_ack(self) -> None:
        epp_communicator = MagicMock(EppCommunicator)
        poll = Poll(epp_communicator)

        expected_result = EppResultData(
            **{
                "client_transaction_id": "c6710aac-cbcf-48d0-9ec3-cfaad1cadc81",
                "code": 1000,
                "message": "Command completed successfully",
                "raw_response": "<response>\n"
                '<result code="1000">\n'
                "<msg>Command completed successfully</msg>\n"
                "</result>\n"
                '<msgQ count="1" id="27690316">\n'
                "</msgQ>\n"
                "<trID>\n"
                "<clTRID>c6710aac-cbcf-48d0-9ec3-cfaad1cadc81</clTRID>\n"
                "<svTRID>CIRA-000097025501-0000000002</svTRID>\n"
                "</trID>\n"
                "</response>",
                "reason": None,
                "repository_object_id": None,
                "result_data": None,
                "server_transaction_id": "CIRA-000097025501-0000000002",
            }
        )

        poll.execute = MagicMock(return_value=expected_result)

        result = poll.acknowledge(27690316)

        self.assertEqual(result.code, 1000)
        self.assertEqual(result.result_data.message_count, 1)
        self.assertEqual(result.result_data.message_id, 27690316)

    def test_data_to_dict(self) -> None:
        epp_communicator = MagicMock(EppCommunicator)
        poll = Poll(epp_communicator)
        data = ServiceMessageQueueData(
            message_count=1,
            message_id=123,
            queue_date="2023-01-01T00:00:00.000Z",
            messages=[ServiceMessageData(language="en", message="Test msg")],
        )
        result = poll._data_to_dict(data)
        self.assertDictEqual(
            result,
            {
                "message_count": 1,
                "message_id": 123,
                "queue_date": "2023-01-01T00:00:00.000Z",
                "messages": [{"language": "en", "message": "Test msg"}],
            },
        )
