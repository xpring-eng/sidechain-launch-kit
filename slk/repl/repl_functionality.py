import os
from typing import Any, Dict, List, Optional, Tuple

from xrpl.models import is_xrp
from xrpl.utils import drops_to_xrp

from slk.chain.chain import Chain
from slk.classes.common import Account


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
