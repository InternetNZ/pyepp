"""
Base command
"""
import uuid

from dataclasses import dataclass
from html import escape
from jinja2 import Environment, BaseLoader

import pyepp.helper as helper  # pylint: disable=consider-using-from-import
from pyepp.epp import EppCommunicator


class ErrorCodeInResultException(Exception):
    """
    Error code in result exception
    """


# pylint: disable=too-few-public-methods
class BaseCommand:
    """
    Base command class
    """
    PARAMS = ()

    def __init__(self, epp_communicator: EppCommunicator) -> None:
        """

        :param EppCommunicator epp_communicator: EPP Communicator object
        """
        self._epp_communicator = epp_communicator
        self._template_engine = Environment(loader=BaseLoader(),
                                            trim_blocks=True,
                                            lstrip_blocks=True,
                                            autoescape=True)

    def execute(self, xml_command: str, **kwargs) -> dict:
        """
        Execute epp command.

        :param str xml_command: XML command
        :param kwargs: Keyword arguments

        :return: Response Object
        :rtype: dict
        """
        cmd = self._prepare_command(xml_command, **kwargs)

        # if kwargs.get('dry_run') == 1:
        #     print(colorize('\n' + cmd + '\n', ANSICOLORS.GREY))
        #     return
        #
        # verbose = False
        # if kwargs.get('verbose') == 1:
        #     verbose = True

        result = self._epp_communicator.execute(cmd)
        return result

    def _prepare_command(self, cmd: str, **kwargs: str) -> str:
        """
        Prepare the command to be executed.

        :param str cmd: Command in XML format
        :param dict kwargs: Keyword arguments

        :return: XML command
        :rtype: str
        """
        if cmd.find('client_transaction_id') != -1 and not kwargs.get('client_transaction_id'):
            kwargs['client_transaction_id'] = str(uuid.uuid4())

        if cmd.find('password') != -1 and not kwargs.get('password'):
            kwargs['password'] = helper.generate_password(16)

        kwargs = {key: value for key, value in kwargs.items() if value}

        new_kwargs = self.__escape_dict(kwargs)

        template = self._template_engine.from_string(cmd)
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
        """Convert dataclass to dict.

        :param dataclass data: data

        :return: data
        :rtype: dict
        """
