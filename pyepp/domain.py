"""
Domain Mapping Module.
"""

from dataclasses import asdict, dataclass
from enum import Enum, IntEnum
from typing import Any, Optional, Union
from datetime import date, datetime

from pyepp.epp import EppResultData
from pyepp.base_command import BaseCommand
from pyepp.command_templates import (
    DOMAIN_CHECK_XML,
    DOMAIN_INFO_XML,
    DOMAIN_CREATE_XML,
    DOMAIN_DELETE_XML,
    DOMAIN_RENEW_XML,
    TRANSFER_REQUEST_XML,
    DOMAIN_UPDATE_XML,
    DOMAIN_RESTORE_XML,
    DOMAIN_RESTORE_REPORT_XML,
)
from pyepp import helper
from pyepp.epp import EppResultCode


class DNSSECAlgorithm(IntEnum):
    """DNSSEC algorithms enumeration (RFC 4034 §A.1, RFC 5910)."""

    DSA_SHA_1 = 3
    RSA_SHA_1 = 5
    DSA_NSEC3_SHA1 = 6
    RSASHA1_NSEC3_SHA1 = 7
    RSA_SHA_256 = 8
    RSA_SHA_512 = 10
    GOST_R_34_10_2001 = 12
    ECDSA_CURVE_P_256_WITH_SHA_256 = 13
    ECDSA_CURVE_P_384_WITH_SHA_384 = 14
    ED25519 = 15
    ED448 = 16
    PRIVATE_ALGORITHM = 253
    PRIVATE_ALGORITHM_OID = 255

    def __str__(self) -> str:
        """Return string representation of the integer value."""
        return str(self.value)


class DigestTypeEnum(IntEnum):
    """Digest types enumeration (RFC 4034 §A.2, RFC 5910)."""

    SHA_1 = 1
    SHA_256 = 2
    GOST_R_34_11_94 = 3
    SHA_384 = 4

    def __str__(self) -> str:
        """Return string representation of the integer value."""
        return str(self.value)


class DNSKeyFlagEnum(IntEnum):
    """DNS Key flags enumeration (RFC 4034 §2.1.1, RFC 5910)."""

    FLAG_256 = 256
    FLAG_257 = 257

    def __str__(self) -> str:
        """Return string representation of the integer value."""
        return str(self.value)


@dataclass
class DSRecordKeyData:
    """DNSSEC Key data dataclass (RFC 4034 §2.1, RFC 5910 §5.1.1)."""

    flag: Optional[Union[DNSKeyFlagEnum, int, str]] = None
    algorithm: Optional[Union[DNSSECAlgorithm, int, str]] = None
    public_key: Optional[str] = None
    protocol: Optional[Union[int, str]] = 3

    def __getitem__(self, key: Any) -> Any:
        """Support dict-like indexing for backward compatibility."""
        dataclass_fields = getattr(self, "__dataclass_fields__", {})
        if isinstance(key, str) and key in dataclass_fields:
            return getattr(self, key)
        raise KeyError(key)

    def get(self, key: Any, default: Any = None) -> Any:
        """Support dict-like .get() for backward compatibility."""
        dataclass_fields = getattr(self, "__dataclass_fields__", {})
        if isinstance(key, str) and key in dataclass_fields:
            return getattr(self, key)
        return default

    def __contains__(self, key: Any) -> bool:
        """Support 'in' operator for backward compatibility."""
        dataclass_fields = getattr(self, "__dataclass_fields__", {})
        return isinstance(key, str) and key in dataclass_fields

    def keys(self) -> list[str]:
        """Support .keys() for backward compatibility."""
        dataclass_fields = getattr(self, "__dataclass_fields__", {})
        return list(dataclass_fields.keys())


@dataclass
class DSRecordData:
    """DNSSEC DS record dataclass (RFC 4034 §5.1, RFC 5910 §5.1.1)."""

    key_tag: Optional[Union[int, str]] = None
    algorithm: Optional[Union[DNSSECAlgorithm, int, str]] = None
    digest_type: Optional[Union[DigestTypeEnum, int, str]] = None
    digest: Optional[str] = None
    dns_key: Optional[Union[DSRecordKeyData, dict]] = None

    def __getitem__(self, key: Any) -> Any:
        """Support dict-like indexing for backward compatibility."""
        dataclass_fields = getattr(self, "__dataclass_fields__", {})
        if isinstance(key, str) and key in dataclass_fields:
            return getattr(self, key)
        raise KeyError(key)

    def get(self, key: Any, default: Any = None) -> Any:
        """Support dict-like .get() for backward compatibility."""
        dataclass_fields = getattr(self, "__dataclass_fields__", {})
        if isinstance(key, str) and key in dataclass_fields:
            return getattr(self, key)
        return default

    def __contains__(self, key: Any) -> bool:
        """Support 'in' operator for backward compatibility."""
        dataclass_fields = getattr(self, "__dataclass_fields__", {})
        return isinstance(key, str) and key in dataclass_fields

    def keys(self) -> list[str]:
        """Support .keys() for backward compatibility."""
        dataclass_fields = getattr(self, "__dataclass_fields__", {})
        return list(dataclass_fields.keys())


@dataclass
class DomainData:
    """Domain name dataclass."""

    # pylint: disable=too-many-instance-attributes
    domain_name: str
    period: Optional[int] = None
    registrant: Optional[str] = ""
    admin: Optional[Union[list[str], tuple[str, ...], str]] = None
    tech: Optional[Union[list[str], tuple[str, ...], str]] = None
    sponsoring_client_id: Optional[str] = ""
    billing: Optional[Union[list[str], tuple[str, ...], str]] = None
    status: Optional[list[str]] = None
    host: Optional[list[str]] = None
    create_date: Optional[str] = ""
    create_client_id: Optional[str] = ""
    update_client_id: Optional[str] = ""
    update_date: Optional[str] = ""
    expiry_date: Optional[str] = ""
    transfer_date: Optional[str] = ""
    password: Optional[str] = ""
    dns_sec: Optional[Union[list[DSRecordData], DSRecordData]] = None


class Domain(BaseCommand):
    """
    Epp domain object class is used to create and manage domain names in Registry.
    """

    def _data_to_dict(self, data: DomainData) -> dict:
        """Convert a domain dataclass to a dictionary.

        :param DomainData data: Domain name details

        :return: Domain name details
        :rtype: dict
        """
        data_dict = asdict(data)

        return data_dict

    @staticmethod
    def _normalize_ds_record_item(item: Union[DSRecordData, dict]) -> dict:
        """Convert a single DS record (dataclass or dict) to a normalized dictionary.

        Unpacks Enum objects (such as DNSSECAlgorithm, DigestTypeEnum, DNSKeyFlagEnum)
        to their underlying scalar values for proper Jinja2 template rendering.

        :param item: DSRecordData or dict representing a DS record
        :return: Dictionary representation of the DS record with unpacked Enum values
        :raises TypeError: If item is neither a DSRecordData nor a dict
        """
        if isinstance(item, DSRecordData):
            item_dict = asdict(item)
        elif isinstance(item, dict):
            item_dict = dict(item)
        else:
            raise TypeError(
                f"Expected DSRecordData or dict, got {type(item).__name__}"
            )

        # Unpack Enum values if present
        if isinstance(item_dict.get("algorithm"), Enum):
            item_dict["algorithm"] = item_dict["algorithm"].value
        if isinstance(item_dict.get("digest_type"), Enum):
            item_dict["digest_type"] = item_dict["digest_type"].value

        # Handle optional nested dns_key (supports DSRecordKeyData or dict when item is a raw dict)
        dns_key = item_dict.get("dns_key")
        if dns_key:
            if isinstance(dns_key, DSRecordKeyData):
                dns_key_dict = asdict(dns_key)
            elif isinstance(dns_key, dict):
                dns_key_dict = dict(dns_key)
            else:
                raise TypeError(
                    f"Expected DSRecordKeyData or dict for dns_key, got {type(dns_key).__name__}"
                )

            if isinstance(dns_key_dict.get("algorithm"), Enum):
                dns_key_dict["algorithm"] = dns_key_dict["algorithm"].value
            if isinstance(dns_key_dict.get("flag"), Enum):
                dns_key_dict["flag"] = dns_key_dict["flag"].value
            item_dict["dns_key"] = dns_key_dict

        return item_dict

    @classmethod
    def _normalize_ds_records(
        cls,
        records: Optional[Union[list[DSRecordData], DSRecordData, list[dict], dict]],
    ) -> Optional[list[dict]]:
        """Normalize DS records into a list of dictionaries with enum values unpacked.

        Handles both DSRecordData instances and pre-serialized dictionaries, accommodating
        both single instances and lists. Resolves Issue #316 by moving shape normalization
        from Jinja2 templates into Python.

        :param records: Single DS record or list of DS records (dataclass or dict)
        :return: Normalized list of DS record dictionaries, or None if records is empty
        """
        if not records:
            return None

        if isinstance(records, (list, tuple)):
            record_list = list(records)
        else:
            record_list = [records]

        return [cls._normalize_ds_record_item(item) for item in record_list]

    @staticmethod
    def _normalize_contact_list(
        contacts: Optional[Union[list[str], tuple[str, ...], str]]
    ) -> Optional[list[str]]:
        """Normalize domain contact identifiers to a list of non-empty strings.

        RFC 5731 §3.2.1 permits zero or more contact elements per type (admin, tech,
        billing). Accepts a single contact id string or a sequence (list or tuple) of
        contact ids, validating types and stripping whitespace.

        :param contacts: Single contact ID string or sequence of contact IDs
        :return: List of contact ID strings, or None if no contacts are provided
        :raises TypeError: If contacts or any element in contacts is not a string
        """
        # Only None bypasses validation; falsey unsupported types must still raise.
        if contacts is None:
            return None
        if isinstance(contacts, str):
            stripped = contacts.strip()
            return [stripped] if stripped else None
        if isinstance(contacts, (list, tuple)):
            result = []
            for c in contacts:
                if not isinstance(c, str):
                    raise TypeError(
                        f"Expected contact ID to be str, got {type(c).__name__}"
                    )
                stripped = c.strip()
                if stripped:
                    result.append(stripped)
            return result or None
        raise TypeError(
            f"Expected contact ID to be str, list[str], or tuple[str, ...], "
            f"got {type(contacts).__name__}"
        )

    # pylint: disable=R0801
    def check(
        self, domain_names: list[str], client_transaction_id: Optional[str] = None
    ) -> EppResultData:
        """A successful Domain Check request determines whether a domain name is available for use and whether a domain
        name registration can be successfully created in the Registry.

        :param list domain_names: List of domain names
        :param client_transaction_id: Client transaction id

        :return: Result object
        :rtype: EppResultData
        """
        result = self.execute(
            DOMAIN_CHECK_XML,
            domain_names=domain_names,
            client_transaction_id=client_transaction_id,
        )

        # In dry-run mode or on error, skip XML payload parsing since there is no response payload
        if int(result.code) != int(EppResultCode.SUCCESS.value) or result.dry_run:
            return result

        raw_response = result.parsed_xml
        # Scope XML parsing to <resData> / <domain:chkData> per RFC 5731 §3.1.1
        # to prevent <cd> elements in <extension> blocks (e.g. fee/launch) from colliding.
        res_data = raw_response.find("resData")
        chk_el = (
            (res_data.find("chkData") or res_data)
            if res_data
            else (raw_response.find("chkData") or raw_response)
        )
        domains_check_data = chk_el.find_all("cd")

        result_data = {}
        for domain_cd in domains_check_data:
            domain = domain_cd.find("name")
            if not domain:
                continue
            available = domain.get("avail") in ("true", "1")
            # RFC 5731 §3.1.1: <domain:reason> is OPTIONAL even when avail="0"/"false".
            # Safely check that the <reason> node exists before accessing .text to
            # prevent AttributeError crashes on registries that omit reason.
            reason_el = domain_cd.find("reason")
            reason = (
                reason_el.text
                if (not available and reason_el is not None)
                else None
            )
            result_data[domain.text] = {
                "avail": available,
                "reason": reason,
            }

        result.result_data = result_data

        return result

    @staticmethod
    def _parse_int_or_enum(
        el: Any,
        enum_cls: Optional[type] = None,
        default: Any = None,
    ) -> Any:
        """Parse an XML element's text into an enum or int, with fallback.

        Handles whitespace stripping and unassigned numeric codes (e.g. private
        or newly assigned IANA DNSSEC algorithms).

        :param el: XML element containing text
        :param enum_cls: Optional Enum/IntEnum class to convert to
        :param default: Default value if element is None or empty
        :return: Enum member, int, raw string fallback, or default
        """
        if el is None or el.text is None:
            return default
        raw = el.text.strip()
        if not raw:
            return default
        try:
            val = int(raw)
        except ValueError:
            return raw

        if enum_cls is not None:
            try:
                return enum_cls(val)
            except ValueError:
                return val
        return val

    @classmethod
    def _parse_ds_key_data(cls, key_data_el: Any) -> Optional[DSRecordKeyData]:
        """Parse a <secDNS:keyData> XML element into a DSRecordKeyData instance.

        :param key_data_el: BeautifulSoup element for <secDNS:keyData>
        :return: Parsed DSRecordKeyData instance, or None if key_data_el is None
        """
        if not key_data_el:
            return None

        # RFC 5910 §5.1.1: Query keyData child elements strictly within <secDNS:keyData>.
        # Previously, querying ds_data.find("alg") returned the DS record's algorithm
        # rather than keyData's algorithm.
        key_flags = key_data_el.find("flags", recursive=False)
        key_proto = key_data_el.find("protocol", recursive=False)
        key_alg = key_data_el.find("alg", recursive=False)
        key_pub = key_data_el.find("pubKey", recursive=False)

        parsed_flag = cls._parse_int_or_enum(key_flags, enum_cls=DNSKeyFlagEnum)
        parsed_proto = cls._parse_int_or_enum(key_proto, default=3)
        parsed_key_alg = cls._parse_int_or_enum(key_alg, enum_cls=DNSSECAlgorithm)
        parsed_pub = (
            key_pub.text.strip() if key_pub and key_pub.text else None
        )

        return DSRecordKeyData(
            flag=parsed_flag,
            protocol=parsed_proto,
            algorithm=parsed_key_alg,
            public_key=parsed_pub,
        )

    @classmethod
    def _parse_ds_record(cls, ds_data: Any) -> DSRecordData:
        """Parse a <secDNS:dsData> XML element into a DSRecordData instance.

        :param ds_data: BeautifulSoup element for <secDNS:dsData>
        :return: Parsed DSRecordData instance
        """
        # Use recursive=False so direct DS child elements (especially <secDNS:alg>)
        # never descend into the nested <secDNS:keyData> element.
        key_tag_el = ds_data.find("keyTag", recursive=False)
        alg_el = ds_data.find("alg", recursive=False)
        digest_type_el = ds_data.find("digestType", recursive=False)
        digest_el = ds_data.find("digest", recursive=False)
        key_data_el = ds_data.find("keyData", recursive=False)

        dns_key = cls._parse_ds_key_data(key_data_el)
        parsed_key_tag = cls._parse_int_or_enum(key_tag_el)
        parsed_alg = cls._parse_int_or_enum(alg_el, enum_cls=DNSSECAlgorithm)
        parsed_digest_type = cls._parse_int_or_enum(
            digest_type_el, enum_cls=DigestTypeEnum
        )
        parsed_digest = (
            digest_el.text.strip() if digest_el and digest_el.text else None
        )

        return DSRecordData(
            key_tag=parsed_key_tag,
            algorithm=parsed_alg,
            digest_type=parsed_digest_type,
            digest=parsed_digest,
            dns_key=dns_key,
        )

    @classmethod
    def _parse_dnssec_extension(cls, raw_response: Any) -> Optional[list[DSRecordData]]:
        """Parse RFC 5910 DNSSEC data from <extension><secDNS:infData>.

        :param raw_response: Parsed XML document or response element
        :return: List of DSRecordData instances, or None if no DNSSEC records found
        """
        ext_data = raw_response.find("extension")
        sec_scope = ext_data if ext_data else raw_response
        all_ds_data = sec_scope.find_all("dsData")
        if not all_ds_data:
            return None
        return [cls._parse_ds_record(ds_data) for ds_data in all_ds_data]

    # pylint: disable=too-many-locals
    def info(
        self, domain_name: str, client_transaction_id: Optional[str] = None
    ) -> EppResultData:
        """A successful Domain Info request retrieves information associated with an existing domain name.

        :param domain_name: Domain name
        :param client_transaction_id: Client transaction id

        :return: Result object
        :rtype: EppResultData
        """
        result = self.execute(
            DOMAIN_INFO_XML,
            domain_name=domain_name,
            client_transaction_id=client_transaction_id,
        )

        # In dry-run mode or on error, skip XML payload parsing since there is no response payload
        if int(result.code) != int(EppResultCode.SUCCESS.value) or result.dry_run:
            return result

        raw_response = result.parsed_xml

        # Per RFC 5731 §3.1.2, elements like registrant, contacts, and authInfo
        # are optional and often omitted or redacted by registries when the domain
        # is queried by a non-sponsoring registrar. Safe null checks prevent
        # AttributeError when parsing responses for external domains.
        # We scope queries to <resData> / <domain:infData> to avoid collisions with
        # identical element names (e.g. status, name, clID) in other EPP blocks or extensions.
        res_data = raw_response.find("resData")
        info_el = (
            (res_data.find("infData") or res_data)
            if res_data
            else (raw_response.find("infData") or raw_response)
        )

        name_el = info_el.find("name")
        cl_id_el = info_el.find("clID")
        reg_el = info_el.find("registrant")
        # RFC 5731 §3.1.2: A domain may have zero, one, or multiple contacts of type
        # "admin", "tech", or "billing" (<domain:contact minOccurs="0" maxOccurs="unbounded">).
        # Query all matching contact elements via find_all() to avoid silently dropping
        # secondary contacts and ensure consistent list representations. Strip whitespace
        # and discard empty/redacted tags so optional contact lists default to None.
        admin_els = info_el.find_all("contact", {"type": "admin"})
        tech_els = info_el.find_all("contact", {"type": "tech"})
        billing_els = info_el.find_all("contact", {"type": "billing"})
        admin_contacts = [
            admin.text.strip()
            for admin in admin_els
            if admin.text and admin.text.strip()
        ]
        tech_contacts = [
            tech.text.strip()
            for tech in tech_els
            if tech.text and tech.text.strip()
        ]
        billing_contacts = [
            billing.text.strip()
            for billing in billing_els
            if billing.text and billing.text.strip()
        ]
        cr_date_el = info_el.find("crDate")
        cr_id_el = info_el.find("crID")
        ex_date_el = info_el.find("exDate")
        up_id_el = info_el.find("upID")
        up_date_el = info_el.find("upDate")
        tr_date_el = info_el.find("trDate")
        pw_el = info_el.find("pw")

        result_data = {
            "domain_name": name_el.text if name_el else None,
            "sponsoring_client_id": cl_id_el.text if cl_id_el else None,
            "status": [
                status.get("s") or status.text
                for status in info_el.find_all("status")
            ],
            "host": (
                [host.text for host in info_el.find_all("hostObj")]
                if info_el.find("ns")
                else None
            ),
            "registrant": reg_el.text if reg_el else None,
            "admin": admin_contacts or None,
            "tech": tech_contacts or None,
            "billing": billing_contacts or None,
            "create_date": cr_date_el.text if cr_date_el else None,
            "create_client_id": cr_id_el.text if cr_id_el else None,
            "expiry_date": ex_date_el.text if ex_date_el else None,
            "update_client_id": up_id_el.text if up_id_el else None,
            "update_date": up_date_el.text if up_date_el else None,
            "transfer_date": tr_date_el.text if tr_date_el else None,
            "password": pw_el.text if pw_el else None,
            "period": None,
            "dns_sec": None,
        }

        # DNSSEC data is defined in RFC 5910 under <extension><secDNS:infData>.
        dns_sec = self._parse_dnssec_extension(raw_response)
        if dns_sec:
            result_data["dns_sec"] = dns_sec

        result.result_data = DomainData(**result_data)

        return result

    def create(
        self, domain: DomainData, client_transaction_id: Optional[str] = None
    ) -> EppResultData:
        """A successful Domain Create request creates a domain object in the Registry, and also creates relationships
        between the domain name and previously created contacts and hosts.

        :param domain: Domain name details
        :param client_transaction_id: Client transaction id

        :return: Result object
        :rtype: EppResultData
        """
        params = self._data_to_dict(domain)
        params["client_transaction_id"] = client_transaction_id

        if not params.get('password'):
            params['password'] = helper.generate_password(16)

        # RFC 5731 §3.2.1: Normalize admin, tech, and billing contacts to lists of strings
        # so DOMAIN_CREATE_XML renders individual <domain:contact> elements without
        # leaking Python list representations or dropping multiple contacts.
        params["admin"] = self._normalize_contact_list(params.get("admin"))
        params["tech"] = self._normalize_contact_list(params.get("tech"))
        params["billing"] = self._normalize_contact_list(params.get("billing"))

        # Issue #316: Normalize dns_sec into a list of dicts with unpacked enum values,
        # ensuring DOMAIN_CREATE_XML receives a standard list rather than handling mappings in Jinja.
        params["dns_sec"] = self._normalize_ds_records(params.get("dns_sec"))

        result = self.execute(DOMAIN_CREATE_XML, **params)

        return result

    def delete(
        self, domain_name: str, client_transaction_id: Optional[str] = None
    ) -> EppResultData:
        """This command provides a transform operation that allows a client to delete a domain object

        :param domain_name: Domain Name
        :param client_transaction_id: Client transaction id

        :return: Result object
        :rtype: EppResultData
        """
        result = self.execute(
            DOMAIN_DELETE_XML,
            domain_name=domain_name,
            client_transaction_id=client_transaction_id,
        )

        return result

    def renew(
        self,
        domain_name: str,
        expiry_date: date,
        period: Optional[int] = 1,
        client_transaction_id: Optional[str] = None,
    ) -> EppResultData:
        """A successful Domain Renew request extends the registration period of a domain name.

        :param domain_name: Domain Name
        :param expiry_date: expiry date
        :param period: period
        :param client_transaction_id: Client transaction id

        :return: Result object
        :rtype: EppResultData
        """
        result = self.execute(
            DOMAIN_RENEW_XML,
            domain_name=domain_name,
            expiry_date=expiry_date.strftime("%Y-%m-%d"),
            period=str(period),
            client_transaction_id=client_transaction_id,
        )

        return result

    def transfer(
        self,
        domain_name: str,
        password: str,
        period: Optional[int] = None,
        client_transaction_id: Optional[str] = None,
    ) -> EppResultData:
        """transfers the sponsorship of a domain name from another Registrar to the Registrar
        submitting the request.

        :param domain_name: Domain Name
        :param password: The authorization password for the domain object
        :param period: period
        :param client_transaction_id: Client transaction id

        :return: Result object
        :rtype: EppResultData
        """
        result = self.execute(
            TRANSFER_REQUEST_XML,
            domain_name=domain_name,
            password=password,
            period=str(period) if period else None,
            client_transaction_id=client_transaction_id,
        )

        return result

    # pylint: disable=too-many-arguments,too-many-locals,too-many-positional-arguments
    def update(
        self,
        domain_name: str,
        registrant: Optional[str] = None,
        password: Optional[str] = None,
        add_admins: Optional[Union[list[str], tuple[str, ...], str]] = None,
        remove_admins: Optional[Union[list[str], tuple[str, ...], str]] = None,
        add_techs: Optional[Union[list[str], tuple[str, ...], str]] = None,
        remove_techs: Optional[Union[list[str], tuple[str, ...], str]] = None,
        add_billings: Optional[Union[list[str], tuple[str, ...], str]] = None,
        remove_billings: Optional[Union[list[str], tuple[str, ...], str]] = None,
        add_statuses: Optional[list[tuple]] = None,
        remove_statuses: Optional[list[str]] = None,
        add_hosts: Optional[list[str]] = None,
        remove_hosts: Optional[list[str]] = None,
        add_dns_sec: Optional[Union[list[DSRecordData], DSRecordData]] = None,
        remove_dns_sec: Optional[Union[list[DSRecordData], DSRecordData]] = None,
        remove_all_dns_sec: bool = False,
        client_transaction_id: Optional[str] = None,
    ) -> EppResultData:
        """A successful Domain Update request modifies a domain object in the Registry, and may also add or delete
        relationships between the domain name and previously created hosts and contacts.

        :param domain_name: Domain name to be updated
        :param registrant: A contact id to replace the current registrant
        :param add_admins: A list, tuple, or single contact id to be added to the admin contacts
        :param remove_admins: A list, tuple, or single contact id to be removed from the admin contacts
        :param add_techs: A list, tuple, or single contact id to be added to the tech contacts
        :param remove_techs: A list, tuple, or single contact id to be removed from the tech contacts
        :param add_billings: A list, tuple, or single contact id to add to the billing contacts
        :param remove_billings: A list, tuple, or single contact id to remove from the billing contacts
        :param add_statuses: List of statuses to be added to the domain name. The tuple must contain two
            elements. The first one will be the Status Code and the second element will be Descriptions.
        :param remove_statuses: A list of statuses to be removed from the domain name.
        :param add_hosts: A list of host names to be added to the domain name.
        :param remove_hosts: A list of host names to be removed from the domain name.
        :param password: A new password to replace the old password.
        :param add_dns_sec: A list of DSRecordData or single DSRecordData to add to the domain name.
        :param remove_dns_sec: A list of DSRecordData or single DSRecordData to remove from the domain name.
        :param remove_all_dns_sec: If True, removes all DNSSEC records from the domain name via <secDNS:all>.
        :param client_transaction_id: Client transaction id

        :return: Result object
        :rtype: EppResultData
        """
        # Issue #291 & RFC 5910 §4.2: <secDNS:rem> uses a choice between <secDNS:all> and <secDNS:dsData>.
        # Specifying both remove_dns_sec and remove_all_dns_sec is conflicting and invalid per schema.
        if remove_all_dns_sec and remove_dns_sec:
            raise ValueError(
                "Cannot specify both remove_dns_sec and remove_all_dns_sec."
            )

        # RFC 5731 §3.2.5: Normalize contact change lists using _normalize_contact_list
        # to accept single strings or sequences and prevent string-splitting character bugs in Jinja.
        add_admins = self._normalize_contact_list(add_admins)
        remove_admins = self._normalize_contact_list(remove_admins)
        add_techs = self._normalize_contact_list(add_techs)
        remove_techs = self._normalize_contact_list(remove_techs)
        add_billings = self._normalize_contact_list(add_billings)
        remove_billings = self._normalize_contact_list(remove_billings)

        add = bool(add_admins or add_techs or add_billings or add_statuses or add_hosts)
        remove = bool(
            remove_admins
            or remove_techs
            or remove_billings
            or remove_statuses
            or remove_hosts
        )
        change = bool(registrant or password)

        normalized_add_dns_sec = self._normalize_ds_records(add_dns_sec)
        normalized_remove_dns_sec = self._normalize_ds_records(remove_dns_sec)

        result = self.execute(
            DOMAIN_UPDATE_XML,
            add=add,
            remove=remove,
            change=change,
            domain_name=domain_name,
            add_admins=add_admins,
            remove_admins=remove_admins,
            add_techs=add_techs,
            remove_techs=remove_techs,
            add_billings=add_billings,
            remove_billings=remove_billings,
            add_statuses=add_statuses,
            remove_statuses=remove_statuses,
            add_hosts=add_hosts,
            remove_hosts=remove_hosts,
            password=password,
            registrant=registrant,
            add_dns_sec=normalized_add_dns_sec,
            remove_dns_sec=normalized_remove_dns_sec,
            remove_all_dns_sec=remove_all_dns_sec,
            client_transaction_id=client_transaction_id,
        )

        return result

    def restore(
        self, domain_name: str, client_transaction_id: Optional[str] = None
    ) -> EppResultData:
        """Restores a domain name that has been deleted.

        :param domain_name: Domain Name
        :param client_transaction_id: Client transaction id

        :return: Result object
        :rtype: EppResultData
        """
        result = self.execute(
            DOMAIN_RESTORE_XML,
            domain_name=domain_name,
            client_transaction_id=client_transaction_id,
        )

        return result

    def restore_report(
        self,
        domain_name: str,
        pre_data: str,
        post_data: str,
        delete_datetime: datetime,
        restore_datetime: datetime,
        restore_reason: str,
        statement_1: str,
        statement_2: str,
        other: Optional[str] = None,
        client_transaction_id: Optional[str] = None,
    ) -> EppResultData:
        """To send a domain restore report after sending restore reqest.

        :param domain_name: Domain Name
        :param pre_data: A copy of the registration data that existed for the domain name prior to the domain name
          being deleted. This parameter MAY contain both text and XML markup.
        :param post_data: A copy of the registration data that exists for the domain name at the time the restore
          report is submitted. This parameter MAY contain both text and XML markup.
        :param delete_datetime: The date and time when the domain name delete request was sent to the server.
        :param restore_datetime: The date and time when the original restore command was sent to the server.
        :param restore_reason: A brief explanation of the reason for restoring the domain name.
        :param statement_1: A text statement that the client has not restored the domain name in order to assume the
          rights to use or sell the domain name for itself or for any third party. Supporting information related to
          this statement MAY be supplied in the other parameter described below.
        :param statement_2: A text statement that the information in the restore report is factual to the best
          of the client's knowledge.
        :param other: Any information needed to support the statements provided by the client.
        :param client_transaction_id: Client transaction id

        :return: Result object
        :rtype: EppResultData
        """
        result = self.execute(
            DOMAIN_RESTORE_REPORT_XML,
            domain_name=domain_name,
            pre_data=pre_data,
            post_data=post_data,
            delete_datetime=delete_datetime.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            restore_datetime=restore_datetime.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            restore_reason=restore_reason,
            statement_1=statement_1,
            statement_2=statement_2,
            other=other,
            client_transaction_id=client_transaction_id,
        )

        return result
