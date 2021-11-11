from typing import Any, Dict, List, Optional

from slk.chain.chain import Chain
from slk.classes.common import Account


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
