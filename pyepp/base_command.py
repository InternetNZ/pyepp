"""
Base command
"""
import uuid

from dataclasses import dataclass
from html import escape

import pyepp.helper as helper  # pylint: disable=consider-using-from-import
from pyepp.epp import EppCommunicator, EppResultData
from pyepp.command_templates import template_engine


class ErrorCodeInResultException(Exception):
    """
    Error code in result exception
    """


# pylint: disable=too-few-public-methods
class BaseCommand:
    """
    Base command class. Other EPP commands will inherit this class.
    """
    PARAMS = ()

    def __init__(self, epp_communicator: EppCommunicator) -> None:
        """
        :param epp_communicator: EPP Communicator object
        """
        self._epp_communicator = epp_communicator

    def execute(self, xml_command: str, **kwargs) -> EppResultData:
        """This receives an EPP XML command and the arguments and send to the EPP server to be executed.

        :param xml_command: XML command
        :param kwargs: Keyword arguments

        :return: Response Object
        """
        cmd = self._prepare_command(xml_command, **kwargs)

        result = self._epp_communicator.execute(cmd)
        return result

    def _prepare_command(self, cmd: str, **kwargs: str) -> str:
        """Prepare an EPP XML command for execution by setting up the arguments.

        :param cmd: Command in XML format
        :param kwargs: Keyword arguments

        :return: XML command
        """
        if cmd.find('client_transaction_id') != -1 and not kwargs.get('client_transaction_id'):
            kwargs['client_transaction_id'] = str(uuid.uuid4())

        if cmd.find('password') != -1 and not kwargs.get('password'):
            kwargs['password'] = helper.generate_password(16)

        kwargs = {key: value for key, value in kwargs.items() if value}

        new_kwargs = self.__escape_dict(kwargs)

        template = template_engine.from_string(cmd)
        xml = template.render(**new_kwargs)

        return xml

    def __escape_list(self, input_list: list) -> list:
        result = []

        for value in input_list:
            if isinstance(value, list):
                result.append(self.__escape_list(value))
            elif isinstance(value, dict):
                result.append(self.__escape_dict(value))
            elif isinstance(value, str):
                result.append(escape(value))
            elif value:
                result.append(value)

        return result

    def __escape_dict(self, input_dict: dict) -> dict:
        result = {}

        for key, value in input_dict.items():
            if isinstance(value, list):
                result[key] = self.__escape_list(value)
            elif isinstance(value, dict):
                result[key] = self.__escape_dict(value)
            elif isinstance(value, str):
                result[key] = escape(value)
            elif value:
                result[key] = value

        return result

    def _data_to_dict(self, data: dataclass) -> dict:
        """Convert a dataclass to a dict.

        :param data: data

        :return: data
        """
