from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

from xrpl.clients import WebsocketClient
from xrpl.models import Request, ServerInfo, Transaction
from xrpl.transaction import safe_sign_and_submit_transaction
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

    @property
    def config_file_name(self: ExternalNode) -> str:
        raise Exception("No config file for an external node")

    def shutdown(self: ExternalNode) -> None:
        self.client.close()

    def get_pid(self: ExternalNode) -> Optional[int]:
        return self.pid

    def request(self: ExternalNode, req: Request) -> Dict[str, Any]:
        if not self.client.is_open():
            self.client.open()
        response = self.client.request(req)
        if response.is_successful():
            return response.result
        raise Exception("failed transaction", response.result)

    def sign_and_submit(
        self: ExternalNode, txn: Transaction, wallet: Wallet
    ) -> Dict[str, Any]:
        if not self.client.is_open():
            self.client.open()
        return safe_sign_and_submit_transaction(txn, wallet, self.client).result

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

    def wait_for_validated_ledger(self: ExternalNode) -> None:
        for i in range(600):
            r = self.request(ServerInfo())
            state = None
            if "info" in r:
                state = r["info"]["server_state"]
                if state == "proposing":
                    print(f"Synced: {self.name} : {state}", flush=True)
                    break
            if not i % 10:
                print(f"Waiting for sync: {self.name} : {state}", flush=True)
            time.sleep(1)

        for i in range(600):
            r = self.request(ServerInfo())
            state = None
            if "info" in r:
                complete_ledgers = r["info"]["complete_ledgers"]
                if complete_ledgers and complete_ledgers != "empty":
                    print(f"Have complete ledgers: {self.name} : {state}", flush=True)
                    return
            if not i % 10:
                print(
                    f"Waiting for complete_ledgers: {self.name} : "
                    f"{complete_ledgers}",
                    flush=True,
                )
            time.sleep(1)

        raise ValueError("Could not sync server {self.config_file_name}")

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
