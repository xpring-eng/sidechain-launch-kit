from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Set, Union

from xrpl.models import FederatorInfo

from slk.chain.chain import Chain
from slk.chain.node import Node
from slk.classes.config_file import ConfigFile


class Mainchain(Chain):
    """Representation of a mainchain."""

    def __init__(
        self: Mainchain,
        exe: str,
        *,
        config: ConfigFile,
        command_log: Optional[str] = None,
        run_server: bool = False,
        server_out: str = os.devnull,
    ) -> None:
        node = Node(config=config, command_log=command_log, exe=exe, name="mainchain")

        self.server_running = False

        super().__init__(node)

        if run_server:
            self.servers_start(server_out=server_out)

    @property
    def standalone(self: Mainchain) -> bool:
        return True

    def get_node(self: Mainchain, i: Optional[int] = None) -> Node:
        assert i is None
        return self.node

    def shutdown(self: Mainchain) -> None:
        self.node.shutdown()
        self.servers_stop()

    def get_pids(self: Mainchain) -> List[int]:
        if pid := self.node.get_pid():
            return [pid]
        return []

    def get_running_status(self: Mainchain) -> List[bool]:
        if self.node.get_pid():
            return [True]
        else:
            return [False]

    def servers_start(
        self: Mainchain,
        *,
        server_indexes: Optional[Union[Set[int], List[int]]] = None,
        server_out: str = os.devnull,
    ) -> None:
        if server_indexes is not None:
            raise Exception("Mainchain does not have server indexes.")

        if self.server_running:
            return

        self.node.start_server(standalone=True, server_out=server_out)

        time.sleep(2)  # give servers time to start

    def servers_stop(
        self: Mainchain, server_indexes: Optional[Union[Set[int], List[int]]] = None
    ) -> None:
        if server_indexes is not None:
            raise Exception("Mainchain does not have server indexes.")
        if self.server_running:
            self.node.stop_server()
            self.server_running = False

    def get_configs(self: Mainchain) -> List[ConfigFile]:
        return [self.node.config]

    # Get a dict of the server_state, validated_ledger_seq, and complete_ledgers
    def get_brief_server_info(self: Mainchain) -> Dict[str, List[Any]]:
        ret = {}
        for (k, v) in self.node.get_brief_server_info().items():
            ret[k] = [v]
        return ret

    def federator_info(
        self: Mainchain, server_indexes: Optional[Union[Set[int], List[int]]] = None
    ) -> Dict[int, Dict[str, Any]]:
        # key is server index. value is federator_info result
        result_dict = {}
        # TODO: do this more elegantly
        if server_indexes is not None and 0 in server_indexes:
            result_dict[0] = self.node.request(FederatorInfo())
        return result_dict
