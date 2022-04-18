"""Representation of an external network (e.g. mainnet/devnet/testnet)."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Set, Union

from slk.chain.chain import Chain
from slk.chain.external_node import ExternalNode
from slk.chain.node import Node
from slk.classes.config_file import ConfigFile


class ExternalChain(Chain):
    """Representation of an external network (e.g. mainnet/devnet/testnet)."""

    def __init__(
        self: ExternalChain,
        url: str,
        port: int,
    ) -> None:
        """
        Initializes an external chain object (the chain itself already exists).

        Args:
            url: The URL of the node.
            port: The WS public port of the node.
        """
        super().__init__(ExternalNode("ws", url, port), add_root=False)
        self.node.client.open()

    @property
    def standalone(self: ExternalChain) -> bool:
        """
        Return whether the chain is in standalone mode.

        Returns:
            True when the chain is in standalone mode, and False otherwise. An external
            chain is by definition not in standalone, so it returns False.
        """
        return False

    def get_pids(self: ExternalChain) -> List[Optional[int]]:
        """
        Return a list of process IDs for the nodes in the chain.

        Returns:
            An empty list, because the external network is not running locally and
            therefore has no PIDs.
        """
        return []

    def get_node(self: ExternalChain, i: Optional[int] = None) -> Node:
        """
        Get a specific node from the chain.

        Args:
            i: The index of the node to return. For an external chain, this must
                be None.

        Returns:
            The node for the chain.
        """
        assert i is None
        return self.node

    def get_configs(self: ExternalChain) -> List[ConfigFile]:
        """
        Get a list of all the config files for the nodes in the chain.

        Returns:
            An empty list, because the external network is not running locally and
            therefore has no config files.
        """
        return []

    def get_running_status(self: ExternalChain) -> List[bool]:
        """
        Return whether the chain is up and running.

        Returns:
            A list of booleans where each element is True if the node is already up and
            running, and false otherwise. An external chain is by definition already up
            and running, so this method returns [True].
        """
        return [True]

    def shutdown(self: ExternalChain) -> None:
        """Shut down the chain."""
        self.node.shutdown()

    def servers_start(
        self: ExternalChain,
        *,
        server_indexes: Optional[Union[Set[int], List[int]]] = None,
        server_out: str = os.devnull,
    ) -> None:
        """
        Start up the servers of the chain. This does nothing because the external
        network is already running.

        Args:
            server_indexes: The server indexes to start. The default is `None`, which
                starts all the servers in the chain.
            server_out: Where to output the results.
        """
        pass

    def servers_stop(
        self: ExternalChain, server_indexes: Optional[Union[Set[int], List[int]]] = None
    ) -> None:
        """
        Stop the servers for the chain.

        Args:
            server_indexes: The server indexes to start. The default is `None`, which
                starts all the servers in the chain.

        Raises:
            Exception: An external network cannot be stopped.
        """
        raise Exception("Cannot stop server for connection to external chain.")

    # specific rippled methods

    # Get a dict of the server_state, validated_ledger_seq, and complete_ledgers
    def get_brief_server_info(self: ExternalChain) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get a dictionary of the server_state, validated_ledger_seq, and
        complete_ledgers for the node that is connected to in the chain.

        Returns:
            A dictionary of the server_state, validated_ledger_seq, and
            complete_ledgers for the node that is connected to in the chain.
        """
        ret = {}
        for (k, v) in self.node.get_brief_server_info().items():
            ret[k] = [v]
        return ret

    def federator_info(
        self: ExternalChain, server_indexes: Optional[Union[Set[int], List[int]]] = None
    ) -> Dict[int, Dict[str, Any]]:
        """
        Get the federator info from the specified servers.

        Args:
            server_indexes: The servers to query for their federator info. If None,
                treat as a wildcard. The default is None.

        Returns:
            The federator info of the servers. This is empty, because the mainchain
            does not have federators.
        """
        return {}
