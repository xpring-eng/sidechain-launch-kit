"""Represents one node in a chain and its network connection."""

from __future__ import annotations

import os
import socket
import subprocess
import time
from typing import Any, Dict, List, Optional

from xrpl.clients import WebsocketClient
from xrpl.models import Request, ServerInfo, Transaction
from xrpl.transaction import safe_sign_and_submit_transaction
from xrpl.wallet import Wallet

from slk.classes.config_file import ConfigFile


class Node:
    """Represents one node in a chain and its network connection."""

    def __init__(
        self: Node,
        *,
        config: ConfigFile,
        exe: str,
        command_log: Optional[str] = None,
        name: str,
    ) -> None:
        """
        Initialize a Node.

        Args:
            config: The config file associated with this node.
            exe: The location of the rippled exe.
            command_log: The location of the log file.
            name: The name of the node (used for printing purposes).
        """
        section = config.port_ws_admin_local
        self.websocket_uri = f"{section.protocol}://{section.ip}:{section.port}"
        self.ip = section.ip
        self.port = int(section.port)
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
        # TODO: actually use `command_log`

    @property
    def config_file_name(self: Node) -> str:
        """
        Get the file name/location for the config file that this node is using.

        Returns:
            The config file name/location.
        """
        return self.config.get_file_name()

    def shutdown(self: Node) -> None:
        """Shut down the connection to the server."""
        self.client.close()

    @property
    def running(self: Node) -> bool:
        """
        Returns whether the chain is running.

        Returns:
            Whether the chain is running.
        """
        return self.pid is not None

    def get_pid(self: Node) -> Optional[int]:
        """
        Get the process id for the server the node is running.

        Returns:
            The process id for the server the node is running.
        """
        return self.pid

    def request(self: Node, req: Request) -> Dict[str, Any]:
        """
        Send a request to the rippled node and return the response.

        Args:
            req: Request to send to the node.

        Returns:
            The response from the node.

        Raises:
            Exception: If the transaction fails.
        """
        if not self.client.is_open():
            self.client.open()
        response = self.client.request(req)
        if response.is_successful():
            return response.result
        raise Exception("failed transaction", response.result)

    def sign_and_submit(self: Node, txn: Transaction, wallet: Wallet) -> Dict[str, Any]:
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
        return safe_sign_and_submit_transaction(txn, wallet, self.client).result

    def start_server(
        self: Node,
        *,
        extra_args: Optional[List[str]] = None,
        standalone: bool = False,
        server_out: str = os.devnull,
    ) -> None:
        """
        Start up the server.

        Args:
            extra_args: Extra arguments to pass to the server.
            standalone: Whether to run the server in standalone mode.
            server_out: The log file for server information.
        """
        if extra_args is None:
            extra_args = []
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
        """
        Stop the server.

        Args:
            server_out: The log file for server information.
        """
        to_run = [self.exe, "--conf", self.config_file_name]
        fout = open(os.devnull, "w")
        subprocess.Popen(to_run + ["stop"], stdout=fout, stderr=subprocess.STDOUT)

        assert self.process is not None
        self.process.wait()
        self.pid = None

    def server_started(self: Node) -> bool:
        """
        Determine whether the server the node is connected to has started and is ready
        to accept a WebSocket connection on its port.

        Returns:
            Whether the socket is open and ready to accept a WebSocket connection.
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            result = sock.connect_ex((self.ip, self.port))
            return result == 0  # means the WS port is open for connections

    def wait_for_validated_ledger(self: Node) -> None:
        """
        Wait for the server to have validated ledgers.

        Raises:
            ValueError: if the servers were unable to sync.
        """
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

        raise ValueError(f"Could not sync server {self.name}")

    def get_brief_server_info(self: Node) -> Dict[str, Any]:
        """
        Get a dictionary of the server_state, validated_ledger_seq, and
        complete_ledgers for the node.

        Returns:
            A dictionary of the server_state, validated_ledger_seq, and
            complete_ledgers for the node.
        """
        ret = {"server_state": "NA", "ledger_seq": "NA", "complete_ledgers": "NA"}
        if not self.running:
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
