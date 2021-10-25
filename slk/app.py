import os
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Union

import pandas as pd
from xrpl.models import (
    AccountInfo,
    AccountLines,
    Amount,
    BookOffers,
    FederatorInfo,
    IssuedCurrency,
    IssuedCurrencyAmount,
    LedgerAccept,
    Payment,
    Request,
    Subscribe,
    is_xrp,
)
from xrpl.models.transactions.transaction import Transaction
from xrpl.transaction import safe_sign_and_submit_transaction

import slk.testnet as testnet
from slk.common import Account
from slk.config_file import ConfigFile
from slk.ripple_client import RippleClient


class KeyManager:
    def __init__(self):
        self._aliases = {}  # alias -> account
        self._accounts = {}  # account id -> account

    def add(self, account: Account) -> bool:
        if account.nickname:
            self._aliases[account.nickname] = account
        self._accounts[account.account_id] = account

    def is_alias(self, name: str) -> bool:
        return name in self._aliases

    def is_account(self, account: str) -> bool:
        return account in self._accounts

    def account_from_alias(self, name: str) -> Account:
        assert name in self._aliases
        return self._aliases[name]

    def known_accounts(self) -> List[Account]:
        return list(self._accounts.values())

    def get_account(self, account: str) -> Account:
        return self._accounts[account]

    def account_id_dict(self) -> Dict[str, Account]:
        return self._accounts

    def alias_or_account_id(self, id: Union[Account, str]) -> str:
        """return the alias if it exists, otherwise return the id"""
        if isinstance(id, Account):
            return id.alias_or_account_id()

        if id in self._accounts:
            return self._accounts[id].nickname
        return id

    def alias_to_account_id(self, alias: str) -> Optional[str]:
        if id in self._aliases:
            return self._aliases[id].account_id
        return None

    def to_string(self, nickname: Optional[str] = None):
        names = []
        account_ids = []
        if nickname:
            names = [nickname]
            if nickname in self._aliases:
                account_ids = [self._aliases[nickname].account_id]
            else:
                account_ids = ["NA"]
        else:
            for (k, v) in self._aliases.items():
                names.append(k)
                account_ids.append(v.account_id)
        # use a dataframe to get a nice table output
        df = pd.DataFrame(data={"name": names, "id": account_ids})
        return f"{df.to_string(index=False)}"


class AssetAliases:
    def __init__(self):
        self._aliases = {}  # alias -> IssuedCurrency

    def add(self, asset: IssuedCurrency, name: str):
        self._aliases[name] = asset

    def is_alias(self, name: str):
        return name in self._aliases

    def asset_from_alias(self, name: str) -> IssuedCurrency:
        assert name in self._aliases
        return self._aliases[name]

    def known_aliases(self) -> List[str]:
        return list(self._aliases.keys())

    def known_assets(self) -> List[IssuedCurrency]:
        return list(self._aliases.values())

    def to_string(self, nickname: Optional[str] = None):
        names = []
        currencies = []
        issuers = []
        if nickname:
            names = [nickname]
            if nickname in self._aliases:
                v = self._aliases[nickname]
                currencies = [v.currency]
                issuers = [v.issuer if v.issuer else ""]
            else:
                currencies = ["NA"]
                issuers = ["NA"]
        else:
            for (k, v) in self._aliases.items():
                names.append(k)
                currencies.append(v.currency)
                issuers.append(v.issuer if v.issuer else "")
        # use a dataframe to get a nice table output
        df = pd.DataFrame(
            data={"name": names, "currency": currencies, "issuer": issuers}
        )
        return f"{df.to_string(index=False)}"


class App:
    """App to to interact with rippled servers"""

    def __init__(
        self,
        *,
        standalone: bool,
        network: Optional[testnet.Network] = None,
        client: Optional[RippleClient] = None,
    ):
        if network and client:
            raise ValueError("Cannot specify both a testnet and client in App")
        if not network and not client:
            raise ValueError("Must specify a testnet or a client in App")

        self.standalone = standalone
        self.network = network

        if client:
            self.client = client
        else:
            self.client = self.network.get_client(0)

        self.key_manager = KeyManager()
        self.asset_aliases = AssetAliases()
        root_account = Account(
            nickname="root",
            account_id="rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh",
            secret_key="snoPBrXtMeMyMHUVTgbuqAfg1SUTb",
        )
        self.key_manager.add(root_account)

    def shutdown(self):
        if self.network:
            self.network.shutdown()
        else:
            self.client.shutdown()

    def send_signed(self, txn: Transaction, autofill: bool = True) -> dict:
        """Sign then send the given transaction"""
        if not self.key_manager.is_account(txn.account):
            raise ValueError("Cannot sign transaction without secret key")
        account_obj = self.key_manager.get_account(txn.account)
        return safe_sign_and_submit_transaction(
            txn, account_obj.wallet, self.client, autofill=True
        )

    def send_command(self, req: Request) -> dict:
        """Send the command to the rippled server"""
        return self.client.request(req)

    def request(self, req: Request) -> dict:
        """Send the command to the rippled server"""
        return self.client.request(req)

    # Need async version to close ledgers from async functions
    async def async_send_command(self, req: Request) -> dict:
        """Asynchronously send the command to the rippled server"""
        return await self.client.request_impl(req)

    def send_subscribe_command(
        self, req: Subscribe, callback: Optional[Callable[[dict], None]] = None
    ) -> dict:
        """Send the subscription command to the rippled server."""
        if not self.client.is_open():
            self.client.open()
        self.client.on("transaction", callback)
        r = self.client.request(req)
        return r.result

    def get_pids(self) -> List[int]:
        if self.network:
            return self.network.get_pids()
        if pid := self.client.get_pid():
            return [pid]

    def get_running_status(self) -> List[bool]:
        if self.network:
            return self.network.get_running_status()
        if self.client.get_pid():
            return [True]
        else:
            return [False]

    # Get a dict of the server_state, validated_ledger_seq, and complete_ledgers
    def get_brief_server_info(self) -> dict:
        if self.network:
            return self.network.get_brief_server_info()
        else:
            ret = {}
            for (k, v) in self.client.get_brief_server_info().items():
                ret[k] = [v]
            return ret

    def servers_start(
        self,
        server_indexes: Optional[Union[Set[int], List[int]]] = None,
        *,
        extra_args: Optional[List[List[str]]] = None,
    ):
        if self.network:
            return self.network.servers_start(server_indexes, extra_args=extra_args)
        else:
            raise ValueError("Cannot start stand alone server")

    def servers_stop(self, server_indexes: Optional[Union[Set[int], List[int]]] = None):
        if self.network:
            return self.network.servers_stop(server_indexes)
        else:
            raise ValueError("Cannot stop stand alone server")

    def federator_info(
        self, server_indexes: Optional[Union[Set[int], List[int]]] = None
    ):
        # key is server index. value is federator_info result
        result_dict = {}
        if self.network:
            if not server_indexes:
                server_indexes = [
                    i
                    for i in range(self.network.num_clients())
                    if self.network.is_running(i)
                ]
            for i in server_indexes:
                if self.network.is_running(i):
                    result_dict[i] = (
                        self.network.get_client(i).request(FederatorInfo()).result
                    )
        else:
            if 0 in server_indexes:
                result_dict[0] = self.client.request(FederatorInfo()).result
        return result_dict

    def __call__(
        self,
        to_send: Union[Transaction, Request, str],
        callback: Optional[Callable[[dict], None]] = None,
        *,
        insert_seq_and_fee=False,
    ) -> dict:
        """Call `send_signed` for transactions or `send_command` for commands"""
        if to_send == "open":
            self.client.open()
            return
        if isinstance(to_send, Subscribe):
            return self.send_subscribe_command(to_send, callback)
        assert callback is None
        if isinstance(to_send, Transaction):
            return self.send_signed(to_send, autofill=insert_seq_and_fee).result
        if isinstance(to_send, Request):
            return self.send_command(to_send).result
        raise ValueError(
            "Expected `to_send` to be either a Transaction, Command, or "
            "SubscriptionCommand"
        )

    def get_configs(self) -> List[str]:
        if self.network:
            return self.network.get_configs()
        return [self.client.config]

    def create_account(self, name: str) -> Account:
        """Create an account. Use the name as the alias."""
        if name == "root":
            return
        assert not self.key_manager.is_alias(name)

        account = Account.create(name)
        self.key_manager.add(account)
        return account

    def create_accounts(
        self,
        names: List[str],
        funding_account: Union[Account, str] = "root",
        amt: Amount = str(1_000_000_000),
    ) -> List[Account]:
        """Fund the accounts with nicknames 'names' by using funding account and amt"""
        accounts = [self.create_account(n) for n in names]
        if not isinstance(funding_account, Account):
            org_funding_account = funding_account
            funding_account = self.key_manager.account_from_alias(funding_account)
        if not isinstance(funding_account, Account):
            raise ValueError(f"Could not find funding account {org_funding_account}")
        if not isinstance(amt, Amount):
            assert isinstance(amt, int)
            amt = str(amt)
        for a in accounts:
            p = Payment(
                account=funding_account.account_id, destination=a.account_id, amount=amt
            )
            self.send_signed(p)
        return accounts

    def maybe_ledger_accept(self):
        if not self.standalone:
            return
        self(LedgerAccept())

    # Need async version to close ledgers from async functions
    async def async_maybe_ledger_accept(self):
        if not self.standalone:
            return
        await self.async_send_command(LedgerAccept())

    def get_balances(
        self,
        account: Union[Account, List[Account], None] = None,
        asset: Union[Amount, List[Amount]] = "0",
    ) -> pd.DataFrame:
        """
        Return a pandas dataframe of account balances. If account is None, treat as a
        wildcard (use address book)
        """
        if account is None:
            account = self.key_manager.known_accounts()
        if isinstance(account, list):
            result = [self.get_balances(acc, asset) for acc in account]
            return pd.concat(result, ignore_index=True)
        if isinstance(asset, list):
            result = [self.get_balances(account, ass) for ass in asset]
            return pd.concat(result, ignore_index=True)
        if is_xrp(asset):
            try:
                df = self.get_account_info(account)
            except:
                # Most likely the account does not exist on the ledger. Give a balance
                # of zero.
                df = pd.DataFrame(
                    {
                        "account": [account],
                        "balance": [0],
                        "flags": [0],
                        "owner_count": [0],
                        "previous_txn_id": ["NA"],
                        "previous_txn_lgr_seq": [-1],
                        "sequence": [-1],
                    }
                )
            df = df.assign(currency="XRP", peer="", limit="")
            return df.loc[:, ["account", "balance", "currency", "peer", "limit"]]
        else:
            try:
                df = self.get_trust_lines(account)
                if df.empty:
                    return df
                df = df[
                    (df["peer"] == asset.issuer) & (df["currency"] == asset.currency)
                ]
            except:
                # Most likely the account does not exist on the ledger. Return an empty
                # data frame
                df = pd.DataFrame(
                    {
                        "account": [],
                        "balance": [],
                        "currency": [],
                        "peer": [],
                        "limit": [],
                    }
                )
            return df.loc[:, ["account", "balance", "currency", "peer", "limit"]]

    def get_balance(self, account: Account, asset: IssuedCurrency) -> IssuedCurrency:
        """Get a balance from a single account in a single asset"""
        try:
            df = self.get_balances(account, asset)
            return asset(df.iloc[0]["balance"])
        except:
            return asset(0)

    def get_account_info(self, account: Optional[Account] = None) -> pd.DataFrame:
        """
        Return a pandas dataframe of account info. If account is None, treat as a
        wildcard (use address book)
        """
        if account is None:
            known_accounts = self.key_manager.known_accounts()
            result = [self.get_account_info(acc) for acc in known_accounts]
            return pd.concat(result, ignore_index=True)
        try:
            result = self.client.request(AccountInfo(account=account.account_id)).result
        except:
            # Most likely the account does not exist on the ledger. Give a balance of 0.
            return pd.DataFrame(
                {
                    "account": [account],
                    "balance": [0],
                    "flags": [0],
                    "owner_count": [0],
                    "previous_txn_id": ["NA"],
                    "previous_txn_lgr_seq": [-1],
                    "sequence": [-1],
                }
            )
        if "account_data" not in result:
            raise ValueError("Bad result from account_info command")
        info = result["account_data"]
        for dk in ["LedgerEntryType", "index"]:
            del info[dk]
        df = pd.DataFrame([info])
        df.rename(
            columns={
                "Account": "account",
                "Balance": "balance",
                "Flags": "flags",
                "OwnerCount": "owner_count",
                "PreviousTxnID": "previous_txn_id",
                "PreviousTxnLgrSeq": "previous_txn_lgr_seq",
                "Sequence": "sequence",
            },
            inplace=True,
        )
        df["balance"] = df["balance"].astype(int)
        return df

    def get_trust_lines(
        self, account: Account, peer: Optional[Account] = None
    ) -> pd.DataFrame:
        """
        Return a pandas dataframe account trust lines. If peer account is None, treat
        as a wildcard
        """
        if peer is None:
            result = self.request(AccountLines(account=account.account_id)).result
        else:
            result = self.request(
                AccountLines(account=account.account_id, peer=peer.account_id)
            ).result
        if "lines" not in result or "account" not in result:
            raise ValueError("Bad result from account_lines command")
        account = result["account"]
        lines = result["lines"]
        for d in lines:
            d["peer"] = d["account"]
            d["account"] = account
        return pd.DataFrame(lines)

    def get_offers(self, taker_pays: Amount, taker_gets: Amount) -> pd.DataFrame:
        """Return a pandas dataframe of offers"""
        result = self.request(
            BookOffers(taker_pays=taker_pays, taker_gets=taker_gets)
        ).result
        if "offers" not in result:
            raise ValueError("Bad result from book_offers command")

        offers = result["offers"]
        delete_keys = [
            "BookDirectory",
            "BookNode",
            "LedgerEntryType",
            "OwnerNode",
            "PreviousTxnID",
            "PreviousTxnLgrSeq",
            "Sequence",
            "index",
        ]
        for d in offers:
            for dk in delete_keys:
                del d[dk]
            for t in ["TakerPays", "TakerGets", "owner_funds"]:
                if "value" in d[t]:
                    d[t] = d[t]["value"]
        df = pd.DataFrame(offers)
        df.rename(
            columns={
                "Account": "account",
                "Flags": "flags",
                "TakerGets": "taker_gets",
                "TakerPays": "taker_pays",
            },
            inplace=True,
        )
        return df

    def account_balance(self, account: Account, asset: Amount) -> Amount:
        """get the account's balance of the asset"""
        # TODO: implement?
        pass

    def substitute_nicknames(
        self, df: pd.DataFrame, cols: List[str] = ["account", "peer"]
    ) -> pd.DataFrame:
        result = df.copy(deep=True)
        for c in cols:
            if c not in result:
                continue
            result[c] = result[c].map(lambda x: self.key_manager.alias_or_account_id(x))
        return result

    def add_to_keymanager(self, account: Account):
        self.key_manager.add(account)

    def is_alias(self, name: str) -> bool:
        return self.key_manager.is_alias(name)

    def account_from_alias(self, name: str) -> Account:
        return self.key_manager.account_from_alias(name)

    def known_accounts(self) -> List[Account]:
        return self.key_manager.known_accounts()

    def known_asset_aliases(self) -> List[str]:
        return self.asset_aliases.known_aliases()

    def known_iou_assets(self) -> List[IssuedCurrencyAmount]:
        return self.asset_aliases.known_assets()

    def is_asset_alias(self, name: str) -> bool:
        return self.asset_aliases.is_alias(name)

    def add_asset_alias(self, asset: IssuedCurrency, name: str):
        self.asset_aliases.add(asset, name)

    def asset_from_alias(self, name: str) -> IssuedCurrency:
        return self.asset_aliases.asset_from_alias(name)

    def insert_seq_and_fee(self, txn: Transaction):
        acc_info = self(AccountInfo(txn.account))
        # TODO: set better fee (Hard code a fee of 15 for now)
        txn.set_seq_and_fee(acc_info["account_data"]["Sequence"], 15)

    def get_client(self) -> RippleClient:
        return self.client


def balances_dataframe(
    chains: List[App],
    chain_names: List[str],
    account_ids: Optional[List[Account]] = None,
    assets: List[Amount] = None,
    in_drops: bool = False,
):
    def _removesuffix(self: str, suffix: str) -> str:
        if suffix and self.endswith(suffix):
            return self[: -len(suffix)]
        else:
            return self[:]

    def _balance_df(
        chain: App,
        acc: Optional[Account],
        asset: Union[Amount, List[Amount]],
        in_drops: bool,
    ):
        b = chain.get_balances(acc, asset)
        if not in_drops:
            b.loc[b["currency"] == "XRP", "balance"] /= 1_000_000
            b = chain.substitute_nicknames(b)
            b = b.set_index("account")
            return b

    if account_ids is None:
        account_ids = [None] * len(chains)

    if assets is None:
        # XRP and all assets in the assets alias list
        assets = [["0"] + c.known_iou_assets() for c in chains]

    dfs = []
    keys = []
    for chain, chain_name, acc, asset in zip(chains, chain_names, account_ids, assets):
        dfs.append(_balance_df(chain, acc, asset, in_drops))
        keys.append(_removesuffix(chain_name, "chain"))
    df = pd.concat(dfs, keys=keys)
    return df


# Start an app with a single client
@contextmanager
def single_client_app(
    *,
    config: ConfigFile,
    command_log: Optional[str] = None,
    server_out=os.devnull,
    run_server: bool = True,
    exe: Optional[str] = None,
    extra_args: Optional[List[str]] = None,
    standalone=False,
):
    """Start a ripple server and return an app"""
    try:
        if extra_args is None:
            extra_args = []
        to_run = None
        app = None
        client = RippleClient(config=config, command_log=command_log, exe=exe)
        if run_server:
            to_run = [client.exe, "--conf", client.config_file_name]
            if standalone:
                to_run.append("-a")
            fout = open(server_out, "w")
            p = subprocess.Popen(
                to_run + extra_args, stdout=fout, stderr=subprocess.STDOUT
            )
            client.set_pid(p.pid)
            print(
                f"started rippled: config: {client.config_file_name} PID: {p.pid}",
                flush=True,
            )
            time.sleep(1.5)  # give process time to startup

        app = App(client=client, standalone=standalone)
        yield app
    finally:
        if app:
            app.shutdown()
        if run_server and to_run:
            subprocess.Popen(to_run + ["stop"], stdout=fout, stderr=subprocess.STDOUT)
            p.wait()


def configs_for_testnet(config_file_prefix: str) -> List[ConfigFile]:
    p = Path(config_file_prefix)
    dir = p.parent
    file = p.name
    file_names = []
    for f in os.listdir(dir):
        cfg = os.path.join(dir, f, "rippled.cfg")
        if f.startswith(file) and os.path.exists(cfg):
            file_names.append(cfg)
    file_names.sort()
    return [ConfigFile(file_name=f) for f in file_names]


# Start an app for a network with the config files matched by
# `config_file_prefix*/rippled.cfg`
@contextmanager
def testnet_app(
    *,
    exe: str,
    configs: List[ConfigFile],
    command_logs: Optional[List[str]] = None,
    run_server: Optional[List[bool]] = None,
    extra_args: Optional[List[List[str]]] = None,
):
    """Start a ripple testnet and return an app"""
    try:
        app = None
        network = testnet.Network(
            exe,
            configs,
            command_logs=command_logs,
            run_server=run_server,
            extra_args=extra_args,
        )
        network.wait_for_validated_ledger()
        app = App(network=network, standalone=False)
        yield app
    finally:
        if app:
            app.shutdown()
