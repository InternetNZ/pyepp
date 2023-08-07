"""
EPP Poll Module
"""
from dataclasses import asdict, dataclass
from typing import List, Optional

from bs4 import BeautifulSoup

from pyepp import EppResultCode
from pyepp.base_command import BaseCommand
from pyepp.command_templates import POLL_REQUEST_XML, POLL_ACK_XML


@dataclass
class ServiceMessageData:
    """Service message data class
    """
    language: str
    message: str


@dataclass
class ServiceMessageQueueData:
    """Service message queue data class
    """
    message_count: int
    message_id: int
    queue_date: Optional[str] = ''
    messages: Optional[List[ServiceMessageData]] = None


class Poll(BaseCommand):
    """
    Epp Poll
    """

    def _data_to_dict(self, data: ServiceMessageQueueData) -> dict:
        """Convert dataclass to dictionary.

        :param ServiceMessageData data: Service message data

        :return: Domain name details
        :rtype: dict
        """
        data_dict = asdict(data)

        return data_dict

    def request(self) -> dict:
        """This command is to check and retrieve queued service messages as wel as keep the
        connection alive.

        :return: Response object
        :rtype: dict
        """
        result = self.execute(POLL_REQUEST_XML)

        if int(result.get('code')) != int(EppResultCode.SUCCESS_ACK_TO_DEQUEUE.value):
            return result

        message_queue = BeautifulSoup(result.get('raw_response'), 'xml')

        result_date = {
            'message_count': int(message_queue.find('msgQ').get('count')),
            'message_id': int(message_queue.find('msgQ').get('id')),
            'queue_date': message_queue.find('qDate').text,
            'messages': [ServiceMessageData(language=message.get('lang'), message=message.text) for message in
                         message_queue.find_all('msg')[1:]] if message_queue.find('msg') else None
        }

        result['result_data'] = ServiceMessageQueueData(**result_date)

        return result

    def acknowledge(self, message_id: int) -> dict:
        """This command will acknowledge and remove a message from the poll queue so that registrars can run another
        poll request to get the next message in line if one exists.

        :return: Response object
        :rtype: dict
        """
        result = self.execute(POLL_ACK_XML, message_id=message_id)

        if int(result.get('code')) != int(EppResultCode.SUCCESS.value):
            return result

        message_queue = BeautifulSoup(result.get('raw_response'), 'xml')

        result_date = {
            'message_count': int(message_queue.find('msgQ').get('count')),
            'message_id': int(message_queue.find('msgQ').get('id')),
        }

        result['result_data'] = ServiceMessageQueueData(**result_date)

        return result