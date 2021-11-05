from __future__ import annotations

import os
import subprocess
import time
from typing import Any, Dict, List, Optional, cast

from xrpl.clients import WebsocketClient
from xrpl.models import Request, ServerInfo, Transaction
from xrpl.transaction import safe_sign_and_submit_transaction
from xrpl.wallet import Wallet

from slk.config_file import ConfigFile


class Node:
    """Client to send commands to the rippled server"""

    def __init__(
        self: Node,
        *,
        config: ConfigFile,
        exe: str,
        command_log: Optional[str] = None,
        name: str,
    ) -> None:
        section = config.port_ws_admin_local
        self.websocket_uri = f"{section.protocol}://{section.ip}:{section.port}"
        self.name = name
        self.client = WebsocketClient(url=self.websocket_uri)
        self.config = config
        self.exe = exe
        self.command_log = command_log
        self.pid: Optional[int] = None
        self.process: Optional[subprocess.Popen[bytes]] = None
        if self.command_log is not None:
            with open(self.command_log, "w") as f:
                f.write("# Start \n")

    @property
    def config_file_name(self: Node) -> str:
        return self.config.get_file_name()

    def shutdown(self: Node) -> None:
        self.client.close()

    def get_pid(self: Node) -> Optional[int]:
        return self.pid

    def request(self: Node, req: Request) -> Dict[str, Any]:
        if not self.client.is_open():
            self.client.open()
        response = self.client.request(req)
        if response.is_successful():
            return response.result
        raise Exception("failed transaction", response.result)

    def request_json(self: Node, req: Request) -> Dict[str, Any]:
        if not self.client.is_open():
            self.client.open()
        response = self.client.request_json(req)
        if response["status"] == "success":
            return cast(Dict[str, Any], response["result"])
        raise Exception("failed transaction", response["result"])

    def sign_and_submit(self: Node, txn: Transaction, wallet: Wallet) -> Dict[str, Any]:
        if not self.client.is_open():
            self.client.open()
        return safe_sign_and_submit_transaction(txn, wallet, self.client).result

    def start_server(
        self: Node,
        extra_args: List[str],
        *,
        standalone: bool = False,
        server_out: str = os.devnull,
    ) -> None:
        to_run = [self.exe, "--conf", self.config_file_name]
        if standalone:
            to_run.append("-a")
        print(f"Starting server {self.name}")
        fout = open(server_out, "w")
        self.process = subprocess.Popen(
            to_run + extra_args, stdout=fout, stderr=subprocess.STDOUT
        )
        self.pid = self.process.pid
        print(
            f"  started rippled: {self.name} PID: {self.process.pid}",
            flush=True,
        )

    def stop_server(self: Node, *, server_out: str = os.devnull) -> None:
        to_run = [self.exe, "--conf", self.config_file_name]
        fout = open(os.devnull, "w")
        subprocess.Popen(to_run + ["stop"], stdout=fout, stderr=subprocess.STDOUT)

        assert self.process is not None
        self.process.wait()
        self.pid = -1

    def wait_for_validated_ledger(self: Node) -> None:
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
    def get_brief_server_info(self: Node) -> Dict[str, Any]:
        ret = {"server_state": "NA", "ledger_seq": "NA", "complete_ledgers": "NA"}
        if not self.pid or self.pid == -1:
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
