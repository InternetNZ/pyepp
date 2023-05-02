"""
Base Command unit tests
"""
import unittest
from unittest.mock import MagicMock, patch
from uuid import UUID

from pyepp.base_command import BaseCommand
from pyepp.epp import EppCommunicator


class BaseCommandTest(unittest.TestCase):

    @patch('pyepp.base_command.uuid.uuid4')
    def test_prepare_command_client_transaction_id(self, mock_uuid) -> None:
        command = """<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0"><command><clTRID>{{ client_transaction_id }}</clTRID></command></epp>"""
        expected_result = """<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0"><command><clTRID>6d053972-b813-4659-8029-924546e94489</clTRID></command></epp>"""
        mock_uuid.return_value = UUID('6d053972-b813-4659-8029-924546e94489')
        epp_communicator = MagicMock(EppCommunicator)

        base_command = BaseCommand(epp_communicator)
        resul = base_command._prepare_command(command)

        self.assertEqual(expected_result, resul)

    @patch('pyepp.base_command.helper.generate_password')
    def test_prepare_command_password(self, mock_generate_password) -> None:
        command = """<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0"><command><contact:authInfo><contact:pw>{{ password }}</contact:pw></contact:authInfo></command></epp>"""
        expected_result = """<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0"><command><contact:authInfo><contact:pw>wle2Dj6zIJCHTNrX</contact:pw></contact:authInfo></command></epp>"""
        mock_generate_password.return_value = 'wle2Dj6zIJCHTNrX'
        epp_communicator = MagicMock(EppCommunicator)

        base_command = BaseCommand(epp_communicator)
        resul = base_command._prepare_command(command)

        self.assertEqual(expected_result, resul)

    def test_escape_list(self) -> None:
        test_list = [
            ['hi&', '<world>'],
            {'key': '<hello&world>'},
            '<hello&world>'
        ]
        expected_result = [
            ['hi&amp;', '&lt;world&gt;'],
            {'key': '&lt;hello&amp;world&gt;'},
            '&lt;hello&amp;world&gt;'
        ]

        epp_communicator = MagicMock(EppCommunicator)
        base_command = BaseCommand(epp_communicator)

        result = base_command._BaseCommand__escape_list(test_list)

        self.assertEqual(expected_result, result)

    def test_escape_dict(self) -> None:
        test_list = {
            'key1': ['hi&', '<world>'],
            'key2': {'key': '<hello&world>'},
            'key3': '<hello&world>'
        }
        expected_result = {
            'key1': ['hi&amp;', '&lt;world&gt;'],
            'key2': {'key': '&lt;hello&amp;world&gt;'},
            'key3': '&lt;hello&amp;world&gt;'
        }

        epp_communicator = MagicMock(EppCommunicator)
        base_command = BaseCommand(epp_communicator)

        result = base_command._BaseCommand__escape_dict(test_list)

        self.assertEqual(expected_result, result)

    def test_execute(self) -> None:
        command = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <command>
    <create>
      <contact:create xmlns:contact="urn:ietf:params:xml:ns:contact-1.0">
        <contact:id>{{ id }}</contact:id>
          <contact:postalInfo type="loc">
            <contact:name>{{ name }}</contact:name>
            {% if organization %} <contact:org>{{ organization }}</contact:org> {% endif %}
            <contact:addr>
              <contact:street>{{ street_1 }}</contact:street>
              {% if street_2 %} <contact:street>{{ street_2 }}</contact:street> {% endif %}
              {% if street_3 %} <contact:street>{{ street_3 }}</contact:street> {% endif %}
              <contact:city>{{ city }}</contact:city>
              {% if province %} <contact:sp>{{ province }}</contact:sp> {% endif %}
              {% if postal_code %} <contact:pc>{{ postal_code }}</contact:pc> {% endif %}
              <contact:cc>{{ country_code }}</contact:cc>
           </contact:addr>
         </contact:postalInfo>
         {% if phone %} <contact:voice>{{ phone }}</contact:voice> {% endif %}
         {% if fax %} <contact:fax>{{ fax }}</contact:fax> {% endif %}
         <contact:email>{{ email }}</contact:email>
         <contact:authInfo>
           <contact:pw> {{ password }}</contact:pw>
         </contact:authInfo>
         {% if privacy %}
         <contact:disclose flag="0">
           {% for element in privacy %}
           <contact:{{ element }}/>
           {% endfor %}
         </contact:disclose>
         {% endif %}
       </contact:create>
    </create>
    <clTRID>{{ client_transaction_id }}</clTRID>
  </command>
</epp>"""

        expected_result = {
                'code': '1000',
                'message': 'Command completed successfully',
                'reason': None,
                'raw_response': 'raw_response',
                'client_transaction_id': 'client_transaction_id',
                'server_transaction_id': 'server_transaction_id',
                'repository_object_id': 'repository_object_id',
            }

        params = {
            'id': 'contact-1-id',
            'name': 'contact-1',
            'street_1': '18 Willis Street',
            'street_2': 'Wellington CBD',
            'postal_code': '6011',
            'email': 'mail@mail.net',
        }

        epp_communicator = MagicMock(EppCommunicator)
        epp_communicator.execute.return_value = expected_result
        base_command = BaseCommand(epp_communicator)

        result = base_command.execute(command, **params)

        self.assertEqual(expected_result, result)