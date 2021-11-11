import os
from typing import Any, Dict, List, Optional

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
