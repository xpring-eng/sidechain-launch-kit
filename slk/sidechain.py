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
from typing import Callable, List

import slk.interactive as interactive
from slk.chain import Chain, configs_for_testnet, single_node_chain
from slk.chain_setup import setup_mainchain, setup_sidechain
from slk.common import disable_eprint, eprint
from slk.config_file import ConfigFile
from slk.log_analyzer import convert_log
from slk.sidechain_params import SidechainParams
from slk.testnet import sidechain_network
from slk.xchain_transfer import main_to_side_transfer, side_to_main_transfer


def simple_test(mc_chain: Chain, sc_chain: Chain, params: SidechainParams):
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


def _rm_debug_log(config: ConfigFile, verbose: bool):
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
):

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
):
    """Convert the log file to json"""
    for c in to_convert:
        try:
            debug_log = c.debug_logfile.get_line()
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
):

    mainchain_cfg = ConfigFile(
        file_name=f"{params.configs_dir}/sidechain_testnet/main.no_shards.mainchain_0/"
        "rippled.cfg"
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

        testnet_configs = configs_for_testnet(
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


def standalone_test(params: SidechainParams):
    def callback(mc_chain: Chain, sc_chain: Chain):
        simple_test(mc_chain, sc_chain, params)

    _standalone_with_callback(params, callback)


def multinode_test(params: SidechainParams):
    def callback(mc_chain: Chain, sc_chain: Chain):
        simple_test(mc_chain, sc_chain, params)

    _multinode_with_callback(params, callback)


# The mainchain runs in standalone mode. Most operations - like cross chain
# payments - will automatically close ledgers. However, some operations, like
# refunds, need an extra close. This loop automatically closes ledgers.
def close_mainchain_ledgers(stop_token: Value, params: SidechainParams, sleep_time=4):
    with single_node_chain(
        config=params.mainchain_config,
        exe=params.mainchain_exe,
        run_server=False,
    ) as mc_chain:
        while stop_token.value != 0:
            mc_chain.maybe_ledger_accept()
            time.sleep(sleep_time)


def standalone_interactive_repl(params: SidechainParams):
    def callback(mc_chain: Chain, sc_chain: Chain):
        # process will run while stop token is non-zero
        stop_token = Value("i", 1)
        p = None
        if mc_chain.standalone:
            p = Process(target=close_mainchain_ledgers, args=(stop_token, params))
            p.start()
        try:
            interactive.repl(mc_chain, sc_chain)
        finally:
            if p:
                stop_token.value = 0
                p.join()

    _standalone_with_callback(params, callback, setup_user_accounts=False)


def multinode_interactive_repl(params: SidechainParams):
    def callback(mc_chain: Chain, sc_chain: Chain):
        # process will run while stop token is non-zero
        stop_token = Value("i", 1)
        p = None
        if mc_chain.standalone:
            p = Process(target=close_mainchain_ledgers, args=(stop_token, params))
            p.start()
        try:
            interactive.repl(mc_chain, sc_chain)
        finally:
            if p:
                stop_token.value = 0
                p.join()

    _multinode_with_callback(params, callback, setup_user_accounts=False)


def main():
    try:
        params = SidechainParams()
    except Exception as e:
        eprint(str(e))
        sys.exit(1)

    interactive.set_hooks_dir(params.hooks_dir)

    if params.quiet:
        print("Disabling eprint")
        disable_eprint()

    if params.interactive:
        if params.standalone:
            standalone_interactive_repl(params)
        else:
            multinode_interactive_repl(params)
    elif params.standalone:
        standalone_test(params)
    else:
        multinode_test(params)


if __name__ == "__main__":
    main()
