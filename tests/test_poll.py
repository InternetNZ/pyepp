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

        # RFC 5730: msg elements and qDate are queried scoped to msgQ
        mock_msgq.find.side_effect = lambda tag, *args, **kwargs: {
            "qDate": mock_qdate,
        }.get(tag, None)
        mock_msgq.find_all.side_effect = lambda tag, *args, **kwargs: {
            "msg": [mock_msg],
        }.get(tag, [])

        mock_parsed.find.side_effect = lambda tag, *args, **kwargs: {
            "msgQ": mock_msgq,
        }.get(tag, None)

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
        self.assertEqual(result.result_data.message_id, "12345")
        self.assertEqual(result.result_data.message_count, 5)
        self.assertEqual(result.result_data.queue_date, "2023-01-01T00:00:00Z")
        self.assertEqual(
            result.result_data.messages,
            [ServiceMessageData(language="en", message="Domain renewed")],
        )

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
        self.assertEqual(result.result_data.message_id, "12345")
        self.assertEqual(result.result_data.message_count, 4)

    def test_poll_request(self) -> None:
        epp_communicator = MagicMock(EppCommunicator)
        poll = Poll(epp_communicator)
        raw_xml = (
            "<response>\n"
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
            "</response>"
        )
        execute_result = EppResultData(
            client_transaction_id="c6710aac-cbcf-48d0-9ec3-cfaad1cadc81",
            code=1301,
            message="Command completed successfully; ack to dequeue",
            raw_response=raw_xml,
            reason=None,
            repository_object_id=None,
            result_data=None,
            server_transaction_id="CIRA-000097025501-0000000002",
        )
        expected_service_message_data = ServiceMessageQueueData(
            message_count=1,
            message_id="27690316",
            queue_date="2023-07-26T00:21:31.246Z",
            messages=[
                ServiceMessageData(
                    language="en",
                    message="Contact inz-contact-1 has been deleted.",
                )
            ],
        )

        poll.execute = MagicMock(return_value=execute_result)

        result = poll.request()

        self.assertEqual(result.code, 1301)
        self.assertEqual(result.result_data, expected_service_message_data)
        self.assertEqual(
            result.client_transaction_id, "c6710aac-cbcf-48d0-9ec3-cfaad1cadc81"
        )
        self.assertEqual(
            result.server_transaction_id, "CIRA-000097025501-0000000002"
        )

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
        self.assertEqual(result.result_data.message_id, "27690316")

    def test_poll_request_missing_msgq_element(self) -> None:
        """Verify Poll.request handles 1301 responses with no <msgQ> element gracefully."""
        epp_communicator = MagicMock(EppCommunicator)
        poll = Poll(epp_communicator)
        raw_xml = (
            "<response>\n"
            '  <result code="1301">\n'
            "    <msg>Command completed successfully; ack to dequeue</msg>\n"
            "  </result>\n"
            "  <trID>\n"
            "    <clTRID>ABC-123</clTRID>\n"
            "    <svTRID>SRV-456</svTRID>\n"
            "  </trID>\n"
            "</response>"
        )
        execute_result = EppResultData(
            code=1301,
            message="Command completed successfully; ack to dequeue",
            raw_response=raw_xml,
            result_data=None,
        )
        poll.execute = MagicMock(return_value=execute_result)
        result = poll.request()
        self.assertEqual(result.code, 1301)
        self.assertEqual(result.result_data.message_count, 0)
        self.assertIsNone(result.result_data.message_id)
        self.assertIsNone(result.result_data.queue_date)
        self.assertIsNone(result.result_data.messages)

    def test_poll_request_no_messages_code_1300(self) -> None:
        """Verify Poll.request returns result without parsing when code is 1300 (no messages)."""
        epp_communicator = MagicMock(EppCommunicator)
        poll = Poll(epp_communicator)
        raw_xml = (
            "<response>\n"
            '  <result code="1300">\n'
            "    <msg>Command completed successfully; no messages</msg>\n"
            "  </result>\n"
            "  <trID>\n"
            "    <clTRID>ABC-123</clTRID>\n"
            "    <svTRID>SRV-456</svTRID>\n"
            "  </trID>\n"
            "</response>"
        )
        execute_result = EppResultData(
            code=1300,
            message="Command completed successfully; no messages",
            raw_response=raw_xml,
            result_data=None,
        )
        poll.execute = MagicMock(return_value=execute_result)
        result = poll.request()
        self.assertEqual(result.code, 1300)
        self.assertIsNone(result.result_data)

    def test_poll_request_alphanumeric_msg_id(self) -> None:
        """Verify Poll.request handles alphanumeric msgID tokens per RFC 5730."""
        epp_communicator = MagicMock(EppCommunicator)
        poll = Poll(epp_communicator)
        raw_xml = (
            "<response>\n"
            '  <result code="1301">\n'
            "    <msg>Command completed successfully; ack to dequeue</msg>\n"
            "  </result>\n"
            '  <msgQ count="3" id="REQ-98123-ABC">\n'
            "    <qDate>2023-08-01T12:00:00.000Z</qDate>\n"
            '    <msg lang="en">Domain example.com transfer requested.</msg>\n'
            "  </msgQ>\n"
            "  <trID>\n"
            "    <clTRID>ABC-123</clTRID>\n"
            "    <svTRID>SRV-456</svTRID>\n"
            "  </trID>\n"
            "</response>"
        )
        execute_result = EppResultData(
            code=1301,
            message="Command completed successfully; ack to dequeue",
            raw_response=raw_xml,
            result_data=None,
        )
        poll.execute = MagicMock(return_value=execute_result)
        result = poll.request()
        self.assertEqual(result.result_data.message_id, "REQ-98123-ABC")
        self.assertEqual(result.result_data.message_count, 3)
        self.assertEqual(result.result_data.queue_date, "2023-08-01T12:00:00.000Z")
        self.assertEqual(
            result.result_data.messages,
            [
                ServiceMessageData(
                    language="en",
                    message="Domain example.com transfer requested.",
                )
            ],
        )

    def test_poll_request_missing_qdate(self) -> None:
        """Verify Poll.request handles optional <qDate> element when omitted."""
        epp_communicator = MagicMock(EppCommunicator)
        poll = Poll(epp_communicator)
        raw_xml = (
            "<response>\n"
            '  <result code="1301">\n'
            "    <msg>Command completed successfully; ack to dequeue</msg>\n"
            "  </result>\n"
            '  <msgQ count="1" id="MSG-100">\n'
            '    <msg lang="en">Notification message.</msg>\n'
            "  </msgQ>\n"
            "  <trID>\n"
            "    <clTRID>ABC-123</clTRID>\n"
            "    <svTRID>SRV-456</svTRID>\n"
            "  </trID>\n"
            "</response>"
        )
        execute_result = EppResultData(
            code=1301,
            message="Command completed successfully; ack to dequeue",
            raw_response=raw_xml,
            result_data=None,
        )
        poll.execute = MagicMock(return_value=execute_result)
        result = poll.request()
        self.assertEqual(result.result_data.message_id, "MSG-100")
        self.assertIsNone(result.result_data.queue_date)

    def test_poll_request_does_not_leak_result_msg(self) -> None:
        """Verify Poll.request does not treat <result><msg> as a queue message."""
        epp_communicator = MagicMock(EppCommunicator)
        poll = Poll(epp_communicator)
        raw_xml = (
            "<response>\n"
            '  <result code="1301">\n'
            "    <msg>Command completed successfully; ack to dequeue</msg>\n"
            "  </result>\n"
            '  <msgQ count="1" id="MSG-101">\n'
            "    <qDate>2023-08-01T12:00:00.000Z</qDate>\n"
            "  </msgQ>\n"
            "  <trID>\n"
            "    <clTRID>ABC-123</clTRID>\n"
            "    <svTRID>SRV-456</svTRID>\n"
            "  </trID>\n"
            "</response>"
        )
        execute_result = EppResultData(
            code=1301,
            message="Command completed successfully; ack to dequeue",
            raw_response=raw_xml,
            result_data=None,
        )
        poll.execute = MagicMock(return_value=execute_result)
        result = poll.request()
        self.assertEqual(result.result_data.message_id, "MSG-101")
        self.assertIsNone(result.result_data.messages)

    def test_poll_request_multiple_msgs_in_queue(self) -> None:
        """Verify Poll.request parses all <msg> tags scoped to <msgQ> without skipping the first."""
        epp_communicator = MagicMock(EppCommunicator)
        poll = Poll(epp_communicator)
        raw_xml = (
            "<response>\n"
            '  <result code="1301">\n'
            "    <msg>Command completed successfully; ack to dequeue</msg>\n"
            "  </result>\n"
            '  <msgQ count="1" id="MSG-102">\n'
            "    <qDate>2023-08-01T12:00:00.000Z</qDate>\n"
            '    <msg lang="en">Domain suspended.</msg>\n'
            '    <msg lang="fr">Domaine suspendu.</msg>\n'
            "  </msgQ>\n"
            "  <trID>\n"
            "    <clTRID>ABC-123</clTRID>\n"
            "    <svTRID>SRV-456</svTRID>\n"
            "  </trID>\n"
            "</response>"
        )
        execute_result = EppResultData(
            code=1301,
            message="Command completed successfully; ack to dequeue",
            raw_response=raw_xml,
            result_data=None,
        )
        poll.execute = MagicMock(return_value=execute_result)
        result = poll.request()
        self.assertIsNotNone(result.result_data.messages)
        self.assertEqual(len(result.result_data.messages), 2)
        self.assertEqual(result.result_data.messages[0].language, "en")
        self.assertEqual(result.result_data.messages[0].message, "Domain suspended.")
        self.assertEqual(result.result_data.messages[1].language, "fr")
        self.assertEqual(result.result_data.messages[1].message, "Domaine suspendu.")

    def test_poll_ack_alphanumeric_msg_id(self) -> None:
        """Verify Poll.acknowledge handles alphanumeric string message IDs."""
        epp_communicator = MagicMock(EppCommunicator)
        poll = Poll(epp_communicator)
        raw_xml = (
            "<response>\n"
            '  <result code="1000">\n'
            "    <msg>Command completed successfully</msg>\n"
            "  </result>\n"
            '  <msgQ count="2" id="REQ-98123-UUID"/>\n'
            "  <trID>\n"
            "    <clTRID>ABC-123</clTRID>\n"
            "    <svTRID>SRV-456</svTRID>\n"
            "  </trID>\n"
            "</response>"
        )
        execute_result = EppResultData(
            code=1000,
            message="Command completed successfully",
            raw_response=raw_xml,
            result_data=None,
        )
        poll.execute = MagicMock(return_value=execute_result)
        result = poll.acknowledge("REQ-98123-UUID")
        self.assertEqual(result.code, 1000)
        self.assertEqual(result.result_data.message_id, "REQ-98123-UUID")
        self.assertEqual(result.result_data.message_count, 2)

    def test_poll_ack_empty_queue_no_id_attribute(self) -> None:
        """Verify Poll.acknowledge handles <msgQ count="0"/> where id attribute is absent."""
        epp_communicator = MagicMock(EppCommunicator)
        poll = Poll(epp_communicator)
        raw_xml = (
            "<response>\n"
            '  <result code="1000">\n'
            "    <msg>Command completed successfully</msg>\n"
            "  </result>\n"
            '  <msgQ count="0"/>\n'
            "  <trID>\n"
            "    <clTRID>ABC-123</clTRID>\n"
            "    <svTRID>SRV-456</svTRID>\n"
            "  </trID>\n"
            "</response>"
        )
        execute_result = EppResultData(
            code=1000,
            message="Command completed successfully",
            raw_response=raw_xml,
            result_data=None,
        )
        poll.execute = MagicMock(return_value=execute_result)
        result = poll.acknowledge("LAST-MSG")
        self.assertEqual(result.code, 1000)
        self.assertEqual(result.result_data.message_count, 0)
        self.assertIsNone(result.result_data.message_id)

    def test_poll_ack_missing_msgq_element(self) -> None:
        """Verify Poll.acknowledge handles responses with no <msgQ> element without crashing."""
        epp_communicator = MagicMock(EppCommunicator)
        poll = Poll(epp_communicator)
        raw_xml = (
            "<response>\n"
            '  <result code="1000">\n'
            "    <msg>Command completed successfully</msg>\n"
            "  </result>\n"
            "  <trID>\n"
            "    <clTRID>ABC-123</clTRID>\n"
            "    <svTRID>SRV-456</svTRID>\n"
            "  </trID>\n"
            "</response>"
        )
        execute_result = EppResultData(
            code=1000,
            message="Command completed successfully",
            raw_response=raw_xml,
            result_data=None,
        )
        poll.execute = MagicMock(return_value=execute_result)
        result = poll.acknowledge(12345)
        self.assertEqual(result.code, 1000)
        self.assertEqual(result.result_data.message_count, 0)
        self.assertIsNone(result.result_data.message_id)

    def test_poll_request_missing_lang_attribute(self) -> None:
        """Verify Poll.request defaults message language to 'en' when lang attribute is omitted per RFC 5730."""
        epp_communicator = MagicMock(EppCommunicator)
        poll = Poll(epp_communicator)
        raw_xml = (
            "<response>\n"
            '  <result code="1301">\n'
            "    <msg>Command completed successfully; ack to dequeue</msg>\n"
            "  </result>\n"
            '  <msgQ count="1" id="MSG-200">\n'
            "    <msg>Domain example.org renewed.</msg>\n"
            "  </msgQ>\n"
            "  <trID>\n"
            "    <clTRID>ABC-123</clTRID>\n"
            "    <svTRID>SRV-456</svTRID>\n"
            "  </trID>\n"
            "</response>"
        )
        execute_result = EppResultData(
            code=1301,
            message="Command completed successfully; ack to dequeue",
            raw_response=raw_xml,
            result_data=None,
        )
        poll.execute = MagicMock(return_value=execute_result)
        result = poll.request()
        self.assertEqual(result.code, 1301)
        self.assertIsNotNone(result.result_data.messages)
        self.assertEqual(len(result.result_data.messages), 1)
        self.assertEqual(result.result_data.messages[0].language, "en")
        self.assertEqual(
            result.result_data.messages[0].message, "Domain example.org renewed."
        )

    def test_poll_request_empty_count_attribute(self) -> None:
        """Verify Poll.request handles empty count attribute gracefully without raising ValueError."""
        epp_communicator = MagicMock(EppCommunicator)
        poll = Poll(epp_communicator)
        raw_xml = (
            "<response>\n"
            '  <result code="1301">\n'
            "    <msg>Command completed successfully; ack to dequeue</msg>\n"
            "  </result>\n"
            '  <msgQ count="" id="MSG-201">\n'
            "    <msg>Notification.</msg>\n"
            "  </msgQ>\n"
            "  <trID>\n"
            "    <clTRID>ABC-123</clTRID>\n"
            "    <svTRID>SRV-456</svTRID>\n"
            "  </trID>\n"
            "</response>"
        )
        execute_result = EppResultData(
            code=1301,
            message="Command completed successfully; ack to dequeue",
            raw_response=raw_xml,
            result_data=None,
        )
        poll.execute = MagicMock(return_value=execute_result)
        result = poll.request()
        self.assertEqual(result.result_data.message_count, 0)
        self.assertEqual(result.result_data.message_id, "MSG-201")

    def test_poll_request_invalid_count_attribute(self) -> None:
        """Verify Poll.request handles non-numeric count attribute gracefully."""
        epp_communicator = MagicMock(EppCommunicator)
        poll = Poll(epp_communicator)
        raw_xml = (
            "<response>\n"
            '  <result code="1301">\n'
            "    <msg>Command completed successfully; ack to dequeue</msg>\n"
            "  </result>\n"
            '  <msgQ count="invalid" id="MSG-201">\n'
            "    <msg>Notification.</msg>\n"
            "  </msgQ>\n"
            "  <trID>\n"
            "    <clTRID>ABC-123</clTRID>\n"
            "    <svTRID>SRV-456</svTRID>\n"
            "  </trID>\n"
            "</response>"
        )
        execute_result = EppResultData(
            code=1301,
            message="Command completed successfully; ack to dequeue",
            raw_response=raw_xml,
            result_data=None,
        )
        poll.execute = MagicMock(return_value=execute_result)
        result = poll.request()
        self.assertEqual(result.result_data.message_count, 0)
        self.assertEqual(result.result_data.message_id, "MSG-201")

    def test_poll_request_mixed_content_nested_tags(self) -> None:
        """Verify Poll.request does not match nested tags inside mixed-content <msg> elements."""
        epp_communicator = MagicMock(EppCommunicator)
        poll = Poll(epp_communicator)
        raw_xml = (
            "<response>\n"
            '  <result code="1301">\n'
            "    <msg>Command completed successfully; ack to dequeue</msg>\n"
            "  </result>\n"
            '  <msgQ count="1" id="MSG-202">\n'
            "    <qDate>2023-08-01T12:00:00.000Z</qDate>\n"
            '    <msg lang="en">Domain renewed: <qDate>nested</qDate><msg>nested-msg</msg></msg>\n'
            "  </msgQ>\n"
            "  <trID>\n"
            "    <clTRID>ABC-123</clTRID>\n"
            "    <svTRID>SRV-456</svTRID>\n"
            "  </trID>\n"
            "</response>"
        )
        execute_result = EppResultData(
            code=1301,
            message="Command completed successfully; ack to dequeue",
            raw_response=raw_xml,
            result_data=None,
        )
        poll.execute = MagicMock(return_value=execute_result)
        result = poll.request()
        self.assertEqual(
            result.result_data.queue_date, "2023-08-01T12:00:00.000Z"
        )
        self.assertEqual(len(result.result_data.messages), 1)

    def test_poll_ack_empty_count_attribute(self) -> None:
        """Verify Poll.acknowledge handles empty count attribute gracefully."""
        epp_communicator = MagicMock(EppCommunicator)
        poll = Poll(epp_communicator)
        raw_xml = (
            "<response>\n"
            '  <result code="1000">\n'
            "    <msg>Command completed successfully</msg>\n"
            "  </result>\n"
            '  <msgQ count=""/>\n'
            "  <trID>\n"
            "    <clTRID>ABC-123</clTRID>\n"
            "    <svTRID>SRV-456</svTRID>\n"
            "  </trID>\n"
            "</response>"
        )
        execute_result = EppResultData(
            code=1000,
            message="Command completed successfully",
            raw_response=raw_xml,
            result_data=None,
        )
        poll.execute = MagicMock(return_value=execute_result)
        result = poll.acknowledge("MSG-1")
        self.assertEqual(result.code, 1000)
        self.assertEqual(result.result_data.message_count, 0)
        self.assertIsNone(result.result_data.message_id)

    def test_poll_ack_invalid_count_attribute(self) -> None:
        """Verify Poll.acknowledge handles non-numeric count attribute gracefully."""
        epp_communicator = MagicMock(EppCommunicator)
        poll = Poll(epp_communicator)
        raw_xml = (
            "<response>\n"
            '  <result code="1000">\n'
            "    <msg>Command completed successfully</msg>\n"
            "  </result>\n"
            '  <msgQ count="invalid"/>\n'
            "  <trID>\n"
            "    <clTRID>ABC-123</clTRID>\n"
            "    <svTRID>SRV-456</svTRID>\n"
            "  </trID>\n"
            "</response>"
        )
        execute_result = EppResultData(
            code=1000,
            message="Command completed successfully",
            raw_response=raw_xml,
            result_data=None,
        )
        poll.execute = MagicMock(return_value=execute_result)
        result = poll.acknowledge("MSG-1")
        self.assertEqual(result.code, 1000)
        self.assertEqual(result.result_data.message_count, 0)
        self.assertIsNone(result.result_data.message_id)

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
