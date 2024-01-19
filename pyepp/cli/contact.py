"""
Contact cli module
"""
import click

from pyepp.cli import utils
from pyepp.contact import Contact, ContactData, PostalInfoData, AddressData


@click.group(name='contact')
@click.pass_context
def contact_group(ctx):
    """
    To work with Contact objects in the registry.
    :param ctx:
    :return:
    """
    ctx.obj.registry_object = Contact(ctx.obj.epp)


@click.command(name='info')
@click.argument('contact-id')
@click.option('--client-transaction-id')
@click.pass_context
def contact_info(ctx, contact_id, client_transaction_id) -> None:
    """Returns contact details."""
    result = ctx.obj.info(contact_id, client_transaction_id)
    utils.echo(result)


@click.command(name='check')
@click.argument('contact-ids', nargs=-1)
@click.option('--client-transaction-id')
@click.pass_context
def contact_check(ctx, contact_ids: tuple, client_transaction_id) -> None:
    """Checks if contact(s) exist in the registry."""
    result = ctx.obj.check(list(contact_ids), client_transaction_id)
    utils.echo(result)


@click.command(name='delete')
@click.argument('contact-id')
@click.option('--client-transaction-id')
@click.pass_context
def contact_delete(ctx, contact_id, client_transaction_id) -> None:
    """Deletes a given contact from registry."""
    result = ctx.obj.delete(contact_id, client_transaction_id)
    utils.echo(result)


@click.command(name='update')
@click.argument('contact-id')
@click.option('--email')
@click.option('--name')
@click.option('--organization')
@click.option('--street-1')
@click.option('--street-2')
@click.option('--street-3')
@click.option('--city', help="required if postal info gets updated.")
@click.option('--province')
@click.option('--postal-code')
@click.option('--country-code', help="required if postal info gets updated.")
@click.option('--phone')
@click.option('--fax')
@click.option('--password')
@click.option('--add-status')
@click.option('--remove-status')
@click.option('--client-transaction-id')
@click.pass_context
# pylint: disable=too-many-arguments, too-many-locals, too-many-boolean-expressions
def contact_update(ctx, contact_id, name, organization, street_1, street_2, street_3, city, province, postal_code,
                   country_code, phone, fax, email, password, add_status, remove_status, client_transaction_id) -> None:
    """Updates contact's details.

    CONTACT_ID: Contact id
    """
    contact_to_update = ContactData(
        id=contact_id,
        email=email,
        phone=phone,
        fax=fax,
        password=password,
        postal_info=PostalInfoData(
            name=name,
            organization=organization,
        )
    )

    if street_1 or street_2 or street_3 or city or province or postal_code or country_code:
        contact_to_update.postal_info.address = AddressData(
            street_1=street_1,
            street_2=street_2,
            street_3=street_3,
            city=city,
            province=province,
            postal_code=postal_code,
            country_code=country_code
        )

    result = ctx.obj.update(contact_to_update, add_status, remove_status, client_transaction_id)
    utils.echo(result)


@click.command(name='create')
@click.argument('contact-id')
@click.option('--email', required=True)
@click.option('--name', required=True)
@click.option('--city', required=True)
@click.option('--country-code', required=True)
@click.option('--organization')
@click.option('--street-1')
@click.option('--street-2')
@click.option('--street-3')
@click.option('--province')
@click.option('--postal-code')
@click.option('--phone')
@click.option('--fax')
@click.option('--password')
@click.option('--client-transaction-id')
@click.pass_context
# pylint: disable=too-many-arguments, too-many-locals
def contact_create(ctx, contact_id, name, organization, street_1, street_2, street_3, city, province, postal_code,
                   country_code, phone, fax, email, password, client_transaction_id) -> None:
    """Creates a new contact in the registry.

    CONTACT_ID: A unique contact id
    """
    contact_to_create = ContactData(
        id=contact_id,
        email=email,
        phone=phone,
        fax=fax,
        password=password,
        postal_info=PostalInfoData(
            name=name,
            organization=organization,
            address=AddressData(
                street_1=street_1,
                street_2=street_2,
                street_3=street_3,
                city=city,
                province=province,
                postal_code=postal_code,
                country_code=country_code
            )
        )
    )

    result = ctx.obj.create(contact_to_create, client_transaction_id)
    utils.echo(result)


contact_group.add_command(contact_check)
contact_group.add_command(contact_info)
contact_group.add_command(contact_delete)
contact_group.add_command(contact_update)
contact_group.add_command(contact_create)
