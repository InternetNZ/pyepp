"""
EPP Poll Module
"""

from dataclasses import asdict, dataclass
from typing import Any, List, Optional, Union

from pyepp import EppResultCode, EppResultData
from pyepp.base_command import BaseCommand
from pyepp.command_templates import POLL_REQUEST_XML, POLL_ACK_XML


@dataclass
class ServiceMessageData:
    """Service message data class."""

    language: str
    message: str


@dataclass
class ServiceMessageQueueData:
    """Service message queue data class."""

    message_count: int
    message_id: Optional[Union[str, int]] = None
    queue_date: Optional[str] = None
    messages: Optional[List[ServiceMessageData]] = None
    response_data: Optional[dict[str, Any]] = None


class Poll(BaseCommand):
    """
    Epp Poll class is used to manage registry service messages. It contains poll request and poll acknowledge commands.
    """

    @staticmethod
    def _clean_attrs(el: Any) -> dict[str, Any]:
        """Extract non-namespace attributes from a BeautifulSoup XML element."""
        attrs = getattr(el, "attrs", {}) or {}
        return {
            key: value
            for key, value in attrs.items()
            if key != "xmlns" and not key.startswith("xmlns:")
        }

    @classmethod
    def _parse_pan_data(cls, pan_el: Any) -> dict[str, Any]:
        """Parse RFC 5731/5732/5733 §3.3 <panData> pending action notification payloads.

        The object identifier element (e.g. <domain:name paResult="1">) carries the
        boolean outcome in its 'paResult' attribute rather than a separate child tag.
        Extracting 'paResult' as a boolean alongside the identifier text preserves
        both values cleanly.
        """
        pan_dict: dict[str, Any] = {}
        children = [
            c for c in pan_el.find_all(recursive=False) if getattr(c, "name", None)
        ]
        for child in children:
            local_name = child.name.split(":")[-1]
            pa_result = child.get("paResult")
            if pa_result is not None:
                raw_text = child.get_text()
                pan_dict[local_name] = raw_text.strip() if raw_text else ""
                pan_dict["paResult"] = str(pa_result).strip().lower() in ("1", "true")
            else:
                pan_dict[local_name] = cls._element_to_data(child)

        for key, value in cls._clean_attrs(pan_el).items():
            pan_dict[f"@{key}" if key in pan_dict else key] = value

        return pan_dict

    @classmethod
    def _element_to_data(cls, el: Any) -> Any:
        """Recursively convert an XML element subtree into structured Python dicts/lists/scalars.

        Strips XML namespace prefixes to keep keys uniform across registries, preserves
        non-xmlns attributes on leaf and container elements, and promotes repeated
        sibling elements (such as multiple <msg> or <item> tags) to lists.
        """
        attrs = cls._clean_attrs(el)
        children = [
            c for c in el.find_all(recursive=False) if getattr(c, "name", None)
        ]
        if not children:
            raw_text = el.get_text()
            text = raw_text.strip() if raw_text and raw_text.strip() else None
            if not attrs:
                return text
            leaf = dict(attrs)
            if text is not None:
                leaf["#text" if "value" in leaf else "value"] = text
            return leaf

        node: dict[str, Any] = {}
        for child in children:
            child_name = child.name.split(":")[-1]
            child_val = (
                cls._parse_pan_data(child)
                if child_name == "panData"
                else cls._element_to_data(child)
            )
            if child_name in node:
                if isinstance(node[child_name], list):
                    node[child_name].append(child_val)
                else:
                    node[child_name] = [node[child_name], child_val]
            else:
                node[child_name] = child_val

        for key, value in attrs.items():
            node[f"@{key}" if key in node else key] = value

        return node

    @classmethod
    def _parse_res_data(cls, res_data_el: Any) -> Optional[dict[str, Any]]:
        """Parse optional <resData> notification payload from a poll response per RFC 5730 §2.9.2.3.

        Handles transfer notifications (<domain:trnData>, <contact:trnData>), pending
        action notifications (<panData>), and arbitrary registry-specific poll payloads,
        returning None when <resData> is absent or contains no child elements.
        """
        if res_data_el is None:
            return None
        containers = [
            c for c in res_data_el.find_all(recursive=False) if getattr(c, "name", None)
        ]
        if not containers:
            return None
        parsed = cls._element_to_data(res_data_el)
        return parsed if isinstance(parsed, dict) and parsed else None

    def _data_to_dict(self, data: ServiceMessageQueueData) -> dict:
        """Convert dataclass to dictionary.

        :param ServiceMessageData data: Service message data

        :return: Domain name details
        :rtype: dict
        """
        data_dict = asdict(data)

        return data_dict

    def request(self, client_transaction_id: Optional[str] = None) -> EppResultData:
        """This command is to check and retrieve queued service messages as wel as keep the
        connection alive.

        :param client_transaction_id: Client transaction id

        :return: Result object
        :rtype: EppResultData
        """
        result = self.execute(
            POLL_REQUEST_XML, client_transaction_id=client_transaction_id
        )

        # In dry-run mode or if no message to dequeue, skip XML payload parsing
        if (
            int(result.code) != int(EppResultCode.SUCCESS_ACK_TO_DEQUEUE.value)
            or result.dry_run
        ):
            return result

        message_queue = result.parsed_xml
        # RFC 5730 §2.6 & §2.9.2.3: Scope poll queue data parsing strictly to <msgQ> under <response>.
        response = message_queue.find("response") if message_queue else None
        msg_q = (
            response.find("msgQ", recursive=False)
            if response
            else (message_queue.find("msgQ") if message_queue else None)
        )

        message_count = 0
        message_id = None
        queue_date = None
        messages = None

        if msg_q is not None:
            count_val = msg_q.get("count")
            try:
                message_count = int(count_val) if count_val else 0
            except (ValueError, TypeError):
                message_count = 0
            # RFC 5730 §2.9.2.3: msgID is an XML token (str), not an integer.
            # Registries often return alphanumeric IDs or UUIDs (e.g. 'REQ-98123').
            # Do not cast to int to prevent ValueError crashes.
            message_id = msg_q.get("id")

            # RFC 5730 §2.9.2.3: <qDate> is OPTIONAL inside <msgQ>.
            # Direct child lookup (recursive=False) avoids matching any mixed-content elements.
            q_date_el = msg_q.find("qDate", recursive=False)
            queue_date = q_date_el.text if q_date_el else None

            # RFC 5730 §2.9.2.3: Human-readable service messages are child <msg>
            # elements of <msgQ>. Scoping to msg_q.find_all("msg", recursive=False) avoids matching
            # <result><msg> or nested elements, removing fragile document-wide index slicing ([1:]).
            msg_elements = msg_q.find_all("msg", recursive=False)
            if msg_elements:
                messages = [
                    ServiceMessageData(
                        # RFC 5730 §4.2 (epp-1.0.xsd mixedMsgType): Default lang attribute is 'en'
                        # when omitted by the registry.
                        language=message.get("lang") or "en",
                        message=message.text,
                    )
                    for message in msg_elements
                ]

        # RFC 5730 §2.9.2.3: Poll responses (code 1301) may carry an object-specific
        # <resData> payload (e.g. <domain:trnData>, <panData>, or custom registry notices)
        # alongside <msgQ>. Scope strictly to <response><resData> when available.
        res_data_el = (
            response.find("resData", recursive=False)
            if response
            else (message_queue.find("resData") if message_queue else None)
        )

        result_data = {
            "message_count": message_count,
            "message_id": message_id,
            "queue_date": queue_date,
            "messages": messages,
            "response_data": self._parse_res_data(res_data_el),
        }

        result.result_data = ServiceMessageQueueData(**result_data)

        return result

    def acknowledge(
        self,
        message_id: Union[str, int],
        client_transaction_id: Optional[str] = None,
    ) -> EppResultData:
        """This command will acknowledge and remove a message from the poll queue so that registrars can run another
        poll request to get the next message in line if one exists.

        :param message_id: Message id (XML token / str or int)
        :param client_transaction_id: Client transaction id

        :return: Response object
        :rtype: EppResultData
        """
        result = self.execute(
            POLL_ACK_XML,
            message_id=message_id,
            client_transaction_id=client_transaction_id,
        )

        # In dry-run mode or on error, skip XML payload parsing since there is no response payload
        if int(result.code) != int(EppResultCode.SUCCESS.value) or result.dry_run:
            return result

        message_queue = result.parsed_xml
        # RFC 5730 §2.6 & §2.9.2.3: When acknowledging the final message in the queue (count="0"),
        # the server responds with <msgQ count="0"/> where 'id' is omitted, or may omit
        # <msgQ> entirely. Safely handle absent <msgQ> and absent 'id' attribute to prevent
        # AttributeError and TypeError crashes.
        response = message_queue.find("response") if message_queue else None
        msg_q = (
            response.find("msgQ", recursive=False)
            if response
            else (message_queue.find("msgQ") if message_queue else None)
        )

        message_count = 0
        message_id_result = None
        if msg_q is not None:
            count_val = msg_q.get("count")
            try:
                message_count = int(count_val) if count_val else 0
            except (ValueError, TypeError):
                message_count = 0
            # RFC 5730 §2.9.2.3: msgID is an XML token (str), not an int.
            message_id_result = msg_q.get("id")

        result_data = {
            "message_count": message_count,
            "message_id": message_id_result,
        }

        result.result_data = ServiceMessageQueueData(**result_data)

        return result
