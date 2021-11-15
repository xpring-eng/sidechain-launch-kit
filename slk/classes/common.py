from __future__ import annotations

import binascii
import sys
from typing import Any, Type

from xrpl.wallet import Wallet

EPRINT_ENABLED = True


def disable_eprint() -> None:
    global EPRINT_ENABLED
    EPRINT_ENABLED = False


def enable_eprint() -> None:
    global EPRINT_ENABLED
    EPRINT_ENABLED = True


def eprint(*args: Any, **kwargs: Any) -> None:
    if not EPRINT_ENABLED:
        return
    print(*args, file=sys.stderr, flush=True, **kwargs)


class Account:
    """Account in the XRPL"""

    def __init__(self: Account, *, account_id: str, nickname: str, seed: str) -> None:
        self.account_id = account_id
        self.nickname = nickname
        self.seed = seed

        self.wallet = Wallet(seed, 0)

    @classmethod
    def create(cls: Type[Account], name: str) -> Account:
        wallet = Wallet.create()
        return Account(
            account_id=wallet.classic_address,
            nickname=name,
            seed=wallet.seed,
        )

    # Accounts are equal if they represent the same account on the ledger
    # I.e. only check the account_id field for equality.
    def __eq__(self: Account, lhs: Any) -> bool:
        if not isinstance(lhs, self.__class__):
            return False
        return self.account_id == lhs.account_id

    def __ne__(self: Account, lhs: Any) -> bool:
        return not self.__eq__(lhs)

    def __str__(self: Account) -> str:
        if self.nickname is not None:
            return self.nickname
        return self.account_id

    def account_id_str_as_hex(self: Account) -> str:
        return binascii.hexlify(self.account_id.encode()).decode("utf-8")
