import os
import time
from typing import Any, Dict, List, Optional, Tuple, cast

from xrpl.models import (
    XRP,
    Currency,
    IssuedCurrency,
    IssuedCurrencyAmount,
    Memo,
    Payment,
    TrustSet,
    is_xrp,
)
from xrpl.utils import drops_to_xrp

from slk.chain.chain import Chain
from slk.classes.account import Account


def _removesuffix(phrase: str, suffix: str) -> str:
    if suffix and phrase.endswith(suffix):
        return phrase[: -len(suffix)]
    else:
        return phrase[:]


def get_account_info(
    chains: List[Chain], chain_names: List[str], account_ids: List[Optional[Account]]
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for chain, chain_name, acc in zip(chains, chain_names, account_ids):
        result = chain.get_account_info(acc)
        # TODO: figure out how to get this to work for both lists and individual
        # accounts
        # TODO: refactor substitute_nicknames to handle the chain name too
        chain_short_name = "main" if chain_name == "mainchain" else "side"
        for res in result:
            chain.substitute_nicknames(res)
            res["account"] = chain_short_name + " " + res["account"]
        results += result
    return results


def get_server_info(
    chains: List[Chain], chain_names: List[str]
) -> List[Dict[str, Any]]:
    def data_dict(chain: Chain, chain_name: str) -> Dict[str, Any]:
        # get the server_info data for a specific chain
        # TODO: refactor get_brief_server_info to make this method less clunky
        filenames = [c.get_file_name() for c in chain.get_configs()]
        chains = []
        for i in range(len(filenames)):
            chains.append(f"{chain_name} {i}")
        data: Dict[str, Any] = {"node": chains}
        data.update(
            {
                "pid": chain.get_pids(),
                "config": filenames,
                "running": chain.get_running_status(),
            }
        )
        bsi = chain.get_brief_server_info()
        data.update(bsi)
        return data

    def result_from_dicts(
        d1: Dict[str, Any], d2: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        # combine the info from the chains, refactor dict for tabulate
        data = []
        for i in range(len(d1["node"])):
            new_dict = {key: d1[key][i] for key in d1}
            data.append(new_dict)
        if d2 is not None:
            for i in range(len(d2["node"])):
                new_dict = {key: d2[key][i] for key in d2}
                data.append(new_dict)
        # shorten config filenames for space
        all_filenames = [d["config"] for d in data]
        cp = os.path.commonprefix(all_filenames)
        short_filenames = [os.path.relpath(f, cp) for f in all_filenames]
        for i in range(len(data)):
            data[i]["config"] = short_filenames[i]
        return data

    data_dicts = [
        data_dict(chain, _removesuffix(name, "chain"))
        for chain, name in zip(chains, chain_names)
    ]
    return result_from_dicts(*data_dicts)


def get_federator_info(
    info_dict: Dict[int, Dict[str, Any]], verbose: bool = False
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    def get_fed_info_table(
        info_dict: Dict[int, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        data = []
        for (k, v) in info_dict.items():
            new_dict = {}
            info = v["info"]
            new_dict["public_key"] = info["public_key"]
            mc = info["mainchain"]
            sc = info["sidechain"]
            new_dict["main last_sent_seq"] = mc["last_transaction_sent_seq"]
            new_dict["side last_sent_seq"] = sc["last_transaction_sent_seq"]
            new_dict["main seq"] = mc["sequence"]
            new_dict["side seq"] = sc["sequence"]
            new_dict["main num_pending"] = len(mc["pending_transactions"])
            new_dict["side num_pending"] = len(sc["pending_transactions"])
            new_dict["main sync_state"] = (
                mc["listener_info"]["state"] if "state" in mc["listener_info"] else None
            )
            new_dict["side sync_state"] = (
                sc["listener_info"]["state"] if "state" in sc["listener_info"] else None
            )
            data.append(new_dict)
        return data

    def get_pending_tx_info(
        info_dict: Dict[int, Dict[str, Any]], verbose: bool = False
    ) -> List[Dict[str, Any]]:
        data = []
        for (k, v) in info_dict.items():
            for chain in ["mainchain", "sidechain"]:
                short_chain_name = chain[:4] + " " + str(k)
                pending = v["info"][chain]["pending_transactions"]
                for t in pending:
                    amt = t["amount"]
                    if is_xrp(amt):
                        amt = drops_to_xrp(amt)
                    if not verbose:
                        pending_info = {
                            "chain": short_chain_name,
                            "amount": amt,
                            "dest_acct": t["destination_account"],
                            "hash": t["hash"],
                            "num_sigs": len(t["signatures"]),
                        }
                        data.append(pending_info)
                    else:
                        for sig in t["signatures"]:
                            pending_info = {
                                "chain": short_chain_name,
                                "amount": amt,
                                "dest_acct": t["destination_account"],
                                "hash": t["hash"],
                                "num_sigs": len(t["signatures"]),
                                "sigs": sig["public_key"],
                            }
        return data

    return get_fed_info_table(info_dict), get_pending_tx_info(info_dict, verbose)


def set_up_ious(mc_chain: Chain, sc_chain: Chain) -> None:
    mc_asset = IssuedCurrency(
        currency="USD", issuer=mc_chain.account_from_alias("root").account_id
    )
    sc_asset = IssuedCurrency(
        currency="USD", issuer=sc_chain.account_from_alias("door").account_id
    )
    mc_chain.add_asset_alias(mc_asset, "rrr")
    sc_chain.add_asset_alias(sc_asset, "ddd")
    mc_chain.send_signed(
        TrustSet(
            account=mc_chain.account_from_alias("alice").account_id,
            limit_amount=cast(
                IssuedCurrencyAmount,
                IssuedCurrencyAmount.from_issued_currency(mc_asset, str(1_000_000)),
            ),
        )
    )

    # create brad account on the side chain and set the trust line
    memos = [
        Memo.from_dict(
            {"MemoData": sc_chain.account_from_alias("brad").account_id_str_as_hex()}
        )
    ]
    mc_chain.send_signed(
        Payment(
            account=mc_chain.account_from_alias("alice").account_id,
            destination=mc_chain.account_from_alias("door").account_id,
            amount=str(3000 * 1_000_000),
            memos=memos,
        )
    )
    mc_chain.maybe_ledger_accept()

    # create a trust line to alice and pay her USD/rrr
    mc_chain.send_signed(
        TrustSet(
            account=mc_chain.account_from_alias("alice").account_id,
            limit_amount=cast(
                IssuedCurrencyAmount,
                IssuedCurrencyAmount.from_issued_currency(mc_asset, str(1_000_000)),
            ),
        )
    )
    mc_chain.maybe_ledger_accept()
    mc_chain.send_signed(
        Payment(
            account=mc_chain.account_from_alias("root").account_id,
            destination=mc_chain.account_from_alias("alice").account_id,
            amount=cast(
                IssuedCurrencyAmount,
                IssuedCurrencyAmount.from_issued_currency(mc_asset, str(10_000)),
            ),
        )
    )
    mc_chain.maybe_ledger_accept()

    time.sleep(2)

    # create a trust line for brad
    sc_chain.send_signed(
        TrustSet(
            account=sc_chain.account_from_alias("brad").account_id,
            limit_amount=cast(
                IssuedCurrencyAmount,
                IssuedCurrencyAmount.from_issued_currency(sc_asset, str(1_000_000)),
            ),
        )
    )


def set_up_accounts(mc_chain: Chain, sc_chain: Chain) -> None:
    for a in ["alice", "bob"]:
        mc_chain.create_account(a)
    for a in ["brad", "carol"]:
        sc_chain.create_account(a)
    amt = str(5000 * 1_000_000)
    src = mc_chain.account_from_alias("root")
    dst = mc_chain.account_from_alias("alice")
    mc_chain.send_signed(
        Payment(account=src.account_id, destination=dst.account_id, amount=amt)
    )
    mc_chain.maybe_ledger_accept()


def get_balances_data(
    chains: List[Chain],
    chain_names: List[str],
    account_ids: Optional[List[Optional[Account]]] = None,
    assets: Optional[List[List[Currency]]] = None,
    in_drops: bool = False,
) -> List[Dict[str, Any]]:
    if account_ids is None:
        account_ids = [None] * len(chains)

    if assets is None:
        # XRP and all assets in the assets alias list
        assets = [
            [cast(Currency, XRP())] + cast(List[Currency], c.known_iou_assets())
            for c in chains
        ]

    result = []
    for chain, chain_name, acc, asset in zip(chains, chain_names, account_ids, assets):
        chain_result = chain.get_balances(acc, asset)
        for chain_res in chain_result:
            chain.substitute_nicknames(chain_res)
            if not in_drops and chain_res["currency"] == "XRP":
                chain_res["balance"] = drops_to_xrp(chain_res["balance"])
            else:
                chain_res["balance"] = int(chain_res["balance"])
            chain_short_name = "main" if chain_name == "mainchain" else "side"
            chain_res["account"] = chain_short_name + " " + chain_res["account"]
        result += chain_result
    return result
