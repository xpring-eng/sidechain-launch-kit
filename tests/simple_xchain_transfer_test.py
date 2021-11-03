import sys
import time
from multiprocessing import Process, Value
from typing import Dict

from xrpl.models import IssuedCurrencyAmount, Payment, TrustSet
from xrpl.utils import xrp_to_drops

from slk.chain import Chain
from slk.common import disable_eprint, eprint, same_amount_new_value
from slk.sidechain import (
    _convert_log_files_to_json,
    _multinode_with_callback,
    _standalone_with_callback,
    close_mainchain_ledgers,
)
from slk.sidechain_params import SidechainParams
from slk.xchain_transfer import main_to_side_transfer, side_to_main_transfer
from tests.utils import (
    mc_connect_subscription,
    sc_connect_subscription,
    set_test_context_verbose_logging,
    tst_context,
    wait_for_balance_change,
)


def simple_xrp_test(mc_chain: Chain, sc_chain: Chain, params: SidechainParams):
    alice = mc_chain.account_from_alias("alice")
    adam = sc_chain.account_from_alias("adam")

    # main to side
    # First txn funds the side chain account
    with tst_context(mc_chain, sc_chain):
        to_send_asset = xrp_to_drops(1000)
        pre_bal = sc_chain.get_balance(adam, to_send_asset)
        main_to_side_transfer(mc_chain, sc_chain, alice, adam, to_send_asset, params)
        wait_for_balance_change(sc_chain, adam, pre_bal, to_send_asset)

    for i in range(2):
        # even amounts for main to side
        for value in range(10, 20, 2):
            with tst_context(mc_chain, sc_chain):
                to_send_asset = xrp_to_drops(value)
                pre_bal = sc_chain.get_balance(adam, to_send_asset)
                main_to_side_transfer(
                    mc_chain, sc_chain, alice, adam, to_send_asset, params
                )
                wait_for_balance_change(sc_chain, adam, pre_bal, to_send_asset)

        # side to main
        # odd amounts for side to main
        for value in range(9, 19, 2):
            with tst_context(mc_chain, sc_chain):
                to_send_asset = xrp_to_drops(value)
                pre_bal = mc_chain.get_balance(alice, to_send_asset)
                side_to_main_transfer(
                    mc_chain, sc_chain, adam, alice, to_send_asset, params
                )
                wait_for_balance_change(mc_chain, alice, pre_bal, to_send_asset)


def simple_iou_test(mc_chain: Chain, sc_chain: Chain, params: SidechainParams):
    alice = mc_chain.account_from_alias("alice")
    adam = sc_chain.account_from_alias("adam")

    mc_asset = IssuedCurrencyAmount(
        value="0", currency="USD", issuer=mc_chain.account_from_alias("root").account_id
    )
    sc_asset = IssuedCurrencyAmount(
        value="0", currency="USD", issuer=sc_chain.account_from_alias("door").account_id
    )
    mc_chain.add_asset_alias(mc_asset, "mcd")  # main chain dollar
    sc_chain.add_asset_alias(sc_asset, "scd")  # side chain dollar
    mc_chain(
        TrustSet(
            account=alice.account_id,
            limit_amount=same_amount_new_value(mc_asset, 1_000_000),
        )
    )

    # make sure adam account on the side chain exists and set the trust line
    with tst_context(mc_chain, sc_chain):
        main_to_side_transfer(
            mc_chain, sc_chain, alice, adam, xrp_to_drops(300), params
        )

    # create a trust line to alice and pay her USD/root
    mc_chain(
        TrustSet(
            account=alice.account_id,
            limit_amount=same_amount_new_value(mc_asset, 1_000_000),
        )
    )
    mc_chain.maybe_ledger_accept()
    mc_chain(
        Payment(
            account=mc_chain.account_from_alias("root").account_id,
            destination=alice.account_id,
            amount=same_amount_new_value(mc_asset, 10_000),
        )
    )
    mc_chain.maybe_ledger_accept()

    # create a trust line for adam
    sc_chain(
        TrustSet(
            account=adam.account_id,
            limit_amount=same_amount_new_value(sc_asset, 1_000_000),
        )
    )

    for i in range(2):
        # even amounts for main to side
        for value in range(10, 20, 2):
            with tst_context(mc_chain, sc_chain):
                to_send_asset = same_amount_new_value(mc_asset, value)
                rcv_asset = same_amount_new_value(sc_asset, value)
                pre_bal = same_amount_new_value(
                    sc_asset, sc_chain.get_balance(adam, rcv_asset)
                )
                print("IN IOU TESTINGGGGGG", to_send_asset, rcv_asset, pre_bal)
                main_to_side_transfer(
                    mc_chain, sc_chain, alice, adam, to_send_asset, params
                )
                wait_for_balance_change(sc_chain, adam, pre_bal, rcv_asset)

        # side to main
        # odd amounts for side to main
        for value in range(9, 19, 2):
            with tst_context(mc_chain, sc_chain):
                to_send_asset = same_amount_new_value(sc_asset, value)
                rcv_asset = same_amount_new_value(mc_asset, value)
                pre_bal = same_amount_new_value(
                    to_send_asset, mc_chain.get_balance(alice, to_send_asset)
                )
                side_to_main_transfer(
                    mc_chain, sc_chain, adam, alice, to_send_asset, params
                )
                wait_for_balance_change(mc_chain, alice, pre_bal, rcv_asset)


def run(mc_chain: Chain, sc_chain: Chain, params: SidechainParams):
    # process will run while stop token is non-zero
    stop_token = Value("i", 1)
    p = None
    if mc_chain.standalone:
        p = Process(target=close_mainchain_ledgers, args=(stop_token, params))
        p.start()
    try:
        # TODO: Tests fail without this sleep. Fix this bug.
        time.sleep(10)
        setup_accounts(mc_chain, sc_chain, params)
        simple_xrp_test(mc_chain, sc_chain, params)
        simple_iou_test(mc_chain, sc_chain, params)
    finally:
        if p:
            stop_token.value = 0
            p.join()
        _convert_log_files_to_json(
            mc_chain.get_configs() + sc_chain.get_configs(), "final.json"
        )


def standalone_test(params: SidechainParams):
    def callback(mc_chain: Chain, sc_chain: Chain):
        mc_connect_subscription(mc_chain, params.mc_door_account)
        sc_connect_subscription(sc_chain, params.sc_door_account)
        run(mc_chain, sc_chain, params)

    _standalone_with_callback(params, callback, setup_user_accounts=False)


def setup_accounts(mc_chain: Chain, sc_chain: Chain, params: SidechainParams):
    # Setup a funded user account on the main chain, and add an unfunded account.
    # Setup address book and add a funded account on the mainchain.
    # Typical female names are addresses on the mainchain.
    # The first account is funded.
    alice = mc_chain.create_account("alice")
    mc_chain.create_account("beth")
    mc_chain.create_account("carol")
    mc_chain.create_account("deb")
    mc_chain.create_account("ella")
    mc_chain(
        Payment(
            account=params.genesis_account.account_id,
            destination=alice.account_id,
            amount=xrp_to_drops(20_000),
        )
    )
    mc_chain.maybe_ledger_accept()

    # Typical male names are addresses on the sidechain.
    # All accounts are initially unfunded
    sc_chain.create_account("adam")
    sc_chain.create_account("bob")
    sc_chain.create_account("charlie")
    sc_chain.create_account("dan")
    sc_chain.create_account("ed")


def multinode_test(params: SidechainParams):
    def callback(mc_chain: Chain, sc_chain: Chain):
        mc_connect_subscription(mc_chain, params.mc_door_account)
        sc_connect_subscription(sc_chain, params.sc_door_account)
        run(mc_chain, sc_chain, params)

    _multinode_with_callback(params, callback, setup_user_accounts=False)


def test_simple_xchain(configs_dirs_dict: Dict[int, str]):
    try:
        params = SidechainParams(configs_dir=configs_dirs_dict[1])
    except Exception as e:
        eprint(str(e))
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
