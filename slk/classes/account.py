"""Representation of an account in the XRPL."""

from __future__ import annotations

import binascii
from typing import Any, Type

from xrpl.wallet import Wallet


class Account:
    """Representation of an account in the XRPL."""

    def __init__(self: Account, *, account_id: str, nickname: str, seed: str) -> None:
        """
        Initialize an account.

        Args:
            account_id: The account address.
            nickname: The shortened nickname for the account.
            seed: The seed for the wallet for the account.
        """
        # TODO: refactor so account_id is pulled from the wallet instead of separately
        # stored
        self.account_id = account_id
        self.nickname = nickname
        self.seed = seed

        self.wallet = Wallet(seed, 0)

    @classmethod
    def from_seed(cls: Type[Account], name: str, seed: str) -> Account:
        """
        Create an account from a seed.

        Args:
            name: The nickname of the account.
            seed: The seed of the account.

        Returns:
            The Account that corresponds to the provided information.
        """
        wallet = Wallet(seed, 0)

        return Account(
            account_id=wallet.classic_address,
            nickname=name,
            seed=wallet.seed,
        )

    @classmethod
    def create(cls: Type[Account], name: str) -> Account:
        """
        Create a new account with a new set of keys.

        Args:
            name: Nickname of the account to create.

        Returns:
            The created account.
        """
        wallet = Wallet.create()
        return Account(
            account_id=wallet.classic_address,
            nickname=name,
            seed=wallet.seed,
        )

    # Accounts are equal if they represent the same account on the ledger
    # I.e. only check the account_id field for equality.
    def __eq__(self: Account, lhs: Any) -> bool:
        """
        Returns whether an Account and something else are equal.

        Accounts are equal if they represent the same account on the ledger,
        i.e. only check the account_id field for equality.

        Args:
            lhs: The object with which to compare for equality.

        Returns:
            Whether the two accounts are equal.
        """
        if not isinstance(lhs, self.__class__):
            return False
        return self.account_id == lhs.account_id

    def __ne__(self: Account, lhs: Any) -> bool:
        """
        Returns whether an Account and something else are not equal.

        Accounts are equal if they represent the same account on the ledger
        I.e. only check the account_id field for equality.

        Args:
            lhs: The object with which to compare for equality.

        Returns:
            Whether the two accounts are not equal.
        """
        return not self == lhs

    def __str__(self: Account) -> str:
        """
        Get a string representation of an Account.

        Returns:
            A string representation of the Account.
        """
        if self.nickname is not None:
            return self.nickname
        return self.account_id

    def account_id_str_as_hex(self: Account) -> str:
        """
        Get the account ID in hex (for cross-chain payments).

        Returns:
            The account ID in hex form.
        """
        return binascii.hexlify(self.account_id.encode()).decode("utf-8")
