# PyEPP
> A Python API on top of EPP protocol to work with registry systems.

This a Python API on [EPP](https://en.wikipedia.org/wiki/Extensible_Provisioning_Protocol) protocol to connect to
any registry systems that support EPP and work with it. It supports bellow RFCs:
- [RFC 5730 - Extensible Provisioning Protocol](https://datatracker.ietf.org/doc/html/rfc5730)
- [RFC 5731 - Domain Name Mapping](https://datatracker.ietf.org/doc/html/rfc5731)
- [RFC 5732 - Host Mapping](https://datatracker.ietf.org/doc/html/rfc5732)
- [RFC 5733 - Contact Mapping](https://datatracker.ietf.org/doc/html/rfc5733)
- [RFC 5734 - Transport over TCP](https://datatracker.ietf.org/doc/html/rfc5734)

>This is an early version and not stable yet. Please use with care.

## Installation

```sh
pip install pyepp
```

## Usage example

```python
from datetime import date

from pyepp import EppCommunicator
from pyepp.domain import Domain, DomainData, DSRecordData, DNSSECAlgorithm, DigestTypeEnum
from pyepp.contact import Contact, ContactData, PostalInfoData, AddressData

config = {
    "server": "epp.test.net.nz",
    "port": "700",
    "client_cert": "/PATH/TO/YOUR/CLIENT_CERTIFICATE.crt",
    "client_key": "/PATH/TO/YOUR/CLIENT_KEY.pem"
}

epp = EppCommunicator(**config)

connect = epp.connect()
login = epp.login("user_name", "password")
# Sends a hello request and receive greeting in respond
hello = epp.hello()

contact = Contact(epp)

# Check contacts availability
contact_check = contact.check(['contact-1', 'contact-2'])

# Create a new contact
contact_create_params = ContactData(
    id='contact-1',
    email='epp@example.net.nz',
    postal_info=PostalInfoData(
        name='Registrar 1',
        organization='Registrar 1',
        address=AddressData(
            street_1='18 Registrar Street',
            street_2='Registrar CBD',
            city='Registrar',
            country_code='NZ',
            province='Registrar',
            postal_code='6011'
        ),
    ),
    phone='+64.111111111'
)
contact_create = contact.create(contact_create_params)

# Get contact details
contact_info = contact.info('contact-1')

domain = Domain(epp)
# Check domains availability
domain_check = domain.check(['domain1.nz', 'domain2.nz'])

# Create a new domain name
domain_create_params = DomainData(
    domain_name='example.nz',
    registrant='contact-1',
    admin='contact-1',
    tech='contact-1',
    billing='contact-3',
    period=3,
    host=['01y.test-indwrx2vkicn2otgm3otav5wpnzvjd.co.nz', '0d9x6239.example.co.nz'],
    dns_sec=DSRecordData(
        key_tag=1235,
        algorithm=DNSSECAlgorithm.DSA_SHA_1.value,
        digest_type=DigestTypeEnum.SHA_1.value,
        digest='8cdb09364147aed879d12c68d615f98af5900b73'
    ),
)
domain_create = domain.create(domain_create_params)

# Renew a domain name
renew_domain = domain.renew(domain_name='example-1.nz', expiry_date=date(2024, 2, 23), period=2)
```

## PyEPP CLI
PyEPP also has a command line interface that allows the user to interact with the registry system.

```text
Usage: pyepp [OPTIONS] COMMAND [ARGS]...

  A command line interface to work with PyEpp library.

Options:
  --server TEXT                   [required]
  --port TEXT                     [required]
  --client-cert TEXT              [required]
  --client-key TEXT               [required]
  --user TEXT                     [required]
  --password TEXT                 [required]
  -o, --output-format [XML|OBJECT|MIN]
                                  [default: XML]
  --no-pretty
  --dry-run
  -f, --file FILENAME             If provided, the output will be written in
                                  the file.
  -v, --verbose
  -d, --debug
  --version                       Show the version and exit.
  -h, --help                      Show this message and exit.

Commands:
  contact  To work with Contact objects in the registry.
  domain   To work with Domain name objects in the registry.
  host     To work with Host objects in the registry.
  poll     To manage registry service messages.
  run      Receive an XML file containing an EPP XML command and execute it.
```

## Development setup
Clone this project. It's recommended to create virtual environment. Then install the dependencies and 
development dependencies:

```shell
pip install -r requirements.txt
pip install -r requirements.dev.txt
```

Before creating any pull requests please make sure your code lints and there is no security issues in your code 
by running below scripts:

```shell
./scripts/linter.sh
./scripts/code-security-check.sh
```

Happy developing!
## Contributing
Please refer to [CONTRIBUTING.md](CONTRIBUTING.md)

<!-- Markdown link & img dfn's -->
[wiki]: https://github.com/internetnz/pyepp/wiki
