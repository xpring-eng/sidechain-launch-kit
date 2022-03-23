"""Helper methods for setting up chains."""

from typing import List, Optional

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
from slk.chain.context_managers import connect_to_external_chain
from slk.classes.account import Account

MAINCHAIN_DOOR_KEEPER = 0
SIDECHAIN_DOOR_KEEPER = 1
UPDATE_SIGNER_LIST = 2

_LSF_DISABLE_MASTER = 0x00100000  # 1048576

_GENESIS_ACCOUNT = Account(
    account_id="rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh",
    seed="snoPBrXtMeMyMHUVTgbuqAfg1SUTb",
    nickname="genesis",
)


def _is_door_master_disabled(door_acct: str, client: SyncClient) -> bool:
    account_root = get_account_root(door_acct, client)
    flags = account_root["Flags"]
    return bool(int(flags) & _LSF_DISABLE_MASTER)


def setup_mainchain(
    mc_chain: Chain,
    federators: List[str],
    mc_door_account: Account,
    main_standalone: bool,
    issuer_seed: Optional[str] = None,
) -> None:
    """
    Set up the mainchain.

    Args:
        mc_chain: The mainchain.
        params: The command-line arguments for setup.

    Raises:
        Exception: If the issuer on an external network doesn't exist.
    """
    mc_chain.add_to_keymanager(mc_door_account)

    # mc_chain.request(LogLevel('fatal'))
    # TODO: only do all this setup for external network if it hasn't already been done

    if main_standalone:
        issuer: Optional[Account] = _GENESIS_ACCOUNT
    elif issuer_seed is not None:
        issuer = Account.from_seed("issuer", issuer_seed)
        mc_chain.add_to_keymanager(issuer)

        if not does_account_exist(issuer.account_id, mc_chain.node.client):
            raise Exception(f"Account {issuer} needs to be funded to exist.")
    else:
        issuer = None

    if issuer is not None:
        # Allow rippling through the IOU issuer account
        mc_chain.send_signed(
            AccountSet(
                account=issuer.account_id,
                set_flag=AccountSetFlag.ASF_DEFAULT_RIPPLE,
            )
        )
        mc_chain.maybe_ledger_accept()

    door_acct = mc_door_account.account_id

    # Create and fund the mc door account
    if main_standalone:
        mc_chain.send_signed(
            Payment(
                account=_GENESIS_ACCOUNT.account_id,
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

    if issuer is not None:
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
    divide = 4 * len(federators)
    by = 5
    quorum = (divide + by - 1) // by
    mc_chain.send_signed(
        SignerListSet(
            account=door_acct,
            signer_quorum=quorum,
            signer_entries=[
                SignerEntry(account=federator, signer_weight=1)
                for federator in federators
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


def setup_sidechain(
    sc_chain: Chain,
    federators: List[str],
    sc_door_account: Account,
) -> None:
    """
    Set up the sidechain.

    Args:
        sc_chain: The sidechain.
        params: The command-line arguments for setup.
    """
    sc_chain.add_to_keymanager(sc_door_account)

    # sc_chain.send_signed(LogLevel('fatal'))
    # sc_chain.send_signed(LogLevel('trace', partition='SidechainFederator'))

    # set the chain's signer list and disable the master key
    # quorum is 80%
    divide = 4 * len(federators)
    by = 5
    quorum = (divide + by - 1) // by
    sc_chain.send_signed(
        SignerListSet(
            account=_GENESIS_ACCOUNT.account_id,
            signer_quorum=quorum,
            signer_entries=[
                SignerEntry(account=federator, signer_weight=1)
                for federator in federators
            ],
        )
    )
    sc_chain.maybe_ledger_accept()
    sc_chain.send_signed(
        TicketCreate(
            account=_GENESIS_ACCOUNT.account_id,
            source_tag=MAINCHAIN_DOOR_KEEPER,
            ticket_count=1,
        )
    )
    sc_chain.maybe_ledger_accept()
    sc_chain.send_signed(
        TicketCreate(
            account=_GENESIS_ACCOUNT.account_id,
            source_tag=SIDECHAIN_DOOR_KEEPER,
            ticket_count=1,
        )
    )
    sc_chain.maybe_ledger_accept()
    sc_chain.send_signed(
        TicketCreate(
            account=_GENESIS_ACCOUNT.account_id,
            source_tag=UPDATE_SIGNER_LIST,
            ticket_count=1,
        )
    )
    sc_chain.maybe_ledger_accept()
    sc_chain.send_signed(
        AccountSet(
            account=_GENESIS_ACCOUNT.account_id,
            set_flag=AccountSetFlag.ASF_DISABLE_MASTER,
        )
    )
    sc_chain.maybe_ledger_accept()


def setup_prod_mainchain(
    mainnet_url: str,
    mainnet_ws_port: int,
    federators: List[str],
    mc_door_account: Account,
    issuer: Optional[str] = None,
) -> None:
    with connect_to_external_chain(
        # TODO: stop hardcoding this
        url=mainnet_url,
        port=mainnet_ws_port,
    ) as mc_chain:
        setup_mainchain(mc_chain, federators, mc_door_account, False, issuer)


def setup_prod_sidechain(
    sidechain_url: str,
    sidechain_ws_port: int,
    federators: List[str],
    sc_door_account: Account,
) -> None:
    with connect_to_external_chain(
        url=sidechain_url,
        port=sidechain_ws_port,
    ) as sc_chain:
        setup_sidechain(sc_chain, federators, sc_door_account)


def main(
    mainnet_url: str,
    mainnet_ws_port: int,
    sidechain_url: str,
    sidechain_ws_port: int,
    federators: List[str],
    mc_door_account: Account,
    sc_door_account: Account,
    issuer: Optional[str] = None,
) -> None:
    setup_prod_mainchain(mainnet_url, mainnet_ws_port, federators, mc_door_account, issuer)
    setup_prod_sidechain(sidechain_url, sidechain_ws_port, federators, sc_door_account)


# TODO: set up CLI args
# if __name__ == "__main__":
#     main()
