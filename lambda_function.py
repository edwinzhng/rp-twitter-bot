import decimal
import os
from time import time
from typing import Dict, Tuple, Union

import tweepy
from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport
from web3 import Web3

TWEET_MSG = """
💰 General 💰
Total Value Locked: Ξ {tvl:.4f}
Staking Pool Balance: Ξ {staker_eth_in_deposit_pool:.4f}

🖥️ Nodes 🖥️
Commission: {minipool_commission:.2f}%
Registered Nodes: {node_count}
Staking Minipools: {staking_minipools}

🪙 Tokens 🪙
rETH Price: Ξ {rETH_price:.4f}
RPL Price: Ξ {rpl_price:.4f}
Total RPL staked: {total_rpl_staked:.2f} RPL
Effective RPL staked: {effective_rpl_staked:.2f} RPL
"""

SUBGRAPH_API_URL = (
    "https://gateway.thegraph.com/api/33bade4c82683211e74eec6acd7b8bb6/"
    "subgraphs/id/0xa508c16666c5b8981fa46eb32784fccc01942a71-3"
)
STAKER_ETH_PER_MINIPOOL = 16
ETH_PER_MINIPOOL = 32


def _wei_to_eth(val: Union[str, int]) -> decimal.Decimal:
    if type(val) == str:
        val = int(val)
    return Web3.fromWei(val, 'ether')


def _fetch_stats() -> Tuple[Dict, Dict]:
    transport = RequestsHTTPTransport(
        url=SUBGRAPH_API_URL,
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
                    queuedMinipools
                    withdrawableMinipools
                    stakingUnbondedMinipools
                    totalFinalizedMinipools
                    newMinipoolFee
                    nodesRegistered
                    oracleNodesRegistered
                    rplPriceInETH
                    rplStaked
                    minimumEffectiveRPL
                    maximumEffectiveRPL
                    effectiveRPLStaked
                    blockTime
                }
                lastNetworkStakerBalanceCheckPoint {
                    stakerETHActivelyStaking
                    stakerETHWaitingInDepositPool
                    stakerETHInRocketETHContract
                    stakerETHInProtocol
                    rETHExchangeRate
                    stakersWithAnRETHBalance
                    totalRETHSupply
                    blockTime
                    totalStakerETHRewards
                }
            }
        }
    ''')

    data = client.execute(query)
    data = data["rocketPoolProtocols"][0]
    node_stats = data["lastNetworkNodeBalanceCheckPoint"]
    staker_stats = data["lastNetworkStakerBalanceCheckPoint"]
    return node_stats, staker_stats


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
    if node_ckpt_diff_hours > max_hours or staker_ckpt_diff_hours > max_hours:
        print(f"Time since last checkpoint longer than {max_hours} hour(s), skipping tweet")
        print(f"  Node checkpoint last updated {node_ckpt_diff_hours:.2f} hours ago")
        print(f"  Staker checkpoint last updated {staker_ckpt_diff_hours:.2f} hours ago")
        return False
    return True


def _tweet_network_stats() -> None:
    node_stats, staker_stats = _fetch_stats()
    should_tweet = _is_valid_time_since_last_checkpoint(node_stats, staker_stats, 1)
    if not should_tweet:
        return

    # Staking stats
    staker_eth_in_deposit_pool = _wei_to_eth(staker_stats["stakerETHWaitingInDepositPool"])
    staker_eth_in_protocol = _wei_to_eth(staker_stats["stakerETHInProtocol"])
    eth_used_percent = (staker_eth_in_deposit_pool / staker_eth_in_protocol) * 100

    # Node stats
    minipool_commission = _wei_to_eth(node_stats["newMinipoolFee"]) * 100
    queued_minipool_demand = int(node_stats["queuedMinipools"]) * STAKER_ETH_PER_MINIPOOL
    node_count = int(node_stats["nodesRegistered"])
    staking_minipools = int(node_stats["stakingMinipools"])

    # Token stats
    rETH_price = _wei_to_eth(staker_stats["rETHExchangeRate"])
    rpl_price = _wei_to_eth(node_stats["rplPriceInETH"])
    total_rpl_staked = _wei_to_eth(node_stats["rplStaked"])
    effective_rpl_staked = _wei_to_eth(node_stats["effectiveRPLStaked"])

    tvl = (staking_minipools * ETH_PER_MINIPOOL) + \
            staker_eth_in_deposit_pool + (total_rpl_staked * rpl_price)

    msg = TWEET_MSG.format(
        tvl=tvl,
        staker_eth_in_deposit_pool=staker_eth_in_deposit_pool,
        eth_used_percent=eth_used_percent,
        minipool_commission=minipool_commission,
        queued_minipool_demand=queued_minipool_demand,
        node_count=node_count,
        staking_minipools=staking_minipools,
        rETH_price=rETH_price,
        rpl_price=rpl_price,
        total_rpl_staked=total_rpl_staked,
        effective_rpl_staked=effective_rpl_staked
    )
    print(f"Sending tweet:\n{msg}")

    # Send tweet
    api = _auth_tweepy()
    api.update_status(msg)


def lambda_handler(event, context):
    """Entrypoint for deploying to AWS Lambda"""
    _tweet_network_stats()
    return
