"""Bring up a rippled sidechain network from a set of config files with fixed ips."""
from __future__ import annotations

import glob
import os
import time
from typing import Any, Dict, List, Optional, Set, Union

from xrpl.models import GenericRequest

from slk.chain.chain import Chain
from slk.chain.node import Node
from slk.classes.config_file import ConfigFile


class Sidechain(Chain):
    # If run_server is None, run all the servers.
    # This is useful to help debugging
    def __init__(
        self: Sidechain,
        exe: str,
        *,
        configs: List[ConfigFile],
        command_logs: Optional[List[Optional[str]]] = None,
        run_server: Optional[List[bool]] = None,
    ) -> None:
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
            self.run_server = []
        else:
            self.run_server = run_server.copy()
        # fill up the rest of run_server (so there's an element for each node)
        self.run_server += [True] * (len(configs) - len(self.run_server))

        if command_logs is None:
            node_logs: List[Optional[str]] = []
        else:
            node_logs = node_logs.copy()
        # fill up the rest of node_logs (so there's an element for each node)
        node_logs += [None] * (len(configs) - len(node_logs))

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
        for config, log in zip(configs, node_logs):
            node = Node(
                config=config, command_log=log, exe=exe, name=f"sidechain {node_num}"
            )
            node_num += 1
            self.nodes.append(node)

        super().__init__(self.nodes[0])

        self.servers_start()

    @property
    def standalone(self: Sidechain) -> bool:
        return False

    def get_pids(self: Sidechain) -> List[int]:
        return [pid for c in self.nodes if (pid := c.get_pid()) is not None]

    # TODO: type this better
    def get_node(self: Sidechain, i: Optional[int] = None) -> Node:
        assert i is not None
        return self.nodes[i]

    def get_configs(self: Sidechain) -> List[ConfigFile]:
        return [c.config for c in self.nodes]

    # returns true if the server is running, false if not. Note, this relies on
    # servers being shut down through the `servers_stop` interface. If a server
    # crashes, or is started or stopped through other means, an incorrect status
    # may be reported.
    def get_running_status(self: Sidechain) -> List[bool]:
        return [i in self.running_server_indexes for i in range(len(self.nodes))]

    def is_running(self: Sidechain, index: int) -> bool:
        return index in self.running_server_indexes

    def shutdown(self: Sidechain) -> None:
        for a in self.nodes:
            a.shutdown()

        self.servers_stop()

    def servers_start(
        self: Sidechain,
        *,
        server_indexes: Optional[Union[Set[int], List[int]]] = None,
        server_out: str = os.devnull,
    ) -> None:
        if server_indexes is None:
            server_indexes = [i for i in range(len(self.nodes))]

        for i in server_indexes:
            if i in self.running_server_indexes or not self.run_server[i]:
                continue

            node = self.nodes[i]
            node.start_server(server_out=server_out)
            self.running_server_indexes.add(i)

        # wait until the servers have started up
        counter = 0
        while not all([node.server_started() for node in self.nodes]):
            counter += 1
            if counter == 20:  # 10 second timeout
                raise Exception("Timeout: servers took too long to start.")
            time.sleep(0.5)

        for node in self.nodes:
            node.client.open()

    def servers_stop(
        self: Sidechain, server_indexes: Optional[Union[Set[int], List[int]]] = None
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

    def federator_info(
        self: Sidechain, server_indexes: Optional[Union[Set[int], List[int]]] = None
    ) -> Dict[int, Dict[str, Any]]:
        # key is server index. value is federator_info result
        result_dict = {}
        if server_indexes is None or len(server_indexes) == 0:
            server_indexes = [i for i in range(len(self.nodes)) if self.is_running(i)]
        for i in server_indexes:
            if self.is_running(i):
                result_dict[i] = self.get_node(i).request(
                    GenericRequest(command="federator_info")  # type: ignore
                )
        return result_dict

    # Get a dict of the server_state, validated_ledger_seq, and complete_ledgers
    def get_brief_server_info(self: Sidechain) -> Dict[str, List[Dict[str, Any]]]:
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

    def wait_for_validated_ledger(self: Sidechain) -> None:
        """Don't return until the network has at least one validated ledger"""
        print("")  # adds some spacing after the rippled startup messages
        for i in range(len(self.nodes)):
            self.nodes[i].wait_for_validated_ledger()
