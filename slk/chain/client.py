from __future__ import annotations

from typing import Any, Dict

from xrpl.clients import WebsocketClient
from xrpl.models import Request, ServerInfo, Transaction
from xrpl.transaction import (
    safe_sign_and_autofill_transaction,
    send_reliable_submission,
)
from xrpl.wallet import Wallet


class Client:
    """Client to send commands to the rippled server"""

    def __init__(
        self: Client,
        protocol: str,
        ip: str,
        port: str,
    ) -> None:
        self.websocket_uri = f"{protocol}://{ip}:{port}"
        self.ip = ip
        self.port = port
        self.client = WebsocketClient(url=self.websocket_uri)

    def shutdown(self: Client) -> None:
        self.client.close()

    def request(self: Client, req: Request) -> Dict[str, Any]:
        if not self.client.is_open():
            self.client.open()
        response = self.client.request(req)
        if response.is_successful():
            return response.result
        raise Exception("failed transaction", response.result)

    def sign_and_submit(
        self: Client, txn: Transaction, wallet: Wallet
    ) -> Dict[str, Any]:
        if not self.client.is_open():
            self.client.open()
        from pprint import pprint

        pprint(txn.to_dict())
        autofilled = safe_sign_and_autofill_transaction(txn, wallet, self.client)
        result = send_reliable_submission(autofilled, self.client).result
        pprint(result)
        return result

    # Get a dict of the server_state, validated_ledger_seq, and complete_ledgers
    def get_brief_server_info(self: Client) -> Dict[str, Any]:
        ret = {"server_state": "NA", "ledger_seq": "NA", "complete_ledgers": "NA"}
        if not self.pid:
            return ret
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
