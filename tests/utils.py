import logging
import pprint
import time
from contextlib import contextmanager
from typing import Optional

from tabulate import tabulate
from xrpl.clients import JsonRpcClient
from xrpl.models import XRP, AccountTx, Amount, IssuedCurrencyAmount
from xrpl.wallet import Wallet, generate_faucet_wallet

from slk.chain.chain import Chain
from slk.classes.account import Account
from slk.repl.repl_functionality import get_balances_data


def wait_for_balance_change(
    chain: Chain, acc: Account, pre_balance: Amount, final_diff: Optional[Amount] = None
):
    logging.info(
        f"waiting for balance change {acc.account_id = } {pre_balance = } "
        f"{final_diff = }"
    )
    for i in range(30):
        currency = XRP() if isinstance(pre_balance, str) else pre_balance
        new_bal = currency.to_amount(chain.get_balance(acc, currency))
        diff = value_diff(new_bal, pre_balance)
        if new_bal != pre_balance:
            logging.info(
                f"Balance changed {acc.account_id = } {pre_balance = } {new_bal = } "
                f"{diff = } {final_diff = }"
            )
            if final_diff is None or diff == final_diff:
                return
        chain.maybe_ledger_accept()
        time.sleep(2)
        if i > 0 and not (i % 5):
            logging.warning(
                f"Waiting for balance to change {acc.account_id = } {pre_balance = }"
            )
    logging.error(
        f"Expected balance to change {acc.account_id = } {pre_balance = } {new_bal = } "
        f"{diff = } {final_diff = } {acc.nickname = }"
    )
    raise ValueError(
        f"Expected balance to change {acc.account_id = } {pre_balance = } {new_bal = } "
        f"{diff = } {final_diff = } {acc.nickname = }"
    )


def log_chain_state(mc_chain, sc_chain, log, msg="Chain State"):
    chains = [mc_chain, sc_chain]
    chain_names = ["mainchain", "sidechain"]
    balances = get_balances_data(chains, chain_names)
    data_as_str = tabulate(
        balances,
        headers="keys",
        tablefmt="presto",
        floatfmt=",.6f",
        numalign="right",
    )
    log(f"{msg} Balances: \n{data_as_str}")
    federator_info = sc_chain.federator_info()
    log(f"{msg} Federator Info: \n{pprint.pformat(federator_info)}")
    side_door = sc_chain.account_from_alias("door")
    door_account_tx = sc_chain.request(AccountTx(account=side_door.account_id))
    log(f"{msg} Side Door Txs: \n{pprint.pformat(door_account_tx)}")


def value_diff(bigger: Amount, smaller: Amount) -> Amount:
    if isinstance(bigger, str):
        assert isinstance(smaller, str)
        return str(int(bigger) - int(smaller))
    else:
        assert isinstance(smaller, IssuedCurrencyAmount)
        assert bigger.issuer == smaller.issuer
        assert bigger.currency == smaller.currency
        return bigger.to_amount(int(bigger.value) - int(smaller.value))


# Tests can set this to True to help debug test failures by showing account
# balances in the log before the test runs
test_context_verbose_logging = False


def set_test_context_verbose_logging(new_val: bool) -> None:
    global test_context_verbose_logging
    test_context_verbose_logging = new_val


def generate_mainchain_account(url: str, wallet: Wallet) -> None:
    if "34.83.125.234" in url:  # devnet
        new_client = JsonRpcClient("https://s.devnet.rippletest.net:51234")
        generate_faucet_wallet(new_client, wallet)
    else:
        raise Exception(f"Unknown mainnet: {url}")


@contextmanager
def tst_context(mc_chain, sc_chain, verbose_logging: Optional[bool] = None):
    """Write extra context info to the log on test failure"""
    global test_context_verbose_logging
    if verbose_logging is None:
        verbose_logging = test_context_verbose_logging
    if verbose_logging:
        log_chain_state(mc_chain, sc_chain, logging.info)
    start_time = time.monotonic()
    try:
        yield
    except:
        log_chain_state(mc_chain, sc_chain, logging.error)
        raise
    finally:
        elapsed_time = time.monotonic() - start_time
        logging.info(f"Test elapsed time: {elapsed_time}")
    if verbose_logging:
        log_chain_state(mc_chain, sc_chain, logging.info)
