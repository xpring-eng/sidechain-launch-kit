from __future__ import annotations

from typing import Dict, List, Optional, Union

from tabulate import tabulate

from slk.classes.account import Account


class KeyManager:
    def __init__(self: KeyManager) -> None:
        self._aliases: Dict[str, Account] = {}  # alias -> account
        self._accounts: Dict[str, Account] = {}  # account id -> account

    def add(self: KeyManager, account: Account) -> None:
        self._aliases[account.nickname] = account
        self._accounts[account.account_id] = account

    def is_alias(self: KeyManager, name: str) -> bool:
        return name in self._aliases

    def is_account(self: KeyManager, account: str) -> bool:
        return account in self._accounts

    def account_from_alias(self: KeyManager, name: str) -> Account:
        assert name in self._aliases
        return self._aliases[name]

    def known_accounts(self: KeyManager) -> List[Account]:
        return list(self._accounts.values())

    def get_account(self: KeyManager, account: str) -> Account:
        return self._accounts[account]

    def account_id_dict(self: KeyManager) -> Dict[str, Account]:
        return self._accounts

    def alias_or_account_id(self: KeyManager, account_id: Union[Account, str]) -> str:
        """return the alias if it exists, otherwise return the id"""
        if isinstance(account_id, Account):
            return account_id.nickname

        if account_id in self._accounts:
            return self._accounts[account_id].nickname
        return account_id

    def alias_to_account_id(self: KeyManager, alias: str) -> Optional[str]:
        if alias in self._aliases:
            return self._aliases[alias].account_id
        return None

    def to_string(self: KeyManager, nickname: Optional[str] = None) -> str:
        data = []
        if nickname is not None:
            if nickname in self._aliases:
                account_id = self._aliases[nickname].account_id
            else:
                account_id = "NA"
            data.append(
                {
                    "name": nickname,
                    "address": account_id,
                }
            )
        else:
            for (k, v) in self._aliases.items():
                data.append(
                    {
                        "name": k,
                        "address": v.account_id,
                    }
                )
        return tabulate(
            data,
            headers="keys",
            tablefmt="presto",
        )
