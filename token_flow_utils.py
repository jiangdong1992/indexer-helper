import sys

sys.path.append('/')
import json
from config import Cfg
import time
from near_multinode_rpc_provider import MultiNodeJsonProviderError, MultiNodeJsonProvider
from typing import *
import decimal


fee_divisor = 10000


class Fees:
    FeeDivsor = 10000

    def __init__(self, trade_fee: int, admin_fee: int):
        self.trade_fee = trade_fee
        self.admin_fee = admin_fee

    def tradeFee(self, amount: int) -> int:
        return amount * self.trade_fee / Fees.FeeDivsor

    def adminFee(self, amount: int) -> int:
        return amount * self.admin_fee / Fees.FeeDivsor

    def normalized_trade_fee(self, num_coins: int, amount: int) -> int:
        adjusted_trade_fee = int(
            (self.trade_fee * num_coins) / (4 * (num_coins - 1)))
        return amount * adjusted_trade_fee / Fees.FeeDivsor


"""
Calculate invariant D
:param amp: factor A, can get from get_stable_pool interface;
:param c_amounts: vector of c_amounts in the pool, can get from get_stable_pool interface;
:return: invariant D
"""


def calc_d(amp: int, c_amounts: List[int]) -> int:
    n_coins = len(c_amounts)
    sum_amounts = sum(c_amounts)
    # Newton Iteration to resolve equation of higher degree
    #   previous approaching value
    d_prev = 0
    #   initial approaching value
    d = sum_amounts
    #   Max 256 round approaching iteration
    for i in range(256):
        #   to calc D_prod, as much precise as possible
        d_prod = d
        for c_amount in c_amounts:
            d_prod = d_prod * d / (c_amount * n_coins)
        #   store previous approaching value
        d_prev = d
        #   get cur-round approaching value
        ann = amp * n_coins ** n_coins
        # d = (ann * sum_amounts + d_prod * n_coins) * d_prev / ((ann - 1) * d_prev + (n_coins + 1) * d_prod)
        numerator = d_prev * (d_prod * n_coins + ann * sum_amounts)
        denominator = d_prev * (ann - 1) + d_prod * (n_coins + 1)
        d = numerator / denominator
        #   iteration terminating condition
        if abs(d - d_prev) <= 1:
            break

    return d


def calc_y(
        amp: int,
        x_c_amount: int,
        current_c_amounts: List[int],
        index_x: int,
        index_y: int
) -> int:
    n_coins = len(current_c_amounts)
    ann = amp * n_coins ** n_coins

    # invariant D
    d = calc_d(amp, current_c_amounts)

    # Solve for y by approximating: y**2 + b*y = c
    s_ = x_c_amount
    c = d * d / x_c_amount
    for i in range(n_coins):
        if i != index_x and i != index_y:
            s_ += current_c_amounts[i]
            c = c * d / current_c_amounts[i]
    c = c * d / (ann * n_coins ** n_coins)
    b = d / ann + s_

    # Newton Iteration to resolve equation of higher degree
    y_prev = 0
    y = d
    for i in range(256):
        y_prev = y
        # $ y_{k+1} = \frac{y_k^2 + c}{2y_k + b - D} $
        y_numerator = y ** 2 + c
        y_denominator = 2 * y + b - d
        y = y_numerator / y_denominator
        #   iteration terminating condition
        if abs(y - y_prev) <= 1:
            break

    return y


"""
Calc swap result (get_return)
:param amp: factor A, can get from get_stable_pool interface;
:param in_token_idx: token in index, starts from 0
:param in_c_amount: depositing token c_amount
:param out_token_idx: token out index, starts from 0
:param old_c_amounts: vector of currently c_amounts in the pool, can get from get_stable_pool interface;
:param fees: (fee ratio in bps, protocol/fee rate in bps)
:return: [swap out token's c_amount, fee c_amount]
"""


def calc_swap(
        amp: int,
        in_token_idx: int,
        in_c_amount: int,
        out_token_idx: int,
        old_c_amounts: List[int],
        fees: Fees
) -> Tuple[int, int]:
    # the new Y token's c_amount
    y = calc_y(amp, in_c_amount + old_c_amounts[in_token_idx], old_c_amounts, in_token_idx, out_token_idx)
    # swap out c_amount if no fee
    dy = old_c_amounts[out_token_idx] - y
    if dy > 0:
        # off-by-one issue
        dy = dy - 1
    # apply fee policy
    trade_fee = fees.tradeFee(dy)
    # real swapped out c_amount
    amount_swapped = dy - trade_fee
    return amount_swapped, trade_fee


def handle_trade_fee(amount, trade_fee):
    return (amount * trade_fee) / fee_divisor


def handle_stable_pool_decimal(pool_kind):
    if pool_kind == "STABLE_SWAP":
        return 18
    else:
        return 24


def shrink_token(amount, decimals):
    return int(amount) / int("1" + "0" * decimals)


def expand_token(amount, decimals):
    return int(amount) * int("1" + "0" * decimals)


def get_stable_and_rated_pool(network_id, pool_ids):
    contract = Cfg.NETWORK[network_id]["REF_CONTRACT"]
    stable_pool_list = {}

    try:
        conn = MultiNodeJsonProvider(network_id)
        rated_pool_ids = pool_ids["rated_pool"]
        for i in range(0, len(rated_pool_ids)):
            print("pool_id:", rated_pool_ids[i])
            time.sleep(0.1)
            ret = conn.view_call(contract, "get_rated_pool",
                                 ('{"pool_id": %s}' % rated_pool_ids[i]).encode(encoding='utf-8'))
            # print("ret:", ret)
            json_str = "".join([chr(x) for x in ret["result"]])
            rated_pool = json.loads(json_str)
            stable_pool_list[rated_pool_ids[i]] = rated_pool

        stable_pool_pool_ids = pool_ids["stable_pool"]
        for i in range(0, len(stable_pool_pool_ids)):
            print("pool_id:", stable_pool_pool_ids[i])
            time.sleep(0.1)
            ret = conn.view_call(contract, "get_stable_pool",
                                 ('{"pool_id": %s}' % stable_pool_pool_ids[i]).encode(encoding='utf-8'))
            # print("ret:", ret)
            json_str = "".join([chr(x) for x in ret["result"]])
            stable_pool = json.loads(json_str)

            if len(stable_pool["token_account_ids"]) > 2:
                stable_pool["rates"] = [expand_token(1, 18), expand_token(1, 18), expand_token(1, 18)]
            else:
                stable_pool["rates"] = [expand_token(1, 18), expand_token(1, 18)]
            stable_pool_list[stable_pool_pool_ids[i]] = stable_pool
        # print("stable_pool_list:", stable_pool_list)
        return stable_pool_list
    except MultiNodeJsonProviderError as e:
        print("RPC Error: ", e)
    except Exception as e:
        print("Error: ", e)
    # stable_pool_list = {'3612': {'token_account_ids': ['nearx.stader-labs.near', 'wrap.near'], 'decimals': [24, 24], 'amounts': ['360130437500959717872155876388', '241034925164942696754683199'], 'c_amounts': ['360130437500959717872155876388', '241034925164942696754683199'], 'total_fee': 5, 'shares_total_supply': '290025281183383226017275327143', 'amp': 240, 'rates': ['1015252798887302123711272', '1000000000000000000000000']}, '3514': {'token_account_ids': ['meta-pool.near', 'wrap.near'], 'decimals': [24, 24], 'amounts': ['428322849551127064685965719567', '641114657909471909434610956492'], 'c_amounts': ['428322849551127064685965719567', '641114657909471909434610956492'], 'total_fee': 5, 'shares_total_supply': '1084557934050730269592224718130', 'amp': 240, 'rates': ['1185260828908668929729857', '1000000000000000000000000']}, '3689': {'token_account_ids': ['dac17f958d2ee523a2206206994597c13d831ec7.factory.bridge.near', 'usdt.tether-token.near'], 'decimals': [6, 6], 'amounts': ['390008890151', '293485026243'], 'c_amounts': ['390008890151712046724945787169', '293485026243426221680392292418'], 'total_fee': 5, 'shares_total_supply': '681653630751992222160464587234', 'amp': 240, 'rates': ['1000000000000000000000000', '1000000000000000000000000']}, '3688': {'token_account_ids': ['v2-nearx.stader-labs.near', 'wrap.near'], 'decimals': [24, 24], 'amounts': ['622927871517326048275450552621', '427770215173582707495607199647'], 'c_amounts': ['622927871517326048275450552621', '427770215173582707495607199647'], 'total_fee': 5, 'shares_total_supply': '1062656475086169370227531484487', 'amp': 240, 'rates': ['1109701044428388114438092', '1000000000000000000000000']}, '3515': {'token_account_ids': ['linear-protocol.near', 'wrap.near'], 'decimals': [24, 24], 'amounts': ['45428599967364407412453711555', '24549661848284505403109810941'], 'c_amounts': ['45428599967364407412453711555', '24549661848284505403109810941'], 'total_fee': 5, 'shares_total_supply': '66158632679195040031207916274', 'amp': 240, 'rates': ['1111846673411922305184471', '1000000000000000000000000']}, '3364': {'token_account_ids': ['2260fac5e5542a773aa44fbcfedf7c193bc2c599.factory.bridge.near', '0316eb71485b0ab14103307bf65a021042c6d380.factory.bridge.near'], 'decimals': [8, 18], 'amounts': ['97949074', '981541972922239266'], 'c_amounts': ['979490745998996886', '981541972922239266'], 'total_fee': 5, 'shares_total_supply': '1960413000030551392', 'amp': 240, 'rates': [1000000000000000000, 1000000000000000000]}, '3433': {'token_account_ids': ['usn', 'cusd.token.a11bd.near'], 'decimals': [18, 24], 'amounts': ['2709341984655912223983', '7807911042146002060092000000'], 'c_amounts': ['2709341984655912223983', '7807911042146002060092'], 'total_fee': 5, 'shares_total_supply': '10463961250080232620194', 'amp': 240, 'rates': [1000000000000000000, 1000000000000000000]}, '3020': {'token_account_ids': ['usn', 'dac17f958d2ee523a2206206994597c13d831ec7.factory.bridge.near'], 'decimals': [18, 6], 'amounts': ['275975213244030788439678', '168561494540'], 'c_amounts': ['275975213244030788439678', '168561494540018436750759'], 'total_fee': 5, 'shares_total_supply': '443702221724586150698230', 'amp': 240, 'rates': [1000000000000000000, 1000000000000000000]}, '1910': {'token_account_ids': ['dac17f958d2ee523a2206206994597c13d831ec7.factory.bridge.near', 'a0b86991c6218b36c1d19d4a2e9eb0ce3606eb48.factory.bridge.near', '6b175474e89094c44da98b954eedeac495271d0f.factory.bridge.near'], 'decimals': [6, 6, 18], 'amounts': ['1094234408895', '2187720704624', '1470608514817812446860901'], 'c_amounts': ['1094234408895454667351814', '2187720704624680201191642', '1470608514817812446860901'], 'total_fee': 5, 'shares_total_supply': '4716094879966164422675567', 'amp': 240, 'rates': [1000000000000000000, 1000000000000000000, 1000000000000000000]}}
    # return stable_pool_list


def get_swapped_amount(token_in_id, token_out_id, amount_in, stable_pool, stable_pool_decimal):
    amp = stable_pool["amp"]
    trade_fee = Fees(stable_pool["total_fee"], 2000)
    in_token_idx = stable_pool["token_account_ids"].index(token_in_id)
    out_token_idx = stable_pool["token_account_ids"].index(token_out_id)
    stable_lp_token_decimals = stable_pool_decimal
    rates = stable_pool["rates"]
    base_old_c_amounts = []
    for c_amount in stable_pool["c_amounts"]:
        base_old_c_amounts.append(shrink_token(c_amount, stable_lp_token_decimals))
    old_c_amounts = []
    for i in range(0, len(base_old_c_amounts)):
        old_c_amounts.append(expand_token(base_old_c_amounts[i] * int(rates[i]), stable_lp_token_decimals))
    in_c_amount = expand_token(amount_in * int(rates[in_token_idx]), stable_lp_token_decimals)
    (amount_swapped, fee) = calc_swap(
        amp,
        in_token_idx,
        in_c_amount,
        out_token_idx,
        old_c_amounts,
        trade_fee
    )
    amount_swapped = amount_swapped / int(rates[out_token_idx])
    if amount_swapped < 0:
        amount_out = "0"
    else:
        amount_out = amount_swapped
    return shrink_token(amount_out, stable_lp_token_decimals)


def combine_token_flow1(token_flow_data_list, swap_amount, ledger):
    now_time = int(time.time())
    ret_list = []
    if ledger != "all" or len(token_flow_data_list) < 2:
        max_token_pair_data = {}
        max_ratio = 0.00
        for token_pair_data in token_flow_data_list:
            # if "'1910'" in token_pair_data["pool_ids"]:
            #     continue
            grade_ratio = 0.00
            if token_pair_data["grade"] == "1":
                if token_pair_data["pool_kind"] == "SIMPLE_POOL":
                    grade_1_ratio = get_token_flow_ratio(swap_amount, token_pair_data["token_in_amount"],
                                                         token_pair_data["token_out_amount"],
                                                         token_pair_data["pool_fee"]) / swap_amount
                else:
                    grade_1_ratio = get_stable_and_rated_pool_ratio(token_pair_data["pool_token_number"],
                                                                    json.loads(token_pair_data["three_pool_ids"]),
                                                                    json.loads(token_pair_data["three_c_amount"]),
                                                                    token_pair_data["token_in"],
                                                                    token_pair_data["token_out"],
                                                                    token_pair_data["token_in_amount"],
                                                                    token_pair_data["token_out_amount"],
                                                                    token_pair_data["amp"],
                                                                    token_pair_data["pool_fee"],
                                                                    json.loads(token_pair_data["rates"]),
                                                                    token_pair_data["pool_kind"], swap_amount) / swap_amount
                token_pair_data["token_pair_ratio"] = format_decimal_float(grade_1_ratio)
                token_pair_data["final_ratio"] = format_decimal_float(grade_1_ratio)
                grade_ratio = float(grade_1_ratio)
            if grade_ratio > max_ratio:
                max_ratio = grade_ratio
                max_token_pair_data = token_pair_data
                max_token_pair_data["amount"] = max_ratio * swap_amount
                max_token_pair_data["swap_amount"] = swap_amount
                max_token_pair_data["timestamp"] = str(now_time)
                max_token_pair_data["swap_ratio"] = 100
        if max_token_pair_data != {}:
            ret_list.append(max_token_pair_data)
    else:
        ratio_data = {}
        ratio_data_key_list = []
        ratio_data_g_1 = {}
        ratio_data_key_list_g_1 = []
        start_ratio = 0
        space_number = 5
        space_length = int((100 - start_ratio) / space_number) + 1
        for i in range(1, space_length):
            for token_pair_data in token_flow_data_list:
                swap_ratio = i * space_number
                ratio = swap_ratio / 100
                if token_pair_data["grade"] == "1":
                    swap_ratio = start_ratio + swap_ratio
                    ratio = swap_ratio / 100
                    ratio_data_key = token_pair_data["pool_ids"] + "_" + str(swap_ratio)
                    ratio_data_g_1[ratio_data_key] = get_pair_ratio(token_pair_data, swap_amount, ratio, now_time, swap_ratio)
                    ratio_data_key_list_g_1.append(ratio_data_key)
                else:
                    ratio_data_key = token_pair_data["pool_ids"] + "_" + str(swap_ratio)
                    ratio_data[ratio_data_key] = get_pair_ratio(token_pair_data, swap_amount, ratio, now_time, swap_ratio)
                    ratio_data_key_list.append(ratio_data_key)
        # print("ratio_data:", ratio_data)
        # print("ratio_data_key_list:", ratio_data_key_list)
        max_combination_ratio = 0.00
        if len(ratio_data_key_list_g_1) > 1:
            for ratio_data_key_g_1 in ratio_data_key_list_g_1:
                g_1_ratio_s = ratio_data_key_g_1.split("_")
                g_1_ratio = 100 - int(g_1_ratio_s[1])
                combination_list = []
                for i in range(1, 4):
                    combinations = calculate_optimal_combination(ratio_data_key_list, g_1_ratio, i)
                    combination_list += combinations
                # print("g_1_ratio:", g_1_ratio)
                # print("combination_list:", combination_list)
                # print("combination_list size:", len(combination_list))
                max_ratio, pair_ratio_list = get_max_combination(combination_list, ratio_data_g_1[ratio_data_key_g_1], ratio_data)
                if max_ratio > max_combination_ratio:
                    max_combination_ratio = max_ratio
                    ret_list = pair_ratio_list
        else:
            max_combination_ratio = 0.00
            for x in range(0, len(token_flow_data_list)):
                pair_ratio_data_b = get_pair_ratio(token_flow_data_list[x], swap_amount, 1, now_time, 100)
                max_ratio = pair_ratio_data_b["amount"]
                if max_ratio > max_combination_ratio:
                    max_combination_ratio = max_ratio
                    ret_list.clear()
                    ret_list.append(pair_ratio_data_b)

                pair_ratio_data_c = get_pair_ratio(token_flow_data_list[x], swap_amount, 0.95, now_time, 95)
                for y in range(0, len(token_flow_data_list)):
                    if token_flow_data_list[y] != token_flow_data_list[x]:
                        pair_ratio_data_d = get_pair_ratio(token_flow_data_list[y], swap_amount, 0.05, now_time, 5)
                        amount_ratio = pair_ratio_data_c["amount"] + pair_ratio_data_d["amount"]
                        if amount_ratio > max_combination_ratio:
                            max_combination_ratio = amount_ratio
                            ret_list.clear()
                            ret_list.append(pair_ratio_data_c)
                            ret_list.append(pair_ratio_data_d)

                pair_ratio_data_e = get_pair_ratio(token_flow_data_list[x], swap_amount, 0.9, now_time, 90)
                for z in range(0, len(token_flow_data_list)):
                    if token_flow_data_list[z] != token_flow_data_list[x]:
                        pair_ratio_data_f = get_pair_ratio(token_flow_data_list[z], swap_amount, 0.1, now_time, 10)
                        amount_ratio = pair_ratio_data_e["amount"] + pair_ratio_data_f["amount"]
                        if amount_ratio > max_combination_ratio:
                            max_combination_ratio = amount_ratio
                            ret_list.clear()
                            ret_list.append(pair_ratio_data_e)
                            ret_list.append(pair_ratio_data_f)
        for token_flow_data_g in token_flow_data_list:
            if token_flow_data_g["grade"] == "1":
                pair_ratio_data_last = get_pair_ratio(token_flow_data_g, swap_amount, 1, now_time, 100)
                max_ratio = pair_ratio_data_last["amount"]
                if max_ratio > max_combination_ratio:
                    max_combination_ratio = max_ratio
                    ret_list.clear()
                    ret_list.append(pair_ratio_data_last)
    end_time = int(time.time())
    print("end:", end_time - now_time)
    return token_flow_return_data(ret_list)


def combine_token_flow(token_flow_data_list, swap_amount, ledger):
    now_time = int(time.time())
    ret_list = []
    grade_one_flow = get_grade_one_flow(token_flow_data_list)
    if ledger != "all":
        if grade_one_flow == {}:
            return ret_list
        else:
            if grade_one_flow["pool_kind"] == "SIMPLE_POOL":
                grade_1_ratio = get_token_flow_ratio(swap_amount, grade_one_flow["token_in_amount"],
                                                     grade_one_flow["token_out_amount"],
                                                     grade_one_flow["pool_fee"]) / swap_amount
            else:
                grade_1_ratio = get_stable_and_rated_pool_ratio(grade_one_flow["pool_token_number"],
                                                                json.loads(grade_one_flow["three_pool_ids"]),
                                                                json.loads(grade_one_flow["three_c_amount"]),
                                                                grade_one_flow["token_in"],
                                                                grade_one_flow["token_out"],
                                                                grade_one_flow["token_in_amount"],
                                                                grade_one_flow["token_out_amount"],
                                                                grade_one_flow["amp"],
                                                                grade_one_flow["pool_fee"],
                                                                json.loads(grade_one_flow["rates"]),
                                                                grade_one_flow["pool_kind"], swap_amount) / swap_amount
            grade_one_flow["token_pair_ratio"] = format_decimal_float(grade_1_ratio)
            grade_one_flow["final_ratio"] = format_decimal_float(grade_1_ratio)
            grade_one_flow["amount"] = format_decimal_float(grade_1_ratio * swap_amount)
            grade_one_flow["swap_amount"] = swap_amount
            grade_one_flow["timestamp"] = str(now_time)
            grade_one_flow["swap_ratio"] = 100
            ret_list.append(grade_one_flow)
    else:
        max_combination_ratio = 0.00
        grade_flow_data = {}
        for token_flow_data in token_flow_data_list:
            grade_flow_data.setdefault(token_flow_data.get("swap_number_grade"), []).append(token_flow_data)
        if grade_one_flow == {}:
            grade_flow_list = handel_grade_flow_data(grade_flow_data, swap_amount)
            for x in range(0, len(grade_flow_list)):
                grade_flow_pool_ids_x = json.loads(grade_flow_list[x]["pool_ids"])
                pair_ratio_data_b = get_pair_ratio(grade_flow_list[x], swap_amount, 1, now_time, 100)
                max_ratio = pair_ratio_data_b["amount"]
                if max_ratio > max_combination_ratio:
                    max_combination_ratio = max_ratio
                    ret_list.clear()
                    ret_list.append(pair_ratio_data_b)

                pair_ratio_data_c = get_pair_ratio(grade_flow_list[x], swap_amount, 0.95, now_time, 95)
                for y in range(0, len(grade_flow_list)):
                    grade_flow_pool_ids_y = json.loads(grade_flow_list[y]["pool_ids"])
                    y_res = list(set(grade_flow_pool_ids_x) & set(grade_flow_pool_ids_y))
                    if grade_flow_list[y] != grade_flow_list[x] and len(y_res) < 1:
                        pair_ratio_data_d = get_pair_ratio(grade_flow_list[y], swap_amount, 0.05, now_time, 5)
                        amount_ratio = pair_ratio_data_c["amount"] + pair_ratio_data_d["amount"]
                        if amount_ratio > max_combination_ratio:
                            max_combination_ratio = amount_ratio
                            ret_list.clear()
                            ret_list.append(pair_ratio_data_c)
                            ret_list.append(pair_ratio_data_d)

                pair_ratio_data_e = get_pair_ratio(grade_flow_list[x], swap_amount, 0.9, now_time, 90)
                for z in range(0, len(grade_flow_list)):
                    grade_flow_pool_ids_z = json.loads(grade_flow_list[z]["pool_ids"])
                    z_res = list(set(grade_flow_pool_ids_x) & set(grade_flow_pool_ids_z))
                    if grade_flow_list[z] != grade_flow_list[x] and len(z_res) < 1:
                        pair_ratio_data_f = get_pair_ratio(grade_flow_list[z], swap_amount, 0.1, now_time, 10)
                        amount_ratio = pair_ratio_data_e["amount"] + pair_ratio_data_f["amount"]
                        if amount_ratio > max_combination_ratio:
                            max_combination_ratio = amount_ratio
                            ret_list.clear()
                            ret_list.append(pair_ratio_data_e)
                            ret_list.append(pair_ratio_data_f)
        else:
            ratio_data = {}
            ratio_data_key_list = []
            ratio_data_g_1 = {}
            ratio_data_key_list_g_1 = []
            start_ratio = 0
            space_number = 5
            space_length = int((100 - start_ratio) / space_number) + 1
            for i in range(1, space_length):
                swap_ratio = i * space_number
                ratio = swap_ratio / 100
                ratio_swap_amount = swap_ratio / 100 * swap_amount
                swap_ratio = start_ratio + swap_ratio
                ratio_data_key = grade_one_flow["pool_ids"] + "_" + str(swap_ratio)
                ratio_data_g_1[ratio_data_key] = get_pair_ratio(grade_one_flow, swap_amount, ratio, now_time, swap_ratio)
                ratio_data_key_list_g_1.append(ratio_data_key)
                grade_flow_list = handel_grade_flow_data(grade_flow_data, ratio_swap_amount)
                top_flow_list = get_top_flow(grade_flow_list)
                for top_flow in top_flow_list:
                    ratio_data_key = top_flow["pool_ids"] + "_" + str(swap_ratio)
                    ratio_data[ratio_data_key] = get_pair_ratio(top_flow, swap_amount, ratio, now_time, swap_ratio)
                    ratio_data_key_list.append(ratio_data_key)
            end_time = int(time.time())
            print("combine_token_flow end1:", end_time - now_time)
            for ratio_data_key_g_1 in ratio_data_key_list_g_1:
                g_1_ratio_s = ratio_data_key_g_1.split("_")
                g_1_ratio = 100 - int(g_1_ratio_s[1])
                combination_list = []
                ratio_data_key_list_end = []
                for ratio_data_key_end in ratio_data_key_list:
                    ratio_data_key_r = int(ratio_data_key_end.split("_")[1])
                    if ratio_data_key_r <= g_1_ratio:
                        ratio_data_key_list_end.append(ratio_data_key_end)
                end_time = int(time.time())
                print("combine_token_flow end2:", end_time - now_time)
                for i in range(1, 4):
                    combinations = calculate_optimal_combination(ratio_data_key_list_end, g_1_ratio, i)
                    combination_list += combinations
                # print("g_1_ratio:", g_1_ratio)
                # print("combination_list:", combination_list)
                # print("combination_list size:", len(combination_list))
                max_ratio, pair_ratio_list = get_max_combination(combination_list, ratio_data_g_1[ratio_data_key_g_1], ratio_data)
                end_time = int(time.time())
                print("combine_token_flow end3:", end_time - now_time)
                if max_ratio > max_combination_ratio:
                    max_combination_ratio = max_ratio
                    ret_list = pair_ratio_list
            end_time = int(time.time())
            print("combine_token_flow end4:", end_time - now_time)
            pair_ratio_data_last = get_pair_ratio(grade_one_flow, swap_amount, 1, now_time, 100)
            max_ratio = pair_ratio_data_last["amount"]
            if max_ratio > max_combination_ratio:
                max_combination_ratio = max_ratio
                ret_list.clear()
                ret_list.append(pair_ratio_data_last)
    end_time = int(time.time())
    print("combine_token_flow end3:", end_time - now_time)
    return token_flow_return_data(ret_list)


def handel_grade_flow_data(grade_flow_data, ratio_swap_amount):
    if ratio_swap_amount < 10:
        ret_flow_data = grade_flow_data[1]
    elif 10 <= ratio_swap_amount < 100:
        ret_flow_data = grade_flow_data[10]
    elif 100 <= ratio_swap_amount < 1000:
        ret_flow_data = grade_flow_data[100]
    elif 1000 <= ratio_swap_amount < 10000:
        ret_flow_data = grade_flow_data[1000]
    elif 10000 <= ratio_swap_amount < 100000:
        ret_flow_data = grade_flow_data[10000]
    else:
        ret_flow_data = grade_flow_data[100000]
    return ret_flow_data


def token_flow_return_data(ret_list):
    ret = []
    for max_token_pair_data in ret_list:
        all_tokens = []
        all_pool_fees = []
        all_tokens.append(max_token_pair_data["token_in"])
        all_pool_fees.append(max_token_pair_data["pool_fee"])
        if max_token_pair_data["revolve_token_one"] != "":
            all_tokens.append(max_token_pair_data["revolve_token_one"])
            all_pool_fees.append(max_token_pair_data["revolve_one_pool_fee"])
        if max_token_pair_data["revolve_token_two"] != "":
            all_tokens.append(max_token_pair_data["revolve_token_two"])
            all_pool_fees.append(max_token_pair_data["revolve_two_pool_fee"])
        all_tokens.append(max_token_pair_data["token_out"])
        ret_data = {
            "token_pair": max_token_pair_data["token_pair"],
            "grade": max_token_pair_data["grade"],
            "pool_ids": json.loads(max_token_pair_data["pool_ids"]),
            "token_in": max_token_pair_data["token_in"],
            "token_out": max_token_pair_data["token_out"],
            "final_ratio": max_token_pair_data["final_ratio"],
            "amount": max_token_pair_data["amount"],
            "swap_amount": max_token_pair_data["swap_amount"],
            "all_tokens": all_tokens,
            "all_pool_fees": all_pool_fees,
            "swap_ratio": max_token_pair_data["swap_ratio"],
            "timestamp": max_token_pair_data["timestamp"]
        }
        ret.append(ret_data)
    return ret


def get_stable_and_rated_pool_ratio(pool_token_number, three_pool_ids, three_c_amount, token_in, token_out,
                                    token_in_amount, token_out_amount, amp, total_fee, rates, pool_kind, swap_amount):
    if pool_token_number == "3":
        token_account_ids = three_pool_ids
        c_amounts = three_c_amount
    else:
        token_account_ids = [token_in, token_out]
        c_amounts = [token_in_amount, token_out_amount]
    stable_pool = {"amp": amp, "total_fee": total_fee, "token_account_ids": token_account_ids,
                   "c_amounts": c_amounts, "rates": rates}
    revolve_token_one_ratio = get_swapped_amount(token_in, token_out, float(swap_amount), stable_pool,
                                                 handle_stable_pool_decimal(pool_kind))
    revolve_token_one_ratio = format_decimal_float(revolve_token_one_ratio)
    return float(revolve_token_one_ratio)


def get_token_flow_ratio(token_in_amount, token_in_balance, token_out_balance, fee):
    try:
        token_in_amount = decimal.Decimal(token_in_amount)
        token_in_balance = decimal.Decimal(token_in_balance)
        token_out_balance = decimal.Decimal(token_out_balance)
        fee = decimal.Decimal(fee)
        ratio = token_in_amount * (10000 - fee) * token_out_balance / (
                10000 * token_in_balance + token_in_amount * (10000 - fee))
        ratio = format_decimal_float(ratio)
        return float(ratio)
    except Exception as e:
        print("get ratio error:", e)
        return 0
    # a, b = str(ratio).split('.')
    # return float(a + '.' + b[0:6])


def get_pair_ratio(token_pair_data, swap_amount, ratio_number, now_time, swap_ratio):
    pair_ratio_data = {
        "token_pair": token_pair_data["token_pair"],
        "grade": token_pair_data["grade"],
        "pool_ids": token_pair_data["pool_ids"],
        "token_in": token_pair_data["token_in"],
        "revolve_token_one": token_pair_data["revolve_token_one"],
        "revolve_token_two": token_pair_data["revolve_token_two"],
        "token_out": token_pair_data["token_out"],
        "token_pair_ratio": token_pair_data["token_pair_ratio"],
        "revolve_token_one_ratio": token_pair_data["revolve_token_one_ratio"],
        "revolve_token_two_ratio": token_pair_data["revolve_token_two_ratio"],
        "final_ratio": token_pair_data["final_ratio"],
        "pool_fee": token_pair_data["pool_fee"],
        "revolve_one_pool_fee": token_pair_data["revolve_one_pool_fee"],
        "revolve_two_pool_fee": token_pair_data["revolve_two_pool_fee"],
    }
    compute_amount = swap_amount * ratio_number
    if token_pair_data["grade"] == "1":
        if token_pair_data["pool_kind"] == "SIMPLE_POOL":
            grade_1_ratio = get_token_flow_ratio(compute_amount, token_pair_data["token_in_amount"],
                                                 token_pair_data["token_out_amount"],
                                                 token_pair_data["pool_fee"]) / compute_amount
        else:
            grade_1_ratio = get_stable_and_rated_pool_ratio(token_pair_data["pool_token_number"],
                                                            json.loads(token_pair_data["three_pool_ids"]),
                                                            json.loads(token_pair_data["three_c_amount"]),
                                                            token_pair_data["token_in"],
                                                            token_pair_data["token_out"],
                                                            token_pair_data["token_in_amount"],
                                                            token_pair_data["token_out_amount"],
                                                            token_pair_data["amp"],
                                                            token_pair_data["pool_fee"],
                                                            json.loads(token_pair_data["rates"]),
                                                            token_pair_data["pool_kind"],
                                                            compute_amount) / compute_amount
        pair_ratio = format_decimal_float(grade_1_ratio)
        pair_ratio_data["token_pair_ratio"] = pair_ratio
        pair_ratio_data["final_ratio"] = pair_ratio
        pair_ratio_data["amount"] = format_decimal_float(grade_1_ratio * compute_amount)
        pair_ratio_data["swap_amount"] = compute_amount
        pair_ratio_data["timestamp"] = str(now_time)
        pair_ratio_data["swap_ratio"] = swap_ratio
    if token_pair_data["grade"] == "2":
        if token_pair_data["pool_kind"] == "SIMPLE_POOL":
            grade_2_ratio_one = get_token_flow_ratio(compute_amount, token_pair_data["token_in_amount"],
                                                     token_pair_data["revolve_one_out_amount"],
                                                     token_pair_data["pool_fee"])
        else:
            grade_2_ratio_one = get_stable_and_rated_pool_ratio(token_pair_data["pool_token_number"],
                                                                json.loads(token_pair_data["three_pool_ids"]),
                                                                json.loads(token_pair_data["three_c_amount"]),
                                                                token_pair_data["token_in"],
                                                                token_pair_data["revolve_token_one"],
                                                                token_pair_data["token_in_amount"],
                                                                token_pair_data["revolve_one_out_amount"],
                                                                token_pair_data["amp"],
                                                                token_pair_data["pool_fee"],
                                                                json.loads(token_pair_data["rates"]),
                                                                token_pair_data["pool_kind"],
                                                                compute_amount)
        if token_pair_data["revolve_one_pool_kind"] == "SIMPLE_POOL":
            grade_2_ratio_two = (get_token_flow_ratio(grade_2_ratio_one, token_pair_data["revolve_one_in_amount"],
                                                      token_pair_data["token_out_amount"],
                                                      token_pair_data["revolve_one_pool_fee"]))
        else:
            grade_2_ratio_two = get_stable_and_rated_pool_ratio(
                token_pair_data["revolve_one_pool_token_number"],
                json.loads(token_pair_data["three_pool_ids"]),
                json.loads(token_pair_data["three_c_amount"]),
                token_pair_data["revolve_token_one"],
                token_pair_data["token_out"],
                token_pair_data["revolve_one_in_amount"],
                token_pair_data["token_out_amount"],
                token_pair_data["revolve_one_pool_amp"],
                token_pair_data["revolve_one_pool_fee"],
                json.loads(token_pair_data["revolve_one_pool_rates"]),
                token_pair_data["revolve_one_pool_kind"], grade_2_ratio_one)
        # grade_2_ratio = grade_2_ratio_one * grade_2_ratio_two
        # pair_ratio = format_decimal_float(grade_2_ratio)
        pair_ratio_data["token_pair_ratio"] = format_decimal_float(grade_2_ratio_one)
        pair_ratio_data["revolve_token_one_ratio"] = format_decimal_float(grade_2_ratio_two)
        pair_ratio_data["final_ratio"] = format_decimal_float(grade_2_ratio_two)
        pair_ratio_data["amount"] = format_decimal_float(grade_2_ratio_two)
        pair_ratio_data["swap_amount"] = compute_amount
        pair_ratio_data["timestamp"] = str(now_time)
        pair_ratio_data["swap_ratio"] = swap_ratio
    if token_pair_data["grade"] == "3":
        if token_pair_data["pool_kind"] == "SIMPLE_POOL":
            grade_3_ratio_one = get_token_flow_ratio(compute_amount, token_pair_data["token_in_amount"],
                                                     token_pair_data["revolve_one_out_amount"],
                                                     token_pair_data["pool_fee"])
        else:
            grade_3_ratio_one = get_stable_and_rated_pool_ratio(token_pair_data["pool_token_number"],
                                                                json.loads(token_pair_data["three_pool_ids"]),
                                                                json.loads(token_pair_data["three_c_amount"]),
                                                                token_pair_data["token_in"],
                                                                token_pair_data["revolve_token_one"],
                                                                token_pair_data["token_in_amount"],
                                                                token_pair_data["revolve_one_out_amount"],
                                                                token_pair_data["amp"],
                                                                token_pair_data["pool_fee"],
                                                                json.loads(token_pair_data["rates"]),
                                                                token_pair_data["pool_kind"],
                                                                compute_amount)
        if token_pair_data["revolve_one_pool_kind"] == "SIMPLE_POOL":
            grade_3_ratio_two = (get_token_flow_ratio(grade_3_ratio_one, token_pair_data["revolve_one_in_amount"],
                                                      token_pair_data["revolve_two_out_amount"],
                                                      token_pair_data["revolve_one_pool_fee"]))
        else:
            grade_3_ratio_two = get_stable_and_rated_pool_ratio(
                token_pair_data["revolve_one_pool_token_number"],
                json.loads(token_pair_data["three_pool_ids"]),
                json.loads(token_pair_data["three_c_amount"]),
                token_pair_data["revolve_token_one"],
                token_pair_data["revolve_token_two"],
                token_pair_data["revolve_one_in_amount"],
                token_pair_data["revolve_two_out_amount"],
                token_pair_data["revolve_one_pool_amp"],
                token_pair_data["revolve_one_pool_fee"],
                json.loads(token_pair_data["revolve_one_pool_rates"]),
                token_pair_data["revolve_one_pool_kind"], grade_3_ratio_one)
        if token_pair_data["revolve_two_pool_kind"] == "SIMPLE_POOL":
            grade_3_ratio_three = (get_token_flow_ratio(grade_3_ratio_two,
                                                        token_pair_data["revolve_two_in_amount"],
                                                        token_pair_data["token_out_amount"],
                                                        token_pair_data["revolve_two_pool_fee"]))
        else:
            grade_3_ratio_three = get_stable_and_rated_pool_ratio(
                token_pair_data["revolve_two_pool_token_number"],
                json.loads(token_pair_data["three_pool_ids"]),
                json.loads(token_pair_data["three_c_amount"]),
                token_pair_data["revolve_token_two"],
                token_pair_data["token_out"],
                token_pair_data["revolve_two_in_amount"],
                token_pair_data["token_out_amount"],
                token_pair_data["revolve_two_pool_amp"],
                token_pair_data["revolve_two_pool_fee"],
                json.loads(token_pair_data["revolve_two_pool_rates"]),
                token_pair_data["revolve_two_pool_kind"], grade_3_ratio_two)
        # grade_3_ratio = grade_3_ratio_one * grade_3_ratio_two * grade_3_ratio_three
        # pair_ratio = format_decimal_float(grade_3_ratio)
        pair_ratio_data["token_pair_ratio"] = format_decimal_float(grade_3_ratio_one)
        pair_ratio_data["revolve_token_one_ratio"] = format_decimal_float(grade_3_ratio_two)
        pair_ratio_data["revolve_token_two_ratio"] = format_decimal_float(grade_3_ratio_three)
        pair_ratio_data["final_ratio"] = format_decimal_float(grade_3_ratio_three)
        pair_ratio_data["amount"] = format_decimal_float(grade_3_ratio_three)
        pair_ratio_data["swap_amount"] = compute_amount
        pair_ratio_data["timestamp"] = str(now_time)
        pair_ratio_data["swap_ratio"] = swap_ratio
    return pair_ratio_data


def get_grade_one_flow(token_flow_list):
    ret_data = {}
    for token_flow_data in token_flow_list:
        if token_flow_data["grade"] == "1":
            ret_data = token_flow_data
    return ret_data


def get_top_flow(token_flow_list):
    ret_list = []
    sorted_token_flow_list = sorted(token_flow_list, key=lambda token_flow: token_flow["final_ratio"], reverse=True)
    for token_flow_data in sorted_token_flow_list:
        if token_flow_data["grade"] == "1":
            continue
        if len(ret_list) < 3:
            ret_list.append(token_flow_data)
    return ret_list


def get_top_flow1(token_flow_list):
    ret_list = []
    grade_flag = True
    sorted_token_flow_list = sorted(token_flow_list, key=lambda token_flow: token_flow["final_ratio"], reverse=True)
    for token_flow_data in sorted_token_flow_list:
        if token_flow_data["grade"] == "1":
            ret_list.append(token_flow_data)
            grade_flag = False
        else:
            if len(ret_list) < 3:
                ret_list.append(token_flow_data)
    if grade_flag:
        ret_list.clear()
        ret_list = sorted_token_flow_list
    return ret_list


def calculate_optimal_combination(ratio_data_key_list, combination_number, number):
    from itertools import combinations
    ret_list = []
    combinations = list(combinations(ratio_data_key_list, number))
    for c in combinations:
        used_pools_list = []
        used_pools_set = set()
        ratio = 0
        pool_ratio_key = set()
        for pool_ratio in c:
            ratio_s = pool_ratio.split("_")
            ratio = ratio + int(ratio_s[1])
            pool_ratio_key.add(ratio_s[0])
            used_pools = json.loads(ratio_s[0])
            used_pools_list += used_pools
            for used_pool in used_pools:
                used_pools_set.add(used_pool)
        if ratio == combination_number and len(c) == len(pool_ratio_key) and len(used_pools_list) == len(used_pools_set):
            ret_list.append(c)
            used_pools_list.clear()
            used_pools_set.clear()
            pool_ratio_key.clear()
    return ret_list


def get_max_combination(combination_list, ratio_data_g_1, ratio_data):
    ret = []
    max_ratio = 0.00
    for combination in combination_list:
        amount = 0.00
        pair_data = []
        for c in combination:
            amount += ratio_data[c]["amount"]
            pair_data.append(ratio_data[c])
        count_amount = amount
        if ratio_data_g_1 != "":
            count_amount = ratio_data_g_1["amount"] + amount
        if count_amount > max_ratio:
            ret.clear()
            if ratio_data_g_1 != "":
                ret.append(ratio_data_g_1)
            ret += pair_data
            max_ratio = count_amount
    return max_ratio, ret


def format_decimal_float(number):
    format_number = "{0:.16f}".format(decimal.Decimal(number))
    if '.' in format_number:
        return float(format_number[:format_number.index('.') + 1 + 8])
    return float(format_number)


def format_decimal_decimal(number):
    format_number = "{:.8f}".format(decimal.Decimal(number))
    return decimal.Decimal(format_number)


def get_token_pair_ratio_data(token_flow_data_list, swap_amount, now_time):
    ratio_data = {}
    ratio_data_key_list = []
    for token_pair_data in token_flow_data_list:
        ratio_data_key = token_pair_data["pool_ids"] + "_" + "5"
        ratio_data[ratio_data_key] = get_pair_ratio(token_pair_data, swap_amount, 0.05, now_time, 5)
        ratio_data_key_list.append(ratio_data_key)

        ratio_data_key = token_pair_data["pool_ids"] + "_" + "10"
        ratio_data[ratio_data_key] = get_pair_ratio(token_pair_data, swap_amount, 0.1, now_time, 10)
        ratio_data_key_list.append(ratio_data_key)

        ratio_data_key = token_pair_data["pool_ids"] + "_" + "90"
        ratio_data[ratio_data_key] = get_pair_ratio(token_pair_data, swap_amount, 0.9, now_time, 90)
        ratio_data_key_list.append(ratio_data_key)

        ratio_data_key = token_pair_data["pool_ids"] + "_" + "95"
        ratio_data[ratio_data_key] = get_pair_ratio(token_pair_data, swap_amount, 0.95, now_time, 95)
        ratio_data_key_list.append(ratio_data_key)

        ratio_data_key = token_pair_data["pool_ids"] + "_" + "100"
        ratio_data[ratio_data_key] = get_pair_ratio(token_pair_data, swap_amount, 1, now_time, 100)
        ratio_data_key_list.append(ratio_data_key)
    return ratio_data_key_list, ratio_data


if __name__ == "__main__":
    print("#########TOKEN FLOW START###########")

    # start_time = int(time.time())
    # # pool_data = get_stable_pool("MAINNET", )
    # pool_ids = {"rated_pool": ["3514", "3689", "3515", "3688", "3612"], "stable_pool": ["3020", "3433", "3364", "1910"]}
    # pool_data = get_stable_and_rated_pool("MAINNET", pool_ids)
    # print(pool_data)
    # end_time1 = int(time.time())
    # print("get_stable_pool consuming:", end_time1 - start_time)

    # stable_pool_test = {'token_account_ids': ['wrap.near', 'meta-pool.near'], 'decimals': [24, 24],
    #                     'amounts': ['557204308996544773502195718777', '482901600452125936664295179841'],
    #                     'c_amounts': ['557204308996544773502195718777', '482901600452125936664295179841'],
    #                     'total_fee': 5, 'shares_total_supply': '1072529148949520003479920392363', 'amp': 240,
    #                     'rates': ['1000000000000000000000000', '1187871064224440774482330']}
    # # stable_pool_test["rates"] = [expand_token(1, 18), expand_token(1, 18)]
    # res = get_swapped_amount("wrap.near", "meta-pool.near", 0.000001, stable_pool_test, 24)
    # print(res)

    # numbers = [50, 45, 40, 35, 30, 25, 20, 15, 10, 5]
    # numbers = [1, 2, 3, 4, 5, 6]
    # combinations = list(combinations(numbers, 3))
    # for c in combinations:
    #     if sum(c) == 10:
    #         print(c)

    aa = 4.2074845559735835e-07
    bb = format_decimal_float(aa)
    print(bb)


