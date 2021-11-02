import time

from xrpl.models import Amount, Memo, Payment

from slk.chain import Chain
from slk.common import Account
from slk.sidechain_params import SidechainParams


def _xchain_transfer(
    from_chain: Chain,
    to_chain: Chain,
    src: Account,
    dst: Account,
    amt: Amount,
    from_chain_door: Account,
    to_chain_door: Account,
):
    memo = Memo(memo_data=dst.account_id_str_as_hex())
    from_chain(
        Payment(
            account=src.account_id,
            destination=from_chain_door.account_id,
            amount=amt,
            memos=[memo],
        )
    )
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
):
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
):
    _xchain_transfer(
        sc_chain,
        mc_chain,
        src,
        dst,
        amt,
        params.sc_door_account,
        params.mc_door_account,
    )
