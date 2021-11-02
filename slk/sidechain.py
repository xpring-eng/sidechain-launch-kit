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

import argparse
import os
import sys
import time
from multiprocessing import Process, Value
from typing import Callable, List, Optional

from dotenv import load_dotenv
from xrpl.models import (
    AccountSet,
    Amount,
    IssuedCurrencyAmount,
    Memo,
    Payment,
    SignerEntry,
    SignerListSet,
    TicketCreate,
    TrustSet,
)
from xrpl.utils import xrp_to_drops

import slk.interactive as interactive
from slk.chain import Chain, configs_for_testnet, single_node_chain
from slk.common import Account, disable_eprint, eprint
from slk.config_file import ConfigFile
from slk.log_analyzer import convert_log
from slk.testnet import sidechain_network

load_dotenv()


def parse_args_helper(parser: argparse.ArgumentParser) -> None:

    parser.add_argument(
        "--debug_sidechain",
        "-ds",
        action="store_true",
        help=("Mode to debug sidechain (prompt to run sidechain in gdb)"),
    )

    parser.add_argument(
        "--debug_mainchain",
        "-dm",
        action="store_true",
        help=("Mode to debug mainchain (prompt to run sidechain in gdb)"),
    )

    parser.add_argument(
        "--exe_mainchain",
        "-em",
        help=("path to mainchain rippled executable"),
    )

    parser.add_argument(
        "--exe_sidechain",
        "-es",
        help=("path to mainchain rippled executable"),
    )

    parser.add_argument(
        "--cfgs_dir",
        "-c",
        help=("path to configuration file dir (generated with create_config_files.py)"),
    )

    parser.add_argument(
        "--standalone",
        "-a",
        action="store_true",
        help=("run standalone tests"),
    )

    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help=("run interactive repl"),
    )

    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help=("Disable printing errors (eprint disabled)"),
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help=("Enable printing errors (eprint enabled)"),
    )

    # Pauses are use for attaching debuggers and looking at logs are know checkpoints
    parser.add_argument(
        "--with_pauses",
        "-p",
        action="store_true",
        help=('Add pauses at certain checkpoints in tests until "enter" key is hit'),
    )

    parser.add_argument(
        "--hooks_dir",
        help=("path to hooks dir"),
    )


def parse_args():
    parser = argparse.ArgumentParser(description=("Test and debug sidechains"))
    parse_args_helper(parser)
    return parser.parse_known_args()[0]


class SidechainParams:
    def __init__(self, *, configs_dir: Optional[str] = None):
        args = parse_args()

        self.debug_sidechain = False
        if args.debug_sidechain:
            self.debug_sidechain = args.debug_sidechain
        self.debug_mainchain = False
        if args.debug_mainchain:
            self.debug_mainchain = args.debug_mainchain

        self.standalone = args.standalone
        self.with_pauses = args.with_pauses
        self.interactive = args.interactive
        self.quiet = args.quiet
        self.verbose = args.verbose

        self.mainchain_exe = None
        if "RIPPLED_MAINCHAIN_EXE" in os.environ:
            self.mainchain_exe = os.environ["RIPPLED_MAINCHAIN_EXE"]
        if args.exe_mainchain:
            self.mainchain_exe = args.exe_mainchain

        self.sidechain_exe = None
        if "RIPPLED_SIDECHAIN_EXE" in os.environ:
            self.sidechain_exe = os.environ["RIPPLED_SIDECHAIN_EXE"]
        if args.exe_sidechain:
            self.sidechain_exe = args.exe_sidechain

        self.configs_dir = None
        if "RIPPLED_SIDECHAIN_CFG_DIR" in os.environ:
            self.configs_dir = os.environ["RIPPLED_SIDECHAIN_CFG_DIR"]
        if args.cfgs_dir:
            self.configs_dir = args.cfgs_dir
        if configs_dir is not None:
            self.configs_dir = configs_dir

        self.hooks_dir = None
        if "RIPPLED_SIDECHAIN_HOOKS_DIR" in os.environ:
            self.hooks_dir = os.environ["RIPPLED_SIDECHAIN_HOOKS_DIR"]
        if args.hooks_dir:
            self.hooks_dir = args.hooks_dir

        if not self.configs_dir:
            self.mainchain_config = None
            self.sidechain_config = None
            self.sidechain_bootstrap_config = None
            self.genesis_account = None
            self.mc_door_account = None
            self.user_account = None
            self.sc_door_account = None
            self.federators = None
            return

        if self.standalone:
            self.mainchain_config = ConfigFile(
                file_name=f"{self.configs_dir}/main.no_shards.dog/rippled.cfg"
            )
            self.sidechain_config = ConfigFile(
                file_name=f"{self.configs_dir}/main.no_shards.dog.sidechain/rippled.cfg"
            )
            self.sidechain_bootstrap_config = ConfigFile(
                file_name=f"{self.configs_dir}/main.no_shards.dog.sidechain/"
                "sidechain_bootstrap.cfg"
            )
        else:
            self.mainchain_config = ConfigFile(
                file_name=f"{self.configs_dir}/sidechain_testnet/main.no_shards."
                "mainchain_0/rippled.cfg"
            )
            self.sidechain_config = ConfigFile(
                file_name=f"{self.configs_dir}/sidechain_testnet/sidechain_0/"
                "rippled.cfg"
            )
            self.sidechain_bootstrap_config = ConfigFile(
                file_name=f"{self.configs_dir}/sidechain_testnet/sidechain_0/"
                "sidechain_bootstrap.cfg"
            )

        self.genesis_account = Account(
            account_id="rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh",
            secret_key="snoPBrXtMeMyMHUVTgbuqAfg1SUTb",
            nickname="genesis",
        )
        self.mc_door_account = Account(
            account_id=self.sidechain_config.sidechain.mainchain_account,
            secret_key=self.sidechain_bootstrap_config.sidechain.mainchain_secret,
            nickname="door",
        )
        self.user_account = Account(
            account_id="rJynXY96Vuq6B58pST9K5Ak5KgJ2JcRsQy",
            secret_key="snVsJfrr2MbVpniNiUU6EDMGBbtzN",
            nickname="alice",
        )

        self.sc_door_account = Account(
            account_id="rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh",
            secret_key="snoPBrXtMeMyMHUVTgbuqAfg1SUTb",
            nickname="door",
        )
        self.federators = [
            line.split()[1].strip()
            for line in self.sidechain_bootstrap_config.sidechain_federators.get_lines()
        ]

    def check_error(self) -> str:
        """
        Check for errors. Return `None` if no errors,
        otherwise return a string describing the error
        """
        if not self.mainchain_exe:
            return "Missing mainchain_exe location. Either set the env variable "
            "RIPPLED_MAINCHAIN_EXE or use the --exe_mainchain command line switch"
        if not self.sidechain_exe:
            return "Missing sidechain_exe location. Either set the env variable "
            "RIPPLED_SIDECHAIN_EXE or use the --exe_sidechain command line switch"
        if not self.configs_dir:
            return "Missing configs directory location. Either set the env variable "
            "RIPPLED_SIDECHAIN_CFG_DIR or use the --cfgs_dir command line switch"
        if self.verbose and self.quiet:
            return "Cannot specify both verbose and quiet options at the same time"


mainDoorKeeper = 0
sideDoorKeeper = 1
updateSignerList = 2


def setup_mainchain(
    mc_chain: Chain, params: SidechainParams, setup_user_accounts: bool = True
):
    mc_chain.add_to_keymanager(params.mc_door_account)
    if setup_user_accounts:
        mc_chain.add_to_keymanager(params.user_account)

    # mc_chain(LogLevel('fatal'))
    mc_chain("open")

    # Allow rippling through the genesis account
    mc_chain(AccountSet(account=params.genesis_account.account_id, set_flag=8))
    mc_chain.maybe_ledger_accept()

    # Create and fund the mc door account
    mc_chain(
        Payment(
            account=params.genesis_account.account_id,
            destination=params.mc_door_account.account_id,
            amount=xrp_to_drops(1_000),
        )
    )
    mc_chain.maybe_ledger_accept()

    # Create a trust line so USD/root account ious can be sent cross chain
    mc_chain(
        TrustSet(
            account=params.mc_door_account.account_id,
            limit_amount=IssuedCurrencyAmount(
                value=str(1_000_000),
                currency="USD",
                issuer=params.genesis_account.account_id,
            ),
        )
    )

    # set the chain's signer list and disable the master key
    divide = 4 * len(params.federators)
    by = 5
    quorum = (divide + by - 1) // by
    mc_chain(
        SignerListSet(
            account=params.mc_door_account.account_id,
            signer_quorum=quorum,
            signer_entries=[
                SignerEntry(account=federator, signer_weight=1)
                for federator in params.federators
            ],
        )
    )
    mc_chain.maybe_ledger_accept()
    mc_chain(
        TicketCreate(
            account=params.mc_door_account.account_id,
            source_tag=mainDoorKeeper,
            ticket_count=1,
        )
    )
    mc_chain.maybe_ledger_accept()
    mc_chain(
        TicketCreate(
            account=params.mc_door_account.account_id,
            source_tag=sideDoorKeeper,
            ticket_count=1,
        )
    )
    mc_chain.maybe_ledger_accept()
    mc_chain(
        TicketCreate(
            account=params.mc_door_account.account_id,
            source_tag=updateSignerList,
            ticket_count=1,
        )
    )
    mc_chain.maybe_ledger_accept()
    mc_chain(AccountSet(account=params.mc_door_account.account_id, set_flag=4))
    mc_chain.maybe_ledger_accept()

    if setup_user_accounts:
        # Create and fund a regular user account
        mc_chain(
            Payment(
                account=params.genesis_account.account_id,
                destination=params.user_account,
                amount=str(2_000),
            )
        )
        mc_chain.maybe_ledger_accept()


def setup_sidechain(
    sc_chain: Chain, params: SidechainParams, setup_user_accounts: bool = True
):
    sc_chain.add_to_keymanager(params.sc_door_account)
    if setup_user_accounts:
        sc_chain.add_to_keymanager(params.user_account)

    sc_chain("open")

    # sc_chain(LogLevel('fatal'))
    # sc_chain(LogLevel('trace', partition='SidechainFederator'))

    # set the chain's signer list and disable the master key
    divide = 4 * len(params.federators)
    by = 5
    quorum = (divide + by - 1) // by
    sc_chain(
        SignerListSet(
            account=params.genesis_account.account_id,
            signer_quorum=quorum,
            signer_entries=[
                SignerEntry(account=federator, signer_weight=1)
                for federator in params.federators
            ],
        )
    )
    sc_chain.maybe_ledger_accept()
    sc_chain(
        TicketCreate(
            account=params.genesis_account.account_id,
            source_tag=mainDoorKeeper,
            ticket_count=1,
        )
    )
    sc_chain.maybe_ledger_accept()
    sc_chain(
        TicketCreate(
            account=params.genesis_account.account_id,
            source_tag=sideDoorKeeper,
            ticket_count=1,
        )
    )
    sc_chain.maybe_ledger_accept()
    sc_chain(
        TicketCreate(
            account=params.genesis_account.account_id,
            source_tag=updateSignerList,
            ticket_count=1,
        )
    )
    sc_chain.maybe_ledger_accept()
    sc_chain(AccountSet(account=params.genesis_account.account_id, set_flag=4))
    sc_chain.maybe_ledger_accept()


def _xchain_transfer(
    from_chain: Chain,
    to_chain: Chain,
    src: Account,
    dst: Account,
    amt: Amount,
    from_chain_door: Account,
    to_chain_door: Account,
):
    memo = Memo(memo_data=dst.account_id_str_as_hex())
    from_chain(
        Payment(
            account=src.account_id,
            destination=from_chain_door.account_id,
            amount=amt,
            memos=[memo],
        )
    )
    from_chain.maybe_ledger_accept()
    if to_chain.standalone:
        # from_chain (side chain) sends a txn, but won't close the to_chain (main chain)
        # ledger
        time.sleep(1)
        to_chain.maybe_ledger_accept()


def main_to_side_transfer(
    mc_chain: Chain,
    sc_chain: Chain,
    src: Account,
    dst: Account,
    amt: Amount,
    params: SidechainParams,
):
    _xchain_transfer(
        mc_chain,
        sc_chain,
        src,
        dst,
        amt,
        params.mc_door_account,
        params.sc_door_account,
    )


def side_to_main_transfer(
    mc_chain: Chain,
    sc_chain: Chain,
    src: Account,
    dst: Account,
    amt: Amount,
    params: SidechainParams,
):
    _xchain_transfer(
        sc_chain,
        mc_chain,
        src,
        dst,
        amt,
        params.sc_door_account,
        params.mc_door_account,
    )


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
                mc_chain.get_configs() + sc_chain.get_configs(), "checkpoint1.json"
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
            mc_chain.get_configs() + sc_chain.get_configs(), "final.json"
        )


def _rm_debug_log(config: ConfigFile):
    try:
        debug_log = config.debug_logfile.get_line()
        if debug_log:
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
        _rm_debug_log(params.mainchain_config)
    with single_node_chain(
        config=params.mainchain_config,
        exe=params.mainchain_exe,
        run_server=not params.debug_mainchain,
    ) as mc_chain:

        setup_mainchain(mc_chain, params, setup_user_accounts)

        if params.debug_sidechain:
            input("Start sidechain server and press enter to continue: ")
        else:
            _rm_debug_log(params.sidechain_config)
        with single_node_chain(
            config=params.sidechain_config,
            exe=params.sidechain_exe,
            run_server=not params.debug_sidechain,
        ) as sc_chain:

            setup_sidechain(sc_chain, params, setup_user_accounts)
            callback(mc_chain, sc_chain)


def _convert_log_files_to_json(to_convert: List[ConfigFile], suffix: str):
    """Convert the log file to json"""
    for c in to_convert:
        try:
            debug_log = c.debug_logfile.get_line()
            if not os.path.exists(debug_log):
                continue
            converted_log = f"{debug_log}.{suffix}"
            if os.path.exists(converted_log):
                os.remove(converted_log)
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
    _rm_debug_log(mainchain_cfg)
    if params.debug_mainchain:
        input("Start mainchain server and press enter to continue: ")
    with single_node_chain(
        config=mainchain_cfg,
        exe=params.mainchain_exe,
        run_server=not params.debug_mainchain,
    ) as mc_chain:
        mc_chain("open")
        if params.with_pauses:
            input("Pausing after mainchain start (press enter to continue)")

        setup_mainchain(mc_chain, params, setup_user_accounts)
        if params.with_pauses:
            input("Pausing after mainchain setup (press enter to continue)")

        testnet_configs = configs_for_testnet(
            f"{params.configs_dir}/sidechain_testnet/sidechain_"
        )
        for c in testnet_configs:
            _rm_debug_log(c)

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
        mc_chain("open")
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
    params = SidechainParams()
    interactive.set_hooks_dir(params.hooks_dir)

    if err_str := params.check_error():
        eprint(err_str)
        sys.exit(1)

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
