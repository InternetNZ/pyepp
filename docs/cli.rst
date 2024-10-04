CLI
=============

PyEPP comes with a command line interface that allows the user to interact with the registry system. It will be installed
the main library.

.. code-block:: text

    sh> pip install pyepp

How to get help
---------------
To see the help page:

.. code-block:: text

    sh> pyepp -h
    Usage: pyepp [OPTIONS] COMMAND [ARGS]...

    A command line interface to work with PyEpp library.

    Options:
      --server TEXT                   [required]
      --port TEXT                     [required]
      --user TEXT                     [required]
      --password TEXT                 [required]
      --client-cert TEXT              [optional]
      --client-key TEXT               [optional]
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

And to get help for a specific command:

.. code-block:: text

    sh> pyepp contact create -h
    Usage: pyepp contact create [OPTIONS] CONTACT_ID

      Creates a new contact in the registry.

      CONTACT_ID: A unique contact id

    Options:
      --email TEXT                  [required]
      --name TEXT                   [required]
      --city TEXT                   [required]
      --country-code TEXT           [required]
      --organization TEXT
      --street-1 TEXT
      --street-2 TEXT
      --street-3 TEXT
      --province TEXT
      --postal-code TEXT
      --phone TEXT
      --fax TEXT
      --password TEXT
      --client-transaction-id TEXT
      -h, --help                    Show this message and exit.

Enable shell autocomplete
-------------------------
To enable shell autocompletion for your shell follow the below commands:

Zsh
^^^^
.. code-block:: text

    mkdir -p ~/.pyepp
    _PYEPP_COMPLETE=zsh_source pyepp > ~/.pyepp/shell-complete.zsh

Source the file in ``~/.zshrc``.

.. code-block:: text

    . ~/.pyepp/shell-complete.zsh

Bash
^^^^
.. code-block:: text

    mkdir -p ~/.pyepp
    _PYEPP_COMPLETE=bash_source pyepp > ~/.pyepp/shell-complete.bash

Source the file in ``~/.bashrc``.

.. code-block:: text

    . ~/.pyepp/shell-complete.bash

How to configure
----------------
The epp server configuration and credentials can be passed to the cli in three different ways. It can be done either
through the command line options, environment variables or a config file.

NOTE: Client certificate and key are optional and only required if the server requires client authentication.

Command line options
^^^^^^^^^^^^^^^^^^^^
The server configuration and credentials can be passed to the cli by command line options:

.. code-block:: text

    sh> pyepp --server epp.test.net.nz \
        --port 700 \
        --user epp_user \
        --password SecurePassWord \
        --client-key /path/to/epp.key.pem \
        --client-cert /path/to/epp.crt \
        contact info ehsan-contact-1

Environment variables
^^^^^^^^^^^^^^^^^^^^^
The below environment variables can be used to pass the epp server configuration and credentials to the cli. By using
this way you don't have to pass the parameters for running each command.

.. code-block:: text

    PYEPP_SERVER=epp.test.net.nz
    PYEPP_PORT=700
    PYEPP_USER=epp_user
    PYEPP_PASSWORD=SecurePassWord
    PYEPP_CLIENT_CERT=/path/to/epp.crt
    PYEPP_CLIENT_KEY=/path/to/epp.key.pem

Config file
^^^^^^^^^^^
To configure the cli by a config file first the config file should be created in the below paths based on the operating
system:

.. code-block:: text

    Mac OS X (POSIX) and Unix (POSIX):
      ~/.pyepp/config.ini
    Windows (not roaming):
      C:\Users\<user>\AppData\Local\pyepp\config.ini

Then add the below lines to the file:

.. code-block:: ini

    [pyepp]
    server = epp.test.net.nz
    port = 700
    user = epp_user
    password = SecurePassWord
    client_cert = /path/to/epp.crt
    client_key = /path/to/epp.key.pem 

Examples
---------------

contact
^^^^^^^^^^^

.. code-block:: text

    sh> pyepp contact create sh8014 --email jdoe@example.com --name Jonh --city Dulles --country-code US
        <?xml version="1.0" encoding="utf-8"?>
        <epp xmlns="urn:ietf:params:xml:ns:epp-1.0" xmlns:contact="urn:ietf:params:xml:ns:contact-1.0" xmlns:domain="urn:ietf:params:xml:ns:domain-1.0" xmlns:host="urn:ietf:params:xml:ns:host-1.0" xmlns:rgp="urn:ietf:params:xml:ns:rgp-1.0" xmlns:secDNS="urn:ietf:params:xml:ns:secDNS-1.1">
         <response>
          <result code="1000">
           <msg>
            Command completed successfully
           </msg>
          </result>
          <resData>
           <contact:creData>
            <contact:id>
             sh8014
            </contact:id>
            <contact:crDate>
             2024-04-12T00:41:59.977Z
            </contact:crDate>
           </contact:creData>
          </resData>
          <trID>
           <clTRID>
            09ac2c26-63f4-4aaf-8574-1add9e620044
           </clTRID>
           <svTRID>
            CIRA-000232270901-0000000002
           </svTRID>
          </trID>
         </response>
        </epp>

.. code-block:: text

    sh> pyepp -o OBJECT contact check sh8014
        EppResultData(code=1000,
                      message='Command completed successfully',
                      raw_response=b'<?xml version="1.0" encoding="UTF-8"?>\n<epp xmln'
                                   b's:host="urn:ietf:params:xml:ns:host-1.0" xmlns:s'
                                   b'ecDNS="urn:ietf:params:xml:ns:secDNS-1.1" xmlns:'
                                   b'rgp="urn:ietf:params:xml:ns:rgp-1.0" xmlns="urn:'
                                   b'ietf:params:xml:ns:epp-1.0" xmlns:contact="urn:i'
                                   b'etf:params:xml:ns:contact-1.0" xmlns:domain="urn'
                                   b':ietf:params:xml:ns:domain-1.0">\n    <response>\n'
                                   b'        <result code="1000">\n            <msg>Co'
                                   b'mmand completed successfully</msg>\n        </res'
                                   b'ult>\n        <resData>\n            <contact:chkD'
                                   b'ata>\n                <contact:cd>\n              '
                                   b'      <contact:id avail="false">sh8014</contact:'
                                   b'id>\n                    <contact:reason>Selected'
                                   b' contact ID is not available</contact:reason>\n  '
                                   b'              </contact:cd>\n            </contac'
                                   b't:chkData>\n        </resData>\n        <trID>'
                                   b'\n            <clTRID>32ebe5a8-225b-4829-a8e0-aa1'
                                   b'a10602138</clTRID>\n            <svTRID>CIRA-0002'
                                   b'32306101-0000000002</svTRID>\n        </trID>\n   '
                                   b' </response>\n</epp>',
                      result_data={'sh8014': {'avail': False,
                                              'reason': 'Selected contact ID is not '
                                                        'available'}},
                      reason=None,
                      client_transaction_id='32ebe5a8-225b-4829-a8e0-aa1a10602138',
                      server_transaction_id='CIRA-000232306101-0000000002',
                      repository_object_id=None)

domain
^^^^^^^^^^^

.. code-block:: text

    sh> pyepp --no-pretty domain check test.nz
        <?xml version="1.0" encoding="UTF-8"?>
        <epp xmlns:host="urn:ietf:params:xml:ns:host-1.0" xmlns:secDNS="urn:ietf:params:xml:ns:secDNS-1.1" xmlns:rgp="urn:ietf:params:xml:ns:rgp-1.0" xmlns="urn:ietf:params:xml:ns:epp-1.0" xmlns:contact="urn:ietf:params:xml:ns:contact-1.0" xmlns:domain="urn:ietf:params:xml:ns:domain-1.0">
            <response>
                <result code="1000">
                    <msg>Command completed successfully</msg>
                </result>
                <resData>
                    <domain:chkData>
                        <domain:cd>
                            <domain:name avail="false">test.nz</domain:name>
                            <domain:reason>Registered</domain:reason>
                        </domain:cd>
                    </domain:chkData>
                </resData>
                <trID>
                    <clTRID>46c89b2a-617f-4d44-a2c1-340aa20a1358</clTRID>
                    <svTRID>CIRA-000232247104-0000000002</svTRID>
                </trID>
            </response>
        </epp>


.. code-block:: text

    sh> pyepp -o MIN domain check test.co.nz 
        {'test.co.nz': {'avail': False, 'reason': 'Registered'}}

host
^^^^^^^^^^^

.. code-block:: text

    sh> pyepp host info test.co.nz
        <?xml version="1.0" encoding="utf-8"?>
        <epp xmlns="urn:ietf:params:xml:ns:epp-1.0" xmlns:contact="urn:ietf:params:xml:ns:contact-1.0" xmlns:domain="urn:ietf:params:xml:ns:domain-1.0" xmlns:host="urn:ietf:params:xml:ns:host-1.0" xmlns:rgp="urn:ietf:params:xml:ns:rgp-1.0" xmlns:secDNS="urn:ietf:params:xml:ns:secDNS-1.1">
         <response>
          <result code="2303">
           <msg>
            Object does not exist
           </msg>
           <extValue>
            <value>
             <ciraCode>
              6010
             </ciraCode>
            </value>
            <reason>
             Host does not exist
            </reason>
           </extValue>
          </result>
          <trID>
           <clTRID>
            7bc656f8-32f0-42d3-ba55-79192cd3b654
           </clTRID>
           <svTRID>
            CIRA-000232224702-0000000002
           </svTRID>
          </trID>
         </response>
    </epp>

.. code-block:: text

    sh> pyepp --dry-run host info test.co.nz
        <?xml version="1.0" encoding="UTF-8" standalone="no"?>
        <epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
         <command>
           <info>
             <host:info xmlns:host="urn:ietf:params:xml:ns:host-1.0">
               <host:name>test.co.nz</host:name>
             </host:info>
           </info>
           <clTRID>dab02e31-5658-44c4-bbd5-ff66b88539b5</clTRID>
         </command>
        </epp>
