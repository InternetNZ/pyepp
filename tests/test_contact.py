"""
Contact unit tests
"""

import unittest
from unittest.mock import MagicMock

from pyepp.contact import (
    ContactData,
    PostalInfoData,
    PostalInfoTypeEnum,
    AddressData,
    Contact,
)
from pyepp.epp import EppCommunicator, EppResultData


class ContactTest(unittest.TestCase):
    """
    Contact unit tests
    """

    def setUp(self) -> None:
        self.maxDiff = None

    def test_data_to_dict(self) -> None:
        data = ContactData(
            id="id",
            status=["status1", "status2"],
            create_date="create_date",
            create_client_id="create_client_id",
            sponsoring_client_id="sponsoring_client_id",
            update_client_id="update_client_id",
            update_date="update_date",
            postal_info=PostalInfoData(
                name="name",
                organization="organization",
                address=AddressData(
                    street_1="street_1",
                    street_2="street_2",
                    street_3="street_3",
                    city="city",
                    province="province",
                    postal_code="postal_code",
                    country_code="country_code",
                ),
            ),
            phone="phone",
            fax="fax",
            email="email",
            password="",
        )

        expected_result = {
            "id": "id",
            "status": ["status1", "status2"],
            "create_date": "create_date",
            "create_client_id": "create_client_id",
            "sponsoring_client_id": "sponsoring_client_id",
            "update_client_id": "update_client_id",
            "update_date": "update_date",
            "name": "name",
            "organization": "organization",
            "street_1": "street_1",
            "street_2": "street_2",
            "street_3": "street_3",
            "city": "city",
            "province": "province",
            "postal_code": "postal_code",
            "country_code": "country_code",
            "phone": "phone",
            "fax": "fax",
            "email": "email",
            "password": "",
            "type": "loc",
        }

        epp_communicator = MagicMock(EppCommunicator)
        contact = Contact(epp_communicator)

        result = contact._data_to_dict(data)
        self.assertDictEqual(result, expected_result)

    def test_data_to_dict_without_postal_info(self) -> None:
        data = ContactData(
            id="id",
            email="email",
            postal_info=None,
        )

        epp_communicator = MagicMock(EppCommunicator)
        contact = Contact(epp_communicator)

        result = contact._data_to_dict(data)

        expected_result = {
            "id": "id",
            "status": None,
            "create_date": "",
            "create_client_id": "",
            "sponsoring_client_id": "",
            "update_client_id": "",
            "update_date": "",
            "phone": "",
            "fax": "",
            "email": "email",
            "password": "",
        }
        self.assertDictEqual(result, expected_result)

    def test_check_unsuccessful(self) -> None:
        epp_communicator = MagicMock(EppCommunicator)
        contact = Contact(epp_communicator)
        expected_result = EppResultData(
            **{
                "code": 2000,
                "message": "Command completed unsuccessfully",
                "reason": None,
                "raw_response": "response",
                "result_data": None,
            }
        )
        contact.execute = MagicMock(return_value=expected_result)

        result = contact.check(["contact1"])

        self.assertEqual(result, expected_result)

    def test_check(self) -> None:
        epp_communicator = MagicMock(EppCommunicator)
        contact = Contact(epp_communicator)
        expected_result = EppResultData(
            **{
                "client_transaction_id": "eccb044f-a80f-4db3-a918-988f1ac918e3",
                "code": 1000,
                "message": "Command completed successfully",
                "raw_response": "<response>\n"
                '<result code="1000">\n'
                "<msg>Command completed successfully</msg>\n"
                "</result>\n"
                "<resData>\n"
                "<contact:chkData>\n"
                "<contact:cd>\n"
                '<contact:id avail="true">contact1</contact:id>\n'
                "</contact:cd>\n"
                "</contact:chkData>\n"
                "</resData>\n"
                "<trID>\n"
                "<clTRID>eccb044f-a80f-4db3-a918-988f1ac918e3</clTRID>\n"
                "<svTRID>CIRA-000062206323-0000000003</svTRID>\n"
                "</trID>\n"
                "</response>",
                "reason": None,
                "repository_object_id": None,
                "result_data": {
                    "contact1": {"avail": True, "reason": None},
                    "contact2": {
                        "avail": False,
                        "reason": "Selected contact ID is not " "available",
                    },
                },
                "server_transaction_id": "CIRA-000062206323-0000000003",
            }
        )

        contact.execute = MagicMock(return_value=expected_result)

        result = contact.check(["contact1", "contact2"])

        self.assertEqual(result, expected_result)

    def test_info_unsuccessful(self) -> None:
        epp_communicator = MagicMock(EppCommunicator)
        contact = Contact(epp_communicator)
        expected_result = EppResultData(
            **{
                "code": 2000,
                "message": "Command completed unsuccessfully",
                "reason": None,
                "raw_response": "response",
                "result_data": None,
            }
        )
        contact.execute = MagicMock(return_value=expected_result)

        result = contact.info("contact1")

        self.assertEqual(result, expected_result)

    def test_check_dry_run(self) -> None:
        epp_communicator = MagicMock(EppCommunicator)
        contact = Contact(epp_communicator)
        expected_result = EppResultData(
            code=1000,
            message="Dry run",
            reason=None,
            raw_response="<contact:check/>",
            result_data=None,
            dry_run=True,
        )
        contact.execute = MagicMock(return_value=expected_result)
        result = contact.check(["contact1"])
        self.assertEqual(result, expected_result)

    def test_info_dry_run(self) -> None:
        epp_communicator = MagicMock(EppCommunicator)
        contact = Contact(epp_communicator)
        expected_result = EppResultData(
            code=1000,
            message="Dry run",
            reason=None,
            raw_response="<contact:info/>",
            result_data=None,
            dry_run=True,
        )
        contact.execute = MagicMock(return_value=expected_result)
        result = contact.info("contact1")
        self.assertEqual(result, expected_result)

    def test_info(self) -> None:
        epp_communicator = MagicMock(EppCommunicator)
        contact = Contact(epp_communicator)
        execute_result = EppResultData(
            **{
                "client_transaction_id": "5123c3d4-79ce-4d87-ad7b-d234eb992474",
                "code": 1000,
                "message": "Command completed successfully",
                "raw_response": "<response>\n"
                '<result code="1000">\n'
                "<msg>Command completed successfully</msg>\n"
                "</result>\n"
                "<resData>\n"
                "<contact:infData>\n"
                "<contact:id>inz-contact-1</contact:id>\n"
                "<contact:roid>9175701-INZ</contact:roid>\n"
                '<contact:status s="linked"/>\n'
                '<contact:postalInfo type="loc">\n'
                "<contact:name>inz</contact:name>\n"
                "<contact:addr>\n"
                "<contact:street>18 test street</contact:street>\n"
                "<contact:city>Wellington</contact:city>\n"
                "<contact:cc>NZ</contact:cc>\n"
                "</contact:addr>\n"
                "</contact:postalInfo>\n"
                "<contact:email>inz@internet.net.nz</contact:email>\n"
                "<contact:clID>933</contact:clID>\n"
                "<contact:crID>933</contact:crID>\n"
                "<contact:crDate>2023-02-23T02:59:16.784Z</contact:crDate>\n"
                "<contact:upID>CIRA_RAR_1</contact:upID>\n"
                "<contact:upDate>2023-02-23T21:59:01.021Z</contact:upDate>\n"
                "<contact:authInfo>\n"
                "<contact:pw>PassWord</contact:pw>\n"
                "</contact:authInfo>\n"
                "</contact:infData>\n"
                "</resData>\n"
                "<trID>\n"
                "<clTRID>5123c3d4-79ce-4d87-ad7b-d234eb992474</clTRID>\n"
                "<svTRID>CIRA-000062211375-0000000003</svTRID>\n"
                "</trID>\n"
                "</response>",
                "reason": None,
                "repository_object_id": "9175701-INZ",
                "server_transaction_id": "CIRA-000062211375-0000000003",
                "result_data": None,
            }
        )

        expected_result = EppResultData(
            **{
                "client_transaction_id": "5123c3d4-79ce-4d87-ad7b-d234eb992474",
                "code": 1000,
                "message": "Command completed successfully",
                "raw_response": "<response>\n"
                '<result code="1000">\n'
                "<msg>Command completed successfully</msg>\n"
                "</result>\n"
                "<resData>\n"
                "<contact:infData>\n"
                "<contact:id>inz-contact-1</contact:id>\n"
                "<contact:roid>9175701-INZ</contact:roid>\n"
                '<contact:status s="linked"/>\n'
                '<contact:postalInfo type="loc">\n'
                "<contact:name>inz</contact:name>\n"
                "<contact:addr>\n"
                "<contact:street>18 test street</contact:street>\n"
                "<contact:city>Wellington</contact:city>\n"
                "<contact:cc>NZ</contact:cc>\n"
                "</contact:addr>\n"
                "</contact:postalInfo>\n"
                "<contact:email>inz@internet.net.nz</contact:email>\n"
                "<contact:clID>933</contact:clID>\n"
                "<contact:crID>933</contact:crID>\n"
                "<contact:crDate>2023-02-23T02:59:16.784Z</contact:crDate>\n"
                "<contact:upID>CIRA_RAR_1</contact:upID>\n"
                "<contact:upDate>2023-02-23T21:59:01.021Z</contact:upDate>\n"
                "<contact:authInfo>\n"
                "<contact:pw>PassWord</contact:pw>\n"
                "</contact:authInfo>\n"
                "</contact:infData>\n"
                "</resData>\n"
                "<trID>\n"
                "<clTRID>5123c3d4-79ce-4d87-ad7b-d234eb992474</clTRID>\n"
                "<svTRID>CIRA-000062211375-0000000003</svTRID>\n"
                "</trID>\n"
                "</response>",
                "reason": None,
                "repository_object_id": "9175701-INZ",
                "result_data": ContactData(
                    id="inz-contact-1",
                    email="inz@internet.net.nz",
                    postal_info=PostalInfoData(
                        **{
                            "address": AddressData(
                                **{
                                    "city": "Wellington",
                                    "country_code": "NZ",
                                    "postal_code": None,
                                    "province": None,
                                    "street_1": "18 test street",
                                    "street_2": None,
                                    "street_3": None,
                                }
                            ),
                            "name": "inz",
                            "organization": None,
                        }
                    ),
                    status=[""],
                    phone=None,
                    fax=None,
                    password="PassWord",
                    create_date="2023-02-23T02:59:16.784Z",
                    create_client_id="933",
                    sponsoring_client_id="933",
                    update_client_id="CIRA_RAR_1",
                    update_date="2023-02-23T21:59:01.021Z",
                ),
                "server_transaction_id": "CIRA-000062211375-0000000003",
            }
        )

        contact.execute = MagicMock(return_value=execute_result)

        result = contact.info("inz-contact-1")

        self.assertEqual(result, expected_result)

    def test_create(self) -> None:
        expected_result = EppResultData(
            **{
                "client_transaction_id": "caae2895-fe01-4f1c-a892-115b17315acc",
                "code": 1000,
                "message": "Command completed successfully",
                "raw_response": "<response>\n"
                '<result code="1000">\n'
                "<msg>Command completed successfully</msg>\n"
                "</result>\n"
                "<resData>\n"
                "<contact:creData>\n"
                "<contact:id>inz-contact-1</contact:id>\n"
                "<contact:crDate>2023-04-26T23:06:11.894Z</contact:crDate>\n"
                "</contact:creData>\n"
                "</resData>\n"
                "<trID>\n"
                "<clTRID>caae2895-fe01-4f1c-a892-115b17315acc</clTRID>\n"
                "<svTRID>CIRA-000062214171-0000000003</svTRID>\n"
                "</trID>\n"
                "</response>",
                "reason": None,
                "repository_object_id": None,
                "server_transaction_id": "CIRA-000062214171-0000000003",
                "result_data": None,
            }
        )

        create_params = ContactData(
            id="inz-contact-1",
            email="epp@internetnz.net.nz",
            postal_info=PostalInfoData(
                name="IRS EPP",
                organization="INZ",
                address=AddressData(
                    street_1="18 test street",
                    street_2="Wellington CBD",
                    city="Wellington",
                    country_code="NZ",
                    province="Wellington",
                    postal_code="6011",
                ),
            ),
            phone="+64.111111111",
        )

        epp_communicator = MagicMock(EppCommunicator)
        contact = Contact(epp_communicator)
        contact.execute = MagicMock(return_value=expected_result)

        result = contact.create(create_params)

        self.assertEqual(result, expected_result)

    def test_delete(self) -> None:
        expected_result = EppResultData(
            **{
                "client_transaction_id": "a21a659d-5040-4848-9f5f-0cffa0ff62d1",
                "code": 1000,
                "message": "Command completed successfully",
                "raw_response": "<response>\n"
                '<result code="1000">\n'
                "<msg>Command completed successfully</msg>\n"
                "</result>\n"
                "<trID>\n"
                "<clTRID>a21a659d-5040-4848-9f5f-0cffa0ff62d1</clTRID>\n"
                "<svTRID>CIRA-000062220522-0000000004</svTRID>\n"
                "</trID>\n"
                "</response>",
                "reason": None,
                "repository_object_id": None,
                "server_transaction_id": "CIRA-000062220522-0000000004",
                "result_data": None,
            }
        )

        epp_communicator = MagicMock(EppCommunicator)
        contact = Contact(epp_communicator)
        contact.execute = MagicMock(return_value=expected_result)

        result = contact.delete("inz-contact-1")

        self.assertEqual(result, expected_result)

    def test_update(self) -> None:
        update_params = ContactData(
            id="inz-contact-1",
            email="ehsan@internetnz.net.nz",
            postal_info=PostalInfoData(name="IRS EPP2"),
        )

        expected_result = EppResultData(
            **{
                "client_transaction_id": "0e872842-b77b-4800-9572-c72e46e068de",
                "code": 1000,
                "message": "Command completed successfully",
                "raw_response": "<response>\n"
                '<result code="1000">\n'
                "<msg>Command completed successfully</msg>\n"
                "</result>\n"
                "<trID>\n"
                "<clTRID>0e872842-b77b-4800-9572-c72e46e068de</clTRID>\n"
                "<svTRID>CIRA-000062223355-0000000004</svTRID>\n"
                "</trID>\n"
                "</response>",
                "reason": None,
                "repository_object_id": None,
                "server_transaction_id": "CIRA-000062223355-0000000004",
                "result_data": None,
            }
        )

        epp_communicator = MagicMock(EppCommunicator)
        contact = Contact(epp_communicator)
        contact.execute = MagicMock(return_value=expected_result)

        result = contact.update(update_params)

        _, call_kwargs = contact.execute.call_args
        self.assertTrue(call_kwargs["postalinfo_change"])
        self.assertEqual(result, expected_result)

    def test_update_without_postal_info(self) -> None:
        """Regression test: update() must not raise AttributeError when postal_info=None."""
        update_params = ContactData(
            id="inz-contact-1",
            email="ehsan@internetnz.net.nz",
            postal_info=None,
        )

        expected_result = EppResultData(
            **{
                "client_transaction_id": "0e872842-b77b-4800-9572-c72e46e068d2",
                "code": 1000,
                "message": "Command completed successfully",
                "raw_response": "<response>\n"
                '<result code="1000">\n'
                "<msg>Command completed successfully</msg>\n"
                "</result>\n"
                "<trID>\n"
                "<clTRID>0e872842-b77b-4800-9572-c72e46e068d2</clTRID>\n"
                "<svTRID>CIRA-000062223355-0000000004</svTRID>\n"
                "</trID>\n"
                "</response>",
                "reason": None,
                "repository_object_id": None,
                "server_transaction_id": "CIRA-000062223355-0000000004",
                "result_data": None,
            }
        )

        epp_communicator = MagicMock(EppCommunicator)
        contact = Contact(epp_communicator)
        contact.execute = MagicMock(return_value=expected_result)

        result = contact.update(update_params)

        _, call_kwargs = contact.execute.call_args
        self.assertFalse(call_kwargs["postalinfo_change"])
        self.assertEqual(result, expected_result)

    def test_create_generates_password_when_not_supplied(self) -> None:
        """contact.create() must auto-generate a password when none is provided."""
        create_params = ContactData(
            id="inz-contact-1",
            email="epp@internetnz.net.nz",
            postal_info=PostalInfoData(
                name="IRS EPP",
                address=AddressData(
                    street_1="18 test street",
                    city="Wellington",
                    country_code="NZ",
                ),
            ),
        )

        epp_communicator = MagicMock(EppCommunicator)
        contact = Contact(epp_communicator)
        contact.execute = MagicMock(
            return_value=EppResultData(
                code=1000,
                message="Command completed successfully",
                raw_response="",
                result_data=None,
            )
        )

        contact.create(create_params)

        _, kwargs = contact.execute.call_args
        self.assertIn("password", kwargs)
        self.assertTrue(
            kwargs["password"], "Password should be a non-empty generated string"
        )

    def test_update_does_not_generate_password_when_not_supplied(self) -> None:
        """contact.update() must NOT generate or include a password when none is provided."""
        update_params = ContactData(
            id="inz-contact-1",
            email="epp@internetnz.net.nz",
            postal_info=PostalInfoData(name="IRS EPP2"),
        )

        epp_communicator = MagicMock(EppCommunicator)
        contact = Contact(epp_communicator)
        contact.execute = MagicMock(
            return_value=EppResultData(
                code=1000,
                message="Command completed successfully",
                raw_response="",
                result_data=None,
            )
        )

        contact.update(update_params)

        _, kwargs = contact.execute.call_args
        self.assertFalse(
            kwargs.get("password"),
            "Password should not be set when not supplied to update()",
        )

    def test_create_with_explicit_password(self) -> None:
        """contact.create() must use the explicit password when provided, not generate one."""
        create_params = ContactData(
            id="inz-contact-1",
            email="epp@internetnz.net.nz",
            postal_info=PostalInfoData(
                name="IRS EPP",
                address=AddressData(
                    street_1="Willis Street",
                    city="Wellington",
                    country_code="NZ",
                ),
            ),
            password="MyExplicitPassword123",
        )

        epp_communicator = MagicMock(EppCommunicator)
        contact = Contact(epp_communicator)
        contact.execute = MagicMock(
            return_value=EppResultData(
                code=1000,
                message="Command completed successfully",
                raw_response="",
                result_data=None,
            )
        )

        contact.create(create_params)

        _, kwargs = contact.execute.call_args
        self.assertEqual(
            kwargs["password"],
            "MyExplicitPassword123",
            "Explicit password should be used",
        )

    def test_info_without_password(self) -> None:
        """contact.info() must handle response when no <contact:pw> node is present."""
        epp_communicator = MagicMock(EppCommunicator)
        contact = Contact(epp_communicator)
        execute_result = EppResultData(
            **{
                "client_transaction_id": "5123c3d4-79ce-4d87-ad7b-d234eb992474",
                "code": 1000,
                "message": "Command completed successfully",
                "raw_response": "<response>\n"
                '<result code="1000">\n'
                "<msg>Command completed successfully</msg>\n"
                "</result>\n"
                "<resData>\n"
                "<contact:infData>\n"
                "<contact:id>inz-contact-1</contact:id>\n"
                "<contact:roid>9175701-INZ</contact:roid>\n"
                '<contact:status s="linked"/>\n'
                '<contact:postalInfo type="loc">\n'
                "<contact:name>inz</contact:name>\n"
                "<contact:addr>\n"
                "<contact:street>Test street</contact:street>\n"
                "<contact:city>Wellington</contact:city>\n"
                "<contact:cc>NZ</contact:cc>\n"
                "</contact:addr>\n"
                "</contact:postalInfo>\n"
                "<contact:email>inz@internet.net.nz</contact:email>\n"
                "<contact:clID>933</contact:clID>\n"
                "<contact:crID>933</contact:crID>\n"
                "<contact:crDate>2023-02-23T02:59:16.784Z</contact:crDate>\n"
                "<contact:upID>CIRA_RAR_1</contact:upID>\n"
                "<contact:upDate>2023-02-23T21:59:01.021Z</contact:upDate>\n"
                "</contact:infData>\n"
                "</resData>\n"
                "<trID>\n"
                "<clTRID>5123c3d4-79ce-4d87-ad7b-d234eb992474</clTRID>\n"
                "<svTRID>CIRA-000062211375-0000000003</svTRID>\n"
                "</trID>\n"
                "</response>",
                "reason": None,
                "repository_object_id": "9175701-INZ",
                "server_transaction_id": "CIRA-000062211375-0000000003",
                "result_data": None,
            }
        )

        contact.execute = MagicMock(return_value=execute_result)
        result = contact.info("inz-contact-1")
        self.assertEqual(result.result_data.password, "")

    def test_data_to_dict_with_int_type(self) -> None:
        """_data_to_dict should correctly extract type='int' from postal_info."""
        data = ContactData(
            id="id",
            postal_info=PostalInfoData(
                name="name",
                organization="organization",
                type="int",
                address=AddressData(
                    city="city",
                    country_code="country_code",
                ),
            ),
        )
        epp_communicator = MagicMock(EppCommunicator)
        contact = Contact(epp_communicator)
        result = contact._data_to_dict(data)
        self.assertEqual(result["type"], "int")

    def test_create_with_int_type(self) -> None:
        """contact.create() must pass type='int' when postal_info type is 'int'."""
        epp_communicator = MagicMock(EppCommunicator)
        contact = Contact(epp_communicator)
        contact.execute = MagicMock(
            return_value=EppResultData(
                code=1000,
                message="Command completed successfully",
                raw_response="",
                result_data=None,
            )
        )
        create_params = ContactData(
            id="test-contact",
            email="test@example.com",
            postal_info=PostalInfoData(
                name="International Contact",
                type="int",
                address=AddressData(
                    street_1="123 Int St",
                    city="Tokyo",
                    country_code="JP",
                ),
            ),
        )
        contact.create(create_params)
        _, kwargs = contact.execute.call_args
        self.assertEqual(kwargs["type"], "int")

    def test_create_xml_rendering_loc_and_int(self) -> None:
        """Verify CONTACT_CREATE_XML renders correct postalInfo type attribute."""
        epp_communicator = MagicMock(EppCommunicator)
        contact = Contact(epp_communicator)

        # Default / loc
        loc_contact = ContactData(
            id="loc-contact",
            email="loc@example.com",
            postal_info=PostalInfoData(
                name="Local Contact",
                address=AddressData(
                    city="Wellington",
                    country_code="NZ",
                ),
            ),
        )
        contact.create(loc_contact)
        loc_xml = epp_communicator.execute.call_args[0][0]
        self.assertIn('<contact:postalInfo type="loc">', loc_xml)

        # int
        int_contact = ContactData(
            id="int-contact",
            email="int@example.com",
            postal_info=PostalInfoData(
                name="International Contact",
                type="int",
                address=AddressData(
                    city="Tokyo",
                    country_code="JP",
                ),
            ),
        )
        contact.create(int_contact)
        int_xml = epp_communicator.execute.call_args[0][0]
        self.assertIn('<contact:postalInfo type="int">', int_xml)

    def test_update_xml_rendering_loc_and_int(self) -> None:
        """Verify CONTACT_UPDATE_XML renders correct postalInfo type attribute."""
        epp_communicator = MagicMock(EppCommunicator)
        contact = Contact(epp_communicator)

        # loc
        loc_contact = ContactData(
            id="loc-contact",
            postal_info=PostalInfoData(
                name="Local Contact",
                type="loc",
                address=AddressData(
                    city="Wellington",
                    country_code="NZ",
                ),
            ),
        )
        contact.update(loc_contact)
        loc_xml = epp_communicator.execute.call_args[0][0]
        self.assertIn('<contact:postalInfo type="loc">', loc_xml)
        self.assertIn('<contact:city>Wellington</contact:city>', loc_xml)
        self.assertIn('<contact:cc>NZ</contact:cc>', loc_xml)

        # int
        int_contact = ContactData(
            id="int-contact",
            postal_info=PostalInfoData(
                name="International Contact",
                type="int",
                address=AddressData(
                    city="Tokyo",
                    country_code="JP",
                ),
            ),
        )
        contact.update(int_contact)
        int_xml = epp_communicator.execute.call_args[0][0]
        self.assertIn('<contact:postalInfo type="int">', int_xml)
        self.assertIn('<contact:name>International Contact</contact:name>', int_xml)
        self.assertIn('<contact:city>Tokyo</contact:city>', int_xml)
        self.assertIn('<contact:cc>JP</contact:cc>', int_xml)

    def test_info_with_int_type(self) -> None:
        """contact.info() must parse type='int' from <contact:postalInfo> node."""
        epp_communicator = MagicMock(EppCommunicator)
        contact = Contact(epp_communicator)
        execute_result = EppResultData(
            **{
                "client_transaction_id": "5123c3d4-79ce-4d87-ad7b-d234eb992474",
                "code": 1000,
                "message": "Command completed successfully",
                "raw_response": "<response>\n"
                '<result code="1000">\n'
                "<msg>Command completed successfully</msg>\n"
                "</result>\n"
                "<resData>\n"
                "<contact:infData>\n"
                "<contact:id>inz-contact-int</contact:id>\n"
                "<contact:roid>9175701-INZ</contact:roid>\n"
                '<contact:status s="linked"/>\n'
                '<contact:postalInfo type="int">\n'
                "<contact:name>inz int</contact:name>\n"
                "<contact:addr>\n"
                "<contact:street>Test street</contact:street>\n"
                "<contact:city>Tokyo</contact:city>\n"
                "<contact:cc>JP</contact:cc>\n"
                "</contact:addr>\n"
                "</contact:postalInfo>\n"
                "<contact:email>inz@internet.net.nz</contact:email>\n"
                "<contact:clID>933</contact:clID>\n"
                "<contact:crID>933</contact:crID>\n"
                "<contact:crDate>2023-02-23T02:59:16.784Z</contact:crDate>\n"
                "</contact:infData>\n"
                "</resData>\n"
                "<trID>\n"
                "<clTRID>5123c3d4-79ce-4d87-ad7b-d234eb992474</clTRID>\n"
                "<svTRID>CIRA-000062211375-0000000003</svTRID>\n"
                "</trID>\n"
                "</response>",
                "reason": None,
                "repository_object_id": "9175701-INZ",
                "server_transaction_id": "CIRA-000062211375-0000000003",
                "result_data": None,
            }
        )
        contact.execute = MagicMock(return_value=execute_result)
        result = contact.info("inz-contact-int")
        self.assertEqual(result.result_data.postal_info.type, "int")

    def test_postal_info_type_enum(self) -> None:
        """PostalInfoData must accept PostalInfoTypeEnum values."""
        postal_loc = PostalInfoData(name="Loc Name", type=PostalInfoTypeEnum.LOC)
        self.assertEqual(postal_loc.type, "loc")

        postal_int = PostalInfoData(name="Int Name", type=PostalInfoTypeEnum.INT)
        self.assertEqual(postal_int.type, "int")

    def test_postal_info_invalid_type_raises_value_error(self) -> None:
        """PostalInfoData must raise ValueError when type is neither 'loc' nor 'int'."""
        with self.assertRaises(ValueError):
            PostalInfoData(name="Test", type="invalid")

    def test_postal_info_none_type_defaults_to_loc(self) -> None:
        """PostalInfoData must default to 'loc' when type is None."""
        postal = PostalInfoData(name="Test", type=None)
        self.assertEqual(postal.type, "loc")

    def test_data_to_dict_invalid_type_raises_value_error(self) -> None:
        """_data_to_dict must raise ValueError if type is invalid."""
        epp_communicator = MagicMock(EppCommunicator)
        contact = Contact(epp_communicator)
        data = ContactData(
            id="test-id",
            postal_info=PostalInfoData(name="Test"),
        )
        # Directly bypass dataclass __post_init__ to test _data_to_dict safeguard
        data.postal_info.type = "unsupported"
        with self.assertRaises(ValueError):
            contact._data_to_dict(data)

    def test_create_missing_postal_info_raises_value_error(self) -> None:
        """create() must raise ValueError if postal_info is missing."""
        epp_communicator = MagicMock(EppCommunicator)
        contact = Contact(epp_communicator)
        data = ContactData(id="test-id", postal_info=None)
        with self.assertRaises(ValueError):
            contact.create(data)

    def test_create_missing_name_raises_value_error(self) -> None:
        """create() must raise ValueError if postal_info name is missing."""
        epp_communicator = MagicMock(EppCommunicator)
        contact = Contact(epp_communicator)
        data = ContactData(
            id="test-id",
            postal_info=PostalInfoData(
                name="",
                address=AddressData(city="Wellington", country_code="NZ"),
            ),
        )
        with self.assertRaises(ValueError):
            contact.create(data)

    def test_create_missing_address_raises_value_error(self) -> None:
        """create() must raise ValueError if address is missing."""
        epp_communicator = MagicMock(EppCommunicator)
        contact = Contact(epp_communicator)
        data = ContactData(
            id="test-id",
            postal_info=PostalInfoData(name="Test", address=None),
        )
        with self.assertRaises(ValueError):
            contact.create(data)

    def test_create_missing_city_or_country_code_raises_value_error(self) -> None:
        """create() must raise ValueError if city or country_code is missing."""
        epp_communicator = MagicMock(EppCommunicator)
        contact = Contact(epp_communicator)
        data = ContactData(
            id="test-id",
            postal_info=PostalInfoData(
                name="Test",
                address=AddressData(city="", country_code="NZ"),
            ),
        )
        with self.assertRaises(ValueError):
            contact.create(data)

        data.postal_info.address.city = "Wellington"
        data.postal_info.address.country_code = ""
        with self.assertRaises(ValueError):
            contact.create(data)

    def test_update_int_type_missing_address_raises_value_error(self) -> None:
        """update() must raise ValueError if int postal_info lacks address."""
        epp_communicator = MagicMock(EppCommunicator)
        contact = Contact(epp_communicator)
        data = ContactData(
            id="test-id",
            postal_info=PostalInfoData(
                name="Int Name",
                type="int",
                address=None,
            ),
        )
        with self.assertRaises(ValueError):
            contact.update(data)

    def test_update_int_type_missing_name_raises_value_error(self) -> None:
        """update() must raise ValueError if int postal_info lacks name."""
        epp_communicator = MagicMock(EppCommunicator)
        contact = Contact(epp_communicator)
        data = ContactData(
            id="test-id",
            postal_info=PostalInfoData(
                name="",
                type="int",
                address=AddressData(city="Tokyo", country_code="JP"),
            ),
        )
        with self.assertRaises(ValueError):
            contact.update(data)

    def test_update_address_missing_city_or_country_code_raises_value_error(self) -> None:
        """update() must raise ValueError if address is provided without city or country_code."""
        epp_communicator = MagicMock(EppCommunicator)
        contact = Contact(epp_communicator)
        data = ContactData(
            id="test-id",
            postal_info=PostalInfoData(
                name="Name",
                type="loc",
                address=AddressData(city="", country_code="NZ"),
            ),
        )
        with self.assertRaises(ValueError):
            contact.update(data)

        data.postal_info.address.city = "Wellington"
        data.postal_info.address.country_code = ""
        with self.assertRaises(ValueError):
            contact.update(data)

    def test_update_empty_postal_info_raises_value_error(self) -> None:
        """update() must raise ValueError if postal_info has neither name, org, nor address."""
        epp_communicator = MagicMock(EppCommunicator)
        contact = Contact(epp_communicator)
        data = ContactData(
            id="test-id",
            postal_info=PostalInfoData(
                name="",
                organization="",
                address=None,
            ),
        )
        with self.assertRaises(ValueError):
            contact.update(data)

    def test_contact_data_create_client_id(self) -> None:
        """ContactData create_client_id field."""
        data = ContactData(id="contact-1", create_client_id="client123")
        self.assertEqual(data.create_client_id, "client123")
