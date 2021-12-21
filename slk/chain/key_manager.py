"""A class that stores account information in easily-accessible ways."""

from __future__ import annotations

from typing import Dict, List, Optional, Union

from tabulate import tabulate

from slk.classes.account import Account


class KeyManager:
    """A class that stores account information in easily-accessible ways."""

    def __init__(self: KeyManager) -> None:
        """Initialize a KeyManager."""
        self._aliases: Dict[str, Account] = {}  # alias -> account
        self._accounts: Dict[str, Account] = {}  # account id -> account

    def add(self: KeyManager, account: Account) -> None:
        """
        Add an account with the given name.

        Args:
            account: The account to add to the key manager.
        """
        self._aliases[account.nickname] = account
        self._accounts[account.account_id] = account

    def is_alias(self: KeyManager, name: str) -> bool:
        """
        Determine whether an account name is a known account.

        Args:
            name: The nickname to check.

        Returns:
            Whether the name is an account in the key manager.
        """
        return name in self._aliases

    def is_account(self: KeyManager, account: str) -> bool:
        """
        Determine whether an account is a known account.

        Args:
            account: The account to check.

        Returns:
            Whether the account is a known account.
        """
        return account in self._accounts

    def account_from_alias(self: KeyManager, name: str) -> Account:
        """
        Get the account information for a given alias.

        Args:
            name: The alias for which to get account info.

        Returns:
            The Account that maps to the provided name.
        """
        assert name in self._aliases
        return self._aliases[name]

    def known_accounts(self: KeyManager) -> List[Account]:
        """
        Return a list of all known accounts.

        Returns:
            A list of all known accounts.
        """
        return list(self._accounts.values())

    def get_account(self: KeyManager, account: str) -> Account:
        """
        Get the account information for a given account id.

        Args:
            account: The account ID for which to get information.

        Returns:
            The Account that the account ID belongs to.
        """
        return self._accounts[account]

    def alias_or_account_id(self: KeyManager, account_id: Union[Account, str]) -> str:
        """
        Return the alias if it exists, otherwise return the id.

        Args:
            account_id: An account ID or account.

        Returns:
            The nickname associated with the account, if it exists. Otherwise, returns
            the ID.
        """
        if isinstance(account_id, Account):
            return account_id.nickname

        if account_id in self._accounts:
            return self._accounts[account_id].nickname
        return account_id

    def alias_to_account_id(self: KeyManager, alias: str) -> Optional[str]:
        """
        Get the account id for a given alias.

        Args:
            alias: The alias to convert to an account ID.

        Returns:
            An account ID, if the alias exists. If not, returns None.
        """
        if alias in self._aliases:
            return self._aliases[alias].account_id
        return None

    def to_string(self: KeyManager, nickname: Optional[str] = None) -> str:
        """
        Return a string representation of the accounts.

        Args:
            nickname: [Optional] the nickname to get account ID.

        Returns:
            The string form of the key manager.
        """
        # TODO: use alias_to_account_id instead of to_string(nickname)
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
