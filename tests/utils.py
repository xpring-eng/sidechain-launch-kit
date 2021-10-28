import json
import logging
import pprint
import time
from contextlib import contextmanager
from typing import Optional

from xrpl.models import Amount, IssuedCurrencyAmount, Subscribe

from slk.app import App, balances_dataframe
from slk.common import Account, same_amount_new_value

MC_SUBSCRIBE_QUEUE = []
SC_SUBSCRIBE_QUEUE = []


def _mc_subscribe_callback(v: dict):
    MC_SUBSCRIBE_QUEUE.append(v)
    logging.info(f"mc subscribe_callback:\n{json.dumps(v, indent=1)}")


def _sc_subscribe_callback(v: dict):
    SC_SUBSCRIBE_QUEUE.append(v)
    logging.info(f"sc subscribe_callback:\n{json.dumps(v, indent=1)}")


def mc_connect_subscription(app: App, door_account: Account):
    app(Subscribe(accounts=[door_account.account_id]), _mc_subscribe_callback)


def sc_connect_subscription(app: App, door_account: Account):
    app(Subscribe(accounts=[door_account.account_id]), _sc_subscribe_callback)


def wait_for_balance_change(
    app: App, acc: Account, pre_balance: Amount, final_diff: Optional[Amount] = None
):
    logging.info(
        f"waiting for balance change {acc.account_id = } {pre_balance = } "
        f"{final_diff = }"
    )
    for i in range(30):
        new_bal = same_amount_new_value(
            pre_balance, app.get_balance(acc, same_amount_new_value(pre_balance, 0))
        )
        diff = value_diff(new_bal, pre_balance)
        if new_bal != pre_balance:
            logging.info(
                f"Balance changed {acc.account_id = } {pre_balance = } {new_bal = } "
                f"{diff = } {final_diff = }"
            )
            if final_diff is None or diff == final_diff:
                return
        app.maybe_ledger_accept()
        time.sleep(2)
        if i > 0 and not (i % 5):
            logging.warning(
                f"Waiting for balance to change {acc.account_id = } {pre_balance = }"
            )
    logging.error(
        f"Expected balance to change {acc.account_id = } {pre_balance = } {new_bal = } "
        f"{diff = } {final_diff = }"
    )
    raise ValueError(
        f"Expected balance to change {acc.account_id = } {pre_balance = } {new_bal = } "
        f"{diff = } {final_diff = }"
    )


def log_chain_state(mc_app, sc_app, log, msg="Chain State"):
    chains = [mc_app, sc_app]
    chain_names = ["mainchain", "sidechain"]
    balances = balances_dataframe(chains, chain_names)
    df_as_str = balances.to_string(float_format=lambda x: f"{x:,.6f}")
    log(f"{msg} Balances: \n{df_as_str}")
    federator_info = sc_app.federator_info()
    log(f"{msg} Federator Info: \n{pprint.pformat(federator_info)}")


def value_diff(bigger: Amount, smaller: Amount) -> Amount:
    if isinstance(bigger, str):
        assert isinstance(smaller, str)
        return str(int(bigger) - int(smaller))
    else:
        assert bigger.issuer == smaller.issuer
        assert bigger.currency == smaller.currency
        return IssuedCurrencyAmount(
            value=str(int(bigger.value) - int(smaller.value)),
            issuer=bigger.issuer,
            currency=bigger.currency,
        )


# Tests can set this to True to help debug test failures by showing account
# balances in the log before the test runs
test_context_verbose_logging = False


def set_test_context_verbose_logging(new_val: bool) -> None:
    global test_context_verbose_logging
    test_context_verbose_logging = new_val


@contextmanager
def tst_context(mc_app, sc_app, verbose_logging: Optional[bool] = None):
    """Write extra context info to the log on test failure"""
    global test_context_verbose_logging
    if verbose_logging is None:
        verbose_logging = test_context_verbose_logging
    try:
        if verbose_logging:
            log_chain_state(mc_app, sc_app, logging.info)
        start_time = time.monotonic()
        yield
    except:
        log_chain_state(mc_app, sc_app, logging.error)
        raise
    finally:
        elapased_time = time.monotonic() - start_time
        logging.info(f"Test elapsed time: {elapased_time}")
    if verbose_logging:
        log_chain_state(mc_app, sc_app, logging.info)