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
        self.websocket_uri = f"{protocol}://{ip}:{port}"
        self.ip = ip
        self.port = port
        self.client = WebsocketClient(url=self.websocket_uri)
        self.name = self.websocket_uri

    @property
    def config_file_name(self: ExternalNode) -> str:
        raise Exception("No config file for an external node")

    def get_pid(self: ExternalNode) -> Optional[int]:
        raise Exception("No pid for an external node")

    def running(self: ExternalNode) -> bool:
        return True

    def sign_and_submit(
        self: ExternalNode, txn: Transaction, wallet: Wallet
    ) -> Dict[str, Any]:
        with WebsocketClient(self.websocket_uri) as client:
            autofilled = safe_sign_and_autofill_transaction(txn, wallet, client)
            return send_reliable_submission(autofilled, client).result

    def start_server(
        self: ExternalNode,
        *,
        extra_args: Optional[List[str]] = None,
        standalone: bool = False,
        server_out: str = os.devnull,
    ) -> None:
        pass

    def stop_server(self: ExternalNode, *, server_out: str = os.devnull) -> None:
        raise Exception("Cannot stop server for an external node")

    def server_started(self: ExternalNode) -> bool:
        """
        Determine whether the server the node is connected to has started and is ready
        to accept a WebSocket connection on its port.

        Returns:
            Whether the socket is open and ready to accept a WebSocket connection.
        """
        return True
