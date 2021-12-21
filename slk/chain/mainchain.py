"""Representation of a standalone mainchain."""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Set, Union

from xrpl.models import FederatorInfo

from slk.chain.chain import Chain
from slk.chain.node import Node
from slk.classes.config_file import ConfigFile


class Mainchain(Chain):
    """Representation of a standalone mainchain."""

    def __init__(
        self: Mainchain,
        exe: str,
        *,
        config: ConfigFile,
        command_log: Optional[str] = None,
        run_server: bool = False,
        server_out: str = os.devnull,
    ) -> None:
        """
        Initializes a mainchain.

        Args:
            exe: The location of the rippled exe to run in standalone mode.
            config: The config file associated with this chain.
            command_log: The location of the log file.
            run_server: Whether to start the server.
            server_out: The file location for server output.
        """
        node = Node(config=config, command_log=command_log, exe=exe, name="mainchain")

        self.server_running = False

        super().__init__(node)

        if run_server:
            self.servers_start(server_out=server_out)

    @property
    def standalone(self: Mainchain) -> bool:
        """
        Return whether the chain is in standalone mode.

        Returns:
            True, because this chain is in standalone mode.
        """
        return True

    def get_pids(self: Mainchain) -> List[int]:
        """
        Return a list of process IDs for the nodes in the chain.

        Returns:
            A list of process IDs for the nodes in the chain.
        """
        if pid := self.node.get_pid():
            return [pid]
        return []

    def get_node(self: Mainchain, i: Optional[int] = None) -> Node:
        """
        Get a specific node from the chain.

        Args:
            i: The index of the node to return. For a standalone mainchain, this must
                be None.

        Returns:
            The node for the chain.
        """
        assert i is None
        return self.node

    def get_configs(self: Mainchain) -> List[ConfigFile]:
        """
        Get a list of all the config files for the nodes in the chain.

        Returns:
            A list of all the config files for the nodes in the chain.
        """
        return [self.node.config]

    def get_running_status(self: Mainchain) -> List[bool]:
        """
        Return whether the chain is up and running.

        Returns:
            A list of the running statuses of the nodes in the chain.
        """
        if self.node.get_pid():
            return [True]
        else:
            return [False]

    def shutdown(self: Mainchain) -> None:
        """Shut down the chain."""
        self.node.shutdown()
        self.servers_stop()

    def servers_start(
        self: Mainchain,
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
            Exception: If the server takes too long to start.
        """
        if server_indexes is not None:
            raise Exception("Mainchain does not have server indexes.")

        if self.server_running:
            return

        self.node.start_server(standalone=True, server_out=server_out)
        self.server_running = True

        # wait until the server has started up
        counter = 0
        while not self.node.server_started():
            counter += 1
            if counter == 20:  # 10 second timeout
                raise Exception("Timeout: server took too long to start.")
            time.sleep(0.5)

    def servers_stop(
        self: Mainchain, server_indexes: Optional[Union[Set[int], List[int]]] = None
    ) -> None:
        """
        Stop the servers for the chain.

        Args:
            server_indexes: The server indexes to start. The default is `None`, which
                starts all the servers in the chain.

        Raises:
            Exception: if server_indexes is passed in.
        """
        if server_indexes is not None:
            raise Exception("Mainchain does not have server indexes.")
        if self.server_running:
            self.node.stop_server()
            self.server_running = False

    def get_brief_server_info(self: Mainchain) -> Dict[str, List[Any]]:
        """
        Get a dictionary of the server_state, validated_ledger_seq, and
        complete_ledgers for all the nodes in the chain.

        Returns:
            A dictionary of the server_state, validated_ledger_seq, and
            complete_ledgers for all the nodes in the chain
        """
        ret = {}
        for (k, v) in self.node.get_brief_server_info().items():
            ret[k] = [v]
        return ret

    def federator_info(
        self: Mainchain, server_indexes: Optional[Union[Set[int], List[int]]] = None
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
        # TODO: do this more elegantly
        if server_indexes is not None and 0 in server_indexes:
            result_dict[0] = self.node.request(FederatorInfo())
        return result_dict
