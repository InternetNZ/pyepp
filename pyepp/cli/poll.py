"""
EPP Poll cli module
"""
import click

from pyepp.poll import Poll
from pyepp.cli import utils


@click.group(name='poll')
@click.pass_context
def poll_group(ctx):
    """ To manage registry service messages."""
    ctx.obj.registry_object = Poll(ctx.obj.epp)


@click.command(name='request')
@click.option('--client-transaction-id')
@click.pass_context
def poll_request(ctx, client_transaction_id):
    """This command is to check and retrieve queued service messages as wel as keep the
        connection alive."""
    result = ctx.obj.request(client_transaction_id=client_transaction_id)
    utils.echo(result)


@click.command(name='acknowledge')
@click.argument('message-id')
@click.option('--client-transaction-id')
@click.pass_context
def poll_acknowledge(ctx, message_id,client_transaction_id):
    """This command will acknowledge and remove a message from the poll queue so that registrars can run another
       poll request to get the next message in line if one exists.

        MESSAGE_ID: Request message id
    """
    result = ctx.obj.acknowledge(message_id,
                                 client_transaction_id=client_transaction_id)
    utils.echo(result)


poll_group.add_command(poll_request)
poll_group.add_command(poll_acknowledge)
