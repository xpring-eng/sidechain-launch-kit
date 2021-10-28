import sys
import time
from multiprocessing import Process, Value
from typing import Dict

from xrpl.models import IssuedCurrencyAmount, Payment, TrustSet
from xrpl.utils import xrp_to_drops

import slk.sidechain as sidechain
from slk.app import App
from slk.common import disable_eprint, eprint, same_amount_new_value
from slk.sidechain import Params
from tests.utils import (
    mc_connect_subscription,
    sc_connect_subscription,
    set_test_context_verbose_logging,
    tst_context,
    wait_for_balance_change,
)


def simple_xrp_test(mc_app: App, sc_app: App, params: Params):
    alice = mc_app.account_from_alias("alice")
    adam = sc_app.account_from_alias("adam")

    # main to side
    # First txn funds the side chain account
    with tst_context(mc_app, sc_app):
        to_send_asset = xrp_to_drops(1000)
        pre_bal = sc_app.get_balance(adam, to_send_asset)
        sidechain.main_to_side_transfer(
            mc_app, sc_app, alice, adam, to_send_asset, params
        )
        wait_for_balance_change(sc_app, adam, pre_bal, to_send_asset)

    for i in range(2):
        # even amounts for main to side
        for value in range(10, 20, 2):
            with tst_context(mc_app, sc_app):
                to_send_asset = xrp_to_drops(value)
                pre_bal = sc_app.get_balance(adam, to_send_asset)
                sidechain.main_to_side_transfer(
                    mc_app, sc_app, alice, adam, to_send_asset, params
                )
                wait_for_balance_change(sc_app, adam, pre_bal, to_send_asset)

        # side to main
        # odd amounts for side to main
        for value in range(9, 19, 2):
            with tst_context(mc_app, sc_app):
                to_send_asset = xrp_to_drops(value)
                pre_bal = mc_app.get_balance(alice, to_send_asset)
                sidechain.side_to_main_transfer(
                    mc_app, sc_app, adam, alice, to_send_asset, params
                )
                wait_for_balance_change(mc_app, alice, pre_bal, to_send_asset)


def simple_iou_test(mc_app: App, sc_app: App, params: Params):
    alice = mc_app.account_from_alias("alice")
    adam = sc_app.account_from_alias("adam")

    mc_asset = IssuedCurrencyAmount(
        value="0", currency="USD", issuer=mc_app.account_from_alias("root").account_id
    )
    sc_asset = IssuedCurrencyAmount(
        value="0", currency="USD", issuer=sc_app.account_from_alias("door").account_id
    )
    mc_app.add_asset_alias(mc_asset, "mcd")  # main chain dollar
    sc_app.add_asset_alias(sc_asset, "scd")  # side chain dollar
    mc_app(
        TrustSet(
            account=alice.account_id,
            limit_amount=same_amount_new_value(mc_asset, 1_000_000),
        )
    )

    # make sure adam account on the side chain exists and set the trust line
    with tst_context(mc_app, sc_app):
        sidechain.main_to_side_transfer(
            mc_app, sc_app, alice, adam, xrp_to_drops(300), params
        )

    # create a trust line to alice and pay her USD/root
    mc_app(
        TrustSet(
            account=alice.account_id,
            limit_amount=same_amount_new_value(mc_asset, 1_000_000),
        )
    )
    mc_app.maybe_ledger_accept()
    mc_app(
        Payment(
            account=mc_app.account_from_alias("root").account_id,
            destination=alice.account_id,
            amount=same_amount_new_value(mc_asset, 10_000),
        )
    )
    mc_app.maybe_ledger_accept()

    # create a trust line for adam
    sc_app(
        TrustSet(
            account=adam.account_id,
            limit_amount=same_amount_new_value(sc_asset, 1_000_000),
        )
    )

    for i in range(2):
        # even amounts for main to side
        for value in range(10, 20, 2):
            with tst_context(mc_app, sc_app):
                to_send_asset = same_amount_new_value(mc_asset, value)
                rcv_asset = same_amount_new_value(sc_asset, value)
                pre_bal = same_amount_new_value(
                    sc_asset, sc_app.get_balance(adam, rcv_asset)
                )
                print("IN IOU TESTINGGGGGG", to_send_asset, rcv_asset, pre_bal)
                sidechain.main_to_side_transfer(
                    mc_app, sc_app, alice, adam, to_send_asset, params
                )
                wait_for_balance_change(sc_app, adam, pre_bal, rcv_asset)

        # side to main
        # odd amounts for side to main
        for value in range(9, 19, 2):
            with tst_context(mc_app, sc_app):
                to_send_asset = same_amount_new_value(sc_asset, value)
                rcv_asset = same_amount_new_value(mc_asset, value)
                pre_bal = same_amount_new_value(
                    to_send_asset, mc_app.get_balance(alice, to_send_asset)
                )
                sidechain.side_to_main_transfer(
                    mc_app, sc_app, adam, alice, to_send_asset, params
                )
                wait_for_balance_change(mc_app, alice, pre_bal, rcv_asset)


def run(mc_app: App, sc_app: App, params: Params):
    # process will run while stop token is non-zero
    stop_token = Value("i", 1)
    p = None
    if mc_app.standalone:
        p = Process(target=sidechain.close_mainchain_ledgers, args=(stop_token, params))
        p.start()
    try:
        # TODO: Tests fail without this sleep. Fix this bug.
        time.sleep(10)
        setup_accounts(mc_app, sc_app, params)
        simple_xrp_test(mc_app, sc_app, params)
        simple_iou_test(mc_app, sc_app, params)
    finally:
        if p:
            stop_token.value = 0
            p.join()
        sidechain._convert_log_files_to_json(
            mc_app.get_configs() + sc_app.get_configs(), "final.json"
        )


def standalone_test(params: Params):
    def callback(mc_app: App, sc_app: App):
        mc_connect_subscription(mc_app, params.mc_door_account)
        sc_connect_subscription(sc_app, params.sc_door_account)
        run(mc_app, sc_app, params)

    sidechain._standalone_with_callback(params, callback, setup_user_accounts=False)


def setup_accounts(mc_app: App, sc_app: App, params: Params):
    # Setup a funded user account on the main chain, and add an unfunded account.
    # Setup address book and add a funded account on the mainchain.
    # Typical female names are addresses on the mainchain.
    # The first account is funded.
    alice = mc_app.create_account("alice")
    mc_app.create_account("beth")
    mc_app.create_account("carol")
    mc_app.create_account("deb")
    mc_app.create_account("ella")
    mc_app(
        Payment(
            account=params.genesis_account.account_id,
            destination=alice.account_id,
            amount=xrp_to_drops(20_000),
        )
    )
    mc_app.maybe_ledger_accept()

    # Typical male names are addresses on the sidechain.
    # All accounts are initially unfunded
    sc_app.create_account("adam")
    sc_app.create_account("bob")
    sc_app.create_account("charlie")
    sc_app.create_account("dan")
    sc_app.create_account("ed")


def multinode_test(params: Params):
    def callback(mc_app: App, sc_app: App):
        mc_connect_subscription(mc_app, params.mc_door_account)
        sc_connect_subscription(sc_app, params.sc_door_account)
        run(mc_app, sc_app, params)

    sidechain._multinode_with_callback(params, callback, setup_user_accounts=False)


def test_simple_xchain(configs_dirs_dict: Dict[int, str]):
    params = sidechain.Params(configs_dir=configs_dirs_dict[1])

    if err_str := params.check_error():
        eprint(err_str)
        sys.exit(1)

    if params.verbose:
        print("eprint enabled")
    else:
        disable_eprint()

    # Set to true to help debug tests
    set_test_context_verbose_logging(True)

    if params.standalone:
        standalone_test(params)
    else:
        multinode_test(params)
