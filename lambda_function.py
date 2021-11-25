import math
import os
from time import time
from typing import Dict, Optional, Tuple, Union

import requests
import tweepy
from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport
from web3 import Web3

TWEET_MSG = """
💰 General
TVL: Ξ{tvl} (${tvl_usd})
Staking Pool Balance: Ξ{staker_eth_in_deposit_pool}

🖥️ Nodes
Commission: {minipool_commission:.2f}%
Registered Nodes: {node_count}
Staking Minipools: {staking_minipools}
ETH Validator Share: {percent_validators:.2f}%

🪙 Tokens
rETH Price: Ξ{rETH_price:.4f} ({rETH_apy:.1f}% APY)
RPL Price: Ξ{rpl_price:.4f}
RPL staked: {total_rpl_staked} RPL
Effective RPL staked: {effective_rpl_staked} RPL
"""

BEACONCHAIN_API_URL = "https://beaconcha.in/api/v1/epoch/latest"
COINGECKO_API_URL = (
    "https://api.coingecko.com/api/v3/coins/ethereum?"
    "localization=false&tickers=false&market_data=true"
    "&community_data=false&developer_data=false&sparkline=false"
)
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
    value = n / 10**(3 * symbol_idx)
    return '{:.{precision}f}{}'.format(
        value,
        NUMBER_SYMBOLS[symbol_idx],
        precision=2 if value < 10 or n < 10000 else 1
    )


def _wei_to_eth(val: Union[str, int]) -> float:
    if type(val) == str:
        val = int(val)
    return float(Web3.fromWei(val, 'ether'))


def _execute_rocketpool_gql(query, variable_values: Optional[Dict] = None) -> Client:
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
    data = client.execute(query, variable_values=variable_values)
    return data


def _fetch_rocketpool_stats() -> Tuple[Dict, Dict]:
    query = gql('''
        query protocolMetrics {
            rocketPoolProtocols {
                lastNetworkNodeBalanceCheckPoint {
                    stakingMinipools
                    queuedMinipools
                    newMinipoolFee
                    nodesRegistered
                    rplPriceInETH
                    rplStaked
                    effectiveRPLStaked
                    blockTime
                }
                lastNetworkStakerBalanceCheckPoint {
                    previousCheckpointId
                    stakerETHWaitingInDepositPool
                    rETHExchangeRate
                    blockTime
                }
            }
        }
    ''')
    data = _execute_rocketpool_gql(query)
    data = data["rocketPoolProtocols"][0]
    node_stats = data["lastNetworkNodeBalanceCheckPoint"]
    staker_stats = data["lastNetworkStakerBalanceCheckPoint"]
    return node_stats, staker_stats


def _fetch_network_staker_balance(checkpointId) -> Dict:
    query = gql('''
        query networkStakerBalanceCheckpoint($checkpointId: ID!) {
            networkStakerBalanceCheckpoint(id: $checkpointId) {
                id
                previousCheckpointId
                rETHExchangeRate
                blockTime
            }
        }
    ''')
    data = _execute_rocketpool_gql(query, variable_values={"checkpointId": checkpointId})
    network_staker_stats = data["networkStakerBalanceCheckpoint"]
    return network_staker_stats


def _fetch_eth_stats() -> Tuple[float, int]:
    # Fetch # of validators from beaconcha.in
    data = requests.get(BEACONCHAIN_API_URL).json()
    active_eth_validators = int(data['data']['validatorscount'])

    # Fetch ETH/USD price from Coingecko
    data = requests.get(COINGECKO_API_URL).json()
    current_price = data['market_data']['current_price']
    eth_price_usd = float(current_price['usd'])
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


def _compute_rETH_apy(staker_stats):
    # Fetch previous checkpoint stats
    prev_staker_stats = _fetch_network_staker_balance(staker_stats["previousCheckpointId"])

    # Calculate time period
    block_time_diff = int(staker_stats["blockTime"]) - int(prev_staker_stats["blockTime"])
    seconds_per_year = 365 * 24 * 60 * 60
    compounding_periods = seconds_per_year / block_time_diff

    # Compute current APY
    current_rate = _wei_to_eth(float(staker_stats["rETHExchangeRate"]))
    prev_rate = _wei_to_eth(float(prev_staker_stats["rETHExchangeRate"]))
    rETH_yield = current_rate / prev_rate
    rETH_apy = 100 * ((rETH_yield**compounding_periods) - 1)
    return rETH_apy


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
    queued_minipools = int(node_stats["queuedMinipools"])
    percent_validators = (staking_minipools / active_eth_validators) * 100

    # Token stats
    rETH_price = _wei_to_eth(staker_stats["rETHExchangeRate"])
    rpl_price = _wei_to_eth(node_stats["rplPriceInETH"])
    total_rpl_staked = _wei_to_eth(node_stats["rplStaked"])
    effective_rpl_staked = _wei_to_eth(node_stats["effectiveRPLStaked"])
    rETH_apy = _compute_rETH_apy(staker_stats)

    tvl = (staking_minipools * ETH_PER_MINIPOOL) + \
            (queued_minipools * STAKER_ETH_PER_MINIPOOL) + \
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
        rETH_apy=rETH_apy,
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
