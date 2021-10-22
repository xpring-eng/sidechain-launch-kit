import binascii
import datetime
from typing import List, Optional, Union
import pandas as pd
import pytz
import sys

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
                 secret_key: Optional[str] = None,
                 result_dict: Optional[dict] = None):
        self.account_id = account_id
        self.nickname = nickname
        self.public_key = public_key
        self.public_key_hex = public_key_hex
        self.secret_key = secret_key

        if result_dict is not None:
            self.account_id = result_dict['account_id']
            self.public_key = result_dict['public_key']
            self.public_key_hex = result_dict['public_key_hex']
            self.secret_key = result_dict['master_key']

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
