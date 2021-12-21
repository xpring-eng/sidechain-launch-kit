"""
Represents a node in an external network (e.g. mainnet/devnet/testnet) and its
network connection.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from xrpl.clients import WebsocketClient
from xrpl.models import Transaction
from xrpl.transaction import (
    safe_sign_and_autofill_transaction,
    send_reliable_submission,
)
from xrpl.wallet import Wallet

from slk.chain.node import Node


class ExternalNode(Node):
    """Client to send commands to the rippled server"""

    def __init__(
        self: ExternalNode,
        protocol: str,
        ip: str,
        port: int,
    ) -> None:
        """
        Initialize an ExternalNode. This is a connection to an external existing
        network (e.g. mainnet/devnet/testnet).

        Args:
            protocol: The protocol (WS/WSS) used to connect to the node.
            ip: The IP address of the node.
            port: The WS port of the node.
        """
        self.websocket_uri = f"{protocol}://{ip}:{port}"
        self.ip = ip
        self.port = port
        self.client = WebsocketClient(url=self.websocket_uri)
        self.name = self.websocket_uri

    @property
    def config_file_name(self: ExternalNode) -> str:
        """
        Get the file name/location for the config file that this node is using.

        Raises:
            Exception: The config file doesn't exist for an external node.
        """
        raise Exception("No config file for an external node")

    def get_pid(self: ExternalNode) -> Optional[int]:
        """
        Get the process id for the server the node is running.

        Raises:
            Exception: The PID doesn't exist for an external node.
        """
        raise Exception("No pid for an external node")

    def running(self: ExternalNode) -> bool:
        """
        Returns whether the chain is running.

        Returns:
            Whether the chain is running. Always True for an external node.
        """
        return True

    def sign_and_submit(
        self: ExternalNode, txn: Transaction, wallet: Wallet
    ) -> Dict[str, Any]:
        """
        Sign and submit the given transaction.

        Args:
            txn: The transaction to send.
            wallet: The wallet to use to sign the transaction.

        Returns:
            The result from the server for the transaction's submission.
        """
        if not self.client.is_open():
            self.client.open()
        autofilled = safe_sign_and_autofill_transaction(txn, wallet, self.client)
        return send_reliable_submission(autofilled, self.client).result

    def start_server(
        self: ExternalNode,
        *,
        extra_args: Optional[List[str]] = None,
        standalone: bool = False,
        server_out: str = os.devnull,
    ) -> None:
        """
        Start up the server. This does nothing because the external network is already
        running.

        Args:
            extra_args: Extra arguments to pass to the server.
            standalone: Whether to run the server in standalone mode.
            server_out: The log file for server information.
        """
        pass

    def stop_server(self: ExternalNode, *, server_out: str = os.devnull) -> None:
        """
        Stop the server.

        Args:
            server_out: The log file for server information.

        Raises:
            Exception: An external network cannot be stopped.
        """
        raise Exception("Cannot stop server for an external node")

    def server_started(self: ExternalNode) -> bool:
        """
        Determine whether the server the node is connected to has started and is ready
        to accept a WebSocket connection on its port.

        Returns:
            Whether the socket is open and ready to accept a WebSocket connection.
        """
        return True
