from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from xrpl.clients import WebsocketClient
from xrpl.models import ServerInfo, Transaction
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

    def sign_and_submit(
        self: ExternalNode, txn: Transaction, wallet: Wallet
    ) -> Dict[str, Any]:
        if not self.client.is_open():
            self.client.open()
        from pprint import pprint

        pprint(txn.to_dict())
        autofilled = safe_sign_and_autofill_transaction(txn, wallet, self.client)
        result = send_reliable_submission(autofilled, self.client).result
        pprint(result)
        return result

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

    # Get a dict of the server_state, validated_ledger_seq, and complete_ledgers
    def get_brief_server_info(self: ExternalNode) -> Dict[str, Any]:
        ret = {"server_state": "NA", "ledger_seq": "NA", "complete_ledgers": "NA"}
        r = self.client.request(ServerInfo()).result
        if "info" not in r:
            return ret
        r = r["info"]
        for f in ["server_state", "complete_ledgers"]:
            if f in r:
                ret[f] = r[f]
        if "validated_ledger" in r:
            ret["ledger_seq"] = r["validated_ledger"]["seq"]
        return ret
