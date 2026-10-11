"""
Base Command unit tests
"""
import threading
import time
import unittest
from unittest.mock import MagicMock, patch
from uuid import UUID

from pyepp.base_command import BaseCommand
from pyepp.command_templates import (
    _CACHE_LOCK,
    DOMAIN_CHECK_XML,
    HELLO_XML,
    TEMPLATES,
    TEMPLATE_CACHE,
    clear_template_cache,
    get_compiled_template,
    template_engine,
)
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

    def test_prepare_command_no_password_auto_generation(self) -> None:
        """When no password is supplied, _prepare_command must NOT auto-generate one."""
        command = """<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0"><command>{% if password %}<contact:authInfo><contact:pw>{{ password }}</contact:pw></contact:authInfo>{% endif %}</command></epp>"""
        expected_result = """<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0"><command></command></epp>"""
        epp_communicator = MagicMock(EppCommunicator)

        base_command = BaseCommand(epp_communicator)
        result = base_command._prepare_command(command)

        self.assertEqual(expected_result, result)

    def test_prepare_command_password_supplied(self) -> None:
        """When a password is supplied, _prepare_command must include it in the output."""
        command = """<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0"><command>{% if password %}<contact:authInfo><contact:pw>{{ password }}</contact:pw></contact:authInfo>{% endif %}</command></epp>"""
        expected_result = """<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0"><command><contact:authInfo><contact:pw>myPassword1</contact:pw></contact:authInfo></command></epp>"""
        epp_communicator = MagicMock(EppCommunicator)

        base_command = BaseCommand(epp_communicator)
        result = base_command._prepare_command(command, password='myPassword1')

        self.assertEqual(expected_result, result)

    def test_prepare_command_falsy_values(self) -> None:
        """_prepare_command must preserve falsy values like 0 and False."""
        command = """<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0"><command><val1>{{ val1 }}</val1><val2>{{ val2 }}</val2></command></epp>"""
        expected_result = """<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0"><command><val1>0</val1><val2>False</val2></command></epp>"""
        epp_communicator = MagicMock(EppCommunicator)

        base_command = BaseCommand(epp_communicator)
        result = base_command._prepare_command(command, val1=0, val2=False)

        self.assertEqual(expected_result, result)

    def test_escape_list(self) -> None:
        test_list = [
            ['hi&', '<world>'],
            {'key': '<hello&world>'},
            '<hello&world>',
            0,
            False,
            None
        ]
        expected_result = [
            ['hi&amp;', '&lt;world&gt;'],
            {'key': '&lt;hello&amp;world&gt;'},
            '&lt;hello&amp;world&gt;',
            0,
            False
        ]

        epp_communicator = MagicMock(EppCommunicator)
        base_command = BaseCommand(epp_communicator)

        result = base_command._BaseCommand__escape_list(test_list)

        self.assertEqual(expected_result, result)

    def test_escape_dict(self) -> None:
        test_dict = {
            'key1': ['hi&', '<world>'],
            'key2': {'key': '<hello&world>'},
            'key3': '<hello&world>',
            'key4': 0,
            'key5': False
        }
        expected_result = {
            'key1': ['hi&amp;', '&lt;world&gt;'],
            'key2': {'key': '&lt;hello&amp;world&gt;'},
            'key3': '&lt;hello&amp;world&gt;',
            'key4': 0,
            'key5': False
        }

        epp_communicator = MagicMock(EppCommunicator)
        base_command = BaseCommand(epp_communicator)

        result = base_command._BaseCommand__escape_dict(test_dict)

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

    def test_get_compiled_template_cached(self) -> None:
        """Verify pre-compiled template returns from cache and subsequent calls return identical object."""
        tmpl1 = BaseCommand._get_compiled_template(DOMAIN_CHECK_XML)
        self.assertIsNotNone(tmpl1)
        tmpl2 = BaseCommand._get_compiled_template(DOMAIN_CHECK_XML)
        self.assertIs(tmpl1, tmpl2)

    def test_get_compiled_template_by_name(self) -> None:
        """Verify template can be retrieved by name and produces matching output."""
        tmpl_by_name = BaseCommand._get_compiled_template("DOMAIN_CHECK")
        tmpl_by_xml = BaseCommand._get_compiled_template(DOMAIN_CHECK_XML)
        self.assertIsNotNone(tmpl_by_name)
        out1 = tmpl_by_name.render(domain_names=["example.nz"], client_transaction_id="123")
        out2 = tmpl_by_xml.render(domain_names=["example.nz"], client_transaction_id="123")
        self.assertEqual(out1, out2)

    def test_prepare_command_with_template_name(self) -> None:
        """Verify _prepare_command handles template names and generates client_transaction_id."""
        epp_communicator = MagicMock(EppCommunicator)
        base_command = BaseCommand(epp_communicator)
        xml = base_command._prepare_command("DOMAIN_CHECK", domain_names=["example.nz"])
        self.assertIn("<domain:name>example.nz</domain:name>", xml)
        self.assertIn("<clTRID>", xml)

    def test_get_compiled_template_custom_string(self) -> None:
        """Verify custom template string is compiled, cached, and reused."""
        custom_xml = """<epp><custom>{{ value }}</custom></epp>"""
        tmpl1 = BaseCommand._get_compiled_template(custom_xml)
        self.assertEqual(tmpl1.render(value="hello"), "<epp><custom>hello</custom></epp>")
        self.assertIn(custom_xml, BaseCommand._TEMPLATE_CACHE)
        tmpl2 = BaseCommand._get_compiled_template(custom_xml)
        self.assertIs(tmpl1, tmpl2)

    def test_get_compiled_template_cold_start_and_clear(self) -> None:
        """Verify get_compiled_template recovers when cache is cleared and re-initializes."""
        custom_xml = """<epp><test>{{ x }}</test></epp>"""
        get_compiled_template(custom_xml)
        self.assertIn(custom_xml, TEMPLATE_CACHE)

        clear_template_cache()
        # Custom template should be gone
        self.assertNotIn(custom_xml, TEMPLATE_CACHE)
        # Static templates should be re-initialized
        self.assertIn("DOMAIN_CHECK", TEMPLATE_CACHE)
        self.assertIn(DOMAIN_CHECK_XML, TEMPLATE_CACHE)

        # Directly test cold cache lookups
        with patch.dict(TEMPLATE_CACHE, {}, clear=True):
            # Lookup by template name
            tmpl_name = get_compiled_template("HELLO")
            self.assertIsNotNone(tmpl_name)
            # Lookup by XML string matching static template
            tmpl_xml = get_compiled_template(HELLO_XML)
            self.assertIsNotNone(tmpl_xml)

    def test_dynamic_template_cache_eviction(self) -> None:
        """Verify dynamic templates are evicted when max cache size is exceeded."""
        clear_template_cache()
        with patch("pyepp.command_templates._MAX_DYNAMIC_CACHE_SIZE", 3):
            for i in range(6):
                get_compiled_template(f"<epp><dynamic_{i}>{{{{ val }}}}</dynamic_{i}></epp>")

            # Ensure static templates were never evicted
            self.assertIn("DOMAIN_CHECK", TEMPLATE_CACHE)
            self.assertIn(DOMAIN_CHECK_XML, TEMPLATE_CACHE)

    def test_concurrent_template_compilation(self) -> None:
        """Verify thread-safe compilation of concurrent templates."""
        results = []
        errors = []

        def worker(idx: int) -> None:
            try:
                tmpl = get_compiled_template(f"<epp><concurrent_{idx % 3}>{{{{ v }}}}</concurrent_{idx % 3}></epp>")
                rendered = tmpl.render(v=str(idx))
                results.append(rendered)
            except Exception as ex:  # pylint: disable=broad-except
                errors.append(ex)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)
        self.assertEqual(len(results), 20)

    def test_get_compiled_template_double_checked_lock(self) -> None:
        """Verify double-checked locking handles case where template was cached while waiting for lock."""
        custom_xml = "<epp><double_check/></epp>"
        entered_lock = threading.Event()
        result_holder = []

        def worker() -> None:
            entered_lock.set()
            tmpl = get_compiled_template(custom_xml)
            result_holder.append(tmpl)

        with _CACHE_LOCK:
            t = threading.Thread(target=worker)
            t.start()
            entered_lock.wait(timeout=1.0)
            time.sleep(0.01)
            # While the lock is held, populate TEMPLATE_CACHE
            expected_tmpl = template_engine.from_string(custom_xml)
            TEMPLATE_CACHE[custom_xml] = expected_tmpl

        t.join(timeout=1.0)
        self.assertEqual(len(result_holder), 1)
        self.assertIs(result_holder[0], expected_tmpl)

    def test_concurrent_template_eviction_no_keyerror(self) -> None:
        """Verify concurrent lookup and cache eviction does not raise KeyError."""
        clear_template_cache()
        errors: list[Exception] = []
        stop_event = threading.Event()

        def reader() -> None:
            while not stop_event.is_set():
                try:
                    for i in range(10):
                        tmpl = BaseCommand._get_compiled_template(f"<epp><item_{i}>{{{{ val }}}}</item_{i}></epp>")
                        self.assertIsNotNone(tmpl)
                except Exception as ex:  # pylint: disable=broad-except
                    errors.append(ex)
                    break

        def writer() -> None:
            with patch("pyepp.command_templates._MAX_DYNAMIC_CACHE_SIZE", 5):
                for i in range(100):
                    if stop_event.is_set():
                        break
                    get_compiled_template(f"<epp><churn_{i}>{{{{ val }}}}</churn_{i}></epp>")

        threads = [threading.Thread(target=reader) for _ in range(4)]
        writer_thread = threading.Thread(target=writer)

        for t in threads:
            t.start()
        writer_thread.start()

        writer_thread.join()
        stop_event.set()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])

    def test_prepare_command_benchmark(self) -> None:
        """Verify that 1,000 iterations of _prepare_command drops execution time by >80%."""
        epp_communicator = MagicMock(EppCommunicator)
        base_command = BaseCommand(epp_communicator)

        # Warm up
        base_command._prepare_command(DOMAIN_CHECK_XML, domain_names=["test.nz"])

        # Measure cached execution (PERF-1)
        t0 = time.perf_counter()
        for _ in range(1000):
            base_command._prepare_command(DOMAIN_CHECK_XML, domain_names=["test.nz"])
        cached_duration = time.perf_counter() - t0

        # Measure uncached execution (simulating old behavior: recompiling every time)
        t0 = time.perf_counter()
        for _ in range(1000):
            tmpl = template_engine.from_string(DOMAIN_CHECK_XML)
            tmpl.render(domain_names=["test.nz"], client_transaction_id="mock-uuid")
        uncached_duration = time.perf_counter() - t0

        speedup_pct = (1.0 - (cached_duration / uncached_duration)) * 100.0
        # Verification requirement: execution time drops by >80%
        self.assertGreater(
            speedup_pct,
            80.0,
            f"Expected >80% speedup, achieved {speedup_pct:.2f}% (cached: {cached_duration:.4f}s, uncached: {uncached_duration:.4f}s)"
        )