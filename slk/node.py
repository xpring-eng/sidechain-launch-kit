import os
import subprocess
from typing import List, Optional

from xrpl.clients import WebsocketClient
from xrpl.models import ServerInfo
from xrpl.transaction import safe_sign_and_submit_transaction

from slk.config_file import ConfigFile


class Node:
    """Client to send commands to the rippled server"""

    def __init__(
        self, *, config: ConfigFile, exe: str, command_log: Optional[str] = None
    ):
        section = config.port_ws_admin_local
        self.websocket_uri = f"{section.protocol}://{section.ip}:{section.port}"
        self.client = WebsocketClient(url=self.websocket_uri)
        self.config = config
        self.exe = exe
        self.command_log = command_log
        self.subscription_websockets = []
        self.tasks = []
        self.pid = None
        self.process = None
        if command_log:
            with open(self.command_log, "w") as f:
                f.write("# Start \n")

    @property
    def config_file_name(self):
        return self.config.get_file_name()

    def shutdown(self):
        self.client.close()

    def get_pid(self) -> Optional[int]:
        return self.pid

    def request(self, req) -> dict:
        return self.client.request(req).result

    def sign_and_submit(self, txn, wallet) -> dict:
        return safe_sign_and_submit_transaction(txn, wallet, self.client).result

    # Get a dict of the server_state, validated_ledger_seq, and complete_ledgers
    def get_brief_server_info(self) -> dict:
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

    def start_server(
        self,
        extra_args: List[str],
        *,
        standalone: bool = False,
        server_out: str = os.devnull,
    ):
        to_run = [self.exe, "--conf", self.config_file_name]
        if standalone:
            to_run.append("-a")
        print(f"Starting server {self.config_file_name}")
        fout = open(server_out, "w")
        self.process = subprocess.Popen(
            to_run + extra_args, stdout=fout, stderr=subprocess.STDOUT
        )
        self.pid = self.process.pid
        print(
            f"started rippled: config: {self.config_file_name} PID: {self.process.pid}",
            flush=True,
        )

    def stop_server(self, *, server_out: str = os.devnull):
        to_run = [self.exe, "--conf", self.config_file_name]
        fout = open(os.devnull, "w")
        subprocess.Popen(to_run + ["stop"], stdout=fout, stderr=subprocess.STDOUT)

        self.process.wait()
        self.pid = -1
