"""
EPP Poll Module
"""
from pyepp.base_command import BaseCommand
from pyepp.command_templates import POLL_REQUEST_XML


class Poll(BaseCommand):
    """
    Epp Poll
    """

    def request(self):
        """

        :return:
        """
        result = self.execute(POLL_REQUEST_XML)
        return result

    def acknowledge(self):
        pass
