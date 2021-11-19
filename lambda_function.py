import decimal
import math
import os
from time import time
from typing import Dict, Tuple, Union

import tweepy
from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport
from web3 import Web3

TWEET_MSG = """
💰 General
TVL: Ξ {tvl} (${tvl_usd})
Staking Pool Balance: Ξ {staker_eth_in_deposit_pool}

🖥️ Nodes
Commission: {minipool_commission:.2f}%
Registered Nodes: {node_count}
Staking Minipools: {staking_minipools}
Total ETH Validator Share: {percent_validators:.3f}%

🪙 Tokens
rETH Price: Ξ {rETH_price:.5f}
RPL Price: Ξ {rpl_price:.5f}
Total RPL staked: {total_rpl_staked}
Effective RPL staked: {effective_rpl_staked}
"""

SUBGRAPH_BASE_URL = "https://gateway.thegraph.com/api/"
SUBGRAPH_API_URL = "subgraphs/id/0xa508c16666c5b8981fa46eb32784fccc01942a71-3"
STAKER_ETH_PER_MINIPOOL = 16
ETH_PER_MINIPOOL = 32


NUMBER_SYMBOLS = ['', 'k', 'M', 'B', 'T']


def _pretty_print_num(n) -> str:
    """Convert numbers to a more readable format, eg) 115.5k, 12.3M"""
    n = float(n)
    symbol_idx = max(
        0,
        min(
            len(NUMBER_SYMBOLS) - 1,
            int(math.floor(0 if n == 0 else math.log10(abs(n)) / 3))
        )
    )

    return '{:.{precision}f}{}'.format(
        n / 10**(3 * symbol_idx),
        NUMBER_SYMBOLS[symbol_idx],
        precision=2 if n < 10000 else 1
    )


def _wei_to_eth(val: Union[str, int]) -> decimal.Decimal:
    if type(val) == str:
        val = int(val)
    return Web3.fromWei(val, 'ether')


def _fetch_rocketpool_stats() -> Tuple[Dict, Dict]:
    subgraph_api_key = os.getenv("SUBGRAPH_API_KEY")
    url = SUBGRAPH_BASE_URL + f"{subgraph_api_key}/" + SUBGRAPH_API_URL
    transport = RequestsHTTPTransport(
        url=url,
        use_json=True,
        headers={
            "Content-type": "application/json",
        },
        retries=3,
    )

    client = Client(transport=transport, fetch_schema_from_transport=True)
    query = gql('''
        query protocolMetrics {
            rocketPoolProtocols {
                lastNetworkNodeBalanceCheckPoint {
                    stakingMinipools
                    newMinipoolFee
                    nodesRegistered
                    rplPriceInETH
                    rplStaked
                    effectiveRPLStaked
                    blockTime
                }
                lastNetworkStakerBalanceCheckPoint {
                    stakerETHWaitingInDepositPool
                    rETHExchangeRate
                    blockTime
                }
            }
        }
    ''')

    data = client.execute(query)
    data = data["rocketPoolProtocols"][0]
    node_stats = data["lastNetworkNodeBalanceCheckPoint"]
    staker_stats = data["lastNetworkStakerBalanceCheckPoint"]
    return node_stats, staker_stats


def _fetch_eth_stats() -> Tuple[float, float]:
    eth_price_usd = 4200
    active_eth_validators = 250000
    return eth_price_usd, active_eth_validators


def _auth_tweepy() -> tweepy.API:
    # Fetch credentials
    consumer_key = os.getenv("CONSUMER_KEY")
    consumer_secret = os.getenv("CONSUMER_SECRET")
    access_token = os.getenv("ACCESS_TOKEN")
    access_token_secret = os.getenv("ACCESS_TOKEN_SECRET")

    # Authenticate
    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)
    return tweepy.API(auth)


def _is_valid_time_since_last_checkpoint(node_stats, staker_stats, max_hours=1) -> bool:
    curr_time = int(time())
    node_ckpt_diff_hours = (curr_time - int(node_stats["blockTime"])) / 3600
    staker_ckpt_diff_hours = (curr_time - int(staker_stats["blockTime"])) / 3600
    print(f"Node checkpoint last updated {node_ckpt_diff_hours:.2f} hours ago")
    print(f"Staker checkpoint last updated {staker_ckpt_diff_hours:.2f} hours ago")

    if node_ckpt_diff_hours > max_hours or staker_ckpt_diff_hours > max_hours:
        print(f"Time since last checkpoint longer than {max_hours} hour(s), skipping tweet")
        return False
    return True


def _tweet_network_stats() -> None:
    node_stats, staker_stats = _fetch_rocketpool_stats()
    should_tweet = _is_valid_time_since_last_checkpoint(node_stats, staker_stats, 1)
    if not should_tweet:
        return

    # ETH stats
    eth_price_usd, active_eth_validators = _fetch_eth_stats()

    # Staking stats
    staker_eth_in_deposit_pool = _wei_to_eth(staker_stats["stakerETHWaitingInDepositPool"])

    # Node stats
    minipool_commission = _wei_to_eth(node_stats["newMinipoolFee"]) * 100
    node_count = int(node_stats["nodesRegistered"])
    staking_minipools = int(node_stats["stakingMinipools"])
    percent_validators = (staking_minipools / active_eth_validators) * 100

    # Token stats
    rETH_price = _wei_to_eth(staker_stats["rETHExchangeRate"])
    rpl_price = _wei_to_eth(node_stats["rplPriceInETH"])
    total_rpl_staked = _wei_to_eth(node_stats["rplStaked"])
    effective_rpl_staked = _wei_to_eth(node_stats["effectiveRPLStaked"])

    tvl = (staking_minipools * ETH_PER_MINIPOOL) + \
            staker_eth_in_deposit_pool + (total_rpl_staked * rpl_price)
    tvl_usd = tvl * eth_price_usd

    msg = TWEET_MSG.format(
        tvl=_pretty_print_num(tvl),
        tvl_usd=_pretty_print_num(tvl_usd),
        staker_eth_in_deposit_pool=_pretty_print_num(staker_eth_in_deposit_pool),
        minipool_commission=minipool_commission,
        node_count=node_count,
        staking_minipools=staking_minipools,
        percent_validators=percent_validators,
        rETH_price=rETH_price,
        rpl_price=rpl_price,
        total_rpl_staked=_pretty_print_num(total_rpl_staked),
        effective_rpl_staked=_pretty_print_num(effective_rpl_staked)
    )

    print(f"Sending tweet:\n{msg}")
    api = _auth_tweepy()
    api.update_status(msg)


def lambda_handler(event, context):
    """Entrypoint for deploying to AWS Lambda"""
    _tweet_network_stats()
    return
