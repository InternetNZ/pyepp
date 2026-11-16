"""
Domain unit tests
"""

import unittest
from datetime import date, datetime
from enum import Enum, IntEnum
from unittest.mock import MagicMock, patch

from bs4 import BeautifulSoup

from pyepp.domain import (
    Domain,
    DomainData,
    DSRecordData,
    DSRecordKeyData,
    DNSKeyFlagEnum,
    DNSSECAlgorithm,
    DigestTypeEnum,
)
from pyepp.epp import EppCommunicator, EppResultData


class DomainTest(unittest.TestCase):
    """
    Domain name unit tests
    """

    def setUp(self) -> None:
        self.maxDiff = None

    def test_check_unsuccessful(self) -> None:
        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        expected_result = EppResultData(
            **{
                "code": 2000,
                "message": "Command completed unsuccessfully",
                "reason": None,
                "raw_response": "response",
                "result_data": None,
            }
        )
        domain.execute = MagicMock(return_value=expected_result)

        result = domain.check(["internet.nz"])

        self.assertEqual(result, expected_result)

    def test_check(self) -> None:
        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        expected_result = EppResultData(
            **{
                "client_transaction_id": "8d537a88-b18c-4f74-903e-aff9be1f902d",
                "code": 1000,
                "message": "Command completed successfully",
                "raw_response": "<response>\n"
                '<result code="1000">\n'
                "<msg>Command completed successfully</msg>\n"
                "</result>\n"
                "<resData>\n"
                "<domain:chkData>\n"
                "<domain:cd>\n"
                '<domain:name avail="false">inz1.nz</domain:name>\n'
                "<domain:reason>Registered</domain:reason>\n"
                "</domain:cd>\n"
                "<domain:cd>\n"
                '<domain:name avail="true">inz2.nz</domain:name>\n'
                "</domain:cd>\n"
                "<domain:cd>\n"
                '<domain:name avail="true">inz3.nz</domain:name>\n'
                "</domain:cd>\n"
                "</domain:chkData>\n"
                "</resData>\n"
                "<trID>\n"
                "<clTRID>8d537a88-b18c-4f74-903e-aff9be1f902d</clTRID>\n"
                "<svTRID>CIRA-000062431732-0000000003</svTRID>\n"
                "</trID>\n"
                "</response>",
                "reason": None,
                "repository_object_id": None,
                "result_data": {
                    "inz3.nz": {"avail": True, "reason": None},
                    "inz2.nz": {"avail": True, "reason": None},
                    "inz1.nz": {"avail": False, "reason": "Registered"},
                },
                "server_transaction_id": "CIRA-000062431732-0000000003",
            }
        )

        domain.execute = MagicMock(return_value=expected_result)

        result = domain.check(["inz1.nz", "inz2.nz", "inz3.nz"])

        self.assertEqual(result, expected_result)

    def test_info_unsuccessful(self) -> None:
        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        expected_result = EppResultData(
            **{
                "code": 2000,
                "message": "Command completed unsuccessfully",
                "reason": None,
                "raw_response": "response",
                "result_data": None,
            }
        )
        domain.execute = MagicMock(return_value=expected_result)

        result = domain.info("internet.nz")

        self.assertEqual(result, expected_result)

    def test_check_dry_run(self) -> None:
        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        expected_result = EppResultData(
            code=1000,
            message="Dry run",
            reason=None,
            raw_response="<domain:check/>",
            result_data=None,
            dry_run=True,
        )
        domain.execute = MagicMock(return_value=expected_result)
        result = domain.check(["internet.nz"])
        self.assertEqual(result, expected_result)

    def test_check_server_message_dry_run_parsed_when_not_dry_run(self) -> None:
        """Verify that a server response with message 'Dry run' is parsed when dry_run=False."""
        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        execute_result = EppResultData(
            code=1000,
            message="Dry run",
            reason=None,
            raw_response=(
                '<response><resData>'
                '<cd><name avail="1">test.nz</name></cd>'
                '</resData></response>'
            ),
            result_data=None,
            dry_run=False,
        )
        domain.execute = MagicMock(return_value=execute_result)
        result = domain.check(["test.nz"])
        self.assertEqual(
            result.result_data, {"test.nz": {"avail": True, "reason": None}}
        )

    def test_check_unavailable_without_reason(self) -> None:
        """RFC 5731 §3.1.1: verify domain.check handles avail="0" without optional <reason>."""
        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        xml = (
            '<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">'
            '<response><resData>'
            '<domain:chkData xmlns:domain="urn:ietf:params:xml:ns:domain-1.0">'
            '<domain:cd><domain:name avail="0">taken.nz</domain:name></domain:cd>'
            '</domain:chkData>'
            '</resData></response>'
        )
        execute_result = EppResultData(
            code=1000,
            message="Command completed successfully",
            reason=None,
            raw_response=xml,
            result_data=None,
            dry_run=False,
            parsed_xml=BeautifulSoup(xml, "xml"),
        )
        domain.execute = MagicMock(return_value=execute_result)
        result = domain.check(["taken.nz"])
        self.assertEqual(
            result.result_data, {"taken.nz": {"avail": False, "reason": None}}
        )

    def test_check_ignores_extension_cd_and_missing_name(self) -> None:
        """Verify domain.check scopes to <resData>/<chkData> and ignores extension <cd> or missing <name>."""
        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        xml = (
            '<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">'
            '<response><resData>'
            '<domain:chkData xmlns:domain="urn:ietf:params:xml:ns:domain-1.0">'
            '<domain:cd><domain:name avail="1">available.nz</domain:name></domain:cd>'
            '<domain:cd><domain:reason>malformed-without-name</domain:reason></domain:cd>'
            '</domain:chkData>'
            '</resData>'
            '<extension>'
            '<fee:chkData xmlns:fee="urn:ietf:params:xml:ns:epp:fee-1.0">'
            '<fee:cd avail="1"><fee:objID>available.nz</fee:objID></fee:cd>'
            '<fee:cd><fee:name>available.nz</fee:name></fee:cd>'
            '</fee:chkData>'
            '</extension>'
            '</response></epp>'
        )
        execute_result = EppResultData(
            code=1000,
            message="Command completed successfully",
            reason=None,
            raw_response=xml,
            result_data=None,
            dry_run=False,
            parsed_xml=BeautifulSoup(xml, "xml"),
        )
        domain.execute = MagicMock(return_value=execute_result)
        result = domain.check(["available.nz"])
        self.assertEqual(
            result.result_data, {"available.nz": {"avail": True, "reason": None}}
        )

    def test_info_ds_data_without_key_data(self) -> None:
        """Verify domain.info parses <secDNS:dsData> when optional <secDNS:keyData> is omitted."""
        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        xml = (
            '<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">'
            '<response><resData>'
            '<domain:infData xmlns:domain="urn:ietf:params:xml:ns:domain-1.0">'
            '<domain:name>ds-only.nz</domain:name>'
            '<domain:status s="ok"/>'
            '<domain:clID>ClientA</domain:clID>'
            '</domain:infData>'
            '</resData>'
            '<extension>'
            '<secDNS:infData xmlns:secDNS="urn:ietf:params:xml:ns:secDNS-1.1">'
            '<secDNS:dsData>'
            '<secDNS:keyTag>12345</secDNS:keyTag>'
            '<secDNS:alg>8</secDNS:alg>'
            '<secDNS:digestType>2</secDNS:digestType>'
            '<secDNS:digest>ABCDEF0123456789</secDNS:digest>'
            '</secDNS:dsData>'
            '</secDNS:infData>'
            '</extension>'
            '</response></epp>'
        )
        execute_result = EppResultData(
            code=1000,
            message="Command completed successfully",
            reason=None,
            raw_response=xml,
            result_data=None,
            dry_run=False,
            parsed_xml=BeautifulSoup(xml, "xml"),
        )
        domain.execute = MagicMock(return_value=execute_result)
        result = domain.info("ds-only.nz")
        self.assertEqual(len(result.result_data.dns_sec), 1)
        ds = result.result_data.dns_sec[0]
        self.assertEqual(ds.key_tag, 12345)
        self.assertEqual(ds.algorithm, DNSSECAlgorithm.RSA_SHA_256)
        self.assertEqual(ds.algorithm, 8)
        self.assertEqual(ds.digest_type, DigestTypeEnum.SHA_256)
        self.assertEqual(ds.digest_type, 2)
        self.assertEqual(ds.digest, "ABCDEF0123456789")
        self.assertIsNone(ds.dns_key)

    def test_check_uses_parsed_xml_directly(self) -> None:
        """Verify domain.check re-uses result.parsed_xml directly."""
        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        mock_parsed = MagicMock()
        mock_cd = MagicMock()
        mock_name = MagicMock()
        mock_name.text = "test.nz"
        mock_name.get.return_value = "1"
        mock_cd.find.side_effect = lambda tag, *args, **kwargs: mock_name if tag == "name" else None
        mock_parsed.find.return_value = None
        mock_parsed.find_all.return_value = [mock_cd]

        execute_result = EppResultData(
            code=1000,
            message="Command completed successfully",
            reason=None,
            raw_response="<dummy/>",
            result_data=None,
            dry_run=False,
            parsed_xml=mock_parsed,
        )
        domain.execute = MagicMock(return_value=execute_result)
        result = domain.check(["test.nz"])
        mock_parsed.find_all.assert_called_with("cd")
        self.assertEqual(
            result.result_data, {"test.nz": {"avail": True, "reason": None}}
        )

    def test_info_uses_parsed_xml_directly(self) -> None:
        """Verify domain.info re-uses result.parsed_xml directly."""
        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        mock_parsed = MagicMock()
        mock_name = MagicMock(text="test.nz")
        mock_clid = MagicMock(text="933")
        mock_registrant = MagicMock(text="reg-1")
        mock_parsed.find.side_effect = lambda tag, *args, **kwargs: {
            "name": mock_name,
            "clID": mock_clid,
            "registrant": mock_registrant,
        }.get(tag, None)
        mock_parsed.find_all.return_value = []

        execute_result = EppResultData(
            code=1000,
            message="Command completed successfully",
            reason=None,
            raw_response="<dummy/>",
            result_data=None,
            dry_run=False,
            parsed_xml=mock_parsed,
        )
        domain.execute = MagicMock(return_value=execute_result)
        result = domain.info("test.nz")
        self.assertEqual(result.result_data.domain_name, "test.nz")
        self.assertEqual(result.result_data.registrant, "reg-1")

    def test_info_dry_run(self) -> None:
        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        expected_result = EppResultData(
            code=1000,
            message="Dry run",
            reason=None,
            raw_response="<domain:info/>",
            result_data=None,
            dry_run=True,
        )
        domain.execute = MagicMock(return_value=expected_result)
        result = domain.info("internet.nz")
        self.assertEqual(result, expected_result)

    def test_info(self) -> None:
        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        execute_result = EppResultData(
            **{
                "client_transaction_id": None,
                "code": 1000,
                "message": "Command completed successfully",
                "raw_response": "<response>\n"
                '<result code="1000">\n'
                "<msg>Command completed successfully</msg>\n"
                "</result>\n"
                "<resData>\n"
                "<domain:infData>\n"
                "<domain:name>internet.nz</domain:name>\n"
                "<domain:roid>9204701-INZ</domain:roid>\n"
                '<domain:status s="inactive"/>\n'
                "<domain:registrant>inz-contact-1</domain:registrant>\n"
                "<domain:contact "
                'type="admin">inz-contact-1</domain:contact>\n'
                "<domain:contact "
                'type="tech">inz-contact-1</domain:contact>\n'
                "<domain:clID>933</domain:clID>\n"
                "<domain:crID>933</domain:crID>\n"
                "<domain:crDate>2023-02-23T21:56:22.713Z</domain:crDate>\n"
                "<domain:upID>CIRA_RAR_1</domain:upID>\n"
                "<domain:upDate>2023-02-24T21:59:27.901Z</domain:upDate>\n"
                "<domain:exDate>2024-02-23T21:56:22.713Z</domain:exDate>\n"
                "</domain:infData>\n"
                "</resData>\n"
                "<extension>\n"
                "<secDNS:infData "
                'xmlns:secDNS="urn:ietf:params:xml:ns:secDNS-1.1">\n'
                "<secDNS:dsData>\n"
                "<secDNS:keyTag>17600</secDNS:keyTag>\n"
                "<secDNS:alg>13</secDNS:alg>\n"
                "<secDNS:digestType>1</secDNS:digestType>\n"
                "<secDNS:digest>4ffb0f3f0fb5edbaa0067d1cd94bb545249cfea2</secDNS:digest>\n"
                "<secDNS:keyData>\n"
                "<secDNS:flags>257</secDNS:flags>\n"
                "<secDNS:protocol>3</secDNS:protocol>\n"
                "<secDNS:alg>14</secDNS:alg>\n"
                "<secDNS:pubKey>1fHiagyGUIxsDmeYaaKOWceffQn7QTaCwM1y6Oy1zYRpndxu/6WAHM99p/X/dM7t+RcGahZ8+GlX5JHkbyaMllg==</secDNS:pubKey>\n"
                "</secDNS:keyData>\n"
                "</secDNS:dsData>\n"
                "<secDNS:dsData>\n"
                "<secDNS:keyTag>17600</secDNS:keyTag>\n"
                "<secDNS:alg>13</secDNS:alg>\n"
                "<secDNS:digestType>2</secDNS:digestType>\n"
                "<secDNS:digest>024c96b094aaad3892babb303e02587f7d6f8f749fef9ff642e3bb8bfc2e0dcf</secDNS:digest>\n"
                "<secDNS:keyData>\n"
                "<secDNS:flags>257</secDNS:flags>\n"
                "<secDNS:protocol>3</secDNS:protocol>\n"
                "<secDNS:alg>13</secDNS:alg>\n"
                "<secDNS:pubKey>2fHiagyGUIxsDmeYaaKOWceffQn7QTaCwM1y6Oy1zYRpndxu/6WAHM99p/X/dM7t+RcGahZ8+GlX5JHkbyaMllg==</secDNS:pubKey>\n"
                "</secDNS:keyData>\n"
                "</secDNS:dsData>\n"
                "<secDNS:dsData>\n"
                "<secDNS:keyTag>17600</secDNS:keyTag>\n"
                "<secDNS:alg>13</secDNS:alg>\n"
                "<secDNS:digestType>4</secDNS:digestType>\n"
                "<secDNS:digest>14d92f9f1e82c0906e2003b9e3401de4024f705724ef14d848fc2708d5714d5572db040faa3e317753e6577c7e70cbb8</secDNS:digest>\n"
                "<secDNS:keyData>\n"
                "<secDNS:flags>257</secDNS:flags>\n"
                "<secDNS:protocol>3</secDNS:protocol>\n"
                "<secDNS:alg>13</secDNS:alg>\n"
                "<secDNS:pubKey>3fHiagyGUIxsDmeYaaKOWceffQn7QTaCwM1y6Oy1zYRpndxu/6WAHM99p/X/dM7t+RcGahZ8+GlX5JHkbyaMllg==</secDNS:pubKey>\n"
                "</secDNS:keyData>\n"
                "</secDNS:dsData>\n"
                "</secDNS:infData>\n"
                '<rgp:infData xmlns:rgp="urn:ietf:params:xml:ns:rgp-1.0">\n'
                '<rgp:rgpStatus s="addPeriod"/>\n'
                "</rgp:infData>\n"
                "<regtype:infData "
                'xmlns:regtype="urn:ietf:params:xml:ns:regtype-0.1">\n'
                "<regtype:type>standard</regtype:type>\n"
                "</regtype:infData>\n"
                "</extension>\n"
                "<trID>\n"
                "<svTRID>CIRA-000063163743-0000000003</svTRID>\n"
                "</trID>\n"
                "</response>",
                "reason": None,
                "repository_object_id": "9204701-INZ",
                "server_transaction_id": "CIRA-000063163743-0000000003",
                "result_data": None,
            }
        )

        expected_result = EppResultData(
            **{
                "client_transaction_id": None,
                "code": 1000,
                "message": "Command completed successfully",
                "raw_response": "<response>\n"
                '<result code="1000">\n'
                "<msg>Command completed successfully</msg>\n"
                "</result>\n"
                "<resData>\n"
                "<domain:infData>\n"
                "<domain:name>internet.nz</domain:name>\n"
                "<domain:roid>9204701-INZ</domain:roid>\n"
                '<domain:status s="inactive"/>\n'
                "<domain:registrant>inz-contact-1</domain:registrant>\n"
                "<domain:contact "
                'type="admin">inz-contact-1</domain:contact>\n'
                "<domain:contact "
                'type="tech">inz-contact-1</domain:contact>\n'
                "<domain:clID>933</domain:clID>\n"
                "<domain:crID>933</domain:crID>\n"
                "<domain:crDate>2023-02-23T21:56:22.713Z</domain:crDate>\n"
                "<domain:upID>CIRA_RAR_1</domain:upID>\n"
                "<domain:upDate>2023-02-24T21:59:27.901Z</domain:upDate>\n"
                "<domain:exDate>2024-02-23T21:56:22.713Z</domain:exDate>\n"
                "</domain:infData>\n"
                "</resData>\n"
                "<extension>\n"
                "<secDNS:infData "
                'xmlns:secDNS="urn:ietf:params:xml:ns:secDNS-1.1">\n'
                "<secDNS:dsData>\n"
                "<secDNS:keyTag>17600</secDNS:keyTag>\n"
                "<secDNS:alg>13</secDNS:alg>\n"
                "<secDNS:digestType>1</secDNS:digestType>\n"
                "<secDNS:digest>4ffb0f3f0fb5edbaa0067d1cd94bb545249cfea2</secDNS:digest>\n"
                "<secDNS:keyData>\n"
                "<secDNS:flags>257</secDNS:flags>\n"
                "<secDNS:protocol>3</secDNS:protocol>\n"
                "<secDNS:alg>14</secDNS:alg>\n"
                "<secDNS:pubKey>1fHiagyGUIxsDmeYaaKOWceffQn7QTaCwM1y6Oy1zYRpndxu/6WAHM99p/X/dM7t+RcGahZ8+GlX5JHkbyaMllg==</secDNS:pubKey>\n"
                "</secDNS:keyData>\n"
                "</secDNS:dsData>\n"
                "<secDNS:dsData>\n"
                "<secDNS:keyTag>17600</secDNS:keyTag>\n"
                "<secDNS:alg>13</secDNS:alg>\n"
                "<secDNS:digestType>2</secDNS:digestType>\n"
                "<secDNS:digest>024c96b094aaad3892babb303e02587f7d6f8f749fef9ff642e3bb8bfc2e0dcf</secDNS:digest>\n"
                "<secDNS:keyData>\n"
                "<secDNS:flags>257</secDNS:flags>\n"
                "<secDNS:protocol>3</secDNS:protocol>\n"
                "<secDNS:alg>13</secDNS:alg>\n"
                "<secDNS:pubKey>2fHiagyGUIxsDmeYaaKOWceffQn7QTaCwM1y6Oy1zYRpndxu/6WAHM99p/X/dM7t+RcGahZ8+GlX5JHkbyaMllg==</secDNS:pubKey>\n"
                "</secDNS:keyData>\n"
                "</secDNS:dsData>\n"
                "<secDNS:dsData>\n"
                "<secDNS:keyTag>17600</secDNS:keyTag>\n"
                "<secDNS:alg>13</secDNS:alg>\n"
                "<secDNS:digestType>4</secDNS:digestType>\n"
                "<secDNS:digest>14d92f9f1e82c0906e2003b9e3401de4024f705724ef14d848fc2708d5714d5572db040faa3e317753e6577c7e70cbb8</secDNS:digest>\n"
                "<secDNS:keyData>\n"
                "<secDNS:flags>257</secDNS:flags>\n"
                "<secDNS:protocol>3</secDNS:protocol>\n"
                "<secDNS:alg>13</secDNS:alg>\n"
                "<secDNS:pubKey>3fHiagyGUIxsDmeYaaKOWceffQn7QTaCwM1y6Oy1zYRpndxu/6WAHM99p/X/dM7t+RcGahZ8+GlX5JHkbyaMllg==</secDNS:pubKey>\n"
                "</secDNS:keyData>\n"
                "</secDNS:dsData>\n"
                "</secDNS:infData>\n"
                '<rgp:infData xmlns:rgp="urn:ietf:params:xml:ns:rgp-1.0">\n'
                '<rgp:rgpStatus s="addPeriod"/>\n'
                "</rgp:infData>\n"
                "<regtype:infData "
                'xmlns:regtype="urn:ietf:params:xml:ns:regtype-0.1">\n'
                "<regtype:type>standard</regtype:type>\n"
                "</regtype:infData>\n"
                "</extension>\n"
                "<trID>\n"
                "<svTRID>CIRA-000063163743-0000000003</svTRID>\n"
                "</trID>\n"
                "</response>",
                "repository_object_id": "9204701-INZ",
                "result_data": DomainData(
                    domain_name="internet.nz",
                    sponsoring_client_id="933",
                    status=["inactive"],
                    host=None,
                    registrant="inz-contact-1",
                    admin=["inz-contact-1"],
                    tech=["inz-contact-1"],
                    billing=None,
                    create_date="2023-02-23T21:56:22.713Z",
                    create_client_id="933",
                    update_client_id="CIRA_RAR_1",
                    update_date="2023-02-24T21:59:27.901Z",
                    expiry_date="2024-02-23T21:56:22.713Z",
                    transfer_date=None,
                    password=None,
                    period=None,
                    dns_sec=[
                        DSRecordData(
                            key_tag=17600,
                            algorithm=DNSSECAlgorithm.ECDSA_CURVE_P_256_WITH_SHA_256,
                            digest_type=DigestTypeEnum.SHA_1,
                            digest="4ffb0f3f0fb5edbaa0067d1cd94bb545249cfea2",
                            dns_key=DSRecordKeyData(
                                algorithm=DNSSECAlgorithm.ECDSA_CURVE_P_384_WITH_SHA_384,
                                flag=DNSKeyFlagEnum.FLAG_257,
                                protocol=3,
                                public_key="1fHiagyGUIxsDmeYaaKOWceffQn7QTaCwM1y6Oy1zYRpndxu/6WAHM99p/X/dM7t+RcGahZ8+GlX5JHkbyaMllg==",
                            ),
                        ),
                        DSRecordData(
                            key_tag=17600,
                            algorithm=DNSSECAlgorithm.ECDSA_CURVE_P_256_WITH_SHA_256,
                            digest_type=DigestTypeEnum.SHA_256,
                            digest="024c96b094aaad3892babb303e02587f7d6f8f749fef9ff642e3bb8bfc2e0dcf",
                            dns_key=DSRecordKeyData(
                                algorithm=DNSSECAlgorithm.ECDSA_CURVE_P_256_WITH_SHA_256,
                                flag=DNSKeyFlagEnum.FLAG_257,
                                protocol=3,
                                public_key="2fHiagyGUIxsDmeYaaKOWceffQn7QTaCwM1y6Oy1zYRpndxu/6WAHM99p/X/dM7t+RcGahZ8+GlX5JHkbyaMllg==",
                            ),
                        ),
                        DSRecordData(
                            key_tag=17600,
                            algorithm=DNSSECAlgorithm.ECDSA_CURVE_P_256_WITH_SHA_256,
                            digest_type=DigestTypeEnum.SHA_384,
                            digest="14d92f9f1e82c0906e2003b9e3401de4024f705724ef14d848fc2708d5714d5572db040faa3e317753e6577c7e70cbb8",
                            dns_key=DSRecordKeyData(
                                algorithm=DNSSECAlgorithm.ECDSA_CURVE_P_256_WITH_SHA_256,
                                flag=DNSKeyFlagEnum.FLAG_257,
                                protocol=3,
                                public_key="3fHiagyGUIxsDmeYaaKOWceffQn7QTaCwM1y6Oy1zYRpndxu/6WAHM99p/X/dM7t+RcGahZ8+GlX5JHkbyaMllg==",
                            ),
                        ),
                    ],
                ),
                "server_transaction_id": "CIRA-000063163743-0000000003",
            }
        )

        domain.execute = MagicMock(return_value=execute_result)

        result = domain.info("internet.nz")
        self.assertEqual(result, expected_result)

    def test_create(self) -> None:
        expected_result = EppResultData(
            **{
                "client_transaction_id": "96aaf073-5741-47bd-b1eb-b5abcf4206fa",
                "code": 1000,
                "message": "Command completed successfully",
                "raw_response": "<response>\n"
                '<result code="1000">\n'
                "<msg>Command completed successfully</msg>\n"
                "</result>\n"
                "<resData>\n"
                "<domain:creData>\n"
                "<domain:name>internet.nz</domain:name>\n"
                "<domain:crDate>2023-05-07T23:36:25.681Z</domain:crDate>\n"
                "<domain:exDate>2026-05-07T23:36:25.681Z</domain:exDate>\n"
                "</domain:creData>\n"
                "</resData>\n"
                "<trID>\n"
                "<clTRID>96aaf073-5741-47bd-b1eb-b5abcf4206fa</clTRID>\n"
                "<svTRID>CIRA-000064317159-0000000003</svTRID>\n"
                "</trID>\n"
                "</response>",
                "reason": None,
                "repository_object_id": None,
                "server_transaction_id": "CIRA-000064317159-0000000003",
                "result_data": None,
            }
        )

        create_params = DomainData(
            domain_name="internet.nz",
            registrant="inz-contact-3",
            admin="inz-contact-1",
            tech="inz-contact-1",
            billing="inz-contact-3",
            period=3,
            host=[
                "01y.test-indwrx2vkicn2otgm3otav5wpnzvjd.co.nz",
                "0d9x6239.drdomain.co.nz",
            ],
            dns_sec=DSRecordData(
                key_tag=1235,
                algorithm=DNSSECAlgorithm.DSA_SHA_1.value,
                digest_type=DigestTypeEnum.SHA_1.value,
                digest="8cdb09364147aed879d12c68d615f98af5900b73",
            ),
        )
        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        domain.execute = MagicMock(return_value=expected_result)

        result = domain.create(create_params)

        self.assertEqual(result, expected_result)

    def test_delete(self) -> None:
        expected_result = EppResultData(
            **{
                "client_transaction_id": "b9c0c77d-b2d9-47c7-9edb-b4d4988c2e7d",
                "code": 1000,
                "message": "Command completed successfully",
                "raw_response": "<response>\n"
                '<result code="1000">\n'
                "<msg>Command completed successfully</msg>\n"
                "</result>\n"
                "<trID>\n"
                "<clTRID>b9c0c77d-b2d9-47c7-9edb-b4d4988c2e7d</clTRID>\n"
                "<svTRID>CIRA-000064688525-0000000004</svTRID>\n"
                "</trID>\n"
                "</response>",
                "reason": None,
                "repository_object_id": None,
                "server_transaction_id": "CIRA-000064688525-0000000004",
                "result_data": None,
            }
        )

        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        domain.execute = MagicMock(return_value=expected_result)

        result = domain.delete("internet.nz")

        self.assertEqual(result, expected_result)

    def test_renew(self) -> None:
        expected_result = EppResultData(
            **{
                "client_transaction_id": "3fc04fc6-0b40-4979-99c0-fa91e9da573f",
                "code": 1000,
                "message": "Command completed successfully",
                "raw_response": "<response>\n"
                '<result code="1000">\n'
                "<msg>Command completed successfully</msg>\n"
                "</result>\n"
                "<resData>\n"
                "<domain:renData>\n"
                "<domain:name>internet.nz</domain:name>\n"
                "<domain:exDate>2026-01-21T21:56:22.713Z</domain:exDate>\n"
                "</domain:renData>\n"
                "</resData>\n"
                "<trID>\n"
                "<clTRID>3fc04fc6-0b40-4979-99c0-fa91e9da573f</clTRID>\n"
                "<svTRID>CIRA-000065618145-0000000004</svTRID>\n"
                "</trID>\n"
                "</response>",
                "reason": None,
                "repository_object_id": None,
                "server_transaction_id": "CIRA-000065618145-0000000004",
                "result_data": None,
            }
        )

        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        domain.execute = MagicMock(return_value=expected_result)

        result = domain.renew(
            domain_name="internet.nz", expiry_date=date(2024, 1, 1), period=2
        )

        self.assertEqual(result, expected_result)

    def test_transfer(self) -> None:
        expected_result = EppResultData(
            **{
                "client_transaction_id": "3fc04fc6-0b40-4979-99c0-fa91e9da573f",
                "code": 1000,
                "message": "Command completed successfully",
                "raw_response": "<response>\n"
                '<result code="1000">\n'
                "<msg>Command completed successfully</msg>\n"
                "</result>\n"
                "<resData>\n"
                "<domain:renData>\n"
                "<domain:name>internet.nz</domain:name>\n"
                "<domain:reID>ClientX</domain:reID>\n"
                "<domain:reDate>2000-06-08T22:00:00.0Z</domain:reDate>\n"
                "<domain:acID>ClientY</domain:acID>\n"
                "<domain:acDate>2000-06-13T22:00:00.0Z</domain:acDate>\n"
                "<domain:exDate>2002-09-08T22:00:00.0Z</domain:exDate>\n"
                "</domain:renData>\n"
                "</resData>\n"
                "<trID>\n"
                "<clTRID>3fc04fc6-0b40-4979-99c0-fa91e9da573f</clTRID>\n"
                "<svTRID>CIRA-000065618145-0000000004</svTRID>\n"
                "</trID>\n"
                "</response>",
                "reason": None,
                "repository_object_id": None,
                "server_transaction_id": "CIRA-000065618145-0000000004",
                "result_data": None,
            }
        )

        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        domain.execute = MagicMock(return_value=expected_result)

        result = domain.transfer(
            domain_name="internet.nz", password="PassWord", period=1
        )

        self.assertEqual(result, expected_result)

    def test_domain_update(self) -> None:
        expected_result = EppResultData(
            **{
                "client_transaction_id": "d2066d60-fc5e-4b7a-9001-893ca2957857",
                "code": 1000,
                "message": "Command completed successfully",
                "raw_response": "<response>\n"
                '<result code="1000">\n'
                "<msg>Command completed successfully</msg>\n"
                "</result>\n"
                "<trID>\n"
                "<clTRID>d2066d60-fc5e-4b7a-9001-893ca2957857</clTRID>\n"
                "<svTRID>CIRA-000068457178-0000000004</svTRID>\n"
                "</trID>\n"
                "</response>",
                "reason": None,
                "repository_object_id": None,
                "server_transaction_id": "CIRA-000068457178-0000000004",
                "result_data": None,
            }
        )

        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        domain.execute = MagicMock(return_value=expected_result)
        domain.info = MagicMock(
            return_value={
                "result_data": DomainData(
                    domain_name="internet.nz",
                    registrant="registrant1",
                    admin="old-admin",
                    tech="old-tech",
                    period=1,
                )
            }
        )

        result = domain.update(
            domain_name="internet.nz",
            password="PassWord",
            add_admins=[
                "contact-admin",
            ],
            add_techs=[
                "contact-tech",
            ],
        )

        self.assertEqual(result, expected_result)

    def test_restore(self) -> None:
        expected_result = EppResultData(
            **{
                "client_transaction_id": "b9c0c77d-b2d9-47c7-9edb-b4d4988c2e7d",
                "code": 1000,
                "message": "Command completed successfully",
                "raw_response": "<response>\n"
                '<result code="1000">\n'
                "<msg>Command completed successfully</msg>\n"
                "</result>\n"
                "<extension>\n"
                "<rgp:upData>\n"
                '<rgp:rgpStatus s="pendingRestore"/>\n'
                "</rgp:upData>\n"
                "</extension>\n"
                "<trID>\n"
                "<clTRID>b9c0c77d-b2d9-47c7-9edb-b4d4988c2e7d</clTRID>\n"
                "<svTRID>CIRA-000064688525-0000000004</svTRID>\n"
                "</trID>\n"
                "</response>",
                "reason": None,
                "repository_object_id": None,
                "server_transaction_id": "CIRA-000064688525-0000000004",
                "result_data": None,
            }
        )

        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        domain.execute = MagicMock(return_value=expected_result)

        result = domain.restore("internet.nz")

        self.assertEqual(result, expected_result)

    def test_restore_report(self) -> None:
        expected_result = EppResultData(
            **{
                "client_transaction_id": "b9c0c77d-b2d9-47c7-9edb-b4d4988c2e7d",
                "code": 1000,
                "message": "Command completed successfully",
                "raw_response": "<response>\n"
                '<result code="1000">\n'
                "<msg>Command completed successfully</msg>\n"
                "</result>\n"
                "<trID>\n"
                "<clTRID>b9c0c77d-b2d9-47c7-9edb-b4d4988c2e7d</clTRID>\n"
                "<svTRID>CIRA-000064688525-0000000004</svTRID>\n"
                "</trID>\n"
                "</response>",
                "reason": None,
                "repository_object_id": None,
                "server_transaction_id": "CIRA-000064688525-0000000004",
                "result_data": None,
            }
        )

        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        domain.execute = MagicMock(return_value=expected_result)

        result = domain.restore_report(
            "internet.nz",
            "pre-data",
            "post-data",
            datetime(2023, 1, 1),
            datetime(2023, 1, 1),
            "reason",
            "statement1",
            "statement2",
        )

        self.assertEqual(result, expected_result)

    def test_create_generates_password_when_not_supplied(self) -> None:
        """domain.create() must auto-generate a password when none is provided."""
        create_params = DomainData(
            domain_name="internet.nz",
            registrant="inz-contact-3",
            period=3,
        )

        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        domain.execute = MagicMock(return_value=EppResultData(
            code=1000, message="Command completed successfully", raw_response="", result_data=None
        ))

        domain.create(create_params)

        _, kwargs = domain.execute.call_args
        self.assertIn("password", kwargs)
        self.assertTrue(kwargs["password"], "Password should be a non-empty generated string")

    def test_update_does_not_generate_password_when_not_supplied(self) -> None:
        """domain.update() must NOT generate or include a password when none is provided."""
        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        domain.execute = MagicMock(return_value=EppResultData(
            code=1000, message="Command completed successfully", raw_response="", result_data=None
        ))
        domain.info = MagicMock(
            return_value={
                "result_data": DomainData(
                    domain_name="internet.nz",
                    registrant="registrant1",
                    period=1,
                )
            }
        )

        domain.update(domain_name="internet.nz", add_admins=["contact-admin"])

        _, kwargs = domain.execute.call_args
        self.assertFalse(kwargs.get("password"), "Password should not be set when not supplied to update()")

    def test_create_renders_dns_sec_single(self) -> None:
        """domain.create() must render a single dns_sec record correctly."""
        dns_sec = DSRecordData(
            key_tag=1235,
            algorithm=DNSSECAlgorithm.DSA_SHA_1.value,
            digest_type=DigestTypeEnum.SHA_1.value,
            digest="8cdb09364147aed879d12c68d615f98af5900b73",
        )
        create_params = DomainData(
            domain_name="internet.nz",
            registrant="inz-contact-3",
            dns_sec=dns_sec,
        )

        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        domain.create(create_params)

        # Access the rendered XML from the call to epp_communicator.execute
        xml_command = epp_communicator.execute.call_args[0][0]
        self.assertIn("<secDNS:keyTag>1235</secDNS:keyTag>", xml_command)
        self.assertIn("<secDNS:alg>3</secDNS:alg>", xml_command)
        self.assertEqual(xml_command.count("<secDNS:dsData>"), 1)

    def test_create_renders_dns_sec_list(self) -> None:
        """domain.create() must render a list of dns_sec records correctly."""
        dns_sec = [
            DSRecordData(
                key_tag=1235,
                algorithm=DNSSECAlgorithm.DSA_SHA_1.value,
                digest_type=DigestTypeEnum.SHA_1.value,
                digest="digest1",
            ),
            DSRecordData(
                key_tag=5678,
                algorithm=DNSSECAlgorithm.RSA_SHA_256.value,
                digest_type=DigestTypeEnum.SHA_256.value,
                digest="digest2",
            )
        ]
        create_params = DomainData(
            domain_name="internet.nz",
            registrant="inz-contact-3",
            dns_sec=dns_sec,
        )

        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        domain.create(create_params)

        # Access the rendered XML from the call to epp_communicator.execute
        xml_command = epp_communicator.execute.call_args[0][0]
        self.assertIn("<secDNS:keyTag>1235</secDNS:keyTag>", xml_command)
        self.assertIn("<secDNS:keyTag>5678</secDNS:keyTag>", xml_command)
        self.assertEqual(xml_command.count("<secDNS:dsData>"), 2)

    def test_create_with_explicit_password(self) -> None:
        """domain.create() must use the explicit password when provided."""
        create_params = DomainData(
            domain_name="internet.nz",
            registrant="inz-contact-3",
            password="MyExplicitPassword"
        )

        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        domain.execute = MagicMock(return_value=EppResultData(
            code=1000, message="Command completed successfully", raw_response="", result_data=None
        ))

        domain.create(create_params)

        _, kwargs = domain.execute.call_args
        self.assertEqual(kwargs["password"], "MyExplicitPassword")

    def test_info_without_dns_sec(self) -> None:
        """domain.info() must handle response when no <secDNS:infData> node is present."""
        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        execute_result = EppResultData(
            **{
                "client_transaction_id": None,
                "code": 1000,
                "message": "Command completed successfully",
                "raw_response": "<response>\n"
                '<result code="1000">\n'
                "<msg>Command completed successfully</msg>\n"
                "</result>\n"
                "<resData>\n"
                "<domain:infData>\n"
                "<domain:name>internet.nz</domain:name>\n"
                "<domain:roid>9204701-INZ</domain:roid>\n"
                '<domain:status s="inactive"/>\n'
                "<domain:registrant>inz-contact-1</domain:registrant>\n"
                "<domain:contact "
                'type="admin">inz-contact-1</domain:contact>\n'
                "<domain:contact "
                'type="tech">inz-contact-1</domain:contact>\n'
                "<domain:clID>933</domain:clID>\n"
                "<domain:crID>933</domain:crID>\n"
                "<domain:crDate>2023-02-23T21:56:22.713Z</domain:crDate>\n"
                "<domain:upID>CIRA_RAR_1</domain:upID>\n"
                "<domain:upDate>2023-02-24T21:59:27.901Z</domain:upDate>\n"
                "<domain:exDate>2024-02-23T21:56:22.713Z</domain:exDate>\n"
                "</domain:infData>\n"
                "</resData>\n"
                "<trID>\n"
                "<svTRID>CIRA-000063163743-0000000003</svTRID>\n"
                "</trID>\n"
                "</response>",
                "reason": None,
                "repository_object_id": "9204701-INZ",
                "server_transaction_id": "CIRA-000063163743-0000000003",
                "result_data": None,
            }
        )

        domain.execute = MagicMock(return_value=execute_result)
        result = domain.info("internet.nz")
        self.assertIsNone(result.result_data.dns_sec)

    def test_domain_update_with_statuses(self) -> None:
        """domain.update() correctly accepts add_statuses and remove_statuses."""
        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        domain.execute = MagicMock(return_value=MagicMock())

        domain.update(
            domain_name="example.com",
            add_statuses=[("clientHold", "Reason")],
            remove_statuses=["clientUpdateProhibited"],
        )

        domain.execute.assert_called_once()
        call_kwargs = domain.execute.call_args.kwargs
        self.assertEqual(call_kwargs["add_statuses"], [("clientHold", "Reason")])
        self.assertEqual(call_kwargs["remove_statuses"], ["clientUpdateProhibited"])
        self.assertTrue(call_kwargs["add"])
        self.assertTrue(call_kwargs["remove"])

    def test_domain_data_create_client_id(self) -> None:
        """DomainData create_client_id field."""
        data = DomainData(domain_name="example.com", create_client_id="client123")
        self.assertEqual(data.create_client_id, "client123")

    def test_info_domain_under_other_registrar_missing_optional_fields(self) -> None:
        """domain.info() must handle response when domain is under another registrar (e.g. no registrant)."""
        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        xml_response = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<epp xmlns="urn:ietf:params:xml:ns:epp-1.0"\n'
            '     xmlns:domain="urn:ietf:params:xml:ns:domain-1.0">\n'
            "    <response>\n"
            '        <result code="1000">\n'
            "            <msg>Command completed successfully</msg>\n"
            "        </result>\n"
            "        <resData>\n"
            "            <domain:infData>\n"
            "                <domain:name>97-dl-domain.nz</domain:name>\n"
            "                <domain:roid>125526-INZ</domain:roid>\n"
            '                <domain:status s="serverDeleteProhibited"/>\n'
            '                <domain:status s="serverTransferProhibited"/>\n'
            '                <domain:status s="serverUpdateProhibited"/>\n'
            "                <domain:ns>\n"
            "                    <domain:hostObj>ns1.97-dl-domain.nz</domain:hostObj>\n"
            "                    <domain:hostObj>ns2.97-dl-domain.nz</domain:hostObj>\n"
            "                    <domain:hostObj>ns3.97-dl-domain.nz</domain:hostObj>\n"
            "                </domain:ns>\n"
            "                <domain:clID>933</domain:clID>\n"
            "                <domain:crDate>2026-07-09T03:23:09.226Z</domain:crDate>\n"
            "                <domain:upDate>2026-10-28T02:19:40.756Z</domain:upDate>\n"
            "                <domain:exDate>2027-07-09T03:23:09.226Z</domain:exDate>\n"
            "            </domain:infData>\n"
            "        </resData>\n"
            "        <trID>\n"
            "            <clTRID>e2bba9f9-49a2-4fea-82d3-594b26b5a571</clTRID>\n"
            "            <svTRID>CIRA-000216281301-0000000002</svTRID>\n"
            "        </trID>\n"
            "    </response>\n"
            "</epp>"
        )
        execute_result = EppResultData(
            client_transaction_id=None,
            code=1000,
            message="Command completed successfully",
            raw_response=xml_response,
            result_data=None,
        )
        domain.execute = MagicMock(return_value=execute_result)

        result = domain.info("97-dl-domain.nz")
        self.assertEqual(result.result_data.domain_name, "97-dl-domain.nz")
        self.assertIsNone(result.result_data.registrant)
        self.assertIsNone(result.result_data.admin)
        self.assertIsNone(result.result_data.tech)
        self.assertIsNone(result.result_data.billing)
        self.assertEqual(result.result_data.sponsoring_client_id, "933")
        self.assertEqual(
            result.result_data.host,
            [
                "ns1.97-dl-domain.nz",
                "ns2.97-dl-domain.nz",
                "ns3.97-dl-domain.nz",
            ],
        )
        self.assertEqual(
            result.result_data.status,
            [
                "serverDeleteProhibited",
                "serverTransferProhibited",
                "serverUpdateProhibited",
            ],
        )
        self.assertEqual(result.result_data.create_date, "2026-07-09T03:23:09.226Z")
        self.assertEqual(result.result_data.update_date, "2026-10-28T02:19:40.756Z")
        self.assertEqual(result.result_data.expiry_date, "2027-07-09T03:23:09.226Z")

    def test_domain_update_add_dns_sec_single(self) -> None:
        """domain.update() correctly renders add_dns_sec with a single record and key data."""
        dns_sec = DSRecordData(
            key_tag=1235,
            algorithm=DNSSECAlgorithm.DSA_SHA_1,
            digest_type=DigestTypeEnum.SHA_1,
            digest="8cdb09364147aed879d12c68d615f98af5900b73",
            dns_key=DSRecordKeyData(
                flag="257",
                algorithm=DNSSECAlgorithm.DSA_SHA_1,
                public_key="AwEAAc0x...",
            ),
        )

        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        domain.update("internet.nz", add_dns_sec=dns_sec)

        xml_command = epp_communicator.execute.call_args[0][0]
        self.assertIn('<secDNS:update xmlns:secDNS="urn:ietf:params:xml:ns:secDNS-1.1">', xml_command)
        self.assertIn("<secDNS:add>", xml_command)
        self.assertIn("<secDNS:keyTag>1235</secDNS:keyTag>", xml_command)
        self.assertIn("<secDNS:alg>3</secDNS:alg>", xml_command)
        self.assertIn("<secDNS:digestType>1</secDNS:digestType>", xml_command)
        self.assertIn("<secDNS:digest>8cdb09364147aed879d12c68d615f98af5900b73</secDNS:digest>", xml_command)
        self.assertIn("<secDNS:keyData>", xml_command)
        self.assertIn("<secDNS:flags>257</secDNS:flags>", xml_command)
        self.assertIn("<secDNS:pubKey>AwEAAc0x...</secDNS:pubKey>", xml_command)
        self.assertNotIn("<secDNS:rem>", xml_command)

    def test_domain_update_add_dns_sec_list(self) -> None:
        """domain.update() correctly renders a list of records in add_dns_sec."""
        dns_sec_list = [
            DSRecordData(
                key_tag=1001,
                algorithm=8,
                digest_type=2,
                digest="digest1001",
            ),
            DSRecordData(
                key_tag=1002,
                algorithm=13,
                digest_type=2,
                digest="digest1002",
            ),
        ]

        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        domain.update("internet.nz", add_dns_sec=dns_sec_list)

        xml_command = epp_communicator.execute.call_args[0][0]
        self.assertIn("<secDNS:keyTag>1001</secDNS:keyTag>", xml_command)
        self.assertIn("<secDNS:keyTag>1002</secDNS:keyTag>", xml_command)
        self.assertEqual(xml_command.count("<secDNS:dsData>"), 2)

    def test_domain_update_remove_dns_sec_single(self) -> None:
        """domain.update() correctly renders remove_dns_sec with a single record."""
        ds_to_remove = DSRecordData(
            key_tag=1235,
            algorithm=DNSSECAlgorithm.DSA_SHA_1.value,
            digest_type=DigestTypeEnum.SHA_1.value,
            digest="olddigest",
        )

        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        domain.update("internet.nz", remove_dns_sec=ds_to_remove)

        xml_command = epp_communicator.execute.call_args[0][0]
        self.assertIn("<secDNS:rem>", xml_command)
        self.assertIn("<secDNS:keyTag>1235</secDNS:keyTag>", xml_command)
        self.assertIn("<secDNS:digest>olddigest</secDNS:digest>", xml_command)
        self.assertNotIn("<secDNS:add>", xml_command)
        self.assertNotIn("<secDNS:all>", xml_command)

    def test_domain_update_remove_dns_sec_list(self) -> None:
        """domain.update() correctly renders remove_dns_sec with a list of records."""
        ds_list = [
            DSRecordData(key_tag=2001, algorithm=8, digest_type=1, digest="d2001"),
            DSRecordData(key_tag=2002, algorithm=8, digest_type=1, digest="d2002"),
        ]

        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        domain.update("internet.nz", remove_dns_sec=ds_list)

        xml_command = epp_communicator.execute.call_args[0][0]
        self.assertIn("<secDNS:rem>", xml_command)
        self.assertIn("<secDNS:keyTag>2001</secDNS:keyTag>", xml_command)
        self.assertIn("<secDNS:keyTag>2002</secDNS:keyTag>", xml_command)

    def test_domain_update_remove_all_dns_sec(self) -> None:
        """domain.update() correctly renders remove_all_dns_sec as <secDNS:all>true</secDNS:all>."""
        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        domain.update("internet.nz", remove_all_dns_sec=True)

        xml_command = epp_communicator.execute.call_args[0][0]
        self.assertIn("<secDNS:rem>", xml_command)
        self.assertIn("<secDNS:all>true</secDNS:all>", xml_command)
        self.assertNotIn("<secDNS:dsData>", xml_command)
        self.assertNotIn("<secDNS:add>", xml_command)

    def test_domain_update_both_remove_and_add_dns_sec_schema_order(self) -> None:
        """RFC 5910 §4.2: <secDNS:rem> MUST appear before <secDNS:add> in <secDNS:update>."""
        rem_ds = DSRecordData(key_tag=1111, algorithm=8, digest_type=1, digest="d1111")
        add_ds = DSRecordData(key_tag=2222, algorithm=13, digest_type=2, digest="d2222")

        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        domain.update("internet.nz", remove_dns_sec=rem_ds, add_dns_sec=add_ds)

        xml_command = epp_communicator.execute.call_args[0][0]
        rem_index = xml_command.find("<secDNS:rem>")
        add_index = xml_command.find("<secDNS:add>")
        self.assertNotEqual(rem_index, -1, "<secDNS:rem> must be present")
        self.assertNotEqual(add_index, -1, "<secDNS:add> must be present")
        self.assertLess(rem_index, add_index, "<secDNS:rem> must appear before <secDNS:add>")

    def test_domain_update_conflict_remove_and_remove_all_raises(self) -> None:
        """domain.update() must raise ValueError if both remove_dns_sec and remove_all_dns_sec are provided."""
        ds = DSRecordData(key_tag=1235, algorithm=3, digest_type=1, digest="d")
        domain = Domain(MagicMock(EppCommunicator))

        with self.assertRaises(ValueError) as ctx:
            domain.update("internet.nz", remove_dns_sec=ds, remove_all_dns_sec=True)

        self.assertIn("Cannot specify both remove_dns_sec and remove_all_dns_sec", str(ctx.exception))

    def test_domain_update_dns_sec_only_omits_domain_subelements(self) -> None:
        """When only DNSSEC is updated, <domain:add>, <domain:rem>, and <domain:chg> must not be rendered."""
        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        domain.update("internet.nz", remove_all_dns_sec=True)

        xml_command = epp_communicator.execute.call_args[0][0]
        self.assertIn("<domain:name>internet.nz</domain:name>", xml_command)
        self.assertNotIn("<domain:add>", xml_command)
        self.assertNotIn("<domain:rem>", xml_command)
        self.assertNotIn("<domain:chg>", xml_command)

    def test_normalize_ds_records_invalid_type_raises(self) -> None:
        """_normalize_ds_records must raise TypeError when an invalid item type is passed."""
        domain = Domain(MagicMock(EppCommunicator))
        with self.assertRaises(TypeError) as ctx:
            domain.update("internet.nz", add_dns_sec="invalid_string")  # type: ignore

        self.assertIn("Expected DSRecordData or dict", str(ctx.exception))

    def test_create_renders_dns_sec_with_key_data_and_enums(self) -> None:
        """domain.create() must render nested DSRecordKeyData and unpack DNSKeyFlagEnum."""
        dns_sec = DSRecordData(
            key_tag=1235,
            algorithm=DNSSECAlgorithm.RSA_SHA_256,
            digest_type=DigestTypeEnum.SHA_256,
            digest="8cdb09364147aed879d12c68d615f98af5900b73",
            dns_key=DSRecordKeyData(
                flag=DNSKeyFlagEnum.FLAG_257,
                algorithm=DNSSECAlgorithm.RSA_SHA_256,
                public_key="AwEAAc0x...",
            ),
        )
        create_params = DomainData(
            domain_name="internet.nz",
            registrant="inz-contact-3",
            dns_sec=dns_sec,
        )

        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)
        domain.create(create_params)

        xml_command = epp_communicator.execute.call_args[0][0]
        self.assertIn("<secDNS:keyTag>1235</secDNS:keyTag>", xml_command)
        self.assertIn("<secDNS:alg>8</secDNS:alg>", xml_command)
        self.assertIn("<secDNS:digestType>2</secDNS:digestType>", xml_command)
        self.assertIn("<secDNS:keyData>", xml_command)
        self.assertIn("<secDNS:flags>257</secDNS:flags>", xml_command)
        self.assertIn("<secDNS:protocol>3</secDNS:protocol>", xml_command)
        self.assertIn("<secDNS:pubKey>AwEAAc0x...</secDNS:pubKey>", xml_command)

    def test_normalize_ds_records_dict_with_dataclass_dns_key_and_invalid_dns_key(self) -> None:
        """_normalize_ds_records handles dict with DSRecordKeyData and rejects invalid dns_key types."""
        normalized = Domain._normalize_ds_records(
            {
                "key_tag": 1235,
                "algorithm": DNSSECAlgorithm.DSA_SHA_1,
                "digest_type": DigestTypeEnum.SHA_1,
                "digest": "abc",
                "dns_key": DSRecordKeyData(
                    flag=DNSKeyFlagEnum.FLAG_256,
                    algorithm=DNSSECAlgorithm.DSA_SHA_1,
                    public_key="pub",
                ),
            }
        )
        self.assertEqual(
            normalized,
            [
                {
                    "key_tag": 1235,
                    "algorithm": 3,
                    "digest_type": 1,
                    "digest": "abc",
                    "dns_key": {
                        "flag": 256,
                        "algorithm": 3,
                        "public_key": "pub",
                        "protocol": 3,
                    },
                }
            ],
        )

        with self.assertRaises(TypeError) as ctx:
            Domain._normalize_ds_records(
                {
                    "key_tag": 1235,
                    "algorithm": 3,
                    "digest_type": 1,
                    "digest": "abc",
                    "dns_key": "invalid_key_type",
                }
            )
        self.assertIn("Expected DSRecordKeyData or dict for dns_key", str(ctx.exception))

    def test_dnssec_enums_are_int_enums(self) -> None:
        """Verify DNSSECAlgorithm, DigestTypeEnum, and DNSKeyFlagEnum are IntEnums."""
        self.assertTrue(issubclass(DNSSECAlgorithm, IntEnum))
        self.assertTrue(issubclass(DNSSECAlgorithm, Enum))
        self.assertTrue(issubclass(DigestTypeEnum, IntEnum))
        self.assertTrue(issubclass(DigestTypeEnum, Enum))
        self.assertTrue(issubclass(DNSKeyFlagEnum, IntEnum))
        self.assertTrue(issubclass(DNSKeyFlagEnum, Enum))

        # Direct integer equality and casting
        self.assertEqual(DNSSECAlgorithm.ECDSA_CURVE_P_256_WITH_SHA_256, 13)
        self.assertEqual(int(DNSSECAlgorithm.ECDSA_CURVE_P_256_WITH_SHA_256), 13)
        self.assertEqual(DigestTypeEnum.SHA_256, 2)
        self.assertEqual(int(DigestTypeEnum.SHA_256), 2)
        self.assertEqual(DNSKeyFlagEnum.FLAG_257, 257)
        self.assertEqual(int(DNSKeyFlagEnum.FLAG_257), 257)

        # String representations (RFC 4034, Python 3.10+ PEP 663 compatibility)
        self.assertEqual(str(DNSSECAlgorithm.DSA_SHA_1), "3")
        self.assertEqual(str(DNSSECAlgorithm.ECDSA_CURVE_P_256_WITH_SHA_256), "13")
        self.assertEqual(str(DigestTypeEnum.SHA_256), "2")
        self.assertEqual(str(DNSKeyFlagEnum.FLAG_257), "257")

    def test_ds_record_data_and_key_data_dict_compatibility(self) -> None:
        """Verify DSRecordKeyData and DSRecordData support dict-like indexing and .get()."""
        key = DSRecordKeyData(
            flag=DNSKeyFlagEnum.FLAG_257,
            algorithm=DNSSECAlgorithm.ECDSA_CURVE_P_256_WITH_SHA_256,
            public_key="pubkey_base64",
            protocol=3,
        )
        # Attribute access
        self.assertEqual(key.flag, 257)
        self.assertEqual(key.algorithm, 13)
        self.assertEqual(key.public_key, "pubkey_base64")
        self.assertEqual(key.protocol, 3)

        # Dict indexing
        self.assertEqual(key["flag"], 257)
        self.assertEqual(key["algorithm"], 13)
        self.assertEqual(key["public_key"], "pubkey_base64")
        self.assertEqual(key["protocol"], 3)
        with self.assertRaises(KeyError):
            _ = key["non_existent"]

        # Dict get and membership
        self.assertEqual(key.get("flag"), 257)
        self.assertEqual(key.get("non_existent", "default_val"), "default_val")
        self.assertIn("flag", key)
        self.assertNotIn("non_existent", key)
        self.assertIn("public_key", key.keys())

        # Rejection of non-string keys
        self.assertNotIn(0, key)
        self.assertEqual(key.get(0, "default_val"), "default_val")
        with self.assertRaises(KeyError):
            _ = key[0]

        # Prevention of method/dunder leakage
        self.assertNotIn("keys", key)
        self.assertNotIn("get", key)
        self.assertNotIn("__getitem__", key)
        self.assertIsNone(key.get("keys"))
        with self.assertRaises(KeyError):
            _ = key["keys"]

        ds = DSRecordData(
            key_tag=17600,
            algorithm=DNSSECAlgorithm.ECDSA_CURVE_P_256_WITH_SHA_256,
            digest_type=DigestTypeEnum.SHA_1,
            digest="4ffb0f3f0fb5edbaa0067d1cd94bb545249cfea2",
            dns_key=key,
        )
        # Attribute access
        self.assertEqual(ds.key_tag, 17600)
        self.assertEqual(ds.algorithm, 13)
        self.assertEqual(ds.digest_type, 1)
        self.assertEqual(ds.digest, "4ffb0f3f0fb5edbaa0067d1cd94bb545249cfea2")
        self.assertEqual(ds.dns_key, key)

        # Dict indexing
        self.assertEqual(ds["key_tag"], 17600)
        self.assertEqual(ds["algorithm"], 13)
        self.assertEqual(ds["digest_type"], 1)
        self.assertEqual(ds["digest"], "4ffb0f3f0fb5edbaa0067d1cd94bb545249cfea2")
        self.assertEqual(ds["dns_key"], key)
        with self.assertRaises(KeyError):
            _ = ds["non_existent"]

        # Dict get and membership
        self.assertEqual(ds.get("key_tag"), 17600)
        self.assertEqual(ds.get("non_existent", "default_val"), "default_val")
        self.assertIn("key_tag", ds)
        self.assertNotIn("non_existent", ds)
        self.assertIn("digest", ds.keys())

        # Rejection of non-string keys
        self.assertNotIn(0, ds)
        self.assertEqual(ds.get(0, "default_val"), "default_val")
        with self.assertRaises(KeyError):
            _ = ds[0]

        # Prevention of method/dunder leakage
        self.assertNotIn("keys", ds)
        self.assertNotIn("get", ds)
        self.assertNotIn("__getitem__", ds)
        self.assertIsNone(ds.get("keys"))
        with self.assertRaises(KeyError):
            _ = ds["keys"]

    def test_domain_info_create_round_trip(self) -> None:
        """Verify DomainData from domain.info() with DNSSEC can be passed to create() and update()."""
        epp_communicator = MagicMock(EppCommunicator)
        domain = Domain(epp_communicator)

        xml = (
            '<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">'
            '<response><resData>'
            '<domain:infData xmlns:domain="urn:ietf:params:xml:ns:domain-1.0">'
            '<domain:name>roundtrip.nz</domain:name>'
            '<domain:status s="ok"/>'
            '<domain:clID>ClientA</domain:clID>'
            '</domain:infData>'
            '</resData>'
            '<extension>'
            '<secDNS:infData xmlns:secDNS="urn:ietf:params:xml:ns:secDNS-1.1">'
            '<secDNS:dsData>'
            '<secDNS:keyTag>12345</secDNS:keyTag>'
            '<secDNS:alg>13</secDNS:alg>'
            '<secDNS:digestType>2</secDNS:digestType>'
            '<secDNS:digest>ABCDEF0123456789</secDNS:digest>'
            '<secDNS:keyData>'
            '<secDNS:flags>257</secDNS:flags>'
            '<secDNS:protocol>3</secDNS:protocol>'
            '<secDNS:alg>13</secDNS:alg>'
            '<secDNS:pubKey>pubkey123</secDNS:pubKey>'
            '</secDNS:keyData>'
            '</secDNS:dsData>'
            '</secDNS:infData>'
            '</extension>'
            '</response></epp>'
        )
        info_mock_result = EppResultData(
            code=1000,
            message="Command completed successfully",
            reason=None,
            raw_response=xml,
            result_data=None,
            dry_run=False,
            parsed_xml=BeautifulSoup(xml, "xml"),
        )
        epp_communicator.execute.return_value = info_mock_result
        info_res = domain.info("roundtrip.nz")
        domain_data = info_res.result_data

        # Verify parsed types
        ds_rec = domain_data.dns_sec[0]
        self.assertIsInstance(ds_rec.algorithm, DNSSECAlgorithm)
        self.assertIsInstance(ds_rec.digest_type, DigestTypeEnum)
        self.assertIsInstance(ds_rec.dns_key, DSRecordKeyData)
        self.assertIsInstance(ds_rec.dns_key.flag, DNSKeyFlagEnum)
        self.assertIsInstance(ds_rec.dns_key.algorithm, DNSSECAlgorithm)

        # Re-use DomainData in domain.create()
        success_result = EppResultData(
            code=1000,
            message="Command completed successfully",
            reason=None,
            raw_response="<ok/>",
            result_data=None,
        )
        epp_communicator.execute.return_value = success_result
        domain.create(domain_data)

        create_xml = epp_communicator.execute.call_args[0][0]
        self.assertIn("<secDNS:keyTag>12345</secDNS:keyTag>", create_xml)
        self.assertIn("<secDNS:alg>13</secDNS:alg>", create_xml)
        self.assertIn("<secDNS:digestType>2</secDNS:digestType>", create_xml)
        self.assertIn("<secDNS:flags>257</secDNS:flags>", create_xml)
        self.assertIn("<secDNS:protocol>3</secDNS:protocol>", create_xml)
        self.assertIn("<secDNS:pubKey>pubkey123</secDNS:pubKey>", create_xml)
        self.assertNotIn("DNSSECAlgorithm", create_xml)
        self.assertNotIn("DigestTypeEnum", create_xml)
        self.assertNotIn("DNSKeyFlagEnum", create_xml)

        # Re-use in domain.update()
        domain.update("roundtrip.nz", add_dns_sec=domain_data.dns_sec)
        update_xml = epp_communicator.execute.call_args[0][0]
        self.assertIn("<secDNS:keyTag>12345</secDNS:keyTag>", update_xml)
        self.assertIn("<secDNS:alg>13</secDNS:alg>", update_xml)
        self.assertIn("<secDNS:digestType>2</secDNS:digestType>", update_xml)
        self.assertNotIn("DNSSECAlgorithm", update_xml)

    def test_parse_dnssec_fallbacks_for_unknown_and_non_integer_values(self) -> None:
        """Verify _parse_ds_key_data, _parse_ds_record, and _parse_dnssec_extension handle edge cases and fallbacks."""
        # Non-existent keyData
        self.assertIsNone(Domain._parse_ds_key_data(None))

        # Direct test of _parse_int_or_enum helper
        self.assertIsNone(Domain._parse_int_or_enum(None))
        self.assertEqual(Domain._parse_int_or_enum(None, default=3), 3)

        empty_el = BeautifulSoup("<el></el>", "xml").find("el")
        self.assertIsNone(Domain._parse_int_or_enum(empty_el))

        ws_el = BeautifulSoup("<el>   </el>", "xml").find("el")
        self.assertIsNone(Domain._parse_int_or_enum(ws_el))

        padded_el = BeautifulSoup("<el>  13  </el>", "xml").find("el")
        self.assertEqual(
            Domain._parse_int_or_enum(padded_el, enum_cls=DNSSECAlgorithm),
            DNSSECAlgorithm.ECDSA_CURVE_P_256_WITH_SHA_256,
        )

        # Unknown enum and non-digit fallbacks in keyData
        key_xml = BeautifulSoup(
            "<keyData><flags>999</flags><protocol>4</protocol><alg>999</alg><pubKey>pub</pubKey></keyData>",
            "xml",
        ).find("keyData")
        k_unknown = Domain._parse_ds_key_data(key_xml)
        self.assertEqual(k_unknown.flag, 999)
        self.assertEqual(k_unknown.protocol, 4)
        self.assertEqual(k_unknown.algorithm, 999)

        key_non_digit_xml = BeautifulSoup(
            "<keyData><flags>flag_str</flags><protocol>proto_str</protocol><alg>alg_str</alg></keyData>",
            "xml",
        ).find("keyData")
        k_non_digit = Domain._parse_ds_key_data(key_non_digit_xml)
        self.assertEqual(k_non_digit.flag, "flag_str")
        self.assertEqual(k_non_digit.protocol, "proto_str")
        self.assertEqual(k_non_digit.algorithm, "alg_str")
        self.assertIsNone(k_non_digit.public_key)

        # Non-digit and unknown fallbacks in dsData
        ds_non_digit_xml = BeautifulSoup(
            "<dsData><keyTag>tag_str</keyTag><alg>alg_str</alg><digestType>type_str</digestType></dsData>",
            "xml",
        ).find("dsData")
        ds_non_digit = Domain._parse_ds_record(ds_non_digit_xml)
        self.assertEqual(ds_non_digit.key_tag, "tag_str")
        self.assertEqual(ds_non_digit.algorithm, "alg_str")
        self.assertEqual(ds_non_digit.digest_type, "type_str")

        ds_unknown_xml = BeautifulSoup(
            "<dsData><keyTag>123</keyTag><alg>999</alg><digestType>99</digestType></dsData>",
            "xml",
        ).find("dsData")
        ds_unknown = Domain._parse_ds_record(ds_unknown_xml)
        self.assertEqual(ds_unknown.key_tag, 123)
        self.assertEqual(ds_unknown.algorithm, 999)
        self.assertEqual(ds_unknown.digest_type, 99)

        # Empty extension returns None
        empty_resp = BeautifulSoup("<response><resData/></response>", "xml")
        self.assertIsNone(Domain._parse_dnssec_extension(empty_resp))

    def test_domain_info_multiple_contacts(self) -> None:
        """Verify domain.info() preserves multiple admin, tech, and billing contacts per RFC 5731 §3.1.2."""
        raw_xml = (
            "<response>\n"
            '  <result code="1000">\n'
            "    <msg>Command completed successfully</msg>\n"
            "  </result>\n"
            "  <resData>\n"
            "    <domain:infData>\n"
            "      <domain:name>multi-contact.nz</domain:name>\n"
            "      <domain:roid>12345-INZ</domain:roid>\n"
            '      <domain:status s="ok"/>\n'
            "      <domain:registrant>reg-contact-1</domain:registrant>\n"
            '      <domain:contact type="admin">admin-contact-1</domain:contact>\n'
            '      <domain:contact type="admin">admin-contact-2</domain:contact>\n'
            '      <domain:contact type="tech">tech-contact-1</domain:contact>\n'
            '      <domain:contact type="tech">tech-contact-2</domain:contact>\n'
            '      <domain:contact type="billing">billing-contact-1</domain:contact>\n'
            '      <domain:contact type="billing">billing-contact-2</domain:contact>\n'
            "      <domain:clID>client-1</domain:clID>\n"
            "    </domain:infData>\n"
            "  </resData>\n"
            "</response>"
        )
        execute_result = EppResultData(
            code=1000,
            message="Command completed successfully",
            raw_response=raw_xml,
            result_data=None,
        )
        domain = Domain(MagicMock(EppCommunicator))
        domain.execute = MagicMock(return_value=execute_result)

        result = domain.info("multi-contact.nz")
        self.assertEqual(
            result.result_data.admin, ["admin-contact-1", "admin-contact-2"]
        )
        self.assertEqual(
            result.result_data.tech, ["tech-contact-1", "tech-contact-2"]
        )
        self.assertEqual(
            result.result_data.billing,
            ["billing-contact-1", "billing-contact-2"],
        )

    def test_domain_create_multiple_contacts_xml(self) -> None:
        """Verify domain.create() renders multiple contacts without Python list reprs."""
        epp = EppCommunicator(
            "localhost",
            "700",
            user="user",
            password="pw",
            dry_run=True,
        )
        domain = Domain(epp)
        domain_data = DomainData(
            domain_name="example.nz",
            registrant="reg-1",
            admin=["admin-1", "admin-2"],
            tech=["tech-1", "tech-2"],
            billing=["bill-1", "bill-2"],
            period=1,
            password="testpassword123",
        )
        result = domain.create(domain_data)
        xml = result.raw_response
        self.assertIn('<domain:contact type="admin">admin-1</domain:contact>', xml)
        self.assertIn('<domain:contact type="admin">admin-2</domain:contact>', xml)
        self.assertIn('<domain:contact type="tech">tech-1</domain:contact>', xml)
        self.assertIn('<domain:contact type="tech">tech-2</domain:contact>', xml)
        self.assertIn('<domain:contact type="billing">bill-1</domain:contact>', xml)
        self.assertIn('<domain:contact type="billing">bill-2</domain:contact>', xml)
        self.assertNotIn("['admin-1'", xml)
        self.assertNotIn("['bill-1'", xml)

    def test_domain_create_string_contacts_xml(self) -> None:
        """Verify domain.create() renders single contact string values cleanly."""
        epp = EppCommunicator(
            "localhost",
            "700",
            user="user",
            password="pw",
            dry_run=True,
        )
        domain = Domain(epp)
        domain_data = DomainData(
            domain_name="single.nz",
            registrant="reg-1",
            admin="admin-single",
            tech="tech-single",
            billing="bill-single",
            period=1,
            password="testpassword123",
        )
        result = domain.create(domain_data)
        xml = result.raw_response
        self.assertIn('<domain:contact type="admin">admin-single</domain:contact>', xml)
        self.assertIn('<domain:contact type="tech">tech-single</domain:contact>', xml)
        self.assertIn('<domain:contact type="billing">bill-single</domain:contact>', xml)
        self.assertNotIn("['", xml)

    def test_domain_info_to_create_round_trip(self) -> None:
        """Verify DomainData returned by info() can be passed directly to create() without schema errors."""
        info_xml = (
            "<response>\n"
            '  <result code="1000">\n'
            "    <msg>Command completed successfully</msg>\n"
            "  </result>\n"
            "  <resData>\n"
            "    <domain:infData>\n"
            "      <domain:name>roundtrip.nz</domain:name>\n"
            "      <domain:roid>99999-INZ</domain:roid>\n"
            '      <domain:status s="ok"/>\n'
            "      <domain:registrant>reg-contact-1</domain:registrant>\n"
            '      <domain:contact type="admin">admin-1</domain:contact>\n'
            '      <domain:contact type="tech">tech-1</domain:contact>\n'
            '      <domain:contact type="billing">billing-1</domain:contact>\n'
            "      <domain:clID>client-1</domain:clID>\n"
            "    </domain:infData>\n"
            "  </resData>\n"
            "</response>"
        )
        execute_result = EppResultData(
            code=1000,
            message="Command completed successfully",
            raw_response=info_xml,
            result_data=None,
        )
        epp = EppCommunicator(
            "localhost",
            "700",
            user="user",
            password="pw",
            dry_run=True,
        )
        domain = Domain(epp)
        domain.execute = MagicMock(return_value=execute_result)

        info_res = domain.info("roundtrip.nz")
        create_domain = Domain(epp)
        create_res = create_domain.create(info_res.result_data)
        xml = create_res.raw_response
        self.assertIn('<domain:contact type="admin">admin-1</domain:contact>', xml)
        self.assertIn('<domain:contact type="tech">tech-1</domain:contact>', xml)
        self.assertIn('<domain:contact type="billing">billing-1</domain:contact>', xml)
        self.assertNotIn("['billing-1']", xml)
        self.assertNotIn("['admin-1']", xml)
        # RFC 5731 §3.2.1: When period is None (not returned by info), <domain:period> is omitted
        self.assertNotIn("<domain:period", xml)
        self.assertNotIn("<domain:registrant>None", xml)

    def test_domain_info_empty_and_whitespace_contacts(self) -> None:
        """Verify domain.info() normalizes empty and whitespace contact tags to None."""
        info_xml = (
            "<response>\n"
            '  <result code="1000">\n'
            "    <msg>Command completed successfully</msg>\n"
            "  </result>\n"
            "  <resData>\n"
            "    <domain:infData>\n"
            "      <domain:name>empty-contacts.nz</domain:name>\n"
            '      <domain:status s="ok"/>\n'
            '      <domain:contact type="admin"></domain:contact>\n'
            '      <domain:contact type="tech">   </domain:contact>\n'
            '      <domain:contact type="billing">\n\t</domain:contact>\n'
            "    </domain:infData>\n"
            "  </resData>\n"
            "</response>"
        )
        execute_result = EppResultData(
            code=1000,
            message="Command completed successfully",
            raw_response=info_xml,
            result_data=None,
        )
        epp = MagicMock(EppCommunicator)
        domain = Domain(epp)
        domain.execute = MagicMock(return_value=execute_result)

        result = domain.info("empty-contacts.nz")
        self.assertIsNone(result.result_data.admin)
        self.assertIsNone(result.result_data.tech)
        self.assertIsNone(result.result_data.billing)

    def test_domain_update_contact_normalization(self) -> None:
        """Verify domain.update() normalizes single strings and tuples without character splitting."""
        epp = EppCommunicator(
            "localhost",
            "700",
            user="user",
            password="pw",
            dry_run=True,
        )
        domain = Domain(epp)
        result = domain.update(
            domain_name="example.nz",
            add_admins="adm-single",
            remove_techs=("tech-1", "tech-2"),
            add_billings="bill-single",
        )
        xml = result.raw_response
        self.assertIn('<domain:contact type="admin">adm-single</domain:contact>', xml)
        self.assertIn('<domain:contact type="tech">tech-1</domain:contact>', xml)
        self.assertIn('<domain:contact type="tech">tech-2</domain:contact>', xml)
        self.assertIn('<domain:contact type="billing">bill-single</domain:contact>', xml)
        # Ensure string wasn't iterated into individual characters
        self.assertNotIn('<domain:contact type="admin">a</domain:contact>', xml)
        self.assertNotIn('<domain:contact type="admin">d</domain:contact>', xml)

    def test_normalize_contact_list(self) -> None:
        """Verify Domain._normalize_contact_list handles various input shapes and types."""
        self.assertIsNone(Domain._normalize_contact_list(None))
        self.assertIsNone(Domain._normalize_contact_list(""))
        self.assertIsNone(Domain._normalize_contact_list("   "))
        self.assertIsNone(Domain._normalize_contact_list([]))
        self.assertIsNone(Domain._normalize_contact_list(["  ", ""]))
        self.assertEqual(Domain._normalize_contact_list("c1"), ["c1"])
        self.assertEqual(Domain._normalize_contact_list("  c1  "), ["c1"])
        self.assertEqual(Domain._normalize_contact_list(["c1", "c2"]), ["c1", "c2"])
        self.assertEqual(Domain._normalize_contact_list(("c1", "c2")), ["c1", "c2"])
        self.assertEqual(Domain._normalize_contact_list(["c1", "  "]), ["c1"])

        with self.assertRaises(TypeError):
            Domain._normalize_contact_list(123)  # type: ignore[arg-type]

        with self.assertRaises(TypeError):
            Domain._normalize_contact_list({"admin": "c1"})  # type: ignore[arg-type]

        with self.assertRaises(TypeError):
            Domain._normalize_contact_list({"c1", "c2"})  # type: ignore[arg-type]

        with self.assertRaises(TypeError):
            Domain._normalize_contact_list(["c1", 123])  # type: ignore[list-item]
