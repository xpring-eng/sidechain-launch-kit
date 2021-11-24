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
from slk.sidechain_params import SidechainParams

MAINCHAIN_DOOR_KEEPER = 0
SIDECHAIN_DOOR_KEEPER = 1
UPDATE_SIGNER_LIST = 2


def setup_mainchain(
    mc_chain: Chain, params: SidechainParams, setup_user_accounts: bool = True
) -> None:
    """
    Set up the mainchain.

    Args:
        mc_chain: The mainchain.
        params: The command-line arguments for setup.
        setup_user_accounts: Whether to create + fund a user account. The default is
            True.
    """
    mc_chain.add_to_keymanager(params.mc_door_account)
    if setup_user_accounts:
        mc_chain.add_to_keymanager(params.user_account)

    # mc_chain.request(LogLevel('fatal'))

    # Allow rippling through the genesis account
    mc_chain.send_signed(
        AccountSet(
            account=params.genesis_account.account_id,
            set_flag=AccountSetFlag.ASF_DEFAULT_RIPPLE,
        )
    )
    mc_chain.maybe_ledger_accept()

    # Create and fund the mc door account
    mc_chain.send_signed(
        Payment(
            account=params.genesis_account.account_id,
            destination=params.mc_door_account.account_id,
            amount=xrp_to_drops(1_000),
        )
    )
    mc_chain.maybe_ledger_accept()

    # Create a trust line so USD/root account ious can be sent cross chain
    mc_chain.send_signed(
        TrustSet(
            account=params.mc_door_account.account_id,
            limit_amount=IssuedCurrencyAmount(
                value=str(1_000_000),
                currency="USD",
                issuer=params.genesis_account.account_id,
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
            account=params.mc_door_account.account_id,
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
            account=params.mc_door_account.account_id,
            source_tag=MAINCHAIN_DOOR_KEEPER,
            ticket_count=1,
        )
    )
    mc_chain.maybe_ledger_accept()
    mc_chain.send_signed(
        TicketCreate(
            account=params.mc_door_account.account_id,
            source_tag=SIDECHAIN_DOOR_KEEPER,
            ticket_count=1,
        )
    )
    mc_chain.maybe_ledger_accept()
    mc_chain.send_signed(
        TicketCreate(
            account=params.mc_door_account.account_id,
            source_tag=UPDATE_SIGNER_LIST,
            ticket_count=1,
        )
    )
    mc_chain.maybe_ledger_accept()
    mc_chain.send_signed(
        AccountSet(
            account=params.mc_door_account.account_id,
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
        setup_user_accounts: Whether to create + fund a user account. The default is
            True.
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
