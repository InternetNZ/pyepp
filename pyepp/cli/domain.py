"""
Domain cli module
"""
from datetime import datetime

import click

from pyepp.cli import utils
from pyepp.domain import Domain, DomainData


@click.group(name='domain')
@click.pass_context
def domain_group(ctx):
    """To work with Domain name objects in the registry."""
    ctx.obj.registry_object = Domain(ctx.obj.epp)


@click.command(name='info')
@click.argument('domain-name')
@click.option('--client-transaction-id')
@click.pass_context
def domain_info(ctx, domain_name, client_transaction_id) -> None:
    """Returns domain name details."""
    result = ctx.obj.info(domain_name, client_transaction_id)
    utils.echo(result)


@click.command(name='check')
@click.argument('domain-names', nargs=-1)
@click.option('--client-transaction-id')
@click.pass_context
def domain_check(ctx, domain_names: tuple, client_transaction_id) -> None:
    """Checks if domain name(s) exist in the registry."""
    result = ctx.obj.check(list(domain_names), client_transaction_id)
    utils.echo(result)


@click.command(name='delete')
@click.argument('domain-name')
@click.option('--client-transaction-id')
@click.pass_context
def domain_delete(ctx, domain_name, client_transaction_id) -> None:
    """Deletes a given domain from registry."""
    result = ctx.obj.delete(domain_name, client_transaction_id)
    utils.echo(result)


@click.command(name='renew')
@click.argument('domain-name')
@click.argument('current-expiry-date')
@click.option('--period')
@click.option('--client-transaction-id')
@click.pass_context
def domain_renew(ctx, domain_name, current_expiry_date, period, client_transaction_id) -> None:
    """Extend the validity period of a domain name.

    \b
    DOMAIN_NAME: Domain name
    CURRENT_EXPIRY_DATE: The current expiry date in 'YYYY-MM-DD' format.
    """
    result = ctx.obj.renew(domain_name,
                           datetime.strptime(current_expiry_date, "%Y-%m-%d"),
                           period,
                           client_transaction_id)
    utils.echo(result)


@click.command(name='transfer')
@click.argument('domain-name')
@click.argument('password')
@click.option('--period', help="The number of years to be added to the registration period of the domain "
                               "object upon completion of the transfer process.")
@click.option('--client-transaction-id')
@click.pass_context
def domain_transfer(ctx, domain_name, password, period, client_transaction_id) -> None:
    """Extend the validity period of a domain name.

    \b
    DOMAIN_NAME: Domain name
    PASSWORD: The authorization password for the domain object.
    """
    result = ctx.obj.transfer(domain_name,
                              password,
                              period,
                              client_transaction_id)
    utils.echo(result)


@click.command(name='create')
@click.argument('domain-name')
@click.option('--registrant', help="Contact id of the registrant.")
@click.option('--admin', help="Contact id of the administrator of the domain.")
@click.option('--tech', help="Contact id of the technical support of the domain.")
@click.option('--billing', help="Contact id of the billing contact of the domain.")
@click.option('--period', default=1, show_default=True,
              help="The initial registration period of the domain in years.")
@click.option('--ns-host', multiple=True, help='Name server. Can be repeated for multiple name servers.')
@click.option('--client-transaction-id')
@click.pass_context
# pylint: disable=too-many-arguments, too-many-locals
def domain_create(ctx, domain_name, registrant, admin, tech, billing, period, ns_host, client_transaction_id):
    """Create a domain name object in registry.

    DOMAIN_NAME: Domain name
    """
    domain_data = DomainData(
        domain_name=domain_name,
        registrant=registrant,
        admin=admin,
        tech=tech,
        billing=billing,
        period=period,
        host=ns_host
    )
    result = ctx.obj.create(domain_data, client_transaction_id)
    utils.echo(result)


@click.command(name='update')
@click.argument('domain-name')
@click.option('--registrant', help="A contact id to replace the current registrant.")
@click.option('--password', help="A new password to replace the current domain password.")
@click.option('--add-admin', multiple=True, help="Contact id to add a new admin contact to the domain object.")
@click.option('--add-tech', multiple=True, help="Contact id to add a new tech contact to the domain object.")
@click.option('--add-billing', multiple=True, help="Contact id to add a new billing contact to the admin domain.")
@click.option('--add-ns-host', multiple=True, help="Name server host to be added to domain object.")
@click.option('--add-status', type=(str, str), multiple=True,
              help="A status to be added to domain abject. Both status value and description must be provided.")
@click.option('--remove-admin', multiple=True, help="Admin contact id to be removed from domain object.")
@click.option('--remove-tech', multiple=True, help="Technical support contact id to be removed from domain object.")
@click.option('--remove-billing', multiple=True, help="Billing contact id to be removed from domain object.")
@click.option('--remove-ns-host', multiple=True, help="Name server host to be removed from domain object.")
@click.option('--remove-status', multiple=True, help="A status to be removed to domain abject.")
@click.option('--client-transaction-id')
@click.pass_context
# pylint: disable=too-many-arguments, too-many-locals
def domain_update(ctx, domain_name, password, registrant, add_admin, add_tech, add_billing, add_ns_host, add_status,
                  remove_admin, remove_tech, remove_billing, remove_ns_host, remove_status, client_transaction_id):
    """Modify the attributes of a domain object in registry.

    DOMAIN_NAME: Domain name
    """
    result = ctx.obj.update(domain_name=domain_name,
                            registrant=registrant,
                            password=password,
                            add_admins=add_admin,
                            remove_admins=remove_admin,
                            add_techs=add_tech,
                            remove_techs=remove_tech,
                            add_billings=add_billing,
                            remove_billings=remove_billing,
                            add_statues=add_status,
                            remove_statues=remove_status,
                            add_hosts=add_ns_host,
                            remove_hosts=remove_ns_host,
                            client_transaction_id=client_transaction_id)
    utils.echo(result)


domain_group.add_command(domain_check)
domain_group.add_command(domain_info)
domain_group.add_command(domain_delete)
domain_group.add_command(domain_update)
domain_group.add_command(domain_create)
domain_group.add_command(domain_renew)
domain_group.add_command(domain_transfer)
