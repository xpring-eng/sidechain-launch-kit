"""Bring up a rippled sidechain network from a set of config files with fixed ips."""

import glob
import os
import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Set, Union

from xrpl.models import FederatorInfo

from slk.chain import Chain
from slk.config_file import ConfigFile
from slk.node import Node


class Sidechain(Chain):
    # If run_server is None, run all the servers.
    # This is useful to help debugging
    def __init__(
        self,
        exe: str,
        configs: List[ConfigFile],
        *,
        command_logs: Optional[List[Optional[str]]] = None,
        run_server: Optional[List[bool]] = None,
        extra_args: Optional[List[List[str]]] = None,
    ):
        if not configs:
            raise ValueError("Must specify at least one config")

        if run_server and len(run_server) != len(configs):
            raise ValueError(
                "run_server length must match number of configs (or be None): "
                f"{len(configs) = } {len(run_server) = }"
            )

        configs = configs
        self.nodes: List[Node] = []
        self.running_server_indexes: Set[int] = set()

        if run_server is None:
            run_server = []
        run_server += [True] * (len(configs) - len(run_server))

        self.run_server = run_server

        if command_logs is None:
            command_logs = []
        command_logs += [None] * (len(configs) - len(command_logs))
        # TODO: figure out what all these Nones do

        # remove the old database directories.
        # we want tests to start from the same empty state every time
        for config in configs:
            db_path = config.database_path.get_line()
            if db_path and os.path.isdir(db_path):
                files = glob.glob(f"{db_path}/**", recursive=True)
                for f in files:
                    if os.path.isdir(f):
                        continue
                    os.unlink(f)

        node_num = 0
        for config, log in zip(configs, command_logs):
            node = Node(
                config=config, command_log=log, exe=exe, name=f"sidechain {node_num}"
            )
            node_num += 1
            self.nodes.append(node)

        super().__init__(node=self.nodes[0])

        self.servers_start(extra_args=extra_args)

    def shutdown(self) -> None:
        for a in self.nodes:
            a.shutdown()

        self.servers_stop()

    @property
    def standalone(self) -> bool:
        return False

    def num_nodes(self) -> int:
        return len(self.nodes)

    # TODO: type this better
    def get_node(self, i: Optional[int] = None) -> Node:
        assert i is not None
        return self.nodes[i]

    def get_configs(self) -> List[ConfigFile]:
        return [c.config for c in self.nodes]

    def get_pids(self) -> List[int]:
        return [pid for c in self.nodes if (pid := c.get_pid()) is not None]

    def federator_info(
        self, server_indexes: Optional[Union[Set[int], List[int]]] = None
    ) -> Dict[int, Dict[str, Any]]:
        # key is server index. value is federator_info result
        result_dict = {}
        if server_indexes is None or len(server_indexes) == 0:
            server_indexes = [i for i in range(self.num_nodes()) if self.is_running(i)]
        for i in server_indexes:
            if self.is_running(i):
                result_dict[i] = self.get_node(i).request(FederatorInfo())
        return result_dict

    # Get a dict of the server_state, validated_ledger_seq, and complete_ledgers
    def get_brief_server_info(self) -> Dict[str, List[Dict[str, Any]]]:
        ret: Dict[str, List[Dict[str, Any]]] = {
            "server_state": [],
            "ledger_seq": [],
            "complete_ledgers": [],
        }
        for n in self.nodes:
            r = n.get_brief_server_info()
            for (k, v) in r.items():
                ret[k].append(v)
        return ret

    # returns true if the server is running, false if not. Note, this relies on
    # servers being shut down through the `servers_stop` interface. If a server
    # crashes, or is started or stopped through other means, an incorrect status
    # may be reported.
    def get_running_status(self) -> List[bool]:
        return [i in self.running_server_indexes for i in range(len(self.nodes))]

    def is_running(self, index: int) -> bool:
        return index in self.running_server_indexes

    def wait_for_validated_ledger(self) -> None:
        """Don't return until the network has at least one validated ledger"""
        print("")  # adds some spacing after the rippled startup messages
        for i in range(len(self.nodes)):
            self.nodes[i].wait_for_validated_ledger()

    def servers_start(
        self,
        server_indexes: Optional[Union[Set[int], List[int]]] = None,
        *,
        extra_args: Optional[List[List[str]]] = None,
    ) -> None:
        if server_indexes is None:
            server_indexes = [i for i in range(len(self.nodes))]

        if extra_args is None:
            extra_args = []
        extra_args += [list()] * (len(self.nodes) - len(extra_args))

        for i in server_indexes:
            if i in self.running_server_indexes or not self.run_server[i]:
                continue

            node = self.nodes[i]
            node.start_server(extra_args[i])
            self.running_server_indexes.add(i)

        time.sleep(2)  # give servers time to start

    def servers_stop(
        self, server_indexes: Optional[Union[Set[int], List[int]]] = None
    ) -> None:
        if server_indexes is None:
            server_indexes = self.running_server_indexes.copy()

        if 0 in server_indexes:
            print(
                "WARNING: Server 0 is being stopped. RPC commands cannot be sent until "
                "this is restarted."
            )

        for i in server_indexes:
            if i not in self.running_server_indexes:
                continue
            node = self.nodes[i]
            node.stop_server()
            self.running_server_indexes.discard(i)


# TODO: rename this method to better represent what it does
# Start a chain for a network with the config files matched by
# `config_file_prefix*/rippled.cfg`
@contextmanager
def sidechain_network(
    *,
    exe: str,
    configs: List[ConfigFile],
    command_logs: Optional[List[Optional[str]]] = None,
    run_server: Optional[List[bool]] = None,
    extra_args: Optional[List[List[str]]] = None,
) -> Generator[Chain, None, None]:
    """Start a ripple testnet and return a chain"""
    try:
        chain = None
        chain = Sidechain(
            exe,
            configs,
            command_logs=command_logs,
            run_server=run_server,
            extra_args=extra_args,
        )
        chain.wait_for_validated_ledger()
        yield chain
    finally:
        if chain:
            chain.shutdown()
