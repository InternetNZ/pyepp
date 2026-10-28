"""
Contact Mapping Module. This module is used to manage contact objects in Registry.
"""

from enum import Enum
from typing import Literal, Optional, Union
from dataclasses import dataclass, asdict

from pyepp import helper
from pyepp.base_command import BaseCommand
from pyepp.command_templates import (
    CONTACT_CHECK_XML,
    CONTACT_INFO_XML,
    CONTACT_CREATE_XML,
    CONTACT_DELETE_XML,
    CONTACT_UPDATE_XML,
)
from pyepp.epp import EppResultCode, EppResultData


class PostalInfoTypeEnum(str, Enum):
    """Postal info type enumeration."""

    LOC = "loc"
    INT = "int"


@dataclass
class AddressData:
    """Contact address data class.

    Street fields (`street_1`, `street_2`, `street_3`) default to `None`, meaning they
    are omitted from the update XML payload (standard RFC 5733 replacement behavior).
    Passing an empty string `""` explicitly renders an empty `<contact:street></contact:street>`
    element in `<contact:update>`, which clears secondary street lines in registries that
    require explicit blank tags (such as CentralNic).

    Street lines in EPP are strictly positional. Sparse updates containing gaps
    (e.g., specifying `street_2` or `street_3` when preceding lines are `None`) are rejected
    with a `ValueError` to prevent unintended positional shifting and registry data corruption.
    """

    street_1: Optional[str] = None
    city: Optional[str] = ""
    country_code: Optional[str] = ""
    street_2: Optional[str] = None
    street_3: Optional[str] = None
    province: Optional[str] = ""
    postal_code: Optional[str] = ""

    @staticmethod
    def validate_street_continuity(
        street_1: Optional[str],
        street_2: Optional[str],
        street_3: Optional[str],
    ) -> None:
        """Validate street lines do not have gaps."""
        if street_1 is None and (street_2 is not None or street_3 is not None):
            raise ValueError(
                "Cannot specify 'street_2' or 'street_3' when preceding street lines are omitted."
            )
        if street_2 is None and street_3 is not None:
            raise ValueError(
                "Cannot specify 'street_3' when 'street_2' is omitted."
            )

    def __post_init__(self) -> None:
        """Validate street lines do not have gaps."""
        self.validate_street_continuity(
            self.street_1, self.street_2, self.street_3
        )


@dataclass
class PostalInfoData:
    """Contact postal info data class."""

    name: Optional[str]
    organization: Optional[str] = ""
    address: Optional[AddressData] = None
    type: Optional[Union[PostalInfoTypeEnum, Literal["loc", "int"]]] = "loc"

    def __post_init__(self) -> None:
        """Validate type conforms to RFC 5733."""
        if self.type is None:
            self.type = "loc"
        elif isinstance(self.type, PostalInfoTypeEnum):
            self.type = self.type.value
        elif self.type not in ("loc", "int"):
            raise ValueError(
                f"Invalid postal info type '{self.type}'. Must be 'loc' or 'int'."
            )


# RFC 5733 §2.9 defines allowed disclosure elements. Under §4 XML schema,
# POSTAL_DISCLOSE_ELEMENTS ('name', 'org', 'addr') are of type contact:intLocType
# and REQUIRE a type="loc" or type="int" attribute, whereas communication elements
# ('voice', 'fax', 'email') have no attributes.
VALID_PRIVACY_ELEMENTS: frozenset[str] = frozenset(
    ["name", "org", "addr", "voice", "fax", "email"]
)
POSTAL_DISCLOSE_ELEMENTS: frozenset[str] = frozenset(
    ["name", "org", "addr"]
)
DISCLOSE_ELEMENT_ORDER: dict[str, int] = {
    "name": 1,
    "org": 2,
    "addr": 3,
    "voice": 4,
    "fax": 5,
    "email": 6,
}


@dataclass
class ContactData:
    """Contact data class. Contains the properties of the contacts associated with the domain name.

    :param id: Contact ID
    :param email: Contact email address
    :param postal_info: Contact postal info data
    :param status: Contact status list
    :param phone: Contact voice telephone number
    :param fax: Contact facsimile number
    :param password: Contact authorization password
    :param create_date: Contact creation date
    :param create_client_id: Client ID that created the contact
    :param sponsoring_client_id: Sponsoring client ID
    :param update_client_id: Client ID that last updated the contact
    :param update_date: Contact last update date
    :param privacy: Contact elements to redact from disclosure (Whois/RDAP) under RFC 5733 §2.9.
        Valid options: 'name', 'org', 'addr', 'voice', 'fax', 'email'.
    """

    # pylint: disable=invalid-name,too-many-instance-attributes
    id: str
    email: Optional[str] = ""
    postal_info: Optional[PostalInfoData] = None
    status: Optional[list[str]] = None
    phone: Optional[str] = ""
    fax: Optional[str] = ""
    password: Optional[str] = ""
    create_date: Optional[str] = ""
    create_client_id: Optional[str] = ""
    sponsoring_client_id: Optional[str] = ""
    update_client_id: Optional[str] = ""
    update_date: Optional[str] = ""
    privacy: Optional[list[str]] = None

    def __post_init__(self) -> None:
        """Validate privacy elements conform to RFC 5733."""
        if self.privacy is not None:
            for item in self.privacy:
                if not isinstance(item, str):
                    raise ValueError(
                        f"Invalid privacy disclosure item: {item}. Must be a string."
                    )
                # Parse optional ':loc' or ':int' suffix (e.g. 'name:int', 'name:loc')
                elem, *ptype_parts = item.split(":", 1)
                if elem not in VALID_PRIVACY_ELEMENTS:
                    raise ValueError(
                        f"Invalid privacy disclosure element '{elem}'. "
                        f"Must be one of {sorted(VALID_PRIVACY_ELEMENTS)}."
                    )
                if ptype_parts:
                    ptype = ptype_parts[0]
                    if ptype not in ("loc", "int"):
                        raise ValueError(
                            f"Invalid postal type '{ptype}' for element '{elem}'. "
                            "Must be 'loc' or 'int'."
                        )
                    if elem not in POSTAL_DISCLOSE_ELEMENTS:
                        raise ValueError(
                            f"Element '{elem}' does not support postal type qualification."
                        )


class Contact(BaseCommand):
    """Epp Contact object class. This class is used to create and manage the contacts within the Registry.

    Contacts are individuals or organizations that are associated with domain names. There are different types of
    contacts including:

    * Registrant - The entity that has the authority to use and manage the domain name.
    * Administrative Contact - Either the Registrant or someone authorized to act on behalf of the Registrant.
    * Technical Contact - A technical contact is an individual identified as a contact for technical information-related
      administration of a registered domain name.
    * Billing Contact - Also known as the Finance Contact, this is the individual or organization responsible for
      payment of fees related to the domain name and will monitor period activity, account balances, and account status.
    """

    @staticmethod
    def _format_privacy_disclosure(
        privacy: list[str], intended_postal_type: str
    ) -> list[dict]:
        """Format privacy elements with intended postal type for disclosure template.

        RFC 5733 requires type="loc" or type="int" on <contact:name>, <contact:org>,
        and <contact:addr> disclosure tags. For postal elements that do not explicitly
        specify a type suffix, we assign the contact's intended postal type (defaulting
        to 'loc' for privacy-only updates). Communication elements (voice, fax, email)
        remain without attributes (type=None).

        Elements are deduplicated and normalized to canonical RFC 5733 schema order
        (name -> org -> addr -> voice -> fax -> email).
        """
        seen: set[tuple[str, Optional[str]]] = set()
        disclosure_data: list[dict] = []
        for item in privacy:
            if not isinstance(item, str):
                raise ValueError(
                    f"Invalid privacy disclosure item '{item}'. Must be a string."
                )
            elem, *ptype_parts = item.split(":", 1)
            if elem not in VALID_PRIVACY_ELEMENTS:
                raise ValueError(
                    f"Invalid privacy disclosure element '{elem}'. "
                    f"Must be one of {sorted(VALID_PRIVACY_ELEMENTS)}."
                )
            if ptype_parts:
                ptype = ptype_parts[0]
                if ptype not in ("loc", "int"):
                    raise ValueError(
                        f"Invalid postal type '{ptype}' for element '{elem}'. "
                        "Must be 'loc' or 'int'."
                    )
                if elem not in POSTAL_DISCLOSE_ELEMENTS:
                    raise ValueError(
                        f"Element '{elem}' does not support postal type qualification."
                    )
                actual_type = ptype
            elif elem in POSTAL_DISCLOSE_ELEMENTS:
                actual_type = intended_postal_type
            else:
                actual_type = None

            key = (elem, actual_type)
            if key not in seen:
                seen.add(key)
                disclosure_data.append({"name": elem, "type": actual_type})

        # RFC 5733 §4 XML schema requires elements in strict sequence:
        # name -> org -> addr -> voice -> fax -> email
        disclosure_data.sort(
            key=lambda x: (
                DISCLOSE_ELEMENT_ORDER.get(x["name"], 99),
                0 if x.get("type") == "int" else (1 if x.get("type") == "loc" else 2),
            )
        )
        return disclosure_data

    def _data_to_dict(self, data: ContactData) -> dict:
        """Convert a contact dataclass to a dictionary.

        :param data: Contact details

        :return: Contact details
        :rtype: dict
        """
        data_dict = asdict(data)
        postal_info = data_dict.pop("postal_info", {})
        address = postal_info.pop("address", {}) if postal_info is not None else {}

        if address:
            AddressData.validate_street_continuity(
                address.get("street_1"),
                address.get("street_2"),
                address.get("street_3"),
            )
            data_dict.update(address)
        if postal_info:
            data_dict.update(postal_info)

        if "type" in data_dict:
            type_val = (
                data_dict["type"].value
                if isinstance(data_dict["type"], Enum)
                else data_dict["type"]
            )
            if type_val not in ("loc", "int"):
                raise ValueError(
                    f"Invalid postal info type '{type_val}'. Must be 'loc' or 'int'."
                )
            data_dict["type"] = type_val

        if data_dict.get("privacy") is not None:
            intended_postal_type = (
                data_dict.get("type")
                if data_dict.get("type") in ("loc", "int")
                else "loc"
            )
            data_dict["privacy"] = self._format_privacy_disclosure(
                data_dict["privacy"], intended_postal_type
            )

        return data_dict

    def check(
        self, contact_ids: list[str], client_transaction_id: Optional[str] = None
    ) -> EppResultData:
        """A successful Contact Check request determines whether a Contact ID is available for use and whether a contact
        can be created in the Registry. When creating a new contact, the Registrar must generate a Registry-unique
        contact ID. A Registry Contact Check request can determine whether an ID is already in use.

        :param contact_ids: List of contact ids
        :param client_transaction_id: Client transaction id

        :return: contact check result
        :rtype: EppResultData
        """
        result = self.execute(
            CONTACT_CHECK_XML,
            ids=contact_ids,
            client_transaction_id=client_transaction_id,
        )

        # In dry-run mode or on error, skip XML payload parsing since there is no response payload
        if int(result.code) != int(EppResultCode.SUCCESS.value) or result.dry_run:
            return result

        raw_response = result.parsed_xml
        contacts_check_data = raw_response.find_all("cd")

        result_data = {}
        for contact_cd in contacts_check_data:
            contact = contact_cd.find("id")
            available = contact.get("avail") in ("true", "1")
            reason = contact_cd.find("reason").text if not available else None
            result_data[contact.text] = {
                "avail": available,
                "reason": reason,
            }

        result.result_data = result_data

        return result

    def info(
        self, contact_id: str, client_transaction_id: Optional[str] = None
    ) -> EppResultData:
        """
        A successful Contact Info request retrieves information associated with an existing contact.
        All available information is returned if the querying Registrar is the contact’s sponsor. For a non-sponsoring
        Registrar, all contact information is returned if the correct authorization code is entered. As well, if the
        Authorization Code Expiry has been configured, the authorization code must not be expired. Otherwise,
        the <contact:info> will fail.

        :param contact_id: Contact ID
        :param client_transaction_id: Client transaction id

        :return: Contact details
        :rtype: EppResultData
        """
        result = self.execute(
            CONTACT_INFO_XML, id=contact_id, client_transaction_id=client_transaction_id
        )

        # In dry-run mode or on error, skip XML payload parsing since there is no response payload
        if int(result.code) != int(EppResultCode.SUCCESS.value) or result.dry_run:
            return result

        raw_response = result.parsed_xml

        result_data = {
            "id": raw_response.find("id").text,
            "status": [status.text for status in raw_response.find_all("status")],
            "create_date": raw_response.find("crDate").text,
            "create_client_id": raw_response.find("crID").text,
            "sponsoring_client_id": raw_response.find("clID").text,
            "update_client_id": (
                raw_response.find("upID").text if raw_response.find("upID") else None
            ),
            "update_date": (
                raw_response.find("upDate").text
                if raw_response.find("upDate")
                else None
            ),
            "postal_info": PostalInfoData(
                **{
                    "name": raw_response.find("name").text,
                    "organization": (
                        raw_response.find("org").text
                        if raw_response.find("org")
                        else None
                    ),
                    "type": (
                        raw_response.find("postalInfo").get("type")
                        if raw_response.find("postalInfo")
                        and raw_response.find("postalInfo").get("type")
                        else "loc"
                    ),
                    "address": AddressData(
                        **{
                            "street_1": (
                                raw_response.find_all("street")[0].text
                                if len(raw_response.find_all("street")) >= 1
                                else None
                            ),
                            "street_2": (
                                raw_response.find_all("street")[1].text
                                if len(raw_response.find_all("street")) >= 2
                                else None
                            ),
                            "street_3": (
                                raw_response.find_all("street")[2].text
                                if len(raw_response.find_all("street")) >= 3
                                else None
                            ),
                            "city": raw_response.find("city").text,
                            "province": (
                                raw_response.find("sp").text
                                if raw_response.find("sp")
                                else None
                            ),
                            "postal_code": (
                                raw_response.find("pc").text
                                if raw_response.find("pc")
                                else None
                            ),
                            "country_code": raw_response.find("cc").text,
                        }
                    ),
                }
            ),
            "phone": (
                raw_response.find("voice").text if raw_response.find("voice") else None
            ),
            "fax": raw_response.find("fax").text if raw_response.find("fax") else None,
            "email": raw_response.find("email").text,
        }

        if raw_response.find("pw"):
            result_data["password"] = raw_response.find("pw").text

        if raw_response.find("disclose"):
            disclose_el = raw_response.find("disclose")
            # RFC 5733 §2.9: flag="0" indicates non-disclosure / redaction (privacy),
            # while flag="1" indicates disclosure is allowed. Only populate privacy
            # when flag is "0" or "false" to prevent marking disclosed fields as private.
            flag = disclose_el.get("flag", "0")
            if flag in ("0", "false"):
                # Preserve postal disclosure types (e.g. 'name:int', 'name:loc') so that
                # both localized and international disclosure settings round-trip losslessly
                # into subsequent update requests instead of collapsing into a single bare tag.
                privacy_items = []
                for el in disclose_el.find_all(recursive=False):
                    if el.name in VALID_PRIVACY_ELEMENTS:
                        ptype = el.get("type")
                        if (
                            el.name in POSTAL_DISCLOSE_ELEMENTS
                            and ptype in ("loc", "int")
                        ):
                            privacy_items.append(f"{el.name}:{ptype}")
                        else:
                            privacy_items.append(el.name)
                result_data["privacy"] = list(dict.fromkeys(privacy_items))

        result.result_data = ContactData(**result_data)

        return result

    def create(
        self, contact: ContactData, client_transaction_id: Optional[str] = None
    ) -> EppResultData:
        """A successful Contact Create request creates a contact object in the Registry. To create a domain name
        successfully, a Registrar does not need to be the sponsor of the related hosts but must be the sponsor of all
        assigned contacts.

        :param contact: Contact
        :param client_transaction_id: Client transaction id

        :return: Result object
        :rtype: EppResultData
        """
        if not contact.postal_info or not contact.postal_info.name:
            raise ValueError("Contact creation requires postal info with 'name'.")
        if (
            not contact.postal_info.address
            or not contact.postal_info.address.city
            or not contact.postal_info.address.country_code
        ):
            raise ValueError(
                "Contact creation requires postal info address with 'city' and 'country_code'."
            )
        if not contact.email or not contact.email.strip():
            raise ValueError("Contact creation requires 'email'.")

        addr = contact.postal_info.address
        if addr.street_1 == "" and (addr.street_2 or addr.street_3):
            raise ValueError(
                "Cannot specify 'street_2' or 'street_3' when 'street_1' is empty."
            )
        if addr.street_2 == "" and addr.street_3:
            raise ValueError(
                "Cannot specify 'street_3' when 'street_2' is empty."
            )

        params = self._data_to_dict(contact)
        params["client_transaction_id"] = client_transaction_id

        if not params.get("password"):
            params["password"] = helper.generate_password(16)

        result = self.execute(CONTACT_CREATE_XML, **params)

        return result

    def delete(
        self, contact_id: str, client_transaction_id: Optional[str] = None
    ) -> EppResultData:
        """A successful Contact Delete request deletes a contact object from the Registry

        :param contact_id: Contact ID
        :param client_transaction_id: Client transaction id

        :return: Result object
        """
        result = self.execute(
            CONTACT_DELETE_XML,
            id=contact_id,
            client_transaction_id=client_transaction_id,
        )

        return result

    def update(
        self,
        contact: ContactData,
        add_status: Optional[str] = "",
        remove_status: Optional[str] = "",
        client_transaction_id: Optional[str] = None,
    ) -> EppResultData:
        """A successful Contact Update request modifies a contact object in the Registry. Updates to Registrant contacts
        must be valid and must be complete.

        :param contact: Contact details to be updated
        :param add_status: Status to be added
        :param remove_status: Status to be removed
        :param client_transaction_id: Client transaction id

        :return: Result object
        :rtype: EppResultData
        """
        # Check if actual postal information (name, org, address) is being modified.
        # If postal_info only specifies type (e.g. type="int" to convey disclosure postal type
        # for a privacy-only update), do not trigger postalinfo_change or validation errors.
        has_postal_change = bool(
            contact.postal_info
            and (
                contact.postal_info.name
                or contact.postal_info.organization
                or contact.postal_info.address
            )
        )
        has_chg = bool(
            has_postal_change
            or contact.phone
            or contact.fax
            or contact.email
            or contact.password
            or contact.privacy
        )
        if not (add_status or remove_status or has_chg):
            raise ValueError(
                "Contact update requires at least one change "
                "(postal_info, phone, fax, email, password) or status modification."
            )

        if contact.postal_info and has_postal_change:
            if contact.postal_info.type == "int":
                if (
                    not contact.postal_info.name
                    or not contact.postal_info.address
                    or not contact.postal_info.address.city
                    or not contact.postal_info.address.country_code
                ):
                    raise ValueError(
                        "Postal info update with type 'int' requires complete 'name', 'city', and 'country_code'."
                    )
            elif contact.postal_info.address:
                if (
                    not contact.postal_info.address.city
                    or not contact.postal_info.address.country_code
                ):
                    raise ValueError(
                        "Postal info address update requires both 'city' and 'country_code'."
                    )
            elif (
                not contact.postal_info.name
                and not contact.postal_info.organization
            ):
                raise ValueError("Postal info update cannot be empty.")

        params = self._data_to_dict(contact)

        params["add_status"] = add_status
        params["remove_status"] = remove_status

        params["postalinfo_change"] = has_postal_change
        params["address_change"] = bool(
            contact.postal_info and contact.postal_info.address
        )
        params["postal_type"] = (
            contact.postal_info.type
            if contact.postal_info and contact.postal_info.type
            else "loc"
        )
        params["client_transaction_id"] = client_transaction_id

        result = self.execute(CONTACT_UPDATE_XML, **params)

        return result
