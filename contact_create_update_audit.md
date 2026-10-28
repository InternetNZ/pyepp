# In-Depth Forensic Audit: Contact Create & Update Logic

This document details the bugs, RFC 5733 schema violations, and edge cases discovered during a forensic audit of `pyepp/contact.py`, `pyepp/command_templates.py`, `pyepp/base_command.py`, and `pyepp/cli/contact.py`.

---

## Summary Checklist

| # | Severity | Issue | Impact |
|---|---|---|---|
| **1** | **Critical** | `s={{ add_status }}` unquoted in `CONTACT_UPDATE_XML` | Fatal XML syntax error; rejected by all XML/EPP parsers. |
| **2** | **High** | Unconditional `<contact:chg>` in `CONTACT_UPDATE_XML` | Status-only updates emit empty `<contact:chg>`, causing EPP 2005 schema error. |
| **3** | **High** | Double XML escaping in `BaseCommand` | Characters like `&` and `<` in names, addresses, and passwords become `&amp;amp;`. |
| **4** | **Medium** | No validation for zero-modification `contact.update()` | Sends empty `<contact:update>` violating RFC 5733 §3.2.5. |
| **5** | **Medium** | Missing `email` validation in `Contact.create()` | Emits `<contact:email></contact:email>` violating RFC 5733 schema. |
| **6** | **Low** | Missing `privacy` field on `ContactData` | Prevents callers from using the `<contact:disclose>` feature. |

---

## 1. [CRITICAL] Unquoted XML Attributes in `CONTACT_UPDATE_XML`

### Location
`pyepp/command_templates.py`, lines 139 and 144:
```jinja2
        {% if add_status %}
        <contact:add>
            <contact:status s={{ add_status }}/>
        </contact:add>
        {% endif %}
        {% if remove_status %}
        <contact:rem>
            <contact:status s={{ remove_status }}/>
        </contact:rem>
        {% endif %}
```

### Bug & Impact
* In XML 1.0, all attribute values must be enclosed in matching quotes (`attribute="value"`).
* Passing `add_status="clientHold"` currently renders:
  ```xml
  <contact:status s=clientHold/>
  ```
* Strict XML parsers (including `lxml`, Python `xml.etree.ElementTree`, and standard EPP registry backends) fail immediately with fatal XML syntax errors:
  * `xml.etree.ElementTree.ParseError: not well-formed (invalid token)`
  * `lxml.etree.XMLSyntaxError: AttValue: " or ' expected`
* Note that `domain:status` and `host:status` in `pyepp/command_templates.py` correctly quote their attributes (`s="{{ status }}"` and `s="{{ s }}"`).

### Recommended Fix
Add double quotes around `{{ add_status }}` and `{{ remove_status }}`:
```jinja2
        {% if add_status %}
        <contact:add>
            <contact:status s="{{ add_status }}"/>
        </contact:add>
        {% endif %}
        {% if remove_status %}
        <contact:rem>
            <contact:status s="{{ remove_status }}"/>
        </contact:rem>
        {% endif %}
```

---

## 2. [HIGH] Unconditional `<contact:chg>` Emitted on Status-Only Updates

### Location
`pyepp/command_templates.py`, line 147:
```jinja2
        <contact:chg>
         {% if postalinfo_change %}
         ...
         {% endif %}
         {% if phone %} <contact:voice>{{ phone }}</contact:voice> {% endif %}
         {% if fax %} <contact:fax>{{ fax }}</contact:fax> {% endif %}
         {% if email %} <contact:email>{{ email }}</contact:email> {% endif %}
         {% if password %}...{% endif %}
         {% if privacy %}...{% endif %}
        </contact:chg>
```

### Bug & Impact
* Under **RFC 5733 §3.2.5** and XML schema definition (`contact:updateType`):
  * At least one of `<contact:add>`, `<contact:rem>`, or `<contact:chg>` must be present.
  * If `<contact:chg>` is present, it **must contain at least one child element** (an empty `<contact:chg></contact:chg>` is schema-invalid).
* If a caller invokes a status-only update:
  ```python
  contact.update(ContactData(id="contact-1"), add_status="clientHold")
  ```
  PyEPP emits:
  ```xml
  <contact:update>
    <contact:id>contact-1</contact:id>
    <contact:add><contact:status s="clientHold"/></contact:add>
    <contact:chg>
    </contact:chg>
  </contact:update>
  ```
* The empty `<contact:chg>` block causes schema validation failure with EPP error `2005` (*Parameter value syntax error*).
* Note: `DOMAIN_UPDATE_XML` in the same file already wraps `<domain:chg>` conditionally with `{% if change %}`.

### Recommended Fix
Make `<contact:chg>` conditional in `CONTACT_UPDATE_XML`:
```jinja2
        {% if postalinfo_change or phone or fax or email or password or privacy %}
        <contact:chg>
         ...
        </contact:chg>
        {% endif %}
```

---

## 3. [HIGH] Double XML Escaping Corrupting Names, Addresses, and Passwords

### Location
`pyepp/base_command.py`, line 79 & `pyepp/command_templates.py`, line 577:
```python
# pyepp/base_command.py
kwargs = {key: value for key, value in kwargs.items() if value is not None}
new_kwargs = self.__escape_dict(kwargs)  # <-- Manual escape (e.g. & -> &amp;)
template = self._get_compiled_template(cmd)
xml = template.render(**new_kwargs)       # <-- Jinja2 autoescape (e.g. &amp; -> &amp;amp;)
```
And:
```python
# pyepp/command_templates.py
_JINJA_ENV = Environment(
    loader=DictLoader(TEMPLATES),
    autoescape=True,  # <-- Jinja2 autoescape enabled
    ...
)
```

### Bug & Impact
* String parameters undergo double XML escaping:
  1. `BaseCommand.__escape_dict` uses `xml.sax.saxutils.escape()` (transforms `A & B` $\rightarrow$ `A &amp; B`).
  2. Jinja2 with `autoescape=True` automatically escapes raw strings again (transforms `A &amp; B` $\rightarrow$ `A &amp;amp; B`).
* Example: Creating a contact with password `Pass<word>&1` emits:
  ```xml
  <contact:pw>Pass&amp;lt;word&amp;gt;&amp;amp;1</contact:pw>
  ```
* When the registry unescapes the XML, the password stored is `Pass&lt;word&amp;1`, permanently desynchronizing credentials and corrupting contact names containing ampersands.

### Recommended Fix
Either:
1. Mark the output strings in `__escape_dict` with `jinja2.Markup` so Jinja2 skips re-escaping, **OR**
2. Remove `__escape_dict` entirely and let Jinja2's native `autoescape=True` handle variable escaping safely.

---

## 4. [MEDIUM] Zero-Modification Update Command Not Validated

### Location
`pyepp/contact.py`, line 380 (`Contact.update`)

### Bug & Impact
* Calling `contact.update(ContactData(id="contact-1"))` with no status additions, no status removals, and no contact details currently proceeds without error.
* Once `<contact:chg>` is made conditional (Issue #2), this payload renders:
  ```xml
  <contact:update>
    <contact:id>contact-1</contact:id>
  </contact:update>
  ```
* RFC 5733 §3.2.5 mandates: *"At least one `<contact:add>`, `<contact:rem>`, or `<contact:chg>` element MUST be provided."*
* The client should validate this upfront and raise `ValueError` rather than transmitting an invalid no-op command.

### Recommended Fix
In `Contact.update()`:
```python
        has_chg = bool(
            contact.postal_info
            or contact.phone
            or contact.fax
            or contact.email
            or contact.password
        )
        if not (add_status or remove_status or has_chg):
            raise ValueError(
                "Contact update requires at least one change (postal_info, phone, fax, email, password) or status modification."
            )
```

---

## 5. [MEDIUM] Missing `email` Validation in `Contact.create()`

### Location
`pyepp/contact.py`, lines 315–335 (`Contact.create`)

### Bug & Impact
* In RFC 5733 §3.2.1 and §4, `<contact:email>` is mandatory for contact creation (`type="eppcom:minTokenType"`, `minLength="1"`).
* `Contact.create()` validates `contact.postal_info`, `contact.postal_info.name`, `city`, and `country_code`, but does not validate `contact.email`.
* If a caller instantiates `ContactData(id="...", postal_info=...)` without passing `email`, it defaults to `""`, emitting:
  ```xml
  <contact:email></contact:email>
  ```
  which violates the schema's `minLength="1"` constraint and triggers EPP `2005`.

### Recommended Fix
In `Contact.create()`:
```python
        if not contact.email:
            raise ValueError("Contact creation requires 'email'.")
```

---

## 6. [LOW] Missing `privacy` Field on `ContactData`

### Location
`pyepp/command_templates.py`, lines 105 & 175

### Observation
* Both `CONTACT_CREATE_XML` and `CONTACT_UPDATE_XML` support disclosure elements:
  ```jinja2
  {% if privacy %}
  <contact:disclose flag="0">
    {% for element in privacy %}
    <contact:{{ element }}/>
    {% endfor %}
  </contact:disclose>
  {% endif %}
  ```
* However, `ContactData` in `pyepp/contact.py` does not define `privacy: Optional[list[str]] = None`.
* Any caller attempting to configure disclosure preferences via `ContactData(..., privacy=["voice", "email"])` receives a Python `TypeError: ContactData.__init__() got an unexpected keyword argument 'privacy'`.

### Recommended Fix
Add `privacy: Optional[list[str]] = None` to the `ContactData` dataclass.
