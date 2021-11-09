from __future__ import annotations

import binascii
import cmd
import json
import os
import pprint
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from tabulate import tabulate

# from slk.transaction import SetHook, Payment, Trust
from xrpl.models import (
    AccountTx,
    IssuedCurrency,
    IssuedCurrencyAmount,
    Memo,
    Payment,
    Subscribe,
    TrustSet,
    is_xrp,
)
from xrpl.utils import drops_to_xrp

from slk.chain import Chain, balances_data
from slk.common import Account, same_amount_new_value


def clear_screen() -> None:
    if os.name == "nt":
        _ = os.system("cls")
    else:
        _ = os.system("clear")


# Directory to find hooks. The hook should be in a directory call "hook_name"
# in a file called "hook_name.wasm"
HOOKS_DIR = Path()


def set_hooks_dir(hooks_dir_to_set: Optional[str]) -> None:
    global HOOKS_DIR
    if hooks_dir_to_set:
        HOOKS_DIR = Path(hooks_dir_to_set)


_valid_hook_names = ["doubler", "notascam"]


def _file_to_hex(filename: Path) -> str:
    with open(filename, "rb") as f:
        content = f.read()
    return binascii.hexlify(content).decode("utf8")


def _removesuffix(phrase: str, suffix: str) -> str:
    if suffix and phrase.endswith(suffix):
        return phrase[: -len(suffix)]
    else:
        return phrase[:]


class SidechainRepl(cmd.Cmd):
    """Simple repl for interacting with side chains"""

    intro = (
        "\n\nWelcome to the sidechain test shell.   Type help or ? to list commands.\n"
    )
    prompt = "RiplRepl> "

    def preloop(self: SidechainRepl) -> None:
        clear_screen()

    def __init__(self: SidechainRepl, mc_chain: Chain, sc_chain: Chain):
        super().__init__()
        assert mc_chain.is_alias("door") and sc_chain.is_alias("door")
        self.mc_chain = mc_chain
        self.sc_chain = sc_chain

    def _complete_chain(self: SidechainRepl, text: str, line: str) -> List[str]:
        if not text:
            return ["mainchain", "sidechain"]
        else:
            return [c for c in ["mainchain", "sidechain"] if c.startswith(text)]

    def _complete_unit(self: SidechainRepl, text: str, line: str) -> List[str]:
        if not text:
            return ["drops", "xrp"]
        else:
            return [c for c in ["drops", "xrp"] if c.startswith(text)]

    def _complete_account(
        self: SidechainRepl, text: str, line: str, chain_name: Optional[str] = None
    ) -> List[str]:
        known_accounts: Set[str] = set()
        chains = [self.mc_chain, self.sc_chain]
        if chain_name == "mainchain":
            chains = [self.mc_chain]
        elif chain_name == "sidechain":
            chains = [self.sc_chain]
        for chain in chains:
            known_accounts = known_accounts | set(
                [a.nickname for a in chain.known_accounts()]
            )
        if not text:
            return list(known_accounts)
        else:
            return [c for c in known_accounts if c.startswith(text)]

    def _complete_asset(
        self: SidechainRepl, text: str, line: str, chain_name: Optional[str] = None
    ) -> List[str]:
        known_assets: Set[str] = set()
        chains = [self.mc_chain, self.sc_chain]
        if chain_name == "mainchain":
            chains = [self.mc_chain]
        elif chain_name == "sidechain":
            chains = [self.sc_chain]
        for chain in chains:
            known_assets = known_assets | set(chain.known_asset_aliases())
        if not text:
            return list(known_assets)
        else:
            return [c for c in known_assets if c.startswith(text)]

    ##################
    # addressbook
    def do_addressbook(self: SidechainRepl, line: str) -> None:
        args = line.split()
        if len(args) > 2:
            print(
                'Error: Too many arguments to addressbook command. Type "help" for '
                "help."
            )
            return

        chains = [self.mc_chain, self.sc_chain]
        chain_names = ["mainchain", "sidechain"]
        nickname = None

        if args and args[0] in ["mainchain", "sidechain"]:
            chain_names = [args[0]]
            if args[0] == "mainchain":
                chains = [self.mc_chain]
            else:
                chains = [self.sc_chain]
            args.pop(0)

        if args:
            nickname = args[0]

        for chain, chain_name in zip(chains, chain_names):
            if nickname and not chain.is_alias(nickname):
                print(f"{nickname} is not part of {chain_name}'s address book.")
            print(f"{chain_name}:\n{chain.key_manager.to_string(nickname)}")
            print("\n")

    def complete_addressbook(
        self: SidechainRepl, text: str, line: str, begidx: int, endidx: int
    ) -> List[str]:
        args = line.split()
        arg_num = len(args)
        if arg_num == 2:  # chain
            return self._complete_chain(text, line) + self._complete_account(text, line)
        if arg_num == 3:  # account
            return self._complete_account(text, line, chain_name=args[1])
        return []

    def help_addressbook(self: SidechainRepl) -> None:
        print(
            "\n".join(
                [
                    "addressbook [mainchain | sidechain] [account]",
                    "Show the address book for the specified chain and account.",
                    "If a chain is not specified, show both address books.",
                    "If the account is not specified, show all addresses.",
                    "",
                ]
            )
        )

    # addressbook
    ##################

    ##################
    # balance
    def do_balance(self: SidechainRepl, line: str) -> None:
        args = line.split()
        arg_index = 0

        """
        Args:
            args[0] (optional): mainchain/sidechain
            args[1] (optional): account name
            args[2] (optional): currency
        """

        if len(args) > 3:
            print('Error: Too many arguments to balance command. Type "help" for help.')
            return

        # which chain
        chains = [self.mc_chain, self.sc_chain]
        chain_names = ["mainchain", "sidechain"]
        if args and args[arg_index] in ["mainchain", "sidechain"]:
            chain_names = [args[0]]
            arg_index += 1
            if chain_names[0] == "mainchain":
                chains = [self.mc_chain]
            else:
                chains = [self.sc_chain]

        # account
        account_ids: List[Optional[Account]] = [None] * len(chains)
        if len(args) > arg_index:
            nickname = args[arg_index]
            # TODO: fix bug where "balance sidechain root" prints out "side door"
            arg_index += 1
            account_ids = []
            for c in chains:
                if not c.is_alias(nickname):
                    print(f"Error: {nickname} is not in the address book")
                    return
                account_ids.append(c.account_from_alias(nickname))

        # currency
        assets = [["0"]] * len(chains)
        in_drops = False
        if len(args) > arg_index:
            asset_alias = args[arg_index]
            arg_index += 1
            if asset_alias in ["xrp", "drops"]:
                if asset_alias == "xrp":
                    in_drops = False
                elif asset_alias == "drops":
                    in_drops = True
            elif len(chains) != 1:
                print(
                    "Error: iou assets can only be shown for a single chain at a time"
                )
                return
            elif not chains[0].is_asset_alias(asset_alias):
                print(f"Error: {asset_alias} is not a valid asset alias")
                return
            assets = [[chains[0].asset_from_alias(asset_alias)]]
        else:
            # XRP and all assets in the assets alias list
            assets = [["0"] + c.known_iou_assets() for c in chains]

        # should be done analyzing all the params
        assert arg_index == len(args)

        result = balances_data(chains, chain_names, account_ids, assets, in_drops)
        print(
            tabulate(
                result,
                headers="keys",
                tablefmt="presto",
                floatfmt=",.6f",
                numalign="right",
            )
        )

    def complete_balance(
        self: SidechainRepl, text: str, line: str, begidx: int, endidx: int
    ) -> List[str]:
        args = line.split()
        arg_num = len(args)
        if arg_num == 2:  # chain or account
            return self._complete_chain(text, line) + self._complete_account(text, line)
        elif arg_num == 3:  # account or unit or asset_alias
            return (
                self._complete_account(text, line)
                + self._complete_unit(text, line)
                + self._complete_asset(text, line, chain_name=args[1])
            )
        elif arg_num == 4:  # unit
            return self._complete_unit(text, line) + self._complete_asset(
                text, line, chain_name=args[1]
            )
        return []

    def help_balance(self: SidechainRepl) -> None:
        print(
            "\n".join(
                [
                    "balance [sidechain | mainchain] [account_name] [xrp | drops | "
                    "asset_alias]",
                    "Show the balance the specified account."
                    "If no account is specified, show the balance for all accounts in "
                    "the addressbook.",
                    "If no chain is specified, show the balances for both chains.",
                    ""
                    "If no asset alias is specified, show balances for all known asset "
                    "aliases.",
                ]
            )
        )

    # balance
    ##################

    ##################
    # account_info

    def do_account_info(self: SidechainRepl, line: str) -> None:
        args = line.split()
        if len(args) > 2:
            print(
                'Error: Too many arguments to account_info command. Type "help" for '
                "help."
            )
            return
        chains = [self.mc_chain, self.sc_chain]
        chain_names = ["mainchain", "sidechain"]
        if args and args[0] in ["mainchain", "sidechain"]:
            chain_names = [args[0]]
            args.pop(0)
            if chain_names[0] == "mainchain":
                chains = [self.mc_chain]
            else:
                chains = [self.sc_chain]

        account_ids: List[Optional[Account]] = [None] * len(chains)
        if args:
            nickname = args[0]
            args.pop()
            account_ids = []
            for c in chains:
                if not c.is_alias(nickname):
                    print(f"Error: {nickname} is not in the address book")
                    return
                account_ids.append(c.account_from_alias(nickname))

        assert not args

        results: List[Dict[str, Any]] = []
        for chain, chain_name, acc in zip(chains, chain_names, account_ids):
            result = chain.get_account_info(acc)
            # TODO: figure out how to get this to work for both lists and individual
            # accounts
            # TODO: refactor substitute_nicknames to handle the chain name too
            chain_short_name = "main" if chain_name == "mainchain" else "side"
            for res in result:
                chain.substitute_nicknames(result)
                res["account"] = chain_short_name + " " + res["account"]
            results += result
        print(
            tabulate(
                results,
                headers="keys",
                tablefmt="presto",
                floatfmt=",.6f",
                numalign="right",
            )
        )

    def complete_account_info(
        self: SidechainRepl, text: str, line: str, begidx: int, endidx: int
    ) -> List[str]:
        args = line.split()
        arg_num = len(args)
        if arg_num == 2:  # chain or account
            return self._complete_chain(text, line) + self._complete_account(text, line)
        elif arg_num == 3:  # account
            return self._complete_account(text, line)
        return []

    def help_account_info(self: SidechainRepl) -> None:
        print(
            "\n".join(
                [
                    "account_info [sidechain | mainchain] [account_name]",
                    "Show the account_info the specified account."
                    "If no account is specified, show the account_info for all "
                    "accounts in the addressbook.",
                    "If no chain is specified, show the account_info for both chains.",
                ]
            )
        )

    # account_info
    ##################

    ##################
    # pay
    def do_pay(self: SidechainRepl, line: str) -> None:
        args = line.split()
        if len(args) < 4:
            print('Error: Too few arguments to pay command. Type "help" for help.')
            return

        if len(args) > 5:
            print('Error: Too many arguments to pay command. Type "help" for help.')
            return

        """
        Args:
            # args[-1]: 'pay'
            args[0]: chain name
            args[1]: sender
            args[2]: destination
            args[3]: amount
            args[4]: units (XRP if not specified)
        """

        in_drops = False
        if args and args[-1] in ["xrp", "drops"]:
            unit = args[-1]
            if unit == "xrp":
                in_drops = False
            elif unit == "drops":
                in_drops = True

        chain = None
        if args[0] not in ["mainchain", "sidechain"]:
            print('Error: First argument must specify the chain. Type "help" for help.')
            return

        if args[0] == "mainchain":
            chain = self.mc_chain
        else:
            chain = self.sc_chain

        src_nickname = args[1]
        if src_nickname == "door":
            print(
                'Error: The "door" account should never be used as a source of '
                "payments."
            )
            return
        if not chain.is_alias(src_nickname):
            print(f"Error: {src_nickname} is not in the address book")
            return
        src_account = chain.account_from_alias(src_nickname)

        dst_nickname = args[2]
        if dst_nickname == "door":
            print(
                'Error: "pay" cannot be used for cross chain transactions. Use the '
                '"xchain" command instead.'
            )
            return
        if not chain.is_alias(dst_nickname):
            print(f"Error: {dst_nickname} is not in the address book")
            return
        dst_account = chain.account_from_alias(dst_nickname)

        amt_value: Optional[Union[int, float]] = None
        try:
            amt_value = int(args[3])
        except:
            try:
                if not in_drops:
                    # could be a decimal (drops must be whole numbers)
                    amt_value = float(args[3])
            except:
                pass

        if amt_value is None:
            print(f"Error: {args[3]} is an invalid amount.")
            return

        asset = None

        if len(args) > 4:
            asset_alias = args[4]
            if not chain.is_asset_alias(asset_alias):
                print(f"Error: {args[4]} is an invalid asset alias.")
                return
            asset = chain.asset_from_alias(asset_alias)

        if ((asset is not None and is_xrp(asset)) or asset is None) and not in_drops:
            amt_value *= 1_000_000

        if asset is not None:
            amt = IssuedCurrencyAmount(
                value=str(amt_value), issuer=asset.issuer, currency=asset.currency
            )
        else:
            amt = str(amt_value)

        # TODO: print error if something wrong with payment (e.g. no trustline)
        chain.send_signed(
            Payment(
                account=src_account.account_id,
                destination=dst_account.account_id,
                amount=amt,
            )
        )
        chain.maybe_ledger_accept()

    def complete_pay(
        self: SidechainRepl, text: str, line: str, begidx: int, endidx: int
    ) -> List[str]:
        args = line.split()
        arg_num = len(args)
        if not text:
            arg_num += 1
        if arg_num == 2:  # chain
            return self._complete_chain(text, line)
        elif arg_num == 3:  # account
            return self._complete_account(text, line, chain_name=args[1])
        elif arg_num == 4:  # account
            return self._complete_account(text, line, chain_name=args[1])
        elif arg_num == 5:  # amount
            return []
        elif arg_num == 6:  # drops or xrp or asset
            return self._complete_unit(text, line) + self._complete_asset(
                text, line, chain_name=args[1]
            )
        return []

    def help_pay(self: SidechainRepl) -> None:
        print(
            "\n".join(
                [
                    "pay (sidechain | mainchain) src_account dst_account amount [xrp | "
                    "drops | iou_alias]",
                    "Send xrp from the src account to the dst account."
                    "Note: the door account can not be used as the src or dst.",
                    "Cross chain transactions should use the xchain command instead of "
                    "this.",
                    "",
                ]
            )
        )

    # pay
    ##################

    ##################
    # xchain
    def do_xchain(self: SidechainRepl, line: str) -> None:
        args = line.split()
        if len(args) < 4:
            print('Error: Too few arguments to pay command. Type "help" for help.')
            return

        if len(args) > 5:
            print('Error: Too many arguments to pay command. Type "help" for help.')
            return

        """
        Args:
            # args[-1]: 'pay'
            args[0]: chain name of the sender
            args[1]: sender on args[0] chain
            args[2]: destination on other chain
            args[3]: amount
            args[4]: units (XRP if not specified)
        """

        in_drops = False
        if args and args[-1] in ["xrp", "drops"]:
            unit = args[-1]
            if unit == "xrp":
                in_drops = False
            elif unit == "drops":
                in_drops = True
            args.pop()

        chain = None
        if args[0] not in ["mainchain", "sidechain"]:
            print('Error: First argument must specify the chain. Type "help" for help.')
            return

        if args[0] == "mainchain":
            chain = self.mc_chain
            other_chain = self.sc_chain
        else:
            chain = self.sc_chain
            other_chain = self.mc_chain
        args.pop(0)

        nickname = args[0]
        if nickname == "door":
            print(
                'Error: The "door" account can not be used as the source of cross '
                "chain funds."
            )
            return
        if not chain.is_alias(nickname):
            print(f"Error: {nickname} is not in the address book")
            return
        src_account = chain.account_from_alias(nickname)
        args.pop(0)

        nickname = args[0]
        if nickname == "door":
            print(
                'Error: The "door" account can not be used as the destination of cross '
                "chain funds."
            )
            return
        if not other_chain.is_alias(nickname):
            print(f"Error: {nickname} is not in the address book")
            return
        dst_account = other_chain.account_from_alias(nickname)
        args.pop(0)

        amt_value: Optional[Union[int, float]] = None
        try:
            amt_value = int(args[0])
        except:
            try:
                if not in_drops:
                    amt_value = float(args[0])
            except:
                pass

        if amt_value is None:
            print(f"Error: {args[0]} is an invalid amount.")
            return
        args.pop(0)

        asset = None

        if args:
            asset_alias = args[0]
            args.pop(0)
            if not chain.is_asset_alias(asset_alias):
                print(f"Error: {asset_alias} is an invalid asset alias.")
                return
            asset = chain.asset_from_alias(asset_alias)

        assert not args

        if ((asset is not None and is_xrp(asset)) or asset is None) and not in_drops:
            amt_value *= 1_000_000

        if asset is not None:
            amt = IssuedCurrencyAmount(
                value=amt_value, issuer=asset.issuer, currency=asset.currency
            )
        else:
            amt = str(amt_value)

        assert not args
        memos = [Memo(memo_data=dst_account.account_id_str_as_hex())]
        door_account = chain.account_from_alias("door")
        chain.send_signed(
            Payment(
                account=src_account.account_id,
                destination=door_account.account_id,
                amount=amt,
                memos=memos,
            )
        )
        chain.maybe_ledger_accept()
        if other_chain.standalone:
            # from_chain (side chain) sends a txn, but won't close the to_chain
            # (main chain) ledger
            time.sleep(2)
            other_chain.maybe_ledger_accept()

    def complete_xchain(
        self: SidechainRepl, text: str, line: str, begidx: int, endidx: int
    ) -> List[str]:
        args = line.split()
        arg_num = len(args)
        if not text:
            arg_num += 1
        if arg_num == 2:  # chain
            return self._complete_chain(text, line)
        elif arg_num == 3:  # this chain account
            return self._complete_account(text, line, chain_name=args[1])
        elif arg_num == 4:  # other chain account
            other_chain_name = None
            if args[1] == "mainchain":
                other_chain_name = "sidechain"
            if args[1] == "sidechain":
                other_chain_name = "mainchain"
            return self._complete_account(text, line, chain_name=other_chain_name)
        elif arg_num == 5:  # amount
            return []
        elif arg_num == 6:  # drops or xrp or asset
            return self._complete_unit(text, line) + self._complete_asset(
                text, line, chain_name=args[1]
            )
        return []

    def help_xchain(self: SidechainRepl) -> None:
        print(
            "\n".join(
                [
                    "xchain (sidechain | mainchain) this_chain_account "
                    "other_chain_account amount [xrp | drops | iou_alias]",
                    "Send xrp from the specified chain to the other chain."
                    "Note: the door account can not be used as the account.",
                    "",
                ]
            )
        )

    # xchain
    ##################

    ##################
    # server_info
    def do_server_info(self: SidechainRepl, line: str) -> None:
        def data_dict(chain: Chain, chain_name: str) -> Dict[str, Any]:
            # get the server_info data for a specific chain
            # TODO: refactor get_brief_server_info to make this method less clunky
            filenames = [c.get_file_name() for c in chain.get_configs()]
            chains = []
            for i in range(len(filenames)):
                chains.append(f"{chain_name} {i}")
            data: Dict[str, Any] = {"node": chains}
            data.update(
                {
                    "pid": chain.get_pids(),
                    "config": filenames,
                    "running": chain.get_running_status(),
                }
            )
            bsi = chain.get_brief_server_info()
            data.update(bsi)
            return data

        def result_from_dicts(
            d1: Dict[str, Any], d2: Optional[Dict[str, Any]] = None
        ) -> List[Dict[str, Any]]:
            # combine the info from the chains, refactor dict for tabulate
            data = []
            for i in range(len(d1["node"])):
                new_dict = {key: d1[key][i] for key in d1}
                data.append(new_dict)
            if d2 is not None:
                for i in range(len(d2["node"])):
                    new_dict = {key: d2[key][i] for key in d2}
                    data.append(new_dict)
            # shorten config filenames for space
            all_filenames = [d["config"] for d in data]
            cp = os.path.commonprefix(all_filenames)
            short_filenames = [os.path.relpath(f, cp) for f in all_filenames]
            for i in range(len(data)):
                data[i]["config"] = short_filenames[i]
            return data

        args = line.split()
        if len(args) > 1:
            print(
                'Error: Too many arguments to server_info command. Type "help" for '
                "help."
            )
            return

        chains = [self.mc_chain, self.sc_chain]
        chain_names = ["mainchain", "sidechain"]

        if args and args[0] in ["mainchain", "sidechain"]:
            chain_names = [args[0]]
            if args[0] == "mainchain":
                chains = [self.mc_chain]
            else:
                chains = [self.sc_chain]
            args.pop(0)

        data_dicts = [
            data_dict(chain, _removesuffix(name, "chain"))
            for chain, name in zip(chains, chain_names)
        ]
        result = result_from_dicts(*data_dicts)
        print(
            tabulate(
                result,
                headers="keys",
                tablefmt="presto",
            )
        )

    def complete_server_info(
        self: SidechainRepl, text: str, line: str, begidx: int, endidx: int
    ) -> List[str]:
        arg_num = len(line.split())
        if arg_num == 2:  # chain
            return self._complete_chain(text, line)
        return []

    def help_server_info(self: SidechainRepl) -> None:
        print(
            "\n".join(
                [
                    "server_info [mainchain | sidechain]",
                    "Show the process ids and config files for the rippled servers "
                    "running for the specified chain.",
                    "If a chain is not specified, show info for both chains.",
                ]
            )
        )

    # server_info
    ##################

    ##################
    # federator_info

    def do_federator_info(self: SidechainRepl, line: str) -> None:
        args = line.split()
        indexes = set()
        verbose = False
        raw = False
        # TODO: do this processing better
        while args and (args[-1] == "verbose" or args[-1] == "raw"):
            if args[-1] == "verbose":
                verbose = True
            if args[-1] == "raw":
                raw = True
            args.pop()

        try:
            for i in args:
                indexes.add(int(i))
        except:
            f'Error: federator_info bad arguments: {args}. Type "help" for help.'

        def get_fed_info_table(
            info_dict: Dict[int, Dict[str, Any]]
        ) -> List[Dict[str, Any]]:
            data = []
            for (k, v) in info_dict.items():
                new_dict = {}
                info = v["info"]
                new_dict["public_key"] = info["public_key"]
                mc = info["mainchain"]
                sc = info["sidechain"]
                new_dict["main last_sent_seq"] = mc["last_transaction_sent_seq"]
                new_dict["side last_sent_seq"] = sc["last_transaction_sent_seq"]
                new_dict["main seq"] = mc["sequence"]
                new_dict["side seq"] = sc["sequence"]
                new_dict["main num_pending"] = len(mc["pending_transactions"])
                new_dict["side num_pending"] = len(sc["pending_transactions"])
                new_dict["main sync_state"] = (
                    mc["listener_info"]["state"]
                    if "state" in mc["listener_info"]
                    else None
                )
                new_dict["side sync_state"] = (
                    sc["listener_info"]["state"]
                    if "state" in sc["listener_info"]
                    else None
                )
                data.append(new_dict)
            return data

        def get_pending_tx_info(
            info_dict: Dict[int, Dict[str, Any]], verbose: bool = False
        ) -> List[Dict[str, Any]]:
            data = []
            for (k, v) in info_dict.items():
                for chain in ["mainchain", "sidechain"]:
                    short_chain_name = chain[:4] + " " + str(k)
                    pending = v["info"][chain]["pending_transactions"]
                    for t in pending:
                        amt = t["amount"]
                        if is_xrp(amt):
                            amt = drops_to_xrp(amt)
                        if not verbose:
                            pending_info = {
                                "chain": short_chain_name,
                                "amount": amt,
                                "dest_acct": t["destination_account"],
                                "hash": t["hash"],
                                "num_sigs": len(t["signatures"]),
                            }
                            data.append(pending_info)
                        else:
                            for sig in t["signatures"]:
                                pending_info = {
                                    "chain": short_chain_name,
                                    "amount": amt,
                                    "dest_acct": t["destination_account"],
                                    "hash": t["hash"],
                                    "num_sigs": len(t["signatures"]),
                                    "sigs": sig["public_key"],
                                }
            return data

        info_dict = self.sc_chain.federator_info(indexes)
        if raw:
            pprint.pprint(info_dict)
            return

        print(
            tabulate(
                get_fed_info_table(info_dict),
                headers="keys",
                tablefmt="presto",
            )
        )
        # pending
        print("")  # newline separation
        pending_tx_data = get_pending_tx_info(info_dict, verbose)
        if len(pending_tx_data) > 0:
            tabulate(
                pending_tx_data,
                headers="keys",
                tablefmt="presto",
            )
        else:
            print("No pending transactions.")

    def complete_federator_info(
        self: SidechainRepl, text: str, line: str, begidx: int, endidx: int
    ) -> List[str]:
        args = line.split()
        if "verbose".startswith(args[-1]):
            return ["verbose"]
        if "raw".startswith(args[-1]):
            return ["raw"]
        running_status = self.sc_chain.get_running_status()
        return [
            str(i)
            for i in range(0, len(self.sc_chain.get_running_status()))
            if running_status[i]
        ]

    def help_federator_info(self: SidechainRepl) -> None:
        print(
            "\n".join(
                [
                    "federator_info [server_index...] [verbose | raw]",
                    "Show the state of the federators queues and startup "
                    "synchronization.",
                    "If a server index is not specified, show info for all running "
                    "federators.",
                ]
            )
        )

    # federator_info
    ##################

    ##################
    # new_account
    def do_new_account(self: SidechainRepl, line: str) -> None:
        args = line.split()
        if len(args) < 2:
            print(
                "Error: new_account command takes at least two arguments. Type "
                '"help" for help.'
            )
            return

        chain = None

        if args[0] not in ["mainchain", "sidechain"]:
            print('Error: The first argument must be "mainchain" or "sidechain".')
            return

        if args[0] == "mainchain":
            chain = self.mc_chain
        else:
            chain = self.sc_chain
        args.pop(0)

        for alias in args:
            if chain.is_alias(alias):
                print(f"Warning: The alias {alias} already exists.")
            else:
                chain.create_account(alias)

    def complete_new_account(
        self: SidechainRepl, text: str, line: str, begidx: int, endidx: int
    ) -> List[str]:
        arg_num = len(line.split())
        if arg_num == 2:  # chain
            return self._complete_chain(text, line)
        return []

    def help_new_account(self: SidechainRepl) -> None:
        print(
            "\n".join(
                [
                    "new_account (mainchain | sidechain) alias [alias...]",
                    "Add a new account to the address book",
                ]
            )
        )

    # new_account
    ##################

    ##################
    # new_iou
    def do_new_iou(self: SidechainRepl, line: str) -> None:
        args = line.split()
        if len(args) != 4:
            print(
                'Error: new_iou command takes exactly four arguments. Type "help" '
                "for help."
            )
            return

        chain = None

        if args[0] not in ["mainchain", "sidechain"]:
            print('Error: The first argument must be "mainchain" or "sidechain".')
            return

        if args[0] == "mainchain":
            chain = self.mc_chain
        else:
            chain = self.sc_chain
        args.pop(0)

        (alias, currency, issuer) = args

        if chain.is_asset_alias(alias):
            print(f"Error: The alias {alias} already exists.")
            return

        if not chain.is_alias(issuer):
            print(f"Error: The issuer {issuer} is not part of the address book.")
            return

        asset = IssuedCurrencyAmount(
            value=0,
            currency=currency,
            issuer=chain.account_from_alias(issuer).account_id,
        )
        chain.add_asset_alias(asset, alias)

    def complete_new_iou(
        self: SidechainRepl, text: str, line: str, begidx: int, endidx: int
    ) -> List[str]:
        arg_num = len(line.split())
        if arg_num == 2:  # chain
            return self._complete_chain(text, line)
        if arg_num == 5:  # issuer
            return self._complete_account(text, line)
        return []

    def help_new_iou(self: SidechainRepl) -> None:
        print(
            "\n".join(
                [
                    "new_iou (mainchain | sidechain) alias currency issuer",
                    "Add a new iou alias",
                ]
            )
        )

    # new_iou
    ##################

    ##################
    # ious
    def do_ious(self: SidechainRepl, line: str) -> None:
        def print_ious(chain: Chain, chain_name: str, nickname: Optional[str]) -> None:
            if nickname and not chain.is_asset_alias(nickname):
                print(f"{nickname} is not part of {chain_name}'s asset aliases.")
            print(f"{chain_name}:\n{chain.asset_aliases.to_string(nickname)}")

        args = line.split()
        if len(args) > 2:
            print('Error: Too many arguments to ious command. Type "help" for help.')
            return

        chains = [self.mc_chain, self.sc_chain]
        chain_names = ["mainchain", "sidechain"]
        nickname = None

        if args and args[0] in ["mainchain", "sidechain"]:
            chain_names = [args[0]]
            if args[0] == "mainchain":
                chains = [self.mc_chain]
            else:
                chains = [self.sc_chain]
            args.pop(0)

        if args:
            nickname = args[0]

        for chain, name in zip(chains, chain_names):
            print_ious(chain, name, nickname)
            print("\n")

    def complete_ious(
        self: SidechainRepl, text: str, line: str, begidx: int, endidx: int
    ) -> List[str]:
        args = line.split()
        arg_num = len(args)
        if arg_num == 2:  # chain or iou
            return self._complete_chain(text, line) + self._complete_asset(text, line)
        if arg_num == 3:  # iou
            return self._complete_asset(text, line, chain_name=args[1])
        return []

    def help_ious(self: SidechainRepl) -> None:
        print(
            "\n".join(
                [
                    "ious [mainchain | sidechain] [alias]",
                    "Show the iou aliases for the specified chain and alias.",
                    "If a chain is not specified, show aliases for both chains.",
                    "If the alias is not specified, show all aliases.",
                    "",
                ]
            )
        )

    # ious
    ##################

    ##################
    # set_trust
    def do_set_trust(self: SidechainRepl, line: str) -> None:
        # TODO: fix bug where REPL crashes if account isn't funded yet
        args = line.split()
        if len(args) != 4:
            print(
                'Error: set_trust command takes exactly four arguments. Type "help" '
                "for help."
            )
            return

        chain = None

        if args[0] not in ["mainchain", "sidechain"]:
            print('Error: The first argument must be "mainchain" or "sidechain".')
            return

        if args[0] == "mainchain":
            chain = self.mc_chain
        else:
            chain = self.sc_chain
        args.pop(0)

        (alias, accountStr, amountStr) = args

        if not chain.is_asset_alias(alias):
            print(f"Error: The alias {alias} does not exists.")
            return

        if not chain.is_alias(accountStr):
            print(f"Error: The issuer {accountStr} is not part of the address book.")
            return

        account = chain.account_from_alias(accountStr)

        amount: Optional[Union[int, float]] = None
        try:
            amount = int(amountStr)
        except:
            try:
                amount = float(amountStr)
            except:
                pass

        if amount is None:
            print(f"Error: Invalid amount {amountStr}")
            return

        asset = same_amount_new_value(chain.asset_from_alias(alias), amount)
        # TODO: resolve error where repl crashes if account doesn't exist
        chain.send_signed(TrustSet(account=account.account_id, limit_amount=asset))
        chain.maybe_ledger_accept()

    def complete_set_trust(
        self: SidechainRepl, text: str, line: str, begidx: int, endidx: int
    ) -> List[str]:
        args = line.split()
        arg_num = len(args)
        if arg_num == 2:  # chain
            return self._complete_chain(text, line)
        if arg_num == 3:  # iou
            return self._complete_asset(text, line, chain_name=args[1])
        if arg_num == 4:  # account
            return self._complete_account(text, line, chain_name=args[1])
        return []

    def help_set_trust(self: SidechainRepl) -> None:
        print(
            "\n".join(
                [
                    "set_trust (mainchain | sidechain) iou_alias account amount",
                    "Set trust amount for account's side of the iou trust line to "
                    "amount",
                ]
            )
        )

    # set_trust
    ##################

    ##################
    # ledger_accept
    def do_ledger_accept(self: SidechainRepl, line: str) -> None:
        args = line.split()
        if len(args) != 1:
            print(
                'Error: ledger_accept command takes exactly one argument. Type "help" '
                "for help."
            )
            return

        chain = None

        if args[0] not in ["mainchain", "sidechain"]:
            print('Error: The first argument must be "mainchain" or "sidechain".')
            return

        if args[0] == "mainchain":
            chain = self.mc_chain
        else:
            chain = self.sc_chain
        args.pop(0)

        assert not args

        chain.maybe_ledger_accept()

    def complete_ledger_accept(
        self: SidechainRepl, text: str, line: str, begidx: int, endidx: int
    ) -> List[str]:
        arg_num = len(line.split())
        if arg_num == 2:  # chain
            return self._complete_chain(text, line)
        return []

    def help_ledger_accept(self: SidechainRepl) -> None:
        print(
            "\n".join(
                [
                    "ledger_accept (mainchain | sidechain)",
                    "Force a ledger_accept if the chain is in stand alone mode.",
                ]
            )
        )

    # ledger_accept
    ##################

    ##################
    # server_start

    def do_server_start(self: SidechainRepl, line: str) -> None:
        args = line.split()
        if len(args) == 0:
            print(
                'Error: server_start command takes one or more arguments. Type "help" '
                "for help."
            )
            return
        indexes: Set[int] = set()
        if len(args) == 1 and args[0] == "all":
            # re-start all stopped servers
            running_status = self.sc_chain.get_running_status()
            for (i, running) in enumerate(running_status):
                if not running:
                    indexes.add(i)
        else:
            try:
                for arg in args:
                    indexes.add(int(arg))
            except:
                f'Error: server_start bad arguments: {args}. Type "help" for help.'
        self.sc_chain.servers_start(indexes)

    def complete_server_start(
        self: SidechainRepl, text: str, line: str, begidx: int, endidx: int
    ) -> List[str]:
        running_status = self.sc_chain.get_running_status()
        if "all".startswith(text):
            return ["all"]
        return [
            str(i)
            for (i, running) in enumerate(running_status)
            if not running and str(i).startswith(text)
        ]

    def help_server_start(self: SidechainRepl) -> None:
        print(
            "\n".join(
                [
                    "server_start index [index...] | all",
                    "Start a running server",
                ]
            )
        )

    # server_start
    ##################

    ##################
    # server_stop

    def do_server_stop(self: SidechainRepl, line: str) -> None:
        args = line.split()
        if len(args) == 0:
            print(
                'Error: server_stop command takes one or more arguments. Type "help" '
                "for help."
            )
            return
        indexes: Set[int] = set()
        if len(args) == 1 and args[0] == "all":
            # stop all running servers
            running_status = self.sc_chain.get_running_status()
            for (i, running) in enumerate(running_status):
                if running:
                    indexes.add(i)
        else:
            try:
                for arg in args:
                    indexes.add(int(arg))
            except:
                f'Error: server_stop bad arguments: {args}. Type "help" for help.'
        self.sc_chain.servers_stop(indexes)

    def complete_server_stop(
        self: SidechainRepl, text: str, line: str, begidx: int, endidx: int
    ) -> List[str]:
        running_status = self.sc_chain.get_running_status()
        if "all".startswith(text):
            return ["all"]
        return [
            str(i)
            for (i, running) in enumerate(running_status)
            if running and str(i).startswith(text)
        ]

    def help_server_stop(self: SidechainRepl) -> None:
        print(
            "\n".join(
                [
                    "server_stop index [index...] | all",
                    "Stop a running server",
                ]
            )
        )

    # server_stop
    ##################

    ##################
    # hook

    # TODO: re-add hook functionality
    # def do_hook(self: SidechainRepl, line: str) -> None:
    #     args = line.split()
    #     if len(args) != 2:
    #         print(
    #             f'Error: hook command takes two arguments. Type "help" for help.'
    #         )
    #         return
    #     nickname = args[0]
    #     args.pop(0)
    #     hook_name = args[0]
    #     args.pop(0)
    #     assert not args

    #     if nickname == 'door':
    #         print(f'Error: Cannot set hooks on the "door" account.')
    #         return

    #     if not self.sc_chain.is_alias(nickname):
    #         print(f'Error: {nickname} is not in the address book')
    #         return

    #     src_account = self.sc_chain.account_from_alias(nickname)

    #     if hook_name not in _valid_hook_names:
    #         print(
    #             f'{hook_name} is not a valid hook. Valid hooks are: '
    #             f'{_valid_hook_names}'
    #         )
    #         return

    #     hook_file = HOOKS_DIR / hook_name / f'{hook_name}.wasm'
    #     if not os.path.isfile(hook_file):
    #         print(f'Error: The hook file {hook_file} does not exist.')
    #         return
    #     create_code = _file_to_hex(hook_file)
    #     self.sc_chain.send_signed(
    #         SetHook(account=src_account.account_id, create_code=create_code)
    #     )
    #     self.sc_chain.maybe_ledger_accept()

    # def complete_hook(
    #     self: SidechainRepl, text: str, line: str, begidx: int, endidx: int
    # ) -> List[str]:
    #     args = line.split()
    #     arg_num = len(args)
    #     if not text:
    #         arg_num += 1
    #     if arg_num == 2:  # account
    #         return self._complete_account(text, line, chain_name='sidechain')
    #     elif arg_num == 3:  # hook
    #         if not text:
    #             return _valid_hook_names
    #         return [c for c in _valid_hook_names if c.startswith(text)]
    #     return []

    # def help_hook(self: SidechainRepl) -> None:
    #     print('\n'.join([
    #         'hook account hook_name',
    #         'Set a hook on a sidechain account',
    #     ]))

    # hook
    ##################

    ##################
    # quit
    def do_quit(self: SidechainRepl, line: str) -> bool:
        print("Thank you for using RiplRepl. Goodbye.\n\n")
        return True

    def help_quit(self: SidechainRepl) -> None:
        print("Exit the program.")

    # quit
    ##################

    ##################
    # setup_accounts

    def do_setup_accounts(self: SidechainRepl, line: str) -> None:
        for a in ["alice", "bob"]:
            self.mc_chain.create_account(a)
        for a in ["brad", "carol"]:
            self.sc_chain.create_account(a)
        amt = str(5000 * 1_000_000)
        src = self.mc_chain.account_from_alias("root")
        dst = self.mc_chain.account_from_alias("alice")
        self.mc_chain.send_signed(
            Payment(account=src.account_id, destination=dst.account_id, amount=amt)
        )
        self.mc_chain.maybe_ledger_accept()

    # setup_accounts
    ##################

    ##################
    # setup_ious

    def do_setup_ious(self: SidechainRepl, line: str) -> None:
        mc_chain = self.mc_chain
        sc_chain = self.sc_chain
        mc_asset = IssuedCurrency(
            currency="USD", issuer=mc_chain.account_from_alias("root")
        )
        sc_asset = IssuedCurrency(
            currency="USD", issuer=sc_chain.account_from_alias("door")
        )
        mc_chain.add_asset_alias(mc_asset, "rrr")
        sc_chain.add_asset_alias(sc_asset, "ddd")
        mc_chain.send_signed(
            TrustSet(
                account=mc_chain.account_from_alias("alice").account_id,
                limit_amount=mc_asset(1_000_000),
            )
        )

        # create brad account on the side chain and set the trust line
        memos = [
            Memo.from_dict(
                {
                    "MemoData": sc_chain.account_from_alias(
                        "brad"
                    ).account_id_str_as_hex()
                }
            )
        ]
        mc_chain.send_signed(
            Payment(
                account=mc_chain.account_from_alias("alice").account_id,
                destination=mc_chain.account_from_alias("door").account_id,
                amount=str(3000 * 1_000_000),
                memos=memos,
            )
        )
        mc_chain.maybe_ledger_accept()

        # create a trust line to alice and pay her USD/rrr
        mc_chain.send_signed(
            TrustSet(
                account=mc_chain.account_from_alias("alice").account_id,
                limit_amount=mc_asset(1_000_000),
            )
        )
        mc_chain.maybe_ledger_accept()
        mc_chain.send_signed(
            Payment(
                account=mc_chain.account_from_alias("root").account_id,
                destination=mc_chain.account_from_alias("alice").account_id,
                amount=mc_asset(10_000),
            )
        )
        mc_chain.maybe_ledger_accept()

        time.sleep(2)

        # create a trust line for brad
        sc_chain.send_signed(
            TrustSet(
                account=sc_chain.account_from_alias("brad").account_id,
                limit_amount=sc_asset(1_000_000),
            )
        )

    # setup_ious
    ##################

    ##################
    # q

    def do_q(self: SidechainRepl, line: str) -> bool:
        return self.do_quit(line)

    def help_q(self: SidechainRepl) -> None:
        return self.help_quit()

    # q
    ##################

    ##################
    # account_tx

    def do_account_tx(self: SidechainRepl, line: str) -> None:
        args = line.split()
        if len(args) < 2:
            print(
                'Error: account_tx command takes two or three arguments. Type "help" '
                "for help."
            )
            return

        chain = None

        if args[0] not in ["mainchain", "sidechain"]:
            print('Error: The first argument must be "mainchain" or "sidechain".')
            return

        if args[0] == "mainchain":
            chain = self.mc_chain
        else:
            chain = self.sc_chain
        args.pop(0)

        accountStr = args[0]
        args.pop(0)

        out_file = None
        if args:
            out_file = args[0]
            args.pop(0)

        assert not args

        if not chain.is_alias(accountStr):
            print(f"Error: The issuer {accountStr} is not part of the address book.")
            return

        account = chain.account_from_alias(accountStr)

        result = json.dumps(
            chain.request(AccountTx(account=account.account_id)), indent=1
        )
        print(f"{result}")
        if out_file:
            with open(out_file, "a") as f:
                f.write(f"{result}\n")

    def complete_account_tx(
        self: SidechainRepl, text: str, line: str, begidx: int, endidx: int
    ) -> List[str]:
        args = line.split()
        arg_num = len(args)
        if not text:
            arg_num += 1
        if arg_num == 2:  # chain
            return self._complete_chain(text, line)
        if arg_num == 3:  # account
            return self._complete_account(text, line, chain_name=args[1])
        return []

    def help_account_tx(self: SidechainRepl) -> None:
        print(
            "\n".join(
                [
                    "account_tx (mainchain | sidechain) account [filename]",
                    "Return the account transactions",
                ]
            )
        )

    # account_tx
    ##################

    ##################
    # subscribe

    # Note: The callback isn't called until the user types a new command.
    # TODO: Make subscribe asynchronous so the callback is called without requiring the
    # user to type
    # a new command.
    def do_subscribe(self: SidechainRepl, line: str) -> None:
        args = line.split()
        if len(args) != 3:
            print(
                'Error: subscribe command takes exactly three arguments. Type "help" '
                "for help."
            )
            return

        chain = None

        if args[0] not in ["mainchain", "sidechain"]:
            print('Error: The first argument must be "mainchain" or "sidechain".')
            return

        if args[0] == "mainchain":
            chain = self.mc_chain
        else:
            chain = self.sc_chain
        args.pop(0)

        accountStr = args[0]
        args.pop(0)

        out_file = args[0]
        args.pop(0)

        assert not args

        if not chain.is_alias(accountStr):
            print(f"Error: The issuer {accountStr} is not part of the address book.")
            return

        account = chain.account_from_alias(accountStr)

        def _subscribe_callback(v: Dict[str, Any]) -> None:
            with open(out_file, "a") as f:
                f.write(f"{json.dumps(v, indent=1)}\n")

        chain.send_subscribe(Subscribe(accounts=[account]), _subscribe_callback)

    def complete_subscribe(
        self: SidechainRepl, text: str, line: str, begidx: int, endidx: int
    ) -> List[str]:
        args = line.split()
        arg_num = len(args)
        if not text:
            arg_num += 1
        if arg_num == 2:  # chain
            return self._complete_chain(text, line)
        if arg_num == 3:  # account
            return self._complete_account(text, line, chain_name=args[1])
        return []

    def help_subscribe(self: SidechainRepl) -> None:
        print(
            "\n".join(
                [
                    "subscribe (mainchain | sidechain) account filename",
                    "Subscribe to the stream and write the results to filename",
                    "Note: The file is not updated until the user types a new command",
                ]
            )
        )

    # subscribe
    ##################

    ##################
    # EOF
    def do_EOF(self: SidechainRepl, line: str) -> bool:
        print("Thank you for using RiplRepl. Goodbye.\n\n")
        return True

    def help_EOF(self: SidechainRepl) -> None:
        print("Exit the program by typing control-d.")

    # EOF
    ##################


def repl(mc_chain: Chain, sc_chain: Chain) -> None:
    SidechainRepl(mc_chain, sc_chain).cmdloop()
