"""
EPP XML command templates
"""

HELLO_XML = """<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <hello/>
</epp>"""

LOGIN_XML = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <command>
    <login>
      <clID>{user}</clID>
      <pw>{password}</pw>
      <options>
        <version>1.0</version>
        <lang>en</lang>
      </options>
      <svcs>
        <objURI>urn:ietf:params:xml:ns:domain-1.0</objURI>
        <objURI>urn:ietf:params:xml:ns:contact-1.0</objURI>
        <svcExtension>
          <extURI>urn:ietf:params:xml:ns:secDNS-1.1</extURI>
        </svcExtension>
      </svcs>
    </login>
  </command>
</epp>"""

LOGOUT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
xsi:schemaLocation="urn:ietf:params:xml:ns:epp-1.0 epp-1.0.xsd">
    <command>
        <logout/>
    </command>
</epp>"""

CONTACT_CHECK_XML = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <command>
    <check>
      <contact:check xmlns:contact="urn:ietf:params:xml:ns:contact-1.0">
      {% for id in ids %}
        <contact:id>{{ id }}</contact:id>
      {% endfor %}
      </contact:check>
    </check>
    <clTRID>{{ client_transaction_id }}</clTRID>
  </command>
</epp>"""

CONTACT_INFO_XML = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <command>
    <info>
      <contact:info xmlns:contact="urn:ietf:params:xml:ns:contact-1.0">
        <contact:id>{{ id }}</contact:id>
      </contact:info>
    </info>
    <clTRID>{{ client_transaction_id }}</clTRID>
  </command>
</epp>
"""

CONTACT_CREAT_XML = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <command>
    <create>
      <contact:create xmlns:contact="urn:ietf:params:xml:ns:contact-1.0">
        <contact:id>{{ id }}</contact:id>
          <contact:postalInfo type="loc">
            <contact:name>{{ name }}</contact:name>
            {% if organization %} <contact:org>{{ organization }}</contact:org> {% endif %}
            <contact:addr>
              <contact:street>{{ street_1 }}</contact:street>
              {% if street_2 %} <contact:street>{{ street_2 }}</contact:street> {% endif %}
              {% if street_3 %} <contact:street>{{ street_3 }}</contact:street> {% endif %}
              <contact:city>{{ city }}</contact:city>
              {% if province %} <contact:sp>{{ province }}</contact:sp> {% endif %}
              {% if postal_code %} <contact:pc>{{ postal_code }}</contact:pc> {% endif %}
              <contact:cc>{{ country_code }}</contact:cc>
           </contact:addr>
         </contact:postalInfo>
         {% if phone %} <contact:voice>{{ phone }}</contact:voice> {% endif %}
         {% if fax %} <contact:fax>{{ fax }}</contact:fax> {% endif %}
         <contact:email>{{ email }}</contact:email>
         <contact:authInfo>
           <contact:pw> {{ password }}</contact:pw>
         </contact:authInfo>
         {% if privacy %}
         <contact:disclose flag="0">
           {% for element in privacy %}
           <contact:{{ element }}/>
           {% endfor %}
         </contact:disclose>
         {% endif %}
       </contact:create>
    </create>
    <clTRID>{{ client_transaction_id }}</clTRID>
  </command>
</epp>"""

CONTACT_DELETE_XML = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <command>
    <delete>
      <contact:delete xmlns:contact="urn:ietf:params:xml:ns:contact-1.0">
        <contact:id>{{ id }}</contact:id>
      </contact:delete>
    </delete>
    <clTRID>{{ client_transaction_id }}</clTRID>
  </command>
</epp>"""

CONTACT_UPDATE_XML = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <command>
    <update>
      <contact:update xmlns:contact="urn:ietf:params:xml:ns:contact-1.0">
        <contact:id>{{ id }}</contact:id>
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
        <contact:chg>
         {% if postalinfo_change %}
          <contact:postalInfo type="loc">
            <contact:name>{{ name }}</contact:name>
            <contact:org>{{ organization }}</contact:org>
            {% if address_change %}
            <contact:addr>
                {% if street_1 %} <contact:street>{{ street_1 }}</contact:street> {% endif %}
                {% if street_2 %} <contact:street>{{ street_2 }}</contact:street> {% endif %}
                {% if street_3 %} <contact:street>{{ street_3 }}</contact:street> {% endif %}
                <contact:city>{{ city }}</contact:city>
                {% if province %} <contact:sp>{{ province }}</contact:sp> {% endif %}
                {% if postal_code %} <contact:pc>{{ postal_code }}</contact:pc> {% endif %}
                <contact:cc>{{ country_code }}</contact:cc>
           </contact:addr>
           {% endif %}
         </contact:postalInfo>
         {% endif %}
         <contact:voice>{{ phone }}</contact:voice>
         {% if fax %} <contact:fax>{{ fax }}</contact:fax> {% else %} <contact:fax/> {% endif %}
         <contact:email>{{ email }}</contact:email>
         <contact:authInfo>
           <contact:pw>{{ password }}</contact:pw>
         </contact:authInfo>
         {% if privacy %}
         <contact:disclose flag="0">
           {% for element in privacy %}
           <contact:{{ element }}/>
           {% endfor %}
         </contact:disclose>
         {% endif %}
        </contact:chg>
       </contact:update>
    </update>
    <clTRID>{{ client_transaction_id }}</clTRID>
  </command>
</epp>"""

DOMAIN_CHECK_XML = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <command>
    <check>
      <domain:check xmlns:domain="urn:ietf:params:xml:ns:domain-1.0">
      {% for domain_name in domain_names %}
        <domain:name>{{ domain_name }}</domain:name>
      {% endfor %}
      </domain:check>
    </check>
    <clTRID>{{ client_transaction_id }}</clTRID>
  </command>
</epp>"""

DOMAIN_INFO_XML = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <command>
    <info>
      <domain:info xmlns:domain="urn:ietf:params:xml:ns:domain-1.0">
        <domain:name hosts="all">{{ domain_name }}</domain:name>
        {% if udai %}
        <domain:authInfo>
          <domain:pw>{{ udai }}</domain:pw>
        </domain:authInfo>
        {% endif %}
      </domain:info>
    </info>
  </command>
</epp>"""

DOMAIN_CREATE_XML = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <command>
    <create>
      <domain:create xmlns:domain="urn:ietf:params:xml:ns:domain-1.0">
        <domain:name>{{ domain_name }}</domain:name>
        <domain:period unit='y'>{{ period }}</domain:period>
        {% if host %}
        <domain:ns>
        {% for ns in host %}
          <domain:hostObj>{{ ns }}</domain:hostObj>
        {% endfor %}
        </domain:ns>
        {% endif %}
        <domain:registrant>{{ registrant }}</domain:registrant>
        {% if admin %}
        <domain:contact type="admin">{{ admin }}</domain:contact>
        {% endif %}
        {% if tech %}
        <domain:contact type="tech">{{ tech }}</domain:contact>
        {% endif %}
        {% if billing %}
        <domain:contact type="billing">{{ billing }}</domain:contact>
        {% endif %}
        <domain:authInfo>
          <domain:pw>{{ password }}</domain:pw>
        </domain:authInfo>
      </domain:create>
    </create>
    {% if dns_sec %}
    <extension>
      <secDNS:create xmlns:secDNS="urn:ietf:params:xml:ns:secDNS-1.1">
        <secDNS:dsData>
          <secDNS:keyTag>{{ dns_sec.get('key_tag') }}</secDNS:keyTag>
          <secDNS:alg>{{ dns_sec.get('algorithm') }}</secDNS:alg>
          <secDNS:digestType>{{ dns_sec.get('digest_type') }}</secDNS:digestType>
          <secDNS:digest>{{ dns_sec.get('digest') }}</secDNS:digest>
          {% if dns_sec.get('dns_key') %}
          <secDNS:keyData>
            <secDNS:flags>{{ dns_sec.get('dns_key').get('flag') }}</secDNS:flags>
            <secDNS:protocol>{{ dns_sec.get('dns_key').get('protocol') }}</secDNS:protocol>
            <secDNS:alg>{{ dns_sec.get('dns_key').get('algorithm') }}</secDNS:alg>
            <secDNS:pubKey>{{ dns_sec.get('dns_key').get('public_key') }}</secDNS:pubKey>
          </secDNS:keyData>
          {% endif %}
        </secDNS:dsData>
        {% if dns_key %}
        <secDNS:keyData>
          <secDNS:flags>{{ dns_key.dns_key.get('flag') }}</secDNS:flags>
          <secDNS:protocol>{{ dns_key.dns_key.get('protocol') }}</secDNS:protocol>
          <secDNS:alg>{{ dns_key.dns_key.get('algorithm') }}</secDNS:alg>
          <secDNS:pubKey>{{ dns_key.dns_key.get('public_key') }}</secDNS:pubKey>
        </secDNS:keyData>
        {% endif %}
      </secDNS:create>
    </extension>
    {% endif %}
    <clTRID>{{ client_transaction_id }}</clTRID>
  </command>
</epp>"""

DOMAIN_DELETE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<epp xmlns="urn:ietf:params:xml:ns:epp-1.0">
  <command>
    <delete>
      <domain:delete xmlns:domain="urn:ietf:params:xml:ns:domain-1.0">
        <domain:name>{{ domain_name }}</domain:name>
      </domain:delete>
    </delete>
    <clTRID>{{ client_transaction_id }}</clTRID>
  </command>
</epp>"""