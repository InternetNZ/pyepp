"""
Host cli module
"""
import click

from pyepp.cli import utils
from pyepp.host import Host, IPAddressData, HostData


@click.group(name='host')
@click.pass_context
def host_group(ctx):
    """To work with Host objects in the registry."""
    ctx.obj.registry_object = Host(ctx.obj.epp)


@click.command(name='info')
@click.argument('host-name')
@click.option('--client-transaction-id')
@click.pass_context
def host_info(ctx, host_name, client_transaction_id) -> None:
    """Returns host details.

    HOST_NAME: Host name
    """
    result = ctx.obj.info(host_name, client_transaction_id)
    utils.echo(result)


@click.command(name='check')
@click.argument('host-names', nargs=-1)
@click.option('--client-transaction-id')
@click.pass_context
def host_check(ctx, host_names: tuple, client_transaction_id) -> None:
    """Checks if host(s) exist in the registry."""
    result = ctx.obj.check(list(host_names), client_transaction_id)
    utils.echo(result)


@click.command(name='delete')
@click.argument('host-name')
@click.option('--client-transaction-id')
@click.pass_context
def host_delete(ctx, host_name, client_transaction_id) -> None:
    """Deletes a given host from registry.

    HOST_NAME: Host name
    """
    result = ctx.obj.delete(host_name, client_transaction_id)
    utils.echo(result)


@click.command(name='update')
@click.argument('host-name')
@click.option('--add-ip', multiple=True, nargs=2, type=click.Tuple([str, str]),
              help="Add IP address to host. <ADDRESS IP[v4, v6]>")
@click.option('--remove-ip', multiple=True, nargs=2, type=click.Tuple([str, str]),
              help="Remove IP address to host. <ADDRESS IP[v4, v6]>")
@click.option('--add-status', multiple=True, help="Add a status to host.")
@click.option('--remove-status', multiple=True, help="Remove a status to host.")
@click.option('--new-host-name', help="The host name will be changed to this new host name.")
@click.option('--client-transaction-id')
@click.pass_context
# pylint: disable=too-many-arguments, too-many-locals, too-many-boolean-expressions
def host_update(ctx, host_name, add_ip, remove_ip, add_status, remove_status, new_host_name,
                client_transaction_id) -> None:
    """Updates host's details.

    HOST_NAME: Host name
    """
    add_ip_address = [IPAddressData(item[0], item[1]) for item in add_ip] if add_ip else None
    remove_ip_address = [IPAddressData(item[0], item[1]) for item in remove_ip] if add_ip else None
    add_statue = list(add_status) if add_status else None
    remove_status = list(remove_status) if add_status else None
    result = ctx.obj.update(host_name,
                            add_ip_address=add_ip_address,
                            remove_ip_address=remove_ip_address,
                            add_status=add_statue,
                            remove_status=remove_status,
                            new_host_name=new_host_name,
                            client_transaction_id=client_transaction_id)
    utils.echo(result)


@click.command(name='create')
@click.argument('host-name')
@click.option('--ip-address', multiple=True, nargs=2, type=click.Tuple([str, str]),
              help="Add IP address to host. At least one required. <ADDRESS IP[v4, v6]>", required=True)
@click.option('--client-transaction-id')
@click.pass_context
def host_create(ctx, host_name, ip_address, client_transaction_id) -> None:
    """Creates a new contact in the registry.

    HOST_NAME: A unique host name
    """
    ip_address = [IPAddressData(item[0], item[1]) for item in ip_address] if ip_address else None
    result = ctx.obj.create(HostData(host_name=host_name,
                                     address=ip_address),
                            client_transaction_id)
    utils.echo(result)


host_group.add_command(host_info)
host_group.add_command(host_check)
host_group.add_command(host_delete)
host_group.add_command(host_update)
host_group.add_command(host_create)
