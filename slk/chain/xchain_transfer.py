"""Methods for running cross-chain transfers."""

import time

from xrpl.models import Amount, Memo, Payment

from slk.chain.chain import Chain
from slk.classes.account import Account
from slk.sidechain_params import SidechainParams


def _xchain_transfer(
    from_chain: Chain,
    to_chain: Chain,
    src: Account,
    dst: Account,
    amt: Amount,
    from_chain_door: Account,
    to_chain_door: Account,
) -> None:
    memo = Memo(memo_data=dst.account_id_str_as_hex())
    print(
        f"xtx, {src.nickname} to {dst.nickname},{amt}, {from_chain_door.account_id}",
        flush=True,
    )
    response = from_chain.send_signed(
        Payment(
            account=src.account_id,
            destination=from_chain_door.account_id,
            amount=amt,
            memos=[memo],
        )
    )
    import pprint
    import sys

    pprint.pprint(response)
    sys.stdout.flush()
    from_chain.maybe_ledger_accept()
    if to_chain.standalone:
        # from_chain (side chain) sends a txn, but won't close the to_chain (main chain)
        # ledger
        time.sleep(1)
        to_chain.maybe_ledger_accept()


def main_to_side_transfer(
    mc_chain: Chain,
    sc_chain: Chain,
    src: Account,
    dst: Account,
    amt: Amount,
    params: SidechainParams,
) -> None:
    """
    Transfer value from the mainchain to the sidechain.

    Args:
        mc_chain: The mainchain.
        sc_chain: The sidechain.
        src: The account to transfer from (on the mainchain).
        dst: The account to transfer to (on the sidechain).
        amt: The amount of value to transfer.
        params: The params (which contain door account info).
    """
    # TODO: refactor so this doesn't need params
    # maybe store door account info in the chain itself?
    _xchain_transfer(
        mc_chain,
        sc_chain,
        src,
        dst,
        amt,
        params.mc_door_account,
        params.sc_door_account,
    )


def side_to_main_transfer(
    mc_chain: Chain,
    sc_chain: Chain,
    src: Account,
    dst: Account,
    amt: Amount,
    params: SidechainParams,
) -> None:
    """
    Transfer value from the sidechain to the mainchain.

    Args:
        mc_chain: The mainchain.
        sc_chain: The sidechain.
        src: The account to transfer from (on the sidechain).
        dst: The account to transfer to (on the mainchain).
        amt: The amount of value to transfer.
        params: The params (which contain door account info).
    """
    _xchain_transfer(
        sc_chain,
        mc_chain,
        src,
        dst,
        amt,
        params.sc_door_account,
        params.mc_door_account,
    )
