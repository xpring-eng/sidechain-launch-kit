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
from multiprocessing import Process, Value
from pathlib import Path
from typing import Any, Callable, List

from slk.chain.chain import Chain
from slk.chain.chain_setup import setup_mainchain, setup_sidechain
from slk.chain.context_managers import (
    connect_to_external_chain,
    sidechain_network,
    single_node_chain,
)
from slk.chain.xchain_transfer import main_to_side_transfer, side_to_main_transfer
from slk.classes.config_file import ConfigFile
from slk.repl import set_hooks_dir, start_repl
from slk.sidechain_params import SidechainParams
from slk.utils.eprint import disable_eprint, eprint
from slk.utils.log_analyzer import convert_log


def _simple_test(mc_chain: Chain, sc_chain: Chain, params: SidechainParams) -> None:
    try:
        bob = sc_chain.create_account("bob")
        main_to_side_transfer(
            mc_chain, sc_chain, params.user_account, bob, "200", params
        )
        main_to_side_transfer(
            mc_chain, sc_chain, params.user_account, bob, "60", params
        )

        if params.with_pauses:
            _convert_log_files_to_json(
                mc_chain.get_configs() + sc_chain.get_configs(),
                "checkpoint1.json",
                params.verbose,
            )
            input("Pausing to check for main -> side txns (press enter to continue)")

        side_to_main_transfer(mc_chain, sc_chain, bob, params.user_account, "9", params)
        side_to_main_transfer(
            mc_chain, sc_chain, bob, params.user_account, "11", params
        )

        if params.with_pauses:
            input("Pausing to check for side -> main txns (press enter to continue)")
    finally:
        _convert_log_files_to_json(
            mc_chain.get_configs() + sc_chain.get_configs(),
            "final.json",
            params.verbose,
        )


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


def _standalone_with_callback(
    params: SidechainParams,
    callback: Callable[[Chain, Chain], None],
    setup_user_accounts: bool = True,
) -> None:
    # TODO: make more elegant once params is more fleshed out
    assert params.mainchain_config is not None
    if params.debug_mainchain:
        input("Start mainchain server and press enter to continue: ")
    else:
        _rm_debug_log(params.mainchain_config, params.verbose)
    with single_node_chain(
        config=params.mainchain_config,
        exe=params.mainchain_exe,
        run_server=not params.debug_mainchain,
    ) as mc_chain:

        setup_mainchain(mc_chain, params, setup_user_accounts)

        if params.debug_sidechain:
            input("Start sidechain server and press enter to continue: ")
        else:
            _rm_debug_log(params.sidechain_config, params.verbose)
        with single_node_chain(
            config=params.sidechain_config,
            exe=params.sidechain_exe,
            run_server=not params.debug_sidechain,
        ) as sc_chain:

            setup_sidechain(sc_chain, params, setup_user_accounts)
            callback(mc_chain, sc_chain)


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


def _multinode_with_callback(
    params: SidechainParams,
    callback: Callable[[Chain, Chain], None],
    setup_user_accounts: bool = True,
) -> None:

    mainchain_cfg = ConfigFile(
        file_name=f"{params.configs_dir}/sidechain_testnet/mainchain/rippled.cfg"
    )
    _rm_debug_log(mainchain_cfg, params.verbose)
    if params.debug_mainchain:
        input("Start mainchain server and press enter to continue: ")
    with single_node_chain(
        config=mainchain_cfg,
        exe=params.mainchain_exe,
        run_server=not params.debug_mainchain,
    ) as mc_chain:
        if params.with_pauses:
            input("Pausing after mainchain start (press enter to continue)")

        setup_mainchain(mc_chain, params, setup_user_accounts)
        if params.with_pauses:
            input("Pausing after mainchain setup (press enter to continue)")

        testnet_configs = _configs_for_testnet(
            f"{params.configs_dir}/sidechain_testnet/sidechain_"
        )
        for c in testnet_configs:
            _rm_debug_log(c, params.verbose)

        run_server_list = [True] * len(testnet_configs)
        if params.debug_sidechain:
            run_server_list[0] = False
            input(
                f"Start testnet server {testnet_configs[0].get_file_name()} and press "
                "enter to continue: "
            )

        with sidechain_network(
            exe=params.sidechain_exe,
            configs=testnet_configs,
            run_server=run_server_list,
        ) as sc_chain:

            if params.with_pauses:
                input("Pausing after testnet start (press enter to continue)")

            setup_sidechain(sc_chain, params, setup_user_accounts)
            if params.with_pauses:
                input("Pausing after sidechain setup (press enter to continue)")
            callback(mc_chain, sc_chain)


def _external_node_with_callback(
    params: SidechainParams,
    callback: Callable[[Chain, Chain], None],
    setup_user_accounts: bool = True,
) -> None:
    assert params.mainnet_port is not None  # TODO: type this better
    with connect_to_external_chain(
        # TODO: stop hardcoding this
        url=params.mainnet_url,
        port=params.mainnet_port,
    ) as mc_chain:
        setup_mainchain(mc_chain, params, setup_user_accounts)
        if params.with_pauses:
            input("Pausing after mainchain setup (press enter to continue)")

        testnet_configs = _configs_for_testnet(
            f"{params.configs_dir}/sidechain_testnet/sidechain_"
        )
        for c in testnet_configs:
            _rm_debug_log(c, params.verbose)

        run_server_list = [True] * len(testnet_configs)
        if params.debug_sidechain:
            run_server_list[0] = False
            input(
                f"Start testnet server {testnet_configs[0].get_file_name()} and press "
                "enter to continue: "
            )

        with sidechain_network(
            exe=params.sidechain_exe,
            configs=testnet_configs,
            run_server=run_server_list,
        ) as sc_chain:

            if params.with_pauses:
                input("Pausing after testnet start (press enter to continue)")

            setup_sidechain(sc_chain, params, setup_user_accounts)
            if params.with_pauses:
                input("Pausing after sidechain setup (press enter to continue)")
            callback(mc_chain, sc_chain)


def standalone_test(params: SidechainParams) -> None:
    """
    Run a mainchain and sidechain in standalone mode and run basic tests on it.

    Args:
        params: The command-line args for running the sidechain.
    """

    def callback(mc_chain: Chain, sc_chain: Chain) -> None:
        _simple_test(mc_chain, sc_chain, params)

    _standalone_with_callback(params, callback)


def multinode_test(params: SidechainParams) -> None:
    """
    Run a mainchain in standalone mode and a multi-node sidechain and run basic tests
    on it.

    Args:
        params: The command-line args for running the sidechain.
    """

    def callback(mc_chain: Chain, sc_chain: Chain) -> None:
        _simple_test(mc_chain, sc_chain, params)

    _multinode_with_callback(params, callback)


def external_node_test(params: SidechainParams) -> None:
    """
    Run a connection to an external chainand a multi-node sidechain and run basic tests
    on it.

    Args:
        params: The command-line args for running the sidechain.
    """

    def callback(mc_chain: Chain, sc_chain: Chain) -> None:
        _simple_test(mc_chain, sc_chain, params)

    _external_node_with_callback(params, callback)


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


def standalone_interactive_repl(params: SidechainParams) -> None:
    """
    Run a mainchain and sidechain in standalone mode and start up the REPL to interact
    with them.

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

    _standalone_with_callback(params, callback, setup_user_accounts=False)


def multinode_interactive_repl(params: SidechainParams) -> None:
    """
    Run a mainchain in standalone mode and a multi-node sidechain and start up the REPL
    to interact with them.

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

    _multinode_with_callback(params, callback, setup_user_accounts=False)


def external_node_interactive_repl(params: SidechainParams) -> None:
    """
    Run a connection to an external standalone node, and a multi-node sidechain, and
    start up the REPL to interact with them.

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

    _external_node_with_callback(params, callback, setup_user_accounts=False)


def main() -> None:
    """Initialize the mainchain-sidechain network, with command-line arguments."""
    try:
        params = SidechainParams()
    except Exception as e:
        eprint(str(e))
        sys.exit(1)

    set_hooks_dir(params.hooks_dir)

    if params.quiet:
        print("Disabling eprint")
        disable_eprint()

    if params.interactive:
        if not params.main_standalone:
            external_node_interactive_repl(params)
        elif params.standalone:
            standalone_interactive_repl(params)
        else:
            multinode_interactive_repl(params)
    elif not params.main_standalone:
        external_node_test(params)
    elif params.standalone:
        standalone_test(params)
    else:
        multinode_test(params)


if __name__ == "__main__":
    main()
