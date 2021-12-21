"""Context managers for working with a chain."""

import os
from contextlib import contextmanager
from typing import Generator, List, Optional

from slk.chain.external_chain import ExternalChain
from slk.chain.mainchain import Mainchain
from slk.chain.sidechain import Sidechain
from slk.classes.config_file import ConfigFile


# Start a chain with a single node
@contextmanager
def single_node_chain(
    *,
    config: ConfigFile,
    command_log: Optional[str] = None,
    server_out: str = os.devnull,
    run_server: bool = True,
    exe: str,
) -> Generator[Mainchain, None, None]:
    """
    Start a rippled server and return a chain.

    Args:
        config: The config file to use for rippled.
        command_log: The log file.
        server_out: The location to output stdout to. The default is os.devnull.
        run_server: Whether to start the server. The default is True.
        exe: The file location of the rippled executable.

    Yields:
        A standalone single-node chain.
    """
    chain = None
    try:
        chain = Mainchain(
            exe,
            config=config,
            command_log=command_log,
            run_server=run_server,
            server_out=server_out,
        )
        yield chain
    finally:
        if chain:
            chain.shutdown()


@contextmanager
def connect_to_external_chain(
    *,
    url: str,
    port: int,
) -> Generator[ExternalChain, None, None]:
    """Start a ripple server and return a chain"""
    chain = None
    try:
        chain = ExternalChain(url, port)
        yield chain
    finally:
        if chain:
            chain.shutdown()


# TODO: rename this method to better represent what it does
# Start a chain for a network with the config files matched by
# `config_file_prefix*/rippled.cfg`
@contextmanager
def sidechain_network(
    *,
    exe: str,
    configs: List[ConfigFile],
    command_logs: Optional[List[Optional[str]]] = None,
    run_server: Optional[List[bool]] = None,
) -> Generator[Sidechain, None, None]:
    """
    Start an XRPL testnet and return a chain.

    Args:
        exe: The file location of the rippled executable.
        configs: The config files to use for rippled.
        command_logs: The log files. Optional.
        run_server: Whether to start the server. Optional.

    Yields:
        A locally-running sidechain.
    """
    chain = None
    try:
        chain = Sidechain(
            exe,
            configs=configs,
            command_logs=command_logs,
            run_server=run_server,
        )
        chain.wait_for_validated_ledger()
        yield chain
    finally:
        if chain:
            chain.shutdown()
