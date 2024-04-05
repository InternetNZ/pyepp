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
      --host TEXT                     [required]
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

How to configure
----------------
The epp server configuration and credentials can be passed to the cli in three different ways. It can be done either
through the command line options, environment variables or a config file.

Command line options
^^^^^^^^^^^^^^^^^^^^
The server configuration and credentials can be passed to the cli by command line options:

.. code-block:: text

    sh> pyepp --host epp.test.net.nz \
        --port 700 \
        --client-key /path/to/epp.key.pem \
        --client-cert /path/to/epp.crt \
        --user epp_user \
        --password SecurePassWord \
        contact info ehsan-contact-1

Environment variables
^^^^^^^^^^^^^^^^^^^^^
The below environment variables can be used to pass the epp server configuration and credentials to the cli. By using
this way you don't have to pass the parameters for running each command.

.. code-block:: text

    PYEPP_HOST=epp.test.net.nz
    PYEPP_PORT=700
    PYEPP_CLIENT_CERT=/path/to/epp.crt
    PYEPP_CLIENT_KEY=/path/to/epp.key.pem
    PYEPP_USER=epp_user
    PYEPP_PASSWORD=SecurePassWord

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
    host = epp.test.net.nz
    port = 700
    client_cert = /path/to/epp.crt
    client_key = /path/to/epp.key.pem
    user = epp_user
    password = SecurePassWord

