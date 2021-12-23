"""Helper methods for setting up chains."""

from xrpl.account import does_account_exist, get_account_root
from xrpl.clients.sync_client import SyncClient
from xrpl.models import (
    AccountSet,
    AccountSetFlag,
    IssuedCurrencyAmount,
    Payment,
    SignerEntry,
    SignerListSet,
    TicketCreate,
    TrustSet,
)
from xrpl.utils import xrp_to_drops

from slk.chain.chain import Chain
from slk.classes.account import Account
from slk.sidechain_params import SidechainParams

MAINCHAIN_DOOR_KEEPER = 0
SIDECHAIN_DOOR_KEEPER = 1
UPDATE_SIGNER_LIST = 2

_LSF_DISABLE_MASTER = 0x00100000  # 1048576


def _is_door_master_disabled(door_acct: str, client: SyncClient) -> bool:
    account_root = get_account_root(door_acct, client)
    flags = account_root["Flags"]
    return bool(int(flags) & _LSF_DISABLE_MASTER)


def setup_mainchain(
    mc_chain: Chain, params: SidechainParams, setup_user_accounts: bool = True
) -> None:
    """
    Set up the mainchain.

    Args:
        mc_chain: The mainchain.
        params: The command-line arguments for setup.
        setup_user_accounts: Whether to create and fund a user account and add it to
            the list of known accounts under the name "alice". The default is True.

    Raises:
        Exception: If the issuer on an external network doesn't exist.
    """
    mc_chain.add_to_keymanager(params.mc_door_account)
    if setup_user_accounts:
        mc_chain.add_to_keymanager(params.user_account)

    # mc_chain.request(LogLevel('fatal'))
    # TODO: only do all this setup for external network if it hasn't already been done

    if params.main_standalone:
        issuer = params.genesis_account
    else:
        issuer = Account.from_seed("issuer", params.issuer)
        mc_chain.add_to_keymanager(issuer)

        if not does_account_exist(issuer.account_id, mc_chain.node.client):
            raise Exception(f"Account {issuer} needs to be funded to exist.")

    # Allow rippling through the IOU issuer account
    mc_chain.send_signed(
        AccountSet(
            account=issuer.account_id,
            set_flag=AccountSetFlag.ASF_DEFAULT_RIPPLE,
        )
    )
    mc_chain.maybe_ledger_accept()

    door_acct = params.mc_door_account.account_id

    # Create and fund the mc door account
    if params.main_standalone:
        mc_chain.send_signed(
            Payment(
                account=params.genesis_account.account_id,
                destination=door_acct,
                amount=xrp_to_drops(1_000),
            )
        )
        mc_chain.maybe_ledger_accept()
    else:
        if not does_account_exist(door_acct, mc_chain.node.client):
            raise Exception(f"Account {door_acct} needs to be funded to exist.")

    if does_account_exist(door_acct, mc_chain.node.client) and _is_door_master_disabled(
        door_acct, mc_chain.node.client
    ):
        # assumed that setup is already done
        # TODO: check if the enabled keys are actually from these federators
        return

    # Create a trust line so USD/root account ious can be sent cross chain
    mc_chain.send_signed(
        TrustSet(
            account=door_acct,
            limit_amount=IssuedCurrencyAmount(
                value=str(1_000_000),
                currency="USD",
                issuer=issuer.account_id,
            ),
        )
    )

    # set the chain's signer list and disable the master key
    # quorum is 80%
    divide = 4 * len(params.federators)
    by = 5
    quorum = (divide + by - 1) // by
    mc_chain.send_signed(
        SignerListSet(
            account=door_acct,
            signer_quorum=quorum,
            signer_entries=[
                SignerEntry(account=federator, signer_weight=1)
                for federator in params.federators
            ],
        )
    )
    mc_chain.maybe_ledger_accept()
    mc_chain.send_signed(
        TicketCreate(
            account=door_acct,
            source_tag=MAINCHAIN_DOOR_KEEPER,
            ticket_count=1,
        )
    )
    mc_chain.maybe_ledger_accept()
    mc_chain.send_signed(
        TicketCreate(
            account=door_acct,
            source_tag=SIDECHAIN_DOOR_KEEPER,
            ticket_count=1,
        )
    )
    mc_chain.maybe_ledger_accept()
    mc_chain.send_signed(
        TicketCreate(
            account=door_acct,
            source_tag=UPDATE_SIGNER_LIST,
            ticket_count=1,
        )
    )
    mc_chain.maybe_ledger_accept()
    mc_chain.send_signed(
        AccountSet(
            account=door_acct,
            set_flag=AccountSetFlag.ASF_DISABLE_MASTER,
        )
    )
    mc_chain.maybe_ledger_accept()

    if setup_user_accounts:
        # Create and fund a regular user account
        mc_chain.send_signed(
            Payment(
                account=params.genesis_account.account_id,
                destination=params.user_account.account_id,
                amount=str(2_000),
            )
        )
        mc_chain.maybe_ledger_accept()


def setup_sidechain(
    sc_chain: Chain, params: SidechainParams, setup_user_accounts: bool = True
) -> None:
    """
    Set up the sidechain.

    Args:
        sc_chain: The sidechain.
        params: The command-line arguments for setup.
        setup_user_accounts: Whether to create and fund a user account and add it to
            the list of known accounts under the name "alice". The default is True.
    """
    sc_chain.add_to_keymanager(params.sc_door_account)
    if setup_user_accounts:
        sc_chain.add_to_keymanager(params.user_account)

    # sc_chain.send_signed(LogLevel('fatal'))
    # sc_chain.send_signed(LogLevel('trace', partition='SidechainFederator'))

    # set the chain's signer list and disable the master key
    # quorum is 80%
    divide = 4 * len(params.federators)
    by = 5
    quorum = (divide + by - 1) // by
    sc_chain.send_signed(
        SignerListSet(
            account=params.genesis_account.account_id,
            signer_quorum=quorum,
            signer_entries=[
                SignerEntry(account=federator, signer_weight=1)
                for federator in params.federators
            ],
        )
    )
    sc_chain.maybe_ledger_accept()
    sc_chain.send_signed(
        TicketCreate(
            account=params.genesis_account.account_id,
            source_tag=MAINCHAIN_DOOR_KEEPER,
            ticket_count=1,
        )
    )
    sc_chain.maybe_ledger_accept()
    sc_chain.send_signed(
        TicketCreate(
            account=params.genesis_account.account_id,
            source_tag=SIDECHAIN_DOOR_KEEPER,
            ticket_count=1,
        )
    )
    sc_chain.maybe_ledger_accept()
    sc_chain.send_signed(
        TicketCreate(
            account=params.genesis_account.account_id,
            source_tag=UPDATE_SIGNER_LIST,
            ticket_count=1,
        )
    )
    sc_chain.maybe_ledger_accept()
    sc_chain.send_signed(
        AccountSet(
            account=params.genesis_account.account_id,
            set_flag=AccountSetFlag.ASF_DISABLE_MASTER,
        )
    )
    sc_chain.maybe_ledger_accept()
