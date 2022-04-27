#!/usr/bin/env python3
"""
Script to test and debug sidechains.

The mainchain exe location can be set through the command line or
the environment variable RIPPLED_MAINCHAIN_EXE

The sidechain exe location can be set through the command line or
the environment variable RIPPLED_SIDECHAIN_EXE

The configs_dir (generated with create_config_files.py) can be set through the command
line or the environment variable RIPPLED_SIDECHAIN_CFG_DIR
"""

import os
import sys
import time
import traceback
from multiprocessing import Process, Value
from pathlib import Path
from typing import Any, Callable, ContextManager, List

from slk.chain.chain import Chain
from slk.chain.chain_setup import setup_mainchain, setup_sidechain
from slk.chain.context_managers import (
    connect_to_external_chain,
    sidechain_network,
    single_node_chain,
)
from slk.chain.external_chain import ExternalChain
from slk.chain.mainchain import Mainchain
from slk.chain.sidechain import Sidechain
from slk.classes.config_file import ConfigFile
from slk.launch.sidechain_params import SidechainParams
from slk.repl import start_repl
from slk.utils.eprint import disable_eprint, eprint
from slk.utils.log_analyzer import convert_log


def _configs_for_testnet(config_file_prefix: str) -> List[ConfigFile]:
    p = Path(config_file_prefix)
    folder = p.parent
    file_name = p.name
    file_names = []
    for f in os.listdir(folder):
        cfg = os.path.join(folder, f, "rippled.cfg")
        if f.startswith(file_name) and os.path.exists(cfg):
            file_names.append(cfg)
    file_names.sort()
    return [ConfigFile(file_name=f) for f in file_names]


def _rm_debug_log(config: ConfigFile, verbose: bool) -> None:
    try:
        debug_log = config.debug_logfile.get_line()
        if debug_log:
            if verbose:
                print(f"removing debug file: {debug_log}", flush=True)
            os.remove(debug_log)
    except:
        pass


def _convert_log_files_to_json(
    to_convert: List[ConfigFile], suffix: str, verbose: bool
) -> None:
    """
    Convert the log file to json.

    Args:
        to_convert: A list of config files to convert the debug files of.
        suffix: The suffix of the log file.
        verbose: Whether to print out extra information.
    """
    for c in to_convert:
        try:
            debug_log = c.debug_logfile.get_line()
            assert isinstance(debug_log, str)  # for typing
            if not os.path.exists(debug_log):
                continue
            converted_log = f"{debug_log}.{suffix}"
            if os.path.exists(converted_log):
                os.remove(converted_log)
            if verbose:
                print(f"Converting log {debug_log} to {converted_log}", flush=True)
            convert_log(debug_log, converted_log, pure_json=True)
        except:
            eprint("Exception converting log")


def _chains_with_callback(
    params: SidechainParams,
    callback: Callable[[Chain, Chain], None],
) -> None:
    # set up/get mainchain
    if params.main_standalone:
        # TODO: make more elegant once params is more fleshed out
        assert params.mainchain_config is not None
        _rm_debug_log(params.mainchain_config, params.verbose)
        if params.debug_mainchain:
            input("Start mainchain server and press enter to continue: ")
        mainchain: ContextManager[Chain] = single_node_chain(
            config=params.mainchain_config,
            exe=params.mainchain_exe,
            run_server=not params.debug_mainchain,
        )
    else:
        assert params.mainnet_port is not None  # TODO: type this better
        mainchain = connect_to_external_chain(
            # TODO: stop hardcoding this
            url=params.mainnet_url,
            port=params.mainnet_port,
        )

    with mainchain as mc_chain:
        if params.with_pauses:
            input("Pausing after mainchain start (press enter to continue)")

        setup_mainchain(mc_chain, params.federators, params.mc_door_account, True)
        if params.with_pauses:
            input("Pausing after mainchain setup (press enter to continue)")

        # set up/get sidechain
        if params.standalone:
            if params.debug_sidechain:
                input("Start sidechain server and press enter to continue: ")
            else:
                _rm_debug_log(params.sidechain_config, params.verbose)

            sidechain: ContextManager[Chain] = single_node_chain(
                config=params.sidechain_config,
                exe=params.sidechain_exe,
                run_server=not params.debug_sidechain,
            )
        else:
            sidechain_configs = _configs_for_testnet(
                f"{params.configs_dir}/sidechain_testnet/sidechain_"
            )
            for c in sidechain_configs:
                _rm_debug_log(c, params.verbose)

            run_server_list = [True] * len(sidechain_configs)
            if params.debug_sidechain:
                run_server_list[0] = False
                input(
                    f"Start testnet server {sidechain_configs[0].get_file_name()} and "
                    "press enter to continue: "
                )
            sidechain = sidechain_network(
                exe=params.sidechain_exe,
                configs=sidechain_configs,
                run_server=run_server_list,
            )

        with sidechain as sc_chain:
            if params.with_pauses:
                input("Pausing after testnet start (press enter to continue)")

            setup_sidechain(sc_chain, params.federators, params.sc_door_account)
            if params.with_pauses:
                input("Pausing after sidechain setup (press enter to continue)")
            callback(mc_chain, sc_chain)


def close_mainchain_ledgers(
    stop_token: Any, params: SidechainParams, sleep_time: int = 4
) -> None:
    """
    The mainchain runs in standalone mode. Most operations - like cross chain payments -
    will automatically close ledgers. However, some operations, like refunds, need an
    extra close. This loop automatically closes ledgers.

    Args:
        stop_token: Something to use to know when to stop.
        params: The command-line args for running the sidechain.
        sleep_time: How long to wait for a ledger close.
    """
    assert params.mainchain_config is not None  # TODO: type this better
    with single_node_chain(
        config=params.mainchain_config,
        exe=params.mainchain_exe,
        run_server=False,
    ) as mc_chain:
        while stop_token.value != 0:
            mc_chain.maybe_ledger_accept()
            time.sleep(sleep_time)


def run_chains(params: SidechainParams) -> None:
    """
    Run a mainchain and sidechain and run basic tests on it.

    Args:
        params: The command-line args for running the sidechain.
    """

    def callback(mc_chain: Chain, sc_chain: Chain) -> None:
        input("The sidechain has been set up. Press any key to kill it. ")

    _chains_with_callback(params, callback)


def run_chains_with_shell(params: SidechainParams) -> None:
    """
    Run a mainchain and sidechain and start up the REPL to interact with them.

    Args:
        params: The command-line args for running the sidechain.
    """

    def callback(mc_chain: Chain, sc_chain: Chain) -> None:
        # process will run while stop token is non-zero
        stop_token = Value("i", 1)
        p = None
        if mc_chain.standalone:
            p = Process(target=close_mainchain_ledgers, args=(stop_token, params))
            p.start()
        try:
            start_repl(mc_chain, sc_chain)
        finally:
            if p:
                stop_token.value = 0
                p.join()

    _chains_with_callback(params, callback)


def _new_close(params: SidechainParams) -> None:
    if os.fork() != 0:
        return
    assert params.mainchain_config is not None  # TODO: type this better
    mc_chain = Mainchain(
        params.mainchain_exe,
        config=params.mainchain_config,
        run_server=False,
    )
    while True:
        mc_chain.maybe_ledger_accept()
        time.sleep(4)


def run_chains_background(params: SidechainParams) -> None:
    """
    Start a mainchain and sidechain and run them in the background.

    Args:
        params: The command-line args for running the sidechain.
    """

    def callback(mc_chain: Chain, sc_chain: Chain) -> None:
        # process will run while stop token is non-zero
        if mc_chain.standalone:
            p = Process(target=_new_close, args=(params,))
            p.start()
            p.join()
        exit(0)

    # set up/get mainchain
    if params.main_standalone:
        # TODO: make more elegant once params is more fleshed out
        assert params.mainchain_config is not None
        _rm_debug_log(params.mainchain_config, params.verbose)
        if params.debug_mainchain:
            input("Start mainchain server and press enter to continue: ")
        mc_chain: Chain = Mainchain(
            exe=params.mainchain_exe,
            config=params.mainchain_config,
            run_server=not params.debug_mainchain,
        )
    else:
        assert params.mainnet_port is not None  # TODO: type this better
        mc_chain = ExternalChain(
            # TODO: stop hardcoding this
            url=params.mainnet_url,
            port=params.mainnet_port,
        )

    if params.with_pauses:
        input("Pausing after mainchain start (press enter to continue)")

    setup_mainchain(mc_chain, params.federators, params.mc_door_account, True)
    if params.with_pauses:
        input("Pausing after mainchain setup (press enter to continue)")

    # set up/get sidechain
    if params.standalone:
        if params.debug_sidechain:
            input("Start sidechain server and press enter to continue: ")
        else:
            _rm_debug_log(params.sidechain_config, params.verbose)

        sc_chain: Chain = Mainchain(
            config=params.sidechain_config,
            exe=params.sidechain_exe,
            run_server=not params.debug_sidechain,
        )
    else:
        sidechain_configs = _configs_for_testnet(
            f"{params.configs_dir}/sidechain_testnet/sidechain_"
        )
        for c in sidechain_configs:
            _rm_debug_log(c, params.verbose)

        run_server_list = [True] * len(sidechain_configs)
        if params.debug_sidechain:
            run_server_list[0] = False
            input(
                f"Start testnet server {sidechain_configs[0].get_file_name()} and "
                "press enter to continue: "
            )
        sc_chain = Sidechain(
            exe=params.sidechain_exe,
            configs=sidechain_configs,
            run_server=run_server_list,
        )
        sc_chain.wait_for_validated_ledger()

    if params.with_pauses:
        input("Pausing after testnet start (press enter to continue)")

    setup_sidechain(sc_chain, params.federators, params.sc_door_account)
    if params.with_pauses:
        input("Pausing after sidechain setup (press enter to continue)")
    callback(mc_chain, sc_chain)


def main() -> None:
    """Initialize the mainchain-sidechain network, with command-line arguments."""
    try:
        params = SidechainParams()
    except Exception:
        eprint(traceback.format_exc())
        sys.exit(1)

    if params.verbose:
        print("eprint enabled")
    else:
        disable_eprint()

    if params.background:
        run_chains_background(params)
    if params.shell:
        run_chains_with_shell(params)
    else:
        run_chains(params)


if __name__ == "__main__":
    main()
