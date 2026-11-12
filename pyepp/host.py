"""
Host Mapping Module. This module is used to manage host objects in Registry.
A host object represents a Domain Name System (DNS) server that resolves domain names into IP addresses.
"""

from dataclasses import dataclass, asdict
from typing import Optional

from pyepp.epp import EppResultData
from pyepp.base_command import BaseCommand
from pyepp.command_templates import (
    HOST_CHECK_XML,
    HOST_INFO_XML,
    HOST_CREATE_XML,
    HOST_DELETE_XML,
    HOST_UPDATE_XML,
)
from pyepp.epp import EppResultCode


@dataclass
class IPAddressData:
    """IP Address data class."""

    address: str
    # pylint: disable=invalid-name
    ip: str


@dataclass
class HostData:
    """Host object data class."""

    host_name: str
    address: Optional[list[IPAddressData]] = None
    status: Optional[list[str]] = None
    create_date: Optional[str] = ""
    create_client_id: Optional[str] = ""
    update_client_id: Optional[str] = ""
    update_date: Optional[str] = ""


class Host(BaseCommand):
    """
    Epp Host object class. This class is used to create and manage host objects in Registry.

    An EPP host object has attributes and associated values that can be viewed and modified by the sponsoring
    Registrar. When you create or update a host, you must follow the rules that ensure that the domain name can still
    be resolved even if there is an outage of any individual host or network. This means that two or more unique name
    servers must be defined for each protocol in use. Although you can use the IPv4 and IPv6 protocols concurrently,
    they are not interchangeable or compatible. As a result, to use both protocols requires that you must provide data
    for two unique name servers that are accessible by IPv4 and two unique name servers that are accessible by IPv6.
    """

    def _data_to_dict(self, data: HostData) -> dict:
        """Convert a host dataclass to a dictionary.

        :param data: Host name details

        :return: Host name details
        :rtype: dict
        """
        data_dict = asdict(data)

        return data_dict

    def check(
        self, host_names: list[str], client_transaction_id: Optional[str] = None
    ) -> EppResultData:
        """A successful Host Check request determines whether a host is available for use and whether a host can be
        created in the Registry. A single request can check from 1 to 15 host names.

        :param host_names: List of domain names
        :param client_transaction_id: Client transaction id

        :return: Result object
        :rtype: EppResultData
        """
        result = self.execute(
            HOST_CHECK_XML,
            host_names=host_names,
            client_transaction_id=client_transaction_id,
        )

        # In dry-run mode or on error, skip XML payload parsing since there is no response payload
        if int(result.code) != int(EppResultCode.SUCCESS.value) or result.dry_run:
            return result

        raw_response = result.parsed_xml
        # Scope XML parsing to <resData> / <host:chkData> per RFC 5732 §3.1.1
        # to prevent <cd> elements in <extension> blocks from colliding or crashing.
        res_data = raw_response.find("resData")
        chk_el = (
            (res_data.find("chkData") or res_data)
            if res_data
            else (raw_response.find("chkData") or raw_response)
        )
        hosts_check_data = chk_el.find_all("cd")

        result_data = {}
        for host_cd in hosts_check_data:
            host_name_el = host_cd.find("name")
            if not host_name_el:
                continue
            available = host_name_el.get("avail") in ("true", "1")
            # RFC 5732 §3.1.1: <host:reason> is OPTIONAL even when avail="0"/"false".
            # Safely check that the <reason> node exists before accessing .text to
            # prevent AttributeError crashes on registries that omit reason.
            reason_el = host_cd.find("reason")
            reason = (
                reason_el.text
                if (not available and reason_el is not None)
                else None
            )
            result_data[host_name_el.text] = {
                "avail": available,
                "reason": reason,
            }

        result["result_data"] = result_data

        return result

    def info(
        self, host_name: str, client_transaction_id: Optional[str] = None
    ) -> EppResultData:
        """A successful Host Info request retrieves detailed host information.

        :param host_name: Host name
        :param client_transaction_id: Client transaction id

        :return: Result object
        :rtype: EppResultData
        """
        result = self.execute(
            HOST_INFO_XML,
            host_name=host_name,
            client_transaction_id=client_transaction_id,
        )

        # In dry-run mode or on error, skip XML payload parsing since there is no response payload
        if int(result.code) != int(EppResultCode.SUCCESS.value) or result.dry_run:
            return result

        raw_response = result.parsed_xml

        # Scope XML parsing to <resData> / <host:infData> per RFC 5732 §3.1.2 to avoid
        # data corruption from colliding tags (e.g. status, name, crDate) in other sections.
        res_data = raw_response.find("resData")
        info_el = (
            (res_data.find("infData") or res_data)
            if res_data
            else (raw_response.find("infData") or raw_response)
        )

        name_el = info_el.find("name")
        cr_date_el = info_el.find("crDate")
        cr_id_el = info_el.find("crID")
        up_id_el = info_el.find("upID")
        up_date_el = info_el.find("upDate")

        result_data = {
            "host_name": name_el.text if name_el else "",
            "status": [
                status.get("s") or status.text
                for status in info_el.find_all("status")
            ],
            "address": (
                [
                    IPAddressData(address=addr.text, ip=addr.get("ip"))
                    for addr in info_el.find_all("addr")
                ]
                if info_el.find("addr")
                else None
            ),
            "create_date": cr_date_el.text if cr_date_el else None,
            "create_client_id": cr_id_el.text if cr_id_el else None,
            "update_client_id": up_id_el.text if up_id_el else None,
            "update_date": up_date_el.text if up_date_el else None,
        }

        result["result_data"] = HostData(**result_data)

        return result

    def create(
        self, host: HostData, client_transaction_id: Optional[str] = None
    ) -> EppResultData:
        """A successful Host Create request creates a host object identified by its name in the Registry.

        :param host: Contact
        :param client_transaction_id: Client transaction id

        :return: Result object
        :rtype: EppResultData
        """
        params = self._data_to_dict(host)
        params["client_transaction_id"] = client_transaction_id

        result = self.execute(HOST_CREATE_XML, **params)

        return result

    def delete(
        self, host_name: str, client_transaction_id: Optional[str] = None
    ) -> EppResultData:
        """A successful Host Delete request deletes a host object.
        Warning: A host object cannot be deleted while it is associated with a domain object.

        :param host_name: Host Name
        :param client_transaction_id: Client transaction id

        :return: Result object
        :rtype: EppResultData
        """
        result = self.execute(
            HOST_DELETE_XML,
            host_name=host_name,
            client_transaction_id=client_transaction_id,
        )

        return result

    # pylint: disable=too-many-arguments
    def update(
        self,
        host_name: str,
        add_ip_address: Optional[list[IPAddressData]] = None,
        remove_ip_address: Optional[list[IPAddressData]] = None,
        add_status: Optional[list[str]] = None,
        remove_status: Optional[list[str]] = None,
        new_host_name: Optional[str] = None,
        client_transaction_id: Optional[str] = None,
    ) -> EppResultData:
        """The EPP <update> command provides a transform operation that allows a client to modify the attributes of a
        host object.

        :param host_name: Host Name
        :param add_ip_address: A list of IP addressed to be added to the host
        :param remove_ip_address: A list of IP addressed to be removed from the host
        :param add_status: A list of status to be added to the host
        :param remove_status: A list of status to be removed from host
        :param new_host_name: The host name will be changed to this new host name
        :param client_transaction_id: Client transaction id

        :return: Result object
        :rtype: EppResultData
        """

        add = bool(add_ip_address or add_status)
        remove = bool(remove_ip_address or remove_status)
        change = bool(new_host_name)

        result = self.execute(
            HOST_UPDATE_XML,
            host_name=host_name,
            add=add,
            remove=remove,
            change=change,
            add_ip_address=add_ip_address,
            remove_ip_address=remove_ip_address,
            add_status=add_status,
            remove_status=remove_status,
            new_host_name=new_host_name,
            client_transaction_id=client_transaction_id,
        )

        return result
