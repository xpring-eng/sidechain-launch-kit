import binascii
import datetime
from typing import Any, List, Optional, Union
import pandas as pd
import pytz
import sys

from xrpl.wallet import Wallet

EPRINT_ENABLED = True


def disable_eprint():
    global EPRINT_ENABLED
    EPRINT_ENABLED = False


def enable_eprint():
    global EPRINT_ENABLED
    EPRINT_ENABLED = True


def eprint(*args, **kwargs):
    if not EPRINT_ENABLED:
        return
    print(*args, file=sys.stderr, flush=True, **kwargs)


class Account:  # pylint: disable=too-few-public-methods
    '''
    Account in the ripple ledger
    '''
    def __init__(self,
                 *,
                 account_id: Optional[str] = None,
                 nickname: Optional[str] = None,
                 public_key: Optional[str] = None,
                 public_key_hex: Optional[str] = None,
                 secret_key: Optional[str] = None):
        self.account_id = account_id
        self.nickname = nickname
        self.secret_key = secret_key
        
        self.wallet = Wallet(secret_key, 0)

    # TODO: fix type here
    def create(cls: Any, name: str):
        wallet = Wallet.create()
        return Account(
            account_id=wallet.classic_address,
            nickname=name,
            public_key=wallet.public_key,
            secret_key=wallet.private_key
        )

    # Accounts are equal if they represent the same account on the ledger
    # I.e. only check the account_id field for equality.
    def __eq__(self, lhs):
        if not isinstance(lhs, self.__class__):
            return False
        return self.account_id == lhs.account_id

    def __ne__(self, lhs):
        return not self.__eq__(lhs)

    def __str__(self) -> str:
        if self.nickname is not None:
            return self.nickname
        return self.account_id

    def alias_or_account_id(self) -> str:
        '''
        return the alias if it exists, otherwise return the id
        '''
        if self.nickname is not None:
            return self.nickname
        return self.account_id

    def account_id_str_as_hex(self) -> str:
        return binascii.hexlify(self.account_id.encode()).decode('utf-8')

    def to_cmd_obj(self) -> dict:
        return {
            'account_id': self.account_id,
            'nickname': self.nickname,
            'public_key': self.public_key,
            'public_key_hex': self.public_key_hex,
            'secret_key': self.secret_key
        }
