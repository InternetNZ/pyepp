# PyEPP Project Context & Agent Guidelines

PyEPP is a Python library and CLI tool for interacting with domain registries using the Extensible Provisioning Protocol (EPP). It provides a high-level API for managing contacts, domains (including DNSSEC and RGP restore), hosts, and poll messages, while abstracting XML communication and TCP/TLS transport.

## Agent Guidelines & Tenets

All AI coding agents working on PyEPP must adhere to these core rules:
- **Simplicity First:** Write the minimum code necessary to solve the problem. Avoid speculative features, premature abstractions, or over-engineering.
- **Surgical Changes:** Modify only what is strictly required. Do not refactor unrelated code, reformat untouched files, or adjust unrelated imports.
- **Logic Changes & Inline Comments:** Whenever modifying existing logic or introducing new logic in the codebase, clearly explain the change, the reasoning behind it, and any handled edge cases using clear comments directly in the code.
- **Verify Before Completion:** Always verify modifications using the project QA scripts (`./scripts/tests.sh`, `./scripts/linter.sh`, `./scripts/code-security-check.sh`, `./scripts/package-audit.sh`).

## Supported Specifications

- [RFC 3915 - Domain Registry Grace Period (RGP) Mapping](https://datatracker.ietf.org/doc/html/rfc3915)
- [RFC 5730 - Extensible Provisioning Protocol (EPP)](https://datatracker.ietf.org/doc/html/rfc5730)
- [RFC 5731 - Domain Name Mapping](https://datatracker.ietf.org/doc/html/rfc5731)
- [RFC 5732 - Host Mapping](https://datatracker.ietf.org/doc/html/rfc5732)
- [RFC 5733 - Contact Mapping](https://datatracker.ietf.org/doc/html/rfc5733)
- [RFC 5734 - Transport over TCP](https://datatracker.ietf.org/doc/html/rfc5734)
- [RFC 5910 - Domain Name System (DNS) Security Extensions Mapping (secDNS-1.1)](https://datatracker.ietf.org/doc/html/rfc5910)

## Project Structure

- `pyepp/`: Core library source code.
  - `base_command.py`: `BaseCommand` base class providing XML template rendering via Jinja2, automatic `client_transaction_id` generation, and command execution. Defines `ErrorCodeInResultException`.
  - `command_templates.py`: EPP XML Jinja2 templates; thread-safe template cache (`get_compiled_template`, `clear_template_cache`) with dynamic LRU eviction and credential isolation.
  - `epp.py`: Transport communicator (`EppCommunicator`) for TLS/TCP sockets, RFC 5734 32-bit length prefix framing, context manager lifecycle (`with EppCommunicator(...)`), XML credential masking (`mask_sensitive_xml`), DoS protection limits, result encapsulation (`EppResultData` with `parsed_xml` for single-pass parsing), result codes (`EppResultCode`), and exceptions (`EppCommunicatorException`, `EppDryRunException`, `EppTransactionMismatchException`).
  - `domain.py`: Domain mapping commands (`check`, `info`, `create`, `delete`, `renew`, `transfer`, `update`, `restore`, `restore_report`) and DNSSEC dataclasses (`DomainData`, `DSRecordData`, `DSRecordKeyData`, `DNSKeyFlagEnum`, `DigestTypeEnum`, `DNSSECAlgorithm`).
  - `contact.py`: Contact mapping commands (`check`, `info`, `create`, `delete`, `update`), dataclasses (`ContactData`, `PostalInfoData`, `PostalInfoTypeEnum`, `AddressData`), RFC 5733 §2.9 privacy disclosure redaction, and street continuity validation.
  - `host.py`: Host mapping commands (`check`, `info`, `create`, `delete`, `update`) and dataclasses (`HostData`, `IPAddressData`).
  - `poll.py`: Poll message mapping (`request`, `acknowledge`) and dataclasses (`ServiceMessageQueueData`, `ServiceMessageData`).
  - `profiles.py`: `Profile` dataclass implementing Mapping protocol, AWS CLI-style configuration profile loader (`load_profile`, `load_all_profiles`, `list_profiles`, `get_default_config_path`) with `[default]` inheritance and legacy `[pyepp]` fallback.
  - `helper.py`: Utility functions (`generate_password` using `secrets`, `xml_pretty`).
  - `cli/`: Click-based command-line interface (`pyepp`).
    - `__main__.py`: CLI entry point, global options, configuration loading, root subcommands (`run`, `hello`).
    - `cli.py`: `PyEppCli` helper class wiring CLI options to `EppCommunicator` and command classes with safe connection cleanup.
    - `profile.py`: `profile` subcommand group (`list`, `show`).
    - `domain.py`, `contact.py`, `host.py`, `poll.py`: Subcommand groups and options.
    - `utils.py`: Output formatting (`XML`, `OBJECT`, `MIN`) and file output handlers.
- `tests/`: Pytest suite covering core modules (`test_base_command.py`, `test_contact.py`, `test_domain.py`, `test_epp.py`, `test_helper.py`, `test_host.py`, `test_poll.py`, `test_profiles.py`, `test_pyepp.py`) and CLI commands (`test_cli.py`, `test_cli_contact.py`, `test_cli_domain.py`, `test_cli_host.py`, `test_cli_profile.py`).
- `scripts/`: Development and QA scripts:
  - `tests.sh`: Runs `coverage run -m pytest ./tests/` and generates coverage report.
  - `linter.sh`: Runs `pylint ./pyepp --disable=R0401,R0801`.
  - `code-security-check.sh`: Runs `bandit -r ./pyepp`.
  - `package-audit.sh`: Runs `pip-audit`.
- `docs/`: Sphinx-based documentation (`conf.py`, `sphinx-rtd-theme`, `myst-parser`).
- `.github/workflows/`:
  - `checks.yml`: CI workflow running lint, tests, package audit, and bandit checks on Python 3.12 (Ubuntu 24.04).
  - `release.yml`: Publishing workflow (uploads `-beta` releases on `develop` to TestPyPI; production releases on `main` to PyPI).
- `pyproject.toml`: Modern packaging configuration using `setuptools` build backend, CLI entry points, and dynamic versioning from `pyepp.__version__`.
- `pylintrc`: Pylint configuration (`fail-under=10`).
- `.coveragerc`: Coverage configuration (`fail_under=85`, branch coverage enabled, omits `pyepp/cli/*`).
- `requirements.txt`: Production dependencies.
- `requirements.dev.txt`: Development dependencies.

## Technologies

- **Language:** Python 3.10+ (CI runs on Python 3.12)
- **Packaging:** [setuptools](https://setuptools.pypa.io/) (>=77.0.0), [build](https://pypa-build.readthedocs.io/), [twine](https://twine.readthedocs.io/)
- **CLI Framework:** [Click](https://click.palletsprojects.com/) (>=8.5.0)
- **XML Parsing & Serialization:** [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) (>=4.15.0) with [lxml](https://lxml.de/) backend (>=6.1.3)
- **Templating:** [Jinja2](https://jinja.palletsprojects.com/) (>=3.1.6) with `autoescape=True`, [MarkupSafe](https://markupsafe.palletsprojects.com/) (>=2.1.1)
- **Testing & Coverage:** [pytest](https://docs.pytest.org/), [coverage](https://coverage.readthedocs.io/) (enforces >=85% branch coverage)
- **Linting & Security:** [pylint](https://pylint.pycqa.org/) (strict score of 10.0 required), [bandit](https://bandit.readthedocs.io/), [pip-audit](https://pypi.org/project/pip-audit/)
- **Documentation:** [Sphinx](https://www.sphinx-doc.org/), [sphinx-rtd-theme](https://sphinx-rtd-theme.readthedocs.io/), [MyST-Parser](https://myst-parser.readthedocs.io/)

## Development Workflow

### Setup

```bash
pip install -r requirements.txt
pip install -r requirements.dev.txt
pip install -e .
```

### Running the CLI

The CLI is installed as the executable `pyepp`:
```bash
pyepp --help
```

Global options:
- `-p, --profile` (configuration profile name from `config.ini`, e.g. `ote`, `prod`)
- `-c, --config-file` (explicit path to `config.ini` file)
- `--server`, `--port`, `--user`, `--password` (or via `PYEPP_*` environment variables or `~/.pyepp/config.ini`)
- `--client-cert`, `--client-key` (for TLS client certificate authentication)
- `--extension` (repeatable custom EPP service extension URIs)
- `-o, --output-format [XML|OBJECT|MIN|TABLE]`
- `--dry-run`, `--no-pretty`, `-f, --file`
- `-v, --verbose`, `-d, --debug`

Subcommands:
- `pyepp contact`: Contact commands (`check`, `info`, `create`, `delete`, `update`).
- `pyepp domain`: Domain commands (`check`, `info`, `create`, `delete`, `renew`, `transfer`, `update`, `restore`, `restore-report`).
- `pyepp host`: Host commands (`check`, `info`, `create`, `delete`, `update`).
- `pyepp poll`: Service message queue operations (`request`, `acknowledge`).
- `pyepp profile`: Manage and inspect EPP configuration profiles (`list`, `show`).
- `pyepp hello`: Send hello command and display greeting.
- `pyepp run`: Execute a raw XML file command.

### Quality Assurance

Before submitting changes, ensure all quality checks pass using the provided scripts:

- **Run Tests:** `./scripts/tests.sh` (pytest with coverage; must satisfy >=85% branch coverage)
- **Linting:** `./scripts/linter.sh` (pylint; must achieve 10.0/10 score)
- **Security Scan:** `./scripts/code-security-check.sh` (bandit on `./pyepp`)
- **Dependency Audit:** `./scripts/package-audit.sh` (pip-audit)

### Conventions & Git Flow

- **Coding Style:** Follow the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html).
- **Git Flow & Branching:**
  - `develop`: Primary integration branch for ongoing development and beta testing. Releases targeting `develop` with `-beta` tag auto-publish to TestPyPI.
  - `main`: Production-ready branch. Releases targeting `main` auto-publish to PyPI.
  - Feature/bugfix branches should be branched from and merged via pull requests.
- **Versioning:** Dynamic version managed in `pyepp/__init__.__version__`.
- **Documentation:** Keep documentation up to date in `docs/` (`.rst` files) when altering APIs or CLI options.
- **Tests:** Maintain high test coverage; new features or bug fixes must include corresponding tests under `tests/`.

## Architectural Notes

- **Transport Protocol (RFC 5734):** `EppCommunicator` establishes a TLS socket connection and frames XML payloads with a 4-byte unsigned big-endian integer header (`>I`) denoting total message length including header. Implements DoS protection via `max_message_size` (default 10 MiB) and chunked reads (`SOCKET_BUFFER_CHUNK_SIZE = 16384`).
- **Command Abstraction:** High-level entities (`Contact`, `Domain`, `Host`, `Poll`) inherit from `BaseCommand`. `BaseCommand._prepare_command` handles input escaping, client transaction ID generation (`uuid.uuid4()`), and template rendering.
- **Template System & Caching:** Predefined XML templates in `pyepp/command_templates.py` are loaded into a Jinja2 `Environment` (`autoescape=True`, `trim_blocks=True`, `lstrip_blocks=True`). `get_compiled_template` provides thread-safe template caching while isolating caller-provided raw XML strings to prevent credential retention.
- **Single-Pass Response Parsing:** Responses are parsed once into `EppResultData.parsed_xml` using `BeautifulSoup` (`lxml` backend) to extract headers (`clTRID`, `svTRID`, `result` code/message, `roid`), passing the parsed DOM directly to entity parsers to avoid redundant parsing.
- **Credential Security:** Expat stream parser (`mask_sensitive_xml`) scrubs passwords and auth-info codes prior to debug logging. `generate_password` uses `secrets` for cryptographic security.

## Stateful Client & Resource Management Guidelines

To ensure robust reliability, eliminate credential desynchronization, and prevent resource leaks across transport lifecycles, adhere strictly to the following mandates:

1. **Atomic Credential & State Transitions:**
   - Never mutate session credentials (e.g., `_user`, `_password`, `_extensions`) before external authentication succeeds. State changes must be transactional:
     - On failure: preserve existing credentials and set `_logged_in = False`.
     - On success (`code == 1000`): atomically update `_user`, `_password`, `_extensions`, and `_logged_in = True`.
   - Never store mismatched credential pairs across context re-entries.

2. **The "Poisoned Transport" Disconnect Invariant:**
   - Any fatal transport anomaly—including EOF (`_read() is None`), premature disconnects, socket timeouts, `ssl.SSLError`, `OSError` (e.g. Broken pipe, Connection reset), or server connection-closing codes (`2500`, `2501`, `2502`)—renders the length-prefixed stream invalid.
   - The method detecting the fatal transport error **must invoke `disconnect()` before raising**.
   - `is_connected` and `is_logged_in` must NEVER report `True` on a dead or timed-out descriptor.

3. **Resource Manager Acquisition Rule (`BaseException`):**
   - Resource acquisition during `__enter__()` and `connect()` must be protected against `BaseException` (specifically `KeyboardInterrupt` / `SIGINT` and `SystemExit`).
   - If allocation succeeds, any subsequent failure before `__enter__()` returns must call `disconnect()` and re-raise. Because Python never calls `__exit__()` if `__enter__()` fails, failure to catch `BaseException` leaks open TLS socket descriptors.

4. **Bifurcated Context Teardown:**
   - In `__exit__()`, bifurcate error logging:
     - When `exc_type is None` (normal completion): log logout/cleanup failures at `logging.warning` and record `last_logout_error` to maintain production auditability.
     - When `exc_type is not None` (active exception): log cleanup failures at `logging.debug` and record `last_logout_error` to prevent masking the primary business exception.
   - Always run `disconnect()` in a `finally` block to ensure deterministic descriptor release.

5. **Mandatory Lifecycle Sequence Tests:**
   - Every stateful client feature must include sequential lifecycle tests:
     - **Failure $\rightarrow$ Context Entry**: Inject EOF, timeout, or network drop; catch error; enter `with client:`; assert it reconnects and re-authenticates rather than reusing dead state.
     - **Credential Switch $\rightarrow$ Reuse**: Execute login with credentials B, disconnect, enter `with client:`; verify it authenticates with B.
     - **Interrupt Simulation**: Mock `KeyboardInterrupt` in `connect()` and `__enter__()`; assert immediate socket closure.
