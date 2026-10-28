"""
Utilities module
"""

import dataclasses
import re
import shutil
import textwrap
from typing import Optional, Any

from bs4 import BeautifulSoup
import click

OUTPUT_FILE = None

# Fields excluded when displaying the top-level EPP Envelope in table/TSV format
ENVELOPE_EXCLUDED_FIELDS = {"raw_response", "parsed_xml", "result_data"}

# Preferred logical order for top-level EPP Envelope fields
PREFERRED_ENVELOPE_ORDER = (
    "code",
    "message",
    "reason",
    "client_transaction_id",
    "server_transaction_id",
    "repository_object_id",
    "dry_run",
)


def _wrap_cell(text: str, width: int) -> list[str]:
    """Wrap a multiline string so each line fits within width without breaking hyphens."""
    cell_lines: list[str] = []
    for raw_line in text.splitlines():
        if not raw_line:
            cell_lines.append("")
        elif len(raw_line) <= width:
            cell_lines.append(raw_line)
        else:
            # Wrap long lines without breaking prematurely on hyphens (e.g. UUIDs, domain names)
            cell_lines.extend(
                textwrap.wrap(
                    raw_line,
                    width=width,
                    break_long_words=True,
                    break_on_hyphens=False,
                )
            )
    return cell_lines or [""]


def _calculate_table_widths(
    headers: list[str], rows: list[list[str]], budget: int
) -> list[int]:
    """Calculate column widths for a grid table fitting within budget."""
    num_cols = len(headers)
    longest = [
        max(len(headers[i]), max((len(l) for row in rows for l in str(row[i]).splitlines()), default=0))
        for i in range(num_cols)
    ]
    if sum(longest) <= budget:
        return longest

    min_widths = [len(h) for h in headers]
    effective_budget = max(sum(min_widths), budget)

    if num_cols == 2:
        # Reserve space for column 1 header before allocating column 0
        max_avail_0 = effective_budget - min_widths[1]
        col0_w = max(min_widths[0], min(longest[0], 25, max_avail_0))
        col1_w = max(min_widths[1], effective_budget - col0_w)
        return [col0_w, col1_w]

    if num_cols == 3:
        # Reserve space for subsequent column headers before allocating each column
        max_avail_0 = effective_budget - min_widths[1] - min_widths[2]
        col0_w = max(min_widths[0], min(longest[0], 30, max_avail_0))
        max_avail_1 = effective_budget - col0_w - min_widths[2]
        col1_w = max(min_widths[1], min(longest[1], 12, max_avail_1))
        col2_w = max(min_widths[2], effective_budget - col0_w - col1_w)
        return [col0_w, col1_w, col2_w]

    remaining = max(0, effective_budget - sum(min_widths))
    extra = remaining // num_cols
    return [mw + extra for mw in min_widths]


def _render_ascii_row(row: list[str], col_widths: list[int], num_cols: int) -> list[str]:
    """Render a single logical data row across one or more wrapped lines."""
    cell_lines_per_col = [
        _wrap_cell(str(row[c]) if row[c] is not None else "None", col_widths[c])
        for c in range(num_cols)
    ]
    row_height = max(len(lines) for lines in cell_lines_per_col)
    rendered_lines = []
    for line_idx in range(row_height):
        line_cells = [
            cell_lines_per_col[c][line_idx] if line_idx < len(cell_lines_per_col[c]) else ""
            for c in range(num_cols)
        ]
        rendered_lines.append(
            "| " + " | ".join(cell.ljust(col_widths[c]) for c, cell in enumerate(line_cells)) + " |"
        )
    return rendered_lines


def _render_ascii_table(
    headers: list[str],
    rows: list[list[str]],
    max_width: int,
    title: Optional[str] = None,
) -> str:
    """Render a matrix of headers and rows into an ASCII grid table with optional title."""
    if not headers or not rows:
        return ""

    num_cols = len(headers)
    overhead = 1 + (3 * num_cols)
    min_budget = sum(len(h) for h in headers)
    budget = max(min_budget, max_width - overhead)
    col_widths = _calculate_table_widths(headers, rows, budget)

    border = "+-" + "-+-".join("-" * w for w in col_widths) + "-+"
    header_row = "| " + " | ".join(h.ljust(w) for h, w in zip(headers, col_widths)) + " |"
    table_lines = [border, header_row, border]

    for row in rows:
        table_lines.extend(_render_ascii_row(row, col_widths, num_cols))

    table_lines.append(border)
    table_str = "\n".join(table_lines)
    if title:
        return f"[ {title} ]\n{table_str}"
    return table_str


def format_tsv_value(val: Any) -> str:
    """Format a single field value for TSV output.

    Escapes newlines and tabs to guarantee each field is represented on a single row.
    """
    if val is None:
        val_str = "None"
    elif isinstance(val, (bool, int, float)):
        val_str = str(val)
    elif isinstance(val, str):
        val_str = val
    else:
        val_str = str(val)

    return val_str.replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")


def _render_tsv_section(
    headers: list[str],
    rows: list[list[str]],
) -> str:
    """Render headers and rows as tab-separated values (TSV)."""
    lines = ["\t".join(headers)]
    for row in rows:
        cleaned_cells = [format_tsv_value(cell) for cell in row]
        lines.append("\t".join(cleaned_cells))
    return "\n".join(lines)


def _format_envelope_fields(result: Any) -> list[list[str]]:
    """Extract (Field, Value) rows for top-level EPP Envelope table/TSV."""
    if dataclasses.is_dataclass(result):
        all_field_names = [
            f.name for f in dataclasses.fields(result) if f.name not in ENVELOPE_EXCLUDED_FIELDS
        ]
    elif hasattr(result, "__dict__"):
        all_field_names = [
            k for k in result.__dict__ if k not in ENVELOPE_EXCLUDED_FIELDS
        ]
    else:
        return []

    ordered_names = [f for f in PREFERRED_ENVELOPE_ORDER if f in all_field_names]
    ordered_names.extend([f for f in all_field_names if f not in ordered_names])

    rows = []
    for name in ordered_names:
        val = getattr(result, name, None)
        rows.append([name, str(val) if val is not None else "None"])
    return rows


def _is_check_dict(data: Any) -> bool:
    """Check if data structure is a check command dictionary mapping entities to availability."""
    if not isinstance(data, dict) or not data:
        return False
    return all(isinstance(v, dict) and "avail" in v for v in data.values())


def _format_check_data(data: dict) -> tuple[str, list[str], list[list[str]]]:
    """Format check command results into (title, headers, rows)."""
    rows = []
    for entity, details in data.items():
        avail_str = "Yes" if details.get("avail") else "No"
        reason = details.get("reason")
        reason_str = str(reason) if reason is not None else "None"
        rows.append([str(entity), avail_str, reason_str])
    return "Check Results", ["Entity", "Available", "Reason"], rows


def _format_postal_info(postal: Any) -> str:
    """Format PostalInfoData into readable multiline string."""
    parts = []
    if getattr(postal, "name", None):
        parts.append(f"Name: {postal.name}")
    if getattr(postal, "organization", None):
        parts.append(f"Org: {postal.organization}")
    addr = getattr(postal, "address", None)
    if addr:
        streets = [
            s for s in (
                getattr(addr, "street_1", None),
                getattr(addr, "street_2", None),
                getattr(addr, "street_3", None),
            ) if s
        ]
        if streets:
            parts.append(f"Street: {', '.join(streets)}")
        loc = [
            p for p in (
                getattr(addr, "city", None),
                getattr(addr, "province", None),
                getattr(addr, "postal_code", None),
                getattr(addr, "country_code", None),
            ) if p
        ]
        if loc:
            parts.append(f"Location: {', '.join(loc)}")
    return "\n".join(parts) if parts else "None"


def _format_dnssec(dns_sec: Any) -> str:
    """Format list of DSRecordData into readable multiline string."""
    if not isinstance(dns_sec, list) or not dns_sec:
        return "None"
    lines = []
    for ds in dns_sec:
        alg = getattr(getattr(ds, "algorithm", None), "name", str(getattr(ds, "algorithm", "")))
        dtype = getattr(getattr(ds, "digest_type", None), "name", str(getattr(ds, "digest_type", "")))
        key_tag = getattr(ds, "key_tag", "")
        digest = getattr(ds, "digest", "")
        lines.append(f"KeyTag: {key_tag}, Alg: {alg}, DigestType: {dtype}, Digest: {digest}")
    return "\n".join(lines)


def _format_list_field(field_name: str, val: list) -> str:
    """Format a list-based entity field into a string."""
    if not val:
        return "None"
    if field_name == "address":
        return "\n".join(
            f"{getattr(a, 'address', a)} ({getattr(a, 'ip', '')})" if hasattr(a, "ip") else str(a)
            for a in val
        )
    if field_name == "messages":
        return "\n".join(
            f"[{getattr(m, 'language', '')}] {getattr(m, 'message', m)}"
            for m in val
        )
    if field_name in ("host", "nameservers"):
        return "\n".join(str(item) for item in val)
    return ", ".join(str(item) for item in val)


def _format_entity_field_value(field_name: str, val: Any) -> str:
    """Format an entity field value into human-readable string for table display."""
    if val is None or val == "":
        return "None"
    if field_name == "postal_info":
        return _format_postal_info(val)
    if field_name == "dns_sec":
        return _format_dnssec(val)
    if isinstance(val, list):
        return _format_list_field(field_name, val)
    return str(val)


def _format_domain_data(data: Any) -> tuple[str, list[str], list[list[str]]]:
    """Format DomainData into (title, headers, rows)."""
    title = (
        f"Domain Information: {data.domain_name}"
        if getattr(data, "domain_name", None)
        else "Domain Information"
    )
    order = (
        "domain_name",
        "registrant",
        "admin",
        "tech",
        "billing",
        "status",
        "host",
        "create_date",
        "expiry_date",
        "update_date",
        "transfer_date",
        "dns_sec",
    )
    rows = []
    for name in order:
        val = getattr(data, name, None)
        label = "nameservers" if name == "host" else name
        rows.append([label, _format_entity_field_value(name, val)])
    return title, ["Property", "Value"], rows


def _format_contact_data(data: Any) -> tuple[str, list[str], list[list[str]]]:
    """Format ContactData into (title, headers, rows)."""
    title = (
        f"Contact Information: {data.id}"
        if getattr(data, "id", None)
        else "Contact Information"
    )
    order = (
        "id",
        "email",
        "postal_info",
        "phone",
        "fax",
        "status",
        "privacy",
        "create_date",
        "create_client_id",
        "update_date",
        "update_client_id",
    )
    rows = []
    for name in order:
        val = getattr(data, name, None)
        rows.append([name, _format_entity_field_value(name, val)])
    return title, ["Property", "Value"], rows


def _format_host_data(data: Any) -> tuple[str, list[str], list[list[str]]]:
    """Format HostData into (title, headers, rows)."""
    title = (
        f"Host Information: {data.host_name}"
        if getattr(data, "host_name", None)
        else "Host Information"
    )
    order = ("host_name", "address", "status", "create_date", "update_date")
    rows = []
    for name in order:
        val = getattr(data, name, None)
        rows.append([name, _format_entity_field_value(name, val)])
    return title, ["Property", "Value"], rows


def _format_generic_data(data: Any) -> tuple[str, list[str], list[list[str]]]:
    """Format any generic dataclass, dict, or object into (title, headers, rows)."""
    if dataclasses.is_dataclass(data):
        title = f"{type(data).__name__}"
        rows = [
            [f.name, _format_entity_field_value(f.name, getattr(data, f.name))]
            for f in dataclasses.fields(data)
        ]
        return title, ["Property", "Value"], rows

    if isinstance(data, dict):
        title = "Result Data"
        rows = [
            [str(k), _format_entity_field_value(str(k), v)]
            for k, v in data.items()
        ]
        return title, ["Property", "Value"], rows

    return "Result Data", ["Property", "Value"], [["result_data", str(data)]]


def _extract_subtable_info(
    data: Any,
) -> Optional[tuple[str, list[str], list[list[str]]]]:
    """Extract (title, headers, rows) for the payload sub-table based on data type."""
    if data is None:
        return None

    if _is_check_dict(data):
        return _format_check_data(data)

    class_name = type(data).__name__
    if class_name == "DomainData":
        return _format_domain_data(data)
    if class_name == "ContactData":
        return _format_contact_data(data)
    if class_name == "HostData":
        return _format_host_data(data)

    return _format_generic_data(data)


def _get_response_soup(result: Any) -> Optional[BeautifulSoup]:
    """Get parsed BeautifulSoup instance from result, parsing raw_response if needed."""
    soup = getattr(result, "parsed_xml", None)
    if isinstance(soup, BeautifulSoup):
        return soup
    raw = getattr(result, "raw_response", None)
    if raw and isinstance(raw, (str, bytes)):
        try:
            return BeautifulSoup(raw, "xml")
        except Exception:  # pylint: disable=broad-exception-caught
            return None
    return None


def _format_container_title(name: str) -> str:
    """Format an XML payload container tag name into a table title."""
    titles = {
        "renData": "Renew Data",
        "trnData": "Transfer Data",
        "creData": "Create Data",
        "panData": "Pending Action Data",
        "infData": "Info Data",
        "chkData": "Check Data",
        "delData": "Delete Data",
    }
    if name in titles:
        return titles[name]
    if name.endswith("Data"):
        return f"{name[:-4].capitalize()} Data"
    return f"{name.capitalize()} Data"


def _extract_res_data(
    result: Any,
) -> Optional[tuple[str, list[str], list[list[str]]]]:
    """Extract sub-table information from undecoded resData in XML response."""
    soup = _get_response_soup(result)
    if soup is None:
        return None

    res_data = soup.find(re.compile(r"(^|:)resData$"))
    if not res_data:
        return None

    containers = [
        child for child in res_data.find_all(recursive=False)
        if hasattr(child, "name") and child.name
    ]
    if not containers:
        return None

    container = containers[0]
    children = [
        c for c in container.find_all(recursive=False)
        if hasattr(c, "name") and c.name
    ]
    if not children or any(c.find_all(recursive=False) for c in children):
        return None

    local_name = container.name.split(":")[-1]
    title = _format_container_title(local_name)

    rows = [
        [child.name.split(":")[-1], child.get_text().strip()]
        for child in children
    ]

    return title, ["Property", "Value"], rows


def _has_undecoded_payload(result: Any) -> bool:
    """Check if result contains an XML payload that was not decoded into result_data."""
    if (
        not hasattr(result, "code")
        or getattr(result, "result_data", None) is not None
        or getattr(result, "dry_run", False)
    ):
        return False

    soup = _get_response_soup(result)
    if soup is None:
        return False

    for tag in ("resData", "extension"):
        element = soup.find(re.compile(rf"(^|:){tag}$"))
        if element and any(
            hasattr(c, "name") and c.name for c in element.find_all(recursive=False)
        ):
            return True

    return False


def format_table(result: Any, max_width: Optional[int] = None) -> Optional[str]:
    """Format EppResultData into Master EPP Envelope table and optional payload Sub-table.

    :param result: The EppResultData object to format.
    :param max_width: Optional maximum table width. If not provided, dynamically checks
        terminal width (fallback to 80 columns).
    :return: Formatted table string, or None if the response contains an undecoded XML
        payload that cannot be represented in tabular form (signaling XML fallback).
    """
    term_width = (
        max_width
        if max_width is not None
        else shutil.get_terminal_size(fallback=(80, 24)).columns
    )
    term_width = max(term_width, 40)

    envelope_rows = _format_envelope_fields(result)
    if not envelope_rows:
        return ""

    master_table = _render_ascii_table(
        headers=["Field", "Value"],
        rows=envelope_rows,
        max_width=term_width,
        title="EPP Response",
    )
    tables = [master_table]

    result_data = getattr(result, "result_data", None)
    if result_data is not None:
        sub_info = _extract_subtable_info(result_data)
        if sub_info:
            sub_title, sub_headers, sub_rows = sub_info
            sub_table = _render_ascii_table(
                headers=sub_headers,
                rows=sub_rows,
                max_width=term_width,
                title=sub_title,
            )
            tables.append(sub_table)
    else:
        # result_data is None: decode XML payload if present (e.g. renew or transfer resData)
        sub_info = _extract_res_data(result)
        if sub_info:
            sub_title, sub_headers, sub_rows = sub_info
            sub_table = _render_ascii_table(
                headers=sub_headers,
                rows=sub_rows,
                max_width=term_width,
                title=sub_title,
            )
            tables.append(sub_table)
        elif _has_undecoded_payload(result):
            # XML payload could not be decoded into a table; return None to trigger XML fallback
            return None

    return "\n\n".join(tables)


def format_tsv(result: Any) -> Optional[str]:
    """Format EppResultData into Master EPP Envelope TSV and optional payload Sub-table TSV.

    :param result: The EppResultData object to format.
    :return: Formatted TSV string, or None if the response contains an undecoded XML
        payload that cannot be represented in TSV form (signaling XML fallback).
    """
    envelope_rows = _format_envelope_fields(result)
    if not envelope_rows:
        return ""

    sections = [_render_tsv_section(headers=["Field", "Value"], rows=envelope_rows)]

    result_data = getattr(result, "result_data", None)
    if result_data is not None:
        sub_info = _extract_subtable_info(result_data)
        if sub_info:
            _, sub_headers, sub_rows = sub_info
            sections.append(_render_tsv_section(headers=sub_headers, rows=sub_rows))
    else:
        # result_data is None: decode XML payload if present (e.g. renew or transfer resData)
        sub_info = _extract_res_data(result)
        if sub_info:
            _, sub_headers, sub_rows = sub_info
            sections.append(_render_tsv_section(headers=sub_headers, rows=sub_rows))
        elif _has_undecoded_payload(result):
            # XML payload could not be decoded into TSV; return None to trigger XML fallback
            return None

    return "\n\n".join(sections)


def echo(
    message: Optional[Any] = None,
    new_line: bool = True,
    err: bool = False,
    color: Optional[bool] = None,
) -> None:
    """

    :param message: The string or bytes to output. Other objects are
        converted to strings.
    :param err: Write to ``stderr`` instead of ``stdout``.
    :param new_line: Print a newline after the message. Enabled by default.
    :param color: Force showing or hiding colors and other styles. By
        default, Click will remove color if the output does not look like
        an interactive terminal.
    """
    # Convert the string to bytes if writing to a file
    if OUTPUT_FILE:
        if message is None:
            message = b""
        elif isinstance(message, str):
            message = message.encode("utf-8")
        elif not isinstance(message, (bytes, bytearray)):
            message = str(message).encode("utf-8")

    click.echo(message, file=OUTPUT_FILE, nl=new_line, err=err, color=color)
