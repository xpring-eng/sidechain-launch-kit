"""Simple REPL for interacting with side chains."""

from __future__ import annotations

import binascii
import cmd
import json
import os
import pprint
import time
from pathlib import Path
from typing import List, Optional, Set, Tuple, Union, cast

from tabulate import tabulate
from xrpl.models import (
    XRP,
    AccountTx,
    Amount,
    Currency,
    IssuedCurrencyAmount,
    Memo,
    Payment,
    TrustSet,
)

from slk.chain.chain import Chain
from slk.classes.account import Account
from slk.repl.repl_functionality import (
    get_account_info,
    get_balances_data,
    get_federator_info,
    get_server_info,
    set_up_accounts,
    set_up_ious,
)


def _clear_screen() -> None:
    if os.name == "nt":
        _ = os.system("cls")
    else:
        _ = os.system("clear")


def _file_to_hex(filename: Path) -> str:
    with open(filename, "rb") as f:
        content = f.read()
    return binascii.hexlify(content).decode("utf8")


class SidechainRepl(cmd.Cmd):
    """Simple REPL for interacting with side chains."""

    intro = "\n\nWelcome to the sidechain shell.   Type help or ? to list commands.\n"
    prompt = "SSX> "

    def preloop(self: SidechainRepl) -> None:
        """Clear the screen before the REPL starts up."""
        _clear_screen()

    def __init__(self: SidechainRepl, mc_chain: Chain, sc_chain: Chain) -> None:
        """
        Initialize the sidechain REPL.

        Args:
            mc_chain: The Chain representing the mainchain.
            sc_chain: The Chain representing the sidechain.
        """
        super().__init__()
        assert mc_chain.is_alias("door") and sc_chain.is_alias("door")
        self.mc_chain = mc_chain
        self.sc_chain = sc_chain

    ##################
    # complete helpers

    def _complete_chain(self: SidechainRepl, text: str) -> List[str]:
        """
        Helper method to complete the chain name.

        Args:
            text: The text to autocomplete.

        Returns:
            The chain names that could autocomplete the provided text.
        """
        if not text:
            return ["mainchain", "sidechain"]
        else:
            return [c for c in ["mainchain", "sidechain"] if c.startswith(text)]

    def _complete_unit(self: SidechainRepl, text: str) -> List[str]:
        """
        Helper method to complete the unit.

        Args:
            text: The text to autocomplete.

        Returns:
            The unit names that could autocomplete the provided text.
        """
        if not text:
            return ["drops", "xrp"]
        else:
            return [c for c in ["drops", "xrp"] if c.startswith(text)]

    def _complete_account(
        self: SidechainRepl, text: str, chain_name: Optional[str] = None
    ) -> List[str]:
        """
        Helper method to complete the account alias name.

        Args:
            text: The text to autocomplete.
            chain_name: The chain to search for accounts. If None, treat as a wildcard.
                The default is None.

        Returns:
            The account nicknames that could autocomplete the provided text.
        """
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
        self: SidechainRepl, text: str, chain_name: Optional[str] = None
    ) -> List[str]:
        """
        Helper method to complete the asset alias name.

        Args:
            text: The text to autocomplete.
            chain_name: The chain to search for assets. If None, treat as a wildcard.
                The default is None.

        Returns:
            The asset names that could autocomplete the provided text.
        """
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

    # complete helpers
    ##################

    ##################
    # do helpers
    def _get_chain_args(
        self: SidechainRepl, chain_args: List[str]
    ) -> Tuple[List[Chain], List[str]]:
        """
        Helper method to get the chains/names.

        Args:
            chain_args: The names of the chains to get.

        Returns:
            The chains and chain names of the chains.
        """
        chains = [self.mc_chain, self.sc_chain]
        chain_names = ["mainchain", "sidechain"]

        if chain_args and chain_args[0] in chain_names:
            chain_names = [chain_args[0]]
            if chain_args[0] == "mainchain":
                chains = [self.mc_chain]
            else:
                chains = [self.sc_chain]
            chain_args.pop(0)

        return chains, chain_names

    def _get_chain_arg(self: SidechainRepl, chain_arg: str) -> Optional[Chain]:
        """
        Helper method to get the chain arg.

        Args:
            chain_arg: The name of the chain to fetch.

        Returns:
            The chain that corresponds to the chain name.
        """
        if chain_arg not in ["mainchain", "sidechain"]:
            print('Error: First argument must specify the chain. Type "help" for help.')
            return None
        if chain_arg == "mainchain":
            return self.mc_chain
        return self.sc_chain

    # do helpers
    ##################

    ##################
    # addressbook
    def do_addressbook(self: SidechainRepl, line: str) -> None:
        """
        Implementation of the `addressbook` REPL command.

        Args:
            line: The command-line arguments.
        """
        args = line.split()
        if len(args) > 2:
            print(
                'Error: Too many arguments to addressbook command. Type "help" for '
                "help."
            )
            return

        chains, chain_names = self._get_chain_args(args)
        nickname = None

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
        """
        Handle autocompletion for the `addressbook` REPL command.

        Args:
            line: The command-line args so far.
            text: The text to autocomplete.
            begidx: The beginning index of the prefix text.
            endidx: The end index of the prefix text.

        Returns:
            The list of possible auto-complete results.
        """
        args = line.split()
        arg_num = len(args)
        if arg_num == 2:  # chain
            return self._complete_chain(text) + self._complete_account(text)
        if arg_num == 3:  # account
            return self._complete_account(text, chain_name=args[1])
        return []

    def help_addressbook(self: SidechainRepl) -> None:
        """Print out a help message for the `addressbook` REPL command."""
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
        """
        Implementation of the `balance` REPL command.

        Args:
            line: The command-line arguments.
        """
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
        chains, chain_names = self._get_chain_args(args)

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
        assets: List[List[Currency]] = [[XRP()]] * len(chains)
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
            assets = [
                [cast(Currency, XRP())] + cast(List[Currency], c.known_iou_assets())
                for c in chains
            ]

        # should be done analyzing all the params
        assert arg_index == len(args)

        result = get_balances_data(chains, chain_names, account_ids, assets, in_drops)
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
        """
        Handle autocompletion for the `balance` REPL command.

        Args:
            line: The command-line args so far.
            text: The text to autocomplete.
            begidx: The beginning index of the prefix text.
            endidx: The end index of the prefix text.

        Returns:
            The list of possible auto-complete results.
        """
        args = line.split()
        arg_num = len(args)
        if arg_num == 2:  # chain or account
            return self._complete_chain(text) + self._complete_account(text)
        elif arg_num == 3:  # account or unit or asset_alias
            return (
                self._complete_account(text)
                + self._complete_unit(text)
                + self._complete_asset(text, chain_name=args[1])
            )
        elif arg_num == 4:  # unit
            return self._complete_unit(text) + self._complete_asset(
                text, chain_name=args[1]
            )
        return []

    def help_balance(self: SidechainRepl) -> None:
        """Print out a help message for the `balance` REPL command."""
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
        """
        Implementation of the `account_info` REPL command.

        Args:
            line: The command-line arguments.
        """
        args = line.split()
        if len(args) > 2:
            print(
                'Error: Too many arguments to account_info command. Type "help" for '
                "help."
            )
            return
        chains, chain_names = self._get_chain_args(args)

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

        results = get_account_info(chains, chain_names, account_ids)

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
        """
        Handle autocompletion for the `account_info` REPL command.

        Args:
            line: The command-line args so far.
            text: The text to autocomplete.
            begidx: The beginning index of the prefix text.
            endidx: The end index of the prefix text.

        Returns:
            The list of possible auto-complete results.
        """
        args = line.split()
        arg_num = len(args)
        if arg_num == 2:  # chain or account
            return self._complete_chain(text) + self._complete_account(text)
        elif arg_num == 3:  # account
            return self._complete_account(text)
        return []

    def help_account_info(self: SidechainRepl) -> None:
        """Print out a help message for the `account_info` REPL command."""
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
        """
        Implementation of the `pay` REPL command.

        Args:
            line: The command-line arguments.
        """
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

        chain = self._get_chain_arg(args[0])
        if not chain:
            return

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

        asset = None
        in_drops = False

        if len(args) > 4:
            asset_alias = args[4]
            if asset_alias in ["xrp", "drops"]:
                if asset_alias == "xrp":
                    in_drops = False
                elif asset_alias == "drops":
                    in_drops = True
            if not chain.is_asset_alias(asset_alias):
                print(f"Error: {args[4]} is an invalid asset alias.")
                return
            asset = chain.asset_from_alias(asset_alias)

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

        if (
            (asset is not None and isinstance(asset, XRP)) or asset is None
        ) and not in_drops:
            amt_value *= 1_000_000

        if asset is not None:
            amt: Amount = asset.to_amount(amt_value)
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
        """
        Handle autocompletion for the `pay` REPL command.

        Args:
            line: The command-line args so far.
            text: The text to autocomplete.
            begidx: The beginning index of the prefix text.
            endidx: The end index of the prefix text.

        Returns:
            The list of possible auto-complete results.
        """
        args = line.split()
        arg_num = len(args)
        if not text:
            arg_num += 1
        if arg_num == 2:  # chain
            return self._complete_chain(text)
        elif arg_num == 3:  # account
            return self._complete_account(text, chain_name=args[1])
        elif arg_num == 4:  # account
            return self._complete_account(text, chain_name=args[1])
        elif arg_num == 5:  # amount
            return []
        elif arg_num == 6:  # drops or xrp or asset
            return self._complete_unit(text) + self._complete_asset(
                text, chain_name=args[1]
            )
        return []

    def help_pay(self: SidechainRepl) -> None:
        """Print out a help message for the `pay` REPL command."""
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
        """
        Implementation of the `xchain` REPL command.

        Args:
            line: The command-line arguments.
        """
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

        nickname = args[1]
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

        nickname = args[2]
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

        amt_value: Optional[Union[int, float]] = None
        in_drops = False
        asset = None

        if len(args) > 4:
            asset_alias = args[4]
            if asset_alias in ["xrp", "drops"]:
                if asset_alias == "xrp":
                    in_drops = False
                elif asset_alias == "drops":
                    in_drops = True
            if not chain.is_asset_alias(asset_alias):
                print(f"Error: {asset_alias} is an invalid asset alias.")
                return
            asset = chain.asset_from_alias(asset_alias)

        try:
            amt_value = int(args[3])
        except:
            try:
                if not in_drops:
                    amt_value = float(args[3])
            except:
                pass

        if amt_value is None:
            print(f"Error: {args[3]} is an invalid amount.")
            return

        if (
            (asset is not None and isinstance(asset, XRP)) or asset is None
        ) and not in_drops:
            amt_value *= 1_000_000

        if asset is not None:
            amt: Amount = asset.to_amount(str(amt_value))
        else:
            amt = str(amt_value)

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
        """
        Handle autocompletion for the `xchain` REPL command.

        Args:
            line: The command-line args so far.
            text: The text to autocomplete.
            begidx: The beginning index of the prefix text.
            endidx: The end index of the prefix text.

        Returns:
            The list of possible auto-complete results.
        """
        args = line.split()
        arg_num = len(args)
        if not text:
            arg_num += 1
        if arg_num == 2:  # chain
            return self._complete_chain(text)
        elif arg_num == 3:  # this chain account
            return self._complete_account(text, chain_name=args[1])
        elif arg_num == 4:  # other chain account
            other_chain_name = None
            if args[1] == "mainchain":
                other_chain_name = "sidechain"
            if args[1] == "sidechain":
                other_chain_name = "mainchain"
            return self._complete_account(text, chain_name=other_chain_name)
        elif arg_num == 5:  # amount
            return []
        elif arg_num == 6:  # drops or xrp or asset
            return self._complete_unit(text) + self._complete_asset(
                text, chain_name=args[1]
            )
        return []

    def help_xchain(self: SidechainRepl) -> None:
        """Print out a help message for the `xchain` REPL command."""
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
        """
        Implementation of the `server_info` REPL command.

        Args:
            line: The command-line arguments.
        """
        args = line.split()
        if len(args) > 1:
            print(
                'Error: Too many arguments to server_info command. Type "help" for '
                "help."
            )
            return

        chains, chain_names = self._get_chain_args(args)

        result = get_server_info(chains, chain_names)

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
        """
        Handle autocompletion for the `server_info` REPL command.

        Args:
            line: The command-line args so far.
            text: The text to autocomplete.
            begidx: The beginning index of the prefix text.
            endidx: The end index of the prefix text.

        Returns:
            The list of possible auto-complete results.
        """
        arg_num = len(line.split())
        if arg_num == 2:  # chain
            return self._complete_chain(text)
        return []

    def help_server_info(self: SidechainRepl) -> None:
        """Print out a help message for the `server_info` REPL command."""
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
        """
        Implementation of the `federator_info` REPL command.

        Args:
            line: The command-line arguments.
        """
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

        info_dict = self.sc_chain.federator_info(indexes)
        if raw:
            pprint.pprint(info_dict)
            return

        info_table, pending_tx_data = get_federator_info(info_dict, verbose)

        print(
            tabulate(
                info_table,
                headers="keys",
                tablefmt="presto",
            )
        )
        # pending
        print("")  # newline separation
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
        """
        Handle autocompletion for the `federator_info` REPL command.

        Args:
            line: The command-line args so far.
            text: The text to autocomplete.
            begidx: The beginning index of the prefix text.
            endidx: The end index of the prefix text.

        Returns:
            The list of possible auto-complete results.
        """
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
        """Print out a help message for the `federator_info` REPL command."""
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
        """
        Implementation of the `new_account` REPL command.

        Args:
            line: The command-line arguments.
        """
        args = line.split()
        if len(args) < 2:
            print(
                "Error: new_account command takes at least two arguments. Type "
                '"help" for help.'
            )
            return

        chain = self._get_chain_arg(args[0])
        if not chain:
            return
        args.pop(0)

        # an new account either generates its own new secret seed, or one may be
        # specified by using a `-s <seed>` switch
        aliases = []
        seeds: List[Optional[str]] = []
        index = 0
        while True:
            if index == len(args):
                break
            if args[index] == "-s":
                print(
                    "Error: new_account -s switch must come after the alias argument."
                    ' Type  "help" for help.'
                )
                return
            aliases.append(args[index])
            seeds.append(None)
            index += 1
            if index == len(args):
                break
            if args[index] != "-s":
                continue
            # user supplied seed
            index += 1
            if index == len(args):
                print(
                    "Error: new_account -s switch takes one argument. Type "
                    '"help" for help.'
                )
                return
            seeds[-1] = args[index]
            index += 1

        if len(aliases) != len(seeds):
            print(
                "Error: internal error.\n"
                "There should be an equal number of aliases and seeds.\n"
                f"{aliases=} {seeds=}"
            )
            return

        for alias, seed in zip(aliases, seeds):
            if chain.is_alias(alias):
                print(f"Warning: The alias {alias} already exists.")
            else:
                try:
                    chain.create_account(alias, seed)
                except:
                    print(
                        f"Error: could not create an account {alias} with seed {seed}"
                    )

    def complete_new_account(
        self: SidechainRepl, text: str, line: str, begidx: int, endidx: int
    ) -> List[str]:
        """
        Handle autocompletion for the `new_account` REPL command.

        Args:
            line: The command-line args so far.
            text: The text to autocomplete.
            begidx: The beginning index of the prefix text.
            endidx: The end index of the prefix text.

        Returns:
            The list of possible auto-complete results.
        """
        arg_num = len(line.split())
        if arg_num == 2:  # chain
            return self._complete_chain(text)
        return []

    def help_new_account(self: SidechainRepl) -> None:
        """Print out a help message for the `new_account` REPL command."""
        print(
            "\n".join(
                [
                    "new_account (mainchain | sidechain) alias "
                    "[-s secret_seed] [alias [-s secret_seed]...] ",
                    "Add a new account to the address book",
                ]
            )
        )

    # new_account
    ##################

    ##################
    # new_iou
    def do_new_iou(self: SidechainRepl, line: str) -> None:
        """
        Implementation of the `new_iou` REPL command.

        Args:
            line: The command-line arguments.
        """
        args = line.split()
        if len(args) != 4:
            print(
                'Error: new_iou command takes exactly four arguments. Type "help" '
                "for help."
            )
            return

        chain = self._get_chain_arg(args[0])
        if not chain:
            return
        args.pop(0)

        (alias, currency, issuer) = args

        if chain.is_asset_alias(alias):
            print(f"Error: The alias {alias} already exists.")
            return

        if not chain.is_alias(issuer):
            print(f"Error: The issuer {issuer} is not part of the address book.")
            return

        asset = IssuedCurrencyAmount(
            value="0",
            currency=currency,
            issuer=chain.account_from_alias(issuer).account_id,
        )
        chain.add_asset_alias(asset, alias)

    def complete_new_iou(
        self: SidechainRepl, text: str, line: str, begidx: int, endidx: int
    ) -> List[str]:
        """
        Handle autocompletion for the `new_iou` REPL command.

        Args:
            line: The command-line args so far.
            text: The text to autocomplete.
            begidx: The beginning index of the prefix text.
            endidx: The end index of the prefix text.

        Returns:
            The list of possible auto-complete results.
        """
        arg_num = len(line.split())
        if arg_num == 2:  # chain
            return self._complete_chain(text)
        if arg_num == 5:  # issuer
            return self._complete_account(text)
        return []

    def help_new_iou(self: SidechainRepl) -> None:
        """Print out a help message for the `new_iou` REPL command."""
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
        """
        Implementation of the `ious` REPL command.

        Args:
            line: The command-line arguments.
        """

        def print_ious(chain: Chain, chain_name: str, nickname: Optional[str]) -> None:
            if nickname and not chain.is_asset_alias(nickname):
                print(f"{nickname} is not part of {chain_name}'s asset aliases.")
            print(f"{chain_name}:\n{chain.asset_aliases.to_string(nickname)}")

        args = line.split()
        if len(args) > 2:
            print('Error: Too many arguments to ious command. Type "help" for help.')
            return

        chains, chain_names = self._get_chain_args(args)

        nickname = None
        if args:
            nickname = args[0]

        for chain, name in zip(chains, chain_names):
            print_ious(chain, name, nickname)
            print("\n")

    def complete_ious(
        self: SidechainRepl, text: str, line: str, begidx: int, endidx: int
    ) -> List[str]:
        """
        Handle autocompletion for the `ious` REPL command.

        Args:
            line: The command-line args so far.
            text: The text to autocomplete.
            begidx: The beginning index of the prefix text.
            endidx: The end index of the prefix text.

        Returns:
            The list of possible auto-complete results.
        """
        args = line.split()
        arg_num = len(args)
        if arg_num == 2:  # chain or iou
            return self._complete_chain(text) + self._complete_asset(text)
        if arg_num == 3:  # iou
            return self._complete_asset(text, chain_name=args[1])
        return []

    def help_ious(self: SidechainRepl) -> None:
        """Print out a help message for the `ious` REPL command."""
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
        """
        Implementation of the `set_trust` REPL command.

        Args:
            line: The command-line arguments.
        """
        # TODO: fix bug where REPL crashes if account isn't funded yet
        args = line.split()
        if len(args) != 4:
            print(
                'Error: set_trust command takes exactly four arguments. Type "help" '
                "for help."
            )
            return

        chain = self._get_chain_arg(args[0])
        if not chain:
            return
        args.pop(0)

        (alias, account_str, amount_str) = args

        if not chain.is_asset_alias(alias):
            print(f"Error: The alias {alias} does not exists.")
            return

        if not chain.is_alias(account_str):
            print(f"Error: The issuer {account_str} is not part of the address book.")
            return

        account = chain.account_from_alias(account_str)

        amount: Optional[Union[int, float]] = None
        try:
            amount = int(amount_str)
        except:
            try:
                amount = float(amount_str)
            except:
                pass

        if amount is None:
            print(f"Error: Invalid amount {amount_str}")
            return

        asset = chain.asset_from_alias(alias).to_amount(amount)
        # TODO: resolve error where repl crashes if account doesn't exist
        chain.send_signed(TrustSet(account=account.account_id, limit_amount=asset))
        chain.maybe_ledger_accept()

    def complete_set_trust(
        self: SidechainRepl, text: str, line: str, begidx: int, endidx: int
    ) -> List[str]:
        """
        Handle autocompletion for the `set_trust` REPL command.

        Args:
            line: The command-line args so far.
            text: The text to autocomplete.
            begidx: The beginning index of the prefix text.
            endidx: The end index of the prefix text.

        Returns:
            The list of possible auto-complete results.
        """
        args = line.split()
        arg_num = len(args)
        if arg_num == 2:  # chain
            return self._complete_chain(text)
        if arg_num == 3:  # iou
            return self._complete_asset(text, chain_name=args[1])
        if arg_num == 4:  # account
            return self._complete_account(text, chain_name=args[1])
        return []

    def help_set_trust(self: SidechainRepl) -> None:
        """Print out a help message for the `set_trust` REPL command."""
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
        """
        Implementation of the `ledger_accept` REPL command.

        Args:
            line: The command-line arguments.
        """
        args = line.split()
        if len(args) != 1:
            print(
                'Error: ledger_accept command takes exactly one argument. Type "help" '
                "for help."
            )
            return

        chain = None

        chain = self._get_chain_arg(args[0])
        if not chain:
            return
        args.pop(0)

        assert not args

        chain.maybe_ledger_accept()

    def complete_ledger_accept(
        self: SidechainRepl, text: str, line: str, begidx: int, endidx: int
    ) -> List[str]:
        """
        Handle autocompletion for the `ledger_accept` REPL command.

        Args:
            line: The command-line args so far.
            text: The text to autocomplete.
            begidx: The beginning index of the prefix text.
            endidx: The end index of the prefix text.

        Returns:
            The list of possible auto-complete results.
        """
        arg_num = len(line.split())
        if arg_num == 2:  # chain
            return self._complete_chain(text)
        return []

    def help_ledger_accept(self: SidechainRepl) -> None:
        """Print out a help message for the `ledger_accept` REPL command."""
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
        """
        Implementation of the `server_start` REPL command.

        Args:
            line: The command-line arguments.
        """
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
        self.sc_chain.servers_start(server_indexes=indexes)

    def complete_server_start(
        self: SidechainRepl, text: str, line: str, begidx: int, endidx: int
    ) -> List[str]:
        """
        Handle autocompletion for the `server_start` REPL command.

        Args:
            line: The command-line args so far.
            text: The text to autocomplete.
            begidx: The beginning index of the prefix text.
            endidx: The end index of the prefix text.

        Returns:
            The list of possible auto-complete results.
        """
        running_status = self.sc_chain.get_running_status()
        if "all".startswith(text):
            return ["all"]
        return [
            str(i)
            for (i, running) in enumerate(running_status)
            if not running and str(i).startswith(text)
        ]

    def help_server_start(self: SidechainRepl) -> None:
        """Print out a help message for the `server_start` REPL command."""
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
        """
        Implementation of the `server_stop` REPL command.

        Args:
            line: The command-line arguments.
        """
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
        """
        Handle autocompletion for the `server_stop` REPL command.

        Args:
            line: The command-line args so far.
            text: The text to autocomplete.
            begidx: The beginning index of the prefix text.
            endidx: The end index of the prefix text.

        Returns:
            The list of possible auto-complete results.
        """
        running_status = self.sc_chain.get_running_status()
        if "all".startswith(text):
            return ["all"]
        return [
            str(i)
            for (i, running) in enumerate(running_status)
            if running and str(i).startswith(text)
        ]

    def help_server_stop(self: SidechainRepl) -> None:
        """Print out a help message for the `server_stop` REPL command."""
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
    # setup_accounts

    def do_setup_accounts(self: SidechainRepl, line: str) -> None:
        """
        Implementation of the `setup_accounts` REPL command.

        Args:
            line: The command-line arguments.
        """
        set_up_accounts(self.mc_chain, self.sc_chain)

    # setup_accounts
    ##################

    ##################
    # load_batch

    def do_load_batch(self: SidechainRepl, line: str) -> None:
        """
        Implementation of the `load_batch` REPL command.

        Args:
            line: The command-line arguments.
        """
        args = line.split()
        if len(args) != 1:
            print(
                'Error: load_batch command takes exactly one argument. Type "help" '
                "for help."
            )
            return
        try:
            path = Path(args[0])
            if not path.is_file():
                print(f"Error: no such file: {path}")
                return
            with open(path) as f:
                for line in f:
                    # remove comments. A comment is a '#' and anything that follows
                    # it up to the end of a line. Note this doesn't account for '#'
                    # inside strings or escaped, but that should be fine for this
                    # simple repl. It doesn't have strings anyway.
                    line = line.split("#")[0].strip()
                    if not line:
                        continue
                    print(f"Running: `{line}`")
                    self.onecmd(line)
        except Exception as e:
            print(f"Error: load_batch command threw an exception: `{e}`")

    def complete_load_batch(
        self: SidechainRepl, text: str, line: str, begidx: int, endidx: int
    ) -> List[str]:
        """
        Handle autocompletion for the `load_batch` REPL command.

        Args:
            line: The command-line args so far.
            text: The text to autocomplete.
            begidx: The beginning index of the prefix text.
            endidx: The end index of the prefix text.

        Returns:
            The list of possible auto-complete results.
        """
        args = line.split()
        if len(args) == 1:
            arg = ""
        else:
            arg = line.split()[-1]
        if not arg:
            arg = "./"
        elif not (arg.startswith("/") or arg.startswith("./")):
            arg = f"./{arg}"
        p = Path(arg)
        if p.is_dir():
            dir = p
            file = "/"
        else:
            dir = p.parent
            file = p.name
        prefix = f"{dir.as_posix()}/"
        return [f.as_posix().lstrip(prefix) for f in dir.glob(f"{file}*")]

    def help_load_batch(self: SidechainRepl) -> None:
        """Print out a help message for the `load_batch` REPL command."""
        print(
            "\n".join(
                [
                    "load_batch file_name",
                    "Run the commands in the specified file",
                ]
            )
        )

    # load_batch
    ##################

    ##################
    # setup_ious

    def do_setup_ious(self: SidechainRepl, line: str) -> None:
        """
        Implementation of the `setup_ious` REPL command.

        Args:
            line: The command-line arguments.
        """
        set_up_ious(self.mc_chain, self.sc_chain)

    # setup_ious
    ##################

    ##################
    # account_tx

    def do_account_tx(self: SidechainRepl, line: str) -> None:
        """
        Implementation of the `account_tx` REPL command.

        Args:
            line: The command-line arguments.
        """
        args = line.split()
        if len(args) < 2:
            print(
                'Error: account_tx command takes two or three arguments. Type "help" '
                "for help."
            )
            return

        chain = None

        chain = self._get_chain_arg(args[0])
        if not chain:
            return
        args.pop(0)

        account_str = args[0]
        args.pop(0)

        out_file = None
        if args:
            out_file = args[0]
            args.pop(0)

        assert not args

        if not chain.is_alias(account_str):
            print(f"Error: The issuer {account_str} is not part of the address book.")
            return

        account = chain.account_from_alias(account_str)

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
        """
        Handle autocompletion for the `account_tx` REPL command.

        Args:
            line: The command-line args so far.
            text: The text to autocomplete.
            begidx: The beginning index of the prefix text.
            endidx: The end index of the prefix text.

        Returns:
            The list of possible auto-complete results.
        """
        args = line.split()
        arg_num = len(args)
        if not text:
            arg_num += 1
        if arg_num == 2:  # chain
            return self._complete_chain(text)
        if arg_num == 3:  # account
            return self._complete_account(text, chain_name=args[1])
        return []

    def help_account_tx(self: SidechainRepl) -> None:
        """Print out a help message for the `account_tx` REPL command."""
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
    # sleep

    def do_sleep(self: SidechainRepl, line: str) -> None:
        """
        Implementation of the `sleep` REPL command.

        Args:
            line: The command-line arguments.
        """
        args = line.split()
        if len(args) != 1:
            print('Error: sleep command takes one argument. Type "help" for help.')
            return
        arg = args[0]
        try:
            sleep_time = int(arg)
        except:
            print(f'Error: "{arg}" is not a number.')
            return
        print(f"Sleeping for {sleep_time} seconds...")
        time.sleep(sleep_time)
        print("")

    def help_sleep(self: SidechainRepl) -> None:
        """Print out a help message for the `sleep` REPL command."""
        print(
            "\n".join(
                [
                    "sleep [num]",
                    "Sleep for `num` seconds.",
                ]
            )
        )

    # sleep
    ##################

    ##################
    # quit
    def do_quit(self: SidechainRepl, line: str) -> bool:
        """
        Implementation of the `quit` REPL command.

        Args:
            line: The command-line arguments.

        Returns:
            True, so that the REPL closes.
        """
        print("Thank you for using the sidechain shell. Goodbye.\n\n")
        return True

    def help_quit(self: SidechainRepl) -> None:
        """Print out a help message for the `quit` REPL command."""
        print("Exit the program.")

    # quit
    ##################

    ##################
    # q

    def do_q(self: SidechainRepl, line: str) -> bool:
        """
        Implementation of the `q` REPL command.

        Args:
            line: The command-line arguments.

        Returns:
            True, so that the REPL closes.
        """
        return self.do_quit(line)

    def help_q(self: SidechainRepl) -> None:
        """Print out a help message for the `q` REPL command."""
        self.help_quit()

    # q
    ##################

    ##################
    # EOF
    def do_EOF(self: SidechainRepl, line: str) -> bool:
        """
        Implementation of what happens when the user types ctrl-d.

        Args:
            line: The command-line arguments.

        Returns:
            True, so that the REPL closes.
        """
        return self.do_quit(line)

    def help_EOF(self: SidechainRepl) -> None:
        """Print out a help message for when the user types ctrl-d."""
        print("Exit the program by typing control-d.")

    # EOF
    ##################


def start_repl(mc_chain: Chain, sc_chain: Chain) -> None:
    """
    Start the REPL.

    Args:
        mc_chain: The mainchain of the network.
        sc_chain: The sidechain of the network.
    """
    SidechainRepl(mc_chain, sc_chain).cmdloop()
