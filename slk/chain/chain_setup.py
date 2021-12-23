from xrpl.account import does_account_exist
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


def setup_mainchain(
    mc_chain: Chain, params: SidechainParams, setup_user_accounts: bool = True
) -> None:
    mc_chain.add_to_keymanager(params.mc_door_account)
    if setup_user_accounts:
        mc_chain.add_to_keymanager(params.user_account)

    # mc_chain.request(LogLevel('fatal'))
    # TODO: only do all this setup for external network if it hasn't already been done

    # TODO: set up cross-chain ious
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

    # Create and fund the mc door account
    if params.main_standalone:
        mc_chain.send_signed(
            Payment(
                account=params.genesis_account.account_id,
                destination=params.mc_door_account.account_id,
                amount=xrp_to_drops(1_000),
            )
        )
        mc_chain.maybe_ledger_accept()
    else:
        if not does_account_exist(
            params.mc_door_account.account_id, mc_chain.node.client
        ):
            raise Exception(
                f"Account {params.mc_door_account.account_id} needs to be funded to "
                "exist."
            )

    # TODO: set up cross-chain ious
    # Create a trust line so USD/root account ious can be sent cross chain
    mc_chain.send_signed(
        TrustSet(
            account=params.mc_door_account.account_id,
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
