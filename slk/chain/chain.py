from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Set, Union

from xrpl.models import FederatorInfo

from slk.chain.chain_base import ChainBase
from slk.chain.node import Node
from slk.classes.config_file import ConfigFile


class Chain(ChainBase):
    """Representation of one chain (mainchain/sidechain)"""

    def __init__(
        self: Chain,
        exe: str,
        *,
        config: ConfigFile,
        command_log: Optional[str] = None,
        run_server: bool = False,
        extra_args: Optional[List[str]] = None,
        server_out: str = os.devnull,
    ) -> None:
        node = Node(config=config, command_log=command_log, exe=exe, name="mainchain")

        self.server_running = False

        super().__init__(node)

        if run_server:
            self.servers_start(extra_args=extra_args, server_out=server_out)

    @property
    def standalone(self: Chain) -> bool:
        return True

    def get_node(self: Chain, i: Optional[int] = None) -> Node:
        assert i is None
        return self.node

    def shutdown(self: Chain) -> None:
        self.node.shutdown()
        self.servers_stop()

    def get_pids(self: Chain) -> List[int]:
        if pid := self.node.get_pid():
            return [pid]
        return []

    def get_running_status(self: Chain) -> List[bool]:
        if self.node.get_pid():
            return [True]
        else:
            return [False]

    def servers_start(
        self: Chain,
        *,
        extra_args: Optional[List[str]] = None,
        server_out: str = os.devnull,
    ) -> None:
        if extra_args is None:
            extra_args = []

        if self.server_running:
            return

        self.node.start_server(
            standalone=True, extra_args=extra_args, server_out=server_out
        )

        time.sleep(2)  # give servers time to start

    def servers_stop(
        self: Chain, server_indexes: Optional[Union[Set[int], List[int]]] = None
    ) -> None:
        if self.server_running:
            self.node.stop_server()
            self.server_running = False

    def get_configs(self: Chain) -> List[ConfigFile]:
        return [self.node.config]

    # Get a dict of the server_state, validated_ledger_seq, and complete_ledgers
    def get_brief_server_info(self: Chain) -> Dict[str, List[Any]]:
        ret = {}
        for (k, v) in self.node.get_brief_server_info().items():
            ret[k] = [v]
        return ret

    def federator_info(
        self: Chain, server_indexes: Optional[Union[Set[int], List[int]]] = None
    ) -> Dict[int, Dict[str, Any]]:
        # key is server index. value is federator_info result
        result_dict = {}
        # TODO: do this more elegantly
        if server_indexes is not None and 0 in server_indexes:
            result_dict[0] = self.node.request(FederatorInfo())
        return result_dict
