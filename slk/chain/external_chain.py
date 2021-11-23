from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Set, Union

from xrpl.models import Transaction

from slk.chain.chain import Chain
from slk.chain.external_node import ExternalNode
from slk.chain.node import Node
from slk.classes.config_file import ConfigFile


class ExternalChain(Chain):
    """Representation of one external chain (mainnet/devnet/testnet)"""

    def __init__(
        self: ExternalChain,
        url: str,
        port: int,
    ) -> None:
        pass
        super().__init__(ExternalNode("ws", url, port), add_root=False)

    @property
    def standalone(self: ExternalChain) -> bool:
        return False

    def get_pids(self: ExternalChain) -> List[int]:
        raise Exception("Cannot get pids for connection to external chain.")

    def get_node(self: ExternalChain, i: Optional[int] = None) -> Node:
        assert i is None
        return self.node

    def get_configs(self: ExternalChain) -> List[ConfigFile]:
        raise Exception("Cannot get configs for connection to external chain.")

    def get_running_status(self: ExternalChain) -> List[bool]:
        raise Exception("Cannot get running status for connection to external chain.")

    def shutdown(self: ExternalChain) -> None:
        self.node.shutdown()

    def servers_start(
        self: ExternalChain,
        *,
        server_indexes: Optional[Union[Set[int], List[int]]] = None,
        server_out: str = os.devnull,
    ) -> None:
        raise Exception("Cannot start server for connection to external chain.")

    def servers_stop(
        self: ExternalChain, server_indexes: Optional[Union[Set[int], List[int]]] = None
    ) -> None:
        raise Exception("Cannot stop server for connection to external chain.")

    # rippled stuff

    def send_signed(self: ExternalChain, txn: Transaction) -> Dict[str, Any]:
        """Sign then send the given transaction"""
        if not self.key_manager.is_account(txn.account):
            raise ValueError("Cannot sign transaction without secret key")
        account_obj = self.key_manager.get_account(txn.account)
        return self.node.sign_and_submit(txn, account_obj.wallet)
        # TODO: need relsub

    # specific rippled methods

    # Get a dict of the server_state, validated_ledger_seq, and complete_ledgers
    def get_brief_server_info(self: ExternalChain) -> Dict[str, List[Dict[str, Any]]]:
        ret = {}
        for (k, v) in self.node.get_brief_server_info().items():
            ret[k] = [v]
        return ret

    def federator_info(
        self: ExternalChain, server_indexes: Optional[Union[Set[int], List[int]]] = None
    ) -> Dict[int, Dict[str, Any]]:
        return {}
