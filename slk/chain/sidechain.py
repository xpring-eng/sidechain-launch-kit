"""Representation of a local sidechain."""
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
    """Representation of a local sidechain."""

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
        """
        Initialize a Sidechain.

        Args:
            exe: The location of the rippled exe.
            configs: The config files associated with this chain.
            command_logs: The location of the log files.
            run_server: Whether to start each of the servers.

        Raises:
            ValueError: If `len(run_server) != len(configs)`
        """
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
    def node(self: Sidechain) -> Node:
        """
        The node to interact with to fetch information from the chain.

        Returns:
            The node to interact with.

        Raises:
            Exception: if there are no nodes running.
        """
        for node in self.nodes:
            if node.running:
                return node
        raise Exception("No nodes running")

    @property
    def standalone(self: Sidechain) -> bool:
        """
        Return whether the chain is in standalone mode.

        Returns:
            True when the chain is in standalone mode, and False otherwise. A sidechain
            is by definition not in standalone, so it returns False.
        """
        return False

    def get_pids(self: Sidechain) -> List[Optional[int]]:
        """
        Return a list of process IDs for all the nodes in the chain (return None if the
        node is not running).

        Returns:
            A list of process IDs for the nodes in the chain (None if the node isn't
                running).
        """
        return [c.get_pid() for c in self.nodes]

    # TODO: type this better
    def get_node(self: Sidechain, i: Optional[int] = None) -> Node:
        """
        Get a specific node from the chain.

        Args:
            i: The index of the node to return.

        Returns:
            The node at index i.
        """
        assert i is not None
        return self.nodes[i]

    def get_configs(self: Sidechain) -> List[ConfigFile]:
        """
        Get a list of all the config files for the nodes in the chain.

        Returns:
            A list of all the config files for the nodes in the chain.
        """
        return [c.config for c in self.nodes]

    # returns true if the server is running, false if not. Note, this relies on
    # servers being shut down through the `servers_stop` interface. If a server
    # crashes, or is started or stopped through other means, an incorrect status
    # may be reported.
    def get_running_status(self: Sidechain) -> List[bool]:
        """
        Return whether the chain is up and running.

        Returns:
            A list of the running statuses of the nodes in the chain.
        """
        return [i in self.running_server_indexes for i in range(len(self.nodes))]

    def _is_running(self: Sidechain, index: int) -> bool:
        return index in self.running_server_indexes

    def shutdown(self: Sidechain) -> None:
        """Shut down the chain."""
        for a in self.nodes:
            if a.running:
                a.shutdown()

        self.servers_stop()

    def servers_start(
        self: Sidechain,
        *,
        server_indexes: Optional[Union[Set[int], List[int]]] = None,
        server_out: str = os.devnull,
    ) -> None:
        """
        Start the servers for the chain.

        Args:
            server_indexes: The server indexes to start. The default is `None`, which
                starts all the servers in the chain.
            server_out: Where to output the results.

        Raises:
            Exception: If the servers take too long to start.
        """
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
        """
        Stop the servers for the chain.

        Args:
            server_indexes: The server indexes to start. The default is `None`, which
                starts all the servers in the chain.
        """
        if server_indexes is None:
            server_indexes = self.running_server_indexes.copy()

        for i in server_indexes:
            if i not in self.running_server_indexes:
                continue
            node = self.nodes[i]
            node.stop_server()
            self.running_server_indexes.discard(i)

        if len(self.running_server_indexes) == 0:
            print(
                "WARNING: All servers are stopped. RPC commands cannot be sent "
                "until this is restarted."
            )

    def get_brief_server_info(self: Sidechain) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get a dictionary of the server_state, validated_ledger_seq, and
        complete_ledgers for all the nodes in the chain.

        Returns:
            A dictionary of the server_state, validated_ledger_seq, and
            complete_ledgers for all the nodes in the chain
        """
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

    def federator_info(
        self: Sidechain, server_indexes: Optional[Union[Set[int], List[int]]] = None
    ) -> Dict[int, Dict[str, Any]]:
        """
        Get the federator info of the servers.

        Args:
            server_indexes: The servers to query for their federator info. If None,
                treat as a wildcard. The default is None.

        Returns:
            The federator info of the servers.
        """
        # key is server index. value is federator_info result
        result_dict = {}
        if server_indexes is None or len(server_indexes) == 0:
            server_indexes = [i for i in range(len(self.nodes)) if self._is_running(i)]
        for i in server_indexes:
            if self._is_running(i):
                result_dict[i] = self.get_node(i).request(
                    GenericRequest(command="federator_info")  # type: ignore
                )
        return result_dict

    def wait_for_validated_ledger(self: Sidechain) -> None:
        """Don't return until the network has at least one validated ledger."""
        print("")  # adds some spacing after the rippled startup messages
        for i in range(len(self.nodes)):
            self.nodes[i].wait_for_validated_ledger()
