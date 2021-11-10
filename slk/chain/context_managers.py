import os
import time
from contextlib import contextmanager
from typing import Generator, List, Optional

from slk.chain.chain import Chain
from slk.chain.node import Node
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
    extra_args: Optional[List[str]] = None,
) -> Generator[Chain, None, None]:
    """Start a ripple server and return a chain"""
    if extra_args is None:
        extra_args = []
    server_running = False
    chain = None
    node = Node(config=config, command_log=command_log, exe=exe, name="mainchain")
    try:
        if run_server:
            node.start_server(extra_args, standalone=True, server_out=server_out)
            server_running = True
            time.sleep(1.5)  # give process time to startup

        chain = Chain(node=node)
        yield chain
    finally:
        if chain:
            chain.shutdown()
        if run_server and server_running:
            node.stop_server()
