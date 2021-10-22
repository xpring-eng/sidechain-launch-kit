"""Model for AccountDelete transaction type."""

from dataclasses import dataclass, field
from typing import Optional

from xrpl.models.required import REQUIRED
from xrpl.models.transactions.transaction import Transaction
from xrpl.models.requests.request import Request, RequestMethod
from xrpl.models.transactions.types import TransactionType
from xrpl.models.utils import require_kwargs_on_init


@require_kwargs_on_init
@dataclass(frozen=True)
class TicketCreate(Transaction):
    """
    A TicketCreate transaction sets aside one or more `sequence numbers 
    <https://xrpl.org/basic-data-types.html#account-sequence>`_ as `Tickets 
    <https://xrpl.org/tickets.html>`_.
    """

    ticket_count: int = REQUIRED  # type: ignore
    """
    How many Tickets to create. This must be a positive number and cannot cause the
    account to own more than 250 Tickets after executing this transaction.

    :meta hide-value:
    """

    transaction_type: TransactionType = field(
        default="TicketCreate",
        init=False,
    )

@require_kwargs_on_init
@dataclass(frozen=True)
class FederatorInfo(Request):
    """
    The federator_info command asks the server for a
    human-readable version of various information
    about the federator server being queried.
    """

    method: RequestMethod = field(default="federator_info", init=False)